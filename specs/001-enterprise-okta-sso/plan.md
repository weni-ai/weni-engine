# Implementation Plan: Enterprise Okta login — Connect organization access policy

**Branch**: `001-enterprise-okta-sso` | **Date**: 2026-09-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-enterprise-okta-sso/spec.md`

## Summary

Connect already enforces, per organization, that members sign in through an
allowed SSO provider without a platform password. This delivery is a **scoped
delta** over that layer, not a new subsystem. It does five things:

1. Lets a policy name **one specific customer's** identity source, by replacing
   the `google | microsoft` `ChoiceField` with a slug-shaped validated value —
   keeping `google` and `microsoft` valid and keeping `okta-acme` and
   `okta-beta` permanently distinct.
2. Adds one boolean, `requires_customer_identity_source`, that scopes new
   **fail-closed** rules to organizations this delivery enables, so an empty
   allowlist denies there and keeps meaning "allow any" everywhere else.
3. Moves policy validation into **one** use case that both the operator path
   and the existing admin path call with the *resulting* state, so an invariant
   cannot hold on one path and not the other.
4. Adds an operator-only **management command** to enable, update and disable a
   customer binding — idempotent, list-replacing, no HTTP surface.
5. Fixes `can_update_password`, which today tells support-domain staff that
   password management is unavailable.

The technical approach is settled in [research.md](./research.md) (R1–R8).
Roughly 60% of the requirements are satisfied by test coverage over behaviour
that already holds; the code delta is one field, one migration, one new module,
one new use case, one command, one new enum value, and one early return.

## Technical Context

**Language/Version**: Python 3.8

**Primary Dependencies**: Django 3.2.16, Django REST Framework 3.12.4,
`mozilla-django-oidc` 2.0, `python-keycloak` 0.25, Poetry

**Storage**: PostgreSQL. Latest migrations: `connect/common` 0099,
`connect/authentication` 0021. This delivery adds `connect/common` 0100 (schema
only, no `RunPython`)

**Testing**: `django.test.TestCase`; `unittest.mock.patch` and injected fakes at
the Keycloak boundary; `LocMemCache` via `@override_settings`; coverage must not
drop (`contrib/compare_coverage.py`)

**Target Platform**: Linux server (existing Django + DRF service)

**Project Type**: Existing Django + DRF service — brownfield extension

**Performance Goals**: No new per-request Keycloak call. The fail-closed branch
short-circuits before the credential lookup, so an incomplete policy costs
strictly less than today's evaluation

**Constraints**: No new v1 endpoints; no new merchant-facing or admin surface;
no migration may rewrite policy on organizations this delivery does not enable;
the `access_status` / `access_disabled_reason` / `sso_config` contract stays
backward compatible on both v1 and v2

**Scale/Scope**: Single-digit customer-identity organizations at go-live, tens
later. FR-010's cross-organization domain check is sized for that (R6)

## Constitution Check

*GATE: passed before Phase 0; re-evaluated after Phase 1 — see below.*

| Principle | Gate | Verdict |
| --- | --- | --- |
| **I. Layered architecture** | New rules live in use cases, not models or views. Dependencies injected via `Optional` `__init__`. No lazy imports added | **PASS** — R3 lifts the fail-closed branch into `EvaluateOrganizationSSOAccessUseCase` rather than onto `OrganizationSSOConfig`; R4 puts validation in `ValidateOrganizationSSOPolicyUseCase`; the management command is a composition root with no logic |
| **II. Auth at the API boundary** | No new authorization in view bodies or use cases | **PASS** — no permission class changes. `HasSSOAccess` picks up the new refusal automatically because it calls the same use case |
| **III. Compatibility and existing patterns** | No new v1 endpoints; new endpoints under v2; existing models reused; Python 3.8 / Django 3.2 | **PASS with two flagged v1 changes** — see Complexity Tracking. No endpoint is added anywhere, in v1 or v2 |
| **IV. Tests and isolation** | Every changed branch tested; no live infrastructure; coverage must not drop | **PASS** — Keycloak injected and faked; cache via `LocMemCache`; the four named suites extended (Phase 1 test map) |
| **V. Simplicity and observability** | Small classes, intent-carrying names, `logger` with f-strings, no dead branches | **PASS** — the incomplete-policy refusal logs at `warning` with organization, member and resolved source (FR-028) |

**Pre-existing violations this delivery works alongside** (governance requires
naming them; a drive-by rewrite is explicitly excluded): business rules on
`OrganizationSSOConfig`; a function-local import in
`serialize_organization_access_status`; a use case reaching into a DRF view in
`enrich_serializer_context_with_sso_access`; v2 serializers importing v1
helpers; authorization in the `sso-settings` view body; `# pragma: no cover`
over `change_password`. Each is tabulated with its rationale in
[research.md](./research.md#pre-existing-constitution-violations-this-delivery-works-alongside).

**Post-Phase-1 re-evaluation**: no gate moved. Phase 1 added no model methods,
no view logic, no endpoint and no abstraction beyond the two modules named in
R4 and R5. The one thing design surfaced that the pre-Phase-0 check did not
anticipate is that FR-024 needs **no** path-specific code once the marker
implies `is_enabled` (R4), which removed a branch rather than adding one.

## Project Structure

### Documentation (this feature)

```text
specs/001-enterprise-okta-sso/
├── spec.md                  # Ratified engineering spec (input)
├── plan.md                  # This file
├── research.md              # Phase 0 — R1…R8, baseline, pre-existing violations
├── data-model.md            # Phase 1 — field, invariants, state transitions
├── quickstart.md            # Phase 1 — runnable validation guide
├── contracts/
│   ├── organization-access.md          # HTTP contract delta (v1 + v2)
│   └── enable-customer-identity-source.md  # Operator command contract
├── checklists/
│   └── requirements.md      # Pre-existing
└── tasks.md                 # Phase 2 — NOT created by /speckit-plan
```

### Source Code (repository root)

Files this delivery touches, all inside the existing domain layout:

```text
connect/
├── common/
│   ├── models.py                                      # +1 field on OrganizationSSOConfig (R1)
│   ├── migrations/
│   │   └── 0100_organizationssoconfig_requires_customer_identity_source.py  # NEW, schema only
│   └── management/commands/
│       └── enable_customer_identity_source.py         # NEW, operator entry point (R5)
├── usecases/organizations/
│   ├── sso_policy.py                                  # NEW — DTO, normalizers, shared validator (R4)
│   ├── enable_customer_identity_source.py             # NEW — operator use case (R5)
│   ├── sso_access.py                                  # +SSO_POLICY_INCOMPLETE, +fail-closed branch (R3, R7)
│   ├── update_sso_config.py                           # calls the shared validator (R4)
│   ├── exceptions.py                                  # +SSOPolicyValidationError
│   └── tests/
│       ├── test_sso_access.py                         # EXTEND
│       ├── test_update_sso_config.py                  # EXTEND
│       ├── test_sso_policy.py                         # NEW — shared validator
│       └── test_enable_customer_identity_source.py    # NEW — use case + command
└── api/v1/
    ├── organization/serializers.py                    # provider child field widened (R2)
    ├── account/serializers.py                         # get_can_update_password early return (R8)
    └── tests/
        └── test_sso_enforcement.py                    # EXTEND — v1 + v2 contract
```

**Structure Decision**: no new package, no new API module. Every new file lands
beside its existing sibling in `connect/usecases/organizations` (which already
holds `sso_access.py`, `update_sso_config.py`, `exceptions.py` and a `tests/`
package) or in `connect/common/management/commands` (which already holds
`grpc.py`). This follows constitution I's "prefer extending an existing module
over introducing a new abstraction" and the Additional Constraints file layout.

**No endpoint is created.** R5 chose a management command over an internal v2
endpoint, so constitution III's "new endpoints MUST go under `connect/api/v2`"
is satisfied vacuously rather than by placement. Two v1 *files* change; neither
change adds a route or a field (see Complexity Tracking).

## Implementation phases

Ordered so that each step is independently reviewable and nothing is merged
that could enable fail-closed evaluation before its validation exists.

### Step 1 — Shared policy vocabulary and validator (R2, R4, R6)

`connect/usecases/organizations/sso_policy.py`: `OrganizationSSOPolicyDTO`
(frozen dataclass), `normalize_identity_source`, `normalize_email_domain`,
`ValidateOrganizationSSOPolicyUseCase`. `SSOPolicyValidationError` added to
`exceptions.py`. Nothing calls it yet, so this step cannot change behaviour.
Invariants and their requirement mapping: [data-model.md](./data-model.md).

### Step 2 — The marker field and its migration (R1)

One `BooleanField(default=False)` on `OrganizationSSOConfig`; migration `0100`
containing a single `AddField` and **no** `RunPython`. Deliberately not added to
`OrganizationSSOConfigSerializer.Meta.fields` — that omission is what enforces
FR-023, so it needs a comment in the review, not in the code, plus the test in
Step 6.

### Step 3 — Scoped fail-closed evaluation (R3, R7)

`SSO_POLICY_INCOMPLETE = "sso_policy_incomplete"` added to
`OrganizationSSOAccessDisabledReason`. A private
`_refuse_incomplete_policy(config)` early return in
`EvaluateOrganizationSSOAccessUseCase.evaluate`, placed after the
support-domain bypass and before provider resolution, guarded by the marker.
`logger.warning` naming the organization, the member and the resolved source.
The model's `is_provider_allowed` / `is_email_domain_allowed` are **not**
touched.

### Step 4 — Admin path validation (R2, R4)

`OrganizationSSOConfigSerializer.allowed_sso_providers` child becomes a
`CharField` normalized through `normalize_identity_source`;
`validate_allowed_email_domains` delegates to `normalize_email_domain`.
`UpdateOrganizationSSOConfigUseCase` merges stored state with the DTO, calls
`ValidateOrganizationSSOPolicyUseCase` on the **resulting** state, and only then
runs `_validate_actor_not_locked_out` — that order matters so an incomplete
policy is reported as such rather than as a lockout. The view maps
`SSOPolicyValidationError` to a 400 the same way it already maps
`SSOConfigLockoutError`.

### Step 5 — Operator procedure (R5, R6)

`EnableCustomerIdentitySourceUseCase` and the
`enable_customer_identity_source` management command. Idempotency is a
short-circuit on an unchanged resulting state (no `save()`, so `updated_at`
does not move); list replacement is a property of the argument shape;
`transaction.atomic()` around the whole operation; `--dry-run` validates and
prints without persisting. Contract:
[contracts/enable-customer-identity-source.md](./contracts/enable-customer-identity-source.md).

### Step 6 — Support-domain password fix (R8)

One early return in `get_can_update_password` reusing
`is_sso_internal_bypass_email`. Argued as a v1 bugfix in R8; the unenforced
`change_password` write path is **reported, not changed**.

### Step 7 — Tests, then docs

Test map below; documentation obligations at the end of this file.

## Test map

Extending the four existing suites, per the delivery constraints. New files only
for genuinely new units, which constitution IV and the project rules require to
carry their own tests.

| Suite | Additions | Requirements / criteria |
| --- | --- | --- |
| `connect/usecases/organizations/tests/test_sso_access.py` (EXTEND) | Two-customer × three-public × no-source matrix; `okta-beta` never satisfies `["okta-acme"]`; pinned `BROKER_ALIAS_TO_PROVIDER` map; `resolve_sso_provider("okta-acme")` is never `"okta"`; incomplete policy denies when the marker is set; **identical inputs on an unmarked org return the pre-delivery outcome**; support domain admitted on an incomplete policy (the R3 ordering decision); look-alike domains (`notweni.ai`, `vtex.com.br`) refused; incomplete-policy branch precedes the credential lookup | FR-001, FR-002, FR-005, FR-006, FR-011, FR-014, FR-015, FR-016, SC-001, SC-002, SC-003, SC-004 |
| `connect/usecases/organizations/tests/test_update_sso_config.py` (EXTEND) | Admin emptying either list on a marked org is rejected with nothing persisted; admin edit to a valid non-empty domain list succeeds; `is_enabled: false` on a marked org rejected; marker in the PATCH payload leaves the marker unchanged; malformed domain and malformed identity-source values rejected; validation runs before the lockout guard | FR-007, FR-009, FR-022, FR-023, FR-024, SC-008, SC-009 |
| `connect/api/v1/tests/test_sso_enforcement.py` (EXTEND) | `access_status` / `access_disabled_reason` / `sso_config` asserted on **both** the v1 and v2 organization serializers, including the new reason value; `sso_config` payload keys unchanged (marker absent); `sso-settings` PATCH accepts `okta-acme` and still accepts `google`; refusal on an enabled org still returns 200 metadata and 403 on deep access; `can_update_password` true for a support-domain member of an enforcing org | FR-017, FR-026, FR-027, SC-005, SC-012 |
| `connect/tests/test_middleware_sso.py` (EXTEND) | A JWT carrying `identity_provider=okta-acme` lands on `request.session_identity_provider` unmodified; a first authentication on a mapped domain creates no `OrganizationAuthorization` | FR-013, SC-006 |
| `connect/usecases/organizations/tests/test_sso_policy.py` (NEW) | Each invariant in isolation, accept and reject; normalization (case, whitespace, `@`, wildcard, empty); FR-010 same-source-shared-domain allowed, different-source rejected, **self excluded**; marker implies `is_enabled` and non-empty lists | FR-003, FR-005, FR-007, FR-008, FR-009, FR-010, FR-024, SC-008 |
| `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` (NEW) | Enablement sets marker, source and domains; **re-run leaves the row byte-identical including `updated_at`**; changed domain list replaces rather than appends; invalid input persists nothing; disable clears marker and `is_enabled` together; two customers do not open each other's organization; the command via `call_command`, including `--dry-run` | FR-018, FR-019, FR-020, FR-025, SC-007, SC-008, SC-010 |

**Isolation**, per constitution IV and the delivery constraints:
`KeycloakCredentialsService` is injected and replaced with the
`FakeCredentialsService` already present in both existing use-case suites; the
Django cache is pinned to `LocMemCache` through `@override_settings` with
`cache.clear()` in `setUp` wherever the credential cache is in play;
`@override_settings(USE_EDA_PERMISSIONS=False)` continues to keep the broker out;
`SSO_INTERNAL_BYPASS_EMAIL_DOMAINS` is set through `@override_settings` rather
than relied on from `settings.py`.

**Coverage**: the only lines with a plausible claim to `# pragma: no cover` are
the command's `handle` argument plumbing, and even those are covered by
`call_command`, so nothing in this delivery needs a pragma. Verify before the PR
with `poetry run coverage run manage.py test`, `poetry run coverage report -m`,
and `poetry run python contrib/compare_coverage.py`.

**weni-webapp contract change implied by R7** — one ticket, two items, neither
blocking this delivery:

1. Add `orgs.access_disabled_reason.sso_policy_incomplete` to `en.json`,
   `pt_br.json`, `es.json` and `ro.json`, per the locale standards (sentence
   case, no trailing period, no exclamation, provider-agnostic, naming no
   customer).
2. Give the reason-to-copy map a **generic fallback** so any unrecognised
   reason — this one or a future one — renders a neutral message instead of a
   raw key. This is the more durable half of the change.

The existing `orgs.access_disabled_reason.sso_session_required` copy, which
still says "Google or Microsoft", must become provider-agnostic in the same
ticket; it is wrong the moment a customer Okta organization ships, and FR-027
forbids provider-named refusals reaching the user.

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| Two files under `connect/api/v1` change, which constitution III permits only as a bugfix | `get_can_update_password` reports the opposite of the enforcement it describes for support-domain staff (FR-017, SC-005) — a wrong answer from an existing field, i.e. a bug. `OrganizationSSOConfigSerializer` is the only admin write path that exists, and FR-022 requires admins to keep write access | Moving either to v2 would break the existing client contract, which FR-026 forbids, and would leave two admin write paths — defeating R4's single-validation-point guarantee. Neither change adds a route or a field, and the provider widening is strictly backward compatible: every previously valid payload stays valid |
| Two new modules in `connect/usecases/organizations` (`sso_policy.py`, `enable_customer_identity_source.py`) rather than extending `update_sso_config.py` | The validator has two callers by requirement (FR-018 and FR-022), so it cannot live inside either one. The operator use case has a different lifecycle, a different actor and different idempotency semantics | Putting the validator in `update_sso_config.py` would make the operator path import from the admin path, inverting the dependency; putting the operator logic there would give one class two reasons to change (constitution V) |
| A management command, with no CRUD-command precedent in this repo | FR-021 forbids a new surface for binding an organization to an identity source. A command has no route and no client, so the requirement is met by construction rather than by an authorization check | Django admin would be a third write path and free-form JSON editing, which the spec's assumptions rule out. An internal v2 endpoint would ship an unused authenticated write path against this feature's most sensitive table; it is the natural upgrade once ops tooling exists, and because all logic sits in the use case that upgrade is a view plus a serializer. Full argument in R5 |
