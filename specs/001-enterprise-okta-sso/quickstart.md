# Quickstart — validating the Connect slice of Enterprise Okta login

**Feature**: `001-enterprise-okta-sso` | **Date**: 2026-09-01

Runnable scenarios that prove the delivery end to end. This is a validation
guide: it names what to run and what to expect, not how to implement anything.
Design details live in [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md) and [contracts/](./contracts/).

## Prerequisites

- Python 3.8, Poetry, `poetry install`
- PostgreSQL reachable at `DEFAULT_DATABASE` (default
  `postgres://weni:weni@localhost:5432/weni`)
- No Keycloak, Redis or RabbitMQ required. Every scenario below either injects a
  fake credentials service or pins the cache to `LocMemCache`

The test suite must never reach live infrastructure (constitution IV). If a run
tries to open a Keycloak or broker connection, that is a defect in the test, not
a missing dependency.

## Setup

```bash
poetry install
poetry run python manage.py migrate            # must apply connect/common 0100
poetry run flake8 connect/
```

Confirm the migration is schema-only — this is the check that FR-006 and SC-002
rest on, and it should be part of review, not just of testing:

```bash
poetry run python manage.py sqlmigrate common 0100
grep -c RunPython connect/common/migrations/0100_*.py    # expect 0
```

## Run the suites

```bash
# Everything this delivery touches
poetry run python manage.py test \
    connect.usecases.organizations.tests \
    connect.api.v1.tests.test_sso_enforcement \
    connect.tests.test_middleware_sso

# Full suite with coverage, as CI runs it
poetry run coverage run manage.py test
poetry run coverage report -m | tail -40
poetry run python contrib/compare_coverage.py
```

`compare_coverage.py` must not report a decrease. Nothing in this delivery
warrants `# pragma: no cover`: the management command's argument plumbing is
exercised through `call_command`.

## Scenario 1 — One customer's identity source, and only that one

Covers US1, FR-001, FR-002, SC-001.

Configure an organization with `allowed_sso_providers=["okta-acme"]`,
`allowed_email_domains=["acme.com"]`, marker set. Evaluate a member on
`@acme.com` with no platform password across the full session matrix.

| Session identity source | Expected `access_status` | Expected reason |
| --- | --- | --- |
| `okta-acme` | `active` | `null` |
| `okta-beta` | `disabled` | `sso_provider_not_allowed` |
| `google` | `disabled` | `sso_provider_not_allowed` |
| `microsoft` | `disabled` | `sso_provider_not_allowed` |
| `github` | `disabled` | `sso_provider_not_allowed` |
| none | `disabled` | `sso_session_required` |

Also assert directly that `resolve_sso_provider("okta-acme") == "okta-acme"` and
never `"okta"`, and that the `BROKER_ALIAS_TO_PROVIDER` keys are exactly the six
existing entries. That pinned-map assertion is the mechanism that stops a future
contributor from collapsing two customers into a shared vendor family.

Then, with the same member holding a platform password on an `okta-acme`
session: `disabled` / `sso_password_configured` (US1 AS-7). With the password
state indeterminate: `disabled` / `sso_credential_unavailable` (FR-014).

## Scenario 2 — Fail-closed only where the marker is set

Covers US2, FR-005, FR-006, SC-002. This is the scenario that protects existing
customers, so run it before enabling anything in a real environment.

Create **two** organizations, both `is_enabled=True` with both lists empty.
Set the marker on one only.

| Organization | Any session | Expected |
| --- | --- | --- |
| Marked | any | `disabled` / `sso_policy_incomplete` |
| Unmarked | `google` | `active` — exactly as before this delivery |
| Unmarked | none | `disabled` / `sso_session_required` — exactly as before |

Then assert the migration wrote nothing: after `migrate`, every pre-existing
`OrganizationSSOConfig` row has `requires_customer_identity_source=False` and
its other four fields byte-identical to before (US2 AS-4).

Finally, attempt to enable the marker while a list is empty, through **both**
paths — the management command and `PATCH …/sso-settings/`. Both must refuse
with nothing persisted (US2 AS-5, FR-007).

## Scenario 3 — Support staff keep a way in

Covers US3, FR-015 … FR-017, SC-004, SC-005.

With a customer-bound organization, invite one member per domain and evaluate on
a platform-password session (no identity source at all):

| Member domain | Expected |
| --- | --- |
| `@weni.ai` | `active` |
| `@vtex.com` | `active` |
| `@notweni.ai` | `disabled` |
| `@vtex.com.br` | `disabled` |
| `@partner.com` | `disabled` |

Set `SSO_INTERNAL_BYPASS_EMAIL_DOMAINS` through `@override_settings` rather than
relying on the default, so the test states its own premise.

Then `GET /v1/account/profile/` as the `@weni.ai` member while they belong to an
enforcing organization: `can_update_password` must be `true` (FR-017, SC-005).
That assertion fails against the current code, which is the bug R8 fixes.

Also assert the R3 ordering decision explicitly: a `@weni.ai` member of a marked
organization whose lists are empty is still `active`. If a reviewer prefers the
literal reading of FR-005, this is the single test that changes.

## Scenario 4 — Operator enablement, twice

Covers US4, FR-018 … FR-020, FR-025, SC-007, SC-010. Contract:
[contracts/enable-customer-identity-source.md](./contracts/enable-customer-identity-source.md).

```bash
ORG=<organization-uuid>

# Rehearse — validates, persists nothing
poetry run python manage.py enable_customer_identity_source \
    --organization $ORG --identity-source okta-acme --email-domain acme.com --dry-run

# Enable
poetry run python manage.py enable_customer_identity_source \
    --organization $ORG --identity-source okta-acme --email-domain acme.com

# Re-run — must be a no-op
poetry run python manage.py enable_customer_identity_source \
    --organization $ORG --identity-source okta-acme --email-domain acme.com
```

Expected after the second run: the four policy fields unchanged **and
`updated_at` unchanged**. The timestamp is the sharp end of SC-007's
"byte-identical stored policy" — an implementation that calls `save()`
unconditionally passes a field-by-field check and fails this one.

Then, re-run with `--email-domain acme.com.br` only. `acme.com` must be **gone**,
not retained (FR-020).

Enable a second customer (`okta-beta` / `beta.com`) on another organization and
confirm neither customer's session opens the other's organization (US4 AS-7,
SC-001). No schema change was needed (SC-010).

Attempt to claim `acme.com` for the beta organization: refused, nothing
persisted (US4 AS-3, FR-010). Then confirm the positive case — a *second* Acme
organization with the identical identity-source list may share `acme.com`,
because one customer may hold several organizations.

Confirm there is no product surface: `OrganizationSSOConfig` is not registered
in Django admin, and no route exposes `requires_customer_identity_source`
(US4 AS-4, FR-021).

## Scenario 5 — Admin edits stay self-service, binding stays operator-owned

Covers US4 AS-5/AS-6, FR-022 … FR-024, SC-008, SC-009. All against
`PATCH /v1/organization/org/{uuid}/sso-settings/` on a customer-bound
organization, as a compliant admin.

| Request body | Expected |
| --- | --- |
| `{"allowed_email_domains": ["acme.com", "acme.io"]}` | `200`, persisted |
| `{"allowed_email_domains": []}` | `400`, nothing persisted |
| `{"allowed_sso_providers": []}` | `400`, nothing persisted |
| `{"is_enabled": false}` | `400`, nothing persisted |
| `{"allowed_email_domains": ["@acme.com"]}` | `400` |
| `{"allowed_email_domains": ["*.acme.com"]}` | `400` |
| `{"allowed_sso_providers": ["Okta Acme!"]}` | `400` |
| `{"requires_customer_identity_source": false}` | `200`, marker **unchanged** |
| `{"allowed_sso_providers": ["google"]}` on a *legacy* org | `200` — the old vocabulary still validates |

The marker case is the important one: DRF drops the unknown key, so the request
succeeds while the marker stands. Assert the stored marker after the call, not
just the status code.

Re-verify each rejection left the database untouched by reloading the row — a
`400` with a partially written row would satisfy the status assertion and
violate FR-022.

## Scenario 6 — Refusals are explainable; authentication grants nothing

Covers US5 and US6, FR-013, FR-028, FR-029, SC-006, SC-011.

Trigger each refusal kind and confirm the log line carries the organization, the
member and the resolved identity source, and that `sso_policy_incomplete` is
distinguishable from the session refusals (it is logged at `warning`, the others
at their current level). Assert no log line and no response body contains an
identity-provider secret or another organization's configuration.

For US6: authenticate a user on a mapped domain who holds no
`OrganizationAuthorization`, and confirm no authorization row is created, the
organization is absent from their list, and deep access by direct reference
returns `403`. This already holds — `create_user` only grants the Django
`can_communicate_internally` permission — so it ships as regression coverage.

## Definition of done

- [ ] All six scenarios pass
- [ ] `flake8 connect/` clean
- [ ] `compare_coverage.py` reports no decrease; no new `# pragma: no cover`
- [ ] Migration `0100` contains no `RunPython`
- [ ] `access_status` / `access_disabled_reason` / `sso_config` asserted on both
      the v1 and v2 organization serializers
- [ ] weni-webapp ticket opened for the `sso_policy_incomplete` locale keys, the
      unknown-reason fallback, and the provider-agnostic rewrite of
      `sso_session_required`
