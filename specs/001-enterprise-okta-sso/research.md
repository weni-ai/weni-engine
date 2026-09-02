# Phase 0 research — Enterprise Okta login (Connect slice)

**Feature**: `001-enterprise-okta-sso` | **Date**: 2026-09-01

This is a brownfield delta over the SSO enforcement layer already in
production. Every decision below is stated against the current code, named by
file, and justified against the constitution. Nothing here proposes a
greenfield structure.

## Baseline established from the code

| Concern | Current state | File |
| --- | --- | --- |
| Policy storage | `OrganizationSSOConfig`: `is_enabled`, `allowed_email_domains` (JSONField), `allowed_sso_providers` (JSONField), OneToOne to `Organization`, integer PK + `uuid` | `connect/common/models.py:311` |
| Emptiness semantics | `is_provider_allowed` and `is_email_domain_allowed` both `return True` when the list is empty | `connect/common/models.py:343,350` |
| Callers of those two methods | Exactly two, both use cases: `EvaluateOrganizationSSOAccessUseCase.evaluate` and `UpdateOrganizationSSOConfigUseCase._validate_actor_not_locked_out` | `sso_access.py:119,123`, `update_sso_config.py:74,78` |
| Alias resolution | `resolve_sso_provider` maps known aliases to `google`/`microsoft` and **passes unknown aliases through lowercased** | `sso_access.py:54` |
| Support exception | `is_sso_internal_bypass_email` — exact domain match against `settings.SSO_INTERNAL_BYPASS_EMAIL_DOMAINS` (default `["weni.ai", "vtex.com"]`) | `sso_access.py:66`, `settings.py:693` |
| Admin write path | `GET`/`PATCH /v1/organization/org/{uuid}/sso-settings/` → `OrganizationSSOConfigSerializer` → `UpdateOrganizationSSOConfigUseCase` | `views.py:681-722` |
| Provider input validation | `ListField(child=ChoiceField(choices=PROVIDER_CHOICES))` — `google`/`microsoft` only | `serializers.py:43` |
| Client contract | `access_status`, `access_disabled_reason`, `sso_config` on v1 **and** v2 org serializers; **v2 imports the v1 helpers**, so the shape is single-sourced | `v1/organization/serializers.py:53-79`, `v2/organizations/serializers.py:23-24` |
| Session claim | `request.session_identity_provider` set from the live JWT `identity_provider` claim | `connect/middleware.py:114-120` |
| Password state | `KeycloakCredentialsService.has_password_credential` → `True`/`False`/`None`; only `True` is cached | `connect/services/keycloak/service.py` |
| Latest migrations | `connect/common` 0099, `connect/authentication` 0021 | — |
| Management commands | Only `grpc` and `edaconsume`, both long-running daemons. No CRUD-command precedent | `connect/*/management/commands/` |
| Database | PostgreSQL (`env.db`, default `postgres://…`) — jsonb available | `settings.py:226` |
---

## R1 — Recording the "enabled for customer-Okta login" marker

**Decision**: add one field to `OrganizationSSOConfig`:

```python
requires_customer_identity_source = models.BooleanField(default=False)
```

Schema-only migration `connect/common/migrations/0100_…`, a single `AddField`
with `default=False` and **no `RunPython`**. The field is read by exactly one
new branch in `EvaluateOrganizationSSOAccessUseCase` (see R3) and set by
exactly one writer (see R5).

**Rationale**:

- FR-006 and SC-002 require that no existing row's evaluated behaviour change.
  A pure `AddField` with a literal default writes `False` into every existing
  row and touches no other column, so the stored policy of every organization
  this delivery does not enable is untouched by construction — there is no
  `RunPython` that could rewrite it, and reviewers can verify that by reading
  the migration. Contrast with migration `0097`, which *did* carry a
  `RunPython` backfill; repeating that pattern here is precisely what FR-006
  forbids.
- `False` is the safe default in the strong sense: the new fail-closed branch
  is a no-op when the marker is `False`, so a legacy row traverses the same code
  path it does today.
- Extending `OrganizationSSOConfig` rather than adding a table follows
  constitution I ("prefer extending an existing module") and III ("existing
  models MUST be reused rather than duplicated"), and satisfies FR-025: a second
  customer is another row's boolean, not a schema change.
- The name is provider-agnostic. FR-027 constrains client-visible strings, but
  a column named `is_okta_enabled` would be wrong the day a customer arrives on
  Entra or Ping, and the spec's Key Entities describe the concept as "customer
  identity source", not Okta.
- The field is **absent from `OrganizationSSOConfigSerializer.Meta.fields`**.
  Because that is a `ModelSerializer` with an explicit `fields` list, omission
  makes the marker neither readable nor writable through the admin path — FR-023
  is enforced structurally rather than by a check that could be forgotten. It
  also keeps the `sso_config` payload byte-identical for existing clients
  (FR-026), so there is nothing for weni-webapp to absorb.

**Alternatives considered**:

- *Infer the marker from policy contents* (e.g. "a provider value outside
  `google`/`microsoft` implies enabled"). Rejected — the spec rules it out
  directly: the two states that must be told apart are an enabled organization
  with empty lists and a legacy organization with empty lists, whose contents
  are identical. Inference is not merely fragile here, it is impossible.
- *A separate `OrganizationCustomerIdentityBinding` model.* Rejected — it would
  duplicate `allowed_sso_providers` and `allowed_email_domains` into a second
  table, creating two places where the policy can disagree, for the benefit of
  one boolean. Constitution III forbids duplicating existing models.
- *A settings-level allowlist of organization UUIDs* (`env.list`). Rejected on
  three counts: FR-018 requires validation against stored state at write time,
  which a deploy-time list cannot provide; FR-028 requires the marker to be
  recoverable per organization from the platform's own records; and it would
  make a security-relevant decision depend on an environment variable that no
  migration or test can pin.
- *Reusing `Organization.require_external_provider_for_access`* (the legacy flag
  migration `0097` backfilled from). Rejected — it already means something else
  and existing rows carry `True`, which would enable fail-closed evaluation on
  exactly the organizations FR-006 protects.

---

## R2 — Per-customer identity-source values, with `google`/`microsoft` still valid

**Decision**: three parts.

1. Replace the serializer child field with a plain `CharField` validated by one
   shared domain function:

   ```python
   allowed_sso_providers = serializers.ListField(
       child=serializers.CharField(), required=False, default=list
   )

   def validate_allowed_sso_providers(self, value):
       return [normalize_identity_source(v) for v in value]
   ```

   `normalize_identity_source` lives in the new domain module (R4), lowercases,
   strips, and rejects anything that does not match the slug shape
   `^[a-z0-9]+(-[a-z0-9]+)*$` with a length ceiling (63 characters, matching a
   DNS label, which is the practical bound on a Keycloak broker alias).

2. Keep `OrganizationSSOConfig.PROVIDER_CHOICES` as-is. It stays the *public*
   provider vocabulary used by `BROKER_ALIAS_TO_PROVIDER`; it stops being the
   allowlist's input constraint.

3. Pin `BROKER_ALIAS_TO_PROVIDER` with a test, not a comment.

**Rationale**:

- The slug shape **subsumes** the old choices: `google` and `microsoft` both
  match it. Every payload that validated before this change still validates,
  which is what FR-026 and SC-012 require of the admin contract.
- Normalization on write is load-bearing, not cosmetic. `is_provider_allowed`
  compares with `provider in self.allowed_sso_providers` — a case-sensitive
  membership test with no read-side normalization. The old `ChoiceField`
  guaranteed lowercase stored values; a bare `CharField` would not, and
  `["Okta-Acme"]` would silently never match a session claim resolved to
  `okta-acme`. This is the single most likely way to ship a policy that admits
  nobody, so normalization must happen at every write, which is why it belongs
  in the shared validator (R4) and not only in the serializer.
- FR-003 ("a value that does not conform MUST be rejected at write time") is
  satisfied by the shape check; the ceiling also stops an arbitrary string from
  ever being stored as a policy value.

**Preventing a future `okta` family in `BROKER_ALIAS_TO_PROVIDER`** (FR-002):
a comment is documentation, not enforcement. Three mechanisms, in order of
strength:

1. A **pinned-map test** in `connect/usecases/organizations/tests/test_sso_access.py`:
   `test_broker_alias_map_contains_no_multi_tenant_vendor_family` asserts
   `set(BROKER_ALIAS_TO_PROVIDER) == {"google", "microsoft", "azure-ad", "azuread", "entra-id", "office365"}`
   exactly. Any addition fails the suite and forces the contributor to read the
   docstring that explains why, which is the only point at which the invariant
   can actually be communicated.
2. A **cross-customer isolation test** asserting that a session resolved to
   `okta-beta` does not satisfy a policy of `["okta-acme"]`, and that
   `resolve_sso_provider("okta-acme") == "okta-acme"` (never `"okta"`). This is
   the behaviour FR-002 and SC-001 actually care about; it fails even if someone
   collapses aliases somewhere other than the map.
3. A `"""why"""` docstring on the map stating that entries are permitted only
   for providers that are a **single global tenant**, and that per-customer
   brokers must pass through unmapped.

**Alternatives considered**:

- *`RegexField` as the child.* Equivalent validation, but it puts the pattern in
  the serializer, so the operator path (R5) would need its own copy — the exact
  duplication FR-018/FR-022 exist to prevent. Rejected in favour of one shared
  function that both paths call.
- *Extending `PROVIDER_CHOICES` with each customer alias.* Rejected — it would
  make onboarding a customer a code change and a migration (`choices` appears in
  migration state), contradicting FR-025 and SC-010.
- *A dedicated `IdentitySource` model with a `slug` column and an FK from the
  policy.* Rejected for this delivery: it adds a table and a join to enforce a
  string shape, and FR-025 explicitly wants customer two to be data. Worth
  revisiting only if identity sources acquire attributes of their own.
- *Making `BROKER_ALIAS_TO_PROVIDER` private or frozen.* Rejected as theatre —
  nothing stops an edit to a module-level dict, and a test that fails is a louder
  signal than an underscore.

---

## R3 — Where the fail-closed branch lives

**Decision**: emptiness is decided **in the use case**, not on the model. The
model methods `is_provider_allowed` and `is_email_domain_allowed` keep their
current bodies unchanged, including `return True` on empty. A new guarded early
return goes into `EvaluateOrganizationSSOAccessUseCase.evaluate`, immediately
after the support-domain bypass and before provider resolution:

```python
if config.requires_customer_identity_source and not config.is_policy_complete_input():
    ...  # non_compliant(SSO_POLICY_INCOMPLETE)
```

— expressed as a private method on the use case
(`_refuse_incomplete_policy(config)`) that reads the two lists directly, so no
new behaviour is added to the model at all.

**Rationale**:

- Constitution I puts business rules in use cases and forbids them on models.
  The two model predicates are a **pre-existing violation** of that rule (they
  are policy decisions living on a Django model). Governance says new code MUST
  NOT copy an existing violation and a drive-by rewrite MUST NOT be included
  unless it is the declared scope. Putting the new rule on the model would copy
  the violation; rewriting the two methods would be the drive-by. Lifting the
  new rule into the use case is the only option that does neither.
- It is the only placement that keeps FR-006 provable rather than argued. The
  two model methods have exactly two callers, and one of them is the lockout
  guard in `UpdateOrganizationSSOConfigUseCase`. Changing the methods would
  change the lockout guard's behaviour for **legacy** organizations as a side
  effect — a behaviour change on organizations this delivery must not touch.
  Leaving them alone makes "legacy path unchanged" a matter of the diff, not of
  reasoning.
- The branch short-circuits before `_get_password_block_reason`, so an
  incomplete policy costs zero Keycloak lookups. That is a small, welcome
  side effect given `HasSSOAccess` constructs a fresh use case per permission
  check (see Pre-existing violations).

**Ordering decision, stated explicitly because it is contestable**: the
support-domain bypass runs **before** the incomplete-policy refusal, so a
`@weni.ai` member is still admitted to an enabled organization whose lists are
empty. The argument against is that FR-005 says an empty list "MUST deny
access", unqualified. The argument for, which we adopt:

- FR-007 makes the empty-list-while-enabled state unreachable through every
  supported write path, so it is only reachable by direct database editing —
  i.e. it is a platform-misconfiguration state, not a user-reachable one.
- US3's stated purpose is that "the platform has no way back in" must never
  happen. An incomplete policy locking out support is exactly the lockout that
  story exists to prevent, and it would lock out the only people who can fix it.
- It preserves the current structure: the bypass is already the first check
  after the `is_enabled` gate, in both the evaluation use case and the lockout
  guard. Reordering it would be a behaviour change to the legacy path.

A reviewer who prefers the literal reading of FR-005 can move one line; the
test that pins this (`test_support_domain_is_admitted_when_policy_is_incomplete`)
documents which reading is in force.

**Alternatives considered**:

- *Make the model methods marker-aware* (`is_provider_allowed` consults
  `self.requires_customer_identity_source`). Rejected per the rationale above:
  it deepens the constitution I violation and silently changes the lockout
  guard.
- *Add `OrganizationSSOConfig.is_policy_complete()` as a model method.* Tempting
  because it reads well, and it is a genuinely borderline call — it is closer to
  a data predicate than to a policy decision. Rejected because "complete" only
  has meaning relative to the fail-closed rule, which makes it a policy
  decision wearing a data predicate's clothes, and because keeping the model
  untouched is what makes the FR-006 diff argument airtight.
- *A separate `EvaluateCustomerIdentityPolicyUseCase` composed alongside the
  existing one.* Rejected — two evaluators is two vocabularies of refusal
  reasons and two orderings; the spec's own assumption is that "the existing
  per-organization evaluation … is reused rather than replaced".

---

## R4 — One shared validation point for the operator and admin paths

**Decision**: a new module `connect/usecases/organizations/sso_policy.py`
holding the policy vocabulary and one validating use case that **both** writers
call with the **resulting** state:

```python
@dataclass(frozen=True)
class OrganizationSSOPolicyDTO:
    is_enabled: bool
    allowed_email_domains: List[str]
    allowed_sso_providers: List[str]
    requires_customer_identity_source: bool

def normalize_identity_source(value: str) -> str: ...
def normalize_email_domain(value: str) -> str: ...

class ValidateOrganizationSSOPolicyUseCase:
    def execute(self, organization: Organization, policy: OrganizationSSOPolicyDTO) -> OrganizationSSOPolicyDTO
```

`SSOPolicyValidationError` joins `SSOConfigLockoutError` in the existing
`connect/usecases/organizations/exceptions.py`.

The validator owns four **state** invariants, none of which know which path
called them:

| Invariant | Requirements |
| --- | --- |
| Every identity-source value is slug-shaped, normalized | FR-003, FR-009 (provider half) |
| Every email domain is a bare domain, lowercased, trimmed — no `@`, no wildcard, no whitespace, non-empty | FR-009 |
| `requires_customer_identity_source` implies `is_enabled` **and** both lists non-empty | FR-005 (write half), FR-007, **FR-024** |
| No other customer-identity organization claims any of these domains under a different identity-source set | FR-010 |

Both writers follow the same three steps: **merge stored state with the
requested delta → validate the resulting state → persist**.

**Rationale**:

- Validating the *resulting* state rather than the delta is what makes "an
  invariant cannot hold on one path and not the other" true. `sso-settings`
  PATCH is partial: an admin sending only `allowed_email_domains: []` submits a
  delta that looks harmless in isolation and produces a forbidden state. Only
  the merged state can be checked.
- **FR-024 falls out of the third invariant for free.** If the marker implies
  `is_enabled`, then any write resulting in `is_enabled=False` while the marker
  is set is rejected as an invalid *state* — the admin path needs no
  path-specific refusal at all, and there is no second code path where the rule
  could be forgotten. The consequence to document in the runbook: the operator's
  disable operation must clear the marker and `is_enabled` **together in one
  save**, inside `transaction.atomic()`.
- **FR-023 is enforced structurally, in three independent layers**: the marker
  is absent from `OrganizationSSOConfigSerializer.Meta.fields`, so DRF drops it
  from `validated_data`; `UpdateOrganizationSSOConfigDTO` has no such attribute,
  so the view's `UpdateOrganizationSSOConfigDTO(**serializer.validated_data)`
  could not carry it even if DRF let it through; and the admin use case reads
  the marker from the stored row into the resulting-state DTO and never assigns
  it. A test asserts a PATCH body containing the marker returns 200 with the
  marker unchanged.
- A use case rather than a pure function, because FR-010 needs a query. That
  also keeps it injectable, so both writers can be tested with the real
  validator (constitution IV prefers in-process substitutes at a Django
  boundary — here the boundary is the test database, so no mock is warranted).
- Ordering inside `UpdateOrganizationSSOConfigUseCase` matters: **validate
  before** `_validate_actor_not_locked_out`. An incomplete policy should be
  reported as an incomplete policy, not as "your SSO provider is not in the
  allowed providers", which is what the lockout guard would say about an empty
  allowlist.

**A deliberate consequence worth naming**: because the marker implies
`is_enabled=True`, every customer-identity organization is inside the
`sso_config__is_enabled=True` filter that
`BuildOrganizationSSOAccessMapUseCase` and
`ExcludeNonCompliantOrganizationProjectsUseCase` already use. Neither queryset
needs a change, and there is no way to create an enabled-for-Okta organization
that those two batch paths would skip.

**Alternatives considered**:

- *A `clean()` method on the model plus `full_clean()` in both writers.*
  Rejected — `full_clean` is not called by `.save()`, so the invariant would
  hold only where someone remembered to call it, and Django's `ValidationError`
  would have to be translated at both call sites anyway. It also puts business
  rules back on the model (constitution I).
- *A database `CheckConstraint`.* Cannot express FR-010 (cross-row) or FR-003
  (regex over JSONB array elements) in Django 3.2 without raw SQL, and a
  constraint violation surfaces as an `IntegrityError` with no field-level
  message for the admin path. Considered as belt-and-braces for the
  marker-implies-`is_enabled` invariant and rejected as not worth a second
  source of truth.
- *Validation in the serializer only.* Rejected — the operator path is not an
  HTTP request under the R5 decision, so it has no serializer, and FR-018
  requires it to validate the same invariants.
- *Duplicating the rules in both use cases.* Rejected by the spec's own
  assumption that the two paths "must share one validation point".

---

## R5 — Form of the internal operational procedure

**Decision**: a Django management command,
`connect/common/management/commands/enable_customer_identity_source.py`, as a
thin composition root over a new
`EnableCustomerIdentitySourceUseCase`
(`connect/usecases/organizations/enable_customer_identity_source.py`).

```
poetry run python manage.py enable_customer_identity_source \
    --organization <org-uuid> \
    --identity-source okta-acme \
    --email-domain acme.com --email-domain acme.com.br \
    [--dry-run]

poetry run python manage.py enable_customer_identity_source \
    --organization <org-uuid> --disable
```

**Rationale**:

- **It is not a surface.** FR-021 forbids any new merchant-facing or admin
  surface for binding an organization to an identity source. A management
  command has no route, no serializer, no permission class and no client — there
  is nothing for a merchant to reach, so FR-021 is satisfied by construction
  rather than by an authorization check that has to be right.
- **It is testable at full fidelity.** `call_command` under
  `django.test.TestCase` exercises argument parsing, the use case, the shared
  validator and the database in one in-process test, with no broker, no HTTP
  and no live infrastructure (constitution IV).
- **Absence of a CRUD-command precedent is not an argument against it.** The
  repo's two commands are daemons because those are the only two long-running
  jobs it has; nothing about `BaseCommand` is daemon-specific, and the
  alternative precedents are worse (see below). The command carries no logic of
  its own: it parses arguments, builds the DTO, calls `execute()`, prints the
  resulting state. Its own coverage cost is therefore near zero.
- **Idempotency (FR-019)** is a property of the use case, and it needs one
  detail that a naive implementation gets wrong: the use case compares the
  computed resulting state against the stored row and **returns without calling
  `save()`** when they are equal. A blind `.save()` would bump `updated_at`
  (`auto_now=True`), so the stored policy would not be "unchanged" and SC-007's
  "byte-identical stored policy" would fail. The comparison is on the four
  policy fields only.
- **List replacement (FR-020)** is a property of the argument shape: the DTO
  carries whole lists, the use case **assigns** them and never extends, and the
  CLI offers `--email-domain` (repeatable, building the complete replacement
  list) with no `--add-domain` counterpart. There is no verb in the interface
  that could append, so a removed domain always loses scope.
- `--dry-run` runs the full validation and prints the resulting state without
  persisting, which is what makes the implantation runbook safe to rehearse.
  The whole operation runs inside `transaction.atomic()`, so a validation
  failure persists nothing (SC-008).
- FR-025 holds trivially: customer two is another invocation.

**Alternatives considered**:

- *Django admin* (registering `OrganizationSSOConfig` with a `ModelAdmin`).
  Rejected on three counts. It **is** a surface, reachable by any user with
  staff access, which sits uncomfortably against FR-021's intent even if a
  merchant cannot reach it. It would become a **third** write path, and a
  `ModelForm` that did not delegate to the shared validator would break the R4
  guarantee outright — while one that did delegate would still expose the raw
  JSON fields for free-form editing beside it. And free-form data editing is
  exactly what the spec's assumptions rule out: "an auditable, repeatable
  operation invoked by an operator rather than free-form data editing".
  `OrganizationSSOConfig` is deliberately left unregistered.
- *An internal endpoint under `connect/api/v2`* with `ModuleHasPermission` or
  `CanCommunicateInternally`. The strongest alternative: it follows
  constitution III's "new endpoints go under v2", gives request-level audit,
  and could be driven from an ops tool. Rejected for this delivery because
  nothing consumes it — there is no ops tool to call it, so it would ship as an
  unused authenticated write path against the most security-sensitive table in
  this feature. It is the natural upgrade the day implantation gets tooling, and
  because all logic lives in the use case, that upgrade is a view plus a
  serializer with no change to the rules.
- *A data migration per customer.* Rejected — it would put customer
  configuration in migration history, cannot be re-run, and FR-006's whole point
  is that migrations must not write policy.
- *A Celery task.* Rejected — no schedule, no queue semantics needed, and it
  would make an operator action asynchronous and harder to verify.

---

## R6 — Detecting a domain already claimed by a different customer (FR-010)

**Decision**: fetch the small candidate set and compare in Python, inside
`ValidateOrganizationSSOPolicyUseCase`:

```python
others = (
    OrganizationSSOConfig.objects
    .filter(requires_customer_identity_source=True)
    .exclude(organization_id=organization.pk)
)
```

then, for each, reject when the normalized domain sets intersect **and** the
normalized identity-source sets are not equal.

**Rationale**:

- The rule is not "this domain is used twice", it is "this domain is used twice
  **bound to a different identity source**". Both configurations' full lists are
  needed to decide that, so a database-side domain filter could only prefilter —
  and the set it prefilters is bounded by the number of customer-identity
  organizations, which is single digits now and tens later. There is nothing to
  optimize.
- Backend-agnostic. `allowed_email_domains__contains=[domain]` compiles to the
  jsonb `@>` operator, which is available here (PostgreSQL is the configured
  engine) but raises `NotSupportedError` on SQLite, so it would couple the
  validator to the deployment engine for no measurable gain.
- **`.exclude(organization_id=organization.pk)` is load-bearing.** Without it,
  re-running enablement on an organization would find that organization's own
  domains already claimed and reject itself, breaking FR-019 — the failure mode
  is easy to miss because it only appears on the second run.
- Correctness rests on normalization, not on the comparison: because every
  write goes through `normalize_email_domain`, stored domains are already
  lowercase and trimmed, so set intersection is exact and case-insensitive
  (FR-008).

**"Different identity source" is defined as set inequality.** Two configurations
sharing a domain must carry the *same* normalized identity-source set; anything
else is rejected. The alternative — reject only when the sets are **disjoint** —
admits a real hole: `["okta-acme", "google"]` and `["google", "okta-beta"]`
overlap on `google` and would pass while naming two different customers. Set
equality has a cost: the same customer's two organizations must keep identical
allowlists to share a domain. That is acceptable because FR-005 already forces a
non-empty list and the intended shape is exactly one customer source per
organization; when it bites, the operator aligns the two lists, which is an
implantation-time decision made by a human rather than a silent runtime
outcome.

**Alternatives considered**:

- *`allowed_email_domains__contains` jsonb prefilter.* Named above as the
  optimization to adopt if the enabled-organization count ever makes the scan
  matter; it would need a GIN index to be worth anything, which is not
  justified at this scale.
- *A separate `ClaimedEmailDomain` table with a unique constraint.* This is the
  only design that makes the rule race-proof rather than check-then-write. It
  is over-built for an operator-invoked procedure with no concurrency: two
  simultaneous implantation runs claiming the same domain is not a scenario this
  delivery needs to survive, and the check runs inside the enablement
  transaction. Worth revisiting if enablement ever becomes self-service.
- *Normalizing domains into a related model.* Same conclusion, plus a migration
  of existing JSONField data, which FR-006 forbids.

---

## R7 — A new `access_disabled_reason` value for incomplete policy (FR-028)

**Decision**: add one value to the existing enum:

```python
class OrganizationSSOAccessDisabledReason(str, Enum):
    ...
    SSO_POLICY_INCOMPLETE = "sso_policy_incomplete"
```

and log the refusal at `warning` (not `info`), since the state is a platform
misconfiguration.

**Rationale**:

- SC-012 permits the reason vocabulary to grow, provided additions are
  provider-agnostic: "unchanged or **purely additive with provider-agnostic
  values**". `sso_policy_incomplete` names no provider, no customer and no
  other tenant's configuration, so FR-027 and US5 AS-4 hold.
- Reusing an existing value would mislead support in the one case where the
  cause is *not* the user's session. A member told
  `sso_provider_not_allowed` will go and change how they signed in, which cannot
  possibly help, while the actual fix is an operator correcting the policy. US5
  exists to make refusals explainable; collapsing this case defeats it.
- The value is also cheap to reach correctly: it is the first thing evaluated
  after the marker check, so it can never be masked by a later rule.

**Client impact, stated both ways as required:**

| | New value `sso_policy_incomplete` (chosen) | Reuse an existing value |
| --- | --- | --- |
| Connect contract | Additive; field set unchanged. Blessed by SC-012 | Byte-identical |
| weni-webapp | Renders `orgs.access_disabled_reason.<value>` from a locale map. An unrecognised key renders a missing translation or the raw key until 4 locale files are updated (`en`, `pt_br`, `es`, `ro`) | No change |
| Support (FR-028 / SC-011) | Distinguishable in the API response *and* the logs | Distinguishable only in logs — arguably satisfies "the platform's records", but a support engineer reading the API sees the wrong cause |
| Coordination | One webapp ticket, non-blocking | None |

**The webapp obligation is therefore two items, not one**: add the four locale
keys, **and** ensure the reason-to-copy map has a generic fallback so that any
future unknown reason degrades to a neutral message rather than a raw key. The
fallback is the more important of the two, because it also covers the next
addition. Because the incomplete-policy state is unreachable through every
supported write path (FR-007), the specific copy is low-traffic while the
fallback is a permanent robustness fix.

**Alternatives considered**:

- *Reuse `sso_provider_not_allowed`.* Rejected per the table above.
- *Keep the client value generic and carry the distinction only in logs.*
  Defensible on a literal reading of FR-028 ("recoverable by support … the
  platform's records"), and it would leave the contract untouched. Rejected
  because the response *is* the record support reads first, and SC-011 asks for
  the two causes to be distinguishable without qualifying where.
- *A separate boolean field on the response* (e.g.
  `access_disabled_is_platform_fault`). Rejected — a second field is a larger
  contract change than a new enum value, and SC-012 blesses the latter
  specifically.

---

## R8 — Scope of the FR-017 fix

**Finding**: `get_can_update_password`
(`connect/api/v1/account/serializers.py:101`) returns `True` when the user has
no identity-provider history, otherwise `False` when the user holds any
authorization in an organization with `sso_config__is_enabled=True`. It never
consults the support-domain exception, so an invited `@weni.ai` member of any
enforcing organization is told password management is unavailable — a direct
FR-017 and SC-005 failure.

**Decision**: one early return, reusing the existing predicate:

```python
def get_can_update_password(self, obj):
    if is_sso_internal_bypass_email(obj.email):
        return True
    ...
```

**Rationale**:

- Reusing `is_sso_internal_bypass_email` rather than re-deriving the domain
  check means the exception's boundary is shared with evaluation by
  construction. FR-016 (`@notweni.ai` and `@vtex.com.br` must not qualify) is
  then covered by the same code that already covers it for access evaluation,
  with no second definition to drift. A local domain comparison here would be
  the beginning of exactly that drift.
- It is a one-line early return in an existing method — no new field, no new
  route, no change to the response shape.

**The second half of the question — does the password-set path have the same
gap?** No, and the reason is worth recording: `change_password`
(`connect/api/v1/account/views.py:133`) has **no SSO gate at all**. It validates
the serializer and calls Keycloak `set_user_password` unconditionally. So:

- There is nothing to fix there for FR-017. The write path never blocked
  support-domain users, so SC-005 ("can set and keep a platform password in 100%
  of attempts") already holds on the write side once the advisory flag is
  corrected.
- The finding to report: **`can_update_password` is advisory only.** A
  non-support member of an enforcing organization is told `False` and can still
  set a password by calling the endpoint directly. Adding enforcement there
  would be a *new* restriction that no requirement in this spec asks for, on
  code marked `# pragma: no cover`. Out of scope, reported rather than fixed, so
  a follow-up spec can decide whether the flag should become a gate.

**Arguing it as a v1 bugfix (constitution III):** constitution III forbids
expanding `connect/api/v1` "except when the change is a bugfix in v1". This
qualifies, and it is not close:

- No new endpoint, no new field, no change to the response shape. The
  `can_update_password` boolean already exists and is already documented; only
  the value it computes for one class of user changes.
- The current value **contradicts the platform's own enforcement**.
  `is_sso_internal_bypass_email` is already the platform-wide support exception,
  honoured by `EvaluateOrganizationSSOAccessUseCase` and by
  `UpdateOrganizationSSOConfigUseCase`. A serializer that reports on
  enforcement while disagreeing with it is reporting a wrong answer — the
  definition of a bug.
- Moving it to v2 is not an option: FR-026 requires the existing contract to
  keep working, and there is no v2 account serializer to move it to. Relocating
  it would *create* the breaking change the spec forbids.

**A related v1 tension to flag rather than resolve silently** (per the
constitution's Development Workflow): R2 widens the accepted input of
`OrganizationSSOConfigSerializer.allowed_sso_providers` on the v1
`sso-settings` route, and R4 adds validation to the same route. Neither adds an
endpoint or a field, and the widening is strictly backward compatible — every
payload valid before stays valid. It is nonetheless a change to a v1 contract,
made because FR-022 requires admins to keep write access and this is the only
admin path that exists. Recorded here so review can weigh it; the alternative
(a v2 admin route duplicating the v1 one) would leave two admin write paths and
break R4's single-validation-point guarantee.

---

## Pre-existing constitution violations this delivery works alongside

Governance requires these to be named in the plan and **not** rewritten as
drive-by work, since none of them is the declared scope of this spec.

| Violation | Principle | Where | Why we leave it |
| --- | --- | --- | --- |
| Business rules on a Django model — `is_provider_allowed`, `is_email_domain_allowed` | I | `connect/common/models.py:343,350` | Rewriting them changes the legacy evaluation path, which is what FR-006 protects. R3 routes around them instead |
| Function-local import to dodge a circular import in `serialize_organization_access_status` | I (lazy imports forbidden) | `connect/api/v1/organization/serializers.py:65` | Fixing it means restructuring the serializer/use-case boundary across v1 and v2. Untouched by this delivery |
| A use case reaching into a DRF view — `enrich_serializer_context_with_sso_access(view, context)` | I (use cases are framework-agnostic) | `connect/usecases/organizations/sso_access.py:217` | Both v1 and v2 org viewsets call it; moving it is an API-layer refactor of its own |
| v2 serializers importing v1 helpers | III (layering) | `connect/api/v2/organizations/serializers.py:23` | It is what makes the contract single-sourced today, which this delivery benefits from. See note below |
| Authorization inside a view body — `_assert_admin` plus a manual `check_object_permissions` | II | `connect/api/v1/organization/views.py:689,706,724` | Pre-dates this spec. The delivery adds no logic to the view body |
| `# pragma: no cover` over business logic — `change_password`, `OrganizationHasPermission` | IV | `connect/api/v1/account/views.py:133`, `connect/api/v1/organization/permissions.py:12` | Not touched. Reported under R8 |
| `HasSSOAccess._is_compliant` constructs a fresh `EvaluateOrganizationSSOAccessUseCase` per call, discarding the per-instance memo | V (cost, not correctness) | `connect/api/v1/organization/permissions.py:184` | Redis caching of positive password lookups mitigates it; the R3 branch adds no lookup |

**The v2-imports-v1 note cuts in our favour.** Because
`connect/api/v2/organizations/serializers.py` imports
`serialize_organization_sso_config` and
`serialize_organization_access_status` from the v1 module, the `sso_config`
payload and the `access_status` / `access_disabled_reason` pair are produced by
one implementation for both API versions. The new reason value from R7 therefore
appears in v2 with no v2 code change, and FR-026 coverage is a matter of
asserting both serializers rather than changing both.

---

## Requirements with no code change, needing regression coverage only

- **FR-013 / SC-006** — authentication must never create membership. Verified in
  the code: `WeniOIDCAuthenticationBackend.create_user`
  (`connect/middleware.py:60`) creates a `User` and calls
  `check_module_permission`, which (`connect/utils.py:54`) only grants the
  Django `can_communicate_internally` permission and never touches
  `OrganizationAuthorization`. Ships as a regression test, no change.
- **FR-011 / SC-003** — per-organization evaluation already holds; the marker is
  per `OrganizationSSOConfig` row, so a dual-membership session is unaffected on
  the non-enforcing side. Extend the matrix, no change.
- **FR-014** — indeterminate password state already denies with
  `sso_credential_unavailable`. The R3 branch runs before the credential lookup,
  so it cannot weaken this. Assert both orderings.
