"""Use case for retrieving the cached billing plan status of a project.

The status is consumed by internal services (e.g. the retail/commerce module)
that need to know, with high frequency, whether a project is on trial. The
result is cached in Redis to avoid hitting the database on every request and
proactively invalidated by signals whenever the underlying BillingPlan or
Organization changes.
"""

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

from connect.common.models import BillingPlan, Project
from connect.usecases.project.exceptions import ProjectNotFoundError

logger = logging.getLogger(__name__)

CACHE_KEY_TEMPLATE = "project:plan-status:{project_uuid}"


def build_cache_key(project_uuid: str) -> str:
    """Return the canonical cache key for a project's plan status."""
    return CACHE_KEY_TEMPLATE.format(project_uuid=str(project_uuid))


def _empty_payload(project_uuid, organization_uuid=None) -> Dict[str, Any]:
    """Return a default payload for projects without a BillingPlan."""
    return {
        "project_uuid": str(project_uuid),
        "organization_uuid": (
            str(organization_uuid) if organization_uuid else None
        ),
        "plan": None,
        "is_trial": False,
        "is_trial_active": False,
        "is_active": False,
        "is_suspended": False,
    }


class GetProjectPlanStatusUseCase:
    """Return the billing plan status payload for a given project."""

    def __init__(self, cache_backend=None, ttl: Optional[int] = None) -> None:
        self._cache = cache_backend or cache
        self._ttl = ttl if ttl is not None else getattr(
            settings, "PLAN_STATUS_CACHE_TTL", 900
        )

    def execute(self, project_uuid: str) -> Dict[str, Any]:
        cache_key = build_cache_key(project_uuid)

        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug(
                "plan-status cache hit", extra={"project_uuid": str(project_uuid)}
            )
            return cached

        payload = self._build_payload(project_uuid)
        self._cache.set(cache_key, payload, self._ttl)
        logger.debug(
            "plan-status cache miss; payload cached",
            extra={"project_uuid": str(project_uuid), "ttl": self._ttl},
        )
        return payload

    def _build_payload(self, project_uuid: str) -> Dict[str, Any]:
        # Fetch only the raw columns we need with a single SQL query.
        # `.values()` skips Project/Organization/BillingPlan model instantiation
        # (and their signals/FieldTracker overhead), which keeps cache misses
        # cheap on this hot path.
        row = (
            BillingPlan.objects.filter(
                organization__project__uuid=project_uuid
            )
            .values(
                "plan",
                "is_active",
                "organization__uuid",
                "organization__is_suspended",
            )
            .first()
        )

        if row is None:
            # No BillingPlan attached: confirm the project itself exists so we
            # can return a 404 instead of a misleading "no plan" payload.
            project = (
                Project.objects.filter(uuid=project_uuid)
                .values("organization__uuid")
                .first()
            )
            if project is None:
                raise ProjectNotFoundError()
            return _empty_payload(
                project_uuid=project_uuid,
                organization_uuid=project["organization__uuid"],
            )

        plan = row["plan"]
        is_active = bool(row["is_active"])
        is_suspended = bool(row["organization__is_suspended"])
        is_trial = plan == BillingPlan.PLAN_TRIAL

        return {
            "project_uuid": str(project_uuid),
            "organization_uuid": str(row["organization__uuid"]),
            "plan": plan,
            "is_trial": is_trial,
            "is_trial_active": is_trial and is_active and not is_suspended,
            "is_active": is_active,
            "is_suspended": is_suspended,
        }


def invalidate_project_plan_status(project_uuid) -> None:
    """Drop the cached plan status for a single project."""
    cache.delete(build_cache_key(project_uuid))


def invalidate_organization_plan_status(organization) -> None:
    """Drop the cached plan status for every project of an organization."""
    project_uuids = list(
        organization.project.values_list("uuid", flat=True)
    )
    if not project_uuids:
        return
    cache.delete_many(
        [build_cache_key(project_uuid) for project_uuid in project_uuids]
    )
