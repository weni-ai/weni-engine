from typing import Optional, Union
from uuid import UUID

import pendulum
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from connect.common.models import (
    Organization,
    OrganizationAuthorization,
    Project,
    ProjectAuthorization,
    ProjectMigration,
    ProjectMigrationStatus,
)
from connect.usecases.project.exceptions import (
    OrganizationNotFoundError,
    ProjectMigrationNotFoundError,
    ProjectMigrationRepublishError,
    ProjectNotFoundError,
    SameOrganizationMigrationError,
)
from connect.usecases.project.migration.eda_publisher import (
    ProjectMigrationEDAPublisher,
)

MODULE_STATUS_SUCCESS = "success"
MODULE_STATUS_ERROR = "error"
MODULE_STATUS_PENDING = "pending"


class MigrateProjectUseCase:
    """Reusable use case for migrating a project between organizations.

    The engine is the source of truth: reassigns Project.organization,
    reconciles ProjectAuthorization, persists a ProjectMigration record,
    then publishes engine.project.migrated on commit.
    """

    ACTIVE_STATUSES = [
        ProjectMigrationStatus.PENDING,
        ProjectMigrationStatus.PUBLISH_FAILED,
        ProjectMigrationStatus.IN_PROGRESS,
        ProjectMigrationStatus.PARTIAL_ERROR,
    ]

    def __init__(self, publisher: Optional[ProjectMigrationEDAPublisher] = None):
        self.publisher = publisher or ProjectMigrationEDAPublisher()

    def execute(
        self,
        project_uuid: Union[UUID, str],
        org_to_uuid: Union[UUID, str],
        requested_by: Optional[str] = None,
    ) -> ProjectMigration:
        try:
            org_to = Organization.objects.get(uuid=org_to_uuid)
        except Organization.DoesNotExist:
            raise OrganizationNotFoundError()

        with transaction.atomic():
            # Lock the project row so concurrent requests cannot both pass the
            # idempotency check and create duplicate migrations.
            try:
                project = (
                    Project.objects.select_for_update()
                    .select_related("organization")
                    .get(uuid=project_uuid)
                )
            except Project.DoesNotExist:
                raise ProjectNotFoundError()

            # Idempotency comes before the same-org guard: a retry after a
            # successful local reassignment still finds the active record.
            existing = (
                ProjectMigration.objects.filter(
                    project=project, status__in=self.ACTIVE_STATUSES
                )
                .order_by("-created_at")
                .first()
            )
            if existing:
                return existing

            if project.organization_id == org_to.uuid:
                raise SameOrganizationMigrationError()

            org_from_uuid = project.organization_id
            project.organization = org_to
            project.save(update_fields=["organization"])
            self._reconcile_project_authorizations(project=project, org_to=org_to)

            migration = ProjectMigration.objects.create(
                project=project,
                org_from=org_from_uuid,
                org_to=org_to.uuid,
                status=ProjectMigrationStatus.PENDING,
                modules_status={},
                requested_by=requested_by,
            )
            migration_uuid = migration.uuid

            transaction.on_commit(
                lambda: self._publish_migration(migration_uuid=migration_uuid)
            )

        return ProjectMigration.objects.get(uuid=migration_uuid)

    def register_module_status(
        self,
        event_id: Union[UUID, str],
        module: str,
        status: str,
        error: Optional[str] = None,
    ) -> ProjectMigration:
        try:
            migration = ProjectMigration.objects.get(uuid=event_id)
        except ProjectMigration.DoesNotExist:
            raise ProjectMigrationNotFoundError()

        modules_status = dict(migration.modules_status or {})
        modules_status[module] = {
            "status": status,
            "error": error,
            "reported_at": pendulum.now("UTC").to_iso8601_string(),
        }
        migration.modules_status = modules_status
        migration.status = self._recompute_status(modules_status)
        migration.save(update_fields=["modules_status", "status", "updated_at"])
        return migration

    def republish(self, event_id: Union[UUID, str]) -> ProjectMigration:
        try:
            migration = ProjectMigration.objects.get(uuid=event_id)
        except ProjectMigration.DoesNotExist:
            raise ProjectMigrationNotFoundError()

        if migration.status != ProjectMigrationStatus.PUBLISH_FAILED:
            raise ProjectMigrationRepublishError()

        self._publish_migration(migration_uuid=migration.uuid)
        return ProjectMigration.objects.get(uuid=migration.uuid)

    def _reconcile_project_authorizations(
        self, project: Project, org_to: Organization
    ) -> None:
        """Relink project auths to destination org auths; drop those without access."""
        authorizations = list(
            ProjectAuthorization.objects.filter(project=project).select_related("user")
        )
        if not authorizations:
            return

        user_ids = [project_auth.user_id for project_auth in authorizations]
        dest_org_auths = {
            org_auth.user_id: org_auth
            for org_auth in OrganizationAuthorization.objects.filter(
                user_id__in=user_ids, organization=org_to
            )
        }
        for project_auth in authorizations:
            dest_org_auth = dest_org_auths.get(project_auth.user_id)
            if dest_org_auth:
                project_auth.organization_authorization = dest_org_auth
                project_auth.save(update_fields=["organization_authorization"])
            else:
                project_auth.delete()

    def _publish_migration(self, migration_uuid: UUID) -> None:
        try:
            migration = ProjectMigration.objects.get(uuid=migration_uuid)
        except ProjectMigration.DoesNotExist:
            return

        try:
            self.publisher.publish_project_migrated(
                event_id=migration.uuid,
                project_uuid=migration.project_id,
                org_from=migration.org_from,
                org_to=migration.org_to,
            )
        except Exception:
            migration.status = ProjectMigrationStatus.PUBLISH_FAILED
            migration.save(update_fields=["status", "updated_at"])
            return

        migration.status = ProjectMigrationStatus.IN_PROGRESS
        migration.published_at = timezone.now()
        migration.save(update_fields=["status", "published_at", "updated_at"])

    def _recompute_status(self, modules_status: dict) -> str:
        expected = list(settings.PROJECT_MIGRATION_EXPECTED_MODULES or [])
        if not expected:
            # Without an expected set we cannot mark COMPLETED automatically.
            has_error = any(
                entry.get("status") == MODULE_STATUS_ERROR
                for entry in modules_status.values()
            )
            return (
                ProjectMigrationStatus.PARTIAL_ERROR
                if has_error
                else ProjectMigrationStatus.IN_PROGRESS
            )

        statuses = [
            (modules_status.get(module) or {}).get("status") for module in expected
        ]

        if any(status == MODULE_STATUS_ERROR for status in statuses):
            return ProjectMigrationStatus.PARTIAL_ERROR

        if all(status == MODULE_STATUS_SUCCESS for status in statuses):
            return ProjectMigrationStatus.COMPLETED

        return ProjectMigrationStatus.IN_PROGRESS
