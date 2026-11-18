# Proposal: Professional subscriptions architecture (TASK-094 draft)

Status: PROPOSAL ONLY. No billing, pricing, accounts, or payment URLs are implemented. TASK-093 evidence and legal review are still absent, so TASK-095 stays on hold.

## Principles
- Entitlement authority lives only on a server; `index.html` and localStorage never decide access.
- Free local-first planner stays fully functional without an account.

## Proposed design
- Identity: hosted auth provider (OIDC); no passwords stored by AcreForge.
- Payments: a merchant-of-record provider (handles tax/VAT and refunds); checkout is provider-hosted.
- Webhooks: verify signature, reject replays, idempotent by event id; update an entitlements table.
- Entitlement check: browser sends a short-lived token; server returns signed feature flags; only server-backed features (e.g. hosted sync) are gated.
- Lifecycle: trial, active, past_due, canceled, refunded; cancellation effective at period end.
- Data: export and deletion on request; retention policy published; abuse/rate limits on API.

## Required before building
Willingness-to-pay evidence, plan entitlements, refund/support terms, jurisdictions, and legal/privacy review (TASK-093). Cost to operate and a terms/privacy page are prerequisites.
