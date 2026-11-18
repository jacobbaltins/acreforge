# Proposal: AI layout architecture (TASK-087) — AWAITING USER APPROVAL

Status: proposed, not approved. No AI code is written until approved.

## Recommended: bring-your-own-key (BYOK), opt-in
- **Provider/model:** user-selected OpenAI-compatible HTTPS endpoint and model; no default provider.
- **Data leaving the browser:** only after an explicit consent dialog listing the payload: parcel outline (local feet, not lat/lon unless the user opts in), acreage, existing item types/sizes, and the user's prompt. No account data or saved projects.
- **Credentials:** user pastes their own API key; held in memory by default, optional sessionStorage. Never embedded in code, exported, or included in project files.
- **Cost:** paid by the user to their provider; AcreForge shows a rough token estimate before sending. No AcreForge operating cost.
- **Retention:** AcreForge stores nothing remotely; provider retention follows the user's provider terms, which are linked in the dialog.
- **Timeout/errors:** 30 s abort, visible failure message, retry/cancel; prior plan untouched.
- **Output handling:** untrusted JSON; validate schema, numeric bounds, supported item types, parcel containment, overlaps, estimates; preview and require user approval before applying.
- **Fallback:** existing `plParse()/plCompute()/plPlace()` rule-based planner, always labeled "rule-based", never "AI".

## Alternatives
- Backend proxy: hides key but needs hosting, abuse controls, billing, privacy policy.
- Local-only: no new capability.

## Decision needed
Approve BYOK (or choose another) to unlock TASK-088/089. Phases 4 and 5 remain gated on professional-review and billing decisions.
