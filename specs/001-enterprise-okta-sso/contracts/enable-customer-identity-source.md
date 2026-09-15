# Contract — operator enablement procedure

**Feature**: `001-enterprise-okta-sso` | **Date**: 2026-09-01

The internal operational procedure required by FR-018 … FR-020 and FR-025. It
is a Django management command, not an HTTP endpoint; the choice is argued in
[research.md](../research.md#r5--form-of-the-internal-operational-procedure).

Because it has no route, no serializer and no client, FR-021 ("MUST NOT add any
new merchant-facing or admin surface") holds by construction rather than by an
authorization check. `OrganizationSSOConfig` is deliberately left unregistered
in Django admin for the same reason.

## Invocation

```
poetry run python manage.py enable_customer_identity_source \
    --organization <organization-uuid> \
    --identity-source <slug> \
    --email-domain <domain> [--email-domain <domain> …] \
    [--dry-run]

poetry run python manage.py enable_customer_identity_source \
    --organization <organization-uuid> --disable [--dry-run]
```

| Argument | Required | Meaning |
| --- | --- | --- |
| `--organization` | yes | Public `uuid` of the Connect organization |
| `--identity-source` | yes unless `--disable` | Keycloak broker alias for the customer, e.g. `okta-acme`. Repeatable; the values **replace** `allowed_sso_providers` wholesale |
| `--email-domain` | yes unless `--disable` | Bare domain in the policy scope. Repeatable; the values **replace** `allowed_email_domains` wholesale |
| `--disable` | no | Clears the marker and `is_enabled` in one save |
| `--dry-run` | no | Validates and prints the resulting state; persists nothing |

**There is no `--add-domain` and no `--remove-domain`.** The interface offers no
verb that could append, which is how FR-020 is guaranteed: re-running with a
shorter list actually removes scope.

## Behaviour

1. Resolve the organization by `uuid`; a miss exits non-zero with a message.
2. Load or build the `OrganizationSSOConfig` row.
3. Compute the resulting state: `is_enabled=True`,
   `requires_customer_identity_source=True`, and the two lists **assigned** from
   the arguments (or, for `--disable`, both booleans `False` with the lists left
   as stored).
4. Validate through `ValidateOrganizationSSOPolicyUseCase`, which normalizes and
   enforces invariants I1–I4 (see [data-model.md](../data-model.md#invariants-owned-by-validateorganizationssopolicyusecase)).
5. Compare the validated resulting state against the stored row on the four
   policy fields. **If equal, log and return without calling `save()`.**
6. Otherwise persist and log.

Steps 2–6 run inside `transaction.atomic()`, so a validation failure persists
nothing (SC-008).

### Idempotency (FR-019, SC-007)

Step 5 is the whole mechanism, and it carries one detail that a naive
implementation gets wrong: `updated_at` is `auto_now=True`, so an unconditional
`save()` would move the timestamp and the stored policy would not be
"unchanged". The comparison is on `is_enabled`,
`requires_customer_identity_source`, `allowed_email_domains` and
`allowed_sso_providers` only, after normalization — so re-running with
`ACME.COM` and `acme.com` is also a no-op.

The row is a `OneToOneField` on `Organization`, so a second policy record for
the same organization is impossible at the schema level; "no second or
interchangeable policy" needs no additional check.

### Exit codes and output

| Situation | Exit | Output |
| --- | --- | --- |
| Enabled, state changed | `0` | The resulting policy |
| Enabled, state already correct | `0` | The policy plus an explicit "unchanged" note |
| `--dry-run`, would validate | `0` | The resulting policy plus a "not persisted" note |
| Validation failed | non-zero (`CommandError`) | The invariant that failed |
| Organization not found | non-zero (`CommandError`) | The uuid that was not found |

Printed output shows the organization, the marker, the identity sources and the
domains. It contains no identity-provider secret and no other organization's
configuration (FR-029); the domain-conflict message says a domain is already in
use, never by whom.

## Worked sequence

```
# 1. Rehearse
… --organization 1a2b… --identity-source okta-acme --email-domain acme.com --dry-run

# 2. Enable
… --organization 1a2b… --identity-source okta-acme --email-domain acme.com

# 3. Re-run — proves idempotency; updated_at must not move
… --organization 1a2b… --identity-source okta-acme --email-domain acme.com

# 4. Add a second domain — the full list is restated, not appended to
… --organization 1a2b… --identity-source okta-acme \
      --email-domain acme.com --email-domain acme.com.br

# 5. Second customer — another run, no schema change (FR-025, SC-010)
… --organization 9z8y… --identity-source okta-beta --email-domain beta.com

# 6. Rejected: beta claiming acme.com under a different source (FR-010)
… --organization 9z8y… --identity-source okta-beta --email-domain acme.com

# 7. Disable — clears marker and is_enabled together
… --organization 1a2b… --disable
```

## Layering

The command is a composition root and carries no logic: it parses arguments,
builds the DTO, calls `EnableCustomerIdentitySourceUseCase.execute()`, and
prints the result. All rules live in the use case and the shared validator, both
under `connect/usecases/organizations`. Keeping it that thin is what makes the
future upgrade to an internal v2 endpoint (if ops tooling ever needs one) a view
plus a serializer, with no change to the rules — and it keeps the command's own
coverage burden near zero while `call_command` still exercises the whole path in
process.
