# Contract — organization access policy (HTTP)

**Feature**: `001-enterprise-okta-sso` | **Date**: 2026-09-01

Delta only. Every field and endpoint not listed here is unchanged. The
governing requirement is FR-026: existing clients must not need a change to
keep working.

## Endpoints touched

| Method | Endpoint | Change |
| --- | --- | --- |
| `GET` | `/v1/organization/org/` and `/v1/organization/org/{uuid}/` | One new possible value of `access_disabled_reason` |
| `GET` | `/v2/organizations/` and `/v2/organizations/{uuid}/` | Same |
| `GET` | `/v1/organization/org/{uuid}/sso-settings/` | Response shape unchanged |
| `PATCH` | `/v1/organization/org/{uuid}/sso-settings/` | Accepted values widened; new rejection cases |
| `GET` | `/v1/account/profile/` (`can_update_password`) | Corrected value for support-domain members |

**No endpoint is added**, in v1 or v2. The operator procedure is a management
command, not an HTTP route — see
[enable-customer-identity-source.md](./enable-customer-identity-source.md).

## Organization read payloads (v1 and v2)

`access_status`, `access_disabled_reason` and `sso_config` are produced by
`serialize_organization_sso_config` and
`serialize_organization_access_status` in
`connect/api/v1/organization/serializers.py`, which the v2 serializer imports.
The contract is therefore single-sourced and identical across both versions;
tests must assert both, but only one implementation exists.

### `sso_config` — unchanged

```json
{
  "is_enabled": true,
  "allowed_email_domains": ["acme.com"],
  "allowed_sso_providers": ["okta-acme"]
}
```

Exactly three keys, as today. `requires_customer_identity_source` is
**deliberately not exposed** — the marker is absent from
`OrganizationSSOConfigSerializer.Meta.fields`, which keeps the payload
byte-identical (FR-026) and is the structural enforcement of FR-023.

The only observable difference is that `allowed_sso_providers` may now contain a
per-customer value such as `"okta-acme"` in addition to `"google"` and
`"microsoft"`. Clients that render this list must not assume a closed set. The
webapp's existing use — showing which provider is required — degrades to
displaying the raw slug, which is acceptable because FR-027 already forbids
provider-named copy; the recommended UX is to stop naming the provider at all.

### `access_status` — unchanged

`"active"` | `"disabled"`.

### `access_disabled_reason` — one value added

`null` when active. Otherwise one of:

| Value | Status | Client guidance |
| --- | --- | --- |
| `sso_session_required` | existing | Prompt to sign in through SSO. Copy must stop naming Google/Microsoft |
| `sso_provider_not_allowed` | existing | Session's identity source is not permitted here |
| `sso_email_domain_not_allowed` | existing | Domain restriction; contact the organization admin |
| `sso_password_configured` | existing | A platform password must be removed |
| `sso_credential_unavailable` | existing | Generic technical message; retry later |
| **`sso_policy_incomplete`** | **NEW** | Generic technical message; contact support. It is a platform misconfiguration, not something the member can act on |

Additive and provider-agnostic, which SC-012 permits explicitly. Consumers must
treat the enum as **open**: an unrecognised value has to render a neutral
fallback message rather than a raw key. See the webapp obligation in
[plan.md](../plan.md#documentation-obligations).

### Example — refused for an incomplete policy

```json
{
  "uuid": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "name": "Acme",
  "is_suspended": false,
  "sso_config": {
    "is_enabled": true,
    "allowed_email_domains": [],
    "allowed_sso_providers": []
  },
  "access_status": "disabled",
  "access_disabled_reason": "sso_policy_incomplete"
}
```

Reachable only if the row was edited outside the supported write paths, since
invariant I3 rejects this state at every writer.

### Example — refused because the session carries another customer's source

```json
{
  "access_status": "disabled",
  "access_disabled_reason": "sso_provider_not_allowed",
  "sso_config": {
    "is_enabled": true,
    "allowed_email_domains": ["acme.com"],
    "allowed_sso_providers": ["okta-acme"]
  }
}
```

The response names neither the session's source nor the other customer
(FR-027, FR-029).

## Deep access — unchanged

Organization reads keep returning `200` with disabled metadata; project access,
organization writes, authorization mutations and the contact-active actions keep
returning `403` for a non-compliant session. `HasSSOAccess` calls the same use
case, so it picks up the new refusal with no permission-class change.

## `PATCH /v1/organization/org/{uuid}/sso-settings/`

Admin-only, unchanged in shape. Request and response bodies remain the three
`sso_config` keys.

### Widened input

`allowed_sso_providers` was `ChoiceField(choices=[google, microsoft])`. It
becomes a normalized, shape-validated string:

- lowercased and trimmed;
- must match `^[a-z0-9]+(-[a-z0-9]+)*$`, at most 63 characters.

**Strictly backward compatible**: `google` and `microsoft` both match, so every
payload that validated before still validates.

```json
{ "is_enabled": true,
  "allowed_sso_providers": ["okta-acme"],
  "allowed_email_domains": ["acme.com"] }
```

### New rejections — `400`, nothing persisted

Validation runs on the **resulting** state (stored row merged with the partial
body), so a delta that looks harmless in isolation is still caught.

| Request | Outcome | Requirement |
| --- | --- | --- |
| Either list emptied on a customer-bound organization | `400` | FR-005, FR-022 |
| `is_enabled: false` on a customer-bound organization | `400` | FR-024 |
| A domain containing `@`, a wildcard, whitespace, or an empty entry | `400` | FR-009 |
| An identity-source value that is not slug-shaped | `400` | FR-003 |
| A domain already claimed by another customer-bound organization under a different identity source | `400` | FR-010 |
| A valid non-empty domain list on a customer-bound organization | `200` | FR-022, SC-009 |
| `requires_customer_identity_source` present in the body | `200`, **silently ignored**, marker unchanged | FR-023 |

The marker is dropped by DRF because it is not in `Meta.fields`; the request is
not rejected. That is intentional — rejecting would leak the existence of the
field to a surface that must not know about it.

Error bodies follow the existing shape used for `SSOConfigLockoutError`:

```json
{ "detail": "…" }
```

Messages describe the invariant that failed (which list is empty, which domain
is malformed) and must name no other organization and no other customer's
configuration (FR-029). The domain-conflict message says that the domain is
already in use, never by whom.

Validation runs **before** the existing lockout guard, so an incomplete policy
is reported as an incomplete policy rather than as "your SSO provider is not in
the allowed providers".

## `GET /v1/account/profile/` — `can_update_password`

Shape unchanged; the value is corrected. A member whose email domain is exactly
a support domain now receives `true` even while belonging to an enforcing
organization (FR-017, SC-005). `@notweni.ai` and `@vtex.com.br` are unaffected,
because the fix reuses the same exact-match predicate as access evaluation
(FR-016).

Known and unchanged: `POST /v1/account/profile/change_password/` enforces no SSO
policy at all, so `can_update_password` is advisory. Reported in
[research.md](../research.md#r8--scope-of-the-fr-017-fix), out of scope here.
