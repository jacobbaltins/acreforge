---
goal: Deliver AcreForge's sequenced property-planning roadmap
version: 1.1
date_created: 2026-11-01
last_updated: 2026-11-01
owner: AcreForge
status: 'In progress'
tags: [feature, product, roadmap, gis]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

Deliver AcreForge as a focused land-planning product through 21 sequenced chunks. Chunks 0-13 establish the core property decision workflow; chunks 14-16 extend it to homesteads and compounds; chunks 17-19 are later expansion; chunk 20 is gated until users validate professional demand. First make the current application easier to navigate, then close property context and decision-support gaps. Existing features are a baseline to audit and improve, not a reason to duplicate them. The original implementation stack remains out of scope for replacement.

## 1. Requirements & Constraints

- **REQ-001**: A new user must be able to select a property, inspect real map context, understand recommended build areas, generate a concept plan, and review a low/medium/high cost range in one guided flow.
- **REQ-002**: Roads and existing building footprints must be clearly distinguished from proposed AcreForge objects and must be identified as mapped references, not verified inventories.
- **REQ-003**: Buildability and recommendations must show their evidence and limitations. Missing, stale, sampled, or unmapped data must never be presented as confirmed clear land.
- **REQ-004**: A recommendation must explain its principal factors, including slope, solar exposure, access, privacy, and any available flood/soil evidence.
- **REQ-005**: Cost output must identify included categories and preserve the existing low, medium, and high estimate distinction.
- **REQ-006**: Primary navigation must contain exactly Projects, Property, Design, Reports, and Settings; existing screens must be regrouped rather than silently discarded.
- **REQ-007**: Chunks are delivered in numeric order, one independently verified increment at a time; each has a measurable acceptance criterion.
- **REQ-008**: Chunks 17-19 are post-core expansion; Chunk 20 must remain gated until there is evidence of active users and validated demand.
- **CON-001**: Preserve the current static, browser-local application architecture and existing project data unless a tested MVP requirement demonstrates that a migration is necessary.
- **CON-002**: Keep the two pre-existing deletions of `CALCULATIONS.md` and `Oregon-Estate-Planner-Print-and-Follow-Guide.pdf` out of MVP work and releases unless explicitly requested.
- **CON-003**: Do not add BIM, plumbing, electrical, HVAC, contractor management, permit automation, collaboration, digital twins, or advanced environmental simulation in this MVP sequence.
- **CON-004**: Keep external map and public-data requests explicit, bounded, attributed, and consistent with the existing privacy notice.
- **CON-005**: Do not assume third-party map coverage is complete; absent mapped features are unknown, not proof of absence.
- **CON-006**: Keep the current static/browser-local application and tested project data format. Do not start a React/FastAPI/PostGIS rewrite as a prerequisite to product validation.
- **GUD-001**: Implement and validate one independently usable chunk at a time; each chunk must improve an identifiable property decision.
- **GUD-002**: Reuse existing map, terrain, parcel, scoring, planner, and test mechanisms before adding new abstractions.
- **PAT-001**: Follow the single-page application patterns in `index.html` and the mocked Playwright browser checks in `tests/smoke.py`.

## 2. Implementation Steps

### Implementation Phase 0 — Foundation Cleanup

- **GOAL-001**: Simplify navigation and establish a map-first visual system. Acceptance: the only primary navigation labels are Projects, Property, Design, Reports, and Settings; existing supported screens remain reachable through those destinations; the property map is the dominant workspace on desktop and mobile.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | In `index.html`, consolidate the navigation entries currently created by `nav` (including dashboard, planner, designer, buildings, homes, infrastructure, financials, operations, compliance, scenarios, manual, and about) into the five required destinations without deleting their working capabilities. Define shared design tokens for spacing, type, color, cards, buttons, and focus states; move secondary controls into contextual panels; remove only controls proven to duplicate the same action. | ✅ | |
| TASK-002 | In `tests/smoke.py`, assert exactly five primary navigation labels, verify each destination loads, confirm existing project/design/report/settings flows remain reachable, and check responsive map-first layout at desktop and mobile viewport sizes. | ✅ | |

### Implementation Phase 1 — Property Search

- **GOAL-002**: Let a user select a property quickly. Acceptance: in a mocked test with address, coordinates, parcel match, and recent-search fixtures, a valid selection is confirmed in under 10 seconds; failures preserve the previous selection.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-003 | In `index.html`, consolidate existing coordinate/address search (`snParseSpot`, `snPickSet`, and the `nominatim` lookup near `snPickUse`) into Property search. Add parcel lookup only where a public endpoint/provider already exists or can be explicitly selected; do not imply nationwide parcel coverage. Persist a bounded recent-search list in the existing project/browser storage and keep pin drop available on the map. | ✅ | |
| TASK-004 | In `tests/smoke.py`, mock geocoding and parcel-search responses; verify address and coordinate selection, pin drop, recent-search restore, no-result/network-failure handling, and the under-10-second success criterion without changing the property on failure. | ✅ | |

### Implementation Phase 2 — Property Boundaries

- **GOAL-003**: Make imported property geometry legible and measurable. Acceptance: supported imported boundaries remain visible at all tested zoom levels and display acreage and perimeter; frontage and adjacent parcels are reported only when geometry/data supports them.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | In `index.html`, extend existing `state.project.parcelBoundary` rendering, normalization, and measurement logic. Show boundary outline, acreage, perimeter, and source. Derive road frontage only from intersecting mapped road geometry; show unavailable where road data is absent. Do not infer ownership or adjacent parcel lines from imagery. | ✅ | 2026-11-01 |
| TASK-006 | In `tests/smoke.py`, cover single and multipart boundaries, zoomed rendering, area/perimeter values, missing road geometry, and computed frontage. Assert unsupported adjacent-parcel or ownership data is labeled unavailable rather than fabricated. | ✅ | 2026-11-01 |

### Implementation Phase 3 — Real Roads

- **GOAL-004**: Show road access before design starts. Acceptance: users can see mapped road context and distinguish road hierarchy before creating proposed roads; unavailable data is explicit.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | In `index.html`, reuse the OpenStreetMap query/mapping path (`snMatch`, `rnRoads`, `snAnchor`, `drawMap`, and terrain OSM layer controls) to surface real road references in Property. Add roads/driveways visibility and label/hierarchy styling where returned tags support classification. Keep mapped road references distinct from user-drawn roads and preserve user-triggered requests and attribution. | ✅ | 2026-11-01 |
| TASK-008 | In `tests/smoke.py`, mock road geometries with hierarchy tags, missing tags, empty results, and service failure. Verify toggles, labels, selection persistence, and visual distinction from proposed driveway/road objects. | ✅ | 2026-11-01 |

### Implementation Phase 4 — Existing Buildings

- **GOAL-005**: Give users reliable visual context for mapped buildings. Acceptance: existing mapped footprints are visually distinct from proposed structures and can be inspected with dimensions only when those dimensions are known or explicitly estimated.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | In `index.html`, reuse the terrain OSM building feature parsing/rendering and `wireTerrainOsmMap` interaction. Add building hover/select information with source and footprint area derived from mapped polygon geometry. Separate reported height from estimated height; style existing and proposed structures differently in 2D and 3D. | ✅ | 2026-11-01 |
| TASK-010 | In `tests/smoke.py`, exercise mapped building selection, hover details, polygon area, missing geometry/height, and proposed-vs-existing styles. Assert the UI does not claim mapped footprints are a complete inventory. | ✅ | 2026-11-01 |

### Implementation Phase 5 — Terrain Engine

- **GOAL-006**: Make elevation and landform immediately understandable. Acceptance: a selected location can display elevation, 3D relief, contours, slope, and hillshade when source data is available; failures are visible and do not masquerade as flat land.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | In `index.html`, build on `terrainMapInstance`, `terrain-3d`, AWS Terrain Tiles, terrain analysis overlays, and `landLookup`. Open at a selected property's coordinates when it belongs to the chosen state; provide slope, contours, and hillshade with visibility/opacity controls; report tile zoom, sample-grid size, coverage, elevation range, contour interval, and slope legend. Convert elevation and horizontal distance to consistent feet-based units. Mask no-data and hide analyses and 3D relief when mapped coverage is below 70% or a tile request fails. | ✅ | 2026-11-01 |
| TASK-012 | In `tests/smoke.py`, verify mapped elevation, transparent no-data, tile failure, the 3D terrain toggle, contour/slope/hillshade controls and opacity persistence, and selected-property center/zoom. Assert that missing data is not rendered as a confirmed level surface and that failures are visible. | ✅ | 2026-11-01 |

### Implementation Phase 6 — Property Health Dashboard

- **GOAL-007**: Summarize evidence about land quality. Acceptance: every selected property shows an overall score and explicit values or unavailable states for buildability, solar, privacy, utilities, drainage, and access.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | In `index.html`, consolidate `pzScore`, `pzTerrain`, `pzCard`, and `landLookup` output into one Property health summary. Preserve existing score formulas where defensible; annotate evidence coverage and source for each dimension and mark missing inputs unavailable rather than assigning optimistic defaults. | ✅ | 2026-10-21 |
| TASK-014 | In `tests/smoke.py`, seed complete, partial, and missing analysis inputs. Assert each score/value matches stored analysis and unavailable dimensions remain explicitly unknown. | ✅ | 2026-10-21 |

### Implementation Phase 7 — Buildability Analysis

- **GOAL-008**: Visually identify candidate, caution, constrained, and unknown areas. Acceptance: the parcel-aware overlay classifies terrain using disclosed concept slope thresholds, keeps incomplete elevation unknown, shows sparse flood observations as point markers only, excludes parcel holes/outside geometry, and never implies legal approval.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | In `index.html`, extend `pzTerrain`, `pzScore`, and `pzCard` with parcel-aware candidate/caution/constrained/unknown terrain classes, a legend and concise click reasons. Use disclosed concept slope thresholds only; show FEMA samples as point observations, not flood boundaries. Do not invent setbacks, easements, wetlands, zoning, or legal access. | ✅ | 2026-11-02 |
| TASK-016 | In `tests/smoke.py`, test mixed-slope terrain, mapped high-flood sample markers, unmapped/partial/no-data elevation, parcel holes, outside-parcel cells, and placement restrictions; verify classes and explanations remain consistent and unknown does not become green. | ✅ | 2026-11-02 |

### Implementation Phase 8 — Opportunity Detection

- **GOAL-009**: Proactively surface plausible property opportunities. Acceptance: candidate house, shop, pond, solar, orchard, and event sites include a reason and evidence status; no unsupported site is presented as confirmed.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | In `index.html`, add an opportunity-ranking layer over existing `pzTerrain` cells, `pzScore`, and parcel geometry. Generate candidate types for house, shop, pond, solar, orchard, and event use from currently available slope, exposure, access, and mapped context; report why each candidate ranks and what evidence is missing. Keep suggestions reviewable, not automatically placed. | ✅ | 2026-11-02 |
| TASK-018 | In `tests/smoke.py`, seed known terrain patterns and assert deterministic opportunity ordering, rationale, parcel containment, and suppression/uncertainty when required evidence is absent. | ✅ | 2026-11-02 |

### Implementation Phase 9 — AI Build Zones

- **GOAL-010**: Recommend a small set of understandable candidate areas. Acceptance: Zone A/B/C are ranked and each has a concise explanation based on slope, solar, privacy, access, and available constraints.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | In `index.html`, extend `pzScore` and the existing `A.zones` generation to produce up to three named candidate zones. Reuse buildability classes and opportunity evidence; show factors, tradeoffs, and unknown constraints per zone. Use deterministic ranking unless a real AI provider is configured and clearly disclosed. | ✅ | 2026-11-02 |
| TASK-020 | In `tests/smoke.py`, verify ranking stability, explanation-to-score consistency, fewer-than-three-zone cases, and no recommendation inside excluded or unknown geometry. | ✅ | 2026-11-02 |

### Implementation Phase 10 — AI Property Copilot

- **GOAL-011**: Enable natural-language property planning commands. Acceptance: the command bar answers property questions and performs supported plan edits with visible confirmation and undo.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | In `index.html`, consolidate existing planner command handling (`asRun`, `plRun`/`plCompute`, and the `plAsk` control) into one property command bar. Support "What can I build here?", "Build a homestead", "Create a compound", and "Create a venue" using existing local rules; explicitly label rule-based behavior and report unsupported commands without silently claiming AI generation. | ✅ | 2026-11-02 |
| TASK-022 | In `tests/smoke.py`, test each supported prompt, unsupported input, command confirmation, undo behavior, and preservation of the active property. | ✅ | 2026-11-02 |

### Implementation Phase 11 — Layout Generator

- **GOAL-012**: Produce an editable concept plan rapidly. Acceptance: a valid request for a home, shop, and orchard generates a usable plan with buildings, roads, utilities assumptions, and placements in under 30 seconds in the deterministic smoke environment.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | In `index.html`, extend existing planner parsing/computation (`plParse`, `plCompute`, `plPhases`), placement (`plPlace`), and analyzer-aware zone placement. Handle requested dimensions such as 2500-square-foot home and 40-by-60-foot shop, include driveway and utility assumptions, and explain placement rationale; preserve editing and undo. | ✅ | 2026-11-02 |
| TASK-024 | In `tests/smoke.py`, measure request-to-editable-layout time and assert requested dimensions, object types, parcel fit, road/utility assumptions, rationale, and recovery from invalid or oversized requests. | ✅ | 2026-11-02 |

### Implementation Phase 12 — Scenario Comparison

- **GOAL-013**: Let users compare multiple possible futures. Acceptance: at least three saved concepts can be compared on cost and available decision metrics without overwriting one another.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-025 | In `index.html`, reuse current scenario state and navigation. Add named scenario snapshots and a comparison view for estimated cost, privacy, buildability, utilities, and self-sufficiency only where values exist; preserve the active scenario and provide restore/delete safeguards. | ✅ | 2026-11-02 |
| TASK-026 | In `tests/smoke.py`, compare three seeded scenarios, verify metric-to-scenario mapping, missing values, reload persistence, active-scenario preservation, and safe restore behavior. | ✅ | 2026-11-02 |

### Implementation Phase 13 — Cost Estimator

- **GOAL-014**: Make concept budgets useful and transparent. Acceptance: each layout provides low/medium/high costs for roads, utilities, buildings, site preparation, and septic assumptions.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-027 | In `index.html`, extend the existing planning cost functions (`plCompute`, `plRoi`, and object/route cost data) to show low/medium/high totals and line items for roads, utilities, buildings, site preparation, and septic. Identify placeholder unit rates and user-editable assumptions; do not imply bids or verified costs. | ✅ | 2026-11-02 |
| TASK-028 | In `tests/smoke.py`, assert line items sum to each total, low ≤ medium ≤ high, geometry/distance changes update relevant costs, and unspecified septic assumptions remain labeled estimates. | ✅ | 2026-11-02 |

### Implementation Phase 14 — Utility Planner

- **GOAL-015**: Explain infrastructure distance, cost, and planning difficulty. Acceptance: water, power, fiber, and septic routes show measured distance where geometry exists and clearly marked assumptions otherwise.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-029 | In `index.html`, reuse utility object definitions and existing route/cost editing in the Site Designer. Add route distance, estimated cost, and relative difficulty for water, power, fiber, and septic; distinguish drawn routes from inferred assumptions and feed estimates into TASK-027 totals. | ✅ | 2026-11-02 |
| TASK-030 | In `tests/smoke.py`, verify route-length arithmetic, cost propagation, missing endpoint behavior, and clear separation between measured and assumed routes. | ✅ | 2026-11-02 |

### Implementation Phase 15 — Homestead Mode

- **GOAL-016**: Create a complete editable homestead concept. Acceptance: one command generates a house, garden, orchard, coop, barn, greenhouse, and pond where the selected parcel and evidence allow.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-031 | In `index.html`, add a homestead preset through the command bar and layout-generation code (`plParse`, `plCompute`, `plPlace`). Reuse existing object types, build zones, cost estimates, and utilities; place only parcel-contained objects and explain omitted components. | ✅ | 2026-10-21 |
| TASK-032 | In `tests/smoke.py`, verify generated homestead objects, dimensions, parcel containment, zone rationale, cost output, and omission behavior for a constrained/small parcel. | ✅ | 2026-10-21 |

### Implementation Phase 16 — Compound Mode

- **GOAL-017**: Generate a multi-household concept with explicit privacy and circulation tradeoffs. Acceptance: one command proposes main, parent, and guest homes plus a shop and reports privacy, utility, and travel-distance tradeoffs.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-033 | In `index.html`, add a compound preset to the layout generator. Use existing build zones, object placement, utility routes, and scenario metrics to place a main house, parent house, guest house, and shop; rank alternatives by privacy, utility sharing, and travel distance without claiming an optimized engineering plan. | ✅ | 2026-11-03 |
| TASK-034 | In `tests/smoke.py`, verify all requested compound buildings fit the parcel, route/distance metrics are consistent, privacy tradeoffs are explained, and insufficient parcels produce a useful limitation instead of overlapping placements. | ✅ | 2026-11-03 |

### Implementation Phase 17 — 3D World

- **GOAL-018**: Present a coherent explorable 3D property. Acceptance: the selected property can be explored with terrain, existing mapped roads/buildings, proposed buildings, trees, and water, with orbit, walkthrough, and fly controls.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | In `index.html`, extend the existing terrain MapLibre 3D and isometric scene renderer to align property terrain, reference roads/buildings, and proposed plan features. Add accessible orbit, walkthrough, and fly interaction modes; keep existing/proposed styling distinct and do not add unsupported Three.js/React Three Fiber dependencies. | ✅ | 2026-11-03 |
| TASK-036 | In `tests/smoke.py`, verify each camera mode is selectable, terrain and supported features render in the selected-property extent, unavailable references are disclosed, and keyboard/pointer interactions do not block navigation. | ✅ | 2026-11-03 |

### Implementation Phase 18 — Event Venue Planner

- **GOAL-019**: Support venue concept planning as a validated second market. Acceptance: a venue concept includes ceremony, reception, parking, guest-flow paths, rough costs, and explicit review caveats.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-037 | In `index.html`, add a venue preset to the planner using existing event, parking, road, and building object types. Generate ceremony/reception areas and guest circulation, and present parking and cost assumptions; do not claim fire, accessibility, occupancy, or permit compliance. | ✅ | 2026-11-03 |
| TASK-038 | In `tests/smoke.py`, test venue layout generation, parking counts/assumptions, route connections, costs, and visible county/professional verification caveats. | ✅ | 2026-11-03 |

### Implementation Phase 19 — Traffic Simulation

- **GOAL-020**: Identify movement bottlenecks for validated planning scenarios. Acceptance: simulated cars, guests, deliveries, and emergency access produce a reproducible bottleneck summary without being represented as a real traffic study.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-039 | Only after core property-selection, context, analysis, layout, and cost chunks pass acceptance, extend existing road-network and traffic simulation code in `index.html` to model cars, guests, deliveries, and emergency-access paths. Report scenario assumptions and bottleneck locations; keep simulation disabled for unsupported/incomplete networks. | ✅ | 2026-11-03 |
| TASK-040 | In `tests/smoke.py`, seed deterministic road networks and movement demand; assert repeatable bottleneck results, blocked-network warnings, and explicit simulation limitations. | ✅ | 2026-11-03 |

### Implementation Phase 20 — Professional Version (Post-User Gate; On Hold)

- **GOAL-021**: Decide whether to begin professional workflows only after user evidence exists. Acceptance: no BIM/MEP/construction-phase/contractor implementation starts until usage and validated customer demand are documented and the scope is separately approved.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-041 | Before implementation, document active-user evidence, validated demand, target buyer, and the specific professional workflow in `plan/`. If evidence is absent, mark this phase On Hold and make no application-code or dependency changes. If evidence exists, create a separate approved architecture plan for BIM layers, electrical, plumbing, HVAC, construction phases, or contractor packages; do not implement these in this roadmap task. | ✅ | 2026-11-03 |
| TASK-042 | Verify the post-user gate by reviewing the evidence artifact and `git diff`; assert that absent evidence results in no professional-version code changes and that any approved work is covered by its separate plan. | ✅ | 2026-11-03 |

#### Suggested delivery windows

- **Month 1**: Chunks 1-5 after foundation cleanup.
- **Month 2**: Chunks 6-9.
- **Month 3**: Chunks 10-13.
- **Month 4**: Chunks 14-16.
- **Month 5+**: Chunks 17-19 only after core validation and user demand.
- **After users exist**: Chunk 20 remains gated by evidence and separate approval.

Dates are planning targets, not acceptance criteria. Complete chunks by passing their stated criteria, not by reaching a calendar date.

## 3. Alternatives

- **ALT-001**: Rewrite the current application into React, TypeScript, Vite, FastAPI, and PostGIS before finishing the MVP. Not chosen because current code already supports the core decision workflow, and a rewrite delays user validation without proving additional decision value.
- **ALT-002**: Add collaboration, contractor workflows, and advanced simulations before the core decision workflow is validated. Not chosen because these do not improve the initial property-selection-to-concept decision path and would expand scope prematurely.
- **ALT-003**: Treat missing land-data coverage as clear or buildable. Not chosen because it would overstate what sparse public samples can establish.

## 4. Dependencies

- **DEP-001**: Existing MapLibre, USGS, AWS Terrain Tiles, and optional OpenStreetMap context code in `index.html`; network-based map checks must use mocked endpoints.
- **DEP-002**: Existing property analysis, planning, placement, and cost-estimation logic in `index.html`.
- **DEP-003**: Existing Playwright and Python smoke-test setup in `tests/smoke.py`.
- **DEP-004**: Current project storage and migration behavior in `index.html`; tests must continue to use project localStorage fixtures.

## 5. Files

- **FILE-001**: `index.html` — property selection, map context, analysis, build zones, planner, cost estimates, and 3D experience.
- **FILE-002**: `tests/smoke.py` — mocked browser regressions and MVP end-to-end path.
- **FILE-003**: `README.md` — user-facing capabilities and data limitations.
- **FILE-004**: `data-notice.html` — disclosure of external requests and local storage.
- **FILE-005**: `CHANGELOG.md` — release notes for shipped chunks.
- **FILE-006**: `sw.js` — static-shell cache version.
- **FILE-007**: `acreforge.zip` — deployable archive rebuilt from its current member list.

## 6. Testing

- **TEST-001**: Run `python tests/smoke.py` after each phase that changes browser behavior.
- **TEST-002**: Validate all inline JavaScript blocks in `index.html` with `node --check`.
- **TEST-003**: Run `git diff --check` and verify the release archive contains the intended current files and cache version.
- **TEST-004**: Verify new data paths with deterministic mocked map/API responses, including empty, partial, and failed coverage.
- **TEST-005**: Confirm no new browser errors, no loss of current parcel selection, and no false claims of legal buildability or complete mapped inventory.

## 7. Risks & Assumptions

- **RISK-001**: OpenStreetMap coverage varies by location; missing roads or buildings must not be interpreted as proof none exist.
- **RISK-002**: Sparse elevation, flood, or soil samples cannot support parcel-wide legal or engineering conclusions; labels must state the actual evidence scope.
- **RISK-003**: Integrating data-driven overlays with proposed design visuals may confuse users unless existing and proposed features use distinct styles and a clear legend.
- **ASSUMPTION-001**: Existing address, pin, parcel import, terrain, analyzer, planner, cost, and 3D capabilities are retained and improved rather than rebuilt.
- **ASSUMPTION-002**: Public services remain optional user-triggered references; this plan does not add accounts, cloud sync, paid APIs, or server-side storage.
- **ASSUMPTION-003**: Each phase is a separate deliverable and should be implemented only after the previous phase's acceptance checks pass.

## 8. Related Specifications / Further Reading

- `README.md` — current product behavior, data sources, limitations, and local-first storage.
- `CHANGELOG.md` — existing feature history and release conventions.
- `data-notice.html` — current privacy and external data request disclosures.
