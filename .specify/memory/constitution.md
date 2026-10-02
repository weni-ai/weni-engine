<!--
SYNC IMPACT REPORT
Version change: 1.0.0 → 1.1.0 (MINOR: principles added and guidance materially
expanded; no existing principle removed or redefined incompatibly)

Modified principles:
  - II. Auth and Tenancy at the API Boundary
      → II. Never Trust the Client: Auth, Tenancy, and Input at the Boundary
        (absorbs backend "Never Trust the Client")
  - III. Compatibility and Existing Patterns
      → III. Compatibility, Versioned Contracts, and Existing Patterns
        (absorbs root "Versioned Contracts")
  - IV. Tests and Isolation from Real Infrastructure
      → IV. Tests Exercise Flows, Isolated from Real Infrastructure
        (absorbs backend "Tests Exercise Flows")
  - V. Simplicity, Observability, and Self-Documenting Code
      → V. Explicit, Self-Documenting Code
        (absorbs backend "Explicit Over Clever"; logging rules moved to VI)

Added principles:
  - VI. Observability and Diagnosable Errors (root "Observability" + backend
    "Diagnosable Errors"; receives the logging rules formerly in V)
  - VII. Fail Gracefully, Retry Within Bounds (backend "Fail Gracefully and
    Predictably" + "Bounded Retry Over REST")
  - VIII. Stateless Services and Declared Peak Load (backend "Scalability and
    Peak Load")
  - IX. Security and Secrets (root)
  - X. Specification Traceability and No Silent Divergence (root)
  - XI. Contained Changes (backend; the former Governance note on drive-by
    rewrites is now a principle)
  - XII. Version Control, Commits, and Changelog (root "Version Control and
    Review" + "Commit Messages" + "Changelog Maintenance")

Added sections: none (Additional Constraints, Development Workflow, Governance
retained and amended)

Removed sections: none

Templates reviewed (not modified, per setup-engineering scope):
  - .specify/templates/plan-template.md — "Constitution Check" gate is generic and
    remains compatible ✅
  - .specify/templates/spec-template.md — lacks the mandatory
    "Inheritance from Product Spec" section ⚠ (see TODO)
  - .specify/templates/tasks-template.md — compatible ✅

Follow-up TODOs (pre-existing gaps against new MUSTs; new code MUST NOT copy them):
  - TODO(SPEC_TEMPLATE): spec-template.md does not open with the inheritance
    section required by Principle X; add it through a Speckit template override.
  - TODO(SPEC_001_INHERITANCE): specs/001-enterprise-okta-sso/spec.md uses a table
    instead of the mandated bullet format and has no "Architecture doc" field.
  - TODO(SPEC_PEAK_LOAD): existing engineering specs do not declare peak load
    (Principle VIII).
  - TODO(HTTP_TIMEOUTS): roughly 72 of 76 production `requests.*` calls under
    connect/ have no explicit `timeout` (Principle VII).
  - TODO(STRUCTURED_LOGS): LOGGING uses a plain-text "verbose" formatter; a
    structured (JSON) formatter is pending (Principle VI).
  - TODO(SENTRY_CONTEXT): connect/sentry/apps.py does not attach project,
    organization, user, and trace identifiers to events (Principle VI).
  - TODO(DEPENDENCY_SCAN): CI (.github/workflows/ci.yml) runs no dependency
    vulnerability check (Principle IX).
  - TODO(BRANCH_PROTECTION): platform branch protection on `main` (required review
    + required CI) could not be verified from the workspace; only the local
    `no-commit-to-branch` hook was observed (Principle XII).
  - TODO(VERSION_SOURCE): CHANGELOG.md is at 3.63.0 while pyproject.toml declares
    1.0.12; the release version source of truth must be unified (Principle XII).

Provenance:
  - Source: weni-ai/vtex-cx-engineering-constitutions (main)
  - Files: base-constitution.md, backend/base-constitution.md
  - Domains: backend
  - Project layer: previous .specify/memory/constitution.md v1.0.0 (2026-09-01)
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
- Services wrap clients, catch infrastructure errors, log them, and return `None` on
  failure. Services MUST NOT propagate infrastructure exceptions upward.
- Clients own HTTP calls to other Weni modules and external providers.
- Dependencies MUST be injected via `__init__` with an `Optional` parameter and a
  concrete fallback, e.g. `def __init__(self, client: Optional[ClientInterface] = None)`.
- New work MUST prefer extending an existing module under `connect/api/v2` and
  `connect/usecases` over introducing a new abstraction.
- Lazy imports to dodge circular imports are forbidden. A circular import is an
  architecture defect; fix the layering instead.

**Rationale:** the layer boundary is what keeps business rules testable without HTTP
and keeps external-provider failures from leaking into domain code.

### II. Never Trust the Client: Auth, Tenancy, and Input at the Boundary

Everything that reaches Connect from outside — the web app, a mobile client, a
third-party webhook, a sibling Weni module, or an EDA message — MUST be treated as
potentially malicious, incomplete, or incorrect until validated on the server.

- Every external input MUST be validated for type, format, range, and business rules
  at the boundary before use: a DRF Serializer for HTTP (including internal and
  webhook endpoints), and explicit payload validation for EDA consumers and gRPC.
- Authorization MUST be enforced on the server for every request, regardless of any
  check already performed by the client or by the calling module.
- Authentication and authorization live only in DRF `permission_classes`.
  Authorization checks MUST NOT appear inside view method bodies or inside use cases.
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

**Rationale:** clients run outside the server's control and can be inspected,
modified, or bypassed; only server-side validation prevents injection, data
corruption, and privilege escalation. A single, declarative enforcement point is the
only version that can be audited in review — scattered inline checks are how tenant
leaks happen.

### III. Compatibility, Versioned Contracts, and Existing Patterns

Connect is brownfield. Existing contracts and shapes are the default.

- Public interfaces — HTTP endpoints, EDA event payloads, and gRPC/protobuf
  messages — MUST evolve backward compatibly or ship with an announced deprecation
  path. Silent breaking changes MUST NOT be introduced.
- A breaking change to an HTTP contract MUST be expressed as a new API major
  (`/v1` → `/v2`), never as an in-place change to an existing route.
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
  `env.json`). Feature flags MUST use `env.bool()`.

**Rationale:** consumers (webapp, Flows, Intelligence, Chats, Integrations, Insights)
depend on stable contracts; explicit versioning and deprecation give them a
predictable path to adapt without outages. Every deviation from the established shape
becomes a migration cost or a second way of doing the same thing.

### IV. Tests Exercise Flows, Isolated from Real Infrastructure (NON-NEGOTIABLE)

- Every flow MUST have at least one test covering the complete use case, from input
  (view, consumer, or task entry point) to resulting effect (persisted state,
  response, published event, or outbound call on the mocked boundary).
- Every flow MUST cover its success path and its failure paths. An error path that
  no test exercises MUST NOT be considered covered.
- Method-level tests SHOULD be used for edge cases and input variations, but MUST NOT
  be the only coverage a flow has.
- Every new or changed function and branch MUST ship unit or integration tests in the
  same PR. Project coverage MUST NOT drop; CI blocks PRs that lower it.
- Tests MUST use `django.test.TestCase` unless an existing sibling test does otherwise.
- When the boundary is Django itself, in-process substitutes (the test database,
  `LocMemCache`) MUST be preferred over mocks.
- When code talks to Redis, S3, sibling Weni services, Lambda, Keycloak, Stripe, or
  RabbitMQ, the client or service MUST be injected and mocked. Tests MUST NOT reach
  live infrastructure.
- Settings that point at Redis, RabbitMQ, or Postgres backends MUST be overridden for
  the duration of the test. New tests that exercise the Django cache MUST use
  `LocMemCache` via `@override_settings` with a `LOCATION` unique to the test class.
- `# pragma: no cover` is permitted only for live-provider bridges, `__main__` blocks,
  and trivial delegations. It MUST NOT be used to skip business logic.
- Test names MUST follow `test_<behavior>`, e.g.
  `test_execute_raises_error_when_input_invalid`.

**Rationale:** a suite made only of isolated method tests can be green while the
composition is broken, and failure paths are the least exercised in development and
the most expensive in production. A suite that touches live infrastructure fails for
reasons unrelated to the change — and passes locally only because Redis and RabbitMQ
happen to be running.

### V. Explicit, Self-Documenting Code

- What a piece of code does MUST be evident where it happens. Hidden side effects and
  implicit control flow MUST NOT be introduced to save lines.
- Any literal that carries meaning — a threshold, a limit, a timeout, a retry count,
  a page size — MUST be a named constant or an `env.*` setting, never an inline value.
  Literals with no meaning beyond their value (an index of 0, an increment of 1) are
  exempt.
- Classes MUST stay small and single-purpose.
- Names MUST carry intent. Comments explain *why* — the constraint, the trade-off, the
  non-obvious reason — never *what*. A block that needs a narrative comment MUST be
  extracted into a private method whose name states the purpose.
- Fail-safe side effects (status updates, notifications, tracking) MUST log internally
  and MUST NOT raise.
- Celery tasks MUST use `try/finally` for lock cleanup and MUST be named `task_<action>`.
- All identifiers MUST be in English, with suffixes `UseCase`, `Service`, `Client`,
  `DTO`, `Serializer`, `Interface`, `Error`.
- f-strings MUST be preferred over `%` and `.format()`.
- Dead branches (`if x: pass else: ...`), redundant boolean wrapping
  (`if expr: return True else: return False`), redundant truthiness checks, and
  commented-out code MUST NOT be merged.

**Rationale:** this codebase is read far more often than it is written, usually by
someone without the context that made the clever version feel obvious. An unexplained
literal is a decision nobody can review, because its origin and safe range are
invisible.

### VI. Observability and Diagnosable Errors

- Logging MUST use `logger = logging.getLogger(__name__)` with f-strings: `info` at
  meaningful use-case steps, `error` including the relevant identifiers and the
  exception message.
- Logs MUST be structured: each entry MUST carry a stable event name and its context
  as `key=value` fields (e.g. `project_migration_failed: project_uuid=... error=...`)
  so it can be parsed and filtered, never free prose alone.
- Logs and error reports MUST NOT contain secrets, tokens, or sensitive personal data
  (names, e-mail addresses, phone numbers, government identifiers). `user.email` MAY
  cross service contracts (Principle II) but MUST NOT be written to logs or error
  reports.
- Errors MUST be traceable across components through the Elastic APM trace
  identifier (`trace.id` / W3C `traceparent`) already provided by
  `elasticapm.contrib.django`; outbound calls and published events SHOULD propagate it.
- Every error sent to Sentry MUST carry, at minimum, the project identifier
  (`Project.uuid`), the account identifier (`Organization.uuid`), an opaque user
  identifier (never the e-mail), and the trace identifier of the request, when those
  exist in the flow.
- Sentry MUST keep `send_default_pii` disabled.

**Rationale:** structured, privacy-safe telemetry is what makes incidents diagnosable
without creating new data-exposure risks. An error without identifying context can be
counted but not investigated; opaque identifiers give exactly the filtering an
investigation needs.

### VII. Fail Gracefully, Retry Within Bounds

- Every call to an external dependency (HTTP via `requests`, gRPC, Keycloak, Stripe,
  S3, Elasticsearch, RabbitMQ) MUST have an explicit timeout sourced from a named
  constant or `env.int` setting, and MUST NOT block indefinitely.
- Failures MUST be handled explicitly and surfaced as consistent, well-defined error
  responses — never as unhandled crashes or leaked stack traces and internal details.
  A Service returning `None` (Principle I) MUST be translated by the use case into a
  defined domain error or a documented fallback.
- When data is propagated to another service over REST, a failed call MUST be retried
  rather than dropped.
- A retry MUST be attempted only on failures that could plausibly succeed on another
  attempt — connection error, timeout, HTTP 5xx, HTTP 429 — and MUST NOT be attempted
  on any other 4xx.
- A retry MUST only be applied to an operation that is idempotent or protected by a
  deduplication key (e.g. the resource `uuid`). A non-idempotent operation MUST be made
  idempotent rather than left without retry.
- Every retry policy (Celery `autoretry_for` / `max_retries` / `retry_backoff`, or a
  bounded client-side loop) MUST define a maximum number of attempts and a backoff
  strategy as named constants or settings. Unbounded retry MUST NOT be used.
- When attempts are exhausted, the failure MUST be logged at `error` level and MUST
  remain recoverable (persisted status, re-runnable task, or reconciliation path). It
  MUST NOT be silently discarded.

**Rationale:** every external dependency eventually fails. Propagation between
services fails for transient reasons far more often than permanent ones, so bounded
retry keeps services converging; retrying a request rejected on its merits, or a
non-idempotent one, amplifies load or duplicates effects instead of repairing them.

### VIII. Stateless Services and Declared Peak Load

- The web (gunicorn/gevent), Celery worker, and EDA consumer processes MUST be
  stateless: state that outlives a single request or task MUST NOT live in process
  memory or on local disk, and MUST live in a shared external store (Postgres, Redis,
  S3).
- Process-local caches MUST NOT hold data whose staleness changes behaviour across
  instances; shared caching MUST go through the Django cache backed by Redis.
- Every engineering spec MUST declare the peak load the affected flow is expected to
  sustain, stated as peak (requests/s, events/s, or tasks/min) and not as average.

**Rationale:** capacity is a design input, not something discovered during an
incident. Statelessness is what makes adding instances a valid answer to load;
declaring the peak turns scalability into a reviewable number.

### IX. Security and Secrets

- Secrets MUST never be committed. They MUST be injected at runtime from the
  platform's secrets manager into environment variables read via `django-environ`, and
  secret settings MUST default to `""`. `.env` files MUST stay git-ignored.
- Access MUST follow least privilege by default: internal endpoints MUST be restricted
  to the modules that need them (Principle II), and service credentials MUST be scoped
  to their purpose.
- Dependencies MUST come only from trusted sources (PyPI and the pinned
  `weni-ai` packages) through `poetry.lock`, and MUST be checked for known
  vulnerabilities.

**Rationale:** leaked credentials and untrusted dependencies are among the most common
and most damaging breaches; prevention is far cheaper than remediation.

### X. Specification Traceability and No Silent Divergence

- Every engineering spec under `specs/` MUST derive from exactly one approved product
  spec and MUST reference it through an immutable, pinned version (commit or tag). A
  mutable URL or ID alone MUST NOT be used. The product spec MUST exist and be tagged
  before its engineering spec is created.
- An engineering spec MUST NOT redefine the "what" it inherits: problem, scope,
  success criteria, and binding decisions belong to the product spec.
- A technical architecture document SHOULD be produced for non-trivial features; when
  it exists it MUST be linked and pinned by commit/tag. Its absence MUST NOT block the
  engineering spec.
- Every engineering spec MUST open with an inheritance section in exactly this format:

  ```
  ## Inheritance from Product Spec
  - Product Spec: <title> — <URL>
  - Pinned version: <commit/tag>
  - Architecture doc: <none | URL + commit/tag>
  - Inherited binding decisions: <short list>
  - Scope of this spec: <slice implemented by this repo>
  - Divergences: <none | link to amendment>
  ```

- When a technical need contradicts something inherited — scope, success criteria, or
  a binding decision — it MUST NOT be implemented silently. It MUST be raised as an
  amendment in the product repository and recorded in `Divergences`; once approved
  and tagged, `Pinned version` MUST be updated.
- A technical difference that contradicts nothing inherited is an implementation
  decision and MUST live in the engineering spec.

**Rationale:** pinning guarantees every repository implements the same version of the
feature; forcing divergences through amendments keeps the product spec authoritative
and every decision traceable. A single format keeps the link machine-checkable.

### XI. Contained Changes

- A change MUST be limited to the context it was asked to address. Refactoring,
  renaming, reformatting, or behaviour adjustments outside that context MUST NOT ride
  along; each belongs to its own change.
- Where existing code already violates a principle, new code MUST NOT copy the
  violation, and the plan MUST carry a short note about it; a rewrite MUST NOT be
  included unless that refactor is the declared scope of the spec.
- A change that stays within scope MAY span several commits (Principle XII).

**Rationale:** a change that reaches beyond its stated scope is a change nobody
reviewed on purpose; it hides the intended fix and turns a revert into a choice
between losing the fix and keeping an unrelated regression.

### XII. Version Control, Commits, and Changelog

- All code MUST enter `main` through a pull request with at least one approved review
  and a green CI run. Direct pushes to `main` MUST be blocked by GitHub branch
  protection; the local `no-commit-to-branch` hook is a convenience, not the control.
- Commits MUST follow Conventional Commits, `<type>: <description>`, with type in
  `feat`, `fix`, `docs`, `refactor`, `test`, `chore`. The description MUST be
  imperative, specific, and at most 50 characters. Commits MUST be atomic.
- PR titles MUST use the same type set and SHOULD stay within 72 characters.
- Connect is a deployed service, not a public library; it keeps `CHANGELOG.md` in its
  own format (`# <version>` followed by `- <type>: <description>` entries). Every
  user-facing change MUST be recorded there under a SemVer-bumped version.

**Rationale:** the review policy is only real when enforced by the platform.
Conventional, atomic commits enable automated changelogs and make bisecting and
reverting cheap; a SemVer-aligned changelog communicates impact to consuming modules.

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
`connect/usecases/commerce/eda_publisher.py`). Event payloads are public contracts
(Principle III). Tests for publishers MUST NOT require a live broker.

**Internal HTTP.** Module-to-module calls MUST use the existing REST clients under
`connect/api/v1/internal`. A parallel internal client stack MUST NOT be added. New or
touched calls MUST satisfy Principle VII (timeouts, bounded retry).

**i18n.** User-facing strings MUST go through Django `gettext` and the locale files
already present in `connect/locale` (`en_US`, `es`, `pt_BR`, `ro`).

**Style and branching.** `black` and `flake8` MUST pass via pre-commit. Branches MUST
be named `feature/<kebab-case>`, or `fix/`, `refactor/`, `chore/` as appropriate.

## Development Workflow

- Planning and implementation MUST target the current code, not a greenfield redesign.
  A plan that assumes structures Connect does not have is not implementable.
- Every engineering spec MUST satisfy Principle X (inheritance section) and
  Principle VIII (declared peak load) before `/speckit-plan` runs.
- Every PR description MUST include a `## What` section and a `## Why` section.
- Before merge, all of the following MUST hold:
  - the test suite passes (`poetry run coverage run manage.py test`);
  - `flake8 connect/` is clean;
  - coverage has not decreased (verify locally with
    `poetry run python contrib/compare_coverage.py`; CI runs `contrib/code_check.py`
    and reports coverage to Codecov).
- When a spec's implementation details conflict with this constitution,
  `.cursor/rules`, or the closest existing module, those three are the source of truth
  for *how* to build. The conflict MUST be flagged in the plan rather than silently
  resolved by diverging. When the conflict touches *what* was inherited from the
  product spec, the amendment route of Principle X applies instead.

## Governance

This constitution governs `/speckit-plan`, `/speckit-analyze`, `/speckit-tasks`, and
`/speckit-implement`. It supersedes ad-hoc convention when the two disagree. Plans
MUST pass the Constitution Check gate; `/speckit-analyze` MUST treat any conflict with
a MUST as CRITICAL.

Precedence: the VTEX CX root engineering constitution prevails over the backend
domain constitution, which prevails over the Connect project layer. A project-level
exception to an inherited article MUST be stated in the article with its
justification.

Amendments require a documented change to this file, a version bump, and PR review.
Versioning is semantic:

- **MAJOR** — a principle is removed or redefined in a backward-incompatible way.
- **MINOR** — a principle or section is added, or guidance is materially expanded.
- **PATCH** — clarification, wording, or typo fixes with no change in meaning.

Compliance is a review gate, not a suggestion. A PR that violates a MUST is
incomplete even if its tests pass. Known pre-existing gaps are tracked in the Sync
Impact Report at the top of this file and are handled per Principle XI.

**Version**: 1.1.0 | **Ratified**: 2026-09-01 | **Last Amended**: 2026-10-01
