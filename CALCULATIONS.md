# Calculation reference

All values are user-editable planning assumptions where controls are provided. Outputs are illustrative and are not professional advice or project-specific determinations.

## Property and land allocation

- Without an imported parcel, site area is the manually entered acreage (`acreage × 43,560` square feet), and the displayed rectangular boundary is generated from the entered aspect ratio.
- The rectangular boundary is a planning extent, not a placement fence: without an imported parcel, the site canvas can be panned, zoomed, and extended beyond it. One map unit equals one foot; zooming and panning do not alter object coordinates or measurements.
- With an imported KML or GeoJSON Polygon/MultiPolygon, the displayed outline uses its WGS84 longitude/latitude coordinates, projected into local feet for the site plan. Parcel acreage is calculated from the geodesic polygon area on an authalic-sphere approximation; interior rings are subtracted as holes.
- Imported geometry defines parcel acreage and the placement-check boundary. The grid remains across the viewport; new or moved objects are checked against the imported outline. Keep source survey/assessor data as the authority: input accuracy depends on the imported boundary and its datum/quality, and this lightweight planner is not a survey/GIS or legal parcel determination.
- The U.S. location view uses generalized 2024 U.S. Census TIGER/Line cartographic state boundaries at 1:500,000. The contiguous states use an Albers equal-area projection; Alaska and Hawaii are shown separately. Location markers are plotted only when supported coordinates are available. This overview is not a navigation map or survey. The parcel/site-plan inset retains local feet coordinates and the imported outline.
- The state terrain viewer uses MapLibre GL JS, USGS topographic or aerial imagery, and public AWS Terrain Tiles elevation data without a paid API key. Online map services and the JavaScript library require an internet connection.
- Terrain-map polygon side lengths and perimeter sum haversine distances between the clicked WGS84 vertices, using a mean Earth radius of 6,371,007.1809 m and converting meters to feet. Polygon area uses the app's spherical geodesic area calculation and is converted with 43,560 square feet per acre. Landmark coordinates are shown directly in latitude and longitude.
- Terrain footprint areas are horizontal plan-view areas: elevation and visible relief do not slope-correct the footprint. Results depend on click placement, map scale, imagery/elevation resolution, and the source data; they are planning measurements, not survey-grade dimensions. A displayed parcel overlay comes only from user-imported geometry; the viewer does not derive or verify parcel lines, zoning, restrictions, houses, or trees from imagery or listing pages.
- The optional mapped-context layer queries OpenStreetMap through the public Overpass API for the current small map viewport. It displays mapped building ways, selected road classes, forest/orchard/vineyard land-use ways, wooded ways, and individual tree nodes. The viewport is sent only after the user enables the layer; the data is not saved into the project. OSM coverage is incomplete and can be stale, and mapped features are not proof that a building, road, or tree currently exists. Attribution: © OpenStreetMap contributors, ODbL.
- Rectangles use `width × length`; ellipses use `width × length × π ÷ 4`; triangles use `width × length ÷ 2`.
- Rounded rectangles use `width × length − (4 − π) × radius²`, with `radius = 0.2 × min(width, length)`.
- Angled polygons bevel all four corners by `cut = 0.18 × min(width, length)`; area is `width × length − 2 × cut²`.
- Curved-road cost uses an approximate centerline length: the rendered cubic Bézier curve is sampled at 40 equal parameter intervals and the segment lengths are summed. Its width and length fields describe the road's bounding footprint; the centerline and stroke stay within that footprint.
- Object acreage is object area divided by 43,560.
- Open acreage is total acreage less conceptual building/hardscape area and pasture area, floored at zero. Linear infrastructure is not subtracted as a polygon footprint.

## Capital allowance

- Fixed-price object: entered unit cost per placed object.
- Area-priced object: square feet × entered unit cost per square foot.
- Acre-priced object: object acreage × entered unit cost per acre.
- Linear object: the longer object dimension × entered unit cost per linear foot.
- Site capital allowance: sum of object costs × `(1 + contingency percentage ÷ 100)`.
- Phase estimates use each object's assigned phase and apply contingency proportionally.

The unit costs are starter placeholders. They exclude site-specific construction scope, land, soft costs, fees, escalation, financing, taxes, and other project costs unless a user includes them in an editable allowance.

## Annual operations

- Boarding revenue: occupied stalls × monthly board rate × 12.
- Event revenue: annual events × average event site fee.
- Linked ancillary revenue: $42,000 if a farm stand is placed, $48,000 if an indoor arena is placed, and $30,000 if placed pasture reaches 10 acres. These are illustrative editable-model defaults, not forecasts.
- Gross revenue: boarding + event + ancillary revenue.
- Operating expense: fixed operating expense less the optional $90,000 family-labor planning offset, plus occupied stalls × variable cost per stall, plus events × direct cost per event. Expense is floored at zero.
- NOI: gross revenue less operating expense.
- Stall breakeven: `ceil((fixed expense − offset + event costs − event revenue − ancillary revenue) ÷ (monthly rate × 12 − variable cost per stall))`, bounded by the current model's inputs. If the needed contribution is non-positive, breakeven is zero; if per-stall margin is non-positive, it is not reached.
- Simple payback: site capital allowance ÷ positive annual NOI. It is not shown as meaningful when NOI is zero or negative.
- Financing: standard fixed-rate fully amortizing monthly-payment estimate using entered principal, annual rate, and term. Estimated annual debt service is 12 monthly payments; NOI after debt service subtracts that estimate.
- Five-year illustration: gross revenue and operating expenses each grow at a fixed 3% per year. The illustration has no ramp-up, variable growth controls, taxes, or other forecast adjustments.

## Important model boundaries

The model does not calculate taxes, depreciation, working capital, insurance, replacement reserves, debt covenants, loan eligibility, development charges, property acquisition, or legal/engineering/site constraints. Linked revenue rules are simplified scenario toggles and should not be interpreted as confirmation that an activity is permitted.

## Full disclaimer

This application provides illustrative planning estimates, conceptual layouts, and organizational prompts only. It is not legal, architectural, engineering, environmental, land-use, zoning, building-code, fire-code, employment, tax, lending, construction, insurance, accessibility, or financial advice. Property-specific conditions, costs, designs, approvals, and requirements must be verified with the appropriate county departments, state agencies, licensed professionals, contractors, lenders, insurers, and legal counsel.
