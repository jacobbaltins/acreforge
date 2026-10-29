# AcreForge

A nationwide, local-first planning workspace for rural land, farms, estates, homes, and buildings. It runs in a modern browser with no build step or paid mapping dependency. The MapLibre viewer library is bundled locally so its controls do not depend on a third-party CDN; loading live USGS imagery, AWS elevation tiles, or optional OpenStreetMap references still requires internet access.

## About and first use

The app opens on **About**, which explains the project vision and links directly to the site planner, Home Builder, and project dashboard. U.S. state maps are available; local rules and permitting information are not built in. Use **Project Settings → Appearance** to change the color theme; the choice is saved in the current browser.

**Commercial status:** AcreForge is a working name, not trademark-cleared. The app is a prototype; paid plans, account sign-in, and fundraising are not active.

## Site designer

The conceptual 2D site designer includes a searchable library of 71 site objects across equestrian, fairgrounds, landscape, building, access/parking, and infrastructure categories. The 1,000-acre starter concept includes an access-road layout, circular round pens and turnout, feed/tack and general stores, distinct post-and-rail, board, woven-wire, electric-tape, and no-climb fences, plus native bushes, tree groups, and a grove. Add event centers, livestock halls, stages, vendor rows, camping, parking, orchards, hedges, gardens, and utilities. Work on an effectively infinite, panning canvas with a feet-based grid; use cursor-centered zoom, adjustable grid spacing and snapping, layers, and labels. Select, move, rotate, resize, duplicate, or delete objects; footprints support rectangles, rounded rectangles, ellipses, triangles, and angled polygons, and roads include straight and curved options. The isometric massing preview supports drag-to-orbit, Shift-drag or right-drag to pan, and wheel zoom; use Reset view to recenter it. Its roads follow straight and curved layouts with distinct road/path surfaces and markings; building previews now include shaded facades, windows, doors, and pitched roofs, while rotations and terrain relief are reflected in the model. Only the selected structure is labeled in the preview to reduce clutter, and secondary options are tucked into a compact menu. The template library, selected-object editor, placed-object list, and drawing-layer controls are collapsible; their open/closed state is kept while you work.

Map scale is 1 map unit = 1 foot. The plan automatically fits and centers the full property extent to the map viewport, including narrow screens, without changing scale; use Fit plan to return after panning or zooming. The 1,000-acre starter extent is a planning reference, not a limit on the infinite canvas or a property boundary. For parcel-based acreage and siting checks, import a single-boundary WGS84 KML or GeoJSON Polygon/MultiPolygon from a county assessor/GIS or survey source. The imported outline sets acreage and checks new or moved object footprints; the planning grid remains visible across the canvas. Acreage is calculated geodesically from the supplied outline, including holes. Paste a Google Maps or Zillow URL as a reference link; the app does not scrape those services or derive parcel lines from their pages. A reference URL is not a substitute for an authoritative boundary file.

Switch between the editable flat site plan, a U.S. state map, and a state terrain viewer. State outlines come from the U.S. Census Bureau 2024 TIGER/Line cartographic boundary dataset (1:500,000), projected in Albers equal-area, with Alaska and Hawaii shown separately. The state viewer uses MapLibre GL JS, USGS topographic or aerial imagery, and public AWS Terrain Tiles elevation data. These services and libraries do not require a paid API key; an internet connection is needed to load them.

State terrain opens in USGS aerial imagery by default; use **Topo map** to switch to USGS topographic maps. At neighborhood zoom, enable **Mapped features** to request OpenStreetMap home/building footprints and other context. Building footprints render as raised 3D blocks at city scale. OSM heights are used when available; otherwise the illustration estimates a height from floor count or a generic building type. These are visual context, not actual building dimensions.

On a state terrain map, select a drawing mode to add house/building footprints, land areas, landmarks, or proposed clearing polygons. The app saves these overlays with the project and reports horizontal WGS84 perimeter, area, and polygon-side measurements. Imported parcel geometry can be displayed as a reference, but parcel lines are not fetched from Zillow or inferred from imagery. Use an assessor/GIS or survey KML/GeoJSON file for parcel geometry. Census state boundaries, imagery, and elevation are generalized planning references, not navigation, survey, or legal property data. Satellite/topographic imagery is not a complete tree or building inventory; add planning overlays manually and verify locations from authoritative sources.

The **Mapped features** control can optionally request nearby OpenStreetMap homes, other buildings, roads, fields/orchards, woods/brush, and individually mapped trees. It sends the visible map bounds to the public Overpass API only after you enable it, and only at neighborhood zoom. Use **Reference layers** to hide categories, click a mapped feature to see its available name/category, or **Clear reference context** to remove temporary downloaded references. Clearing does not change map imagery, the saved parcel boundary, or project overlays. Reference data is temporary and is not saved with the project; coverage varies and may be missing or out of date. OpenStreetMap data is © OpenStreetMap contributors (ODbL); an internet connection is required. **Proposed clearing** is only a saved planning annotation; it does not alter satellite imagery or real-world vegetation.

The map can show coordinates parsed from a Google Maps link or the center of an imported parcel, along with an inset of the parcel and its site objects. Switching views does not change saved project data. New starter projects default to 200 acres (1,000 is the maximum); existing saved project acreage is preserved and can be edited in Project Settings until an imported parcel boundary sets it from the source geometry.

The designer is for early planning only: its rectangular planning extent is acreage-derived, not surveyed parcel geometry. Object dimensions and cost assumptions are illustrative and do not establish feasibility, permits, or approvals.

The isometric preview uses procedural 3D geometry for shaded buildings, circle/ellipse/triangle footprints, trees, clustered bushes, hedges, and post/rail, board, electric, and mesh fences. Select **Free rotate** and drag an object around its center, or use the object editor’s 0–359° slider/number field; no extra model or asset download is required.

Pastures and crop fields are **land zones** (Land zones card), not placeable objects: draw, move, recolor, resize, reshape, and rotate them. The **Ground surface** card sets the base biome (temperate, eastern Oregon, desert, short grass, tall grass) and lets you paint or erase local ground cover (short/tall grass, sagebrush, desert, soil); paint is saved per scenario, supports undo/redo, and can be hidden with the "Ground cover" layer. Ground colors are illustrative, not a soil or habitat survey. All code is original to AcreForge; Map3D, VoxCity and 3D City Database were reviewed only as inspiration.

## Roads, water, traffic and real-map snippet

- **Roads:** the Roads tool draws dirt, gravel, paved, street, avenue and trail segments (straight or curved, one-way optional) with per-foot build costs that feed the project budget. Roads that cross creeks or rivers get bridges, or culverts for short crossings on dirt/gravel roads; their estimated cost is included.
- **Traffic simulation:** press **Simulate traffic** to run cars and pedestrians on the network, with signal lights at street/avenue junctions, a congestion heat map, and stats for trips, stalled cars and buildings not served by a road.
- **Creeks & rivers:** the Water tool draws streams, creeks, rivers and canals with natural meanders. Flow is animated (disabled when your system prefers reduced motion). Ponds and lakes are placeable items.
- **Real map snippet:** **Pick location** lets you search an address, paste a Google Maps link or `lat, lon`, click the map, or use one of the preset small-town locations. **Re-capture** fetches USGS aerial imagery for your land (clipped to an imported parcel outline); it is hidden until you turn Show on. **Match real features** imports nearby OpenStreetMap roads, waterways, ponds, houses, other buildings, trees and bushes as editable items. It needs internet access, public Overpass servers can be busy (press Match again), and results are planning references, not survey data. OpenStreetMap data is © OpenStreetMap contributors (ODbL); imagery is from USGS The National Map.

## Building & Lot Builder
Open **Building & Lot Builder** in the sidebar. Pick a starter (3-bed home, horse barn, shop/garage, retail, full lot) and a drawing area (72–600 ft). Browse 12 library folders (rooms, kitchen, bath, garage/shop, barn, commercial, lot items). With the Move tool, click a room or item to edit its size, position, rotation, type and height, or duplicate/delete it. Keys: 1 Move, 2 Room, 3 Wall, 4 Door, 5 Window, 6 Erase, R rotate, Delete remove, Ctrl+Z undo. Toggle 3D to spin the model; **Place on site plan** drops it on the property. Export a letter-landscape **Print-ready PDF** with floor labels, room areas and dimensions, or export a layered DXF with room labels for CAD.

## Run locally

For the most reliable local run, extract the ZIP and serve the complete folder with any static file server. In PowerShell, from that folder:

```powershell
npx serve .
```

## Deploy to GitHub Pages

Live site: https://jacobbaltins.github.io/acreforge/

1. Push these files to the `main` branch of the repository root.
2. In Settings > Pages, serve from `main` and `/`. No build step is needed (`.nojekyll` is included).

GitHub Pages is static only, so there are no server functions.

## Contents

- `index.html` — application.
- `vendor/` — pinned MapLibre GL JS/CSS files and upstream license notice.
- `us-states.js` — bundled U.S. Census state-boundary paths required by the location map.
- `CALCULATIONS.md` — formulas, model boundaries, and planning assumptions.
- `CHANGELOG.md` — implementation notes.
- `support.html` — prototype and payment status.
- `data-notice.html` — factual prototype data-use and privacy notice.
- `CAMPAIGN.md` — unpublished fundraising planning draft.
- `acreforge.zip` — deployable archive of the above files (excluding itself); regenerate it after changing the app or documentation.

## Data and privacy

Project data autosaves to this browser's local storage and is not cloud-synced by the app. The terrain map requests USGS imagery and AWS elevation tiles; the optional OpenStreetMap feature lookup sends the visible map bounds only after the user enables it. Public project export is intended to publish its JSON file alongside the site, so review it for sensitive information first. The [prototype data and privacy notice](data-notice.html) describes these flows and the unverified status of any server-side Stripe webhook configuration. It is not a complete commercial privacy policy.

The app can read the legacy `st3` site-planner local-storage data and migrate its site objects and financial assumptions on first launch.

## Limits

The site map is an acreage-derived rectangular planning boundary, not a survey, GIS parcel, or legal property boundary. Terrain overlays are measured from map clicks and their accuracy is limited by map resolution and source data; they are not survey-grade. Terrain relief does not convert horizontal footprint measurements into slope-adjusted surface area. The imagery may not show every building or tree. The isometric view is a WebGL-free conceptual massing illustration. Cost, revenue, staffing, and regulatory prompts are illustrative only. No output establishes property-specific feasibility, compliance, approval, financing, or professional design.

See `CALCULATIONS.md` and the in-app Project Settings for the full disclaimer and formulas.

## Sharing with family

Each browser keeps its own copy. To share: click **Export**, send the dated .json file, and the other person clicks **Import**. Import shows both save times and warns if the file is older. The newest exported file wins, so agree on who edits at a time.

## Terrain and themes

Use **Terrain** in the Site Designer to sculpt elevation (shown in the isometric view). Change the color theme in **Project Settings → Appearance**.


## Publishing publicly
1. Click **Public export** (edit mode) and save published-project.json next to index.html.
2. Commit and push the folder contents to GitHub Pages.
3. Visitors see a view-only copy; open your-site/?edit=1 once on your own browser to edit. This is a convenience link, not security. Anyone who knows it can edit their own copy, but nobody can change the published one.


## Accounts and payments

Paid plans, account sign-in, and payment processing are currently disabled. Do not add payment URLs, account credentials, customer email allowlists, or secret keys to `index.html`: browser code is public, and local license flags are not secure access control. Before accepting payments, implement and test server-side checkout/entitlements, cancellation and refund handling, customer support, and truthful pricing disclosures; have the resulting flow and legal terms reviewed for the jurisdictions where you sell.
