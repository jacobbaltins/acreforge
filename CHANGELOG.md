# Changelog

## Unreleased
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
