## v110

- Add a CAD Studio Quick Build wizard for appending editable one-, two-, or three-room rectangular concepts with user dimensions, room names, a door, and a window.
- Validate dimensions and required layer availability before mutation; save the batch as one undoable action and disclose conceptual-only limits.
- Add browser smoke coverage for cancellation, invalid dimensions, locked layers, all layouts, append behavior, and single-step undo.

## v109

- Make CAD window/crossing selection classify from the final mouseup coordinates as well as intermediate movement, avoiding missed selections when browser move events are coalesced.
- Add a regression test for a selection drag with no intermediate mousemove event.

## v108

- Add a local ASCII R12 DXF importer for LINE, straight 2D POLYLINE, CIRCLE, ARC, and TEXT with explicit unit conversion, preview, source-layer mapping, append-only import, and one-step undo.
- Reject malformed, out-of-range, elevated, non-XY, and curved-polyline geometry without modifying the drawing; skip and report unsupported entity records.
- Document DXF subset, parser limits, local-only behavior, and remaining CAD import limitations.

## v107

- Add CAD Studio conceptual takeoffs for room floor area, wall centerline length, gross wall area, and door/window counts, with optional user-entered rates and a local CSV download.
- Validate rates, preserve them in the browser, and disclose quantity assumptions and the limits of partial cost allowances.
- Track remaining gaps: PDF sheet selection, preview, PNG export, and a declarative interaction transition table.

## v106

- Add a CAD Studio export wizard for conceptual vector PDF sets and R12 DXF files, with a PDF paper choice and a clear local-download/format disclosure.
- Preserve command-line PDF and DXF exports, keep canceled paper choices from changing the saved drawing, and report partial PDF sheet generation.
- Clarify CAD Studio's implemented linked 3D and export features and document its remaining import/layout limitations.

## v105

- Add a live CAD Studio Mode status: ready, point, number, option, text, object, selection, window/crossing selection, pan and drag states.
- Keep interaction state visible and plain-language while drawing, selecting, or using the command line.
- Reinstall terrain map layers after both default MapLibre style diffs and full style reloads, without waiting for external tiles or duplicating controls.

## v104

- Linked 3D view: **Split 3D** button shows a concept block model (walls, door/window openings, simplified roof) beside the plan, with ViewCube buttons (Top/Front/Right/Back/Left/Home), drag to orbit, wheel to zoom. It updates as you draw. Gambrel and barn roofs show as gable. Not an engineered model; not saved in the drawing. Command: VIEW3D (Top/Front/Right/Back/Left/Home/Off). ZIP is now built from LF-normalized text so it matches the committed files.

## v103

- CAD Studio error and recovery layer: plain-language health chip (Normal / Warning / Error / Recovery), your work is never discarded automatically.
- Rejects walls of 6 in or less, rooms under 24 x 24 in, doors/windows off a wall, oversized or overlapping openings, with guidance; empty undo/redo says so.
- Browser-storage-full detection pauses saving, keeps the drawing open and offers a JSON backup download (BACKUP command).
- Rolling local backup; a corrupt saved drawing is restored from it (damaged copy kept). Crash detection offers Restore / Discard.
- Autosave every 20 seconds plus on each change. PDF export skips a failed sheet and reports a partial set (e.g. 9 of 10).
- Local-first only; cloud sync, offline merge and terrain-sculpt warnings are future. Inches only, conceptual output.

## v102
- CAD Studio: new cad-sheets.js. Elevations (front/rear/left/right) are derived from walls plus door/window openings; ROOF (gable/hip/shed/gambrel/barn, pitch/12, overhang) reports area, ridge length and ridge height (hip/gambrel/barn are simplified approximations); section profile; ELEV, ROOF and PDF commands; paper select and Download PDF button. The PDF is a real vector PDF (hand-written writer, no browser print dialog) with 10 sheets (cover, floor plan, 4 elevations, section/roof, foundation, electrical CONCEPT, plumbing CONCEPT), title block, sheet numbers, auto 1:N scale, north arrow, inch units. Papers: Letter, Legal, 11x17, ARCH D, ARCH E, A, B, A4, A3. Conceptual, not for construction; DXF/PDF only, no DWG. Still free.

## v101
- CAD Studio: HiDPI-crisp canvas (devicePixelRatio-aware, pixel-aligned lines, per-layer lineweights, major/minor grid, filled dimension arrows), grouped ribbon toolbar, and new commands ROTATE, MIRROR, SCALE, OFFSET, TRIM, EXTEND, FILLET, ARC, HATCH, ID, UNITS, PROFILE.
- CAD Studio is inches-only by default: feet-and-inches notation is rejected; areas in sq in; UNITS switches display/input to mm, cm or m (geometry and DXF stay in inches).
- Add a selectable AcreForge-own User keyboard profile (aliases C, R; Ctrl+Shift+C/T/M/F, Ctrl+R, Ctrl+Shift+P, Home); unmapped Inventor-only items are listed in help. No Autodesk files are bundled; DXF only, no DWG.
- DXF export now writes ARC entities and hatch as lines.

## v100
- Add a dedicated CAD Studio workspace (nav + dashboard card): dark model-space canvas with grid, ortho/polar/snap/object snaps, live coordinates, pan/zoom, layers panel, properties and a command line (LINE, PLINE, RECT, CIRCLE, ERASE, MOVE, COPY, WALL, ROOM, DOOR, WINDOW, OUTLET, FIXTURE, STAIR, DIM, TEXT, DIST, AREA, LAYER, CEILING, WALLTH, GRID, ZOOM, UNDO/REDO, SELECTALL, HELP, DXF). Typed distances, angles and @relative coordinates in feet/inches. DXF (R12) export only; not DWG, not AutoCAD parity, conceptual only. Free until further notice.

## v99
- Add a Lot Builder command line and hotkeys (tools, ROOM/WALL/DIM by feet, LEVEL, UNDO/REDO, FIT, 2D/3D, DXF, HELP). Unknown or out-of-range input is rejected with a message; DXF remains the conceptual existing export, not DWG or full AutoCAD.

## v98
- Make all available AcreForge features free until further notice and remove the paid-pilot promotion; optional external model-provider charges remain separate.
- Add a current-scenario landscape object schedule with approximate footprints and walking-path lengths, not a planting or materials takeoff.
- Add browser-local, manually drawn four-sided elevation sketches in Lot Builder, independent of the existing floor plan and 3D model.
- Add office outlet markers, room ceiling heights and editable door/window dimensions in inches; reflect opening widths in floor-plan exports and show dimensions in the conceptual 3D model.
- Refine the 3D presentation and use room ceiling heights for matching walls, retaining the existing cutaway and interactive controls.
- Add a Space & building builder heading and printable conceptual floor-plan and elevation sheets with room, opening and outlet details.
- Clarify that elevation sketches are not included in project backups or floor-plan exports and are not construction drawings.

## v97
- Respect the system reduced-motion preference in Home Builder by disabling automatic 3D rotation; manual preview controls remain available.
- Avoid creating the Home Builder animation timer when rotation is disabled.

## v96
- AF-026: Run the Home Builder 3D auto-rotation timer only while its 3D view is visible; stop the timer in 2D, on other pages, or in a hidden tab.
- Preserve manual preview and editing actions; this does not change other animation timers.

## v95
- AF-026: Suspend the Site Designer's periodic 3D auto-rotation timer while the document is hidden, and resume it when the designer becomes visible again.
- Keep manual redraws and project data unchanged; other preview timers are not covered by this optimization.

## v94
- AF-014: Add a local seasonal sun-position preview using explicit WGS84 coordinates and a chosen browser-local date/time, with approximate sunrise/sunset and azimuth/elevation.
- Show selected-day and nominal June/December solstice elevation paths; validate coordinate bounds and disclose timezone/accuracy assumptions.
- Do not infer a location or claim shade, obstruction, solar-panel, or building-orientation analysis.

## v93
- AF-023: Add a local side-by-side visual comparison of frozen saved concept layouts, with a selectable “After” snapshot and the existing numeric decision metrics.
- Keep previews schematic and read-only; do not alter the active scenario, project data, or existing restore/export workflows.

## v92
- Replace ambiguous Pro/early-access copy with an explicitly unvalidated future paid-pilot hypothesis covering multiple projects, cloud backup/sync, collaboration, project history, and enhanced reports.
- Keep the core local planning workflow free and useful; state that no price, pilot, paid feature, or payment is active, and link to user-controlled feedback rather than implying enrollment.

## v91
- Replace the public issue/waitlist path with a user-controlled, blank-recipient email draft and copy fallback.
- Add an in-app feedback route with limited, non-sensitive prompts; no backend inbox, persistence, analytics, project-data access, or automatic sending.
- Explain recipient/provider handling and the draft's local-only behavior; add focused browser smoke coverage.

## v90
- Improve the existing print-ready report with saved property assumptions, a schematic site layout, building-concept schedule, modeled land allocation, and explicit cost inputs versus estimates.
- Focus the due-diligence section on open questions and include descriptions, priorities, report date, units, and source/accuracy caveats.
- Keep report generation and printing local; preserve the existing project backup, CSV, PDF, and DXF exports.

## v89
- Keep save status accurate through saving, success, startup-storage errors, and recovery-only launches; leave it visible on narrow screens.
- Preserve the first-property draft marker until a save succeeds, including when a workspace switch flushes pending edits.
- Clarify local storage, recovery, backup/import warnings, and what leaves the device; add persistence and failure-safety checks.

## v88
- Clarify the first-project choice: create and name a new property or open an illustrative sample layout.
- Keep sample data and recovery separate from the user project, with visible return and sample-reset actions.
- Guide new projects to the planner or site designer and show a clear continuation path for saved work.

## v87
- AF-021: Add a selectable cost-sensitivity preview for overall contingency or a populated site-object type at −20%, current, and +20%.
- Reconcile the current preview to conceptual CapEx, exclude unavailable object types, and keep saved project assumptions unchanged.

## v86
- AF-019: Add an RV park concept with a configurable site count and gross area allowance, check-in, restroom, and existing well/septic placeholders.
- Keep each RV area as one editable footprint; validate bounded inputs, disclose planning-only assumptions, and preserve the previous generated objects on invalid requests.

## v85
- AF-018: Add a local ranch concept program with an outdoor arena, round pen, pasture and paddock placeholders, feed/tack, hay, and manure storage.
- Include generated ranch-object costs in the existing low/medium/high estimate; disclose that footprints do not establish animal capacity, grazing suitability, water supply, welfare compliance, or permits.

## v84
- AF-015: Add a local downslope routing preview from known terrain nodes, with relative contributing-node counts, no-data gaps, flat/local-low stops, and explicit limits.
- Keep this read-only terrain proxy separate from water-flow, runoff, flood, drainage design, project estimates, and external lookups.

## v83
- AF-013: Add a temporary, user-configurable slope-only what-if preview of sampled terrain cells, preserving unknowns and excluding outside-boundary cells.
- Keep the preview separate from the existing analysis, plan, and budget; environmental, legal, access, and site constraints remain unverified.

## v82
- AF-010: Add a local conceptual septic occupancy, daily-flow, tank-volume/footprint, and drain-field-area estimator driven only by user-entered assumptions.
- Keep septic results separate from the existing planner budget and explicitly disclaim Oregon permitting suitability, regulatory compliance, and site-specific design.

## v81
- Guard conceptual earthwork against invalid footprint dimensions or coordinates, and clarify that a saved relative target must be reviewed when terrain is replaced.
- Add a mixed-slope cut/fill calculation check and refresh the release archive.

## v80
- Add an explicit relative target-elevation input for bounded conceptual cut/fill quantities over supported plan footprints.
- Show gross cut/export and fill/material-import quantities, recalculate during terrain strokes and on undo/redo, persist the user-selected target, and suppress unsupported terrain/footprint cases.

## v79
- Add a local driveway material allowance calculator using user-entered length, width, depth, material label, and low / expected / high rates per cubic yard.
- Leave market prices blank, validate ordered rates, persist inputs locally, and keep the material-only result separate from the existing planner budget with explicit exclusions.

## v78
- Add explicit direct-drag repositioning for the local reference-image underlay in Site Designer, saving its property-local anchor on release.
- Keep other plan gestures inactive during underlay move mode; support Escape cancellation and preserve the image's approximate, non-survey status.

## v77
- Add local reference-image rotation about the top-left plan anchor, with explicit clockwise angle and saved-project compatibility.
- Keep reference images beneath editable objects; image placement remains approximate and is not georeferencing or survey registration.

## v76
- Add local known-distance reference-image scaling from a measured horizontal or vertical pixel span, preserving image aspect ratio and requiring explicit placement.
- Validate the measurement and image availability without changing the saved project on failure; calibration does not establish image position, rotation or survey registration.

## v75
- Add local, validated re-importable terrain CSV downloads for edited and synthetic grids, retaining no-data and relative relief without fabricating a vertical datum.
- Reject unsupported extents and grids outside the existing import limits; original source, absolute elevations and provenance do not travel with the CSV.

## v74
- Start new browser profiles with a blank concept and a dismissible welcome offering a local rule-based planning prompt or free exploration.
- Add an illustrative land-plan example; preserve returning projects and recovery data, and keep generation and placement explicit.

## v73
- Add named, project-scoped flat-plan view bookmarks that restore local center and zoom without changing the layout.
- Views are included in backups and public exports; they do not capture geographic or 3D cameras, layer settings or layout changes.

## v72
- Add project-scoped reusable site-object presets with confirmed removal and undoable placement of independent editable copies.
- Presets include bounded object settings in backups and public exports; they do not copy location, lock or verification status.

## v71
- Add a local PNG/JPEG reference underlay in Site Designer with explicit property-feet placement, opacity, visibility, replacement and removal.
- Store image bytes separately in browser IndexedDB; backups retain only placement and public exports omit underlay metadata. The underlay is an approximate 2D tracing aid, not survey registration.

## v70
- Add strict, local-only property-feet CSV elevation grid import with bounded dimensions, uniform spacing, no-data masks, replacement confirmation, terrain undo and provenance.
- Preserve unknown elevation cells; reject invalid or unsupported grids before replacing terrain. This is not LAS/LAZ, GeoTIFF or raw LiDAR support.

## v69
- Add a local user-supplied GeoJSON building/tree reference inventory with a distinct 3D map layer, review list, visibility control, replacement confirmation and removal.
- Validate supported WGS84 geometry and bounded input before replacement. Backups include the inventory; public export removes it. References are unverified and are neither automatic detection nor proposed objects.

## v68
- Add temporary, scenario-scoped site-object group selection with atomic move, duplicate, confirmed delete, alignment and equal-gap distribution.
- Reject locked or parcel-invalid group actions without partial changes; support one-step undo and redo. These remain conceptual layout tools, not collision or engineering checks.

## v67
- Validate new GeoJSON/KML parcel rings before replacement, with bounded input and legacy saved-project compatibility.
- Add searchable site-object filters, version-aware snapshot deltas and a sampled utility-corridor terrain profile.
- Preserve unknown terrain and explicitly distinguish centerline and privacy proxies from verified engineering measurements.

## v66
- Add local project milestones, reporting phase subtotals, contingency sensitivity, an assumptions register, and a compact current-scenario summary export.
- Show local storage health and backup metadata before restore; add a public-export privacy confirmation and exclude new milestone data from that export.
- Suppress conceptual earthwork for incomplete or unsupported terrain/footprint inputs, label new edits to imported elevation samples, export a local relative-height terrain grid CSV with no-data flags, and sample straight-line terrain cross-sections with unknown gaps.
- Preserve existing saved-project format and add deterministic browser coverage.

## v65
- Include structured conceptual handoff provenance, units, boundary caveats, exclusions and professional review checklist in the downloadable project JSON backup.
- Smoke-test the JSON backup metadata, in addition to the local TXT, CSV, DXF and PDF outputs.

## v64
- Add print-ready report disclosures for local feet coordinates, imported-boundary limits, exclusions and professional review.
- Add conceptual disclaimers to the site-plan PDF/print-sheet notes and smoke coverage for report, DXF and PDF export behavior.

## v63
- Label both DXF exports with a conceptual / not-for-construction comment header.

## v62
- Add a local-only conceptual handoff CSV (units, coordinates, review checklist; nothing sent).
- Add a subscriptions architecture proposal; no billing is implemented.

## v61
- Add a local-only, clearly labeled conceptual handoff text export on Reports (units, coordinate assumptions, exclusions, professional-review checklist); nothing is uploaded or sent and no surveyor/engineer review is implied.
- Phase 4 scope limited to this export; billing (Phase 5) remains gated.

## v60
- Add an opt-in, bring-your-own-key AI layout proposal (separate from the rule-based planner): explicit consent, https endpoint, key kept in memory only, 30 s timeout and cancel.
- Treat model output as untrusted: validate schema, types, bounds, parcel containment and overlaps; preview first and apply only on approval, with AI provenance.
- Failures, malformed output and cancellation leave the plan unchanged; add mocked browser coverage.

## v59
- Add a shared WGS84/local-feet projection so parcels, proposed features, roads, buildings, pins and terrain align on the map.
- Extend the terrain map context to a 1,000-acre square while the editable plan stays at its own size; mask elevation no-data cells.
- Add a map source status line (origin, layers, retrieval time, empty/stale/failed/offline) that makes no requests.
- Simplify dense OpenStreetMap geometry for display only (1 m), keep source geometry for measurements, and disclose the 4,000-feature display cap.
- Add browser coverage for alignment, source status, offline behavior, and dense geometry.

## v58
- Add deterministic peak-hour route analysis for cars, guest vehicles, guest walking, deliveries, and a separate emergency-access probe with bottleneck locations.
- Disable traffic simulation and analysis until the road network has vehicle-access gates and all destinations are connected; disclose route-demand assumptions and study limitations.
- Add browser coverage for repeatability, movement arithmetic, emergency-route disclosure, disconnected destinations, and networks without vehicle-access gates.

## v57
- Add an event-venue concept preset with ceremony, reception, restroom, guest-parking, and connected guest-flow path objects.
- Reconcile parking capacity and footprint to 2.4 guests per car, a 10% reserve, and 300 sq ft per car; estimate guest circulation at $10/ft with a pre-layout allowance.
- Omit guest-flow paths that cross an imported parcel boundary and disclose the generated route lengths, costs, and omissions.
- State that fire access, accessibility, occupancy, parking, and permit compliance are not assessed; add browser coverage for venue components, parking arithmetic, route connectivity, costs, and county/professional review caveats.

## v56
- Align proposed site-plan buildings, land areas, trees, roads, and water with parcel/location coordinates and 3D terrain in the MapLibre property view.
- Distinguish proposed features from optional, incomplete OpenStreetMap reference context; disclose when the plan has no usable georeference.
- Add accessible Orbit, Walkthrough, and Fly camera modes with keyboard movement/turn controls and reduced-motion-aware camera transitions.
- Add browser coverage for georeferenced proposals, missing-reference disclosures, all camera modes, and keyboard/pointer navigation.

## v55
- Add a family compound starter for a main house, parent house, guest house, and shared 40 × 60 ft shop.
- Keep compound objects within imported parcel boundaries and reject undersized layouts without replacing the prior generated layout.
- Show privacy spacing, straight-line travel, shared-trench estimates, and ranked utility-first, balanced, and privacy-first alternatives as heuristic comparisons.
- Add browser coverage for building fit, parcel containment, overlap prevention, metric consistency, alternative ranking, and constrained-site failure behavior.

## v54
- Add a one-command homestead concept with a 2,500 sq ft house, garden, orchard, coop, barn, greenhouse, pond, well, septic assumptions, and an estimated budget.
- Keep imported-parcel homestead footprints inside the supplied boundary and disclose terrain/placement rationale and unverified assumptions.
- On constrained sites, place components that fit and list omitted features with reasons; preserve the prior layout when the house itself cannot fit.
- Add smoke coverage for complete and constrained homesteads, parcel containment, rationale, cost totals, and safe failure behavior.

## v53
- Add water, power, fiber, and septic route distances, per-foot cost estimates, and short/moderate/long difficulty bands to the Property planner.
- Use named Site Designer Utility Corridor layout geometry when available; identify endpoint straight-lines and planner-distance fallbacks as estimates, and keep unavailable routes unpriced.
- Let users edit and persist route distances and per-foot rates; propagate utility and septic route costs into the corresponding low/mid/high budget lines and CSV.
- Disclose shared-sewer concepts, connection-point uncertainty, and unverified route, service, and septic conditions; add regression coverage for route arithmetic, cost propagation, geometry sources, and missing endpoints.

## v52
- Add transparent low/mid/high concept budgets for roads, utilities, buildings, site preparation, septic, design/permit allowances, and contingency.
- Make road rate, utility-rate factor, septic allowance, site-preparation, design/permit, and contingency assumptions editable and persistent per plan.
- Keep budget line items and totals reconcilable in the UI and CSV; clearly label shared sewer assumptions and when private septic is not included.
- Add regression coverage for range arithmetic, distance and building-size changes, editable assumptions, persistence, and subdivision septic disclosure.

## v51
- Save up to 12 named, frozen scenario comparison snapshots without changing the active layout.
- Compare estimated cost, home-spacing privacy, property-level buildability, generated utility routes, and self-sufficiency only when the relevant inputs exist; identify shared context and keep missing evidence unavailable.
- Restore a snapshot as a new editable scenario, or delete one with confirmation; preserve existing scenarios and snapshots.
- Retain layout-generator prompt and distance assumptions per scenario, and ensure the solar-array site-object template is available when saved projects are reloaded.
- Add browser smoke coverage for three-scenario comparison, metric mapping, unavailable values, reload persistence, active-scenario preservation, and safe restore/delete behavior.

## v50
- Generate editable concept layouts from requested home square footage and shop dimensions while checking spacing and available planning or parcel extents before replacing an existing generated layout.
- Add a conceptual driveway stub where space and parcel constraints allow, utility assumptions, per-object placement rationale, and explicit limits around access, service, permits, setbacks, and costs.
- Preserve undo behavior; reject invalid, oversized, or unplaceable plans without changing the existing layout.
- Add smoke coverage for exact dimensions, parcel extent fit, utility/access caveats, rationale, undo, safe rejection, and request-to-layout time.

## v49
- Consolidate property questions, plan starters, cost adjustments, and supported site-object edits into one rule-based Property Copilot command bar.
- Return property analysis and explicit evidence limitations; make unsupported commands fail clearly instead of implying successful AI generation.
- Extend undo snapshots to restore plan settings and goal state as well as site-plan edits; confirm each action and preserve the selected property.
- Add smoke coverage for buildability questions, homestead/compound/venue prompts, cost and object edits, undo, unsupported commands, and property retention.

## v48
- Add up to three spatially distinct, deterministically ranked build zones with lettered map markers, factor scores, rationale, tradeoffs, and keyboard-accessible details.
- Rank only candidate/caution terrain, reuse opportunity fit evidence, treat mapped-road proximity as optional context, and avoid cells with mapped high/moderate flood sample points.
- Keep privacy and unverified constraints explicit; return no zones when available terrain is constrained, unknown, or otherwise unsuitable.
- Add smoke coverage for score consistency, stable ranking, parcel containment, flood-point handling, keyboard interaction, and zero-zone results.

## v47
- Add deterministic, evidence-aware suggestions for house, shop, pond, solar, orchard, and event sites, with ranked cards, distinct map markers, rationale, and explicit evidence gaps.
- Keep suggestions reviewable and separate from saved site-plan placements; use optional mapped-road proximity only as context, never as proof of legal access.
- Add smoke coverage for all suggestion types, stable ranking, parcel containment, missing evidence, and selecting each map marker.

## v46
- Add an evidence-aware buildability map with parcel-aware candidate, caution, constrained, and unknown terrain cells, point-only flood sample markers, and click explanations.
- Exclude parcel holes and outside cells from buildability classes; reject unknown or constrained cells for generated site-plan placements.
- Add browser regressions for mixed slopes, flood markers, partial/no elevation data, parcel holes, outside geometry, and layout placement; document conceptual thresholds and unverified constraints.

## v45
- Add an evidence-aware Property Health dashboard with mapped terrain/soil indicators, explicit coverage, unavailable privacy and missing-source states, and clearly labeled distance-based access/utility estimates excluded from the composite score.
- Reject transparent or insufficient in-parcel elevation samples instead of treating no-data as flat terrain; clear stale scores before each analysis run.
- Add complete, partial, missing-source, and transparent-elevation browser regressions; document score and data-request limitations.

## v44
- Center state terrain on a selected property at neighborhood scale and report the current view center and zoom.
- Add AWS Terrarium-derived hillshade with visibility and opacity controls; align slope calculations to feet-based elevation and distance units.
- Mask transparent/no-data samples and show coverage, tile zoom, sample-grid resolution, elevation range, and analysis legend; hide overlays and relief when coverage is insufficient or requests fail.
- Add mocked terrain coverage for property-centered navigation, mapped elevation, no-data, request failures, 3D relief controls, and saved hillshade preferences.

## v43
- Add an on-demand Property building-footprint lookup with selectable mapped polygons, geodesic footprint areas, source labels, and explicitly tagged versus illustrative heights.
- Keep existing-building references temporary and separate from proposed designs; clear stale results on location or parcel changes and disclose incomplete OSM coverage and request details.
- Add mocked tests for missing/open geometry, measurements, selection, tagged/estimated heights, empty results, service errors, and proposal separation.

## v42
- Add an explicit Property road-context lookup for attributed OpenStreetMap roads, driveways, tracks, hierarchy, and supplied road names.
- Keep mapped roads temporary and separate from proposed site-plan roads; add category visibility toggles and clear incomplete-coverage, access, and request-extent limitations.
- Clear stale road references when the selected property changes; add mocked road-service coverage for user-triggered requests, classifications, labels, toggles, empty data, and service failure.

## v41
- Report imported parcel source, geodesic area, and total perimeter in Property Search; make road-frontage and adjacent-parcel gaps explicit when supporting data is unavailable.
- Keep imported parcel outlines screen-stable at different map zoom levels.
- Add multipart/interior-ring perimeter and zoomed-boundary smoke coverage.

## v40
- Add Property Search for addresses, coordinates, full Google Maps URLs, interactive map pins, and eight saved recent locations.
- Move location selection out of the Site Designer map-snapshot panel and use the selected location in property analysis.
- Explicitly distinguish location selection from parcel lookup/boundary data; retain import from assessor/GIS or survey files.
- Add mocked geocoding, failure-preservation, recent-search, pin-drop, and response-time smoke coverage.

## v39
- Replace the extra All tools/Simple menu with exactly five primary navigation destinations and open the Projects command center by default.
- Add a responsive, non-editable conceptual site-plan preview and property snapshot to the dashboard.
- Add smoke coverage for primary navigation, secondary-screen reachability, and desktop/mobile map-first layout.

## v38
- Cancel superseded Land Data lookups and discard results when the active parcel or location changes.
- Show lookup progress and prevent duplicate Land Data button submissions.

## v37
- Add a scanline fallback to fill the nine-point land-sampling cap for narrow or diagonal parcel shapes missed by the regular grid.

## v36
- Distribute land-data sample points across imported multipart parcels, exclude polygon holes, and report component coverage within the nine-point cap.
- Improve fallback sampling for parcel components missed by the initial grid.

## v35
- Extend sampled land lookups to USGS elevation at up to nine parcel points; report sampled minimum, maximum, average, and mapped coverage.
- Document that Land Data sends sampled coordinates to public elevation, flood, and soil services.

## v34
- Sample FEMA flood and USDA soil data at up to nine locations inside an imported parcel, with bounded request concurrency and explicit data-coverage counts.
- Unmapped or incomplete flood samples are not classified as low risk; parcel sampling also handles antimeridian boundaries.

## v33
- Flood and wetland overlay visibility and opacity now persist alongside slope and contour settings.

## v33
- Flood and wetland overlay visibility and opacity now persist alongside slope and contour settings.

## v32
- Added on-demand, color-coded slope bands and adaptive contour lines to the terrain map, with saved visibility and opacity controls.

## v31
- Layer opacity sliders and reference-layer toggles are remembered between visits and re-renders.

## v30
- Utilities card reconciles with the plan total: shows the generic utility amount already in the plan and a layout-adjusted total.

## Venue check uses your layout
- Venue card reads the placed parking, walking distance to the ceremony, and restroom count from the plan.

## Event venue check
- Venue and retreat plans show parking, ceremony and reception space, restrooms, arrival queue time, emergency access and a low/likely/high revenue range.

## Terrain read
- Property page explains slope aspect, water flow direction, high points and low points from the parcel elevation grid.

## Cost range
- Driveway plus utilities shown as low, likely and high estimates with assumptions.

## Utility routes
- Property planner shows power, fiber, water and septic runs with distance, material, estimated cost and difficulty.

## Layer manager additions
- The terrain map's Reference layers panel now has opacity sliders for your design and the basemap, plus a color legend (gray existing, green proposed, blue selected).

## Green proposed, blue selected
- On the 3D terrain map, houses and buildings you draw now show green (proposed) and turn blue when selected.

## Building info
- Clicking a mapped building on the 3D terrain map now shows its footprint area and distance from your picked spot.

## Driveway cost
- The driveway explanation now shows an approximate gravel cost.

## Driveway access
- Placing a plan now adds a driveway from the main house to the nearest property edge, with a written reason and length, so access is never disconnected.

## Layer opacity + gray existing buildings
- Terrain map reference layers get opacity sliders (buildings, roads, trees, fields/woods).
- Existing OSM buildings are now gray, per the map color scheme.

## Family Compound scores
- Privacy, walking distance, shared-utility trench and expansion scores for multi-home plans, with tips.

## Homestead scores
- Homestead plans show Food Production, Energy Independence and Expansion Capability scores (0-100) with tips, scaled to the household size in your prompt (e.g. 'for six people').
- Rule-of-thumb scoring from growing area, livestock, solar, water and unused buildable land.

## Budget-driven costs
- Type a target such as 'reduce to $300k' or 'cut 15%' (Ask box or new Budget field) and the plan is redesigned to fit: economy finishes, optional items dropped, homes shrunk.
- Says honestly when the target can't be reached.

## Analysis-driven placement
- 'Place on Site Designer' now uses the analyzer: the house goes on the best build zone, shop/barn/greenhouse on nearby flat ground, orchard and garden on gentler slopes, the pond on the lowest ground.
- A 'Why AcreForge put things here' list explains every placement.

## Simple workflow menu
- Nav cut to Projects, Property, Design, Reports, Settings with section tabs; 'All tools' restores the full menu.
- 'Ask AcreForge' box and goal buttons (Homestead, Compound, Venue, Retreat, Subdivision) build a starter plan in one click.

## Property Analyzer
- Paste an address: buildable area, slope, solar, flood, soil, best build zones, site-cost range.
- Command-center score, sub-score cards, click-a-cell popup (elevation, slope, uses).
- Design-system colors for scores.
- Each build zone explains why it was chosen (slope, sun, privacy, flood).

## Land overlays, retries, no-duplicate placing
- Terrain map: toggle FEMA flood zones, NWI wetlands and slope shading (planning-grade).
- Land data lookup retries slow sources once.
- Fire layer places detectors in more rooms.
- Place on Site Designer replaces earlier planner items instead of duplicating.

## Land data lookup
- AI Planner: Land data card pulls elevation (USGS), FEMA flood zone and USDA soil/drainage for the parcel center; each source fails independently.

## BIM-style layers
- Lot Builder: Layer selector (Architecture, Structure, Electrical, Plumbing, HVAC, Fire safety) with generated schematic overlays; click a room in Plumbing to list fixtures and pipe sizes.

## Design assistant
- AI Planner tab: command box edits the Site Designer plan (add another house, move the barn north, remove X, increase parking, lower costs).

## AI Planner
- New AI Planner tab: describe a project in plain text and get a program, low/mid/high cost, bill of materials, utilities trench costs, phasing chart, permit checklist, event/traffic simulation, investment/developer pro forma, and Reduce-cost-by-20% redesign.
- Place on Site Designer adds the planned buildings as objects; CSV export.
- Rule-based planning estimates, not bids or engineering.

## Lot Builder tools 5
- Added dedicated Undo/Redo buttons and keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y)
- Whole-plan scaling and rotation now transform rooms, furniture dimensions, doors, windows, and dimension lines together
- Snap-to-foot now rounds furniture sizes and dimension endpoints as well as plan geometry
- Added a CSV export for room totals, estimated costs, and furniture counts by level
- Preserved the existing Lot Builder summary stats while adding wall, door, window, and level totals

## Lot Builder tools 4
- Snap 1 ft, Remove duplicates, Scale 125%/80%, Rotate design 90°
- Delete key removes the selected item; R/Home resets the 3D view
- Wall length, door and window totals in the schedule

## Lot Builder tools 3
- Room schedule and cost estimate panel (by room type, total area, furniture summary)
- Fit scale and Center item buttons
- Keyboard: Tab / Shift+Tab cycles items, PageUp/PageDown switches levels, Q/E spins the 3D view, Alt+arrows resize the selected item

## Lot Builder tools 2
- Turn 90° 3D camera, Mirror and Flip the whole design, Copy level, Clear items, Blank design
- Share link (design is encoded in the URL and opens on load)
- Keyboard: [ and ] rotate the selected item 15°, Esc deselects

## Lot Builder tools
- Download the plan or 3D view as a PNG, save/open designs as .json files, export an item list CSV
- Center design button, arrow-key nudge (Shift = 2 ft), Ctrl+Z undo, Ctrl+D duplicate
- Library item size tooltips, visible keyboard focus rings, toast confirmations

## Lot Builder 3D + building editing
- Buildings cards: "Edit in Lot Builder · 3D" generates an editable barn, arena, shop, event hall, stand, yurt, etc. from the card's footprint and count
- Multi-part 3D furniture (sofas, beds, tables, chairs, trees, bleachers…) with shading, back-face culling and any rotation angle
- Library: thumbnails, search, new bleacher/bench/stage items, per-item colour in the inspector

## Polish pass
- Installable offline app (manifest, service worker, icon), share/SEO meta tags
- Skip link, ARIA labels, live save status with last-saved time
- Alt+1-9 tab shortcuts and ? help with storage usage
- Per-tab page titles, scroll reset, offline/online notices
- Unsaved-save guard on close, persistent storage request, print stylesheet

# Changelog

## Unreleased
- Imported parcels and their aerial/elevation/OSM overlays now use a north-up plan orientation; older parcel projects migrate their objects, routes, ground paint, terrain, and saved map image without changing their relative layout.
- Site Designer terrain can now be seeded from real AWS elevation tiles for a selected location or imported parcel, then edited with raise, lower, smooth, and flatten brushes. Real-scale (1×) relief is the default; visual exaggeration is labeled as such. Removed the synthetic hills shortcut.
- Site Designer: Cities-Skylines-style road network. Draw roads point by point (dirt, gravel, two-lane, main street, boulevard, walking path) with curves, one-way, junction snapping, upgrade and bulldoze tools, and import of existing road objects. Road cost feeds the budget.
- Traffic and pedestrian simulation: cars follow routes with lane keeping, following distance and junction yielding; walkers use sidewalks and paths. Congestion, car-volume and foot-traffic overlays in 2D and 3D, plus live stats and flags for buildings with no road access.
- 3D preview: auto-fit framing, camera views (isometric, top-down, low angle, showcase orbit) and sun-direction shadows that follow time of day (with an on/off setting).
- 3D preview options: time of day (day, dawn, sunset, night), season tint, render quality (low, medium, high) and a Save PNG screenshot button. Settings persist in this browser.
- Site Designer: pastures and crop fields are now editable land zones (type, name, color, size, outline, rotation) drawn on the plan and shown in 3D, not placeable objects.
- 3D Site Designer: polygon and rounded buildings use their true footprint and orientation.
- Site Designer: paintable ground — choose a base biome (temperate, eastern Oregon, desert, short grass, tall grass) and paint or erase local ground cover; saved per scenario with undo/redo, a "Ground cover" layer toggle, and 3D rendering.
- Originality note: Map3D, VoxCity and 3D City Database were reviewed only as inspiration; AcreForge uses its own original code and no third-party code or data.
- 3D Site Designer: roads and paths use distinct surfaced routes and terrain-aware elevation; primary/service roads gain markings, and buildings gain shaded walls, pitched roofs, windows, and doors.
- 3D Site Designer: selected road/building labels render safely; object rotations are reflected in the detailed preview.
- Site Designer: rotate mode now has a dedicated pointer interaction so rotation works alongside map drag handling.
- Site Designer: added free 360° object rotation by drag or slider, true circle and ellipse footprints, and 3D circle/triangle building forms.
- 3D Site Designer: added procedural dimensional trees, clustered bushes, hedges, and detailed post/rail, board, electric, and mesh fences; buildings now cast shadows and use faceted roof shading.
- Lot Builder: added a letter-landscape print-ready floor-plan PDF with room labels, areas, dimensions, and a planning title block; DXF now includes room labels.
- Lot Builder: DXF exports now declare CAD layers and lay out multiple floors side by side for easier review.
- Lot Builder: DXF export now includes door openings, swing leaves, and window lines on separate layers.
- Business guide: added an in-app download link to the family business launch guide.
- Accessibility: improved contrast for site-plan palette badges and active Lot Builder tools.
- Accessibility: unlabeled form controls now get accessible names automatically.
- Mobile: the ? Guide button no longer covers the bottom navigation.
- About page: pricing cards now say DXF export and PDF download are available (no longer 'planned').
- First-run quick start guide (shown once, reopen with the ? Guide button).
- Site Designer: new one-click **Download PDF** button (letter landscape, title block) next to Print sheet.
- DXF export fixed for CAD compatibility: declares the R12 format, defines named layers, and uses standard POLYLINE outlines (validated with the ezdxf parser).
- Backup files now default to an "acreforge-project" name (dated Export backup and Import/Restore already existed).
- Live on GitHub Pages: https://jacobbaltins.github.io/acreforge/ (editing on by default; the view-only mode is local/legacy).
- Added a Free / Pro (planned) / Early Access pricing preview and a Pro waitlist link; payments are not active.
- Decluttered the sidebar (shorter labels, hidden footer on short screens, scrollable mobile nav).
- Site Designer objects now have a minimum ~18px invisible hit area so they stay draggable at large acreage.
- Default parcel size is now 80 acres with 1,000 acres as the maximum (selectable in settings).
- Home Builder became the Building & Lot Builder: 12 library folders (~50 new items), editable rooms and items (size, position, rotation, type, height, duplicate, delete), starter presets (home, barn, shop, retail, full lot) and 72/150/300/600 ft drawing scales.
- Made USGS aerial imagery the default state terrain basemap, clarified the aerial/topographic layer switch, and added raised 3D building context at neighborhood zoom using reported OSM heights or explicitly estimated defaults.
- Expanded the state terrain map's optional, neighborhood-scale OpenStreetMap context to distinguish homes, other buildings, fields/orchards, woods/brush, roads, and mapped trees; added category visibility controls, safe click-to-inspect labels, and a clear action that preserves parcel geometry and user overlays.
- Clarified that mapped context is incomplete reference data, parcel boundaries must come from an assessor/GIS or survey file, and proposed-clearing polygons do not alter imagery or real-world land cover.
- Rebranded the working product name to AcreForge and updated positioning for U.S.-wide rural-property planning; the name still needs trademark clearance before commercial launch.
- Disabled the incomplete browser-only Pro/account/trial controls, removed a client-side email allowlist, and clarified that paid plans and fundraising are not active.
- Updated the support page and campaign draft to remove unconfirmed prices, rewards, and delivery promises.
- Added a prototype data/privacy notice covering browser-local data, map requests, public exports, and the unverified server-side webhook configuration; linked it from the app and status page.
- Added an unpublished, support-only GoFundMe campaign draft with suggested title, short description, and story, plus official platform/IRS references; it avoids inventing a goal, budget, organizer identity, reward, or launch date.
- Added a private, evidence-based campaign budget worksheet and organizer-only GoFundMe setup checklist; no personal identity or payout details are requested or stored.
- Added an About landing page as the app's first screen, with a summary of the project vision and shortcuts into planning and design.
- Moved the persistent color-theme control from the obstructive top-right overlay into Project Settings.

## 1.18.0
- Home Builder: Roof toggle (gable roof) in the 3D view.
- Home Builder: Dimension tool (key 7) draws ft/in measurement lines; Erase removes them.
- Home Builder: DXF export of all levels (walls and dimensions, feet) for AutoCAD/Inventor.

## 1.16.0
- CAD workspace: full-screen AutoCAD-style mode (menus, quick-access bar, tool strip, navigation bar, crosshair, command line, coordinate/status bar). Drag & drop or File menu to load project JSON or GeoJSON/KML parcels.
- Print sheet with title block; DXF export for AutoCAD.

## 1.15.0
- New default 'CAD' theme: dark drafting workspace, blue accents, square controls, crosshair cursor, model-space status bar.

## 1.14.1
- Live drag preview: a snapped ghost follows the cursor and turns red outside the parcel.

## 1.14.0
- Map view: measurement grid (50-1000 ft auto-spacing) and flat-plan overlay placed on the terrain map. Objects outside the parcel get red outlines; Zoom to plan button.

## 1.13.0
- Slope & earthwork panel: land by slope, per-object slope warnings, rough cut/fill yardage.
- City tools: generate a street grid and house lots, remove generated objects.

## 1.12.0
- 7-day free trial, free-access emails, Supabase sign-in, Stripe webhook for automatic Pro.
- Favicon and share-preview tags.

## 1.11.0
- Palette grouped by category with counts.
- Pro tier groundwork: Go Pro dialog, license-key unlock, watermark on free printed reports.
- Fixed Farmland and Town layers missing from new projects.

## 1.10.0
- Public/private mode: on a public web address visitors get a view-only plan; add ?edit=1 once to unlock editing in your browser (?edit=0 to lock). 'Public export' downloads published-project.json with boundary, location, finances and notes removed. Added map-data credits. 3D preview zoom now reaches 80x.

## 1.9.0
- Added foliage (oak, Douglas-fir, fruit trees, forest, riparian buffer, meadow, lawn, flower beds), a Farmland group (row crops, hay, vineyard, berries, greenhouse, pond, silo, sheds) and a Town & city group (houses, townhomes, apartments, shops, school, park, plaza, streets). New Farmland and Town layer toggles.

# Change log

## 1.8.1

- Added Forest, Ranch and Daylight color themes (picker at top right, remembered per browser).
- Family sharing: exported files now carry a date/time in the name, and Import shows both save times, warns if the file is older than your current project, and keeps a recovery copy.

## 1.8.0

- Added editable terrain: a **⛰ Terrain** tool in the Site Designer with raise, lower, smooth and flatten brushes, adjustable size/strength, undo/redo, "Gentle hills" and "Flatten all".
- Elevations are saved in `project.terrain` (feet), shown as a blue-to-tan overlay on the plan, and lift the ground and objects in the isometric preview (adjustable vertical exaggeration).
- Terrain travels with **Export JSON / Import**, so family members can pass the project file around. Edits are not live-synced; the latest exported file wins.

## 1.7.3

- Bundled MapLibre GL JS/CSS locally so the map viewer does not depend on loading its library from a third-party CDN.
- Moved the isometric preview into a full-width panel below the plan and editing sidebar.
- Made the template library, selected-object editor, placed-object list, and drawing layers collapsible, preserving panel state while working.

## 1.7.2

- Added panning to the interactive isometric preview using Shift-drag or right-drag, alongside drag-to-orbit and wheel zoom.
- Added a reset-view control and tucked cutaway/auto-rotate switches into a compact preview-options menu.
- Reduced visual clutter in the isometric view by labeling only the selected structure.

## 1.7.1

- Fit and center the complete site plan to the actual map viewport on entry, including narrow panels, without distorting the feet-based scale.
- Keep fit-to-plan and cursor-centered zoom consistent with the responsive viewBox; recalculate the view on window resize.

## 1.7.0

- Set new starter projects to a 1,000-acre conceptual extent while preserving acreage in existing saved projects and imported parcel boundaries.
- Expanded the starter layout with access roads, circular round pens and turnout, feed/tack and general stores, multiple horse-safe fence concepts, native bushes, and a grove.
- Added 14 site-object templates for road types, circular pens, retail/support buildings, fence variants, and shrub planting; refined their map symbols for easier visual distinction.
- Kept dimensions, costs, road alignments, and siting illustrative and editable; they do not represent surveyed or engineered plans.

## 1.6.0

- Added an opt-in OpenStreetMap context overlay for mapped buildings, local roads, wooded/land-use areas, and individually mapped trees.
- Limited lookups to a small viewport at neighborhood zoom; map bounds are sent to the public Overpass API only while the user enables the layer.
- Kept external map references temporary and separate from saved project geometry, with visible OpenStreetMap attribution and coverage caveats.

## 1.5.0

- Added a selectable state terrain viewer using MapLibre GL JS, free USGS topographic/aerial basemaps, and public AWS Terrain Tiles elevation data; no paid API key is required.
- Added persistent georeferenced overlays for house/building footprints, land areas, landmarks, and proposed clearing, with WGS84 side, perimeter, and area measurements.
- Clarified that terrain imagery, elevation, and click-derived overlay measurements are planning references, not a complete real-world inventory, survey, or legal parcel determination.

## 1.4.0

- Replaced illustrative state shapes with bundled U.S. Census Bureau 2024 TIGER/Line cartographic state boundaries, including Albers equal-area contiguous-state geometry and Alaska/Hawaii insets.
- Added an effectively infinite, feet-based planning canvas with visible grid beyond the acreage-derived planning extent, cursor-centered zoom, panning, fit-to-plan, and scale/zoom HUD.
- Added rounded-rectangle and beveled-polygon area formulas, unrestricted-degree footprint rotation, and a curved gravel road whose centerline length informs linear cost.
- Clarified that Census boundaries and conceptual layouts are not survey or navigation sources; parcel-specific acreage and siting checks use imported authoritative geometry.

## 1.3.0

- Added a flat-plan / U.S. location-map toggle with coordinate markers and an imported parcel/site-plan inset.
- Set new starter projects to 300 acres; imported parcel boundaries still determine the acreage.
- Kept the U.S. map illustrative rather than a live basemap; switching views does not modify saved project data.

## 1.2.0

- Added KML and GeoJSON Polygon/MultiPolygon parcel-boundary import, coordinate validation, geodesic acreage calculation, non-rectangular outline rendering, and map-grid clipping.
- Added Google Maps/Zillow reference links and clear source labeling; acreage is tied to imported boundary geometry, and object placement checks against the outline.
- The input file must come from an authoritative assessor/GIS or survey source; pasted listing/map links are references only and are not scraped for parcel data.

## 1.1.0

- Expanded the 2D site designer into a searchable, category-filtered library of 56 site-planning objects, including event centers, exposition and livestock halls, show venues, vendor and food areas, camping, parking, fences, individual trees, groves, orchards, hedges, gardens, and access features.
- Refined the conceptual map with parcel texture, perimeter landscaping, object-specific map details, labels, a compass, and a scale bar.
- Added adjustable 10/20/40/100-foot grid spacing, optional placement snapping, map zoom and pan, grid and label visibility controls, and responsive palette styling.
- Kept new objects additive and optional so existing saved scenarios are preserved; the starter layout remains unchanged.

## 1.0.0

- Built a self-contained, local-first Oregon Estate Planner with 11 planning sections.
- Added an acreage-derived 2D conceptual site map with structure placement, object editing, selection, movement, rotation, undo/redo, scenario-specific layouts, layer visibility, and object-cost controls.
- Added editable conceptual building diagrams and an interactive isometric canvas preview that does not depend on WebGL.
- Connected site quantities and financial assumptions to capital estimates, operating revenue/expenses, breakeven, financing illustration, phase estimates, and a five-year illustrative projection.
- Added infrastructure notes, editable staffing ratios, a categorized due-diligence checklist, scenario comparison, print report, JSON backup/restore, CSV schedule export, and searchable reference manual.
- Added versioned local storage, recovery snapshot, legacy `st3` migration, accessibility labels/focus handling, responsive layout, reduced-motion behavior, and the full planning disclaimer.

- 3D realism: soil slab edge under the land, tree contact shadows, leaf dapple, time-of-day color grade and vignette.

- Creeks & rivers: draw streams, creeks, rivers and canals as natural meandering channels with banks, in 2D and 3D (Water tool).
- Bridges: roads that cross water get bridge decks and rails automatically, in 2D and 3D.
- Real map snippet: capture USGS aerial imagery of your land as an optional underlay in 2D and 3D (hidden until you turn Show on; adjustable opacity).
- Match real features now also brings in real ponds, lakes and reservoirs as editable pond items (the Pond item is already in the palette for drawing your own).
- 3D terrain now turns rocky grey on steep slopes (real grade, not just shading), so hills read more clearly.
- New Lake / Reservoir object at $1.25/sq ft (a 10-acre lake is about $545k, versus $1.7M at the pond rate). Large water bodies imported from the real map become lakes. Fixed a thin seam line in the sunset sky.
- The 3D preview's corner label is now readable at sunset and night, and the lower sky blends darker.
- The 3D ground now has soft light and dark patches so large lots look less flat.
- Real-map matching now retries up to 5 times with growing waits when the public OpenStreetMap servers are busy.
- New projects start as a square 200-acre lot. The 3D preview now shows the lot centred inside a 1,000-acre surrounding area so you can see context.
- Traffic signals now appear in the 3D preview as poles with live red/green lights that follow the simulation.
- Irrigation canals are costed at $55/ft excavated and added to the build cost (ponds were already costed; creeks and rivers are natural, no cost)
- Quick-start guide steps have "Take me there" buttons that jump to the right tab
- 3D preview has a time-of-day sky gradient, sun/moon glow and horizon haze
- New starter projects now default to 200 acres (saved projects keep their acreage)
- Creeks, rivers and canals animate flowing water downstream in the plan and 3D preview (respects reduced motion)
- Real-map snippet is clipped to the imported parcel outline in the plan and 3D preview
- Bridges and culverts where roads cross water are costed and added to the road build cost and project budget
- Traffic simulation has signalised intersections: lights alternate on street/avenue junctions and cars stop on red
- Pick location has one-click presets: Cedarville CA, Christmas Valley OR, Wagontire OR and 15 more small towns across the West and Southwest. Any other town works through search.
- Pick location: search an address, paste a Google Maps link or coordinates, or click the satellite map; one press captures the map and matches real features. OpenStreetMap is now read in three small requests (roads first) and includes roads just outside the land edge.
- Imported buildings, scrub and woods keep their real rotation and footprint size.
- Match real features: copy real roads, houses, other buildings, trees, bushes, scrub and waterways from OpenStreetMap into your plan as editable items.
