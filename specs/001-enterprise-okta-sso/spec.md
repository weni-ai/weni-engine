# Feature Specification: Enterprise Okta login — Connect organization access policy

**Feature Branch**: `001-enterprise-okta-sso`

**Created**: 2026-09-01

**Status**: Clarified

**Input**: Engineering spec for the `weni-engine` (Connect) slice of the ratified product spec *Enterprise Okta login*. Connect must enforce, per organization, that members sign in through **one specific customer's** Okta identity source rather than through any SSO provider, must fail closed on incomplete policy for organizations enabled for this delivery, must leave every other organization's behaviour untouched, and must let implantation enable a customer without any merchant-facing configuration surface.

## Inheritance from Product Spec

| Field | Value |
| --- | --- |
| Product spec | Enterprise Okta login — `weni-ai/vtex-cx-experience-specs`, `specs/003-okta-login/spec.md` |
| Pinned version | `003-okta-login-v2` (`14f91f5`) |
| Inherited binding decisions | BD-001 … BD-009 (all binding, none renegotiated) |
| Scope of this spec | `weni-engine` (Connect) changes only |
| Divergences | None |

Product requirements are referenced inline as `P:FR-00x`, `P:NFR-00x`, `P:BD-00x`, `P:SC-00x`.

### Cross-repo division of labour

The product spec assigns the login experience and identity routing to the Keycloak realm and theme, and organization access policy to Connect. This spec covers **only the Connect half**.

| Product capability | Owning repo | In this spec |
| --- | --- | --- |
| Identity-first login step, third-party actions, login copy and locales (`P:FR-001`, `P:FR-003`, `P:NFR-005`) | `connect-keycloak` | No |
| Email domain → customer identity source routing, doors A/B/C, direct-start identifier handling (`P:FR-002` routing half, `P:FR-013`) | `connect-keycloak` | No |
| Session issuance and the identity-source claim on the session (`P:BD-001`) | `connect-keycloak` | Consumed, not produced |
| Removal of platform passwords for members at go-live (`P:FR-010` action) | Implantation / ops runbook | Verification only |
| Blocked-organization copy rendering, direct-start link handling in the web app (`P:FR-012` strings) | `weni-webapp` | No |
| **Per-organization access policy and its evaluation** (`P:FR-005` … `P:FR-011`, `P:FR-014` … `P:FR-017`) | **`weni-engine`** | **Yes** |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A customer organization admits only that customer's identity source (Priority: P1)

Maria belongs to Acme, which is configured for Acme's Okta, and to Side Project, which has no SSO policy. When Maria's session was established through Acme's Okta, both organizations are usable. When her session was established any other way — a platform password, GitHub, Google, Microsoft, or a *different* customer's Okta — Acme is reported as disabled with a reason, while Side Project stays fully usable.

**Why this priority**: This is the enforcement rule the whole delivery exists for, and it is the one place where a defect leaks one customer's tenant into another's. Nothing else can ship without it.

**Independent Test**: Configure one organization for a specific customer identity source. Exercise it with a session carrying that source, a session carrying a second customer's Okta source, a session carrying a public third-party source, and a session with no source at all. Only the first admits; the non-enforcing organization admits in every case.

**Acceptance Scenarios**:

1. **Given** an organization configured for customer A's identity source, **When** a member's session carries that exact source and the member has no platform password, **Then** the organization is active and deep access (projects, writes, authorization changes) is permitted.
2. **Given** the same organization, **When** a member's session carries customer B's Okta identity source, **Then** the organization is reported disabled for the reason "identity source not allowed" and deep access is refused.
3. **Given** the same organization, **When** a member's session carries a public third-party source (GitHub, Google, or Microsoft), **Then** the organization is reported disabled and deep access is refused.
4. **Given** the same organization, **When** a member's session carries no identity source at all, **Then** the organization is reported disabled for the reason "SSO session required".
5. **Given** a member of both that organization and an organization with no SSO policy, **When** the session satisfies the first, **Then** both are usable without re-authenticating.
6. **Given** that same dual member, **When** the session does *not* satisfy the enforcing organization, **Then** the non-enforcing organization stays fully usable and only the enforcing one is disabled.
7. **Given** a member whose session carries the correct customer identity source but who still has a platform password, **When** access is evaluated, **Then** the organization is reported disabled for the reason "password configured".

---

### User Story 2 - Incomplete policy denies on enabled organizations and changes nothing elsewhere (Priority: P1)

An organization enabled for customer-Okta login whose allowed-identity-source list or allowed-email-domain list is empty must deny, never admit. Every organization *not* enabled for this delivery — including existing SSO organizations that already have empty lists and are admitted today — must behave exactly as it does now.

**Why this priority**: Today an empty list means "allow anything". Flipping that platform-wide would silently lock existing customers out of their own organizations; not flipping it at all turns a half-finished Okta enablement into "any SSO passes", which is the security hole the product spec calls out. The rule only works if it is scoped.

**Independent Test**: Take two organizations that both have SSO enabled with empty lists. Mark only one as enabled for customer-Okta login. The marked one denies every session; the unmarked one admits exactly the sessions it admitted before the change. Confirm no stored policy on the unmarked organization was rewritten.

**Acceptance Scenarios**:

1. **Given** an organization enabled for customer-Okta login with an empty allowed-identity-source list, **When** any session is evaluated, **Then** access is denied — the empty list MUST NOT mean "any source passes".
2. **Given** an organization enabled for customer-Okta login with an empty allowed-email-domain list, **When** any session is evaluated, **Then** access is denied — the empty list MUST NOT mean "any domain is in scope".
3. **Given** an existing SSO-enforcing organization that is **not** enabled for customer-Okta login and has an empty allowed-identity-source list, **When** a session with any SSO source is evaluated, **Then** it is admitted exactly as before this delivery.
4. **Given** any organization not enabled for customer-Okta login, **When** this delivery is deployed, **Then** its stored policy is unchanged and no migration has rewritten it.
5. **Given** an operator attempts to enable customer-Okta login on an organization while either list is empty, **When** the operation runs, **Then** it is rejected with an explanation and nothing is persisted.

---

### User Story 3 - Support staff reach a customer organization without that customer's Okta (Priority: P1)

An invited user whose email domain is `@weni.ai` or `@vtex.com` can open an Okta-configured organization on any session — platform password, GitHub, Google, or Microsoft — and is allowed to keep a platform password. No other email domain gets this exception.

**Why this priority**: Without it, the moment a customer goes live, Weni and VTEX support lose access to the organization they are supporting, and the platform has no way back in. It is also the only sanctioned exception, so its boundary must be exact.

**Independent Test**: Invite a `@weni.ai` user and a `@partner.com` user into an Okta-configured organization. Give both a platform-password session. The support user is admitted and may still manage their password; the other is refused.

**Acceptance Scenarios**:

1. **Given** an invited `@weni.ai` member of an Okta-configured organization, **When** their session comes from a platform password, **Then** the organization is active and deep access is permitted.
2. **Given** an invited `@vtex.com` member of the same organization, **When** their session comes from GitHub, Google, or Microsoft, **Then** the organization is active.
3. **Given** an invited `@weni.ai` member who belongs to an SSO-enforcing organization, **When** they inspect or change their own account password settings, **Then** setting and keeping a platform password is permitted.
4. **Given** an invited member on any other email domain, **When** their session does not carry the organization's customer identity source, **Then** the organization is disabled for them.
5. **Given** a member on a domain that merely *ends with* a support domain (for example `@notweni.ai` or `@vtex.com.br`), **When** access is evaluated, **Then** the exception does **not** apply.

---

### User Story 4 - Implantation enables a customer without a merchant-facing surface (Priority: P2)

An operator enables customer-Okta login for an organization as part of an implantation request: the organization's policy is turned on, bound to that customer's identity source, and given that customer's email domains. There is no merchant or admin product screen that can create or edit this connection. Running the same enablement twice changes nothing. A second customer is enabled the same way, with no new surface.

**Why this priority**: The product spec forbids a v1 configuration UI, and the first customers cannot go live without some enablement path. It is P2 only because Stories 1–3 define the behaviour this story configures.

**Independent Test**: Enable a customer through the internal operation, verify the organization now enforces that customer's identity source, run the identical operation again and confirm the stored policy is unchanged and no duplicate policy exists. Then enable a second customer and confirm neither customer's session opens the other's organization.

**Acceptance Scenarios**:

1. **Given** an implantation request for a customer, **When** the operator runs the internal enablement with the customer's identity source and email domains, **Then** the organization enforces that source and those domains.
2. **Given** an organization already enabled for a customer, **When** the identical enablement runs again, **Then** the result is unchanged and no second or interchangeable policy is created.
3. **Given** a domain already claimed by one customer-Okta-enabled organization, **When** an operator tries to claim it for another organization bound to a *different* identity source, **Then** the operation is rejected and nothing is persisted.
4. **Given** a merchant admin browsing organization or project settings, **When** they look for a way to attach a customer identity connection, **Then** no such product surface exists.
5. **Given** an admin of an enabled organization, **When** they edit the email-domain list to a valid non-empty list, **Then** the change is accepted.
6. **Given** that same admin, **When** they try to empty either list, clear the customer-Okta enablement attribute, or turn enforcement off, **Then** the attempt is rejected and nothing is persisted.
7. **Given** two customers each enabled through this operation, **When** a member of the first signs in, **Then** the second customer's organization is not opened by that session.

---

### User Story 5 - Support can explain a refusal without inspecting another tenant (Priority: P2)

When a member reports "I cannot open this organization", support can determine why from the platform's own records: which organization, which member, which identity source established the session, and which rule refused it. Nothing in those records exposes an identity-provider secret or another customer's configuration.

**Why this priority**: The first customers go live with a manually verified runbook, so the platform's records are the only thing standing between a support ticket and a guess. It is P2 because Stories 1–3 define the refusals this story explains.

**Independent Test**: Trigger a refusal of each kind — wrong identity source, no identity source, domain out of scope, password still present, incomplete policy — and confirm each is attributable to an organization, a member, a resolved identity source, and a reason, with no secret or foreign-tenant data present.

**Acceptance Scenarios**:

1. **Given** an access evaluation that refuses a session, **When** an operator inspects the platform's records for that request, **Then** the organization, the member, the resolved identity source, and the refusal reason are all recoverable.
2. **Given** a refusal caused by an incomplete policy on an enabled organization, **When** an operator inspects the records, **Then** it is distinguishable from a refusal caused by a non-satisfying session.
3. **Given** any refusal record, **When** it is inspected, **Then** it contains no identity-provider secret and no other customer's configuration.
4. **Given** a refusal reason returned to a client, **When** it is read, **Then** it names no provider, no customer, and no other tenant's configuration.

---

### User Story 6 - Authenticating through a customer Okta never grants membership (Priority: P3)

Someone who authenticates successfully through a mapped domain but was never invited does not become a member of that customer's organization. Product access stays invite and authorization based.

**Why this priority**: This is existing platform behaviour that the new path must not erode. It is P3 as regression protection rather than new capability, but a regression here would hand a customer's organization to anyone on their email domain.

**Independent Test**: Establish a session for a user on a mapped domain who has no authorization record in the customer organization, and confirm the organization does not appear as a member workspace and deep access is refused.

**Acceptance Scenarios**:

1. **Given** a first-time authentication through a customer identity source, **When** the platform account is created, **Then** no organization authorization is created alongside it.
2. **Given** an authenticated user on a mapped domain with no authorization in the customer organization, **When** they list their organizations, **Then** that organization is absent.
3. **Given** the same user, **When** they attempt deep access to that organization by direct reference, **Then** access is refused.

---

### Edge Cases

- **Empty lists on an enabled organization** — deny, per Story 2. An empty list is never "allow all" once the organization is enabled for this delivery.
- **Empty lists on a legacy SSO organization** — admit, exactly as today. This delivery must not retroactively tighten organizations it did not enable.
- **Subdomain of a listed domain** — `mail.acme.com` is not covered by a listing of `acme.com`. Each domain must be listed to be in scope.
- **Domain letter case** — `Maria@ACME.com` and `maria@acme.com` resolve identically; stored domains are normalized.
- **Malformed domain entries** — a stored domain containing `@`, a wildcard, surrounding whitespace, or an empty value is rejected at write time rather than silently never matching.
- **Domain claimed twice** — the same domain on two enabled organizations bound to *different* identity sources is rejected. The same domain across organizations bound to the *same* customer source is allowed, since one customer may hold several organizations.
- **Identity-source value that is not a known shape** — a value that is not a slug-shaped identity-source identifier is rejected at write time, so the stored policy can never name an arbitrary string.
- **Two customer sources that share a vendor** — Acme's Okta and Beta's Okta are distinct values and must never be folded into a shared "okta" value that would let either satisfy the other.
- **Credential state cannot be determined** — when the platform cannot establish whether a member holds a platform password, evaluation continues to deny with the existing "credential unavailable" reason. Availability of that lookup must not become a way to bypass the rule.
- **Support-domain member with no password** — admitted; the exception grants access regardless of whether a password exists, it does not require one.
- **Member of two enabled organizations bound to different customers** — each organization is evaluated independently against the session; satisfying one never satisfies the other.
- **Repeat enablement with changed domains** — re-running enablement with a different domain list updates the list rather than appending to it, so a removed domain actually loses scope.
- **Organization suspended for billing while also Okta-enabled** — the two conditions are independent and both continue to apply.

## Requirements *(mandatory)*

### Functional Requirements

**Identity source identity and isolation**

- **FR-001**: The organization access policy MUST be able to name a **specific customer identity source** as its allowed source, alongside the public sources it already accepts. (`P:FR-006`, `P:BD-004`)
- **FR-002**: Distinct customer identity sources MUST remain distinct throughout evaluation. The system MUST NOT fold them into a shared vendor-family value, and a session from one customer's source MUST NOT satisfy a policy naming another customer's source. (`P:FR-006`, `P:BD-001`, `P:SC-004`)
- **FR-003**: A stored identity-source value MUST conform to a constrained identifier shape, and a value that does not conform MUST be rejected at write time. (`P:FR-013`)

**Scoped fail-closed evaluation**

- **FR-004**: An organization MUST be distinguishable as "enabled for customer-Okta login" separately from being an SSO-enforcing organization, so the rules below can apply to it alone. (`P:FR-017`)
- **FR-005**: On an organization enabled for customer-Okta login, an empty allowed-identity-source list MUST deny access, and an empty allowed-email-domain list MUST deny access. (`P:FR-015`)
- **FR-006**: On an organization **not** enabled for customer-Okta login, both the stored policy and the evaluation outcome MUST be identical to their pre-delivery behaviour, including empty lists continuing to admit. No migration or backfill may rewrite those organizations. (`P:FR-017`, `P:SC-011`)
- **FR-007**: Enabling customer-Okta login on an organization MUST be rejected while either list is empty, so the forbidden production state cannot be reached through the supported path. (`P:FR-015`)

**Domain semantics**

- **FR-008**: Email-domain matching MUST compare the full domain after `@`, exactly and case-insensitively, with no subdomain inheritance in either direction. (`P:FR-002`, product Key Entities)
- **FR-009**: Stored email domains MUST be normalized to lowercase and trimmed on write, and entries that are not bare domains MUST be rejected rather than stored. (`P:FR-002`, product edge cases)
- **FR-010**: A given email domain MUST NOT be claimable by two customer-Okta-enabled organizations bound to different identity sources; the enablement operation MUST reject the second claim. (product edge cases — "two customers MUST NOT own the same domain")

**Per-organization enforcement**

- **FR-011**: Access MUST continue to be evaluated per organization against the current session, so a member of an enforcing and a non-enforcing organization keeps the non-enforcing one when the session does not satisfy the enforcing one. (`P:FR-007`, `P:SC-003`)
- **FR-012**: A member of a customer-Okta-enabled organization who is not on a support domain MUST be denied while a platform password exists on their account. (`P:FR-010`)
- **FR-013**: Successful authentication through a customer identity source MUST NOT create or modify any organization authorization. Access stays invite and authorization based. (`P:FR-008`, `P:FR-009`, `P:BD-006`, `P:SC-005`)
- **FR-014**: When the platform cannot determine a member's platform-password state, evaluation MUST continue to deny with the existing reason rather than admit. (existing behaviour, preserved)

**Support-domain exception**

- **FR-015**: An invited member whose email domain is exactly `@weni.ai` or `@vtex.com` MUST be admitted to a customer-Okta-enabled organization on any session, including a platform-password session, and MUST NOT be required to hold that customer's identity source. (`P:FR-016`, `P:BD-009`)
- **FR-016**: The support exception MUST apply only to those exact domains. A domain that merely ends with one of them MUST NOT qualify. (`P:FR-016`)
- **FR-017**: A member on a support domain MUST be permitted to set and keep a platform password even while belonging to an SSO-enforcing organization. The platform MUST NOT report password management as unavailable to them. (`P:FR-016`, `P:BD-009`)

**Operational enablement**

- **FR-018**: Enablement, update, and disablement of a customer-Okta organization policy MUST be performable through an internal operational procedure that validates FR-003, FR-005, FR-007, FR-009, and FR-010 before persisting. (`P:FR-011`, `P:BD-005`)
- **FR-019**: The enablement operation MUST be idempotent: re-running it with the same inputs MUST leave the stored policy unchanged and MUST NOT create a second or interchangeable policy. (product edge cases — idempotent implantation)
- **FR-020**: Re-running enablement with a changed domain or identity-source list MUST replace the stored list rather than accumulate entries, so removals take effect. (product edge cases)
- **FR-021**: This delivery MUST NOT add any new merchant-facing or admin surface, and MUST NOT extend the existing admin path, to create a customer identity connection or bind an organization to one. Binding is operator-only; the admin write access retained by FR-022 covers the policy of an organization an operator has already bound. (`P:FR-011`, `P:SC-006`)
- **FR-022**: Organization admins MUST retain write access to their organization's access policy, and every write MUST be validated against the invariants in FR-003, FR-005, FR-009, and FR-010. A write whose resulting state would violate any of them MUST be rejected with nothing persisted. (Clarification Q1)
- **FR-023**: The "enabled for customer-Okta login" attribute MUST NOT be writable through the admin path. Only the internal operational procedure may set or clear it. (Clarification Q1 — an admin who could clear the attribute would bypass every validation in FR-022)
- **FR-024**: Turning enforcement off on an organization enabled for customer-Okta login MUST be rejected through the admin path, because it produces the mapping-on / policy-off state the product spec forbids in production. Disabling such an organization is an operator action. (Clarification Q1, `P:FR-015`)
- **FR-025**: Enabling a second customer MUST require only another run of the same operation, with no new product surface and no change to the model. (`P:NFR-004`, `P:SC-006`)

**Client contract and observability**

- **FR-026**: The existing organization access contract — access status, disabled reason, and exposed policy shape — MUST be preserved. Existing clients MUST NOT need a change to keep working. (`P:FR-017`, constitution III)
- **FR-027**: Disabled reasons returned to clients MUST remain provider-agnostic. This delivery MUST NOT introduce a reason that names a specific provider, names a customer, or reveals another tenant's configuration. (`P:FR-012`, `P:NFR-003`)
- **FR-028**: Every access refusal MUST be recoverable by support with the organization, the member, the resolved session identity source, and the refusal reason. A refusal caused by an incomplete policy MUST be distinguishable from one caused by a non-satisfying session. (`P:NFR-003`, product cross-cutting observability)
- **FR-029**: No record produced by this delivery may contain an identity-provider secret or another customer's configuration. (`P:NFR-003`)

### Out of Scope

Everything the product spec places outside Connect, restated so the boundary is unambiguous:

- The identity-first login step, the third-party actions on it, login copy, login locales, and login accessibility. Those live in the Keycloak login theme.
- The email-domain → identity-source **routing** table and the redirect it drives. Connect owns the *policy* domain list, not the routing table; the two are deliberately separate layers.
- Doors A, B, and C, direct-start identifiers, and the handling of invalid ones.
- Validating customer Okta tokens. Connect continues to trust exactly one issuer.
- Removing platform passwords from Keycloak, and **reporting on go-live readiness**. Ops performs the removal and verifies the result manually against the implantation runbook for the first customers (Clarification Q2). Connect neither automates the removal nor exposes a readiness view in this delivery.
- Blocked-organization copy strings in the web app.
- SCIM, group-to-role synchronization, automatic deprovisioning, and just-in-time membership.
- Merchant self-service for identity connections.
- Retroactively tightening organizations this delivery does not enable.

### Key Entities *(include if feature involves data)*

- **Customer identity source**: One customer's Okta as a distinct trust root, identified by a stable per-customer identifier that the session carries and the policy names. Never interchangeable with another customer's source or with a public third-party source.
- **Organization access policy**: Per organization — whether enforcement is on, which identity sources are allowed, which email domains are in scope, and whether the organization is enabled for customer-Okta login. The last attribute is what scopes the fail-closed rules to this delivery.
- **Session identity source**: The identity source that established the *current* session, read live per request. Historical records of which sources a member has ever used are not part of the decision.
- **Support domain**: An exact email domain (`weni.ai`, `vtex.com`) whose members bypass the policy for support purposes and may keep a platform password.
- **Platform password state**: Whether a member holds a password on the platform identity service. An indeterminate state denies rather than admits.
- **Organization authorization**: The existing invite-based membership record. It is the only thing that grants product access; authentication never creates it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sessions carrying a second customer's identity source are refused by the first customer's enabled organization, across an exhaustive matrix of two customer sources × three public sources × no source. (validates FR-001, FR-002; `P:SC-004`)
- **SC-002**: 100% of access evaluations against an enabled organization with either list empty are refusals, and 100% of evaluations against a non-enabled organization return the same outcome as the pre-delivery build for the same inputs. (validates FR-005, FR-006; `P:SC-011`)
- **SC-003**: A member of one enforcing and one non-enforcing organization retains the non-enforcing organization in 100% of non-satisfying-session cases, without re-authenticating. (validates FR-011; `P:SC-003`)
- **SC-004**: 100% of invited members on the two support domains are admitted to an enabled organization on a platform-password session, and 100% of members on look-alike domains are refused. (validates FR-015, FR-016; `P:SC-010`)
- **SC-005**: A support-domain member belonging to an SSO-enforcing organization can set and keep a platform password in 100% of attempts. (validates FR-017; `P:SC-010`)
- **SC-006**: Authenticating on a mapped domain without an invitation yields zero organization memberships in 100% of attempts. (validates FR-013; `P:SC-005`)
- **SC-007**: Enabling a customer twice produces a byte-identical stored policy and exactly one policy record, in 100% of repeat runs. (validates FR-019)
- **SC-008**: 100% of attempts — through either the admin path or the internal operation — to reach a state with an empty list, a malformed domain, a malformed identity-source value, or a domain already claimed by a different customer are rejected with nothing persisted. (validates FR-003, FR-007, FR-009, FR-010, FR-022)
- **SC-009**: 100% of admin attempts to clear the customer-Okta enablement attribute or to turn enforcement off on an enabled organization are rejected, while admin edits to the domain list that keep the policy valid succeed. (validates FR-022, FR-023, FR-024)
- **SC-010**: A second customer is brought live with zero new product surfaces and zero schema changes beyond configuration data. (validates FR-025; `P:SC-006`, `P:NFR-004`)
- **SC-011**: Every refusal is attributable to an organization, a member, a resolved identity source, and a reason, and incomplete-policy refusals are distinguishable from non-satisfying-session refusals; zero refusal records contain a provider secret or another customer's configuration. (validates FR-028, FR-029; `P:NFR-003`)
- **SC-012**: Existing clients of the organization access contract require no change: the set of exposed fields and the set of possible disabled reasons are unchanged or purely additive with provider-agnostic values. (validates FR-026, FR-027)

## Assumptions

**Inherited from the product spec, treated as given**

- The platform continues to trust exactly one identity issuer. Each customer Okta is a hidden identity source behind it, never a second issuer Connect validates (`P:BD-001`).
- The session carries a stable, per-customer identity-source identifier that Connect can read on every request. Producing that claim is the identity platform's responsibility; this spec only consumes it.
- Domain → identity-source routing is enforced upstream of Connect. Connect's domain list is a *policy* scope list, and the two lists are intentionally maintained as separate layers (`P:BD-004`).
- Support domains are exactly `weni.ai` and `vtex.com`. They remain configurable, but production runs with exactly those two values (`P:FR-016`).
- Protocol choice between OIDC and SAML is invisible to Connect (`P:BD-008`).

**Engineering assumptions made where the product spec was silent**

- The "enabled for customer-Okta login" attribute is an explicit, recorded property of the organization's policy rather than something inferred from the policy contents. Inference cannot work, because the case that must be distinguished — an enabled organization with empty lists versus a legacy organization with empty lists — is exactly the case where the contents are identical.
- The internal operational procedure is an auditable, repeatable operation invoked by an operator rather than free-form data editing, because FR-007, FR-010, and FR-019 all require validation at write time that free-form editing would bypass. Its exact form is a planning decision.
- The policy invariants are a property of the stored policy, not of whichever path wrote it. The operator path and the admin path (FR-022) must therefore share one validation point, so a rule cannot hold on one path and not the other.
- The support exception continues to apply platform-wide to all SSO-enforcing organizations, not only to Okta-enabled ones, because narrowing it would change the behaviour of organizations this delivery must leave untouched (`P:FR-017`).
- Denying on indeterminate password state is retained unchanged. The product spec does not revisit it, and relaxing it would create a bypass triggered by an outage.
- The existing per-organization evaluation, the existing disabled-reason vocabulary, and the existing organization access contract are reused rather than replaced. This delivery is a scoped extension of a policy layer that already exists in Connect, not a new one.

**Dependencies**

- The identity platform must expose the per-customer identity source on the session before Connect enforcement can be validated end to end. Connect-side work can be developed and tested against synthesized sessions in the meantime.
- Production go-live for a customer depends on the ops runbook removing platform passwords for non-support members **and** manually verifying the result, since Connect exposes no readiness view (Clarification Q2). The runbook must therefore cover both the removal and its verification.
- Provider-agnostic blocked-organization copy is a web-app change. Connect's contribution is limited to not introducing provider-named reasons.

## Clarifications

### Session 2026-09-01

- **Q1**: Once an organization is enabled for customer-Okta login, may its admins still change that policy through the existing admin path? → **A**: Admins keep write access, but every write is validated and rejected when the resulting state would violate the fail-closed invariants (FR-022). Two consequences follow necessarily and are specified rather than left open: the customer-Okta enablement attribute is not admin-writable (FR-023), since an admin who could clear it would bypass the validation entirely; and turning enforcement off on an enabled organization is rejected through the admin path (FR-024), since that produces exactly the mapping-on / policy-off state `P:FR-015` forbids in production. Day-to-day domain edits therefore stay self-service, while tenant binding and enforcement remain operator-owned.

- **Q2**: Does go-live readiness reporting ship in this delivery? → **B**: Out of scope. Implantation verifies readiness manually against the runbook for the first customers. Connect exposes no readiness view and performs no per-member password sweep. The accepted risk is that a leftover platform password is caught by a customer-reported lockout after go-live rather than by an automated pre-flight check; the per-member refusal reason already identifies the cause when that happens (FR-028). Revisit when the number of enabled organizations makes manual verification impractical.
