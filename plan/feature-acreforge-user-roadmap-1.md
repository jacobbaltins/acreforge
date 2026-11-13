---
goal: Deliver AcreForge's User-Prioritized Five-Phase Roadmap
version: 1.0
date_created: 2026-11-03
last_updated: 2026-11-03
owner: AcreForge
status: 'In progress'
tags: [feature, roadmap, product, gis]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan follows the user's five-phase product roadmap and prioritizes **real-world map synchronization as the next 100+ hour development focus**. Basic real maps, terrain, mapped roads/buildings, and parcel import already exist; the remaining Phase 1 gap is trustworthy end-to-end spatial alignment of those references and terrain with the selected property and proposed site plan. Phase 2 capabilities are also substantially implemented. Phase 3 is not complete: deterministic, rule-based layout generation is not AI. Phase 4 and Phase 5 require separate scope approval and user-demand evidence before implementation. No payment, account, contractor, or professional-service capability is authorized by this roadmap alone.

## 1. Requirements & Constraints

- **REQ-001**: Preserve the user's phase order and feature groupings: real maps/terrain/roads/buildings/parcels; utilities/costs/reports; AI layout/building placement; construction/professional handoff; professional subscriptions.
- **REQ-002**: Distinguish existing completed features from genuinely new AI, professional, and subscription capabilities; deterministic local rules must never be described as AI.
- **REQ-003**: Preserve existing saved projects, parcel selection, scenario selection, and browser-local behavior during implementation.
- **REQ-004**: Identify source, coverage, assumptions, and limitations; no planning output may claim to be survey-grade, engineered, permitted, or contractor-approved.
- **REQ-005**: Add deterministic browser tests for new behavior and use mocked network/service responses.
- **REQ-006**: Phase 1 must make imported parcel boundaries, chosen property location, mapped roads/buildings, elevation/terrain, and proposed site features use a common documented coordinate reference and transform, with measurable alignment checks and visible source/coverage limitations.
- **REQ-007**: A synchronization failure, stale response, unsupported projection, or missing reference layer must be reported as unavailable; it must never shift features silently or imply that absent map coverage means absence in the real world.
- **SEC-001**: Never place model-provider keys, payment credentials, or privileged tokens in browser code or exported project files.
- **SEC-002**: Do not add authentication, billing, subscriptions, or persistent access before the user approves an architecture with server-side authorization and entitlement enforcement.
- **CON-001**: Keep the current static/browser-local application for existing Phases 1 and 2; no framework rewrite or new runtime dependency without a separately approved architecture decision.
- **CON-002**: Phase 3's real AI behavior requires an explicitly approved inference architecture, data-sharing boundary, and failure/fallback policy; do not silently substitute deterministic logic for AI.
- **CON-003**: Keep Phase 4 and Phase 5 on hold until active-user evidence, validated demand, target buyer, and distinct implementation scopes are documented and approved.
- **CON-004**: Do not alter or restore the pre-existing deleted `CALCULATIONS.md` or `Oregon-Estate-Planner-Print-and-Follow-Guide.pdf`.
- **GUD-001**: Reuse the current functions and tested mechanisms in `index.html` and `tests/smoke.py` before introducing new abstractions.
- **GUD-002**: Complete and verify one phase at a time; update docs, `sw.js`, and `acreforge.zip` only when shipped browser behavior changes.
- **PAT-001**: Follow current `normalizeState()`, `save()`, accessible DOM, and mocked Playwright patterns.

## 2. Implementation Steps

### Implementation Phase 1 — Real-World Map Synchronization (100+ Hour Priority)

- **GOAL-042**: Turn the existing real-map, terrain, mapped-road/building, parcel-boundary, and proposed-plan overlays into a coherent, testable spatial workflow. The user identified this as the next 100+ development-hour priority. The estimate is a prioritization signal, not a promise of duration or a reason to batch implementation without validation.

**Initial coordinate audit (pre-refactor):** Imported GeoJSON/KML parcel coordinates are WGS84 longitude/latitude. Parcel normalization computed a mean-vertex origin, converted coordinates to approximate local feet, and then a north-up migration flipped plan Y. Selected-location plans were centered on the selected WGS84 point. Terrain map vectors and the property map had separate anchor implementations; OSM road/building rendering and the older OSM import path repeated direct longitude-difference arithmetic. This meant antimeridian wrapping and alignment depended on which layer performed the transform. OSM features are optional, user-requested OpenStreetMap references with variable coverage; terrain relief uses available elevation tiles and does not imply complete or survey-grade coverage.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-083 | In `index.html`, audit `normalizeParcelBoundary()`, `propertyDims()`, `snAnchor()`, `drawMap()`, `terrainPlanAnchor()`, `terrainPlanCollection()`, and the terrain map source/update path. Document the WGS84 source coordinates, local-feet approximation, north-up migration, selected-location origin, data provenance, coverage limits, and duplicated-transform alignment gap in the audit above. Define the canonical reference as WGS84 longitude/latitude for source geometry and local feet relative to one property origin for the flat site plan. | ✅ | 2026-11-03 |
| TASK-084 | In `tests/smoke.py`, add deterministic projection fixtures for an imported parcel and a selected-location-only project, including a non-square/offset parcel and antimeridian-adjacent coordinates. Assert forward/inverse round trips within 1 ft, shared parcel-corner alignment, invalid coordinate rejection, and one-time legacy north-up migration. Depends on TASK-083. | ✅ | 2026-11-03 |
| TASK-096 | In `index.html`, consolidate WGS84-to-local-feet and inverse transforms used by parcel normalization, `snAnchor()`, and the terrain map anchor into one shared local equirectangular projection contract. Use one explicit origin (parcel reference center when available, otherwise selected coordinate), preserve raw WGS84 source geometry, wrap longitude at the antimeridian, and reject invalid transforms rather than falling back to an arbitrary map center. Preserve the existing saved-project schema and north-up migration. Depends on TASK-083 and TASK-084. | ✅ | 2026-11-03 |
| TASK-097 | In `tests/smoke.py`, verify forward/inverse projection round trips, parcel-origin and selected-location-origin consistency, antimeridian wrapping, invalid coordinate rejection, and legacy parcel-plan migration of items, fields, roads, paint, and terrain. Depends on TASK-096. | ✅ | 2026-11-03 |
| TASK-098 | In `index.html`, align the imported parcel outline and all rendered mapped-road, mapped-building, and proposed-feature geometries through the shared projection before display. Keep references visually distinct from proposals, retain OSM attribution and user-triggered lookup behavior, and ensure the same source point resolves to the same plan/map location at multiple zoom levels. Depends on TASK-096. | ✅ | 2026-11-03 |
| TASK-099 | In `tests/smoke.py`, use mocked roads/building polygons crossing known parcel vertices and interior test points; assert overlay-to-parcel alignment within 1 ft in plan coordinates, stable location under map zoom/pan, no mutation of proposed objects, and graceful handling of incomplete geometry. Depends on TASK-098. | ✅ | 2026-11-03 |
| TASK-100 | In `index.html`, synchronize terrain elevations/relief and slope/contour/hillshade overlays with the shared map position and property extent. Preserve elevation units and vertical-exaggeration disclosure; mask no-data, expose actual sampled extent/resolution/coverage, and never stretch unsupported terrain across the parcel as if it were measured. Depends on TASK-096. | ✅ | 2026-11-03 |
| TASK-101 | In `tests/smoke.py`, mock elevation samples with known coordinates/elevations and verify terrain-to-parcel/feature alignment, vertical unit conversion, sampled extent and coverage, no-data gaps, tile failure, and consistent placement in flat and 3D views. Depends on TASK-100. | ✅ | 2026-11-03 |
| TASK-102 | In `index.html`, add a small, accessible map-alignment/source status that reports selected spatial origin, active parcel/location reference, available map layers, last successful retrieval time, and failed/stale layer state. Status display must not initiate network requests or describe incomplete OSM/elevation data as a complete inventory. Depends on TASK-096. | ✅ | 2026-11-03 |
| TASK-103 | In `tests/smoke.py`, test source status with mocked success, empty, stale, offline, and failed responses; assert no fetch occurs just by rendering the status and that existing local editing remains available. Depends on TASK-102. | ✅ | 2026-11-03 |
| TASK-104 | In `index.html`, bound real-world geometry processing/rendering for large mapped road/building results by simplifying only display copies with a documented tolerance, retaining source geometry for measurements, and exposing a clear loading/failure state. Do not silently drop entire returned layers or exceed the current user-triggered request bounds. Depends on TASK-098. | ✅ | 2026-11-03 |
| TASK-105 | In `tests/smoke.py`, seed dense line/polygon fixtures and assert bounded render complexity, no change to measured source geometry, correct source attribution, and no loss of parcel or proposed overlays. Depends on TASK-104. | ✅ | 2026-11-03 |
| TASK-106 | Update `README.md`, `CHANGELOG.md`, `sw.js`, and `acreforge.zip` only after Phase 1 behavior is implemented and its smoke tests pass. Document synchronization reference, supported layers, alignment verification, source dates/coverage, and limitations; preserve the ZIP member list and unrelated dirty files. Depends on TASK-097, TASK-099, TASK-101, TASK-103, and TASK-105. | ✅ | 2026-11-03 |

### Implementation Phase 2 — Utility Planning, Costs, and Reports (Existing Baseline)

- **GOAL-043**: Preserve and verify the already delivered utility-route planning, estimate ranges, and report/export experience.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-085 | In `index.html`, retain utility distance/rate assumptions, low/medium/high estimates, route provenance, report rendering, and project/CSV exports. Do not recast allowances as bids or provider quotes. | ✅ | 2026-11-03 |
| TASK-086 | In `tests/smoke.py`, retain and run existing arithmetic, route-source, cost-reconciliation, report, and export regressions; verify unavailable route inputs are not fabricated. | ✅ | 2026-11-03 |

### Implementation Phase 3 — AI Property Layout and Building Placement

- **GOAL-044**: Add genuine AI-assisted concept layout and building-placement recommendations while accurately distinguishing AI output from existing deterministic rules.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-087 | Before coding, document and obtain user approval for the inference architecture: model/provider, whether property geometry or project details leave the browser, credential boundary, operating cost, retention policy, user consent, timeout/error handling, and deterministic fallback. `index.html` currently implements `plParse()`, `plCompute()`, `plPlace()`, and a local rule-based command bar; explicitly preserve that baseline and never label it AI. Do not embed provider secrets in browser code. | ✅ | 2026-11-03 |
| TASK-088 | After TASK-087 is approved, implement an opt-in AI layout recommendation path in `index.html` and only the explicitly approved supporting files. Treat model output as untrusted proposed data: validate schema, numeric bounds, supported item types, parcel containment, overlaps, and estimates before preview or application; require user review, provide clear AI provenance/limitations, and leave the prior plan unchanged on errors or cancellation. | ✅ | 2026-11-03 |
| TASK-089 | In `tests/smoke.py`, mock the approved inference interface and test valid, malformed, unsafe/out-of-bounds, timeout, provider-failure, cancel, and fallback cases; verify deterministic baseline behavior and that AI output never mutates the plan before user approval. Depends on TASK-088. | ✅ | 2026-11-03 |

### Implementation Phase 4 — Construction Workflow and Professional Handoff (Gated)

- **GOAL-045**: Define a safely bounded handoff workflow for planning concepts; implementation remains blocked by the user-evidence gate.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-090 | Before implementation, add substantiated active-user evidence, validated demand, target-buyer definition, and the selected construction/handoff workflow to `plan/`; obtain separate user approval for deliverables, recipients, and liability boundaries. Keep this task on hold while any evidence or approval is absent. | | |
| TASK-091 | Only after TASK-090 approval, extend `reportsPage()`, `exportProject()`, and relevant existing CSV/DXF/PDF exporters to create a clearly labeled conceptual handoff package with source files, units, coordinate assumptions, exclusions, and professional-review checklist. Do not create construction-ready documents, claim code compliance, upload/send files, or represent a surveyor/engineer as having reviewed them. | | |
| TASK-092 | In `tests/smoke.py`, after TASK-091, verify package contents, units/provenance/disclaimers, unsupported-data handling, local-only export, and that no handoff is transmitted without an explicit user action. Depends on TASK-091. | | |

### Implementation Phase 5 — Professional Subscriptions (Gated)

- **GOAL-046**: Assess a secure, truthful subscription model only after demand validation; no billing implementation is authorized yet.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-093 | Before implementation, document active-user and willingness-to-pay evidence, target segments, proposed plan entitlements, cancellation/refund/support expectations, jurisdictions, and separate user approval. Keep this task on hold while those inputs are absent; do not add pricing, checkout, accounts, or payment URLs by assumption. | | |
| TASK-094 | Only after TASK-093 approval, produce a separate security/privacy/legal architecture for server-side identity, verified payment events, entitlement checks, account lifecycle, data retention/export/deletion, and abuse handling. Do not put credentials or entitlement authority in `index.html` or local storage. | | |
| TASK-095 | Implement and test subscriptions only after the separate architecture and jurisdiction-specific legal review are approved. Test server-side authorization, webhook authenticity/idempotency, subscription lifecycle, cancellation/refund behavior, failed payment, account deletion, and feature access; never claim completion from a browser-side flag. Depends on TASK-094. | | |

## 3. Alternatives

- **ALT-001**: Call the existing deterministic planner “AI.” Rejected because `plParse()`, `plCompute()`, and `plPlace()` are local rule-based logic and the UI discloses that distinction.
- **ALT-002**: Put a model or payment-provider secret directly in browser code. Rejected because static client code and exported files are inspectable and cannot enforce privileged access securely.
- **ALT-003**: Start contractor workflows and subscriptions without demand evidence or a defined buyer. Rejected because the existing roadmap explicitly gates professional work on validated users and separate approval.

## 4. Dependencies

- **DEP-001**: Existing property, parcel, terrain, roads, and building feature paths and tests in `index.html` and `tests/smoke.py`.
- **DEP-002**: Existing local layout/cost logic: `plParse()`, `plCompute()`, `plPlace()`, `compute()`, and `reportsPage()` in `index.html`.
- **DEP-003**: Shared geographic projection contract and deterministic reference fixtures before the Phase 1 layer-synchronization tasks.
- **DEP-004**: User decision on AI inference architecture and data-sharing boundaries before TASK-088.
- **DEP-005**: Substantiated user-demand evidence and separate approval before Phase 4 or Phase 5 implementation.
- **DEP-006**: Independent security/privacy/legal review before any account, payment, or subscription implementation.

## 5. Files

- **FILE-001**: `index.html` — existing local application and future approved UI/inference integration.
- **FILE-002**: `tests/smoke.py` — existing and future mocked browser regression coverage.
- **FILE-003**: `README.md` — shipped functionality, data-source details, and limitations.
- **FILE-004**: `CHANGELOG.md` — release notes for approved shipped changes.
- **FILE-005**: `sw.js` — static-shell cache marker for approved browser changes.
- **FILE-006**: `acreforge.zip` — release archive refreshed with the unchanged existing member list when applicable.
- **FILE-007**: `plan/feature-acreforge-user-roadmap-1.md` — this user-prioritized roadmap.

## 6. Testing

- **TEST-001**: Run `python tests/smoke.py` from the repository root for each phase that changes browser behavior.
- **TEST-002**: Validate inline JavaScript syntax with the available Node.js syntax-check procedure after editing `index.html`.
- **TEST-003**: Run `git diff --check` and verify no unrelated dirty files or pre-existing deletions were changed.
- **TEST-004**: For AI functionality, verify mocked valid/invalid/failure responses, approval gating, provenance, and safe fallback without live model access.
- **TEST-005**: For professional exports, verify exact package contents, labels, units, no unintended transmission, and visible limitations.
- **TEST-006**: For subscriptions, test server-side authorization and payment event lifecycle only in an explicitly approved non-production test environment; never use live payment data for tests.

## 7. Risks & Assumptions

- **RISK-001**: Projection errors can make plausible-looking reference layers spatially wrong; source geometry, transform origin, units, and alignment tolerance must be tested together.
- **RISK-002**: Real-world map and elevation sources vary in positional accuracy, update time, license, and coverage; visible provenance and uncertainty are mandatory.
- **RISK-003**: AI-generated placements can violate parcel, geometry, or object constraints; all output must be validated and previewed before mutation.
- **RISK-004**: Sending property details to a model provider may expose sensitive location information; data minimization and informed consent are prerequisites.
- **RISK-005**: Contractor or professional handoff files may be mistaken for approved construction documents; explicit scope, source, coordinate, and limitation labels are mandatory.
- **RISK-006**: Client-side subscriptions can be bypassed; identity, payment verification, and entitlements require a trusted server.
- **RISK-007**: Subscription and professional-services obligations vary by jurisdiction; legal and operational review must precede launch.
- **ASSUMPTION-001**: Phases 1 and 2 are feature-complete based on the existing roadmap and regression suite; this plan preserves rather than rebuilds them.
- **ASSUMPTION-002**: Phase 3 is not implemented as AI until the user selects and approves an inference architecture.
- **ASSUMPTION-003**: Phase 4 and 5 remain gated even though they are now listed in the product roadmap; listing them does not itself satisfy the evidence, legal, or approval requirements.

## 8. Related Specifications / Further Reading

- `plan/feature-acreforge-mvp-decision-flow-1.md` — original roadmap and Phase 20 post-user gate.
- `plan/phase-20-user-evidence.md` — current evidence review and hold decision.
- `README.md` — existing local-first behavior and disclosures, including current limitations for AI, accounts, and payments.
- `tests/smoke.py` — deterministic mocked Playwright regression suite.
