<!--
SYNC IMPACT REPORT
Version change: unversioned template → 1.0.0 (initial ratification)

Modified principles: none (no prior populated constitution; the previous file was
the unfilled scaffold containing placeholder tokens only)

Added sections:
  - Core Principles
    - I. Layered Architecture (NON-NEGOTIABLE)
    - II. Auth and Tenancy at the API Boundary
    - III. Compatibility and Existing Patterns
    - IV. Tests and Isolation from Real Infrastructure (NON-NEGOTIABLE)
    - V. Simplicity, Observability, and Self-Documenting Code
  - Additional Constraints
  - Development Workflow
  - Governance

Removed sections: none

Follow-up TODOs: none. All placeholders resolved.
-->

# Connect Constitution

Connect (`weni-engine`) is the Weni/VTEX hub for identity, organizations, projects,
billing, and internal APIs. It is a brownfield Django 3.2 + DRF service on Python 3.8
managed with Poetry, licensed MPL-2.0. This constitution governs changes to that
existing system; it MUST NOT be read as license to redesign it.

## Core Principles

### I. Layered Architecture (NON-NEGOTIABLE)

Every request flows in one direction: Views → Use Cases → Services → Clients.

- Views MUST be thin: validate input through a Serializer, build a DTO, compose and
  inject the use case, return a `Response`.
- Views MUST NOT contain business logic, ORM queries, or any `Model.objects.*` call.
- Use Cases own business rules, ORM access, orchestration across services, and domain
  exceptions. Each exposes a public `execute()`.
- Use Cases MUST NOT import `rest_framework` — no `Request`, no `Response`, no
  `status`, no permission classes. They are framework-agnostic.
- Services wrap clients, catch infrastructure errors, and return `None` on failure.
  Services MUST NOT propagate infrastructure exceptions upward.
- Clients own HTTP calls to other Weni modules and external providers.
- Dependencies MUST be injected via `__init__` with an `Optional` parameter and a
  concrete fallback, e.g. `def __init__(self, client: Optional[ClientInterface] = None)`.
- New work MUST prefer extending an existing module under `connect/api/v2` and
  `connect/usecases` over introducing a new abstraction.
- Lazy imports to dodge circular imports are forbidden. A circular import is an
  architecture defect; fix the layering instead.

Rationale: the layer boundary is what keeps business rules testable without HTTP and
keeps external-provider failures from leaking into domain code.

### II. Auth and Tenancy at the API Boundary

Authentication and authorization live only in DRF `permission_classes`.

- Authorization checks MUST NOT appear inside view method bodies or inside use cases.
- `check_object_permissions()` MUST NOT be called by hand. Use DRF's `get_object()` or
  express the rule as a permission class.
- Permissions MUST be composed declaratively with `&` and `|`. Custom permission
  classes MUST inherit from `BasePermission` so composition works.
- User-facing endpoints MUST use `IsAuthenticated` plus the permission the resource
  already requires: `OrganizationHasPermission`
  (`connect/api/v1/organization/permissions.py`), the project-role permissions
  (`IsProjectViewer` / `IsProjectContributor` / `IsProjectModerator` in
  `connect/api/v2/permissions.py`), and `Has2FA` where two-factor is already enforced.
- Internal module-to-module endpoints MUST use `ModuleHasPermission`
  (`connect/api/v1/internal/permissions.py`) or `CanCommunicateInternally`
  (`connect/api/v2/commerce/permissions.py`, backed by `can_communicate_internally`).
- Identity is OIDC/Keycloak. The public identifier exposed toward sibling services is
  `user.email`.
- Existing organization and project authorization semantics MUST be preserved.
  Multi-tenant isolation MUST NOT be weakened by any change.

Rationale: a single, declarative enforcement point is the only version that can be
audited in review; scattered inline checks are how tenant leaks happen.

### III. Compatibility and Existing Patterns

Connect is brownfield. Existing contracts and shapes are the default.

- Public HTTP contracts MUST be preserved unless the spec explicitly changes them.
- New endpoints MUST go under `connect/api/v2`. `connect/api/v1` MUST NOT be expanded
  except when the change is a bugfix in v1.
- Existing models, permission classes, EDA publishers, and internal clients MUST be
  reused rather than duplicated.
- New models MUST use Django's default integer primary key plus a separate
  `uuid = models.UUIDField(default=uuid4, editable=False, unique=True)` as the public
  identifier.
- New models MUST NOT use `uuid` as the primary key. UUID primary keys (`Project`,
  `Organization`, and others) are legacy and MUST NOT be replicated.
- Legacy primary-key shapes MUST NOT be migrated as part of an unrelated change.
- All new code MUST be Python 3.8 and Django 3.2 compatible.
- Configuration MUST go through `django-environ` (`env.str`, `env.bool`, `env.int`,
  `env.json`). Secrets MUST default to `""` and MUST NOT be committed. Feature flags
  MUST use `env.bool()`.

Rationale: every deviation from the established shape becomes a migration cost or a
second way of doing the same thing, both paid for by the next contributor.

### IV. Tests and Isolation from Real Infrastructure (NON-NEGOTIABLE)

- Every new or changed function and branch MUST ship unit or integration tests in the
  same PR.
- Project coverage MUST NOT drop. CI blocks PRs that lower it.
- Tests MUST use `django.test.TestCase` unless an existing sibling test does otherwise.
- When the boundary is Django itself, in-process substitutes (the test database,
  `LocMemCache`) MUST be preferred over mocks.
- When code talks to Redis, S3, sibling Connect services, Lambda, Keycloak, Stripe, or
  RabbitMQ, the client or service MUST be injected and mocked. Tests MUST NOT reach
  live infrastructure.
- Settings that point at Redis, RabbitMQ, or Postgres backends MUST be overridden for
  the duration of the test. New tests that exercise the Django cache MUST use
  `LocMemCache` via `@override_settings`.
- `# pragma: no cover` is permitted only for live-provider bridges, `__main__` blocks,
  and trivial delegations. It MUST NOT be used to skip business logic.
- Test names MUST follow `test_<behavior>`, e.g.
  `test_execute_raises_error_when_input_invalid`.

Rationale: coverage is the only automated check that new branches were reasoned about,
and a suite that touches live infrastructure is a suite that fails for reasons unrelated
to the change under review.

### V. Simplicity, Observability, and Self-Documenting Code

- Classes MUST stay small and single-purpose.
- Names MUST carry intent. Comments explain *why*, never *what*. A block that needs a
  narrative comment MUST be extracted into a private method whose name states the
  purpose.
- Logging MUST use `logger = logging.getLogger(__name__)` with f-strings: `info` at
  meaningful use-case steps, `error` including the relevant identifiers and the
  exception message.
- Fail-safe side effects (status updates, notifications, tracking) MUST log internally
  and MUST NOT raise.
- Celery tasks MUST use `try/finally` for lock cleanup and MUST be named `task_<action>`.
- All identifiers MUST be in English, with suffixes `UseCase`, `Service`, `Client`,
  `DTO`, `Serializer`, `Interface`, `Error`.
- f-strings MUST be preferred over `%` and `.format()`.
- Dead branches (`if x: pass else: ...`), redundant boolean wrapping
  (`if expr: return True else: return False`), redundant truthiness checks, and
  commented-out code MUST NOT be merged.

Rationale: this codebase is read far more often than it is written; clarity at review
time is cheaper than clarity reconstructed six months later.

## Additional Constraints

**File layout.** New files MUST follow the existing domain layout: `views.py`,
`serializers.py`, and `urls.py` kept separate, with `usecases/` holding the use case,
its `dto.py`, and a `tests/` package beside them — as in `connect/api/v2/commerce`
and `connect/usecases/commerce`.

**DTOs.** DTOs MUST be `@dataclass(frozen=True)` immutable value objects, suffixed
`DTO`.

**Models.** Timestamps MUST use `auto_now_add=True` / `auto_now=True` and MUST NOT be
set by hand. A composite or conditional uniqueness rule MUST use `UniqueConstraint`
with an explicit `name` rather than `unique=True`. `(project, ...)` and `(tenant, ...)`
pairs queried on hot paths MUST be indexed in `Meta.indexes`.

**EDA.** Event publishing MUST follow the existing `*EDAPublisher` pattern (see
`connect/usecases/project/eda_publisher.py`,
`connect/usecases/commerce/eda_publisher.py`). Tests for publishers MUST NOT require a
live broker.

**Internal HTTP.** Module-to-module calls MUST use the existing REST clients under
`connect/api/v1/internal`. A parallel internal client stack MUST NOT be added.

**i18n.** User-facing strings MUST go through Django `gettext` and the locale files
already present in `connect/locale` (`en_US`, `es`, `pt_BR`, `ro`).

**Style and branching.** `black` and `flake8` MUST pass via pre-commit. Commits
directly to `main` are forbidden (enforced by `no-commit-to-branch`). Branches MUST be
named `feature/<kebab-case>`, or `fix/`, `refactor/`, `chore/` as appropriate.

## Development Workflow

- Planning and implementation MUST target the current code, not a greenfield redesign.
  A plan that assumes structures Connect does not have is not implementable.
- Every PR description MUST include a `## What` section and a `## Why` section.
- Before merge, all of the following MUST hold:
  - the test suite passes (`poetry run coverage run manage.py test`);
  - `flake8 connect/` is clean;
  - coverage has not decreased (verify locally with
    `poetry run python contrib/compare_coverage.py`; CI runs `contrib/code_check.py`
    and reports coverage to Codecov).
- When a spec's implementation details conflict with this constitution,
  `.cursor/rules`, or the closest existing module, those three are the source of truth.
  The conflict MUST be flagged in the plan rather than silently resolved by diverging.

## Governance

This constitution governs `/speckit-plan`, `/speckit-analyze`, `/speckit-tasks`, and
`/speckit-implement`. It supersedes ad-hoc convention when the two disagree.

Amendments require a documented change to this file, a version bump, and PR review.
Versioning is semantic:

- **MAJOR** — a principle is removed or redefined in a backward-incompatible way.
- **MINOR** — a principle or section is added, or guidance is materially expanded.
- **PATCH** — clarification, wording, or typo fixes with no change in meaning.

Compliance is a review gate, not a suggestion. A PR that violates a MUST is
incomplete even if its tests pass.

Where existing code already violates a principle, new code MUST NOT copy the
violation. The plan MUST carry a short note about the pre-existing violation; a
drive-by rewrite MUST NOT be included unless that refactor is the declared scope of
the spec.

**Version**: 1.0.0 | **Ratified**: 2026-09-01 | **Last Amended**: 2026-09-01
