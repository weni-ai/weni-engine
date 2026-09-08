# Tasks: Enterprise Okta login — Connect organization access policy

**Input**: Design documents from `/specs/001-enterprise-okta-sso/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md),
[constitution.md](../../.specify/memory/constitution.md)

**Tests**: MANDATORY. Constitution IV is non-negotiable — every new or changed branch
ships tests in the same PR and project coverage must not drop. The template's
"tests are OPTIONAL" default does **not** apply to this delivery.

**Brownfield**: this is a delta over a working SSO enforcement layer in an existing
Django 3.2 / DRF service. There is **no setup phase** — no project init, no dependency
install, no linting config, no directory creation. Phase 1 is Foundational.

**Decomposition**: plan.md's "Implementation phases" (Steps 1–7) and "Test map" are
authoritative. Step 4 (admin path) straddles US1, US2 and US4; each task sits in the
story whose acceptance scenarios it satisfies.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different file, no dependency on an incomplete task
- **[Story]**: US1…US6, mapping to the user stories in spec.md
- Every task names its exact file path and appends the FR/SC identifiers it satisfies

## Path conventions

Real paths only, from plan.md's source tree. Django tests live beside the code they
cover. **Never** create `src/`, `tests/contract/`, `tests/integration/` or
`tests/unit/` — those directories do not exist in this repository.

Four existing suites are extended; only two new test files are authorized:

| Suite | Status |
| --- | --- |
| `connect/usecases/organizations/tests/test_sso_access.py` | EXTEND |
| `connect/usecases/organizations/tests/test_update_sso_config.py` | EXTEND |
| `connect/api/v1/tests/test_sso_enforcement.py` | EXTEND |
| `connect/tests/test_middleware_sso.py` | EXTEND |
| `connect/usecases/organizations/tests/test_sso_policy.py` | NEW (authorized) |
| `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` | NEW (authorized) |

## Test isolation (applies to every test task)

Non-negotiable per constitution IV and plan.md's test map. No task may reach live
Keycloak, Redis or RabbitMQ.

- Inject `KeycloakCredentialsService` and replace it with the `FakeCredentialsService`
  already present in `test_sso_access.py:31` and `test_update_sso_config.py:21`.
- Pin the cache to `LocMemCache` via `@override_settings` with `cache.clear()` in
  `setUp` wherever the credential cache is in play.
- Keep `@override_settings(USE_EDA_PERMISSIONS=False)`.
- Set `SSO_INTERNAL_BYPASS_EMAIL_DOMAINS` through `@override_settings` rather than
  relying on `settings.py`, so each test states its own premise.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: the shared policy vocabulary, the validator, and the marker field. Steps 1
and 2 of plan.md.

**⚠️ CRITICAL**: no user story work can begin until this phase is complete. The
sequencing safety rule below depends on it: the validator must exist and be tested
before the field exists, and the field must exist before US2 makes fail-closed
evaluation reachable.

- [X] T001 Add `SSOPolicyValidationError(Exception)` beside `SSOConfigLockoutError` in `connect/usecases/organizations/exceptions.py`, with a docstring naming the invariant family it reports (FR-022)
- [X] T002 Create `connect/usecases/organizations/sso_policy.py` with `OrganizationSSOPolicyDTO` as a `@dataclass(frozen=True)` carrying `is_enabled`, `allowed_email_domains`, `allowed_sso_providers`, `requires_customer_identity_source` — the *resulting* policy state, per data-model.md (FR-022)
- [X] T003 Add `normalize_identity_source(value)` to `connect/usecases/organizations/sso_policy.py` implementing invariant I1 — lowercase, trim, then require `^[a-z0-9]+(-[a-z0-9]+)*$` and at most 63 characters, raising `SSOPolicyValidationError` otherwise (FR-003, FR-009)
- [X] T004 Add `normalize_email_domain(value)` to `connect/usecases/organizations/sso_policy.py` implementing invariant I2 — lowercase, trim, then reject empty, `@`, internal whitespace, wildcard, and any value without a dot (FR-008, FR-009)
- [X] T005 Implement `ValidateOrganizationSSOPolicyUseCase.execute(organization, policy)` in `connect/usecases/organizations/sso_policy.py` applying I1 and I2 elementwise and then I3 — `requires_customer_identity_source` implies `is_enabled` **and** both lists non-empty — returning the normalized DTO so callers persist exactly what was validated (FR-003, FR-005, FR-007, FR-009, FR-024)
- [X] T006 Add invariant I4 to `ValidateOrganizationSSOPolicyUseCase` in `connect/usecases/organizations/sso_policy.py`: query `OrganizationSSOConfig.objects.filter(requires_customer_identity_source=True).exclude(organization_id=organization.pk)` and reject when normalized domain sets intersect while normalized identity-source sets are not **equal**; the message must say a domain is already in use and never name the holder (FR-010, FR-029)
- [X] T007 Create `connect/usecases/organizations/tests/test_sso_policy.py` covering I1 and I2 in isolation — accept and reject, plus normalization of case, surrounding whitespace, `@`, wildcard and empty values (FR-003, FR-008, FR-009, SC-008)
- [X] T008 Extend `connect/usecases/organizations/tests/test_sso_policy.py` with I3 accept and reject: the marker with `is_enabled=False`, with an empty provider list, and with an empty domain list are each rejected; the complete state is accepted (FR-005, FR-007, FR-024, SC-008)
- [X] T009 Extend `connect/usecases/organizations/tests/test_sso_policy.py` with I4: a second marked organization sharing a domain under an **identical** identity-source set is accepted, under a different set is rejected, and set inequality is what decides it (FR-010, SC-008)
- [X] T010 Extend `connect/usecases/organizations/tests/test_sso_policy.py` with the self-exclusion test: re-validating an organization against its own already-stored domains is accepted, proving `.exclude(organization_id=...)` is present — the failure this guards appears only on a second run (FR-010, FR-019)
- [X] T011 Add `requires_customer_identity_source = models.BooleanField(default=False)` to `OrganizationSSOConfig` in `connect/common/models.py`. Do **not** add it to `OrganizationSSOConfigSerializer.Meta.fields` or to `UpdateOrganizationSSOConfigDTO`; the omission is the enforcement (FR-004, FR-023, FR-026)
- [X] T012 Re-check the highest existing migration number in `connect/common/migrations/` immediately before generating the next one (today it is `0099_project_currency.py`) and renumber if another branch has landed `0100`; a duplicated number is an unmergeable migration graph (FR-006)
- [X] T013 Generate `connect/common/migrations/0100_organizationssoconfig_requires_customer_identity_source.py` containing a single `migrations.AddField` with `default=False` and **no** `RunPython` — this is the mechanism by which existing rows are provably untouched (FR-006, SC-002)
- [X] T013a Extend `connect/usecases/organizations/tests/test_sso_access.py` asserting the migration's shape in the same phase as the migration itself: every operation in `connect.common.migrations.0100_organizationssoconfig_requires_customer_identity_source` is a `migrations.AddField` and none is a `RunPython`. T013 claims FR-006 and SC-002, so Phase 1 must not close with that claim unverified (FR-006, SC-002)

**Checkpoint**: the validator exists and is tested; the marker field and its schema-only
migration exist and the migration's shape is asserted; nothing reads the marker yet, so
behaviour is unchanged. User story work can begin.

---

## Phase 2: User Story 1 — A customer organization admits only that customer's identity source (Priority: P1) 🎯 MVP

**Goal**: a policy can name one specific customer's identity source, and two customer
sources stay permanently distinct throughout evaluation.

**Independent test**: configure one organization for `okta-acme`. Exercise it with a
session carrying `okta-acme`, one carrying `okta-beta`, one carrying each public source,
and one carrying no source. Only the first admits; a non-enforcing organization admits
in every case. Quickstart scenario 1.

- [X] T014 [US1] Replace the `allowed_sso_providers` child `ChoiceField` with `serializers.CharField()` in `OrganizationSSOConfigSerializer` in `connect/api/v1/organization/serializers.py` and add `validate_allowed_sso_providers` delegating each entry to `normalize_identity_source`; every payload valid before this change must stay valid. The validator lets `SSOPolicyValidationError` propagate rather than translating it locally — T028 maps it at the view, which is what keeps the error body in the `{"detail": "…"}` shape `contracts/organization-access.md` pins instead of DRF's field-keyed default (FR-001, FR-003, FR-026, SC-008, SC-012)
- [X] T028 [US1] Map `SSOPolicyValidationError` to a `400` in `update_sso_settings` in `connect/api/v1/organization/views.py`, covering **both** `serializer.is_valid()` and the `UpdateOrganizationSSOConfigUseCase` call, mirroring the existing `SSOConfigLockoutError` handling and its `{"detail": "…"}` body. `serializer.is_valid(raise_exception=True)` currently sits outside the `try`, and `SSOPolicyValidationError` is a plain `Exception` that DRF's `to_internal_value` does not catch, so without this a malformed payload returns `500`. It sits in US1 rather than US2 because T014 is what makes the exception reachable; the ID is kept from its original Phase 3 position to avoid renumbering (FR-022, SC-008)
- [X] T015 [US1] Document the admission rule for `BROKER_ALIAS_TO_PROVIDER` in `connect/usecases/organizations/sso_access.py`: entries are permitted only for providers that are a single global tenant, and per-customer brokers must pass through unmapped (FR-002)
- [X] T016 [US1] Add `test_broker_alias_map_contains_no_multi_tenant_vendor_family` to `connect/usecases/organizations/tests/test_sso_access.py` pinning `set(BROKER_ALIAS_TO_PROVIDER)` to exactly `{"google", "microsoft", "azure-ad", "azuread", "entra-id", "office365"}`, and assert `resolve_sso_provider("okta-acme") == "okta-acme"` — never `"okta"` (FR-002, SC-001)
- [X] T017 [US1] Add the evaluation matrix to `connect/usecases/organizations/tests/test_sso_access.py`: two customer sources × three public sources × no source against a marked organization allowing `["okta-acme"]` / `["acme.com"]`, asserting `active`/`null` for the matching source and the exact refusal reason for every other cell (FR-001, FR-002, SC-001)
- [X] T018 [US1] Add the alias-isolation test to `connect/usecases/organizations/tests/test_sso_access.py`: a session resolved to `okta-beta` never satisfies a policy of `["okta-acme"]`, and the reverse also holds (FR-002, SC-001)
- [X] T019 [US1] Add the credential-state tests to `connect/usecases/organizations/tests/test_sso_access.py`: with a satisfying `okta-acme` session, a member holding a platform password is refused with `sso_password_configured`, and an indeterminate `None` from the injected fake is refused with `sso_credential_unavailable` (FR-012, FR-014)
- [X] T020 [US1] Add the dual-membership test to `connect/usecases/organizations/tests/test_sso_access.py`: a member of one marked and one policy-free organization keeps the policy-free one active on a non-satisfying session, with no re-authentication (FR-011, SC-003)
- [X] T021 [US1] Add the domain-semantics regression test to `connect/usecases/organizations/tests/test_sso_access.py`: `Maria@ACME.com` matches a stored `acme.com`, while `mail.acme.com` is not covered by `acme.com` in either direction (FR-008)
- [X] T022 [US1] Extend `connect/api/v1/tests/test_sso_enforcement.py`: `PATCH /v1/organization/org/{uuid}/sso-settings/` accepts `["okta-acme"]` and still accepts `["google"]` on a legacy organization, and the response keeps the same three `sso_config` keys. Also assert the reject side of the branch T014 adds: `["Okta Acme!"]` returns `400` with a `{"detail": …}` body and nothing persisted, which is the assertion that proves T028's mapping is wired to the serializer path and not only to the use-case call (FR-001, FR-003, FR-026, SC-008, SC-012)
- [X] T023 [US1] Extend `connect/api/v1/tests/test_sso_enforcement.py`: a refused session still receives `200` with disabled metadata on the organization read while deep access by direct reference returns `403`, confirming `HasSSOAccess` picks up the outcome with no permission-class change (FR-011, SC-001)
- [X] T024 [US1] [P] Extend `connect/tests/test_middleware_sso.py`: a JWT carrying `identity_provider=okta-acme` lands on `request.session_identity_provider` unmodified, with no alias folding anywhere in the middleware (FR-002, SC-001)

**Checkpoint**: one customer's source is nameable and isolated, and a malformed policy
value is refused with a `400` rather than a `500`. US1 is independently testable and is
the MVP.

---

## Phase 3: User Story 2 — Incomplete policy denies on enabled organizations and changes nothing elsewhere (Priority: P1)

**Goal**: an empty list denies on a marked organization and keeps meaning "allow any"
everywhere else, and the forbidden state is unreachable through every supported write.

**Independent test**: two organizations, both `is_enabled=True` with both lists empty,
marker on one. The marked one denies every session; the unmarked one returns exactly its
pre-delivery outcome. Quickstart scenario 2.

- [X] T025 [US2] Add `SSO_POLICY_INCOMPLETE = "sso_policy_incomplete"` to `OrganizationSSOAccessDisabledReason` in `connect/usecases/organizations/sso_access.py`, leaving the five existing values and their strings untouched (FR-028, SC-012)
- [X] T026 [US2] Add a private `_refuse_incomplete_policy(config)` early return to `EvaluateOrganizationSSOAccessUseCase.evaluate` in `connect/usecases/organizations/sso_access.py`, guarded by the marker, placed **after** the support-domain bypass and **before** `resolve_sso_provider`. Route it and the four existing `non_compliant` exits (five reasons) through one private `_refuse(reason, organization, user, provider)` that logs the organization, the member and the resolved identity source — `logger.warning` for `sso_policy_incomplete`, `logger.info` for the five session reasons. `evaluate` logs nothing on refusal today and the response body carries no identity source, so logging only the new reason would leave FR-028's "resolved session identity source" recoverable from no record at all for five of six refusals. Refusal *outcomes* are unchanged, which is what keeps FR-006's "legacy path unchanged" a matter of the diff. Do not touch `is_provider_allowed` or `is_email_domain_allowed` (FR-004, FR-005, FR-028, SC-011)
- [X] T027 [US2] Rewrite `UpdateOrganizationSSOConfigUseCase.execute` in `connect/usecases/organizations/update_sso_config.py` to merge the stored row with the DTO, build an `OrganizationSSOPolicyDTO` of the resulting state, call `ValidateOrganizationSSOPolicyUseCase`, **then** `_validate_actor_not_locked_out`, then persist the normalized values. The marker is read from the stored row and never assigned (FR-005, FR-007, FR-022, FR-023, FR-024)
- [X] T029 [US2] Extend `connect/usecases/organizations/tests/test_sso_access.py`: a marked organization with either list empty denies with `sso_policy_incomplete`, and an unmarked organization given identical inputs returns the pre-delivery outcome — `google` admits, no source refuses with `sso_session_required` (FR-005, FR-006, SC-002)
- [X] T030 [US2] Extend `connect/usecases/organizations/tests/test_sso_access.py` asserting the incomplete-policy branch precedes the credential lookup: the injected `FakeCredentialsService` records zero `has_password_credential` calls on that path, so the refusal cannot weaken FR-014's indeterminate-state denial (FR-014, SC-002)
- [X] T030a [US2] Extend `connect/usecases/organizations/tests/test_sso_access.py` with `assertLogs` over the refusal log site T026 introduces, covering every reason reachable in this phase: each carries the organization, the member and the resolved identity source, and `sso_policy_incomplete` is the only one at `WARNING`. This is the same-phase cover for T026's change to the five existing exits; T058 asserts the support-facing distinguishability in US5 (FR-028, SC-011)
- [X] T031 [US2] Extend `connect/usecases/organizations/tests/test_sso_access.py` asserting a legacy `OrganizationSSOConfig` row carries `requires_customer_identity_source=False` with its other four fields byte-identical, and evaluates exactly as it did pre-delivery. The migration's shape is asserted by T013a in Phase 1, beside the migration itself (FR-006, SC-002)
- [X] T032 [US2] Extend `connect/usecases/organizations/tests/test_update_sso_config.py`: an admin emptying `allowed_sso_providers` or `allowed_email_domains` on a marked organization is rejected with `SSOPolicyValidationError` and the row reloaded from the database is unchanged (FR-005, FR-007, FR-022, SC-002, SC-008)
- [X] T033 [US2] Extend `connect/usecases/organizations/tests/test_update_sso_config.py` asserting validation runs **before** the lockout guard: an incomplete resulting state raises `SSOPolicyValidationError`, not the `SSOConfigLockoutError` message "Your current SSO provider is not in the allowed providers" (FR-022, SC-008)
- [X] T034 [US2] Extend `connect/api/v1/tests/test_sso_enforcement.py` asserting `access_status`, `access_disabled_reason` and `sso_config` on **both** the v1 and the v2 organization serializers, including that `sso_policy_incomplete` surfaces on both and that `sso_config` still has exactly the three keys `is_enabled`, `allowed_email_domains`, `allowed_sso_providers` (FR-026, FR-027, SC-012)

**Checkpoint**: fail-closed evaluation is live, scoped to marked organizations, and
unreachable in an incomplete state through any supported write.

---

## Phase 4: User Story 3 — Support staff reach a customer organization without that customer's Okta (Priority: P1)

**Goal**: `@weni.ai` and `@vtex.com` members keep access to an enforcing organization on
any session and are correctly told they may keep a platform password. No look-alike
domain qualifies.

**Independent test**: invite one member per domain into a customer-bound organization
and evaluate each on a platform-password session; then read
`GET /v1/account/profile/` as the support member. Quickstart scenario 3.

- [X] T035 [US3] Add an `is_sso_internal_bypass_email(obj.email)` early return to `get_can_update_password` in `connect/api/v1/account/serializers.py`, reusing the existing predicate rather than re-deriving the domain comparison so the exception's boundary cannot drift (FR-017, SC-005)
- [X] T036 [US3] Extend `connect/usecases/organizations/tests/test_sso_access.py` with the support-domain matrix against a customer-bound organization on a platform-password session: `@weni.ai` and `@vtex.com` are `active`; `@notweni.ai`, `@vtex.com.br` and `@partner.com` are refused; `SSO_INTERNAL_BYPASS_EMAIL_DOMAINS` is set through `@override_settings` (FR-015, FR-016, SC-004)
- [X] T037 [US3] Add `test_support_domain_is_admitted_when_policy_is_incomplete` to `connect/usecases/organizations/tests/test_sso_access.py`, pinning the R3 ordering decision — a `@weni.ai` member of a marked organization with empty lists is still `active`. Its docstring must state that a reviewer preferring the literal reading of FR-005 reverses the decision by moving one line in `evaluate` (FR-005, FR-015, SC-004)
- [X] T038 [US3] Extend `connect/api/v1/tests/test_sso_enforcement.py`: `GET /v1/account/profile/` returns `can_update_password: true` for a support-domain member of an enforcing organization, and the value for `@notweni.ai` and `@vtex.com.br` members is unchanged from the pre-delivery behaviour (FR-016, FR-017, SC-005)

**Checkpoint**: the platform retains a way back into every enforcing organization, and
the exception's boundary is exact.

---

## Phase 5: User Story 4 — Implantation enables a customer without a merchant-facing surface (Priority: P2)

**Goal**: an operator enables, updates and disables a customer binding idempotently
through a command with no route and no client, while organization admins keep validated
write access to their own policy.

**Independent test**: enable a customer, re-run the identical invocation and confirm the
stored policy including `updated_at` is unchanged, then enable a second customer and
confirm neither session opens the other's organization. Quickstart scenarios 4 and 5.

### Operator path (Step 5)

- [X] T039 [US4] Create `connect/usecases/organizations/enable_customer_identity_source.py` with a frozen `EnableCustomerIdentitySourceDTO` and `EnableCustomerIdentitySourceUseCase.execute`: resolve the organization by public `uuid`, `get_or_create` the config, compute the resulting state with the two lists **assigned** from the DTO, validate through `ValidateOrganizationSSOPolicyUseCase`, compare the validated state against the stored row on the four policy fields, and return without calling `save()` when equal — all inside `transaction.atomic()`, with `KeycloakCredentialsService` injectable (FR-018, FR-019, FR-020, SC-007, SC-008)
- [X] T040 [US4] Add the disable operation to `EnableCustomerIdentitySourceUseCase` in `connect/usecases/organizations/enable_customer_identity_source.py`, clearing `requires_customer_identity_source` and `is_enabled` in the **same save** so invariant I3 is never transiently violated, leaving the two lists as stored (FR-024)
- [X] T041 [US4] Add dry-run support to `EnableCustomerIdentitySourceUseCase` in `connect/usecases/organizations/enable_customer_identity_source.py`: run the full merge and validation, return the resulting state, persist nothing (FR-018)
- [X] T042 [US4] Create `connect/common/management/commands/enable_customer_identity_source.py` as a composition root carrying no logic — `--organization`, repeatable `--identity-source` and `--email-domain`, `--disable`, `--dry-run`; build the DTO, call `execute()`, print the organization, marker, sources and domains; raise `CommandError` on validation failure and on an unknown organization uuid. No `--add-domain` and no `--remove-domain` (FR-018, FR-020, FR-021, FR-025)
- [X] T043 [US4] Change `validate_allowed_email_domains` in `OrganizationSSOConfigSerializer` in `connect/api/v1/organization/serializers.py` to delegate each entry to `normalize_email_domain` instead of its current inline `strip().lower()` filter, so a malformed domain is rejected rather than silently dropped. Like T014 it lets `SSOPolicyValidationError` propagate to T028's mapping rather than translating locally, so both fields produce the same `{"detail": …}` body (FR-009, FR-022, SC-008)

### Operator path tests

- [X] T044 [US4] Create `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting enablement sets the marker, `is_enabled`, the identity source and the domains on a previously policy-free organization (FR-018, SC-010)
- [X] T045 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting an idempotent re-run leaves `updated_at` **unchanged**, not merely the four policy fields — `auto_now=True` means a blind `save()` passes a field-by-field check and fails SC-007. Also assert a re-run with `ACME.COM` for a stored `acme.com` is a no-op (FR-019, SC-007)
- [X] T046 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting a changed domain list **replaces** rather than appends: re-running with only `acme.com.br` removes `acme.com` from scope (FR-020)
- [X] T047 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting invalid input persists nothing — a malformed domain, a malformed identity source, and an empty list each leave the reloaded row untouched, proving the `transaction.atomic()` boundary (FR-003, FR-007, FR-009, SC-008)
- [X] T048 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting `--disable` clears the marker and `is_enabled` together in one save, leaving a state invariant I3 accepts (FR-024)
- [X] T049 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting the FR-010 conflict both ways: a second organization claiming `acme.com` under `okta-beta` is rejected with nothing persisted, while a second Acme organization with the identical identity-source list may share `acme.com` (FR-010, SC-008)
- [X] T050 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting two customers do not open each other's organization after both are enabled through the same operation, and that no schema change was required for the second (FR-025, SC-001, SC-010)
- [X] T051 [US4] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` driving the command through `call_command`, covering argument parsing, the repeatable flags, `--dry-run` persisting nothing, and `CommandError` for an unknown organization uuid — this is what keeps the command's plumbing covered without a `# pragma: no cover` (FR-018, FR-021)

### Admin path invariants (Step 4 — US4 AS-5 / AS-6)

- [X] T052 [US4] Extend `connect/usecases/organizations/tests/test_update_sso_config.py`: an admin editing a customer-bound organization's domain list to a valid non-empty list succeeds and persists, so day-to-day edits stay self-service (FR-022, SC-009)
- [X] T053 [US4] Extend `connect/usecases/organizations/tests/test_update_sso_config.py`: `is_enabled: false` on a marked organization is rejected by invariant I3 with nothing persisted (FR-024, SC-009)
- [X] T054 [US4] Extend `connect/usecases/organizations/tests/test_update_sso_config.py`: a PATCH body containing `requires_customer_identity_source` returns `200` with the **stored** marker unchanged — assert the reloaded value, not just the status code, because DRF silently drops the unknown key (FR-023, SC-009)
- [X] T055 [US4] Extend `connect/usecases/organizations/tests/test_update_sso_config.py`: a domain containing `@`, a wildcard, surrounding whitespace or an empty value, and an identity-source value that is not slug-shaped, are each rejected (FR-003, FR-009, SC-008)
- [X] T056 [US4] Extend `connect/usecases/organizations/tests/test_update_sso_config.py` reloading the row after **every** rejection case above and asserting all four policy fields plus the marker are untouched — a `400` with a partial write satisfies a status assertion and violates FR-022 (FR-022, SC-008)
- [X] T057 [US4] Extend `connect/api/v1/tests/test_sso_enforcement.py` asserting there is no product surface: `OrganizationSSOConfig` is absent from `django.contrib.admin.site._registry`, and neither the `sso-settings` response nor the v1/v2 organization payloads expose `requires_customer_identity_source` (FR-021, SC-010)

**Checkpoint**: a customer can be brought live and taken back down by an operator, with
admins retaining validated write access and no new surface anywhere.

---

## Phase 6: User Story 5 — Support can explain a refusal without inspecting another tenant (Priority: P2)

**Goal**: every refusal is attributable, incomplete-policy refusals are distinguishable
from session refusals, and no record leaks a secret or another tenant's configuration.

**Independent test**: trigger each refusal kind and inspect the log line and the
response body. Quickstart scenario 6. Most of this story falls out of US2 — these are
assertions, not new code.

- [X] T058 [US5] Extend `connect/usecases/organizations/tests/test_sso_access.py` with `assertLogs`: **all six** refusal reasons are logged carrying the organization, the member and the resolved identity source, and `sso_policy_incomplete` is the only one at `WARNING` while the five session reasons are at `INFO` — that level split is what makes the platform fault distinguishable from a session problem. Quickstart scenario 6 asks for the log line on *each* refusal kind, so pinning the five at their pre-delivery silence would fail T066 (FR-028, SC-011)
- [X] T059 [US5] Extend `connect/usecases/organizations/tests/test_sso_access.py` asserting no refusal log line and no refusal result carries an identity-provider secret or another organization's configuration — the refusal reason names no provider, no customer and no other tenant (FR-027, FR-029, SC-011)
- [X] T060 [US5] Extend `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` asserting the FR-010 conflict message states that a domain is already in use and never names the organization or the identity source holding it, and that command output carries no secret (FR-029, SC-011)

**Checkpoint**: a support engineer can attribute any refusal from the platform's own
records without cross-tenant exposure.

---

## Phase 7: User Story 6 — Authenticating through a customer Okta never grants membership (Priority: P3)

**Goal**: regression protection only. **Zero code change** — research.md verified that
`WeniOIDCAuthenticationBackend.create_user` calls `check_module_permission`, which grants
only the Django `can_communicate_internally` permission and never writes
`OrganizationAuthorization`.

**Independent test**: authenticate a user on a mapped domain who holds no authorization
and confirm the organization is absent from their list and deep access is refused.

- [X] T061 [US6] Extend `connect/tests/test_middleware_sso.py`: a first authentication on a mapped domain creates the `User` and creates **no** `OrganizationAuthorization` row for the customer organization (FR-013, SC-006)
- [X] T062 [US6] Extend `connect/api/v1/tests/test_sso_enforcement.py`: an authenticated user on a mapped domain with no authorization does not see the customer organization in their organization list, and deep access by direct reference returns `403` (FR-013, SC-006)

**Checkpoint**: all six stories are independently functional and covered.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T065 [P] Add the §7.2 supersession note to `docs/2026-08-enterprise-okta-sso-plan.md` pointing at `specs/001-enterprise-okta-sso/` as the ratified decomposition of the Connect slice (FR-026)
- [X] T066 Run the verification gate: `poetry run coverage run manage.py test`, `flake8 connect/`, and `poetry run python contrib/compare_coverage.py` showing no decrease with no new `# pragma: no cover`; then walk quickstart.md scenarios 1–6 including `poetry run python manage.py sqlmigrate common 0100` and `grep -c RunPython connect/common/migrations/0100_*.py` returning `0` (FR-006, SC-002, SC-008, and the full FR/SC set by suite)

---

## External follow-up (not implementable here)

The weni-webapp change lives in a **different repository** and is deliberately not a
checkbox in this tasks.md. One ticket, three items, none blocking this delivery:

1. Add `orgs.access_disabled_reason.sso_policy_incomplete` to `en.json`, `pt_br.json`,
   `es.json` and `ro.json`, per the locale standards — sentence case, no trailing
   period, no exclamation, provider-agnostic, naming no customer.
2. Give the reason-to-copy map a **generic fallback** so any unrecognised reason renders
   a neutral message instead of a raw key. This is the more durable half.
3. Rewrite the existing `orgs.access_disabled_reason.sso_session_required` copy, which
   still says "Google or Microsoft", to be provider-agnostic — it is wrong the moment a
   customer Okta organization ships, and FR-027 forbids provider-named refusals reaching
   the user.

---

## Anti-tasks — must NOT be generated or implemented

Each of these violates a requirement or the governance rule against drive-by rewrites.
Listed so `/speckit-analyze` and `/speckit-implement` can detect drift.

| Forbidden change | Why |
| --- | --- |
| Adding `requires_customer_identity_source` to `OrganizationSSOConfigSerializer.Meta.fields` | Its omission **is** the enforcement of FR-023 |
| Registering `OrganizationSSOConfig` in Django admin | FR-021; rejected in R5 |
| Adding any endpoint, in v1 or v2 | R5 chose a management command |
| Adding `RunPython` or any data migration touching policy | FR-006, SC-002 |
| Rewriting `is_provider_allowed` / `is_email_domain_allowed` | Pre-existing constitution I violation; R3 routes around it. A rewrite silently changes the legacy lockout guard |
| Fixing the lazy import in `serialize_organization_access_status` | Pre-existing violation tabulated in research.md; governance forbids the drive-by |
| Refactoring `enrich_serializer_context_with_sso_access` | Same |
| Rewriting the v1 `sso-settings` view body's `_assert_admin` / `check_object_permissions` | Same; this delivery adds no logic to the view body |
| Adding SSO enforcement to `change_password` | R8 reports it as out of scope — a new restriction no requirement asks for |
| Adding `# pragma: no cover` anywhere | Nothing in this delivery warrants one; the command's plumbing is covered via `call_command` |

---

## Dependencies & Execution Order

### Phase dependencies

- **Foundational (Phase 1)**: no dependencies. **Blocks every user story.**
- **US1, US2, US3 (P1)**: all depend on Foundational. US1 carries T028 (the `400`
  mapping) alongside T014, since T014 is what makes the exception reachable. US2
  additionally depends on T011 and T013 existing (it reads the marker).
- **US4 (P2)**: depends on Foundational and on T027 (the admin path must already merge
  and validate before the admin-path invariant tests can pass).
- **US5 (P2)**: depends on T026 (the warning log it asserts) and T039/T042 (the command
  output it asserts). Thin by design.
- **US6 (P3)**: depends on Foundational only. Zero code change — can be done at any
  point after Phase 1.
- **Polish (Phase 8)**: T063–T065 can run in parallel at any time; T066 depends on
  everything.

### Sequencing safety rule

No task may make fail-closed evaluation reachable before its validation exists. The
enforced order is:

1. **T001–T010** — the validator and its tests. Nothing calls it, so behaviour cannot
   change.
2. **T011–T013a** — the marker field, its schema-only migration, and the assertion that
   the migration is schema-only. Nothing reads the marker.
3. **T014 with T028** — the widened provider input and the view mapping that turns a
   validation failure into a `400`. T028 lands *with* T014, never later: T014 is what
   makes `SSOPolicyValidationError` reachable from `serializer.is_valid()`, and until the
   mapping exists a malformed payload returns `500`.
4. **T025–T027** — the fail-closed branch and the validated admin write path.

**What actually prevents a marked organization being persisted with an incomplete policy**
is that nothing writes the marker until T039/T042 in Phase 5, and US4 already depends on
T027. The admin path is therefore merging and validating before any organization can be
marked, whichever of T026 and T027 lands first — so the relative order of those two is a
reviewability preference, not a safety property. T042 (the command) may only land after
T039–T041, which validate before persisting.

### Shared-file conflicts — do not work these concurrently

Step 4 splits across three stories, and the four extended suites are shared. Serialize
edits to each file below, or rebase between them.

| File | Tasks | Stories |
| --- | --- | --- |
| `connect/api/v1/organization/serializers.py` | T014, T043 | **US1 and US4** — the providers child (T014) and the domains validator (T043) touch the same serializer class. Land T014 first |
| `connect/usecases/organizations/sso_policy.py` | T002–T006 | Foundational — strictly sequential |
| `connect/usecases/organizations/sso_access.py` | T015, T025, T026 | US1 and US2 |
| `connect/api/v1/organization/views.py` | T028 | US1 — the only task touching the view body |
| `connect/usecases/organizations/tests/test_sso_access.py` | T013a, T016–T021, T029, T030, T030a, T031, T036, T037, T058, T059 | Foundational, US1, US2, US3, US5 |
| `connect/usecases/organizations/tests/test_update_sso_config.py` | T032, T033, T052–T056 | US2 and US4 |
| `connect/api/v1/tests/test_sso_enforcement.py` | T022, T023, T034, T038, T057, T062 | US1, US2, US3, US4, US6 |
| `connect/tests/test_middleware_sso.py` | T024, T061 | US1 and US6 |
| `connect/usecases/organizations/tests/test_enable_customer_identity_source.py` | T044–T051, T060 | US4 and US5 |

### Parallel opportunities

Genuine `[P]` tasks are the ones touching a file no other in-flight task touches:

- **T024** (`test_middleware_sso.py`) is the only genuinely parallel task in Phase 2
  once Phase 1 is done. Two `[P]` markers were dropped: **T016**, because T013a writes
  `test_sso_access.py` during Phase 1 so T016 is not that file's first writer; and
  **T022**, because its `400` assertion now depends on T028 completing, which the `[P]`
  definition excludes.
- **T063**, **T064** and **T065** are three different documents and can run together at
  any time.
- Across stories: once Phase 1 is complete, US1, US3 and US6 have no code dependency on
  each other and can be staffed in parallel provided the shared-suite table above is
  respected.

### Within each user story

- Code and its tests ship together — constitution IV blocks a PR that lowers coverage,
  so no task in this list is complete until its branch is covered.
- Validator before the writers; writers before the branch that depends on a validated
  state; tests alongside.

---

## Implementation Strategy

### MVP first (Foundational + US1)

1. Complete Phase 1: Foundational — T001–T013a.
2. Complete Phase 2: US1 — T014 and T028, then T015–T024.
3. **Stop and validate**: quickstart scenario 1 plus `flake8 connect/` and
   `compare_coverage.py`.

At this point a policy can name one customer's identity source and two customers are
provably isolated, with no change to any existing organization's behaviour.

### Incremental delivery

1. Foundational → validator and marker in place, behaviour unchanged.
2. + US1 → customer sources nameable and isolated (MVP).
3. + US2 → fail-closed scoped to marked organizations; run quickstart scenario 2 before
   enabling anything in a real environment.
4. + US3 → support keeps a way in; the `can_update_password` bug is fixed.
5. + US4 → implantation can enable, update and disable a customer.
6. + US5, US6 → refusals explainable, membership regression pinned.
7. + Polish → docs and the verification gate.

The P1 set (Foundational + US1 + US2 + US3) is the smallest safely deployable increment:
enforcement is correct and support cannot be locked out. US4 is required before a
customer can actually be brought live, since without it no supported path sets the
marker.

---

## Notes

- `[P]` means a different file with no dependency on an incomplete task; the
  shared-file table above overrides an optimistic `[P]`.
- Test names follow `test_<behavior>` per constitution IV.
- Two observations surfaced while generating this list, neither changing any task:
  - plan.md's Step 7 says "documentation obligations at the end of this file", but the
    file ends at Complexity Tracking and the section is absent. T063–T065 use the three
    documents named in the delivery constraints and referenced from
    `contracts/organization-access.md`.
  - `EvaluateOrganizationSSOAccessUseCase.evaluate` logs **nothing** on refusal today,
    and the response body carries no identity source. T026 therefore routes all six
    refusals through one log site rather than only the new one: FR-028 and SC-011 require
    the resolved identity source to be recoverable for *every* refusal, and quickstart
    scenario 6 asks for the log line on each refusal kind. plan.md's Constitution Check
    describes only the new `warning` line and understates this; it is the plan that needs
    the correction, not the requirement.
