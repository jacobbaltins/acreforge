---
goal: Add the Next 20 Local-First AcreForge Upgrades
version: 1.0
date_created: 2026-11-03
last_updated: 2026-11-03
owner: AcreForge
status: 'Deprecated'
tags: [feature, roadmap, local-first, usability]
---

# Introduction

![Status: Deprecated](https://img.shields.io/badge/status-Deprecated-red)

Superseded by `plan/feature-acreforge-user-roadmap-1.md`, which records the user's five-phase priority and makes real-world map synchronization the next 100+ hour focus. Do not execute this former generic Phases 21–40 plan. No tasks from this plan were started.

## 1. Requirements & Constraints

- **REQ-001**: Deliver exactly 20 independently verifiable feature increments, numbered Phases 21–40, in the order listed below.
- **REQ-002**: Every feature must preserve existing saved projects, parcel selection, scenario selection, and browser-local behavior.
- **REQ-003**: Every new persistent field must have a default and a migration/normalization path in `normalizeState()` in `index.html`; importing older backups must continue to work.
- **REQ-004**: New measurements, evidence, comparisons, and costs must identify their source and uncertainty; none may be described as a survey, bid, permit, legal finding, or professional design.
- **REQ-005**: Add only user-triggered public-data requests, preserve attribution, disclose failures, and do not infer a missing result as a negative finding.
- **REQ-006**: Each phase must add deterministic Playwright coverage to `tests/smoke.py`; use seeded localStorage fixtures and mocked network responses, not live public services.
- **REQ-007**: Update `README.md`, `CHANGELOG.md`, `sw.js`, and `acreforge.zip` only in phases that change user-visible behavior; preserve the archive's member list and pre-existing unrelated workspace changes.
- **CON-001**: Keep the application static and local-first; do not introduce React, a server, accounts, cloud sync, telemetry, paid APIs, or new runtime dependencies.
- **CON-002**: Do not implement BIM, MEP, contractor workflows, permit automation, construction management, professional traffic/fire/access reviews, or other scope gated by Phase 20.
- **CON-003**: Do not alter or restore the pre-existing deleted `CALCULATIONS.md` or `Oregon-Estate-Planner-Print-and-Follow-Guide.pdf`.
- **CON-004**: Preserve current export/import safety behavior and warn before any action that replaces user data.
- **GUD-001**: Prefer extending the named existing functions and DOM event delegation in `index.html`; extract a helper only when it is shared by multiple surfaces.
- **GUD-002**: Keep every feature opt-in or dismissible where it could interrupt an existing workflow.
- **PAT-001**: Match the existing single-file application patterns, state normalization, `save()` persistence, accessible labels, and Playwright checks in `tests/smoke.py`.

## 2. Implementation Steps

### Implementation Phase 21 — Guided Project Setup

- **GOAL-022**: Give new projects a dismissible, progress-aware first-use path.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-043 | In `index.html`, extend `defaultState()`, `normalizeState()`, `dashboardPage()`, and delegated click handling to add a first-use panel with four explicit steps: choose property/location, import or defer parcel, inspect land data, and create or review a concept. Persist dismissal and step completion per project; never mark an external lookup complete unless it returned usable data. | | |
| TASK-044 | In `tests/smoke.py`, seed empty, partially complete, and finished projects; assert step state, dismiss/restore behavior, reload persistence, and that failed lookups do not count as complete. Depends on TASK-043. | | |

### Implementation Phase 22 — Due-Diligence Evidence Tracking

- **GOAL-023**: Let users track evidence and follow-up for existing checklist prompts without suggesting compliance.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-045 | In `index.html`, extend `compliancePage()`, `taskSeed`, `normalizeState()`, and the checklist input handler so each existing item can store status (`open`, `in-progress`, `verified-by-user`, `not-applicable`), a short note, source label/URL, and review date. Migrate legacy `state.tasks[name].done` to a compatible status and retain the current non-compliance disclaimer. | | |
| TASK-046 | In `tests/smoke.py`, verify legacy migration, each status transition, bounded note/source input, persistence, and the unchanged warning that user-marked status is not official compliance. Depends on TASK-045. | | |

### Implementation Phase 23 — Project Milestones

- **GOAL-024**: Add a lightweight project milestone list with dates and completion state.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-047 | In `index.html`, add `state.project.milestones` normalization and a milestone panel in `dashboardPage()` with add, edit, complete, and remove actions. Limit the list to 50 entries; require a non-empty title; validate optional ISO dates; save changes using existing `save()` and confirm before removal. | | |
| TASK-048 | In `tests/smoke.py`, cover valid/invalid dates, title validation, add/edit/complete/remove, the 50-entry limit, confirm-cancel behavior, and reload persistence. Depends on TASK-047. | | |

### Implementation Phase 24 — Evidence and Source Register

- **GOAL-025**: Make source provenance for user-supplied property evidence visible in one place.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-049 | In `index.html`, add normalized `state.project.evidenceSources` records and an Evidence section under `reportsPage()` listing source title, category, user-provided URL or description, added date, and optional note. Reuse existing parcel source and map-data attribution where available; do not claim a source was independently verified. Escape all rendered values and keep entries local. | | |
| TASK-050 | In `tests/smoke.py`, verify rendering/escaping, add/edit/remove, empty and missing-source states, migration from a project without the field, and absence of external requests. Depends on TASK-049. | | |

### Implementation Phase 25 — Parcel Geometry Quality Checks

- **GOAL-026**: Detect common imported-boundary geometry problems before displaying derived measurements.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-051 | In `index.html`, extend `parseGeoCoordinates()`, `normalizeParcelBoundary()`, and the parcel import flow with deterministic checks for non-finite/out-of-range WGS84 coordinates, duplicate consecutive vertices, too-short rings, zero-area rings, and self-intersections. Reject invalid input without replacing the existing boundary; report warnings separately for valid but unusual multipart geometry. | | |
| TASK-052 | In `tests/smoke.py`, seed valid polygon, hole, multipart, self-intersecting, zero-area, out-of-range, and duplicate-vertex fixtures; assert acceptance/rejection, unchanged prior parcel on rejection, and no fabricated measurements. Depends on TASK-051. | | |

### Implementation Phase 26 — Site-Plan Measurement Tool

- **GOAL-027**: Provide explicit point-to-point distance and drawn-area measurements on the flat plan.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-053 | In `index.html`, extend `designerPage()`, map toolbar event handling, and `drawMap()` with a non-persistent measurement mode for segment distance and polygon area/perimeter. Use the existing feet-based plan coordinate system, show units and a clear/remove control, and label results as planar estimates that do not adjust for terrain slope. Do not write measurement geometry into saved site objects. | | |
| TASK-054 | In `tests/smoke.py`, verify deterministic length/area arithmetic, mode cancellation, clear behavior, no project-state mutation, keyboard-accessible controls, and explicit planar-measurement caveats. Depends on TASK-053. | | |

### Implementation Phase 27 — Print-Ready Site-Plan Sheet

- **GOAL-028**: Make the site plan more legible when printed or saved from the browser.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-055 | In `index.html`, extend `drawMap()` and the existing print/report styles to provide a print layout with project/scenario title, north indicator, scale bar derived from the current plan dimensions, symbol legend, boundary-source label, and date. Hide editor controls in print CSS; retain the boundary-not-a-survey disclaimer and avoid changing the on-screen map. | | |
| TASK-056 | In `tests/smoke.py`, assert required print-sheet elements, scale-bar arithmetic at multiple extents, correct legend for empty/non-empty plans, and that editor controls are excluded from print media. Depends on TASK-055. | | |

### Implementation Phase 28 — Multi-Select and Bulk Transform

- **GOAL-029**: Improve layout editing for several selected site objects at once.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-057 | In `index.html`, extend selection state, `drawMap()`, pointer/keyboard handlers, and undo snapshots to support additive multi-selection and group move/duplicate/delete. Keep resize/rotate behavior single-selection only; parcel-boundary violations must reject the entire group move without partial mutation. | | |
| TASK-058 | In `tests/smoke.py`, test additive selection, group move, duplicate, delete, undo/redo, mixed valid/invalid parcel moves, and regression behavior for existing single-object editing. Depends on TASK-057. | | |

### Implementation Phase 29 — Alignment and Distribution Guides

- **GOAL-030**: Help users align object edges and distribute gaps consistently.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-059 | In `index.html`, extend the object drag/resize path in `drawMap()` and designer event handlers with optional alignment guides and explicit Align left/center/right, Align top/middle/bottom, and Distribute horizontal/vertical actions for multi-selection. Keep snapping visual-only until release and preserve parcel checks and undo semantics. | | |
| TASK-060 | In `tests/smoke.py`, seed unequal object sizes and assert exact resulting edges/centers/gaps, guide visibility, snap toggle behavior, parcel rejection, and one-step undo. Depends on TASK-059. | | |

### Implementation Phase 30 — Site-Object Search and Filters

- **GOAL-031**: Make large site plans easier to inspect through a searchable object list.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-061 | In `index.html`, extend `designerPage()` and the placed-object list renderer with case-insensitive name/type search plus filters for type, planning phase, and status. Selecting a result must select and center its object on the map without changing the saved project. Preserve the existing list and layer controls. | | |
| TASK-062 | In `tests/smoke.py`, verify combined filters, empty results, keyboard selection, map focus on the correct object, and unchanged item data while filtering. Depends on TASK-061. | | |

### Implementation Phase 31 — Phase Schedule Summary

- **GOAL-032**: Summarize the existing conceptual Phase 1/2/3 assignments without creating construction-management claims.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-063 | In `index.html`, extend `reportsPage()` and `compute()` to group current site objects and modeled costs by their existing `phase` field, report unassigned/unknown items explicitly, and label the result as a conceptual planning sequence rather than a construction schedule. Do not add labor, durations, dependencies, or contractor workflow. | | |
| TASK-064 | In `tests/smoke.py`, seed items across all phases and missing/invalid phase values; assert item counts and cost totals reconcile with the overall estimate and limitation text remains visible. Depends on TASK-063. | | |

### Implementation Phase 32 — Cost Sensitivity View

- **GOAL-033**: Show how editable cost assumptions affect the current low/medium/high estimate.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-065 | In `index.html`, extend `plCompute()`, `plCost()`/budget rendering, and `reportsPage()` with a deterministic sensitivity view that varies one selected existing cost assumption at a time by −20%, current, and +20%. Do not mutate saved assumptions while previewing; label all values as local planning estimates and exclude unavailable line items. | | |
| TASK-066 | In `tests/smoke.py`, assert monotonic response to unit-rate/contingency changes, unchanged persisted assumptions after preview, reconciliation to current totals, and correct unavailable-line behavior. Depends on TASK-065. | | |

### Implementation Phase 33 — Scenario Delta Comparison

- **GOAL-034**: Explain changes between saved scenario snapshots, beyond showing their absolute metrics.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-067 | In `index.html`, extend the scenario snapshot comparison renderer to show signed deltas for cost, buildability, utility distance, and self-sufficiency only when both snapshots contain compatible values; show privacy as unavailable unless both values are measured. Add a clear baseline selector and never imply that correlation is causation. | | |
| TASK-068 | In `tests/smoke.py`, compare snapshots with positive, negative, zero, and missing metrics; assert delta arithmetic, baseline switching, and correct unavailable behavior. Depends on TASK-067. | | |

### Implementation Phase 34 — Assumptions Register

- **GOAL-035**: Collect estimates and unresolved assumptions in a single reviewable report section.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-069 | In `index.html`, extend `reportsPage()` to generate an Assumptions register from existing cost assumptions, utility-route provenance, venue/compound disclosures, terrain coverage, and user-entered evidence notes. Each row must identify its source or say “not supplied”; do not create an inferred fact to fill a gap. | | |
| TASK-070 | In `tests/smoke.py`, seed known, missing, and user-entered assumptions; assert complete source labeling, no optimistic fallback, and stable output across repeated renders. Depends on TASK-069. | | |

### Implementation Phase 35 — Structured Report Export

- **GOAL-036**: Add a portable, machine-readable project summary without changing the existing full backup format.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-071 | In `index.html`, add a separate `exportReportJson()` action to `reportsPage()` that exports only the current project/scenario summary, measurements, estimate ranges, evidence sources, open due-diligence items, and disclosures. Include schema version and generation time; do not export unrelated local history or credentials. Keep `exportProject()` as the full backup action. | | |
| TASK-072 | In `tests/smoke.py`, intercept the download and verify the report schema, selected scenario, totals, required caveats, absence of unrelated state, and valid JSON escaping. Depends on TASK-071. | | |

### Implementation Phase 36 — Local Storage Health

- **GOAL-037**: Make local save state and storage pressure understandable before data is lost.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-073 | In `index.html`, extend `save()` and the save-status UI to report successful local saves, quota/storage errors, and approximate current project-data size. On write failure retain the existing in-memory project, show an actionable export-backup message, and do not display a success state. | | |
| TASK-074 | In `tests/smoke.py`, stub storage writes to succeed, throw quota errors, and recover; assert status text, approximate byte count, in-memory state preservation, and no success-shaped error response. Depends on TASK-073. | | |

### Implementation Phase 37 — Backup Inspection and Safe Restore

- **GOAL-038**: Let users inspect backup metadata and compare it to the current project before import.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-075 | In `index.html`, extend the project import handler and `normalizeState()` to preview backup project name, save time, scenario count, and object count before applying. Preserve the current confirm-before-replacement gate, reject malformed/newer backups before mutation, and state that comparison is metadata-only. | | |
| TASK-076 | In `tests/smoke.py`, verify metadata preview, cancel preserving the current project, confirmed import, malformed/newer backup rejection, and legacy backup normalization. Depends on TASK-075. | | |

### Implementation Phase 38 — Public Export Privacy Preflight

- **GOAL-039**: Help users review potentially identifying project details before generating a public export.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-077 | In `index.html`, extend the public export action to list project name, location fields, parcel-source metadata, notes, and site-object labels that would be included; require a distinct confirmation before download and offer cancel without changing data. Do not silently redact or modify the user's project. | | |
| TASK-078 | In `tests/smoke.py`, seed identifying and non-identifying values; assert the preflight enumerates included fields, cancel prevents download, confirmation exports the unchanged selected data, and no value is silently removed. Depends on TASK-077. | | |

### Implementation Phase 39 — Offline and Data-Source Status

- **GOAL-040**: Distinguish locally available project features from network-dependent references and lookups.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-079 | In `index.html`, add an accessible network-status indicator and source-state labels for user-triggered terrain, elevation, FEMA, USDA, geocoding, and OpenStreetMap features. Reuse their current request/error state; never initiate requests from the indicator, and never describe stale or failed data as current. | | |
| TASK-080 | In `tests/smoke.py`, simulate online/offline transitions and mocked success/empty/failure responses; assert labels update correctly, local editing remains available, and no network call occurs solely from status display. Depends on TASK-079. | | |

### Implementation Phase 40 — Accessibility and Interaction Audit

- **GOAL-041**: Close keyboard, focus, and announcement gaps across the new and existing high-use planning flows.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-081 | In `index.html`, audit the new onboarding, checklist, map measurement, object search, multi-select, report export, and traffic-analysis controls. Add semantic labels, visible focus states, non-color status cues, keyboard alternatives for pointer-only actions, and concise live announcements; do not change analysis results or silently alter user data. | | |
| TASK-082 | In `tests/smoke.py`, exercise those flows with keyboard-only navigation, assert accessible names/focus restoration/live status changes, and verify no keyboard action triggers an unintended destructive operation. Depends on TASK-081. | | |

## 3. Alternatives

- **ALT-001**: Start a framework/server rewrite. Rejected because the existing static app and local project format already support the proposed work, and a rewrite adds migration risk without a validated need.
- **ALT-002**: Implement all 20 features in one release. Rejected because it makes regressions harder to isolate and contradicts the repository's verified one-chunk-at-a-time delivery pattern.
- **ALT-003**: Add collaboration, payments, or professional workflows as part of this package. Rejected because they require separate security, privacy, customer-demand, and Phase 20 approval.

## 4. Dependencies

- **DEP-001**: Existing state model and migration path in `index.html`: `defaultState()`, `normalizeState()`, `save()`, and `scenario()`.
- **DEP-002**: Existing user surfaces in `index.html`: `dashboardPage()`, `designerPage()`, `compliancePage()`, `reportsPage()`, `drawMap()`, `compute()`, and `plCompute()`.
- **DEP-003**: Existing deterministic Playwright fixtures and mocked network routes in `tests/smoke.py`.
- **DEP-004**: Original roadmap Phase 20 remains on hold; this plan does not satisfy or bypass its evidence gate.

## 5. Files

- **FILE-001**: `index.html` — local state, UI, geometry, calculations, export, storage, and interaction changes.
- **FILE-002**: `tests/smoke.py` — deterministic regression tests for every new phase.
- **FILE-003**: `README.md` — user-facing descriptions and limitations for shipped additions.
- **FILE-004**: `CHANGELOG.md` — release notes when user-visible additions ship.
- **FILE-005**: `sw.js` — static-shell cache marker when user-visible code changes ship.
- **FILE-006**: `acreforge.zip` — refreshed release archive with existing member list preserved.
- **FILE-007**: `plan/feature-acreforge-next-20-upgrades-1.md` — this execution plan and completion record.

## 6. Testing

- **TEST-001**: For each implementation phase, run its focused Playwright assertions in `tests/smoke.py` using deterministic fixtures.
- **TEST-002**: After each browser-behavior change, run `python tests/smoke.py` from the repository root.
- **TEST-003**: Check inline JavaScript syntax in `index.html` using the repository's available Node.js syntax-check procedure.
- **TEST-004**: Run `git diff --check`; confirm existing saved-project import/export and scenario regressions remain green.
- **TEST-005**: When refreshing `acreforge.zip`, verify CRC integrity, unchanged member list, and exact parity for updated packaged files.

## 7. Risks & Assumptions

- **RISK-001**: New project-state fields can break old backups if added without defaults; every phase must test legacy migration and round-trip persistence.
- **RISK-002**: More detailed reports can overstate data quality; source, coverage, timestamp, and uncertainty must remain explicit.
- **RISK-003**: Multi-select and map gesture changes can interfere with existing pan, draw, and single-object selection; preserve their regression tests.
- **RISK-004**: Browser storage quotas vary; storage diagnostics must be estimates and never promise a guaranteed capacity.
- **RISK-005**: Browser print output varies; test generated DOM and print CSS rather than claiming pixel-identical printer output.
- **ASSUMPTION-001**: The repository remains a static browser-local app and no user has authorized cloud accounts, paid services, or external sharing.
- **ASSUMPTION-002**: These 20 upgrades are planned additions; each phase requires normal implementation, validation, and release review before it is marked complete.
- **ASSUMPTION-003**: All network data remains optional, user-triggered, attributed, and subject to the existing coverage limitations.

## 8. Related Specifications / Further Reading

- `plan/feature-acreforge-mvp-decision-flow-1.md` — completed original roadmap and Phase 20 gate.
- `plan/phase-20-user-evidence.md` — evidence review that keeps professional-version work on hold.
- `README.md` — current application behavior, local storage, public data, and limitations.
- `tests/smoke.py` — established browser test harness and deterministic fixtures.
