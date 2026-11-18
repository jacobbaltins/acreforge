"""AcreForge smoke test. Run: python tests/smoke.py  (serves the repo on :8766)"""
import subprocess, sys, time, os, struct, zlib, json, re, math, csv, io, base64
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
srv = subprocess.Popen([sys.executable, "-m", "http.server", "8766"], cwd=root,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
fails, errors = [], []

def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        fails.append(name)

def start_analysis(page):
    page.evaluate("""() => {
      const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
      window.__originalImageSrc = descriptor;
      Object.defineProperty(HTMLImageElement.prototype, 'src', {
        ...descriptor,
        set(value) { descriptor.set.call(this, value + '?health-test=' + Date.now()); }
      });
    }""")
    try:
        page.locator('[data-pl="pz"]').click()
        page.wait_for_function(
            "() => !document.querySelector('#pzOut')?.textContent.includes('Reading terrain and public land data')",
            timeout=60000)
        page.wait_for_timeout(400)
    finally:
        page.evaluate("""() => {
          if (window.__originalImageSrc) {
            Object.defineProperty(HTMLImageElement.prototype, 'src', window.__originalImageSrc);
            delete window.__originalImageSrc;
          }
        }""")

def geodesic_feet(a, b):
    radius = 6371007.1809
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h)) * 3.280839895

def terrarium_png(no_data=False, partial_no_data=False, partial_import=False,
                  slope_profile=False, steep_profile=False):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    rows = bytearray()
    for y in range(256):
        rows.append(0)
        for x in range(256):
            if steep_profile:
                value = 32768 + 100 + x * 3 + y * 0.01
            elif slope_profile:
                whole_band = x // 85
                remainder = x % 85
                gradients = [0.02, 0.20, 0.55]
                value = 32768 + 100 + sum(85 * gradient for gradient in gradients[:whole_band])
                value += remainder * gradients[min(whole_band, 2)] + y * 0.01
            else:
                value = 32768 + 100 + (x + y) * 0.12
            whole = int(value)
            rows.extend((whole // 256, whole % 256, int((value - whole) * 256),
                         0 if no_data or partial_no_data and x < 20
                         or partial_import and x < 128 else 255))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(service_workers="block")
        page = ctx.new_page()
        page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        page.on("pageerror", lambda e: errors.append(str(e)))
        dem = terrarium_png()
        no_data_dem = terrarium_png(no_data=True)
        partial_no_data_dem = terrarium_png(partial_no_data=True)
        partial_import_dem = terrarium_png(partial_import=True)
        mixed_slope_dem = terrarium_png(slope_profile=True)
        steep_dem = terrarium_png(steep_profile=True)
        terrain_mode = {"case": "mapped", "calls": 0}
        def mock_terrain_tile(route):
            terrain_mode["calls"] += 1
            if terrain_mode["case"] == "failure":
                route.fulfill(status=503, body="Elevation unavailable",
                              content_type="image/png",
                              headers={"Access-Control-Allow-Origin": "*",
                                       "Cache-Control": "no-store"})
                return
            if terrain_mode["case"] == "partial-no-data":
                body = partial_no_data_dem
            elif terrain_mode["case"] == "partial-import":
                body = partial_import_dem
            elif terrain_mode["case"] == "mixed-slope":
                body = mixed_slope_dem
            elif terrain_mode["case"] == "all-steep":
                body = steep_dem
            else:
                body = no_data_dem if terrain_mode["case"] == "no-data" else dem
            route.fulfill(status=200,
                          body=body,
                          content_type="image/png",
                          headers={"Access-Control-Allow-Origin": "*",
                                   "Cache-Control": "no-store"})
        page.route("https://s3.amazonaws.com/elevation-tiles-prod/terrarium/**",
                   mock_terrain_tile)
        land_requests = {"fema": 0, "soil": 0, "epqs": 0}
        land_mode = {"fema_case": "partial-high", "soil_case": "mapped", "delay": False}
        elevation_mode = {"case": "mapped"}
        road_mode = {"case": "mapped", "calls": 0, "center": [-123, 44]}
        building_mode = {"case": "mapped"}
        def delay_land_response():
            if land_mode["delay"]:
                time.sleep(0.08)
        def mock_fema(route):
            delay_land_response()
            land_requests["fema"] += 1
            if land_mode["fema_case"] == "failure":
                route.fulfill(status=503, json={"error": "temporarily unavailable"})
                return
            query = parse_qs(urlparse(route.request.url).query)
            lon, lat = map(float, query["geometry"][0].split(","))
            features = []
            if land_mode["fema_case"] == "all-high":
                features = [{"attributes": {"FLD_ZONE": "A", "ZONE_SUBTY": "1% annual chance", "SFHA_T": "T"}}]
            elif land_mode["fema_case"] == "all-low":
                features = [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "Minimal hazard", "SFHA_T": "F"}}]
            elif land_mode["fema_case"] == "partial-high" and abs(lon + 123) < 0.0001 and abs(lat - 44) < 0.0001:
                features = [{"attributes": {"FLD_ZONE": "A", "ZONE_SUBTY": "1% annual chance", "SFHA_T": "T"}}]
            elif land_mode["fema_case"] == "partial-low" and abs(lon + 123) < 0.0001 and abs(lat - 44) < 0.0001:
                features = [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "Minimal hazard", "SFHA_T": "F"}}]
            route.fulfill(json={"features": features})
        def mock_soil(route):
            delay_land_response()
            land_requests["soil"] += 1
            if land_mode["soil_case"] == "failure":
                route.fulfill(status=503, json={"error": "temporarily unavailable"})
                return
            query = json.loads(route.request.post_data)["query"]
            match = re.search(r"point\((-?[\d.]+)\s+(-?[\d.]+)\)", query)
            if not match:
                route.fulfill(status=400, json={"Message": "Missing sample point"})
                return
            lon = float(match.group(1))
            row = ["Clay loam", "Poorly drained", "D"] if lon > -123 else ["Sandy loam", "Well drained", "A"]
            route.fulfill(json={"Table": [row]})
        def mock_epqs(route):
            delay_land_response()
            land_requests["epqs"] += 1
            query = parse_qs(urlparse(route.request.url).query)
            lon, lat = float(query["x"][0]), float(query["y"][0])
            if elevation_mode["case"] == "partial-failure" and lat > 44:
                route.fulfill(status=503, json={"error": "temporarily unavailable"})
                return
            value = "No Data" if elevation_mode["case"] == "unmapped" else str(
                1000 + round((lat - 43.99) * 10000) + round((lon + 123) * 5000))
            route.fulfill(json={"value": value})
        page.route("https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query**", mock_fema)
        page.route("https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest", mock_soil)
        page.route("https://epqs.nationalmap.gov/v1/json**", mock_epqs)
        def mock_roads(route):
            road_mode["calls"] += 1
            query = parse_qs(route.request.post_data).get("data", [""])[0]
            road_mode["query"] = query
            if 'way["building"]' in query:
                if building_mode["case"] == "failure":
                    route.fulfill(status=503, json={"error": "temporarily unavailable"})
                    return
                if building_mode["case"] == "empty":
                    route.fulfill(json={"elements": []})
                    return
                lon, lat = road_mode["center"]
                def building(osm_id, tags, points=None):
                    element = {"type": "way", "id": osm_id, "tags": tags}
                    if points is not None:
                        element["geometry"] = [{"lon": x, "lat": y} for x, y in points]
                    return element
                square = [[lon - .00005, lat - .00005], [lon + .00005, lat - .00005],
                          [lon + .00005, lat + .00005], [lon - .00005, lat + .00005],
                          [lon - .00005, lat - .00005]]
                route.fulfill(json={"elements": [
                    building(11, {"name": "Farmhouse", "height": "8.5", "building": "house"}, square),
                    building(12, {"building": "warehouse", "building:levels": "2"},
                             [[x + .0002, y] for x, y in square]),
                    building(13, {"building": "barn"}),
                    building(14, {"building": "shed"},
                             [[x + .0004, y] for x, y in square[:-1]]),
                ]})
                return
            if road_mode["case"] == "failure":
                route.fulfill(status=503, json={"error": "temporarily unavailable"})
                return
            if road_mode["case"] == "empty":
                route.fulfill(json={"elements": []})
                return
            lon, lat = road_mode["center"]
            def way(osm_id, highway, points, name=None, service=None):
                tags = {"highway": highway}
                if name:
                    tags["name"] = name
                if service:
                    tags["service"] = service
                return {"type": "way", "id": osm_id, "tags": tags,
                        "geometry": [{"lon": x, "lat": y} for x, y in points]}
            route.fulfill(json={"elements": [
                way(1, "primary", [[lon - .001, lat], [lon + .001, lat]], "Oak Road"),
                way(2, "secondary", [[lon, lat - .001], [lon, lat + .001]]),
                way(3, "residential", [[lon - .001, lat - .001], [lon + .001, lat - .001]]),
                way(4, "service", [[lon - .001, lat + .001], [lon + .001, lat + .001]],
                    service="driveway"),
                way(5, "track", [[lon - .001, lat], [lon, lat + .001]]),
            ]})
        page.route("https://overpass-api.de/api/interpreter", mock_roads)
        def mock_geocoder(route):
            query = parse_qs(urlparse(route.request.url).query).get("q", [""])[0]
            if query == "Network Error":
                route.fulfill(status=503, json={"error": "temporarily unavailable"})
                return
            if query == "Known Test Address":
                route.fulfill(json=[{"lat": "44.25", "lon": "-123.25",
                                     "display_name": "Known Test Address, Oregon"}])
            else:
                route.fulfill(json=[])
        page.route("https://nominatim.openstreetmap.org/search**", mock_geocoder)
        page.goto("http://localhost:8766/index.html?spatial-test=1")
        page.wait_for_timeout(800)
        projection = page.evaluate("""() => {
          const spatial = window.__acreforgeSpatialTest;
          const origin = [179.999, 44];
          const point = [-179.999, 44.0004];
          const local = spatial.geoToLocalFeet(point, origin);
          const roundTrip = spatial.localFeetToGeo(local, origin);
          const invalidRejected = (() => {
            try { spatial.geoToLocalFeet([181, 44], origin); return false; }
            catch { return true; }
          })();
          const dims = {w: 800, h: 600};
          const locationAnchor = spatial.geoPlanAnchorFor(dims, null, [-123, 44]);
          const locationPoint = [-122.999, 44.0005];
          const locationRoundTrip = spatial.planPointToGeo(
            locationAnchor,
            ...spatial.geoToPlanPoint(locationAnchor, locationPoint));
          const boundary = spatial.normalizeParcelBoundary({source: 'projection fixture', coordinates: [[[
            [-123.01, 43.99], [-122.99, 43.99], [-122.99, 44.01],
            [-123.01, 44.01], [-123.01, 43.99]
          ]]]});
          const parcelAnchor = spatial.geoPlanAnchorFor(dims, boundary, boundary.center);
          const sourceCorner = boundary.coordinates[0][0][0];
          const projectedCorner = spatial.geoToPlanPoint(parcelAnchor, sourceCorner);
          const dateLineBoundary = spatial.normalizeParcelBoundary({source: 'antimeridian fixture',
            coordinates: [[[[179.99, 43.99], [-179.99, 43.99], [-179.99, 44.01],
              [179.99, 44.01], [179.99, 43.99]]]]});
          const legacyBoundary = spatial.normalizeParcelBoundary({source: 'legacy fixture',
            coordinates: [[[
              [-123.01, 43.99], [-122.99, 43.99], [-122.99, 44.01],
              [-123.01, 44.01], [-123.01, 43.99]
            ]]]});
          const legacy = spatial.migrateParcelPlanCoordinates({
            project: {parcelBoundary: legacyBoundary, terrain: {cols: 2, rows: 2, h: [1, 2, 3, 4]}},
            scenarios: [{items: [{y: 100, h: 50, rotation: 90}],
              fields: [{y: 200, h: 30}], roads: [{pts: [[1, 20], [2, 50]]}],
              waters: [], surfacePatches: [{y: 20}]}]
          });
          return {
            roundTrip, expected: point, local,
            locationRoundTrip, locationExpected: locationPoint,
            parcelCornerError: Math.hypot(
              projectedCorner[0] - boundary.polygons[0][0][0][0],
              projectedCorner[1] - boundary.polygons[0][0][0][1]),
            dateLineWidth: dateLineBoundary.width,
            legacy: {
              height: legacy.project.parcelBoundary.height,
              itemY: legacy.scenarios[0].items[0].y,
              rotation: legacy.scenarios[0].items[0].rotation,
              fieldY: legacy.scenarios[0].fields[0].y,
              roadY: legacy.scenarios[0].roads[0].pts[0][1],
              patchY: legacy.scenarios[0].surfacePatches[0].y,
              terrain: legacy.project.terrain.h,
              markerRemoved: !legacy.project.parcelBoundary._migratePlanCoordinates
            },
            invalidRejected
          };
        }""")
        check("shared WGS84 projection round-trips antimeridian and selected-location points",
              geodesic_feet(projection["roundTrip"], projection["expected"]) < 1
              and geodesic_feet(projection["locationRoundTrip"],
                                projection["locationExpected"]) < 1)
        check("parcel corners use the shared local-feet plan transform",
              projection["parcelCornerError"] < 1e-6 and projection["invalidRejected"])
        check("antimeridian parcel extents stay local and legacy plan coordinates migrate once",
              4000 < projection["dateLineWidth"] < 10000
              and projection["legacy"]["itemY"] == projection["legacy"]["height"] - 150
              and projection["legacy"]["rotation"] == 270
              and projection["legacy"]["fieldY"] == projection["legacy"]["height"] - 230
              and projection["legacy"]["roadY"] == projection["legacy"]["height"] - 20
              and projection["legacy"]["patchY"] == projection["legacy"]["height"] - 20
              and projection["legacy"]["terrain"] == [3, 4, 1, 2]
              and projection["legacy"]["markerRemoved"])
        labels = page.locator("#nav button span:not(.ico)").all_text_contents()
        check("exactly six primary navigation labels including CAD Studio",
              labels == ["Projects", "Property", "Design", "CAD Studio", "Reports", "Settings"])
        check("Projects dashboard opens by default",
              page.locator("#nav [data-page=dashboard]").get_attribute("aria-current") == "page")
        check("desktop dashboard leads with a non-editable concept map",
              page.locator(".command-map-preview #siteMap").count() == 1
              and page.locator(".command-map-preview").evaluate("(el) => el.inert")
              and page.locator(".command-map-preview").evaluate("(el) => el.getBoundingClientRect().height >= 320")
              and page.locator(".command-center-grid").evaluate("(el) => getComputedStyle(el).gridTemplateColumns.split(' ').length == 2"))
        for nav, destinations in [
                ("dashboard", ["dashboard", "scenarios", "operations", "about"]),
                ("planner", ["planner"]),
                ("designer", ["designer", "buildings", "homes", "infrastructure"]),
                ("reports", ["reports", "financials", "compliance", "manual"]),
                ("settings", ["settings"])]:
            page.locator(f"#nav [data-page={nav}]").click()
            for dest in destinations:
                if dest != nav:
                    page.locator(f"#content .tabbar [data-page={dest}]").click()
                page.wait_for_timeout(100)
                check("reachable screen " + dest,
                      page.locator("#content").inner_text().strip() != "")
        page.locator("#nav [data-page=dashboard]").click()
        page.locator("#content .tabbar [data-page=about]").click()
        about_copy = page.locator("#content").inner_text()
        check("About states all available features are free without promoting a paid tier",
              "FREE UNTIL FURTHER NOTICE" in about_copy
              and "AcreForge is free to use" in about_copy
              and "external model providers may charge separately" in about_copy
              and "AcreForge Pro" not in about_copy
              and page.locator("[data-pro-hypothesis]").count() == 0
              and "free until further notice" in page.locator(".pubbar").inner_text().lower())
        page.locator("#content [data-page=feedback]").click()
        check("About links directly to the user-controlled feedback route",
              page.locator("[data-feedback-form]").count() == 1
              and page.locator("[data-feedback-email]").get_attribute("href").startswith("mailto:?"))
        page.locator("#nav [data-page=dashboard]").click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(150)
        check("mobile dashboard stacks the map and snapshot",
              page.locator(".command-center-grid").evaluate("(el) => getComputedStyle(el).gridTemplateColumns.split(' ').length == 1")
              and page.locator(".command-map-preview #siteMap").is_visible()
              and page.locator("#nav button span:not(.ico)").all_text_contents()
              == ["Projects", "Property", "Design", "CAD Studio", "Reports", "Settings"])
        page.set_viewport_size({"width": 1280, "height": 800})
        feedback_requests = []
        page.on("request", lambda request: feedback_requests.append(request.url)
                if not request.url.startswith(("http://localhost:8766", "http://127.0.0.1:8766")) else None)
        page.click("#nav [data-page=settings]")
        page.locator("#content .tabbar [data-page=feedback]").click()
        check("feedback route is reachable from Settings and starts with a neutral improvement choice",
              page.locator("[data-feedback-form]").count() == 1
              and page.locator("#feedbackInterest").input_value() == ""
              and "future improvements" in page.locator("label[for=feedbackInterest]").inner_text()
              and "planned pro" not in page.locator("[data-feedback-route]").inner_text().lower()
              and page.locator("[data-feedback-preview]").inner_text().startswith("AcreForge product interest and feedback"))
        page.locator(".pubbar [data-action='page:feedback']").click()
        check("status-bar feedback control opens the user-controlled route and replaces public issue submission",
              page.locator("[data-feedback-form]").count() == 1
              and page.locator(".pubbar a[href*='github.com']").count() == 0
              and "github.com" not in page.locator(".pubbar").inner_text().lower())
        page.locator("#feedbackInterest").select_option(label="Maybe")
        page.locator("[name=usecase][value='Enhanced reports']").check()
        feedback_note = "GENERAL_FEEDBACK_CANARY_7b93"
        page.locator("#feedbackNote").fill(feedback_note)
        mail_href = page.locator("[data-feedback-email]").get_attribute("href")
        mail_fields = parse_qs(urlparse(mail_href).query)
        mail_body = mail_fields.get("body", [""])[0]
        check("feedback email draft has a blank recipient and includes only selected basic answers",
              urlparse(mail_href).scheme == "mailto" and urlparse(mail_href).path == ""
              and mail_fields.get("subject") == ["AcreForge product interest and feedback"]
              and "Interest in future improvements: Maybe" in mail_body
              and "Enhanced reports" in mail_body and feedback_note in mail_body
              and "Project:" not in mail_body and "Coordinates:" not in mail_body)
        saved_user = page.evaluate("() => localStorage.getItem('oregon-estate-planner-v1') || ''")
        saved_sample = page.evaluate("() => localStorage.getItem('oregon-estate-planner-sample-v1') || ''")
        check("feedback answers are not persisted in the user project or separate sample storage",
              feedback_note not in saved_user and feedback_note not in saved_sample)
        page.evaluate("""() => Object.defineProperty(navigator, 'clipboard', {configurable:true,
          value:{writeText:async text => {window.__copiedFeedback=text}}})""")
        page.locator("[data-action=feedback-copy]").click()
        page.wait_for_function("() => document.querySelector('[data-feedback-status]').textContent.includes('copied')")
        check("copy fallback copies the same local-only draft and gives an explicit status",
              page.evaluate("() => window.__copiedFeedback") == mail_body
              and "send it only if you choose" in page.locator("[data-feedback-status]").inner_text())
        page.wait_for_timeout(250)
        check("feedback form and copy action issue no network requests",
              feedback_requests == [])
        page.click("#nav [data-page=planner]")
        check("planner renders property search after switching from feedback",
              page.locator("#propertySearchQuery").count() == 1)
        search_started = time.perf_counter()
        page.fill("#propertySearchQuery", "44, -123")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function(
            "() => { const raw = localStorage['oregon-estate-planner-v1']; return !!raw && JSON.parse(raw).project.locationCoordinates?.lat === 44; }",
            timeout=3000)
        check("coordinate search selects a property in under 10 seconds",
              time.perf_counter() - search_started < 10)
        search_started = time.perf_counter()
        page.fill("#propertySearchQuery", "Known Test Address")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function(
            "() => { const raw = localStorage['oregon-estate-planner-v1']; return !!raw && JSON.parse(raw).project.locationLabel === 'Known Test Address, Oregon'; }",
            timeout=3000)
        check("address search selects geocoded coordinates",
              page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).project.locationCoordinates.lon") == -123.25
              and time.perf_counter() - search_started < 10)
        page.fill("#propertySearchQuery", "https://www.google.com/maps/@44.1,-123.1,14z")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function(
            "() => { const raw = localStorage['oregon-estate-planner-v1']; return !!raw && JSON.parse(raw).project.locationCoordinates?.lat === 44.1; }")
        check("Google Maps coordinate links select their embedded location",
              page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).project.locationCoordinates.lon") == -123.1)
        page.fill("#propertySearchQuery", "Unknown Test Address")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function("() => document.querySelector('#propertySearchStatus').textContent.includes('Address not found')")
        page.fill("#propertySearchQuery", "Network Error")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function("() => document.querySelector('#propertySearchStatus').textContent.includes('HTTP 503')")
        check("failed search preserves previous property selection",
              page.evaluate("""() => {
                const p = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
                return p.locationCoordinates.lat === 44.1 && p.locationCoordinates.lon === -123.1;
              }"""))
        page.wait_for_function("() => !document.querySelector('[data-property-recent=\"2\"]').disabled")
        page.locator('[data-property-recent="2"]').click()
        page.wait_for_function(
            "() => { const raw = localStorage['oregon-estate-planner-v1']; return !!raw && JSON.parse(raw).project.locationCoordinates?.lon === -123; }")
        check("recent search restores a saved coordinate selection",
              page.evaluate("""() => {
                const p = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
                return p.locationCoordinates.lat === 44 && p.locationCoordinates.lon === -123;
              }"""))
        page.locator("#nav [data-page=planner]").click()
        page.wait_for_selector("#propertySearchCard")
        check("recent searches persist after reload",
              page.locator("#propertySearchCard [data-property-recent]").count() == 3)
        page.locator("[data-property-map-pick]").click()
        page.wait_for_selector("#snPickMapEl canvas")
        page.wait_for_timeout(500)
        map_box = page.locator("#snPickMapEl canvas").bounding_box()
        page.mouse.click(map_box["x"] + map_box["width"] * .6,
                         map_box["y"] + map_box["height"] * .6)
        page.wait_for_function("() => !document.querySelector('#snPickUse').disabled")
        page.locator("#snPickUse").click()
        page.wait_for_function(
            "() => { const raw = localStorage['oregon-estate-planner-v1']; return !!raw && JSON.parse(raw).project.recentSearches?.[0]?.source === 'Map pin'; }")
        check("map pin drop selects and remembers the chosen point",
              page.locator("#snPickBox").count() == 0
              and page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).project.recentSearches.length") <= 8)
        road_mode["center"] = page.evaluate("""() => {
          const c = JSON.parse(localStorage['oregon-estate-planner-v1']).project.locationCoordinates;
          return [c.lon, c.lat];
        }""")
        page.wait_for_selector("#propertyRoadPanel")
        check("road references are not requested before user action",
              road_mode["calls"] == 0 and page.locator("[data-property-roads-load]").is_enabled())
        proposed_before_roads = page.evaluate(
            "() => JSON.stringify(JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios)")
        page.locator("[data-property-roads-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyRoadStatus').textContent.includes('Loaded 5 mapped road features')")
        check("bounded OpenStreetMap query loads attributed roads by hierarchy",
              road_mode["calls"] == 1 and "out tags geom 2000" in road_mode["query"]
              and page.locator("#propertyRoadPanel [data-road-kind=arterial]").count() == 1
              and page.locator("#propertyRoadPanel [data-road-kind=collector]").count() == 1
              and page.locator("#propertyRoadPanel [data-road-kind=local]").count() == 1
              and page.locator("#propertyRoadPanel [data-road-kind=driveway]").count() == 1
              and page.locator("#propertyRoadPanel [data-road-kind=track]").count() == 1
              and "© OpenStreetMap contributors" in page.locator("#propertyRoadPanel").inner_text())
        check("mapped road names are labeled only when supplied",
              page.locator('#propertyRoadPanel svg text').evaluate("(el) => el.textContent") == "Oak Road"
              and page.locator('#propertyRoadPanel [data-mapped-road="residential"] title')
              .all_text_contents()[0].startswith("residential · OpenStreetMap reference"))
        page.locator('[data-property-road-layer="driveways"]').uncheck()
        check("driveway visibility toggle hides only mapped driveway references",
              page.locator("#propertyRoadPanel [data-road-kind=driveway]").count() == 0
              and page.locator("#propertyRoadPanel [data-road-kind=arterial]").count() == 1)
        page.locator('[data-property-road-layer="driveways"]').check()
        check("mapped roads remain separate from saved proposed layouts",
              page.evaluate("() => JSON.stringify(JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios)")
              == proposed_before_roads
              and "Mapped road references" not in page.evaluate(
                  "() => localStorage['oregon-estate-planner-v1']"))
        page.fill("#propertySearchQuery", "44.2, -123.2")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).project.locationCoordinates?.lat === 44.2")
        check("changing selected property clears stale road references",
              page.locator("#propertyRoadPanel [data-mapped-road]").count() == 0
              and "cleared" in page.locator("#propertyRoadStatus").inner_text())
        road_mode["center"] = [-123.2, 44.2]
        road_mode["case"] = "empty"
        page.locator("[data-property-roads-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyRoadStatus').textContent.includes('No road features were returned')")
        check("empty road coverage is not presented as proof of no roads",
              "does not establish that roads are absent" in page.locator("#propertyRoadStatus").inner_text()
              and page.locator("#propertyRoadPanel [data-mapped-road]").count() == 0)
        road_mode["case"] = "failure"
        page.locator("[data-property-roads-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyRoadStatus').textContent.includes('lookup failed (HTTP 503)')")
        check("road-service failures are visible and retryable",
              page.locator("[data-property-roads-load]").is_enabled()
              and "HTTP 503" in page.locator("#propertyRoadStatus").inner_text())
        proposed_before_buildings = page.evaluate("""() => {
          const project = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
          return JSON.stringify({scenarios: JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios,
            mapFeatures: project.mapFeatures || []});
        }""")
        page.locator("[data-property-buildings-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyBuildingStatus').textContent.includes('Loaded 2 mapped building footprints')")
        check("building lookup is user-triggered and rejects missing or open footprint geometry",
              'way["building"]' in road_mode["query"]
              and "out tags geom 400" in road_mode["query"]
              and page.locator("#propertyBuildingPanel [data-mapped-building]").count() == 2
              and page.locator("#propertyBuildingPanel").inner_text().count("sq ft footprint") == 2)
        farmhouse_area = int(page.locator('[data-mapped-building="osm-way-11"] [data-footprint-area-sqft]')
                             .get_attribute("data-footprint-area-sqft"))
        check("building footprint area is calculated from mapped polygon geometry",
              farmhouse_area > 0
              and f"{farmhouse_area:,} sq ft" in page.locator(".property-building-detail").inner_text())
        check("tagged and illustrative heights are explicitly distinguished",
              "OpenStreetMap tagged height: 8.5 m" in page.locator(".property-building-detail").inner_text())
        page.locator('[data-property-building="osm-way-12"]').click()
        check("mapped buildings are selectable with estimated height clearly labeled",
              page.locator(".property-building-detail").inner_text().startswith("warehouse")
              and "Illustrative height estimate: 6.0 m" in page.locator(".property-building-detail").inner_text()
              and page.locator('[data-mapped-building="osm-way-12"] [data-footprint-area-sqft]')
              .get_attribute("fill") == "#60a5fa")
        page.locator('[data-mapped-building="osm-way-11"]').click()
        check("existing footprint style and selection remain distinct from saved proposals",
              page.locator('[data-mapped-building="osm-way-12"] [data-footprint-area-sqft]')
              .get_attribute("fill") == "#9aa3a8"
              and page.evaluate("""() => {
                const store = JSON.parse(localStorage['oregon-estate-planner-v1']);
                return JSON.stringify({scenarios: store.scenarios,
                  mapFeatures: store.project.mapFeatures || []});
              }""") == proposed_before_buildings
              and "Mapped building references" not in page.evaluate(
                  "() => localStorage['oregon-estate-planner-v1']"))
        page.locator("[data-property-buildings-clear]").click()
        check("clearing mapped footprints leaves proposed buildings and parcel intact",
              "references cleared" in page.locator("#propertyBuildingStatus").inner_text()
              and page.locator("#propertyBuildingPanel [data-mapped-building]").count() == 0)
        building_mode["case"] = "empty"
        page.locator("[data-property-buildings-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyBuildingStatus').textContent.includes('No mapped building footprints')")
        check("empty building coverage is reported as unknown rather than no buildings",
              "does not establish that buildings are absent" in page.locator("#propertyBuildingStatus").inner_text())
        building_mode["case"] = "failure"
        page.locator("[data-property-buildings-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyBuildingStatus').textContent.includes('lookup failed (HTTP 503)')")
        check("building lookup failure is visible and retryable",
              page.locator("[data-property-buildings-load]").is_enabled()
              and "HTTP 503" in page.locator("#propertyBuildingStatus").inner_text())
        building_mode["case"] = "mapped"
        page.fill("#propertySearchQuery", "44.3, -123.3")
        page.locator("[data-property-search-form]").press("Enter")
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).project.locationCoordinates?.lat === 44.3")
        check("changing selected property clears mapped-building references",
              page.locator("#propertyBuildingPanel [data-mapped-building]").count() == 0
              and "cleared" in page.locator("#propertyBuildingStatus").inner_text())
        check("parcel search limitations are explicit",
              "Nationwide parcel lookup is not configured" in page.locator("#propertySearchCard").inner_text()
              and "Not measured · import a parcel boundary" in page.locator("#propertySearchCard").inner_text()
              and page.locator("#propertySearchCard").inner_text().count("Unavailable") == 2)
        page.fill("#plPrompt","Build a self-sufficient homestead with a 2,500 sqft house")
        page.click("[data-pl=gen]")
        page.wait_for_timeout(900)
        page.click("[data-pl=place]")
        page.wait_for_timeout(900)
        t = page.inner_text("body")
        n = page.evaluate("""()=>{const s=JSON.parse(localStorage['oregon-estate-planner-v1']);
          return s.scenarios.flatMap(c=>c.items).filter(o=>o.fromPlan).length}""")
        check("plan placed items (%d)" % n, n > 0)
        homestead = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const plan = s.plan.layoutSummary;
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan);
          return {summary: plan, types: items.map(o => o.type),
            rationale: items.every(o => typeof o.why === 'string' && o.why.length > 0),
            estimate: document.querySelector('[data-estimate-total="mid"]')?.textContent.trim(),
            budget: document.querySelector('[data-budget-total="mid"]')?.textContent.trim()};
        }""")
        check("homestead preset generates a house, garden, orchard, coop, barn, greenhouse, and pond",
              homestead["summary"]["homestead"]
              and homestead["summary"]["home"]["area"] == 2500
              and all(any(re.search(pattern, item_type, re.I)
                          for item_type in homestead["types"])
                      for pattern in ("home", "garden", "orchard", "coop",
                                      "barn", "greenhouse", "pond"))
              and homestead["rationale"]
              and homestead["estimate"] == homestead["budget"]
              and homestead["estimate"].startswith("$")
              and not homestead["summary"]["omitted"])
        ranch_prompt = "Plan a working horse ranch with a 40x60 shop"
        page.fill("#plPrompt", ranch_prompt)
        page.click("[data-pl=gen]")
        page.wait_for_function(
            "(prompt) => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt === prompt",
            arg=ranch_prompt)
        page.click("[data-pl=place]")
        page.wait_for_function(
            "(prompt) => JSON.parse(localStorage['oregon-estate-planner-v1']).plan"
            "?.layoutSummary?.prompt === prompt",
            arg=ranch_prompt)
        ranch = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const summary = s.plan.layoutSummary;
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(item => item.fromPlan);
          const facilities = new Set(summary.ranchFacilities.map(item => item.type));
          const overlap = items.some((a, i) => items.slice(i + 1).some(b =>
            a.x < b.x + b.w && a.x + a.w > b.x
            && a.y < b.y + b.h && a.y + a.h > b.y));
          return {summary, facilities: [...facilities], overlap,
            rationale: items.every(item => typeof item.why === 'string' && item.why.length > 0),
            programText: document.querySelector('[data-ranch-program]')?.innerText || '',
            estimate: document.querySelector('[data-estimate-total="mid"]')?.textContent.trim(),
            budget: document.querySelector('[data-budget-total="mid"]')?.textContent.trim()};
        }""")
        check("ranch preset adds editable facilities without implying animal capacity",
              ranch["summary"]["ranch"]
              and all(item_type in ranch["facilities"]
                      for item_type in ("outdoor", "roundpen", "pasture", "paddock",
                                        "feedstore", "hay", "manure"))
              and len([item for item in ranch["summary"]["ranchFacilities"]
                       if item["type"] == "pasture"]) == 2
              and not ranch["overlap"] and ranch["rationale"]
              and "animal capacity" in ranch["programText"].lower()
              and ranch["estimate"] == ranch["budget"])
        rv_prompt = "Plan an RV park for 16 sites, 2,500 sq ft per site"
        page.fill("#plPrompt", rv_prompt)
        page.click("[data-pl=gen]")
        page.wait_for_function(
            "(prompt) => {const raw=localStorage.getItem('oregon-estate-planner-v1');"
            "return raw && JSON.parse(raw).plan.prompt === prompt}",
            arg=rv_prompt)
        page.click("[data-pl=place]")
        page.wait_for_function(
            "(prompt) => {const raw=localStorage.getItem('oregon-estate-planner-v1');"
            "return raw && JSON.parse(raw).plan?.layoutSummary?.prompt === prompt}",
            arg=rv_prompt)
        rv_park = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const summary = s.plan.layoutSummary;
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(item => item.fromPlan);
          const area = items.find(item => item.type === 'rv');
          return {summary, types: items.map(item => item.type), area,
            summaryText: document.querySelector('[data-rv-park-summary]')?.innerText || '',
            estimate: document.querySelector('[data-estimate-total="mid"]')?.textContent.trim(),
            budget: document.querySelector('[data-budget-total="mid"]')?.textContent.trim()};
        }""")
        check("RV park preset reconciles site-count and gross-area assumptions with one editable area footprint",
              rv_park["summary"]["rvPark"]["sites"] == 16
              and rv_park["summary"]["rvPark"]["areaPerSite"] == 2500
              and rv_park["summary"]["rvPark"]["totalArea"] == 40000
              and rv_park["area"]["w"] * rv_park["area"]["h"] >= 40000
              and all(item_type in rv_park["types"]
                      for item_type in ("rv", "checkin", "restroom", "well", "septic"))
              and "individual pads" in rv_park["summaryText"]
              and "not assessed" in rv_park["summaryText"].lower()
              and rv_park["estimate"] == rv_park["budget"])
        rv_layout_before = page.evaluate("""() => JSON.stringify(
          JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios
            .find(c=>c.id===JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario)
            .items.filter(i=>i.fromPlan))""")
        invalid_rv_prompt = "Plan an RV park for 0 sites, 100 sq ft per site"
        page.fill("#plPrompt", invalid_rv_prompt)
        page.click("[data-pl=gen]")
        page.wait_for_selector("[data-rv-input-error]")
        page.click("[data-pl=place]")
        page.wait_for_function(
            "() => document.querySelector('.af-toast')?.textContent.includes('RV concepts support')")
        rv_layout_after = page.evaluate("""() => JSON.stringify(
          JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios
            .find(c=>c.id===JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario)
            .items.filter(i=>i.fromPlan))""")
        check("invalid RV site assumptions are explicit and preserve the previous generated layout",
              rv_layout_after == rv_layout_before)
        venue_prompt = "Design a wedding venue for 250 guests"
        page.fill("#plPrompt", venue_prompt)
        page.click("[data-pl=gen]")
        page.wait_for_function(
            "(prompt) => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt === prompt",
            arg=venue_prompt)
        page.click("[data-pl=place]")
        page.wait_for_function(
            "(prompt) => JSON.parse(localStorage['oregon-estate-planner-v1']).plan"
            "?.layoutSummary?.prompt === prompt",
            arg=venue_prompt)
        venue = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const summary = s.plan.layoutSummary;
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(item => item.fromPlan);
          const parking = items.find(item => item.type === 'parking');
          const endpoint = id => items.find(item => item.id === id);
          const routes = items.filter(item => item.type === 'path'
            && item.name.startsWith('Guest flow · ')).map(item => {
              const from = endpoint(item.routeFromId), to = endpoint(item.routeToId);
              return {item, from, to,
                centerline: from && to ? Math.hypot(
                  from.x + from.w / 2 - to.x - to.w / 2,
                  from.y + from.h / 2 - to.y - to.h / 2) : null};
            });
          return {
            summary, items, routes,
            parking: parking && {name: parking.name, area: parking.w * parking.h},
            summaryText: document.querySelector('[data-venue-summary]')?.innerText || '',
            layoutText: document.querySelector('[data-venue-layout]')?.innerText || '',
            programText: document.body.innerText,
            estimate: document.querySelector('[data-estimate-total="mid"]')?.textContent.trim(),
            budget: document.querySelector('[data-budget-total="mid"]')?.textContent.trim()
          };
        }""")
        expected_cars = math.ceil(math.ceil(250 / 2.4) * 1.1)
        venue_types = {item["type"] for item in venue["items"]}
        check("venue preset creates ceremony, reception, restroom, and parking components",
              {"pavilion", "event", "restroom", "parking"}.issubset(venue_types)
              and any(item["type"] == "pavilion" and "Ceremony" in item["name"]
                      for item in venue["items"])
              and any(item["type"] == "event" and "reception" in item["name"].lower()
                      for item in venue["items"]))
        check("venue parking follows 2.4 guests per car plus 10% reserve and 300 sq ft per car",
              venue["summary"]["parking"]["cars"] == expected_cars
              and venue["parking"]["name"] == f"Guest parking ({expected_cars} cars)"
              and venue["parking"]["area"] >= expected_cars * 300
              and "2.4 guests/car" in venue["summaryText"]
              and f"{expected_cars * 300:,} sq ft allocated" in venue["summaryText"])
        check("venue guest-flow paths connect their named endpoints and use measured lengths",
              len(venue["routes"]) == 2
              and {route["item"]["name"] for route in venue["routes"]}
                  == {"Guest flow · Parking to ceremony",
                      "Guest flow · Ceremony to reception"}
              and all(route["from"] and route["to"]
                      and route["item"]["routeLengthFt"] == route["centerline"]
                      and route["item"]["routeFromId"] != route["item"]["routeToId"]
                      for route in venue["routes"])
              and venue["summary"]["guestRoutes"]["totalFeet"]
                  == sum(math.floor(route["item"]["routeLengthFt"] + 0.5)
                         for route in venue["routes"]))
        check("venue path costs appear in the estimate and reconcile to the budget",
              venue["summary"]["guestRoutes"]["estimatedCost"]
                  == sum(math.floor(route["item"]["routeLengthFt"] * 10 + 0.5)
                         for route in venue["routes"])
              and f"Guest-flow paths ({venue['summary']['guestRoutes']['totalFeet']} ft @ $10/ft)"
                  in venue["programText"]
              and venue["estimate"] == venue["budget"])
        check("venue caveats identify county/professional review and unassessed compliance",
              all(term in venue["summaryText"].lower()
                  for term in ("county", "professionals", "fire access",
                               "accessibility", "occupancy", "permit compliance"))
              and "fire lane" in venue["layoutText"].lower()
              and "do not establish" in venue["layoutText"].lower())
        page.fill("#plPrompt", "Create a venue")
        page.click("[data-pl=gen]")
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt === 'Create a venue'")
        check("venue prompts without an attendance count use the disclosed 150-guest default",
              "EVENT VENUE CHECK · 150 GUESTS" in page.locator("[data-venue-summary]").inner_text())
        page.fill("#plPrompt", "Create a venue for 80 attendees")
        page.click("[data-pl=gen]")
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt"
            " === 'Create a venue for 80 attendees'")
        check("venue summary honors attendee counts as well as guest counts",
              "EVENT VENUE CHECK · 80 GUESTS" in page.locator("[data-venue-summary]").inner_text())
        original_layout = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return JSON.stringify(s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan));
        }""")
        page.fill("#plPrompt", "Build a 2,500 sqft house, 40x60 shop, and orchard")
        layout_started = time.monotonic()
        page.click("[data-pl=gen]")
        page.wait_for_function("""() =>
          JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt
            === "Build a 2,500 sqft house, 40x60 shop, and orchard" """)
        page.click("[data-pl=place]")
        page.wait_for_function("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return s.plan?.layoutSummary?.home?.area === 2500;
        }""")
        layout_elapsed = time.monotonic() - layout_started
        layout_data = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan);
          return {
            types: items.map(o => o.type),
            allExplained: items.every(o => Boolean(o.why)),
            drivewayCount: items.filter(o => o.type === 'road'
              && /^Driveway/.test(o.name)).length,
            shop: items.find(o => o.type === 'shop'),
            summary: s.plan.layoutSummary,
            utilityText: document.body.innerText.includes('UTILITY ROUTES')
              && document.body.innerText.includes('provider service')
          };
        }""")
        check("requested house footprint is exactly 2,500 sq ft",
              layout_data["summary"]["home"]["area"] == 2500
              and "2,500 sq ft" in page.locator("[data-generated-layout]").inner_text())
        check("requested shop dimensions and orchard are placed",
              layout_data["shop"] is not None
              and (layout_data["shop"]["w"], layout_data["shop"]["h"]) == (40, 60)
              and "orchard" in layout_data["types"])
        check("layout includes one conceptual driveway, utilities, and rationale",
              layout_data["drivewayCount"] == 1
              and {"well", "septic"}.issubset(set(layout_data["types"]))
              and layout_data["allExplained"]
              and layout_data["utilityText"]
              and "unverified" in page.locator("[data-generated-layout]").inner_text())
        check("request-to-editable-layout completes in under 30 seconds",
              layout_elapsed < 30 and page.locator("[data-generated-layout]").count() == 1)
        page.locator("[data-af=undo]").click()
        page.wait_for_function("""expected => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return JSON.stringify(s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan)) === expected;
        }""", arg=original_layout)
        check("layout generation is undoable without losing the previous layout",
              page.evaluate("""() => JSON.stringify(
                JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios
                  .find(c => c.id === JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario)
                  .items.filter(o => o.fromPlan))""") == original_layout)
        page.fill("#plPrompt", "Build a 2,500 sqft house, 40x60 shop, and orchard")
        page.click("[data-pl=gen]")
        page.wait_for_function("""() =>
          JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt
            === "Build a 2,500 sqft house, 40x60 shop, and orchard" """)
        page.click("[data-pl=place]")
        page.wait_for_function("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return s.plan?.layoutSummary?.prompt
            === "Build a 2,500 sqft house, 40x60 shop, and orchard"
            || document.querySelector('.af-toast')?.textContent.includes('Could not');
        }""")
        failed_layout_before = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return JSON.stringify(s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan));
        }""")
        dimensions_before = page.evaluate("""() => {
          const project = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
          return {acres: project.acres, aspect: project.aspect};
        }""")
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const s = JSON.parse(localStorage[key]);
          s.project.acres = 1;
          localStorage[key] = JSON.stringify(s);
        }""")
        page.reload()
        page.locator("#nav [data-page=planner]").click()
        page.fill("#plPrompt", "Build a self-sufficient homestead with a 50000 sqft house")
        page.click("[data-pl=gen]")
        page.wait_for_function("""() =>
          JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt
            === "Build a self-sufficient homestead with a 50000 sqft house" """)
        page.click("[data-pl=place]")
        page.wait_for_function("() => document.querySelector('.af-toast')?.textContent.includes('does not fit')")
        failed_layout_after = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return JSON.stringify(s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan));
        }""")
        check("oversized homestead house is rejected without damaging the existing layout",
              failed_layout_after == failed_layout_before)
        page.fill("#plPrompt", "Build a house with a 0x60 shop")
        page.click("[data-pl=gen]")
        page.click("[data-pl=place]")
        page.wait_for_function(
            "() => document.querySelector('.af-toast')?.textContent.includes('dimensions are invalid')")
        invalid_layout_after = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return JSON.stringify(s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan));
        }""")
        check("invalid dimensions are rejected without damaging the existing layout",
              invalid_layout_after == failed_layout_before)
        page.fill("#plPrompt", "Build a self-sufficient homestead with a 2,500 sqft house")
        page.click("[data-pl=gen]")
        page.wait_for_function("""() =>
          JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt
            === "Build a self-sufficient homestead with a 2,500 sqft house" """)
        page.click("[data-pl=place]")
        page.wait_for_function(
            """() => JSON.parse(localStorage['oregon-estate-planner-v1']).plan
              ?.layoutSummary?.prompt
                === "Build a self-sufficient homestead with a 2,500 sqft house" """)
        constrained_homestead = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan);
          const margin = 30, width = Math.min(
            Math.sqrt(s.project.acres * 43560 * s.project.aspect) * .9, 1800);
          const height = Math.min(
            s.project.acres * 43560 /
              Math.sqrt(s.project.acres * 43560 * s.project.aspect) * .9, 1800);
          const buildings = items.filter(item => item.type !== 'road');
          return {summary: s.plan.layoutSummary, items, width, height,
            overlaps: buildings.some((a, i) => buildings.slice(i + 1).some(b =>
              a.x < b.x + b.w + margin && a.x + a.w + margin > b.x
              && a.y < b.y + b.h + margin && a.y + a.h + margin > b.y))};
        }""")
        check("a constrained one-acre homestead places fitting components and explains omissions",
              constrained_homestead["summary"]["home"] is not None
              and constrained_homestead["summary"]["omitted"]
              and constrained_homestead["overlaps"] is False
              and all(item["x"] >= 240 and item["y"] >= 240
                      and item["x"] + item["w"] <= 240 + constrained_homestead["width"]
                      and item["y"] + item["h"] <= 240 + constrained_homestead["height"]
                      for item in constrained_homestead["items"])
              and page.locator("[data-layout-omissions] li").count()
                  == len(constrained_homestead["summary"]["omitted"]))
        constrained_layout_before = page.evaluate("""() => JSON.stringify(
          JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios
            .find(c => c.id === JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario)
            .items.filter(o => o.fromPlan))""")
        page.fill("#plPrompt", "Design a family compound with 3 homes and a 40x60 shop")
        page.click("[data-pl=gen]")
        page.wait_for_function("""() =>
          JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt
            === "Design a family compound with 3 homes and a 40x60 shop" """)
        page.click("[data-pl=place]")
        page.wait_for_function(
            "() => document.querySelector('.af-toast')?.textContent.includes('Could not')")
        constrained_compound_after = page.evaluate("""() => JSON.stringify(
          JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios
            .find(c => c.id === JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario)
            .items.filter(o => o.fromPlan))""")
        check("an undersized compound planning area reports a fit limit and preserves the prior layout",
              constrained_compound_after == constrained_layout_before)
        page.evaluate("""dimensions => {
          const key = 'oregon-estate-planner-v1';
          const s = JSON.parse(localStorage[key]);
          s.project.acres = dimensions.acres;
          s.project.aspect = dimensions.aspect;
          localStorage[key] = JSON.stringify(s);
        }""", dimensions_before)
        page.reload()
        page.locator("#nav [data-page=planner]").click()
        check("no JS errors", not errors)
        road_mode["center"] = [-123.3, 44.3]
        road_mode["case"] = "mapped"
        page.locator("[data-property-roads-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyRoadStatus').textContent.includes('Loaded 5 mapped road features')")
        page.locator("[data-property-buildings-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyBuildingStatus').textContent.includes('Loaded 2 mapped building footprints')")
        check("both temporary map contexts load before parcel geometry changes",
              page.locator("#propertyRoadPanel [data-mapped-road]").count() > 0
              and page.locator("#propertyBuildingPanel [data-mapped-building]").count() == 2)
        boundary_coordinates = [
            [
                [[-123.01, 43.99], [-122.99, 43.99], [-122.99, 44.01],
                 [-123.01, 44.01], [-123.01, 43.99]],
                [[-123.005, 43.995], [-123.005, 44.005], [-122.995, 44.005],
                 [-122.995, 43.995], [-123.005, 43.995]],
            ],
            [
                [[-123.03, 44.0], [-123.025, 44.0], [-123.025, 44.005],
                 [-123.03, 44.005], [-123.03, 44.0]],
            ],
        ]
        expected_perimeter = sum(
            geodesic_feet(a, b)
            for polygon in boundary_coordinates
            for ring in polygon
            for a, b in zip(ring, ring[1:]))
        page.locator("#nav [data-page=designer]").click()
        geojson = {"type": "MultiPolygon", "coordinates": boundary_coordinates}
        page.locator("#parcelFile").set_input_files({
            "name": "Boundary measurement smoke test.geojson",
            "mimeType": "application/geo+json",
            "buffer": json.dumps(geojson).encode(),
        })
        page.wait_for_function("""() => {
          const project = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
          return project.parcelBoundary?.source === 'Boundary measurement smoke test.geojson';
        }""")
        page.locator("#nav [data-page=planner]").click()
        check("importing a new parcel clears references for the previous planning extent",
              page.locator("#propertyRoadPanel [data-mapped-road]").count() == 0
              and page.locator("#propertyBuildingPanel [data-mapped-building]").count() == 0
              and "cleared" in page.locator("#propertyRoadStatus").inner_text()
              and "cleared" in page.locator("#propertyBuildingStatus").inner_text())
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.project.locationCoordinates = {lon: -123.006, lat: 44.003, state: 'OR'};
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.wait_for_timeout(800)
        page.locator("#nav [data-page=planner]").click()
        road_mode["center"] = [-123.006, 44.003]
        page.locator("[data-property-roads-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyRoadStatus').textContent.includes('Loaded 5 mapped road features')")
        page.locator("[data-property-buildings-load]").click()
        page.wait_for_function(
            "() => document.querySelector('#propertyBuildingStatus').textContent.includes('Loaded 2 mapped building footprints')")
        aligned_overlays = page.evaluate("""() => {
          const spatial = window.__acreforgeSpatialTest;
          const project = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
          const boundary = spatial.normalizeParcelBoundary(project.parcelBoundary);
          const anchor = spatial.geoPlanAnchorFor(
            {w: boundary.width, h: boundary.height}, boundary, boundary.center);
          const expected = point => spatial.geoToPlanPoint(anchor, point);
          const road = document.querySelector('#propertyRoadPanel [data-mapped-road="primary"]');
          const roadPoints = road.getAttribute('points').split(' ')
            .map(point => point.split(',').map(Number));
          const building = document.querySelector('#propertyBuildingPanel polygon[data-footprint-area-sqft]');
          const buildingPoints = building.getAttribute('points').split(' ')
            .map(point => point.split(',').map(Number));
          const buildingCenter = buildingPoints.slice(0, -1).reduce(
            (sum, point) => [sum[0] + point[0] / (buildingPoints.length - 1),
              sum[1] + point[1] / (buildingPoints.length - 1)], [0, 0]);
          const marker = document.querySelector('#propertyRoadPanel [data-selected-location]');
          const buildingMarker = document.querySelector('#propertyBuildingPanel [data-selected-location]');
          const markerPoint = [Number(marker.getAttribute('cx')), Number(marker.getAttribute('cy'))];
          return {
            roadPoints,
            expectedRoadStart: expected([-123.007, 44.003]),
            expectedRoadEnd: expected([-123.005, 44.003]),
            roadMidpoint: [(roadPoints[0][0] + roadPoints[1][0]) / 2,
              (roadPoints[0][1] + roadPoints[1][1]) / 2],
            expectedSelected: expected([-123.006, 44.003]),
            markerPoint,
            buildingCenter,
            expectedBuildingCenter: expected([-123.006, 44.003]),
            buildingMarker: [Number(buildingMarker.getAttribute('cx')),
              Number(buildingMarker.getAttribute('cy'))]
          };
        }""")
        within_one_foot = lambda actual, expected: math.dist(actual, expected) <= 1
        check("mocked mapped road vertices align to the imported parcel frame",
              within_one_foot(aligned_overlays["roadPoints"][0],
                              aligned_overlays["expectedRoadStart"])
              and within_one_foot(aligned_overlays["roadPoints"][1],
                                  aligned_overlays["expectedRoadEnd"]))
        check("mapped road midpoint, building footprint, and selected pin share the same parcel coordinates",
              within_one_foot(aligned_overlays["roadMidpoint"],
                              aligned_overlays["expectedSelected"])
              and within_one_foot(aligned_overlays["buildingCenter"],
                                  aligned_overlays["expectedBuildingCenter"])
              and within_one_foot(aligned_overlays["markerPoint"],
                                  aligned_overlays["expectedSelected"])
              and within_one_foot(aligned_overlays["buildingMarker"],
                                  aligned_overlays["expectedSelected"]))
        page.fill("#plPrompt", "Build a homestead with a 2,500 sqft house")
        page.click("[data-pl=gen]")
        page.click("[data-pl=place]")
        page.wait_for_function("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return s.plan?.layoutSummary?.parcelChecked === true
            || document.querySelector('.af-toast')?.textContent.includes('Could not');
        }""")
        parcel_layout = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const b = s.project.parcelBoundary;
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan);
          const pointInParcel = (x, y) => b.polygons.some(poly => {
            const inside = ring => {
              let value = false;
              for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
                const a = ring[i], c = ring[j];
                if ((a[1] > y) !== (c[1] > y)
                    && x < (c[0] - a[0]) * (y - a[1]) / (c[1] - a[1]) + a[0]) value = !value;
              }
              return value;
            };
            return inside(poly[0]) && !poly.slice(1).some(inside);
          });
          const outsideParcel = o => {
            const points = [[o.x, o.y], [o.x + o.w, o.y],
              [o.x + o.w, o.y + o.h], [o.x, o.y + o.h],
              [o.x + o.w / 2, o.y + o.h / 2]];
            if (!points.every(p => pointInParcel(...p))) return true;
            const cross = (a, c, d) => {
              const v = (c[0] - a[0]) * (d[1] - a[1]) - (c[1] - a[1]) * (d[0] - a[0]);
              return Math.abs(v) < 1e-7 ? 0 : v > 0 ? 1 : 2;
            };
            const intersects = (a, c, d, e) =>
              cross(a, c, d) !== cross(a, c, e) && cross(d, e, a) !== cross(d, e, c);
            const edges = points.slice(0, 4).map((p, i) => [p, points[(i + 1) % 4]]);
            return b.polygons.some(poly => poly.some(ring =>
              ring.some((a, i) => edges.some(([c, d]) =>
                intersects(a, ring[(i + 1) % ring.length], c, d)))));
          };
          return {width: b.width, height: b.height, parcelChecked: s.plan.layoutSummary.parcelChecked,
          homestead: s.plan.layoutSummary.homestead, omitted: s.plan.layoutSummary.omitted,
          prompt: s.plan.layoutSummary.prompt,
            items: items.map(o => ({
            x: o.x, y: o.y, w: o.w, h: o.h, type: o.type
          })), withinParcel: items.every(o => !outsideParcel(o))};
        }""")
        parcel_layout_fits = (parcel_layout["items"]
                              and parcel_layout["parcelChecked"]
                              and parcel_layout["homestead"]
                              and parcel_layout["prompt"] == "Build a homestead with a 2,500 sqft house"
                              and not parcel_layout["omitted"]
                              and all(o["x"] >= 0 and o["y"] >= 0
                                      and o["x"] + o["w"] <= parcel_layout["width"]
                                      and o["y"] + o["h"] <= parcel_layout["height"]
                                      for o in parcel_layout["items"])
                              and parcel_layout["withinParcel"])
        parcel_types = [item["type"] for item in parcel_layout["items"]]
        check("complete homestead fits the imported parcel boundary without omitting components",
              parcel_layout_fits
              and all(any(re.search(pattern, item_type, re.I) for item_type in parcel_types)
                      for pattern in ("home", "garden", "orchard", "coop",
                                      "barn", "greenhouse", "pond")))
        compound_prompt = "Design a family compound with 3 homes and a 40x60 shop"
        page.fill("#plPrompt", compound_prompt)
        page.click("[data-pl=gen]")
        page.wait_for_function(
            "(prompt) => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.prompt === prompt",
            arg=compound_prompt)
        page.click("[data-pl=place]")
        page.wait_for_function(
            "(prompt) => JSON.parse(localStorage['oregon-estate-planner-v1']).plan"
            "?.layoutSummary?.prompt === prompt",
            arg=compound_prompt)
        compound_layout = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const boundary = s.project.parcelBoundary;
          const items = s.scenarios.find(c => c.id === s.activeScenario).items
            .filter(o => o.fromPlan);
          const inside = (x, y) => boundary.polygons.some(poly => {
            const ringInside = ring => {
              let value = false;
              for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
                const a = ring[i], b = ring[j];
                if ((a[1] > y) !== (b[1] > y)
                    && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) value = !value;
              }
              return value;
            };
            return ringInside(poly[0]) && !poly.slice(1).some(ringInside);
          });
          const footprintInside = item => {
            const points = [[item.x, item.y], [item.x + item.w, item.y],
              [item.x + item.w, item.y + item.h], [item.x, item.y + item.h],
              [item.x + item.w / 2, item.y + item.h / 2]];
            if (!points.every(point => inside(...point))) return false;
            const cross = (a, b, c) => {
              const v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
              return Math.abs(v) < 1e-7 ? 0 : v > 0 ? 1 : 2;
            };
            const intersects = (a, b, c, d) =>
              cross(a, b, c) !== cross(a, b, d) && cross(c, d, a) !== cross(c, d, b);
            const edges = points.slice(0, 4).map((point, i) => [point, points[(i + 1) % 4]]);
            return !boundary.polygons.some(poly => poly.some(ring =>
              ring.some((point, i) => edges.some(([a, b]) =>
                intersects(point, ring[(i + 1) % ring.length], a, b)))));
          };
          const homeItems = items.filter(item => item.type === 'home');
          const homes = homeItems.slice().sort((a, b) => a.name.localeCompare(b.name));
          const mainHome = homeItems.find(item => item.name === 'Main house');
          const center = item => [item.x + item.w / 2, item.y + item.h / 2];
          const distance = (a, b) => Math.hypot(center(a)[0] - center(b)[0],
            center(a)[1] - center(b)[1]);
          const nearest = homes.flatMap((a, i) => homes.slice(i + 1).map(b => distance(a, b)));
          const shops = items.filter(item => item.type === 'shop');
          const buildings = items.filter(item => !['road', 'utility'].includes(item.type));
          const alternatives = [...document.querySelectorAll('[data-compound-alternative]')]
            .map(row => ({name: row.dataset.compoundAlternative,
              rank: +row.dataset.rank, score: +row.dataset.relativeIndex,
              gap: +row.dataset.closestHomesFt, walk: +row.dataset.farthestWalkFt,
              trench: +row.dataset.sharedTrenchFt}));
          const tradeoffs = document.querySelector('[data-compound-tradeoffs]');
          return {
            summary: s.plan.layoutSummary, items, homes: homes.map(item => item.name),
            shops: shops.map(item => ({name: item.name, w: item.w, h: item.h})),
            contained: items.every(footprintInside),
            overlaps: buildings.some((a, i) => buildings.slice(i + 1).some(b =>
              a.x < b.x + b.w && a.x + a.w > b.x
              && a.y < b.y + b.h && a.y + a.h > b.y)),
            minGap: Math.round(Math.min(...nearest)),
            farthestWalk: Math.max(...homeItems.filter(home => home !== mainHome)
              .map(home => Math.round(distance(mainHome, home)))),
            tradeoffs: tradeoffs && {
              minGap: +tradeoffs.dataset.compoundMinHomeDistance,
              walk: +tradeoffs.dataset.compoundFarthestWalk,
              trench: +tradeoffs.dataset.compoundSharedTrench,
              text: tradeoffs.innerText
            },
            alternatives,
            midEstimate: document.querySelector('[data-estimate-total="mid"]')?.textContent.trim(),
            midBudget: document.querySelector('[data-budget-total="mid"]')?.textContent.trim()
          };
        }""")
        check("compound places main, parent, and guest homes plus the shared shop",
              compound_layout["summary"]["compound"]
              and compound_layout["homes"] == ["Guest house", "Main house", "Parent house"]
              and len(compound_layout["shops"]) == 1
              and compound_layout["shops"][0]["w"] == 40
              and compound_layout["shops"][0]["h"] == 60
              and compound_layout["midEstimate"] == compound_layout["midBudget"])
        check("compound buildings stay inside the imported parcel without overlaps",
              compound_layout["contained"] and not compound_layout["overlaps"])
        check("privacy and travel metrics match the generated home geometry",
              compound_layout["tradeoffs"]["minGap"] == compound_layout["minGap"]
              and compound_layout["tradeoffs"]["walk"] == compound_layout["farthestWalk"]
              and "privacy" in compound_layout["tradeoffs"]["text"].lower()
              and "walking distance" in compound_layout["tradeoffs"]["text"].lower())
        alternatives = compound_layout["alternatives"]
        check("compound spacing alternatives are ranked and disclose shared-utility tradeoffs",
              len(alternatives) == 3
              and [row["rank"] for row in alternatives] == [1, 2, 3]
              and [row["score"] for row in alternatives]
                  == sorted((row["score"] for row in alternatives), reverse=True)
              and {row["name"] for row in alternatives}
                  == {"Utility-first cluster", "Balanced spacing", "Privacy-first spread"}
              and all(row["gap"] > 0 and row["walk"] > 0 and row["trench"] > 0
                      for row in alternatives)
              and "not separately placed plans" in compound_layout["tradeoffs"]["text"]
              and page.locator("[data-utility-route-row]").count() >= 3)
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.scenarios = [{
            id: 'boundary-test', name: 'Boundary measurement test',
            items: [], fields: [], surfacePatches: [],
            finance: saved.scenarios[0].finance
          }];
          saved.activeScenario = 'boundary-test';
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.locator("#nav [data-page=planner]").click()
        page.wait_for_selector("[data-boundary-perimeter-ft]")
        boundary_metrics = page.evaluate("""() => {
          const project = JSON.parse(localStorage['oregon-estate-planner-v1']).project;
          const text = document.querySelector('#propertySearchCard').innerText;
          return {
            area: project.parcelBoundary.acres,
            projectArea: project.acres,
            perimeterText: document.querySelector('[data-boundary-perimeter-ft]').textContent,
            sourceVisible: text.includes('Boundary measurement smoke test'),
            frontageUnavailable: text.includes('Road frontage') && text.includes('Unavailable'),
            neighborsUnavailable: text.includes('Adjacent parcels') && text.includes('Unavailable')
          };
        }""")

        observed_perimeter = int(re.sub(r"[^0-9]", "", boundary_metrics["perimeterText"]))
        check("multipart parcel area is calculated and shown",
              round(boundary_metrics["area"], 2) == round(boundary_metrics["projectArea"], 2)
              and page.locator("[data-boundary-area]").inner_text()
              == f"{boundary_metrics['area']:.2f} acres")
        check("perimeter includes every polygon and interior ring",
              abs(observed_perimeter - round(expected_perimeter)) <= 1)
        check("boundary source, unsupported frontage, and adjacent-parcel gaps are explicit",
              boundary_metrics["sourceVisible"] and boundary_metrics["frontageUnavailable"]
              and boundary_metrics["neighborsUnavailable"])
        page.locator("#nav [data-page=designer]").click()
        outline = page.locator("#siteMap .parcel-boundary-outline")
        outline_info = outline.evaluate("""path => {
          const svg = path.ownerSVGElement;
          const box = svg.viewBox.baseVal;
          const zoomed = {x: box.x + box.width * .375, y: box.y + box.height * .375,
            width: box.width / 4, height: box.height / 4};
          svg.setAttribute('viewBox', `${zoomed.x} ${zoomed.y} ${zoomed.width} ${zoomed.height}`);
          return {
            vectorEffect: path.getAttribute('vector-effect'),
            visibleAtZoom: path.getAttribute('d').length > 0
              && path.getBBox().width > 0 && path.getBBox().height > 0
          };
        }""")
        check("parcel outline remains visible with screen-stable stroke when zoomed",
              outline.count() == 1 and outline_info["vectorEffect"] == "non-scaling-stroke"
              and outline_info["visibleAtZoom"])
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.project.parcelBoundary = {
            ...saved.project.parcelBoundary,
            source: 'Buildability hole smoke test',
            coordinates: [[
              [[-123.01, 43.99], [-122.99, 43.99], [-122.99, 43.997],
               [-123.003, 43.997], [-123.003, 44.01], [-123.01, 44.01],
               [-123.01, 43.99]],
              [[-123.009, 43.991], [-123.007, 43.991], [-123.007, 43.993],
               [-123.009, 43.993], [-123.009, 43.991]]
            ]]
          };
          saved.project.locationCoordinates = {lon: -123, lat: 44, state: 'OR'};
          saved.land = null;
          saved.analysis = null;
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.locator('[data-page="planner"]').first.click()
        start_analysis(page)
        parcel_cells = page.evaluate("""() => {
          const a = JSON.parse(localStorage['oregon-estate-planner-v1']).analysis;
          const boundary = JSON.parse(localStorage['oregon-estate-planner-v1']).project.parcelBoundary;
          const outer = boundary.coordinates[0][0], hole = boundary.coordinates[0][1], g = a.grid;
          const contains = (point, ring) => {
            let inside = false;
            for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
              const p = ring[i], q = ring[j];
              if ((p[1] > point[1]) !== (q[1] > point[1])
                  && point[0] < (q[0] - p[0]) * (point[1] - p[1]) / (q[1] - p[1]) + p[0]) {
                inside = !inside;
              }
            }
            return inside;
          };
          const cells = [];
          for (let r = 0; r < a.gh; r++) for (let q = 0; q < a.gw; q++) {
            if (a.cells[r][q] !== '.') continue;
            const point = [
              g.lon0 + (g.x0 + (q + .5) * g.cw) / g.kLon,
              g.lat0 + (g.y1 - (r + .5) * g.ch) / g.kLat
            ];
            cells.push({q, r, inHole: contains(point, hole), inParcel: contains(point, outer)});
          }
          const holeCell = cells.find(cell => cell.inHole);
          const outsideCell = cells.find(cell => !cell.inParcel);
          const clickCell = cell => {
            const svg = document.querySelector('#pzMap'), point = svg.createSVGPoint();
            point.x = cell.q + .5; point.y = cell.r + .5;
            const screen = point.matrixTransform(svg.getScreenCTM());
            svg.dispatchEvent(new MouseEvent('click', {
              bubbles: true, clientX: screen.x, clientY: screen.y
            }));
            return document.querySelector('#pzPop').textContent;
          };
          return {
            holeCells: cells.filter(cell => cell.inHole).length,
            outsideCells: cells.filter(cell => !cell.inParcel).length,
            holeMessage: holeCell ? clickCell(holeCell) : '',
            outsideMessage: outsideCell ? clickCell(outsideCell) : ''
          };
        }""")
        check("parcel holes and outside geometry receive no buildability class",
              parcel_cells["holeCells"] > 0 and parcel_cells["outsideCells"] > 0
              and "no buildability class is assigned" in parcel_cells["holeMessage"]
              and "no buildability class is assigned" in parcel_cells["outsideMessage"])
        land_requests.update(fema=0, soil=0, epqs=0)
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.scenarios = [{id: 'sample-test', name: 'Sampling test',
            items: [], fields: [], surfacePatches: []}];
          saved.activeScenario = 'sample-test';
          saved.project.parcelBoundary = {source: 'smoke test', coordinates: [[[
            [-123.01, 43.99], [-122.99, 43.99], [-122.99, 44.01],
            [-123.01, 44.01], [-123.01, 43.99]
          ]]]};
          saved.project.locationCoordinates = {lon: -123, lat: 44, state: 'OR'};
          saved.land = null;
          saved.analysis = null;
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.wait_for_timeout(800)
        page.locator('[data-page="planner"]').first.click()
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.sampleCount === 9",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        check("parcel flood and soil sampling covers nine points",
              land["sampleCount"] == 9 and land_requests == {"fema": 9, "soil": 9, "epqs": 9})
        check("parcel elevations report a sampled range and average",
              land["elevationSampleCount"] == 9 and land["elevationMin"] < land["elevationMean"]
              < land["elevationMax"] and land["elev"].endswith("(9/9 samples)")
              and "USGS elevation 9/9 responded, 9 mapped" in land["coverage"])
        check("partial flood risk and soil mix are explicit",
              land["floodRisk"] == "high" and land["floodCounts"]["high"] == 1
              and "1/9" in land["flood"] and "Sandy loam" in land["soil"]
              and "Clay loam" in land["soil"] and "9 sampled points" in land["coverage"])
        land_mode["delay"] = True
        land_mode["fema_case"] = "partial-high"
        page.locator('[data-pl="land"]').click()
        check("land lookup shows progress and blocks duplicate clicks",
              page.locator('[data-pl="land"]').is_disabled()
              and page.locator('[data-pl="land"]').inner_text() == "Checking…")
        land_mode["fema_case"] = "partial-low"
        land_mode["delay"] = False
        page.locator('[data-pl="pz"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.floodCounts?.low === 1",
            timeout=30000)
        page.wait_for_function("() => !document.querySelector('[data-pl=\"land\"]')?.disabled")
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis?.healthVersion === 2",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        analysis = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        check("overlapping analyzer lookup replaces the earlier request",
              land["floodRisk"] == "unavailable" and land["floodCounts"]["low"] == 1
              and land["floodCounts"]["high"] == 0 and land["floodCounts"]["unmapped"] == 8)
        check("health score reports terrain coverage and measured evidence basis",
              analysis["score"] is not None and analysis["terrainCoverage"] >= .7
              and "mapped indicators" in analysis["scoreBasis"]
              and "Access and utility values are distance-based estimates" in analysis["scoreBasis"])
        displayed_metrics_match = page.locator(".pz-hero").get_attribute("data-health-score") == str(analysis["score"])
        for dimension, metric in analysis["sub"].items():
            card = page.locator(f'[data-health-dimension="{dimension}"]')
            expected_value = "" if metric["value"] is None else str(metric["value"])
            displayed_metrics_match = displayed_metrics_match and card.get_attribute("data-health-status") == metric["status"] \
                and card.get_attribute("data-health-value") == expected_value
        check("displayed health scores and values match persisted analysis",
              displayed_metrics_match)
        check("privacy is unavailable rather than inferred from parcel edges",
              analysis["sub"]["Privacy"]["value"] is None
              and analysis["sub"]["Privacy"]["status"] == "unavailable"
              and "sightlines are not modeled" in analysis["sub"]["Privacy"]["detail"])
        check("terrain and soil evidence coverage is disclosed",
              "AWS Terrarium" in analysis["sub"]["Buildability"]["detail"]
              and "%" in analysis["sub"]["Solar"]["detail"]
              and "/" in analysis["sub"]["Drainage"]["detail"])
        check("access and utility indicators disclose planning assumptions",
              analysis["sub"]["Access"]["status"] == "estimate"
              and analysis["sub"]["Utilities"]["status"] == "estimate"
              and "assumed" in analysis["sub"]["Access"]["detail"]
              and "no utility provider data" in analysis["sub"]["Utilities"]["detail"])
        check("partial flood samples do not create a confident flood score",
              analysis["floodRisk"] == "unavailable"
              and "Flood" not in analysis["scoreBasis"])
        check("health dashboard displays unavailable and estimated states",
              page.locator('[data-health-dimension="Privacy"]').get_attribute("data-health-status") == "unavailable"
              and page.locator('[data-health-dimension="Access"]').get_attribute("data-health-status") == "estimate"
              and page.locator('[data-health-dimension="Privacy"]').inner_text().find("Unavailable") >= 0)
        land_mode["fema_case"] = "all-low"
        page.locator('[data-pl="pz"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.floodRisk === 'low'",
            timeout=30000)
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis?.floodRisk === 'low'",
            timeout=30000)
        complete_analysis = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        check("complete mapped terrain, soil, and flood inputs remain explicitly sourced",
              complete_analysis["sub"]["Drainage"]["status"] == "sampled"
              and complete_analysis["floodRisk"] == "low"
              and complete_analysis["sub"]["Privacy"]["status"] == "unavailable")
        command_baseline = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return {coordinates: s.project.locationCoordinates, parcel: s.project.parcelBoundary,
            scenario: s.activeScenario, plan: s.plan?.prompt || '',
            mod: s.plan?.mod || null, itemCount: s.scenarios.find(x => x.id === s.activeScenario).items.length};
        }""")
        check("one rule-based property command bar replaces the separate design-assistant input",
              page.locator("[data-property-command-bar] #afAsk").count() == 1
              and page.locator("#plAsk").count() == 0
              and "RULE-BASED" in page.locator("[data-property-command-bar]").inner_text())
        page.fill("#afAsk", "What can I build here?")
        page.locator('[data-af="ask"]').click()
        answer = page.locator("#afOut").inner_text()
        check("property question returns the current analysis and explicit caveats",
              "Zone A" in answer and "not permit" in answer.lower()
              and page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario")
              == command_baseline["scenario"])
        for prompt, expected in [
                ("Build a homestead", "self-sufficient homestead"),
                ("Create a compound", "family compound"),
                ("Create a venue", "wedding venue")]:
            page.fill("#afAsk", prompt)
            page.locator('[data-af="ask"]').click()
            check(f"property command prepares a rule-based plan: {prompt}",
                  expected in page.locator("#plPrompt").input_value().lower()
                  and "rule-based starter plan" in page.locator("#afOut").inner_text().lower())
            page.locator('[data-af="undo"]').click()
        page.fill("#afAsk", "Build a homestead")
        page.locator('[data-af="ask"]').click()
        page.wait_for_timeout(400)
        before_cost_command = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.mod")
        page.fill("#afAsk", "Lower costs")
        page.locator('[data-af="ask"]').click()
        page.wait_for_timeout(400)
        lowered = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.mod")
        check("lower-cost command applies the rule-based estimator and confirms the change",
              lowered != before_cost_command
              and "applied rule-based cost reductions" in page.locator("#afOut").inner_text().lower())
        page.locator('[data-af="undo"]').click()
        page.wait_for_timeout(400)
        restored_mod = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).plan.mod")
        check("undo restores the previous planner estimate settings",
              restored_mod == before_cost_command)
        command_baseline["itemCount"] = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios.find(s => s.id === JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario).items.length")
        page.fill("#afAsk", "Add another house")
        page.locator('[data-af="ask"]').click()
        page.wait_for_timeout(400)
        item_count_after_command = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios.find(s => s.id === JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario).items.length")
        check("supported site-object command reports the edit and changes the plan",
              item_count_after_command == command_baseline["itemCount"] + 1
              and "Added 1" in page.locator("#afOut").inner_text())
        page.locator('[data-af="undo"]').click()
        page.wait_for_timeout(400)
        check("undo reverses a site-object command",
              page.evaluate(
                  "() => JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios.find(s => s.id === JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario).items.length")
              == command_baseline["itemCount"])
        page.fill("#afAsk", "Invent a zoning permit")
        page.locator('[data-af="ask"]').click()
        check("unsupported command is reported without a success-shaped response",
              "can't perform" in page.locator("#afOut").inner_text().lower())
        command_after = page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return {coordinates: s.project.locationCoordinates, parcel: s.project.parcelBoundary,
            scenario: s.activeScenario};
        }""")
        check("property copilot commands preserve the selected property and scenario",
              command_after["coordinates"] == command_baseline["coordinates"]
              and command_after["parcel"] == command_baseline["parcel"]
              and command_after["scenario"] == command_baseline["scenario"])
        land_mode["fema_case"] = "failure"
        land_mode["soil_case"] = "failure"
        page.locator('[data-pl="pz"]').click()
        page.wait_for_function(
            "() => { const s = JSON.parse(localStorage['oregon-estate-planner-v1']).land?.samples; "
            "return s?.length === 9 && s.every(p => p.flood.status === 'unavailable' "
            "&& p.soil.status === 'unavailable'); }",
            timeout=30000)
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis?.sub?.Drainage?.status === 'unavailable'",
            timeout=30000)
        missing_analysis = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        check("missing flood and soil sources stay unavailable in the health dashboard",
              missing_analysis["sub"]["Drainage"]["value"] is None
              and missing_analysis["sub"]["Drainage"]["status"] == "unavailable"
              and missing_analysis["floodRisk"] == "unavailable")
        terrain_mode["case"] = "mixed-slope"
        land_mode["fema_case"] = "all-high"
        land_mode["soil_case"] = "mapped"
        start_analysis(page)
        page.wait_for_function(
            "() => { const a = JSON.parse(localStorage['oregon-estate-planner-v1']).analysis; "
            "return a?.buildabilityVersion === 1 && a.floodMarkers?.length "
            "&& a.floodMarkers.every(marker => marker.status === 'high'); }",
            timeout=30000)
        mixed = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        class_counts = {key: sum(line.count(code) for line in mixed["cells"])
                        for key, code in (("candidate", "g"), ("caution", "y"),
                                          ("constrained", "o"), ("unknown", "?"))}
        check("mixed terrain produces distinct candidate, caution, constrained and unknown classes",
              all(class_counts[key] > 0 for key in ("candidate", "caution", "constrained")))
        check("high FEMA samples render as discrete red point markers, not flood polygons",
              mixed["floodMarkers"] and all(marker["status"] == "high" for marker in mixed["floodMarkers"])
              and page.locator('[data-flood-marker="high"]').count() == len(mixed["floodMarkers"])
              and "point observations, not flood boundaries" in mixed["floodSummary"])
        check("buildability cells and legend identify the four terrain classes",
              page.locator('[data-buildability-class="candidate"]').count() > 0
              and page.locator('[data-buildability-class="caution"]').count() > 0
              and page.locator('[data-buildability-class="constrained"]').count() > 0
              and page.locator('[data-buildability-class="unknown"]').count() == class_counts["unknown"]
              and "Candidate" in page.locator(".property-road-legend").inner_text())
        before_slope_preview = page.evaluate("localStorage['oregon-estate-planner-v1']")
        page.evaluate("""() => {
          window.__slopeOriginalFetch = window.fetch;
          window.__slopeFetches = 0;
          window.fetch = (...args) => { window.__slopeFetches++; return window.__slopeOriginalFetch(...args); };
        }""")
        page.locator('[data-slope-preview-form] [name="limit"]').fill("8")
        page.locator('[data-slope-preview-form] button').click()
        preview_eight = page.locator('[data-slope-preview-cell="within"]').count()
        page.locator('[data-slope-preview-form] [name="limit"]').fill("15")
        check("editing the slope threshold clears the stale preview",
              page.locator("[data-slope-preview-cell]").count() == 0
              and "show the preview again" in page.locator("[data-slope-preview-result]").inner_text())
        page.locator('[data-slope-preview-form] button').click()
        expected = sum(1 for r, line in enumerate(mixed["cells"]) for q, cell in enumerate(line)
                       if cell not in ".?" and mixed["SL"][r * mixed["gw"] + q] is not None
                       and mixed["SL"][r * mixed["gw"] + q] <= 15)
        check("slope what-if uses inclusive threshold and leaves analysis and layout untouched",
              page.locator('[data-slope-preview-cell="within"]').count() == expected
              and expected > preview_eight
              and page.evaluate("localStorage['oregon-estate-planner-v1']") == before_slope_preview
              and "Wetlands, easements, setbacks, flood zones" in page.locator("[data-slope-preview]").inner_text())
        check("slope what-if does not make a network lookup",
              page.evaluate("window.__slopeFetches === 0"))
        page.evaluate("window.fetch = window.__slopeOriginalFetch")
        page.locator('[data-slope-preview-form] [name="limit"]').fill("101")
        page.locator('[data-slope-preview-form] button').click()
        check("out-of-range slope thresholds cannot produce a preview",
              page.locator("[data-slope-preview-cell]").count() == 0)
        edge_preview = page.evaluate("""() => {
          const f = window.__acreforgeSlopePreviewTest.pzSlopePreview;
          const a = {buildabilityVersion: 1, gw: 4, gh: 1, cells: ["ggo."], SL: [8, 8.1, null, null]};
          return {counts: f(a, 8).counts, invalid: f(a, -1) === null && f(a, 101) === null,
            malformed: f({...a, SL: []}, 8) === null};
        }""")
        check("slope what-if includes the exact threshold and rejects missing or invalid data",
              edge_preview["counts"] == {"within": 1, "above": 1, "unknown": 1}
              and edge_preview["invalid"] and edge_preview["malformed"])
        opportunity_result = page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1', saved = JSON.parse(localStorage[key]);
          const a = saved.analysis, opportunities = a.opportunities || [], zones = a.zones || [];
          const inRing = (point, ring) => {
            let inside = false;
            for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
              const p = ring[i], q = ring[j];
              if ((p[1] > point[1]) !== (q[1] > point[1])
                  && point[0] < (q[0] - p[0]) * (point[1] - p[1]) / (q[1] - p[1]) + p[0]) {
                inside = !inside;
              }
            }
            return inside;
          };
          const polygons = saved.project.parcelBoundary.coordinates;
          const contained = opportunities.every(item => {
            const point = [item.lon, item.lat];
            return polygons.some(poly => inRing(point, poly[0])
              && !poly.slice(1).some(ring => inRing(point, ring))
              && (a.cells[item.r] || '')[item.q] && ['g', 'y'].includes(a.cells[item.r][item.q]));
          });
          const zonesContained = zones.every(zone => {
            const point = [zone.lon, zone.lat];
            return polygons.some(poly => inRing(point, poly[0])
              && !poly.slice(1).some(ring => inRing(point, ring))
              && ['g', 'y'].includes((a.cells[zone.r] || '')[zone.q]));
          });
          const zoneSorted = zones.every((zone, index) => !index
            || zones[index - 1].fit > zone.fit
            || (zones[index - 1].fit === zone.fit
              && (zones[index - 1].r < zone.r
                || (zones[index - 1].r === zone.r && zones[index - 1].q <= zone.q))));
          const zoneFits = zones.every(zone => {
            const f = zone.factors, hasRoad = f.road !== null;
            const score = (f.slope * .40 + f.solar * .25 + f.terrain * .10
              + f.opportunity * .15 + (hasRoad ? f.road * .10 : 0)) / (hasRoad ? 1 : .90);
            return zone.fit === Math.round(score) && zone.privacy === null
              && zone.reason && zone.tradeoff && zone.accessStatus
              && f.opportunity >= 0 && f.opportunity <= 100;
          });
          const zoneDistinct = zones.every((zone, index) => zones.slice(0, index).every(previous => {
            const dx = (zone.q - previous.q) * a.grid.cw;
            const dy = (zone.r - previous.r) * a.grid.ch;
            return Math.hypot(dx, dy) >= Math.max(200, Math.max(a.grid.cw, a.grid.ch) * 1.5);
          }));
          const sampledFloodCellsAvoided = zones.every(zone => !a.floodMarkers.some(marker =>
            ['high', 'moderate'].includes(marker.status)
            && Math.floor(marker.q) === zone.q && Math.floor(marker.r) === zone.r));
          return {
            kinds: opportunities.map(item => item.kind),
            sorted: opportunities.every((item, index) => !index || opportunities[index - 1].fit >= item.fit),
            tiesOrdered: opportunities.every((item, index) => !index
              || opportunities[index - 1].fit !== item.fit
              || opportunities[index - 1].kind.localeCompare(item.kind) <= 0),
            contained,
            explained: opportunities.every(item => item.reason && item.missing && item.evidence
              && item.fit >= 0 && item.fit <= 100),
            roadUnknown: opportunities.every(item => item.evidence.includes('no mapped-road lookup')),
            accessUnknown: opportunities.filter(item => ['house', 'shop', 'event'].includes(item.kind))
              .every(item => item.missing.toLowerCase().includes('access')),
            zoneLabels: zones.every((zone, index) => zone.letter === String.fromCharCode(65 + index)
              && zone.name === `Zone ${String.fromCharCode(65 + index)}`),
            zoneSorted, zoneFits, zoneDistinct, zonesContained, sampledFloodCellsAvoided,
            zoneCountBounded: zones.length <= 3,
            zoneRanks: zones.map(zone => zone.fit)
          };
        }""")
        expected_opportunities = {"house", "shop", "pond", "solar", "orchard", "event"}
        check("opportunity detector ranks all six uses with clear rationale and unknown constraints",
              set(opportunity_result["kinds"]) == expected_opportunities
              and opportunity_result["sorted"] and opportunity_result["tiesOrdered"]
              and opportunity_result["explained"]
              and opportunity_result["roadUnknown"] and opportunity_result["accessUnknown"])
        check("opportunity ranking uses stable tie-breaking and stays inside buildable parcel cells",
              opportunity_result["contained"])
        check("build zones are deterministically ranked with explainable factor scores",
              opportunity_result["zoneLabels"] and opportunity_result["zoneSorted"]
              and opportunity_result["zoneFits"] and opportunity_result["zoneDistinct"]
              and opportunity_result["zoneCountBounded"])
        check("build zones stay inside candidate or caution parcel cells and avoid sampled high-risk points",
              opportunity_result["zonesContained"] and opportunity_result["sampledFloodCellsAvoided"])
        check("build-zone cards and accessible map labels match the ranked zone count",
              page.locator("[data-build-zone-card]").count() == len(opportunity_result["zoneRanks"])
              and page.locator("#pzMap [data-build-zone]").evaluate_all(
                  "items => new Set(items.map(item => item.dataset.buildZone)).size")
              == len(opportunity_result["zoneRanks"])
              and all(f"Zone {letter}" in page.locator("[data-build-zones]").inner_text()
                      for letter in "ABC"[:len(opportunity_result["zoneRanks"])])
              and "Privacy is unavailable" in page.locator("[data-build-zones]").inner_text())
        page.locator('#pzMap [data-build-zone="A"]').first.press("Enter")
        check("build-zone map markers support keyboard detail selection",
              "Zone A · screening fit" in page.locator("#pzPop").inner_text()
              and "Privacy:" in page.locator("#pzPop").inner_text())
        terrain_mode["case"] = "all-steep"
        start_analysis(page)
        no_candidate_zones = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        check("fewer than three zones are returned when all mapped terrain is constrained",
              no_candidate_zones["zones"] == []
              and not no_candidate_zones["opportunities"]
              and "No distinct candidate zone" in page.locator("[data-build-zones]").inner_text())
        terrain_mode["case"] = "mixed-slope"
        start_analysis(page)
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis?.zones?.length > 0",
            timeout=30000)
        check("opportunity cards and lettered map markers remain suggestions, not placements",
              page.locator("[data-property-opportunities] [data-opportunity-kind]").count() == 6
              and page.locator("#pzMap [data-property-opportunity]").count() == 6
              and page.locator("#pzMap [data-property-opportunity]").evaluate_all(
                  "items => new Set(items.map(item => item.dataset.gridRow + ',' + item.dataset.gridColumn)).size === items.length")
              and "Suggestions are not placed on the site plan."
              in page.locator("[data-property-opportunities]").inner_text())
        page.locator('#pzMap [data-property-opportunity="house"]').click()
        check("selecting an opportunity marker shows its score and evidence gaps",
              "House site opportunity" in page.locator("#pzPop").inner_text()
              and "Still unknown:" in page.locator("#pzPop").inner_text()
              and "not a surveyed" in page.locator("#pzPop").inner_text())
        page.locator('[data-flood-marker="high"]').first.click()
        check("clicking a flood marker explains its point-only evidence",
              "Flood sample:" in page.locator("#pzPop").inner_text()
              and "Point sample only" in page.locator("#pzPop").inner_text())
        terrain_mode["case"] = "partial-no-data"
        land_mode["fema_case"] = "unmapped"
        start_analysis(page)
        page.wait_for_function(
            "() => { const a = JSON.parse(localStorage['oregon-estate-planner-v1']).analysis; "
            "return a?.buildabilityVersion === 1 && a.cells?.some(line => line.includes('?')) "
            "&& a.floodMarkers?.length && a.floodMarkers.every(marker => marker.status === 'unmapped'); }",
            timeout=30000)
        partial = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        unknown_count = sum(line.count("?") for line in partial["cells"])
        check("partial no-data cells stay unknown while valid terrain remains classified",
              unknown_count > 0
              and page.locator('[data-buildability-class="unknown"]').count() == unknown_count
              and page.locator('[data-buildability-class="candidate"]').count() > 0)
        page.locator('[data-slope-preview-form] button').click()
        check("slope what-if retains unknown cells and excludes outside-parcel cells",
              page.locator('[data-slope-preview-cell="unknown"]').count() == unknown_count
              and page.locator('[data-slope-preview-cell]').count()
              == sum(len(line) - line.count(".") for line in partial["cells"]))
        check("unmapped flood samples are shown as unknown markers, never green clear areas",
              partial["floodMarkers"] and all(marker["status"] == "unmapped"
                                               for marker in partial["floodMarkers"])
              and page.locator('[data-flood-marker="unmapped"]').count() == len(partial["floodMarkers"]))
        terrain_mode["case"] = "no-data"
        start_analysis(page)
        page.wait_for_function(
            "() => document.querySelector('#pzOut')?.textContent.includes('Terrain analysis unavailable')",
            timeout=30000)
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis === null",
            timeout=30000)
        no_data_analysis = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis")
        no_data_message = page.locator("#pzOut").inner_text()
        check("transparent property elevation tiles do not save a flat-ground score",
              no_data_analysis is None and "70% valid elevation coverage" in no_data_message
              and page.locator("[data-property-opportunities]").count() == 0
              and page.locator("[data-slope-preview]").count() == 0)
        terrain_mode["case"] = "mapped"
        land_mode["fema_case"] = "partial-low"
        land_mode["soil_case"] = "mapped"
        start_analysis(page)
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).analysis?.healthVersion === 2",
            timeout=30000)
        check("land lookup exits its busy state after replacement",
              not page.locator('[data-pl="land"]').is_disabled()
              and page.locator("#plLandOut").inner_text() != "Land Data lookup in progress.")
        land_mode["fema_case"] = "partial-low"
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.floodCounts?.low === 1",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        check("partial low-risk coverage remains unavailable overall",
              land["floodRisk"] == "unavailable" and land["floodCounts"]["unmapped"] == 8)
        land_mode["fema_case"] = "unmapped"
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.floodCounts?.unmapped === 9",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        check("unmapped flood samples are not labeled low risk",
              land["floodRisk"] == "unavailable" and "No mapped flood zone" in land["flood"]
              and "FEMA 9/9 responded, 0 zones mapped" in land["coverage"])
        elevation_mode["case"] = "partial-failure"
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.elevationSampleCount === 6",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        check("partial elevation failures are reported without hiding valid samples",
              land["elevationSampleCount"] == 6 and "(6/9 samples)" in land["elev"]
              and "USGS elevation 6/9 responded, 6 mapped" in land["coverage"])
        elevation_mode["case"] = "unmapped"
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.elevationSampleCount === 0",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        check("unmapped elevation responses are not converted to zero feet",
              land["elev"] == "No mapped elevation data" and land["elevationMin"] is None
              and "USGS elevation 9/9 responded, 0 mapped" in land["coverage"])
        elevation_mode["case"] = "mapped"
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.project.parcelBoundary = {source: 'antimeridian smoke test', coordinates: [[[
            [179.8, 43.99], [-179.8, 43.99], [-179.8, 44.01],
            [179.8, 44.01], [179.8, 43.99]
          ]]]};
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.wait_for_timeout(800)
        page.locator('[data-page="planner"]').first.click()
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => Math.abs(JSON.parse(localStorage['oregon-estate-planner-v1']).land?.lon || 0) > 179.5",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        longitudes = [sample["lon"] for sample in land["samples"]]
        check("antimeridian parcels sample on both sides of 180 degrees",
              abs(land["lon"]) > 179.5 and all(abs(lon) > 179 for lon in longitudes)
              and any(lon > 0 for lon in longitudes) and any(lon < 0 for lon in longitudes))
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.project.parcelBoundary = {source: 'multipart with hole smoke test', coordinates: [
            [
              [[-123.01, 43.99], [-122.99, 43.99], [-122.99, 44.01],
               [-123.01, 44.01], [-123.01, 43.99]],
              [[-123.003, 43.997], [-122.997, 43.997], [-122.997, 44.003],
               [-123.003, 44.003], [-123.003, 43.997]]
            ],
            [[[-122.81, 43.99], [-122.80, 43.99], [-122.80, 44.01],
              [-122.81, 44.01], [-122.81, 43.99]]]
          ]};
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.wait_for_timeout(800)
        page.locator('[data-page="planner"]').first.click()
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.parcelParts === 2",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        locations = [(sample["lon"], sample["lat"]) for sample in land["samples"]]
        in_ring = lambda point, ring: page.evaluate("""([p, ring]) => {
          let inside = false;
          for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            const a = ring[i], b = ring[j];
            if ((a[1] > p[1]) !== (b[1] > p[1])
                && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
          }
          return inside;
        }""", [point, ring])
        hole = [[-123.003, 43.997], [-122.997, 43.997], [-122.997, 44.003],
                [-123.003, 44.003], [-123.003, 43.997]]
        check("multipart parcels receive samples on every component",
              land["sampleCount"] == 9 and land["parcelParts"] == 2
              and land["sampledParts"] == 2 and "parts 2/2 sampled" in land["coverage"]
              and any(lon > -122.82 for lon, _ in locations))
        check("hole interiors are excluded from parcel samples",
              all(not in_ring(point, hole) for point in locations))
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          const length = 0.02, slope = 0.37, offset = 0.123;
          const normal = [-slope / Math.hypot(slope, 1) * 0.00004,
                          1 / Math.hypot(slope, 1) * 0.00004];
          const at = (t, side) => [-123.01 + length * t + normal[0] * side * length,
            43.99 + length * (offset + slope * t) + normal[1] * side * length];
          saved.project.parcelBoundary = {source: 'thin diagonal smoke test', coordinates: [[[
            at(0, -1), at(1, -1), at(1, 1), at(0, 1), at(0, -1)
          ]]]};
          delete saved.land;
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.reload()
        page.wait_for_timeout(800)
        page.locator('[data-page="planner"]').first.click()
        page.locator('[data-pl="land"]').click()
        page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).land?.sampleCount === 9",
            timeout=30000)
        land = page.evaluate("() => JSON.parse(localStorage['oregon-estate-planner-v1']).land")
        thin_ring = page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).project.parcelBoundary.coordinates[0][0]")
        check("thin diagonal parcels get distributed interior samples",
              land["sampleCount"] == 9
              and all(in_ring((sample["lon"], sample["lat"]), thin_ring) for sample in land["samples"]))
        page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const saved = JSON.parse(localStorage[key]);
          saved.project.locationCoordinates = {
            lat: 44, lon: -123, state: 'OR', source: 'terrain smoke test'
          };
          localStorage[key] = JSON.stringify(saved);
        }""")
        page.click("[data-page=designer]")
        page.locator('[data-action="toggle-map-view"]').click()
        page.locator('#stateHits path[data-state-map="OR"]').click()
        page.wait_for_selector(".ovbar", timeout=30000)
        page.wait_for_function(
            """() => {
              const status = document.querySelector('#terrainMapStatus')?.textContent || '';
              const zoom = Number(status.match(/Zoom ([\\d.]+)/)?.[1]);
              return status.includes('Map context: 1,000-acre initial square') && zoom >= 13.5;
            }""")
        page.wait_for_timeout(600)
        terrain_status = page.locator("#terrainMapStatus").inner_text()
        terrain_zoom = float(re.search(r"Zoom ([\d.]+)", terrain_status).group(1))
        check("terrain opens on a 1,000-acre map context without changing the editable parcel",
              "View center 44.00000°, -123.00000°" in terrain_status
              and "Location 44.00000°, -123.00000°" in terrain_status
              and terrain_zoom >= 13.5
              and "Map context: 1,000-acre initial square" in terrain_status)
        relief_button = page.locator('[data-action="terrain-3d"]')
        page.wait_for_function("""() => document.querySelector('.ovbar')
          && document.querySelector('[data-action="terrain-3d"]')?.textContent === '3D relief on'
          && document.querySelector('#terrainMapStatus')?.textContent.includes('3D terrain on')""")
        relief_button.click()
        page.wait_for_function("""() => document.querySelector('[data-action="terrain-3d"]')?.textContent === '3D relief off'
          && document.querySelector('#terrainMapStatus')?.textContent.includes('3D terrain off')""")
        check("3D terrain can be toggled off after map initialization",
              relief_button.inner_text() == "3D relief off")
        relief_button.click()
        page.wait_for_function("""() => document.querySelector('[data-action="terrain-3d"]')?.textContent === '3D relief on'
          && document.querySelector('#terrainMapStatus')?.textContent.includes('3D terrain on')""")
        check("3D terrain can be toggled on after map initialization",
              relief_button.inner_text() == "3D relief on")
        page.wait_for_function(
            "() => document.querySelector('#terrainWorldStatus')?.dataset.cameraPitch === '55'")
        camera = page.locator("#terrainCameraMode")
        world_status = page.locator("#terrainWorldStatus")
        page.wait_for_function(
            "() => document.querySelector('#terrainCanvas canvas')?.dataset.cameraReady === 'true'")
        check("orbit, walkthrough, and fly camera modes are available by name",
              [camera.locator("option").nth(i).get_attribute("value") for i in range(3)]
              == ["orbit", "walkthrough", "fly"])
        camera.select_option("walkthrough")
        page.wait_for_function("""() => {
          const status = document.querySelector('#terrainWorldStatus');
          return status?.dataset.cameraMode === 'walkthrough'
            && Number(status.dataset.cameraPitch) >= 65
            && Number(status.dataset.cameraPitch) <= 70;
        }""")
        page.wait_for_function(
            "() => !window.__acreforgeSpatialTest.terrainMap().isMoving()")
        center_before_walk = page.evaluate("""() => {
          const center = window.__acreforgeSpatialTest.terrainMap().getCenter();
          return [center.lng, center.lat];
        }""")
        terrain_canvas = page.locator("#terrainCanvas canvas")
        terrain_canvas.focus()
        page.keyboard.press("w")
        page.wait_for_function(
            """before => {
              const center = window.__acreforgeSpatialTest.terrainMap().getCenter();
              return Math.hypot(center.lng - before[0], center.lat - before[1]) > 1e-6;
            }""",
            arg=center_before_walk, timeout=5000)
        check("walkthrough keyboard movement navigates the terrain map",
              page.locator("#terrainWorldStatus").get_attribute("data-camera-mode") == "walkthrough")
        camera.select_option("fly")
        page.wait_for_function("""() => {
          const status = document.querySelector('#terrainWorldStatus');
          return status?.dataset.cameraMode === 'fly'
            && Number(status.dataset.cameraPitch) >= 74;
        }""")
        page.wait_for_function(
            "() => !window.__acreforgeSpatialTest.terrainMap().isMoving()")
        bearing_before_fly = page.evaluate(
            "() => window.__acreforgeSpatialTest.terrainMap().getBearing()")
        terrain_canvas.focus()
        page.keyboard.press("d")
        page.wait_for_function(
            """before => {
              const bearing = window.__acreforgeSpatialTest.terrainMap().getBearing();
              return Math.abs(((bearing - before + 540) % 360) - 180) > 1;
            }""",
            arg=bearing_before_fly, timeout=5000)
        camera.select_option("orbit")
        check("fly keyboard turning works and orbit remains selectable",
              world_status.get_attribute("data-camera-mode") == "orbit"
              and "Arrow-key map navigation remains available" in page.locator("#terrainCameraHelp").inner_text())
        center_before_drag = page.locator("#terrainMapStatus").inner_text()
        map_box = terrain_canvas.bounding_box()
        page.mouse.move(map_box["x"] + map_box["width"] * .55,
                        map_box["y"] + map_box["height"] * .55)
        page.mouse.down()
        page.mouse.move(map_box["x"] + map_box["width"] * .62,
                        map_box["y"] + map_box["height"] * .60, steps=4)
        page.mouse.up()
        page.wait_for_function(
            "(before) => document.querySelector('#terrainMapStatus')?.textContent !== before",
            arg=center_before_drag, timeout=5000)
        check("pointer orbit and pan remain responsive after camera-mode changes",
              page.locator("#terrainWorldStatus").get_attribute("data-proposed-layer") == "true")
        check("unavailable map references are disclosed as optional and incomplete",
              "Existing map references are optional and incomplete" in world_status.inner_text()
              and "Mapped context is off" in page.locator("#terrainOsmStatus").inner_text())
        for _ in range(6):
            page.locator(".maplibregl-ctrl-zoom-in").evaluate("el => el.click()")
            page.wait_for_timeout(150)
        page.locator('[data-ov="slope"]').check()
        page.locator('[data-ov="contours"]').check()
        page.locator('[data-ov="hillshade"]').check()
        page.locator('[data-ov="flood"]').check()
        page.locator('[data-ov="wet"]').check()
        page.wait_for_function("document.querySelector('#terrainAnalysisStatus')?.textContent.includes('Elevation sampled')", timeout=30000)
        check("hillshade image layer renders from sampled elevation",
              page.locator('[data-ov="hillshade"]').is_checked()
              and "hillshade: 315° NW light" in page.locator("#terrainAnalysisStatus").inner_text())
        for layer, value in [("slope", "50"), ("hillshade", "40"),
                             ("flood", "45"), ("wet", "55")]:
            page.locator(f'[data-ov-op="{layer}"]').evaluate("(e, value) => { e.value = value; e.dispatchEvent(new Event('input', {bubbles:true})); }", value)
        prefs = page.evaluate("() => JSON.parse(localStorage['acreforge-layerprefs'])")
        expected = {"slope": True, "contours": True, "hillshade": True,
                    "flood": True, "wet": True}
        check("terrain overlays and opacity save",
              all(prefs["analysis"].get(layer) == value
                  for layer, value in expected.items())
              and prefs["op"]["slope"] == 0.5
              and prefs["op"]["hillshade"] == 0.4
              and prefs["op"]["flood"] == 0.45
              and prefs["op"]["wet"] == 0.55)
        terrain_mode["case"] = "no-data"
        for _ in range(8):
            page.locator(".maplibregl-ctrl-zoom-out").evaluate("el => el.click()")
            page.wait_for_timeout(120)
        no_data_state = page.wait_for_function("""() => {
          const text=document.querySelector('#terrainAnalysisStatus')?.textContent || '';
          const relief=document.querySelector('[data-action="terrain-3d"]')?.textContent;
          return text.includes('Elevation no-data') && relief === '3D relief off'
            ? {text,relief} : false;
        }""", timeout=30000).json_value()
        check("terrain no-data is not shown as flat mapped ground",
              "unknown terrain is not shown as level ground" in no_data_state["text"])
        failure_calls = terrain_mode["calls"]
        page.evaluate("""() => {
          const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
          window.__terrainImageSrc = descriptor;
          Object.defineProperty(HTMLImageElement.prototype, 'src', {
            ...descriptor,
            set(value) { descriptor.set.call(this, value + '?failure-test=' + Date.now()); }
          });
        }""")
        terrain_mode["case"] = "failure"
        page.locator(".maplibregl-ctrl-zoom-in").evaluate("el => el.click()")
        failure_state = page.wait_for_function("""() => {
          const text=document.querySelector('#terrainAnalysisStatus')?.textContent || '';
          const relief=document.querySelector('[data-action="terrain-3d"]')?.textContent;
          return text.includes('Terrain elevation unavailable') && relief === '3D relief off'
            ? {text,relief} : false;
        }""", timeout=30000).json_value()
        page.evaluate("""() => {
          if (window.__terrainImageSrc) {
            Object.defineProperty(HTMLImageElement.prototype, 'src', window.__terrainImageSrc);
            delete window.__terrainImageSrc;
          }
        }""")
        check("terrain tile failures are visible and disable relief",
              terrain_mode["calls"] > failure_calls
              and "hidden" in failure_state["text"])
        terrain_mode["case"] = "mapped"
        imported_terrain = page.evaluate("""async () => {
          const spatial = window.__acreforgeSpatialTest;
          const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
          Object.defineProperty(HTMLImageElement.prototype, 'src', {
            ...descriptor,
            set(value) { descriptor.set.call(this, value + '?terrain-import=' + crypto.randomUUID()); }
          });
          try { await spatial.terrainImportReal(); }
          finally { Object.defineProperty(HTMLImageElement.prototype, 'src', descriptor); }
          const terrain = spatial.terrainData();
          return {
            cols: terrain.cols, rows: terrain.rows, samples: terrain.sampleCount,
            validCount: terrain.valid.filter(Boolean).length,
            extent: spatial.terrainExtent(terrain),
            range: terrain.elevationRangeFeet,
            status: spatial.terrainSampleStatus(terrain)
          };
        }""")
        check("real terrain import records extent, grid resolution, sample coverage, and feet conversion",
              imported_terrain["samples"] == imported_terrain["cols"] * imported_terrain["rows"]
              and imported_terrain["validCount"] == imported_terrain["samples"]
              and imported_terrain["extent"]["w"] > 0
              and imported_terrain["extent"]["h"] > 0
              and 300 < imported_terrain["range"]["min"] < 350
              and 500 < imported_terrain["range"]["max"] < 550
              and "sample nodes (100% coverage)" in imported_terrain["status"]
              and "spacing" in imported_terrain["status"])
        terrain_mode["case"] = "partial-import"
        partial_terrain = page.evaluate("""async () => {
          const spatial = window.__acreforgeSpatialTest;
          const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
          Object.defineProperty(HTMLImageElement.prototype, 'src', {
            ...descriptor,
            set(value) { descriptor.set.call(this, value + '?terrain-import=' + crypto.randomUUID()); }
          });
          try { await spatial.terrainImportReal(); }
          finally { Object.defineProperty(HTMLImageElement.prototype, 'src', descriptor); }
          const terrain = spatial.terrainData();
          let validCells = 0, missingCells = 0;
          for (let y = 0; y < terrain.rows - 1; y++) {
            for (let x = 0; x < terrain.cols - 1; x++) {
              if (spatial.terrainCellValid(terrain, x, y)) validCells++;
              else missingCells++;
            }
          }
          const svg = new DOMParser().parseFromString(
            spatial.terrainOverlaySvg(), 'image/svg+xml');
          let expectedRendered = 0;
          for (let y = 0; y < terrain.rows - 1; y++) {
            for (let x = 0; x < terrain.cols - 1; x++) {
              const i = y * terrain.cols + x;
              if (spatial.terrainCellValid(terrain, x, y)
                  && Math.abs((terrain.h[i] + terrain.h[i + 1]
                    + terrain.h[i + terrain.cols]
                    + terrain.h[i + terrain.cols + 1]) / 4) >= 0.25) {
                expectedRendered++;
              }
            }
          }
          return {
            validCount: terrain.valid.filter(Boolean).length,
            total: terrain.valid.length, validCells, missingCells,
            renderedCells: svg.querySelectorAll('rect').length, expectedRendered,
            status: spatial.terrainSampleStatus(terrain)
          };
        }""")
        check("partial terrain no-data is masked consistently from flat and 3D terrain cells",
              0 < partial_terrain["validCount"] < partial_terrain["total"]
              and partial_terrain["missingCells"] > 0
              and partial_terrain["renderedCells"] == partial_terrain["expectedRendered"]
              and "no-data cells are masked" in partial_terrain["status"])
        terrain_before_failure = page.evaluate(
            "() => JSON.stringify(window.__acreforgeSpatialTest.terrainData())")
        terrain_mode["case"] = "no-data"
        page.evaluate("""async () => {
          const spatial = window.__acreforgeSpatialTest;
          const descriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
          Object.defineProperty(HTMLImageElement.prototype, 'src', {
            ...descriptor,
            set(value) { descriptor.set.call(this, value + '?terrain-import=' + crypto.randomUUID()); }
          });
          try { await spatial.terrainImportReal(); }
          finally { Object.defineProperty(HTMLImageElement.prototype, 'src', descriptor); }
        }""")
        terrain_after_failure = page.evaluate(
            "() => JSON.stringify(window.__acreforgeSpatialTest.terrainData())")
        check("fully unmapped elevation leaves the previous terrain intact",
              terrain_after_failure == terrain_before_failure)
        terrain_mode["case"] = "mapped"
        page.reload()
        page.wait_for_timeout(800)
        page.locator('[data-page=designer]').first.click()
        page.locator('[data-action="toggle-map-view"]').click()
        page.locator('#stateHits path[data-state-map="OR"]').click()
        page.wait_for_selector(".ovbar", timeout=30000)
        check("overlay settings restore after reload",
              all(page.locator(f'[data-ov="{layer}"]').is_checked()
                  for layer in expected)
              and page.locator('[data-ov-op="hillshade"]').input_value() == "40"
              and page.locator('[data-ov-op="flood"]').input_value() == "45"
              and page.locator('[data-ov-op="wet"]').input_value() == "55")
        style_reload_layers = [
            "estate-feature-fill", "estate-feature-line", "estate-landmark-dot",
            "estate-draft-fill", "estate-draft-line", "estate-location-dot",
            "osm-context-fill", "osm-context-extrusion", "osm-context-line",
            "osm-context-tree", "proposed-site-fill", "proposed-site-line",
            "proposed-site-road-line", "proposed-site-extrusion",
            "proposed-site-trees", "supplied-reference-fill",
            "supplied-reference-line", "supplied-reference-point",
            "ov-flood", "ov-wet", "terrain-analysis-slope",
            "terrain-analysis-contours", "terrain-analysis-hillshade",
        ]
        page.evaluate("""() => {
          const map = window.__acreforgeSpatialTest.terrainMap();
          const style = JSON.parse(JSON.stringify(map.getStyle()));
          const baseSources = new Set(['usgs-topo', 'usgs-imagery', 'elevation-dem']);
          const baseLayers = new Set(['usgs-topo', 'usgs-imagery']);
          style.sources = Object.fromEntries(
            Object.entries(style.sources).filter(([id]) => baseSources.has(id)));
          style.layers = style.layers.filter(layer => baseLayers.has(layer.id));
          window.__terrainStyleReloads = 0;
          window.__terrainStyleData = 0;
          map.on('style.load', () => window.__terrainStyleReloads++);
          map.on('styledata', () => window.__terrainStyleData++);
          window.__terrainBaseStyle = style;
          map.setStyle(style);
        }""")
        page.wait_for_function(
            """() => window.__terrainStyleData > 0
              && window.__acreforgeSpatialTest.terrainMap().getLayer('proposed-site-fill')""",
            timeout=15000)
        page.wait_for_function(
            """layers => {
              const map = window.__acreforgeSpatialTest.terrainMap();
              const style = map.getStyle();
              return layers.every(id => map.getLayer(id))
                && layers.every(id => style.layers.filter(layer => layer.id === id).length === 1)
                && document.querySelectorAll('.ovbar').length === 1
                && document.querySelectorAll('.ovbar [data-ov]').length === 5;
            }""",
            arg=style_reload_layers, timeout=10000)
        check("default style diff restores map layers and controls without style.load",
              page.evaluate("""layers => {
                const map = window.__acreforgeSpatialTest.terrainMap();
                const style = map.getStyle();
                return window.__terrainStyleData > 0
                  && window.__terrainStyleReloads === 0
                  && layers.every(id => map.getLayer(id))
                  && layers.every(id => style.layers.filter(layer => layer.id === id).length === 1)
                  && document.querySelectorAll('.ovbar').length === 1
                  && document.querySelectorAll('.ovbar [data-ov]').length === 5;
              }""", style_reload_layers))
        page.evaluate("""() => {
          const map = window.__acreforgeSpatialTest.terrainMap();
          map.setStyle(window.__terrainBaseStyle, {diff: false});
        }""")
        page.wait_for_function(
            "window.__terrainStyleReloads === 1", timeout=15000)
        page.wait_for_function(
            """layers => {
              const map = window.__acreforgeSpatialTest.terrainMap();
              const style = map.getStyle();
              return layers.every(id => map.getLayer(id))
                && layers.every(id => style.layers.filter(layer => layer.id === id).length === 1)
                && document.querySelectorAll('.ovbar').length === 1
                && document.querySelectorAll('.ovbar [data-ov]').length === 5;
            }""",
            arg=style_reload_layers, timeout=10000)
        page.evaluate("""() => {
          const map = window.__acreforgeSpatialTest.terrainMap();
          map.setStyle(window.__terrainBaseStyle, {diff: false});
        }""")
        page.wait_for_function(
            "window.__terrainStyleReloads === 2", timeout=15000)
        page.wait_for_function(
            """layers => {
              const map = window.__acreforgeSpatialTest.terrainMap();
              const style = map.getStyle();
              return layers.every(id => map.getLayer(id))
                && layers.every(id => style.layers.filter(layer => layer.id === id).length === 1)
                && document.querySelectorAll('.ovbar').length === 1
                && document.querySelectorAll('.ovbar [data-ov]').length === 5;
            }""",
            arg=style_reload_layers, timeout=10000)
        flood_overlay = page.locator('[data-ov="flood"]')
        flood_overlay.uncheck()
        page.wait_for_function(
            """() => window.__acreforgeSpatialTest.terrainMap()
              .getLayoutProperty('ov-flood', 'visibility') === 'none'""")
        flood_overlay.check()
        page.wait_for_function(
            """() => window.__acreforgeSpatialTest.terrainMap()
              .getLayoutProperty('ov-flood', 'visibility') === 'visible'""")
        page.locator("#terrainCameraMode").select_option("walkthrough")
        page.wait_for_function(
            "() => document.querySelector('#terrainWorldStatus')?.dataset.cameraMode === 'walkthrough'",
            timeout=5000)
        center_before_reload_key = page.evaluate("""() => {
          const center = window.__acreforgeSpatialTest.terrainMap().getCenter();
          return [center.lng, center.lat];
        }""")
        page.locator("#terrainCanvas canvas").focus()
        page.keyboard.press("w")
        page.wait_for_function(
            """before => {
              const center = window.__acreforgeSpatialTest.terrainMap().getCenter();
              return Math.hypot(center.lng - before[0], center.lat - before[1]) > 1e-6;
            }""",
            arg=center_before_reload_key, timeout=5000)
        check("repeated style loads restore map layers and keep controls responsive without duplicates",
              page.evaluate("""layers => {
                const map = window.__acreforgeSpatialTest.terrainMap();
                const style = map.getStyle();
                return window.__terrainStyleReloads === 2
                  && layers.every(id => map.getLayer(id))
                  && layers.every(id => style.layers.filter(layer => layer.id === id).length === 1)
                  && document.querySelectorAll('.ovbar').length === 1
                  && document.querySelectorAll('.ovbar [data-ov]').length === 5
                  && document.querySelector('#terrainWorldStatus')?.dataset.cameraMode === 'walkthrough';
              }""", style_reload_layers))
        world_context = b.new_context(service_workers="block")
        world_page = world_context.new_page()
        world_page.add_init_script("""localStorage.setItem('acreforge-guide-seen','1');
          localStorage.setItem('oregon-estate-planner-v1', JSON.stringify({
            schemaVersion: 1,
            project: {name: '3D World test', acres: 80,
              locationCoordinates: {lat: 44, lon: -123, state: 'OR'}},
            scenarios: [{id: 'base', name: 'World test', fields: [],
              items: [
                {id: 'world-barn', type: 'barn', name: 'World barn',
                  x: 120, y: 180, w: 60, h: 40, height: 18},
                {id: 'world-tree', type: 'tree', name: 'World tree',
                  x: 240, y: 280, w: 20, h: 20, height: 18}
              ],
              roads: [{id: 'world-road', type: 'gravel',
                pts: [[100, 100], [500, 100]], curve: false}],
              waters: [{id: 'world-water', type: 'creek',
                pts: [[100, 300], [500, 300]], meander: false}]
            }],
            activeScenario: 'base'
          }));""")
        world_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        world_page.click("[data-page=designer]")
        world_page.locator('[data-action="toggle-map-view"]').click()
        world_page.locator('#stateHits path[data-state-map="OR"]').click()
        world_page.wait_for_selector("#terrainWorldStatus", timeout=30000)
        world_page.wait_for_function(
            "() => document.querySelector('#terrainWorldStatus')?.dataset.proposedLayer === 'true'")
        world_status = world_page.locator("#terrainWorldStatus")
        check("3D World aligns proposed buildings, trees, roads, and water to the selected property",
              int(world_status.get_attribute("data-proposed-features") or "0") >= 4
              and {"building", "tree", "road", "water"}.issubset(
                  set((world_status.get_attribute("data-proposed-kinds") or "").split(",")))
              and world_status.get_attribute("data-plan-reference") == "location"
              and "aligned" in world_status.inner_text())
        check("3D map context expands independently of the 80-acre buildable plan",
              "Map context: 1,000-acre initial square" in world_page.locator("#terrainMapStatus").inner_text()
              and "editable plan: 80.00 acres" in world_page.locator("#terrainMapStatus").inner_text())
        proposed_alignment = world_page.evaluate("""() => {
          const spatial = window.__acreforgeSpatialTest;
          const before = localStorage['oregon-estate-planner-v1'];
          const anchor = spatial.terrainPlanAnchor();
          const features = spatial.terrainPlanCollection().features;
          const feature = kind => features.find(item => item.properties.kind === kind);
          const toPlan = point => spatial.geoToPlanPoint(anchor, point);
          const building = feature('building').geometry.coordinates[0]
            .slice(0, -1).map(toPlan);
          const buildingCenter = building.reduce(
            (sum, point) => [sum[0] + point[0] / building.length,
              sum[1] + point[1] / building.length], [0, 0]);
          const road = feature('road').geometry.coordinates.map(toPlan);
          const tree = toPlan(feature('tree').geometry.coordinates);
          const water = feature('water').geometry.coordinates[0].map(toPlan);
          return {
            buildingCenter, roadStart: road[0], roadEnd: road[road.length - 1], tree,
            waterBounds: [
              Math.min(...water.map(point => point[0])),
              Math.max(...water.map(point => point[0]))
            ],
            unchanged: before === localStorage['oregon-estate-planner-v1']
          };
        }""")
        check("proposed 3D geometries round-trip to their saved plan coordinates without mutation",
              math.dist(proposed_alignment["buildingCenter"], [150, 200]) <= 1
              and math.dist(proposed_alignment["tree"], [250, 290]) <= 1
              and math.dist(proposed_alignment["roadStart"], [100, 100]) <= 1
              and math.dist(proposed_alignment["roadEnd"], [500, 100]) <= 1
              and proposed_alignment["waterBounds"][0] <= 100
              and proposed_alignment["waterBounds"][1] >= 500
              and proposed_alignment["unchanged"])
        source_status = world_page.evaluate("""() => {
          const t = window.__acreforgeSourceTest, log = t.mapSourceLog, now = Date.now();
          const el = document.querySelector('#mapSourceStatus');
          const rendered = el ? el.textContent : '';
          const out = {rendered, idle: t.mapSourceStatusText(now)};
          log.osm = {state: 'loaded', at: now - 60000, count: 12};
          out.success = t.mapSourceStatusText(now);
          log.osm = {state: 'empty', at: now - 60000, count: 0};
          out.empty = t.mapSourceStatusText(now);
          log.osm = {state: 'loaded', at: now - t.MAP_SOURCE_STALE_MS - 120000, count: 12};
          out.stale = t.mapSourceStatusText(now);
          log.osm = {state: 'failed', failedAt: now, error: 'HTTP 503', at: now - 120000, count: 12};
          out.failed = t.mapSourceStatusText(now);
          log.osm = {state: 'idle'};
          return out;
        }""")
        check("source status reports origin, layers, and no-request idle state",
              "Spatial origin:" in source_status["rendered"]
              and "not requested" in source_status["idle"]
              and "Layers available" in source_status["idle"])
        check("source status distinguishes success, empty, stale, and failed responses",
              "12 features retrieved 1 min ago" in source_status["success"]
              and "not a complete inventory" in source_status["success"]
              and "not proof of none" in source_status["empty"]
              and "Stale" in source_status["stale"]
              and "request failed (HTTP 503)" in source_status["failed"]
              and "may be stale" in source_status["failed"])
        status_requests = []
        world_page.on("request", lambda r: status_requests.append(r.url)
                      if "overpass" in r.url else None)
        world_page.evaluate("() => { window.__acreforgeSourceTest.mapSourceStatusText(); }")
        world_page.wait_for_timeout(300)
        world_context.set_offline(True)
        world_page.wait_for_timeout(300)
        offline_text = world_page.locator("#mapSourceStatus").inner_text()
        world_context.set_offline(False)
        check("rendering source status makes no map-data requests and offline keeps editing available",
              not status_requests and "Offline" in offline_text
              and "local editing remains available" in offline_text)
        dense = world_page.evaluate("""() => {
          const t = window.__acreforgeSourceTest;
          const geom = Array.from({length: 2000}, (_, i) => ({lon: -122 + i * 1e-6, lat: 45 + Math.sin(i / 50) * 1e-6}));
          const elements = [{type: "way", id: 1, tags: {highway: "residential"}, geometry: geom}];
          const ring = Array.from({length: 1000}, (_, i) => ({lon: -122 + Math.cos(i / 1000 * 6.2832) * 1e-3, lat: 45 + Math.sin(i / 1000 * 6.2832) * 1e-3}));
          elements.push({type: "way", id: 2, tags: {building: "house"}, geometry: ring});
          for (let i = 0; i < 4100; i++) elements.push({type: "node", id: 100 + i, lon: -122, lat: 45, tags: {natural: "tree"}});
          const features = t.parseTerrainOsm({elements});
          t.setOsm(features);
          const display = t.terrainOsmCollection().features;
          const road = features.find(f => f.geometry.type === "LineString"), droad = display.find(f => f.geometry.type === "LineString");
          const home = features.find(f => f.geometry.type === "Polygon"), dhome = display.find(f => f.geometry.type === "Polygon");
          return {src: road.geometry.coordinates.length, disp: droad.geometry.coordinates.length,
            srcRing: home.geometry.coordinates[0].length, dispRing: dhome.geometry.coordinates[0].length,
            closed: JSON.stringify(dhome.geometry.coordinates[0][0]) === JSON.stringify(dhome.geometry.coordinates[0].at(-1)),
            source: droad.properties.source, total: features.length, shown: display.length, truncated: t.getTruncated()};
        }""")
        check("dense OSM geometry is simplified for display only with disclosed cap",
              dense["src"] == 2000 and dense["disp"] < 100 and dense["srcRing"] == 1001
              and 4 <= dense["dispRing"] < 400 and dense["closed"]
              and dense["source"] == "OpenStreetMap"
              and dense["total"] == 4000 and dense["shown"] == 4000 and dense["truncated"] > 0)
        world_context.close()
        world_context = b.new_context(service_workers="block")
        world_page = world_context.new_page()
        world_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        world_page.goto("http://127.0.0.1:8766")
        world_page.click("[data-page=designer]")
        world_page.locator('[data-action="toggle-map-view"]').click()
        world_page.locator('#stateHits path[data-state-map="OR"]').click()
        world_page.wait_for_selector("#terrainWorldStatus", timeout=30000)
        world_page.wait_for_function(
            "() => document.querySelector('#terrainWorldStatus')?.dataset.proposedLayer === 'true'")
        check("missing property georeference is disclosed without inventing feature placement",
              world_page.locator("#terrainWorldStatus").get_attribute("data-plan-reference")
              == "unavailable"
              and world_page.locator("#terrainWorldStatus").get_attribute("data-proposed-features") == "0"
              and "not georeferenced" in world_page.locator("#terrainWorldStatus").inner_text())
        world_context.close()
        ho_context = b.new_context(service_workers="block", accept_downloads=True)
        ho_page = ho_context.new_page()
        ho_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        ho_requests = []
        ho_page.on("request", lambda r: ho_requests.append(r.url) if not r.url.startswith("http://127.0.0.1") and not r.url.startswith("http://localhost") and not r.url.startswith("data:") and not r.url.startswith("blob:") else None)
        ho_page.on("pageerror", lambda e: print("HO ERR", e))
        ho_page.goto("http://127.0.0.1:8766")
        ho_page.wait_for_timeout(500)
        ho_page.locator("#nav [data-page=reports]").click()
        before_ho = len(ho_requests)
        with ho_page.expect_download() as dl_info:
            ho_page.locator('[data-action="handoff"]').first.click()
        ho_path = dl_info.value.path()
        ho_text = open(ho_path, encoding="utf-8").read()
        check("conceptual handoff is a local labeled file with units, exclusions and review checklist",
              "NOT FOR CONSTRUCTION" in ho_text and "Units: feet" in ho_text
              and "EXCLUSIONS" in ho_text and "PROFESSIONAL REVIEW CHECKLIST" in ho_text
              and "nothing was uploaded" in ho_text and len(ho_requests) == before_ho)
        with ho_page.expect_download() as dl2:
            ho_page.locator('[data-action="handoff-csv"]').first.click()
        ho_csv = open(dl2.value.path(), encoding="utf-8").read()
        check("handoff CSV carries conceptual label, units and review checklist without network use",
              "NOT FOR CONSTRUCTION" in ho_csv and "Units: feet" in ho_csv and "Review checklist" in ho_csv
              and len(ho_requests) == before_ho)
        with ho_page.expect_download() as backup_info:
            ho_page.locator('[data-action="export"]').first.click()
        backup = json.load(open(backup_info.value.path(), encoding="utf-8"))
        check("JSON project export carries conceptual handoff provenance and remains a project backup",
              backup["schemaVersion"] == 1 and backup["scenarios"]
              and backup["handoff"]["label"] == "CONCEPTUAL ONLY - NOT FOR CONSTRUCTION"
              and backup["handoff"]["units"] == "feet"
              and "boundary" in backup["handoff"] and backup["handoff"]["exclusions"]
              and backup["handoff"]["reviewChecklist"] and len(ho_requests) == before_ho)
        ho_page.locator("#nav [data-page=reports]").click()
        ho_page.locator("#content .tabbar [data-page=compliance]").click()
        ho_page.locator('[data-task="EFU zoning & farm use"]').check()
        ho_page.locator("#content .tabbar [data-page=reports]").click()
        ho_page.evaluate("window.__printCalls=0;window.print=()=>window.__printCalls++")
        report_text = ho_page.locator("#content").inner_text()
        open_questions = ho_page.locator("[data-open-questions]").inner_text()
        check("concept report identifies project, selected scenario, export time and measurement units",
              "AcreForge" in report_text and "Starter concept" in report_text
              and "Report / export date" in report_text and "feet" in report_text
              and "acres" in report_text and "USD" in report_text)
        report_lower = report_text.lower()
        check("concept report distinguishes saved property assumptions from modeled estimates",
              "property assumptions · saved project inputs" in report_lower
              and "boundary basis" in report_lower and "land allocation · modeled estimates" in report_lower
              and "not independently verified property facts" in report_lower)
        check("concept report contains an accessible site schematic and building concepts",
              ho_page.locator('[data-report-layout] svg[role="img"]').count() == 1
              and "Conceptual site layout schematic" in ho_page.locator(
                  '[data-report-layout] svg').get_attribute("aria-label")
              and ho_page.locator("[data-building-concepts]").count() == 1
              and "20-Stall Main Barn" in ho_page.locator("[data-building-concepts]").inner_text())
        check("due-diligence report shows open questions and omits completed items",
              "Septic feasibility" in open_questions
              and "EFU zoning & farm use" not in open_questions
              and "does not verify a requirement" in report_text)
        check("cost assumptions separate object subtotal, contingency and conceptual estimate",
              "Object-cost subtotal" in report_text and "Contingency assumption" in report_text
              and "Illustrative USD only" in report_text and "not bids" in report_text)
        ho_page.locator('[data-action="print"]').click()
        ho_page.emulate_media(media="print")
        print_break = ho_page.locator("[data-concept-report]").evaluate(
            "el => getComputedStyle(el).breakInside")
        ho_page.emulate_media(media="screen")
        check("print-ready report retains caveats, local print flow, and multipage legibility",
              "not for construction" in report_lower
              and "does not depict a verified parcel boundary" in report_lower
              and "grading, drainage, structural work" in report_lower
              and "licensed professionals" in report_lower
              and "acreforge does not upload this report" in report_lower
              and ho_page.evaluate("window.__printCalls") >= 1
              and print_break == "auto")
        ho_page.locator("#nav [data-page=designer]").click()
        ho_page.wait_for_selector('[data-sx="dxf"]', timeout=30000)
        before_export_requests = len(ho_requests)
        with ho_page.expect_download() as dxf_info:
            ho_page.locator('[data-sx="dxf"]').click()
        dxf_text = open(dxf_info.value.path(), encoding="utf-8").read()
        check("site-plan DXF includes conceptual disclaimer and units and exports locally",
              "AcreForge CONCEPTUAL export" in dxf_text and "NOT FOR CONSTRUCTION" in dxf_text
              and "$INSUNITS" in dxf_text and len(ho_requests) == before_export_requests)
        with ho_page.expect_download() as pdf_info:
            ho_page.locator('[data-sx="pdf"]').click()
        pdf_data = open(pdf_info.value.path(), "rb").read()
        check("site-plan PDF exports locally as a valid PDF", pdf_data.startswith(b"%PDF-")
              and len(pdf_data) > 1024 and len(ho_requests) == before_export_requests)
        ho_context.close()
        ai_context = b.new_context(service_workers="block")
        ai_page = ai_context.new_page()
        ai_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        ai_errors = []
        ai_page.on("pageerror", lambda e: ai_errors.append(str(e)))
        ai_mode = {"mode": "ok"}
        ai_calls = []
        ai_routes = []

        def ai_handler(route):
            ai_routes.append(route)
            ai_calls.append(route.request.headers.get("authorization", ""))
            mode = ai_mode["mode"]
            if mode == "fail":
                route.fulfill(status=503, body="down")
            elif mode == "hang":
                return
            else:
                objs = {
                    "ok": [{"type": "barn", "name": "AI barn", "x": 100, "y": 100, "w": 40, "h": 30},
                           {"type": "barn", "name": "Out", "x": -50, "y": 10, "w": 40, "h": 30},
                           {"type": "nonsense", "name": "Bad", "x": 300, "y": 300, "w": 20, "h": 20}],
                    "bad": [{"type": "barn", "name": "Out", "x": 1e9, "y": 0, "w": 40, "h": 30}],
                }[mode] if mode != "malformed" else None
                content = "not json{" if mode == "malformed" else json.dumps({"objects": objs, "notes": "n"})
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"choices": [{"message": {"content": content}}]}))
        ai_page.route("https://ai.example.test/**", ai_handler)
        ai_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        ai_page.wait_for_timeout(500)
        ai_page.locator('[data-page="planner"]').first.click()

        def ai_request():
            ai_page.locator("#aiEndpoint").fill("https://ai.example.test/v1/chat")
            ai_page.locator("#aiModel").fill("test-model")
            ai_page.locator("#aiKey").fill("sk-test")
            ai_page.locator("#aiPrompt").fill("Add a barn")
            ai_page.locator('[data-pl="ai-request"]').click()

        base_count = ai_page.evaluate("() => window.__acreforgeSourceTest.itemCount()")
        ai_page.locator('[data-pl="ai-request"]').click()
        no_consent = ai_page.locator("[data-ai-status]").inner_text()
        ai_page.locator("#aiConsent").check()
        ai_request()
        ai_page.wait_for_selector("[data-ai-proposal]")
        preview_count = ai_page.evaluate("() => window.__acreforgeSourceTest.itemCount()")
        proposal_text = ai_page.locator("[data-ai-proposal]").inner_text()
        check("AI proposal requires consent, is validated, and does not mutate the plan before approval",
              "Consent is required" in no_consent
              and ai_calls == ["Bearer sk-test"] and preview_count == base_count
              and "AI barn" in proposal_text and "Outside the property extent" in proposal_text
              and "Unsupported item type" in proposal_text and "not applied yet" in proposal_text)
        ai_page.locator('[data-pl="ai-discard"]').click()
        check("discarding an AI proposal leaves the plan unchanged",
              ai_page.evaluate("() => window.__acreforgeSourceTest.itemCount()") == base_count
              and ai_page.locator("[data-ai-proposal]").count() == 0)
        ai_request()
        ai_page.wait_for_selector("[data-ai-proposal]")
        ai_page.locator('[data-pl="ai-apply"]').click()
        check("approved AI proposal adds only validated objects",
              ai_page.evaluate("() => window.__acreforgeSourceTest.itemCount()") == base_count + 1)
        for mode, expect in (("malformed", "not valid JSON"), ("bad", "No proposed object passed"),
                             ("fail", "failed (HTTP 503)")):
            ai_mode["mode"] = mode
            ai_request()
            ai_page.wait_for_function(
                "() => !document.querySelector('[data-pl=\"ai-cancel\"]').disabled === false"
                " && !/Waiting/.test(document.querySelector('[data-ai-status]').textContent)")
            text = ai_page.locator("[data-ai-status]").inner_text()
            check(f"AI {mode} response leaves plan unchanged and reports error",
                  expect in text and ai_page.locator("[data-ai-proposal]").count() == 0
                  and ai_page.evaluate("() => window.__acreforgeSourceTest.itemCount()") == base_count + 1)
        ai_mode["mode"] = "hang"
        ai_request()
        ai_page.wait_for_selector('[data-pl="ai-cancel"]:not([disabled])')
        ai_page.locator('[data-pl="ai-cancel"]').click()
        ai_page.wait_for_function(
            "() => /cancelled/.test(document.querySelector('[data-ai-status]').textContent)")
        check("cancelling an AI request leaves the plan unchanged and baseline planner works",
              ai_page.evaluate("() => window.__acreforgeSourceTest.itemCount()") == base_count + 1
              and ai_page.locator('[data-pl="gen"]').count() == 1 and not ai_errors)
        try:
            ai_routes[-1].abort()
        except Exception:
            pass
        ai_page.unroute_all(behavior="ignoreErrors")
        ai_context.close()
        budget_context = b.new_context(service_workers="block")
        budget_page = budget_context.new_page()
        budget_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        budget_errors = []
        budget_page.on("pageerror", lambda e: budget_errors.append(str(e)))
        budget_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        budget_page.wait_for_timeout(500)
        budget_page.locator('[data-page="planner"]').first.click()
        check("driveway calculator starts without invented dimensions or market prices",
              budget_page.locator("[data-driveway-calculator]").count() == 1
              and budget_page.locator('[data-driveway-form] [name="lengthFt"]').input_value() == ""
              and budget_page.locator('[data-driveway-form] [name="lowRate"]').input_value() == ""
              and budget_page.locator("[data-septic-calculator]").count() == 1
              and all(budget_page.locator(
                  f'[data-septic-form] [name="{field}"]').input_value() == ""
                  for field in ("bedrooms", "occupantsPerBedroom", "dailyGallonsPerPerson",
                                "tankHoldingDays", "tankLiquidDepthFt",
                                "fieldLoadingGpdPerSqFt"))
              and budget_page.locator("[data-septic-results]").count() == 0
              and "no regional or regulatory values are prefilled" in
                  budget_page.locator("[data-septic-calculator]").inner_text().lower())
        budget_page.locator("#plPrompt").fill("Build 1000 sqft house and 20x30 shop")
        budget_page.locator("#plDist").fill("600")
        budget_page.locator('[data-pl="gen"]').click()
        budget_page.wait_for_selector('[data-budget-line="total"]')
        initial_budget = budget_page.locator("[data-budget-line]").evaluate_all("""rows => {
          const value = cell => Number(cell.textContent.replace(/[^0-9]/g, '')) || 0;
          const categories = rows.filter(row => row.dataset.budgetLine !== 'total');
          const sum = band => categories.reduce((total, row) =>
            total + value(row.querySelector(`[data-budget-value="${band}"]`)), 0);
          const total = band => value(document.querySelector(`[data-budget-total="${band}"]`));
          const amount = label => value(document.querySelector(
            `[data-budget-line="${label}"] [data-budget-value="mid"]`));
          return {low: total('low'), mid: total('mid'), high: total('high'),
            lowSum: sum('low'), midSum: sum('mid'), highSum: sum('high'),
            roads: amount('Roads & driveway'), utilities: amount('Utilities & well'),
            buildings: amount('Buildings'), site: amount('Site preparation'),
            septic: amount('Septic'), septicNote: document.querySelector(
              '[data-budget-line="Septic"]').innerText};
        }""")
        check("cost estimator presents ordered low/mid/high totals that equal their line items",
              initial_budget["low"] <= initial_budget["mid"] <= initial_budget["high"]
              and initial_budget["low"] == initial_budget["lowSum"]
              and initial_budget["mid"] == initial_budget["midSum"]
              and initial_budget["high"] == initial_budget["highSum"]
              and all(initial_budget[key] > 0
                      for key in ("roads", "utilities", "buildings", "site", "septic")))
        budget_page.locator('[data-driveway-form] [name="material"]').select_option("gravel")
        for field, value in [("lengthFt", "120"), ("widthFt", "12"), ("depthIn", "6"),
                             ("lowRate", "20"), ("expectedRate", "35"), ("highRate", "50")]:
            budget_page.locator(f'[data-driveway-form] [name="{field}"]').fill(value)
        budget_page.locator('[data-driveway-form] button[type="submit"]').click()
        driveway_values = budget_page.locator("[data-driveway-calculator]").evaluate("""card => ({
          volume: card.querySelector('[data-driveway-result]').textContent,
          low: card.querySelector('[data-driveway-total="low"]')?.textContent,
          expected: card.querySelector('[data-driveway-total="expected"]')?.textContent,
          high: card.querySelector('[data-driveway-total="high"]')?.textContent,
          budgetRoads: document.querySelector(
            '[data-budget-line="Roads & driveway"] [data-budget-value="mid"]')?.textContent,
          budgetTotal: document.querySelector('[data-budget-total="mid"]')?.textContent
        })""")
        parse_amount = lambda value: int(re.sub(r"[^0-9]", "", value or ""))
        check("driveway calculator converts dimensions to cubic yards and applies user-supplied rate bands",
              "26.67 cu yd" in driveway_values["volume"]
              and [parse_amount(driveway_values[key]) for key in ("low", "expected", "high")]
              == [533, 933, 1333])
        check("standalone driveway material allowance does not double-count the planner budget",
              parse_amount(driveway_values["budgetRoads"]) == initial_budget["roads"]
              and parse_amount(driveway_values["budgetTotal"]) == initial_budget["mid"]
              and "not a bid" in budget_page.locator(
                "[data-driveway-calculator]").inner_text().lower())
        for field, value in [("bedrooms", "3"), ("occupantsPerBedroom", "2"),
                             ("dailyGallonsPerPerson", "60"), ("tankHoldingDays", "2"),
                             ("tankLiquidDepthFt", "5"), ("fieldLoadingGpdPerSqFt", "0.5")]:
            budget_page.locator(f'[data-septic-form] [name="{field}"]').fill(value)
        budget_page.locator('[data-septic-form] button[type="submit"]').click()
        septic_values = budget_page.locator("[data-septic-results]").evaluate("""section => {
          const value = name => Number(section.querySelector(
            `[data-septic-output="${name}"]`).dataset.value);
          return {occupants: value('occupants'), flow: value('daily-flow-gpd'),
            tankGallons: value('tank-volume-gallons'),
            tankArea: value('tank-footprint-sqft'), fieldArea: value('drain-field-area-sqft')};
        }""")
        check("septic estimator derives occupancy, user-assumed daily flow, tank proxy, and field area",
              septic_values["occupants"] == 6 and septic_values["flow"] == 360
              and septic_values["tankGallons"] == 720
              and abs(septic_values["tankArea"] - 19.25) < .02
              and septic_values["fieldArea"] == 720)
        septic_copy = budget_page.locator("[data-septic-calculator]").inner_text().lower()
        check("septic estimator explicitly disclaims Oregon permitting and regulatory suitability",
              "does not assess oregon permitting suitability or regulatory compliance" in septic_copy
              and "not a tank design" in septic_copy
              and "percolation conditions" in septic_copy)
        septic_budget_after = int(budget_page.locator(
            '[data-budget-total="mid"]').inner_text().replace("$", "").replace(",", ""))
        septic_line_after = int(budget_page.locator(
            '[data-budget-line="Septic"] [data-budget-value="mid"]').inner_text()
            .replace("$", "").replace(",", ""))
        check("septic area preview stays separate from the planner budget",
              septic_budget_after == initial_budget["mid"]
              and septic_line_after == initial_budget["septic"])
        septic_math = budget_page.evaluate("""() => {
          const api = window.__acreforgeSepticTest;
          const valid = {bedrooms: 3, occupantsPerBedroom: 2, dailyGallonsPerPerson: 60,
            tankHoldingDays: 2, tankLiquidDepthFt: 5, fieldLoadingGpdPerSqFt: .5};
          return {missing: api.calculateSepticEstimate({}), badBedroom:
            api.calculateSepticEstimate({...valid, bedrooms: 0}), badLoading:
            api.calculateSepticEstimate({...valid, fieldLoadingGpdPerSqFt: 0})};
        }""")
        check("septic estimator suppresses incomplete, out-of-range, and zero-loading calculations",
              all(value is None for value in septic_math.values()))
        budget_page.locator('[data-septic-form] [name="bedrooms"]').fill("4")
        check("editing septic assumptions marks old results stale until recalculated",
              budget_page.locator("[data-septic-results]").count() == 0
              and "calculate again" in budget_page.locator("[data-septic-result]").inner_text().lower())
        budget_page.locator('[data-driveway-form] [name="lowRate"]').fill("50")
        budget_page.locator('[data-driveway-form] [name="expectedRate"]').fill("20")
        budget_page.locator('[data-driveway-form] [name="highRate"]').fill("10")
        budget_page.locator('[data-driveway-form] button[type="submit"]').click()
        check("driveway calculator rejects unordered cost bands without changing its prior result",
              "ascending order" in budget_page.locator("[data-driveway-result]").inner_text()
              and parse_amount(budget_page.locator(
                '[data-driveway-total="expected"]').inner_text()) == 933)
        budget_page.locator("#plDist").fill("1000")
        budget_page.locator('[data-pl="gen"]').click()
        budget_page.wait_for_timeout(150)
        distance_budget = budget_page.locator(
            '[data-budget-line="Roads & driveway"] [data-budget-value="mid"]').inner_text()
        distance_utilities = budget_page.locator(
            '[data-budget-line="Utilities & well"] [data-budget-value="mid"]').inner_text()
        check("road distance changes update road and utility allowances",
              int(distance_budget.replace("$", "").replace(",", ""))
              - initial_budget["roads"] == 16000
              and int(distance_utilities.replace("$", "").replace(",", ""))
              - initial_budget["utilities"] == 29600)
        budget_page.locator("#plPrompt").fill("Build 2500 sqft house and 40x60 shop")
        budget_page.locator('[data-pl="gen"]').click()
        larger_building = budget_page.locator(
            '[data-budget-line="Buildings"] [data-budget-value="mid"]').inner_text()
        check("larger requested building dimensions increase the building estimate",
              int(larger_building.replace("$", "").replace(",", ""))
              > initial_budget["buildings"])
        budget_page.locator('[data-cost-assumptions] summary').click()
        budget_page.locator('[data-cost-assumption="roadRate"]').fill("50")
        budget_page.locator('[data-cost-assumption="roadRate"]').press("Tab")
        budget_page.wait_for_function(
            "() => { const raw = localStorage.getItem('oregon-estate-planner-v1'); "
            "return !!raw && JSON.parse(raw).plan?.cost?.roadRate === 50; }")
        budget_page.locator('[data-cost-assumptions] summary').click()
        budget_page.locator('[data-cost-assumption="septicAllowance"]').fill("50000")
        budget_page.locator('[data-cost-assumption="septicAllowance"]').press("Tab")
        budget_page.wait_for_function(
            "() => { const raw = localStorage.getItem('oregon-estate-planner-v1'); "
            "return !!raw && JSON.parse(raw).plan?.cost?.septicAllowance === 50000; }")
        edited_costs = budget_page.locator("[data-budget-line]").evaluate_all("""rows => {
          const amount = label => Number(document.querySelector(
            `[data-budget-line="${label}"] [data-budget-value="mid"]`).textContent
            .replace(/[^0-9]/g, '')) || 0;
          return {roads: amount('Roads & driveway'), septic: amount('Septic'),
            low: Number(document.querySelector('[data-budget-total="low"]').textContent
              .replace(/[^0-9]/g, '')) || 0,
            mid: Number(document.querySelector('[data-budget-total="mid"]').textContent
              .replace(/[^0-9]/g, '')) || 0,
            high: Number(document.querySelector('[data-budget-total="high"]').textContent
              .replace(/[^0-9]/g, '')) || 0};
        }""")
        check("editable road and septic assumptions change the budget and persist",
              edited_costs["roads"] == 50000 and edited_costs["septic"] == 85000
              and edited_costs["low"] <= edited_costs["mid"] <= edited_costs["high"])
        budget_page.reload()
        budget_page.wait_for_timeout(500)
        budget_page.locator('[data-page="planner"]').first.click()
        budget_page.locator('[data-cost-assumptions] summary').click()
        check("custom cost assumptions survive reload",
              budget_page.locator('[data-cost-assumption="roadRate"]').input_value() == "50"
              and budget_page.locator(
                  '[data-cost-assumption="septicAllowance"]').input_value() == "50000")
        check("driveway dimensions, material, and rate bands survive reload",
              budget_page.locator('[data-driveway-form] [name="material"]').input_value() == "gravel"
              and [budget_page.locator(f'[data-driveway-form] [name="{field}"]').input_value()
                   for field in ("lengthFt", "widthFt", "depthIn", "lowRate",
                                 "expectedRate", "highRate")]
              == ["120", "12", "6", "20", "35", "50"]
              and "26.67 cu yd" in budget_page.locator("[data-driveway-result]").inner_text())
        check("septic assumptions and estimate survive reload as local project inputs",
              [budget_page.locator(f'[data-septic-form] [name="{field}"]').input_value()
               for field in ("bedrooms", "occupantsPerBedroom", "dailyGallonsPerPerson",
                             "tankHoldingDays", "tankLiquidDepthFt",
                             "fieldLoadingGpdPerSqFt")]
              == ["3", "2", "60", "2", "5", "0.5"]
              and budget_page.locator('[data-septic-output="daily-flow-gpd"]')
                  .get_attribute("data-value") == "360"
              and budget_page.locator('[data-septic-output="drain-field-area-sqft"]')
                  .get_attribute("data-value") == "720")
        budget_page.locator("#plPrompt").fill("Build 1000 sqft house")
        budget_page.locator("#plDist").fill("600")
        budget_page.locator('[data-pl="gen"]').click()
        routes = budget_page.locator("[data-utility-route-row]").evaluate_all("""rows => rows.map(row => {
          const value = cell => Number(cell.textContent.replace(/[^0-9]/g, '')) || 0;
          return {key: row.dataset.utilityRouteRow, distance: row.querySelector('input').value,
            basis: row.cells[2].innerText, cost: value(row.cells[3])};
        })""")
        power_route = next(route for route in routes if route["key"] == "power")
        check("utility routes show explicit assumed distances, rates, and arithmetic",
              power_route["distance"] == "600"
              and "Planning-distance assumption" in power_route["basis"]
              and "Moderate" in power_route["basis"]
              and power_route["cost"] == 600 * 32)
        utility_before_route_edit = int(budget_page.locator(
            '[data-budget-line="Utilities & well"] [data-budget-value="mid"]').inner_text()
            .replace("$", "").replace(",", ""))
        power_distance = budget_page.locator(
            '[data-utility-route="power"][data-utility-field="distanceFt"]')
        power_distance.fill("1000")
        power_distance.press("Tab")
        budget_page.wait_for_function(
            "() => JSON.parse(localStorage.getItem('oregon-estate-planner-v1')).plan"
            "?.utilityRoutes?.power?.distanceFt === 1000")
        utility_after_route_edit = int(budget_page.locator(
            '[data-budget-line="Utilities & well"] [data-budget-value="mid"]').inner_text()
            .replace("$", "").replace(",", ""))
        check("longer routes move to the length-based planning difficulty band",
              "Long" in budget_page.locator(
                  '[data-utility-route-row="power"] td:nth-child(3)').inner_text())
        check("editing a route distance updates and persists its utility budget line",
              utility_after_route_edit - utility_before_route_edit == (1000 - 600) * 32)
        utility_before_rate_edit = utility_after_route_edit
        budget_page.get_by_text("Edit route unit rates", exact=True).click()
        power_rate = budget_page.locator(
            '[data-utility-route="power"][data-utility-field="rate"]')
        power_rate.fill("40")
        power_rate.press("Tab")
        budget_page.wait_for_function(
            "() => JSON.parse(localStorage.getItem('oregon-estate-planner-v1')).plan"
            "?.utilityRoutes?.power?.rate === 40")
        utility_after_rate_edit = int(budget_page.locator(
            '[data-budget-line="Utilities & well"] [data-budget-value="mid"]').inner_text()
            .replace("$", "").replace(",", ""))
        check("editing a per-route rate persists and propagates through the budget",
              utility_after_rate_edit - utility_before_rate_edit == 1000 * (40 - 32))
        budget_page.locator('[data-pl="place"]').click()
        budget_page.wait_for_timeout(150)
        layout_routes = budget_page.locator("[data-utility-route-row]").evaluate_all("""rows => rows.map(row => ({
          key: row.dataset.utilityRouteRow, distance: row.querySelector('input').value,
          basis: row.cells[2].innerText
        }))""")
        water_route = next(route for route in layout_routes if route["key"] == "water")
        septic_route = next(route for route in layout_routes if route["key"] == "septic")
        check("placed source and destination geometry yields straight-line route lengths, not claimed pipe runs",
              "Layout geometry · straight line" in water_route["basis"]
              and "Layout geometry · straight line" in septic_route["basis"]
              and "not a routed" in water_route["basis"]
              and "unverified" in septic_route["basis"])
        budget_page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1', state = JSON.parse(localStorage.getItem(key));
          state.scenarios[0].items.push({id: 'smoke-power-corridor', type: 'utility',
            name: 'Power', x: 1200, y: 1200, w: 750, h: 12, unitCost: 0, fromPlan: false});
          state.plan.cost = {...(state.plan.cost || {}), utilityFactor: 100};
          localStorage.setItem(key, JSON.stringify(state));
        }""")
        budget_page.reload()
        budget_page.wait_for_timeout(500)
        budget_page.locator('[data-page="planner"]').first.click()
        budget_page.locator('[data-utility-reset="power"]').click()
        power_corridor = budget_page.locator(
            '[data-utility-route-row="power"]').evaluate("""row => ({
              distance: row.querySelector('input').value, basis: row.cells[2].innerText,
              cost: Number(row.cells[3].textContent.replace(/[^0-9]/g, '')) || 0
            })""")
        check("a named utility corridor uses its drawn layout length and per-foot rate",
              power_corridor["distance"] == "750"
              and "Drawn utility corridor" in power_corridor["basis"]
              and power_corridor["cost"] == 750 * 40)
        budget_page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1', state = JSON.parse(localStorage.getItem(key));
          state.scenarios[0].items = [];
          state.plan.dist = 0;
          state.plan.utilityRoutes = {};
          localStorage.setItem(key, JSON.stringify(state));
        }""")
        budget_page.reload()
        budget_page.wait_for_timeout(500)
        budget_page.locator('[data-page="planner"]').first.click()
        missing_routes = budget_page.locator("[data-utility-route-row]").evaluate_all(
            "rows => rows.map(row => row.cells[2].innerText)")
        check("routes without geometry or a distance assumption are unavailable rather than fabricated",
              len(missing_routes) == 4
              and all("Unavailable" in route for route in missing_routes))
        budget_page.locator("#plPrompt").fill("Create a subdivision with 40 homes")
        budget_page.locator('[data-pl="gen"]').click()
        check("subdivision budgets disclose when private septic is not included",
              budget_page.locator(
                  '[data-budget-line="Septic"] [data-budget-value="mid"]').inner_text() == "$0"
              and "Not included" in budget_page.locator(
                  '[data-budget-line="Septic"]').inner_text()
              and budget_page.locator(
                  '[data-cost-assumption="septicAllowance"]').is_disabled())
        sewer_route = budget_page.locator(
            '[data-utility-route-row="sewer"]').evaluate("""row => ({
              distance: Number(row.querySelector('input').value),
              cost: Number(row.cells[3].textContent.replace(/[^0-9]/g, '')) || 0,
              basis: row.cells[2].innerText
            })""")
        check("shared sewer cost remains visible as an assumed route, not private septic",
              sewer_route["distance"] == 2400 and sewer_route["cost"] == 2400 * 70
              and "Planning-distance assumption" in sewer_route["basis"])
        check("cost estimator actions produce no JavaScript errors", not budget_errors)
        budget_context.close()
        traffic_context = b.new_context(service_workers="block")
        traffic_page = traffic_context.new_page()
        traffic_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        traffic_errors = []
        traffic_page.on("pageerror", lambda e: traffic_errors.append(str(e)))
        traffic_page.goto("http://127.0.0.1:8766")
        traffic_page.wait_for_timeout(500)
        traffic_page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const state = JSON.parse(localStorage[key] || JSON.stringify({
            schemaVersion: 1, project: {name: 'Traffic fixture', acres: 40, aspect: 1},
            scenarios: [{id: 'base', name: 'Base', items: [], fields: [], finance: {}}],
            activeScenario: 'base'
          }));
          const base = state.scenarios.find(x => x.id === state.activeScenario) || state.scenarios[0];
          state.scenarios = [{
            ...structuredClone(base), id: 'traffic-fixture', name: 'Traffic fixture',
            items: [{id: 'traffic-home', type: 'home', x: 280, y: 180, w: 40, h: 40,
              height: 12, fromPlan: 1, name: 'Destination'}],
            roads: [{id: 'main-road', type: 'gravel', pts: [[100, 200], [300, 200], [500, 200]],
              curve: false, oneway: false}],
            waters: [], fields: []
          }];
          state.activeScenario = 'traffic-fixture';
          localStorage[key] = JSON.stringify(state);
        }""")
        traffic_page.reload()
        traffic_page.wait_for_timeout(500)
        traffic_page.locator("#nav [data-page=designer]").click()
        traffic_page.locator('[data-traffic-demand="cars"]').fill("6")
        traffic_page.locator('[data-traffic-demand="guests"]').fill("5")
        traffic_page.locator('[data-traffic-demand="deliveries"]').fill("1")
        traffic_page.locator("[data-traffic-analyze]").click()
        traffic_page.wait_for_function(
            "() => document.querySelector('[data-traffic-report]')?.textContent.includes('Peak-hour demand:')")
        first_traffic_report = traffic_page.locator("[data-traffic-report]").inner_text()
        first_bottleneck = traffic_page.locator("[data-bottleneck]").first.inner_text()
        traffic_page.locator("[data-traffic-analyze]").click()
        second_traffic_report = traffic_page.locator("[data-traffic-report]").inner_text()
        check("traffic analysis is deterministic for fixed roads and demand",
              first_traffic_report == second_traffic_report)
        check("traffic analysis converts guest demand and reports a measured bottleneck",
              "6 cars + 3 guest vehicles (5 guests ÷ 2.4 per vehicle) + 1 deliveries" in first_traffic_report
              and "10 modeled vehicles" in first_bottleneck
              and "Destination: 5 guests, 200 ft" in first_traffic_report
              and "near" in first_bottleneck)
        check("traffic report includes an emergency route and explicit study limitations",
              "Emergency access probe" in first_traffic_report
              and "not a traffic study" in first_traffic_report
              and "not included in bottleneck counts" in first_traffic_report)
        check("traffic demand assumptions persist in the browser",
              traffic_page.evaluate(
                  "() => JSON.parse(localStorage['acreforge.traffic']).demand") ==
              {"cars": 6, "guests": 5, "deliveries": 1})
        traffic_page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1', state = JSON.parse(localStorage[key]);
          state.scenarios[0].items[0].x = 3000;
          localStorage[key] = JSON.stringify(state);
        }""")
        traffic_page.reload()
        traffic_page.wait_for_timeout(500)
        traffic_page.locator("#nav [data-page=designer]").click()
        readiness = traffic_page.locator("[data-traffic-readiness]").inner_text()
        check("incomplete destination networks disable simulation and analysis with a warning",
              "more than 650 ft from a road" in readiness
              and traffic_page.locator("[data-road-sim]").is_disabled()
              and traffic_page.locator("[data-traffic-analyze]").is_disabled())
        traffic_page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1', state = JSON.parse(localStorage[key]);
          state.scenarios[0].items[0].x = 280;
          state.scenarios[0].roads[0].pts = [[100, 200], [200, 100], [300, 200], [200, 300], [100, 200]];
          localStorage[key] = JSON.stringify(state);
        }""")
        traffic_page.reload()
        traffic_page.wait_for_timeout(500)
        traffic_page.locator("#nav [data-page=designer]").click()
        check("closed road loops without a vehicle-access gate remain disabled",
              "No vehicle-access gate" in traffic_page.locator(
                  "[data-traffic-readiness]").inner_text()
              and traffic_page.locator("[data-road-sim]").is_disabled()
              and traffic_page.locator("[data-traffic-analyze]").is_disabled())
        check("traffic analysis actions produce no JavaScript errors", not traffic_errors)
        traffic_context.close()
        snapshot_context = b.new_context(service_workers="block")
        snapshot_page = snapshot_context.new_page()
        snapshot_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        snapshot_errors = []
        snapshot_page.on("pageerror", lambda e: snapshot_errors.append(str(e)))
        snapshot_page.goto("http://127.0.0.1:8766")
        snapshot_page.wait_for_timeout(500)
        snapshot_page.evaluate("""() => {
          const key = 'oregon-estate-planner-v1';
          const state = {schemaVersion: 1, project: {name: 'Scenario test', acres: 40, aspect: 1},
            scenarios: [{id: 'base', name: 'Base', items: [], fields: [], finance: {}}],
            activeScenario: 'base'};
          const item = (id, type, x, y, w, h, extra = {}) => ({
            id, type, x, y, w, h, height: 12, fromPlan: 1, ...extra
          });
          const base = state.scenarios[0];
          const make = (id, name, items, prompt = '', distance = 0) => ({
            ...structuredClone(base), id, name, items, fields: [], planningPrompt: prompt,
            planningDistance: distance
          });
          state.scenarios = [
            make('compound', 'Family compound', [
              item('c-home-1', 'home', 100, 100, 40, 40),
              item('c-home-2', 'home', 440, 100, 40, 40),
              item('c-drive', 'road', 100, 140, 400, 12, {name: 'Driveway concept'}),
              item('c-well', 'well', 100, 220, 20, 20),
              item('c-septic', 'septic', 300, 240, 40, 30)
            ], 'Create a family compound', 600),
            make('compact', 'Compact plan', [
              item('m-home', 'home', 160, 160, 40, 40),
              item('m-home-2', 'home', 310, 160, 40, 40),
              item('m-drive', 'road', 160, 200, 150, 12, {name: 'Driveway concept'}),
              item('m-utility', 'utility', 160, 240, 80, 16)
            ], 'Build a compact home', 150),
            make('homestead', 'Homestead', [
              item('h-home', 'home', 220, 220, 40, 40),
              item('h-orchard', 'orchard', 400, 250, 120, 100),
              item('h-solar', 'solar', 170, 300, 20, 10)
            ], 'Build a self-sufficient homestead for 3 people with an orchard', 100)
          ];
          state.activeScenario = 'compact';
          state.analysis = {sub: {Buildability: {value: 82}}, solar: 70};
          state.scenarioSnapshots = [];
          localStorage[key] = JSON.stringify(state);
        }""")
        snapshot_page.reload()
        snapshot_page.wait_for_timeout(600)
        snapshot_page.locator('[data-page="scenarios"]').first.click()
        active_before_snapshot = snapshot_page.evaluate(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario")
        for scenario_id, snapshot_name in [
                ("compact", "Compact decision"), ("compound", "Compound decision"),
                ("homestead", "Homestead decision")]:
            if snapshot_page.evaluate(
                    "() => JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario") != scenario_id:
                snapshot_page.locator(
                    f'[data-action="switch-scenario"][data-id="{scenario_id}"]').click()
            snapshot_page.once("dialog", lambda dialog, name=snapshot_name: dialog.accept(name))
            snapshot_page.locator('[data-snapshot-action="save"]').click()
            snapshot_page.wait_for_function(
                "(count) => JSON.parse(localStorage['oregon-estate-planner-v1']).scenarioSnapshots.length === count",
                arg=["compact", "compound", "homestead"].index(scenario_id) + 1)
        saved_snapshots = snapshot_page.evaluate("""() => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return {active: s.activeScenario, snapshots: s.scenarioSnapshots.map(x => ({
            id: x.id, name: x.name, scenarioId: x.scenario.id, metrics: x.metrics
          }))};
        }""")
        rendered_snapshots = snapshot_page.locator("[data-scenario-snapshot-row]").evaluate_all(
            "(rows) => rows.map(row => ({id: row.dataset.scenarioSnapshotRow, "
            "cost: row.dataset.cost, privacy: row.dataset.privacy, "
            "buildability: row.dataset.buildability, utilities: row.dataset.utilities, "
            "selfSufficiency: row.dataset.selfSufficiency}))")
        snapshot_by_scenario = {s["scenarioId"]: s for s in saved_snapshots["snapshots"]}
        rows_match = len(rendered_snapshots) == 3 and all(
            row["id"] == next(s["id"] for s in saved_snapshots["snapshots"]
                              if s["id"] == row["id"])
            and float(row["cost"]) == snapshot_by_scenario[
                next(s["scenarioId"] for s in saved_snapshots["snapshots"]
                     if s["id"] == row["id"])]["metrics"]["cost"]["value"]
            for row in rendered_snapshots)
        check("three named snapshots persist and preserve the active scenario",
              len(saved_snapshots["snapshots"]) == 3
              and saved_snapshots["active"] == "homestead")
        before_plan = snapshot_page.locator('[data-snapshot-plan-preview="before"]')
        after_plan = snapshot_page.locator('[data-snapshot-plan-preview="after"]')
        check("before/after previews show geometry from their matching frozen snapshots",
              before_plan.count() == 1 and after_plan.count() == 1
              and before_plan.locator('[data-object="m-home"]').count() == 1
              and before_plan.locator('[data-object="c-home-1"]').count() == 0
              and after_plan.locator('[data-object="c-home-1"]').count() == 1
              and after_plan.locator('[data-object="m-home"]').count() == 0
              and snapshot_page.locator("[data-snapshot-plan-after]").input_value()
                  == snapshot_by_scenario["compound"]["id"])
        snapshot_page.locator("[data-snapshot-plan-after]").select_option(label="Homestead decision")
        check("visual after selection redraws the chosen snapshot without changing the active scenario",
              snapshot_page.locator('[data-snapshot-plan-preview="after"] [data-object="h-home"]').count() == 1
              and snapshot_page.locator('[data-snapshot-plan-preview="after"] [data-object="c-home-1"]').count() == 0
              and snapshot_page.evaluate(
                  "() => JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario") == "homestead")
        check("snapshot comparison maps metrics to the matching saved concept",
              rows_match
              and len({s["metrics"]["cost"]["value"] for s in saved_snapshots["snapshots"]}) == 3
              and snapshot_by_scenario["compound"]["metrics"]["privacy"]["value"] !=
                  snapshot_by_scenario["compact"]["metrics"]["privacy"]["value"]
              and snapshot_by_scenario["compact"]["metrics"]["utilities"]["value"] >
                  snapshot_by_scenario["homestead"]["metrics"]["utilities"]["value"]
              and snapshot_by_scenario["homestead"]["metrics"]["selfSufficiency"] is not None
              and all(s["metrics"]["buildability"]["value"] == 82
                      for s in saved_snapshots["snapshots"]))
        check("comparison leaves unmeasured privacy unavailable",
              rendered_snapshots[2]["privacy"] == ""
              and "Unavailable" in snapshot_page.locator(
                  f'[data-scenario-snapshot-row="{snapshot_by_scenario["homestead"]["id"]}"]')
                  .inner_text())
        snapshot_page.wait_for_timeout(500)
        snapshot_page.reload()
        snapshot_page.wait_for_timeout(600)
        snapshot_page.locator('[data-page="scenarios"]').first.click()
        check("saved comparison snapshots survive reload",
              snapshot_page.locator("[data-scenario-snapshot-row]").count() == 3
              and snapshot_page.evaluate(
                  "() => JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario")
              == "homestead")
        compound_snapshot = snapshot_by_scenario["compound"]["id"]
        original_compound = snapshot_page.evaluate("""(id) => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          return JSON.stringify(s.scenarios.find(x => x.id === 'compound').items);
        }""", compound_snapshot)
        snapshot_page.once("dialog", lambda dialog: dialog.accept())
        snapshot_page.locator(
            f'[data-snapshot-action="restore"][data-id="{compound_snapshot}"]').click()
        snapshot_page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios.length === 4")
        restored = snapshot_page.evaluate("""(snapshotId) => {
          const s = JSON.parse(localStorage['oregon-estate-planner-v1']);
          const snapshot = s.scenarioSnapshots.find(x => x.id === snapshotId);
          const active = s.scenarios.find(x => x.id === s.activeScenario);
          return {active: s.activeScenario, name: active.name, source: s.scenarios.find(x => x.id === 'compound'),
            snapshot: snapshot, activeItems: active.items};
        }""", compound_snapshot)
        check("restoring a snapshot creates a new editable scenario without replacing its source",
              restored["active"] != "compound"
              and restored["name"] == "Compound decision restored"
              and restored["activeItems"] == restored["snapshot"]["scenario"]["items"]
              and snapshot_page.evaluate(
                  "() => JSON.stringify(JSON.parse(localStorage['oregon-estate-planner-v1'])"
                  ".scenarios.find(x => x.id === 'compound').items)") == original_compound
              and snapshot_page.locator(
                  f'[data-scenario-snapshot-row="{compound_snapshot}"]').count() == 1)
        snapshot_count = snapshot_page.locator("[data-scenario-snapshot-row]").count()
        snapshot_page.once("dialog", lambda dialog: dialog.dismiss())
        snapshot_page.locator(
            f'[data-snapshot-action="delete"][data-id="{compound_snapshot}"]').click()
        check("cancelled snapshot deletion preserves the saved comparison",
              snapshot_page.locator("[data-scenario-snapshot-row]").count() == snapshot_count)
        snapshot_page.once("dialog", lambda dialog: dialog.accept())
        snapshot_page.locator(
            f'[data-snapshot-action="delete"][data-id="{compound_snapshot}"]').click()
        snapshot_page.wait_for_function(
            "() => JSON.parse(localStorage['oregon-estate-planner-v1']).scenarioSnapshots.length === 2")
        check("confirmed snapshot deletion removes only the chosen snapshot",
              snapshot_page.locator("[data-scenario-snapshot-row]").count() == 2
              and snapshot_page.evaluate(
                  "() => JSON.parse(localStorage['oregon-estate-planner-v1']).activeScenario")
              == restored["active"])
        check("scenario snapshot actions produce no JavaScript errors", not snapshot_errors)
        snapshot_context.close()
        # Reporting and recovery upgrades use a separate browser profile and no live services.
        upgrade_context = b.new_context(service_workers="block", accept_downloads=True)
        upgrade_page = upgrade_context.new_page()
        upgrade_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        upgrade_errors, upgrade_requests = [], []
        upgrade_page.on("pageerror", lambda e: upgrade_errors.append(str(e)))
        upgrade_page.on("request", lambda r: upgrade_requests.append(r.url)
                        if not r.url.startswith(("http://127.0.0.1", "http://localhost", "data:", "blob:")) else None)
        upgrade_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        upgrade_page.evaluate("""() => {
          const {state: getState,scenario,items,save} = window.__acreforgeUpgradeTest;
          const state=getState();
          state.project.name = 'Upgrade <test>';
          state.project.privateMarker = 'PRIVATE-NOT-EXPORTED';
          state.scenarios.push({...JSON.parse(JSON.stringify(scenario())),id:'other',name:'Unrelated scenario'});
          items().forEach((item, index) => { item.phase = String(index % 3 + 1); });
          scenario().finance.contingency = 10;
          save();
        }""")
        upgrade_page.wait_for_timeout(500)
        check("local save reports approximate project JSON size",
              "Saved locally" in upgrade_page.locator("#saveState").inner_text()
              and "KiB" in upgrade_page.locator("#saveState").inner_text())
        normalized_acquisition = upgrade_page.evaluate("""() => {
          const normalize=window.__acreforgeUpgradeTest.normalizeAcquisitionInputs;
          return {empty:normalize(),mixed:normalize({purchasePrice:'125000',transactionCosts:2500,
            dueDiligenceCosts:'',initialReserve:-1,planningBudget:1000000001,ignored:9})};
        }""")
        check("acquisition amounts normalize missing, invalid, and legacy project values safely",
              all(normalized_acquisition["empty"][key] is None for key in
                  ("purchasePrice","transactionCosts","dueDiligenceCosts","initialReserve","planningBudget"))
              and normalized_acquisition["mixed"] == {
                  "purchasePrice":125000,"transactionCosts":2500,"dueDiligenceCosts":None,
                  "initialReserve":None,"planningBudget":None})
        upgrade_page.locator("#nav [data-page=reports]").click()
        upgrade_page.locator("#content .tabbar [data-page=financials]").click()
        acquisition_summary = upgrade_page.locator("[data-acquisition-summary]").inner_text()
        check("acquisition worksheet distinguishes unknown inputs from zero",
              "Enter all four acquisition amounts" in acquisition_summary
              and "No market data or external services" in
                  upgrade_page.locator("[data-acquisition-worksheet]").inner_text()
              and upgrade_page.locator("#acquisition-purchasePrice").input_value() == "")
        upgrade_page.locator("#acquisition-planningBudget").fill("1000000001")
        upgrade_page.locator("#acquisition-planningBudget").blur()
        check("acquisition worksheet rejects out-of-range amounts without saving them",
              "Enter an amount from $0 to $1,000,000,000" in
                  upgrade_page.locator("[data-acquisition-message]").inner_text()
              and upgrade_page.evaluate("""() =>
                window.__acreforgeUpgradeTest.state().project.acquisitionInputs.planningBudget === null"""))
        acquisition_capex = upgrade_page.evaluate(
            "window.__acreforgeUpgradeTest.compute().capex")
        acquisition_budget = math.ceil((acquisition_capex + 400000) / 1000) * 1000
        acquisition_values = {"purchasePrice":250000,"transactionCosts":10000,
                              "dueDiligenceCosts":15000,"initialReserve":25000,
                              "planningBudget":acquisition_budget}
        for key, value in acquisition_values.items():
            upgrade_page.locator(f"#acquisition-{key}").fill(str(value))
            upgrade_page.locator(f"#acquisition-{key}").blur()
        acquisition_total = acquisition_capex + 300000
        acquisition_expected_total = "$" + format(round(acquisition_total), ",")
        acquisition_expected_subtotal = "$300,000"
        acquisition_budget_diff = "$" + format(round(acquisition_budget-acquisition_total), ",")
        acquisition_result = upgrade_page.locator("[data-acquisition-summary]").inner_text()
        upgrade_page.wait_for_timeout(500)
        check("acquisition worksheet totals supplied amounts and compares only with the user's budget",
              acquisition_expected_subtotal in acquisition_result
              and acquisition_expected_total in acquisition_result
              and acquisition_budget_diff + " below your entered planning budget" in acquisition_result
              and upgrade_page.evaluate("""expected => {
                const values=JSON.parse(localStorage.getItem('oregon-estate-planner-v1'))
                  .project.acquisitionInputs;
                return Object.entries(expected).every(([key,value])=>values[key]===value);
              }""", acquisition_values))
        upgrade_page.reload()
        upgrade_page.locator("#nav [data-page=reports]").click()
        upgrade_page.locator("#content .tabbar [data-page=financials]").click()
        check("acquisition worksheet inputs and totals persist after reload",
              upgrade_page.locator("#acquisition-purchasePrice").input_value() == "250000"
              and acquisition_expected_total in
                  upgrade_page.locator("[data-acquisition-summary]").inner_text())
        upgrade_page.locator("#nav [data-page=reports]").click()
        phase = upgrade_page.evaluate("""() => {
          const {reportPhases,compute,items,reportSensitivity,scenario}=window.__acreforgeUpgradeTest;
          return {rows: reportPhases(), subtotal: compute().costs,
            count: items().length, capex: compute().capex,
            sensitivity: reportSensitivity(), rate: scenario().finance.contingency};
        }""")
        check("phase summary counts and unrounded subtotals reconcile with the current scenario",
              sum(r["count"] for r in phase["rows"]) == phase["count"]
              and math.isclose(sum(r["subtotal"] for r in phase["rows"]), phase["subtotal"], rel_tol=1e-12)
              and "not a construction schedule" in upgrade_page.locator("[data-phase-summary]").inner_text())
        check("contingency preview is monotonic, reconciles and does not change the saved rate",
              phase["sensitivity"][0]["total"] <= phase["sensitivity"][1]["total"] <= phase["sensitivity"][2]["total"]
              and math.isclose(phase["sensitivity"][1]["total"], phase["capex"], rel_tol=1e-12)
              and phase["rate"] == 10 and "saved assumptions are unchanged" in
              upgrade_page.locator("[data-report-sensitivity]").inner_text())
        sensitivity_setup = upgrade_page.evaluate("""() => {
          const api=window.__acreforgeUpgradeTest, choices=api.reportSensitivityChoices();
          const original=api.items().slice();
          api.items().splice(0);
          const emptyChoices=api.reportSensitivityChoices();
          api.items().push(...original);
          const itemChoice=choices.find(x=>x.key!=='contingency');
          return {choices, emptyChoices, type:itemChoice?.key,label:itemChoice?.label,
            saved:localStorage.getItem('oregon-estate-planner-v1')};
        }""")
        check("cost sensitivity omits unavailable object assumptions",
              sensitivity_setup["type"] is not None
              and [x["key"] for x in sensitivity_setup["emptyChoices"]] == ["contingency"])
        if sensitivity_setup["type"]:
            upgrade_page.locator("[data-report-sensitivity-select]").select_option(
                value=sensitivity_setup["type"])
            object_sensitivity = upgrade_page.evaluate("""type => {
              const {reportSensitivity,compute}=window.__acreforgeUpgradeTest;
              return {rows:reportSensitivity(type),capex:compute().capex,
                label:document.querySelector('[data-report-sensitivity]').innerText,
                saved:localStorage.getItem('oregon-estate-planner-v1')};
            }""", sensitivity_setup["type"])
            check("selected object-cost sensitivity is monotonic and reconciles at current assumptions",
                  object_sensitivity["rows"][0]["total"] <= object_sensitivity["rows"][1]["total"]
                  <= object_sensitivity["rows"][2]["total"]
                  and math.isclose(object_sensitivity["rows"][1]["total"],
                                   object_sensitivity["capex"], rel_tol=1e-12)
                  and object_sensitivity["rows"][0]["assumption"] == sensitivity_setup["type"])
            check("cost sensitivity preview leaves saved assumptions and local backup unchanged",
                  object_sensitivity["saved"] == sensitivity_setup["saved"]
                  and sensitivity_setup["saved"] is not None
                  and sensitivity_setup["label"] in object_sensitivity["label"]
                  and "saved assumptions are unchanged" in object_sensitivity["label"])
            upgrade_page.locator("[data-report-sensitivity-select]").select_option(
                value="contingency")
        check("cost sensitivity returns to contingency selection after an object preview",
              upgrade_page.locator("[data-report-sensitivity-select]").input_value()
              == "contingency"
              and "Overall contingency" in upgrade_page.locator(
                  "[data-report-sensitivity]").inner_text())
        assumptions = upgrade_page.locator("[data-assumptions-register]").inner_text()
        check("assumptions register identifies missing data and disclaims verification",
              "no imported boundary" in assumptions and "No terrain data supplied" in assumptions
              and "Source verification not supplied" in assumptions and "not independent verification" in assumptions
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.reportAssumptions()) === JSON.stringify(window.__acreforgeUpgradeTest.reportAssumptions())"))
        before_upgrade_requests = len(upgrade_requests)
        with upgrade_page.expect_download() as summary_info:
            upgrade_page.locator("[data-report-summary-export]").click()
        summary = json.load(open(summary_info.value.path(), encoding="utf-8"))
        check("summary JSON exports active-scenario context and explicit limitations locally",
              summary["schemaVersion"] == 1 and summary["project"]["name"] == "Upgrade <test>"
              and summary["scenario"]["objectCount"] == phase["count"]
              and summary["scenario"]["buildingConcepts"]
              and summary["measurements"]["dimensions"] == "feet"
              and summary["openDueDiligence"]
              and "question" in summary["openDueDiligence"][0]
              and math.isclose(summary["estimate"]["conceptualCapex"], phase["capex"], rel_tol=1e-12)
              and "not for construction" in summary["disclosures"][0]
              and "PRIVATE-NOT-EXPORTED" not in json.dumps(summary)
              and "Unrelated scenario" not in json.dumps(summary)
              and "purchasePrice" not in json.dumps(summary)
              and len(upgrade_requests) == before_upgrade_requests)
        upgrade_page.evaluate("""() => {
          window.persistedBeforeFailure = localStorage.getItem('oregon-estate-planner-v1');
          window.originalStorageSet = Storage.prototype.setItem;
          Storage.prototype.setItem = function() { throw new DOMException('Full', 'QuotaExceededError'); };
          window.__acreforgeUpgradeTest.state().project.name = 'Unsaved in memory';
          window.__acreforgeUpgradeTest.save();
        }""")
        upgrade_page.wait_for_timeout(500)
        check("storage failure preserves in-memory work and advises exporting a backup",
              "export a backup" in upgrade_page.locator("#saveState").inner_text()
              and "Saved locally" not in upgrade_page.locator("#saveState").inner_text()
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Unsaved in memory"
              and upgrade_page.evaluate("localStorage.getItem('oregon-estate-planner-v1') === window.persistedBeforeFailure"))
        upgrade_page.evaluate("Storage.prototype.setItem = window.originalStorageSet; window.__acreforgeUpgradeTest.save()")
        upgrade_page.wait_for_timeout(500)
        check("local save status recovers after a storage error",
              "Saved locally" in upgrade_page.locator("#saveState").inner_text())
        backup_data = upgrade_page.evaluate("""() => {
          const copy=JSON.parse(JSON.stringify(window.__acreforgeUpgradeTest.state())); copy.project.name='Backup metadata test';
          return JSON.stringify(copy);
        }""")
        dialogs = []
        upgrade_page.once("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        upgrade_page.locator("#importFile").set_input_files({
            "name": "backup.json", "mimeType": "application/json", "buffer": backup_data.encode()})
        upgrade_page.wait_for_timeout(200)
        check("backup preview gives metadata and cancellation preserves the current project",
              dialogs and "Backup metadata test" in dialogs[0] and "Scenarios: 2" in dialogs[0]
              and "Site objects (all scenarios):" in dialogs[0] and "Metadata preview only" in dialogs[0]
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Unsaved in memory")
        older_backup = json.loads(backup_data)
        older_backup["project"]["name"] = "Older backup"
        older_backup["updatedAt"] = "2000-01-01T00:00:00.000Z"
        older_warning = []
        upgrade_page.once("dialog", lambda d: (older_warning.append(d.message), d.dismiss()))
        upgrade_page.locator("#importFile").set_input_files({
            "name": "older-backup.json", "mimeType": "application/json",
            "buffer": json.dumps(older_backup).encode()})
        upgrade_page.wait_for_timeout(200)
        check("older backup warns before replacement and cancellation preserves current data",
              older_warning and "OLDER" in older_warning[0]
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Unsaved in memory")
        upgrade_page.evaluate(
            "window.persistedBeforeInvalidImport = localStorage.getItem('oregon-estate-planner-v1')")
        for label, payload in [("malformed", b"{"), ("newer schema", json.dumps({
                **json.loads(backup_data), "schemaVersion": 999}).encode())]:
            rejection = []
            upgrade_page.once("dialog", lambda d: (rejection.append(d.message), d.accept()))
            upgrade_page.locator("#importFile").set_input_files({
                "name": label.replace(" ", "-") + ".json", "mimeType": "application/json", "buffer": payload})
            upgrade_page.wait_for_timeout(100)
            check(f"{label} backup is rejected before project replacement",
                  rejection and "Import failed" in rejection[0]
                  and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Unsaved in memory"
                  and upgrade_page.evaluate(
                      "localStorage.getItem('oregon-estate-planner-v1') === window.persistedBeforeInvalidImport"))
        upgrade_page.evaluate("""() => {
          window.__acreforgeUpgradeTest.state().project.terrain = {
            cols:4, rows:4, h:Array(16).fill(0), valid:[false,...Array(15).fill(true)],
            source:'real', sampledWidthFeet:1000, sampledHeightFeet:1000, show:true
          };
        }""")
        upgrade_page.locator("#nav [data-page=designer]").click()
        slope_text = upgrade_page.locator("#slopePanel").inner_text()
        check("earthwork suppresses estimates when elevation samples are missing",
              "Estimate unavailable" in slope_text and "unmapped samples" in slope_text
              and "cu yd" not in slope_text)
        earthwork_original_items = upgrade_page.evaluate(
            "window.__acreforgeUpgradeTest.items().map(item=>({...item}))")
        upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest, volume=window.__acreforgeEarthworkTest;
          const items=test.items(), prototype=items.find(item=>volume.limitOf(item)!==null);
          if(!prototype)throw Error("No supported earthwork fixture object is available.");
          items.splice(0,items.length,{...prototype,id:"earthwork-volume-test",x:0,y:0,w:100,h:50,rotation:0});
          const project=test.state().project;
          project.terrain={cols:4,rows:4,h:Array(16).fill(0),valid:Array(16).fill(true),
            source:"real",sampledWidthFeet:300,sampledHeightFeet:150,show:true};
          project.earthworkTargetFeet=null;test.save();
        }""")
        upgrade_page.locator("#nav [data-page=reports]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        check("cut/fill estimate requires an explicit target and does not invent a design grade",
              upgrade_page.locator("[data-earthwork-target-form] #earthworkTargetFeet").input_value() == ""
              and "No target grade is assumed" in upgrade_page.locator("[data-earthwork-volumes]").inner_text()
              and "Enter a target elevation" in upgrade_page.locator("[data-earthwork-volume-result]").inner_text())
        upgrade_page.locator("#earthworkTargetFeet").fill("5")
        upgrade_page.locator("[data-earthwork-target-form] button[type=submit]").click()
        first_volume_text=upgrade_page.locator("[data-earthwork-volume-result]").inner_text()
        check("flat terrain at a higher target yields fill and gross material-import quantities",
              "Fill volume (gross): 925.93 cu yd" in first_volume_text
              and "Export if all cut is removed: 0.00 cu yd" in first_volume_text
              and "Fill material if none is reused: 925.93 cu yd" in first_volume_text
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.earthworkTargetFeet") == 5)
        upgrade_page.wait_for_timeout(400)
        check("target elevation persists with the local project",
              upgrade_page.evaluate(
                  "JSON.parse(localStorage.getItem('oregon-estate-planner-v1')).project.earthworkTargetFeet") == 5)
        upgrade_page.locator('[data-tool="terrain"]').click()
        upgrade_page.locator("#earthworkTargetFeet").fill("6")
        upgrade_page.locator("#siteMap").scroll_into_view_if_needed()
        brush_point = upgrade_page.evaluate("""() => {
          const svg=document.querySelector('#siteMap'), point=svg.createSVGPoint();
          point.x=50;point.y=25;
          const p=point.matrixTransform(document.querySelector('#mapObjects').getScreenCTM());
          return {x:p.x,y:p.y};
        }""")
        upgrade_page.mouse.move(brush_point["x"], brush_point["y"])
        upgrade_page.mouse.down()
        upgrade_page.wait_for_function(
            "(before) => document.querySelector('[data-earthwork-volume-result]')?.innerText !== before",
            arg=first_volume_text)
        live_volume_text=upgrade_page.locator("[data-earthwork-volume-result]").inner_text()
        check("cut/fill updates during a terrain stroke without applying an unsaved target",
              live_volume_text != first_volume_text
              and upgrade_page.locator("#earthworkTargetFeet").input_value() == "6"
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.earthworkTargetFeet") == 5)
        upgrade_page.mouse.up()
        upgrade_page.locator('[data-tact="undo"]').click()
        check("terrain undo restores the prior cut/fill estimate",
              upgrade_page.locator("[data-earthwork-volume-result]").inner_text() == first_volume_text)
        upgrade_page.locator('[data-tact="redo"]').click()
        check("terrain redo restores the edited cut/fill estimate",
              upgrade_page.locator("[data-earthwork-volume-result]").inner_text() == live_volume_text)
        upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest, project=test.state().project;
          test.terrainApply({x:50,y:25});test.save();
        }""")
        upgrade_page.locator("#nav [data-page=reports]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        edited_volume_text=upgrade_page.locator("[data-earthwork-volume-result]").inner_text()
        check("terrain edits recalculate volume results against the saved target elevation",
              edited_volume_text != first_volume_text
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain.modified") is True)
        upgrade_page.evaluate("""() => {
          const project=window.__acreforgeUpgradeTest.state().project;
          project.terrain.h.fill(10);window.__acreforgeUpgradeTest.save();
        }""")
        upgrade_page.locator("#nav [data-page=reports]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        cut_volume_text=upgrade_page.locator("[data-earthwork-volume-result]").inner_text()
        check("terrain above the explicit target yields cut and gross potential-export quantities",
              "Cut volume (gross): 925.93 cu yd" in cut_volume_text
              and "Export if all cut is removed: 925.93 cu yd" in cut_volume_text
              and "Fill material if none is reused: 0.00 cu yd" in cut_volume_text)
        mixed = upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest, volume=window.__acreforgeEarthworkTest;
          const terrain=test.state().project.terrain, item=test.items()[0];
          terrain.h=Array.from({length:16},(_,i)=>(i%4)*10);
          const estimate=volume.estimate();
          const oldWidth=item.w;item.w=0;
          const invalid=volume.estimate();item.w=oldWidth;
          return {estimate,invalid};
        }""")
        check("mixed planar slope yields independent gross cut and fill",
              math.isclose(mixed["estimate"]["cutCuYd"], 5000 * 1.25 / 27, rel_tol=1e-10)
              and math.isclose(mixed["estimate"]["fillCuYd"], 5000 * 1.25 / 27, rel_tol=1e-10)
              and mixed["estimate"]["exportCuYd"] == mixed["estimate"]["cutCuYd"]
              and mixed["estimate"]["importCuYd"] == mixed["estimate"]["fillCuYd"])
        check("invalid footprint dimensions suppress cut/fill estimates",
              "invalid dimensions or coordinates" in mixed["invalid"].get("error", ""))
        check("relative target warning addresses terrain replacement",
              "review it for the new grid’s relative zero" in
              upgrade_page.locator("[data-earthwork-volumes]").inner_text())
        upgrade_page.locator("[data-earthwork-clear]").click()
        check("clearing the target removes the assumed grade and restores the explicit-input prompt",
              upgrade_page.locator("#earthworkTargetFeet").input_value() == ""
              and "Enter a target elevation" in upgrade_page.locator("[data-earthwork-volume-result]").inner_text())
        upgrade_page.evaluate("""items => {
          const test=window.__acreforgeUpgradeTest, project=test.state().project;
          test.items().splice(0,test.items().length,...items);
          project.terrain={cols:4,rows:4,h:Array(16).fill(0),valid:[false,...Array(15).fill(true)],
            source:"real",sampledWidthFeet:1000,sampledHeightFeet:1000,show:true};
          project.earthworkTargetFeet=null;test.save();
        }""", earthwork_original_items)
        upgrade_page.locator("#nav [data-page=reports]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        upgrade_page.locator('[data-tool="terrain"]').click()
        csv_header = "row,col,x_ft,y_ft,elevation_ft"
        def elevation_csv(unknown=False):
            return "\n".join([csv_header] + [
                f"{r},{c},{c*100},{r*50}," +
                ("NA" if unknown and (r,c)==(3,3) else str(100+r*2+c))
                for r in range(4) for c in range(4)]) + "\n"
        terrain_before_csv = upgrade_page.evaluate(
            "JSON.stringify(window.__acreforgeUpgradeTest.state().project.terrain)")
        network_before_csv = len(upgrade_requests)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator("[data-local-elevation-file]").set_input_files({
            "name":"elevation.csv","mimeType":"text/csv","buffer":elevation_csv(True).encode()})
        upgrade_page.wait_for_function("() => document.querySelector('[data-local-elevation-message]')?.textContent.includes('Imported 15/16')")
        imported_csv = upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain")
        check("local CSV elevation import records grid, extent, no-data and unverified provenance",
              imported_csv["rows"] == imported_csv["cols"] == 4
              and imported_csv["sampledWidthFeet"] == 300
              and imported_csv["sampledHeightFeet"] == 150
              and imported_csv["importKind"] == "local-csv"
              and imported_csv["valid"][-1] is False and sum(imported_csv["valid"]) == 15
              and math.isclose(imported_csv["h"][0] + imported_csv["elevationRangeFeet"]["mean"], 100)
              and "datum and accuracy unverified" in upgrade_page.locator("#terrainSampleStatus").inner_text()
              and len(upgrade_requests) == network_before_csv)
        check("CSV no-data masks terrain interpolation instead of becoming zero",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.terrainElev(300,150)") is None
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.terrainElev(0,0)") is not None)
        csv_exported = upgrade_page.evaluate(
            "window.__acreforgeUpgradeTest.terrainGridCsv(window.__acreforgeUpgradeTest.terrainData())")
        csv_export_rows = list(csv.reader(io.StringIO(csv_exported)))
        check("imported unknown nodes remain unknown in terrain grid exports",
              csv_export_rows[-1] == ["3","3","300","150","","no"])
        minimum_grid = "\n".join([csv_header]+[
            f"{r},{c},{c*100},{r*50},"+("100" if r<2 and c<2 else "NA")
            for r in range(4) for c in range(4)])
        check("minimum sufficient CSV coverage accepts one known 2-by-2 cell",
              upgrade_page.evaluate(
                  "s=>window.__acreforgeUpgradeTest.parseLocalElevationCsv(s).sampleCount",
                  minimum_grid) == 4)
        edit_import = upgrade_page.evaluate("""() => {
          const t=window.__acreforgeUpgradeTest, grid=t.state().project.terrain;
          t.terrainApply({x:100,y:50});
          return {modified:grid.modified,missing:grid.valid[15],missingHeight:grid.h[15],status:t.terrainSampleStatus(grid)};
        }""")
        check("CSV terrain editing preserves unknown nodes and marks imported provenance",
              edit_import["modified"] and not edit_import["missing"] and edit_import["missingHeight"] == 0
              and "edited after import" in edit_import["status"])
        upgrade_page.evaluate("grid => {window.__acreforgeUpgradeTest.state().project.terrain=grid}",imported_csv)
        upgrade_page.locator('[data-tact="undo"]').click()
        check("CSV import undo restores the previous terrain as one step",
              upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.terrain)") == terrain_before_csv)
        upgrade_page.locator('[data-tact="redo"]').click()
        check("CSV import redo restores the imported terrain and no-data",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain") == imported_csv)
        upgrade_page.wait_for_timeout(500)
        upgrade_page.reload()
        upgrade_page.locator("#nav [data-page=designer]").click()
        upgrade_page.locator('[data-tool="terrain"]').click()
        check("CSV terrain and provenance survive project reload",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain") == imported_csv)
        invalid_csv = {
            "header":elevation_csv().replace(csv_header,"row,col,x,y,z",1),
            "duplicate":elevation_csv()+"0,0,0,0,100\n",
            "missing":elevation_csv().replace("1,1,100,50,103\n",""),
            "non-finite":elevation_csv().replace("0,0,0,0,100","0,0,0,0,Infinity"),
            "out-of-range":elevation_csv().replace("0,0,0,0,100","0,0,0,0,30001"),
            "nonuniform":elevation_csv().replace("1,1,100,50,103","1,1,101,50,103"),
            "origin":elevation_csv().replace("0,0,0,0,100","0,0,1,0,100"),
            "too-small-spacing":elevation_csv().replace("0,1,100,0,101","0,1,0.01,0,101"),
            "insufficient": "\n".join([csv_header]+[f"{r},{c},{c*100},{r*50},NA" for r in range(4) for c in range(4)]),
            "disconnected-samples": "\n".join([csv_header]+[
                f"{r},{c},{c*100},{r*50},"+("100" if (r+c)%2==0 else "NA")
                for r in range(4) for c in range(4)]),
            "relief":elevation_csv().replace("0,0,0,0,100","0,0,0,0,1000"),
            "too-many-columns":elevation_csv()+"0,200,20000,0,100\n",
            "negative-index":elevation_csv().replace("0,0,0,0,100","-1,0,0,0,100"),
            "infinite-coordinate":elevation_csv().replace("0,0,0,0,100","0,0,1e999,0,100"),
            "non-numeric-no-data":elevation_csv().replace("0,0,0,0,100","0,0,0,0,nan"),
            "quoted":elevation_csv().replace("0,0,0,0,100",'0,0,"0",0,100'),
            "coordinate-range":elevation_csv().replace("0,0,0,0,100","0,0,100001,0,100"),
        }
        for label, bad in invalid_csv.items():
            upgrade_page.locator("[data-local-elevation-file]").set_input_files({
                "name":"bad.csv","mimeType":"text/csv","buffer":bad.encode()})
            upgrade_page.wait_for_function("() => document.querySelector('[data-local-elevation-message]')?.textContent.startsWith('CSV import failed:')")
            check(f"invalid CSV {label} leaves existing terrain unchanged",
                  upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain") == imported_csv)
        upgrade_page.locator("[data-local-elevation-file]").set_input_files({
            "name":"oversized.csv","mimeType":"text/csv","buffer":b" "*(2*1024*1024+1)})
        upgrade_page.wait_for_function("() => document.querySelector('[data-local-elevation-message]')?.textContent.includes('2 MiB limit')")
        check("oversized CSV is rejected before terrain mutation",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain") == imported_csv)
        upgrade_page.once("dialog", lambda d: d.dismiss())
        upgrade_page.locator("[data-local-elevation-file]").set_input_files({
            "name":"complete.csv","mimeType":"text/csv","buffer":elevation_csv().encode()})
        upgrade_page.wait_for_function("() => document.querySelector('[data-local-elevation-message]')?.textContent.includes('cancelled')")
        check("cancelling a valid CSV replacement preserves the existing grid",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain") == imported_csv)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator("[data-local-elevation-file]").set_input_files({
            "name":"complete.csv","mimeType":"text/csv","buffer":elevation_csv().encode()})
        upgrade_page.wait_for_function("() => document.querySelector('[data-local-elevation-message]')?.textContent.includes('Imported 16/16')")
        check("complete CSV grid imports with measured relative heights",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain.valid.every(Boolean)")
              and math.isclose(upgrade_page.evaluate(
                  "window.__acreforgeUpgradeTest.terrainElev(300,150)-window.__acreforgeUpgradeTest.terrainElev(0,0)"), 9)
              and len(upgrade_requests) == network_before_csv)
        # Use the actual terrain brush on a previously imported grid with one unknown node.
        edited_grid = upgrade_page.evaluate("""grid => {
          const t=window.__acreforgeUpgradeTest;
          t.state().project.terrain=grid; t.terrainApply({x:100,y:50});
          return structuredClone(t.state().project.terrain);
        }""", imported_csv)
        with upgrade_page.expect_download() as portable_info:
            upgrade_page.locator("[data-local-elevation-export]").click()
        portable_csv = open(portable_info.value.path(), encoding="utf-8").read()
        portable_rows = list(csv.reader(io.StringIO(portable_csv)))
        check("portable terrain download preserves edited grid and unknowns without mutation or requests",
              portable_rows[0] == csv_header.split(",") and portable_rows[-1] == ["3","3","300","150","NA"]
              and edited_grid["modified"] and edited_grid["h"] != imported_csv["h"]
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain") == edited_grid
              and "provenance are not included" in upgrade_page.locator("[data-local-elevation-export-status]").inner_text()
              and len(upgrade_requests) == network_before_csv)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator("[data-local-elevation-file]").set_input_files({
            "name":"relative.csv","mimeType":"text/csv","buffer":portable_csv.encode()})
        upgrade_page.wait_for_function("() => document.querySelector('[data-local-elevation-message]')?.textContent.includes('Imported 15/16')")
        round_trip = upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.terrain")
        check("portable terrain reimport preserves extent, no-data and relative relief",
              round_trip["valid"] == edited_grid["valid"]
              and round_trip["sampledWidthFeet"] == 300 and round_trip["sampledHeightFeet"] == 150
              and all(math.isclose(round_trip["h"][i]-round_trip["h"][0],
                                   edited_grid["h"][i]-edited_grid["h"][0], abs_tol=1e-9)
                      for i in range(16) if edited_grid["valid"][i]))
        for label, script, reason in [
            ("unknown imported extent", "t=>{delete t.sampledWidthFeet}", "no recorded extent"),
            ("excessive relief", "t=>{t.h[0]=300;t.h[1]=-300}", "within 300 ft"),
            ("too-small spacing", "t=>{t.sampledWidthFeet=.01}", "spacing"),
            ("oversized grid", """t=>{t.rows=200;t.cols=200;t.sampledWidthFeet=12345.6789;
                t.sampledHeightFeet=9876.54321;t.valid=Array(40000).fill(true);
                t.h=Array.from({length:40000},(_,i)=>0.123456789012345+i*1e-12)}""", "2 MiB"),
        ]:
            upgrade_page.evaluate("""([grid,script]) => {
              const t=structuredClone(grid); (0,eval)(script)(t);
              window.__acreforgeUpgradeTest.state().project.terrain=t;
            }""", [edited_grid, script])
            before_bad_export = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.terrain)")
            upgrade_page.locator("[data-local-elevation-export]").click()
            check(f"portable export rejects {label} without changing terrain",
                  reason in upgrade_page.locator("[data-local-elevation-export-status]").inner_text()
                  and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.terrain)") == before_bad_export
                  and len(upgrade_requests) == network_before_csv)
        upgrade_page.evaluate("""grid=>{
          const t=structuredClone(grid); t.source='synthetic'; delete t.sampledWidthFeet;
          delete t.sampledHeightFeet; t.valid=Array(16).fill(true);
          window.__acreforgeUpgradeTest.state().project.terrain=t;
        }""", edited_grid)
        with upgrade_page.expect_download() as synthetic_info:
            upgrade_page.locator("[data-local-elevation-export]").click()
        synthetic_csv = open(synthetic_info.value.path(), encoding="utf-8").read()
        check("synthetic terrain exports using property dimensions and meets the import contract",
              upgrade_page.evaluate("s=>window.__acreforgeUpgradeTest.parseLocalElevationCsv(s).sampleCount",
                                    synthetic_csv) == 16 and len(upgrade_requests) == network_before_csv)
        upgrade_page.evaluate("""old => {
          window.__acreforgeUpgradeTest.state().project.terrain=JSON.parse(old);
        }""",terrain_before_csv)
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        upgrade_page.locator('[data-tool="terrain"]').click()
        with upgrade_page.expect_download() as grid_info:
            upgrade_page.locator("[data-export-terrain-grid]").click()
        grid_rows = list(csv.reader(io.StringIO(open(grid_info.value.path(), encoding="utf-8").read())))
        check("terrain grid CSV preserves no-data and relative coordinates without network access",
              grid_rows[3] == ["Column", "Row", "X ft", "Y ft", "Relative height ft", "Valid"]
              and grid_rows[4] == ["0", "0", "0", "0", "", "no"]
              and grid_rows[-1] == ["3", "3", "1000", "1000", "0", "yes"]
              and "not absolute elevation" in grid_rows[1][0]
              and len(upgrade_requests) == before_upgrade_requests)
        check("legacy imported grid with no recorded extent is not exported",
              upgrade_page.evaluate("""() => {
                const test=window.__acreforgeUpgradeTest, t={...test.state().project.terrain};
                delete t.sampledWidthFeet; return test.terrainGridCsv(t) === null;
              }"""))
        # A previous edit's debounced save updates state.updatedAt asynchronously.
        upgrade_page.wait_for_timeout(500)
        before_profile = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state())")
        for field, value in [("x1", "0"), ("y1", "0"), ("x2", "1000"), ("y2", "1000")]:
            upgrade_page.locator(f'[data-terrain-profile-form] [name="{field}"]').fill(value)
        upgrade_page.locator("[data-terrain-profile-form] button").click()
        profile_text = upgrade_page.locator("[data-terrain-profile-result]").inner_text()
        check("terrain cross-section shows sampled gaps without changing the saved project",
              "21 samples available" in profile_text and "Unknown" in profile_text
              and upgrade_page.locator("[data-terrain-profile-result] tbody tr").count() == 21
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state())") == before_profile
              and len(upgrade_requests) == before_upgrade_requests)
        upgrade_page.locator('[data-terrain-profile-form] [name="x1"]').fill("-1")
        upgrade_page.locator("[data-terrain-profile-form] button").click()
        check("terrain cross-section rejects endpoints outside the grid",
              "inside the sampled terrain extent" in upgrade_page.locator("[data-terrain-profile-result]").inner_text())
        profile_math = upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest, t=test.state().project.terrain;
          const oldValid=t.valid,oldHeights=t.h;
          t.valid=Array(16).fill(true); t.h=Array.from({length:16},(_,i)=>(i%4)+2*Math.floor(i/4));
          const p=test.terrainProfile(0,0,1000,1000);
          t.valid=oldValid; t.h=oldHeights;
          return p;
        }""")
        check("terrain cross-section interpolates a known plane deterministically",
              math.isclose(profile_math["distance"], math.sqrt(2) * 1000, rel_tol=1e-12)
              and math.isclose(profile_math["samples"][0]["height"], 0, abs_tol=1e-12)
              and math.isclose(profile_math["samples"][10]["height"], 4.5, abs_tol=1e-12)
              and math.isclose(profile_math["samples"][-1]["height"], 9, abs_tol=1e-12))
        corridor_geometry=upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest, item={...test.items()[0],id:'utility-test',
            type:'utility',name:'Water corridor',x:100,y:100,w:600,h:20,rotation:0};
          test.items().push(item);
          return test.utilityProfileEndpoints({...item,rotation:90});
        }""")
        upgrade_page.locator('[data-tool="terrain"]').click()
        upgrade_page.locator('[data-utility-profile-form] select').select_option("utility-test")
        before_utility=upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state())")
        upgrade_page.locator('[data-utility-profile-form] button').click()
        utility_text=upgrade_page.locator("[data-utility-profile-result]").inner_text()
        check("drawn utility terrain profile uses the rotated centerline and shows no-data gaps",
              math.isclose(corridor_geometry[0],400,abs_tol=1e-8)
              and math.isclose(corridor_geometry[1],-190,abs_tol=1e-8)
              and math.isclose(corridor_geometry[2],400,abs_tol=1e-8)
              and math.isclose(corridor_geometry[3],410,abs_tol=1e-8)
              and "600.0 ft approximate centerline" in utility_text and "Unknown" in utility_text
              and "not a continuous grade" in utility_text
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state())")==before_utility
              and len(upgrade_requests)==before_upgrade_requests)
        flow_math=upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest, before=JSON.stringify(test.state());
          const base={cols:4,rows:4,h:Array.from({length:16},(_,i)=>3-i%4),
            valid:Array(16).fill(true),source:'real',sampledWidthFeet:300,sampledHeightFeet:150};
          const plane=test.terrainFlowPreview(base), flat=test.terrainFlowPreview({...base,h:Array(16).fill(1)});
          const gap={...base,valid:[...base.valid]};gap.valid[6]=false;
          const partial=test.terrainFlowPreview(gap);
          const diagonal={...base,h:Array(16).fill(5),valid:Array(16).fill(true)};
          diagonal.h[10]=0;diagonal.valid[6]=false;diagonal.valid[9]=false;
          const blocked=test.terrainFlowPreview(diagonal);
          const unbounded=test.terrainFlowPreview({...base,sampledWidthFeet:undefined});
          return {plane,flat,partial,blocked,unbounded,unchanged:JSON.stringify(test.state())===before};
        }""")
        check("downslope routing follows the steepest drop and accumulates relative grid nodes",
              flow_math["plane"]["routedNodes"] == 12
              and flow_math["plane"]["maxContributingNodes"] == 4
              and flow_math["plane"]["segments"] > 0
              and flow_math["plane"]["unknownNodes"] == 0)
        check("downslope routing preserves flat stops, unknown nodes, missing extents, and project state",
              flow_math["flat"]["routedNodes"] == 0
              and flow_math["flat"]["stopNodes"] == 16
              and flow_math["partial"]["validNodes"] == 15
              and flow_math["partial"]["unknownNodes"] == 1
              and flow_math["blocked"]["blockedDiagonalSteps"] > 0
              and flow_math["unbounded"] is None
              and flow_math["unchanged"])
        old_flow_terrain=upgrade_page.evaluate("""() => {
          const test=window.__acreforgeUpgradeTest,project=test.state().project;
          const old=JSON.stringify(project.terrain);
          project.terrain={cols:4,rows:4,h:Array.from({length:16},(_,i)=>3-i%4),
            valid:Array(16).fill(true),show:true};
          return old;
        }""")
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        if upgrade_page.locator("[data-terrain-flow]").count() == 0:
            upgrade_page.locator('[data-tool="terrain"]').click()
        before_flow=upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state())")
        before_flow_requests=len(upgrade_requests)
        upgrade_page.locator("[data-terrain-flow-run]").click()
        flow_text=upgrade_page.locator("[data-terrain-flow-result]").inner_text()
        check("terrain panel previews downhill paths locally without changing project or making requests",
              upgrade_page.locator("[data-flow-preview]").count() == 1
              and "relative contributing nodes" in flow_text
              and "not a water-flow or runoff simulation" in upgrade_page.locator("[data-terrain-flow]").inner_text()
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state())")==before_flow
              and len(upgrade_requests)==before_flow_requests)
        upgrade_page.evaluate("""old => {
          window.__acreforgeUpgradeTest.state().project.terrain=JSON.parse(old);
        }""",old_flow_terrain)
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        upgrade_page.evaluate("""() => {
          const a=window.__acreforgeUpgradeTest.items(); a.splice(a.findIndex(i=>i.id==='utility-test'),1);
        }""")
        upgrade_page.evaluate("""() => {
          const s=window.__acreforgeUpgradeTest.state(); s.project.terrain.valid=Array(16).fill(true);
          s.scenarios.find(x=>x.id===s.activeScenario).items[0].rotation=45;
        }""")
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        check("earthwork suppresses unsupported rotated or out-of-extent footprints",
              "rotated or extends beyond" in upgrade_page.locator("#slopePanel").inner_text()
              and "cu yd" not in upgrade_page.locator("#slopePanel").inner_text())
        edited_status = upgrade_page.evaluate("""() => {
          const t=window.__acreforgeUpgradeTest;
          t.state().project.terrain.elevationRangeFeet={min:100,max:110,mean:105};
          t.terrainApply({x:500,y:500});
          return {modified:t.state().project.terrain.modified,status:t.terrainSampleStatus(t.state().project.terrain)};
        }""")
        check("editing imported terrain labels original sample range and modified provenance",
              edited_status["modified"] and "original sampled elevations" in edited_status["status"]
              and "edited after import" in edited_status["status"])
        upgrade_page.evaluate("delete window.__acreforgeUpgradeTest.state().project.terrain")
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#milestoneTitle").fill("  Contact county  ")
        upgrade_page.locator("#milestoneDate").fill("2027-02-28")
        upgrade_page.locator("[data-milestone-form] button[type=submit]").click()
        upgrade_page.wait_for_timeout(500)
        check("milestones migrate older projects and add a dated local reminder",
              upgrade_page.evaluate("""() => {
                const milestones=window.__acreforgeUpgradeTest.state().project.milestones;
                return milestones.length === 1 && milestones[0].title === 'Contact county'
                  && milestones[0].date === '2027-02-28';
              }"""))
        public_dialogs = []
        upgrade_page.once("dialog", lambda d: (public_dialogs.append(d.message), d.dismiss()))
        upgrade_page.get_by_role("button", name="Public export").click()
        check("public export preflight explains retained data and cancellation leaves the project intact",
              public_dialogs and "site-object labels" in public_dialogs[0]
              and "acquisition worksheet inputs" in public_dialogs[0]
              and "not automatically reviewed" in public_dialogs[0]
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.milestones.length") == 1)
        def accept_public_dialog(dialog):
            dialog.accept()
        upgrade_page.on("dialog", accept_public_dialog)
        with upgrade_page.expect_download() as public_info:
            upgrade_page.get_by_role("button", name="Public export").click()
        public_data = json.load(open(public_info.value.path(), encoding="utf-8"))
        check("public export removes milestones and acquisition inputs without modifying the saved project",
              "milestones" not in public_data["project"]
              and "acquisitionInputs" not in public_data["project"]
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.milestones.length") == 1)
        upgrade_page.remove_listener("dialog", accept_public_dialog)
        upgrade_page.locator('[data-milestone-action="edit"]').click()
        upgrade_page.locator("#milestoneTitle").fill("Confirm boundary")
        upgrade_page.locator("[data-milestone-form] button[type=submit]").click()
        upgrade_page.locator('[data-milestone-action="toggle"]').click()
        upgrade_page.wait_for_timeout(500)
        upgrade_page.reload()
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        check("milestone edits and completion persist across reload",
              "Confirm boundary" in upgrade_page.locator("[data-milestones]").inner_text()
              and "Complete" in upgrade_page.locator("[data-milestones]").inner_text()
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.validMilestoneDate('2027-02-29')") is False)
        upgrade_page.once("dialog", lambda d: d.dismiss())
        upgrade_page.locator('[data-milestone-action="remove"]').click()
        check("cancelling milestone removal keeps the reminder",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.milestones.length") == 1)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator('[data-milestone-action="remove"]').click()
        upgrade_page.wait_for_timeout(500)
        check("confirmed milestone removal persists",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.milestones.length") == 0)
        upgrade_page.locator("#milestoneTitle").fill("   ")
        upgrade_page.locator("[data-milestone-form] button[type=submit]").click()
        check("milestones reject whitespace-only titles",
              "Enter a title" in upgrade_page.locator("[data-milestone-message]").inner_text())
        upgrade_page.evaluate("""() => {
          window.__acreforgeUpgradeTest.state().project.milestones =
            Array.from({length:50}, (_,i) => ({id:'limit-'+i,title:'Reminder '+i,date:'',done:false}));
        }""")
        upgrade_page.locator("#milestoneTitle").fill("One too many")
        upgrade_page.locator("[data-milestone-form] button[type=submit]").click()
        check("milestone creation respects the 50-entry limit",
              "50-milestone limit" in upgrade_page.locator("[data-milestone-message]").inner_text()
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.milestones.length") == 50)
        topology = upgrade_page.evaluate("""() => {
          const validate=window.__acreforgeUpgradeTest.validateImportedParcelRings;
          const run=p=>{try{validate(p);return true}catch(e){return false}};
          const outer=[[179,10],[-179,10],[-179,12],[179,12],[179,10]];
          const hole=[[179.2,10.2],[179.4,10.2],[179.4,10.4],[179.2,10.4],[179.2,10.2]];
          return {
            hole:run([[outer,hole]]),
            multipart:run([[[[0,0],[1,0],[1,1],[0,1],[0,0]]],[[[2,0],[3,0],[3,1],[2,1],[2,0]]]]),
            crossed:run([[[[0,0],[3,3],[0,2],[2,0],[0,0]]]]),
            duplicate:run([[[[0,0],[1,0],[1,0],[1,1],[0,0]]]]),
            backtrack:run([[[[0,0],[2,0],[1,0],[1,1],[0,1],[0,0]]]]),
            zero:run([[[[0,0],[1,0],[2,0],[0,0]]]]),
            invalid:run([[[[0,0],[181,0],[1,1],[0,0]]]])
          };
        }""")
        check("parcel import validates holes, multipart and antimeridian rings and rejects bad topology",
              topology["hole"] and topology["multipart"] and not any(
                  topology[k] for k in ("crossed", "duplicate", "backtrack", "zero", "invalid")))
        valid_geo = {"type":"Polygon", "coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
        import_dialogs = []
        upgrade_page.once("dialog", lambda d: (import_dialogs.append(d.message), d.accept()))
        upgrade_page.locator("#parcelFile").set_input_files({
            "name":"valid.geojson","mimeType":"application/geo+json","buffer":json.dumps(valid_geo).encode()})
        upgrade_page.wait_for_timeout(300)
        boundary_before = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.parcelBoundary)")
        bad_geo = {"type":"Polygon", "coordinates":[[[0,0],[3,3],[0,2],[2,0],[0,0]]]}
        import_dialogs = []
        upgrade_page.once("dialog", lambda d: (import_dialogs.append(d.message), d.accept()))
        upgrade_page.locator("#parcelFile").set_input_files({
            "name":"crossed.geojson","mimeType":"application/geo+json","buffer":json.dumps(bad_geo).encode()})
        upgrade_page.wait_for_timeout(300)
        check("rejected parcel leaves previously imported boundary untouched",
              import_dialogs and "Parcel import failed" in import_dialogs[0]
              and boundary_before != "null"
              and boundary_before == upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.parcelBoundary)"))
        upgrade_page.evaluate("""() => {
          const t=window.__acreforgeUpgradeTest, s=t.state(), sc=t.scenario();
          s.project.parcelBoundary=null;
          const sample=JSON.parse(JSON.stringify(sc));
          const m=(n,p)=>({cost:{value:n,detail:'estimate'},privacy:p===null?null:{value:p,detail:'proxy'},
            buildability:{value:40,detail:'screen'},utilities:{value:500,detail:'estimate'},selfSufficiency:null});
          s.scenarioSnapshots=[
            {id:'delta-a',name:'Baseline',scenario:sample,metrics:m(1000,20),metricVersion:1},
            {id:'delta-b',name:'Alternative',scenario:sample,metrics:m(1200,null),metricVersion:1},
            {id:'delta-legacy',name:'Legacy',scenario:sample,metrics:m(900,30)}
          ]; t.save();
        }""")
        upgrade_page.wait_for_timeout(500)
        upgrade_page.locator("#content .tabbar [data-page=scenarios]").click()
        delta_row = upgrade_page.locator('[data-delta-snapshot="delta-b"]')
        check("scenario deltas show signed comparable values and leave missing metrics unavailable",
              "+$200" in delta_row.inner_text() and "Unavailable" in delta_row.inner_text()
              and "not measured privacy" in upgrade_page.locator("[data-snapshot-deltas]").inner_text()
              and "Unavailable" in upgrade_page.locator('[data-delta-snapshot="delta-legacy"]').inner_text())
        upgrade_page.locator("[data-snapshot-baseline]").select_option("delta-b")
        check("scenario delta baseline switching reverses the signed comparison",
              "−$200" in upgrade_page.locator('[data-delta-snapshot="delta-a"]').inner_text())
        upgrade_page.reload()
        upgrade_page.locator("#content .tabbar [data-page=scenarios]").click()
        check("scenario metric version survives project reload",
              "+$200" in upgrade_page.locator('[data-delta-snapshot="delta-b"]').inner_text()
              and "Unavailable" in upgrade_page.locator('[data-delta-snapshot="delta-legacy"]').inner_text())
        upgrade_page.evaluate("""() => {
          const t=window.__acreforgeUpgradeTest, a=t.items();
          a[0].name='North filter barn';a[0].phase='2';a[0].status='Reviewed';
          a[1].name='South filter object';a[1].phase='1';a[1].status='Preliminary';
        }""")
        upgrade_page.locator("#nav [data-page=designer]").click()
        objects_detail=upgrade_page.locator('[data-detail="objects"]')
        if objects_detail.get_attribute("open") is None:
            objects_detail.locator("summary").click()
        objects_before=upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        upgrade_page.locator('[data-object-filter="query"]').fill("NORTH FILTER")
        object_type=upgrade_page.evaluate("window.__acreforgeUpgradeTest.items()[0].type")
        upgrade_page.locator('[data-object-filter="type"]').select_option(object_type)
        upgrade_page.locator('[data-object-filter="phase"]').select_option("2")
        upgrade_page.locator('[data-object-filter="status"]').select_option("Reviewed")
        check("site-object search combines case-insensitive query and phase/status without mutation",
              "1 matching object" in upgrade_page.locator("[data-object-filter-count]").inner_text()
              and upgrade_page.locator('[data-select-object]:visible').count() == 1
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == objects_before)
        upgrade_page.locator('[data-select-object]:visible').focus()
        upgrade_page.keyboard.press("Enter")
        check("filtered object is keyboard selectable without changing saved objects",
              upgrade_page.locator('[data-select-object].selected:visible').count() == 1
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == objects_before)
        upgrade_page.locator('[data-object-filter="query"]').fill("nothing matches")
        check("object filters report zero matches",
              "0 matching objects" in upgrade_page.locator("[data-object-filter-count]").inner_text())
        upgrade_page.evaluate("""() => {
          const t=window.__acreforgeUpgradeTest, sc=t.scenario(), base=sc.items[0];
          sc.items=[0,1,2].map(n=>({...base,id:'group-'+n,name:'Group '+n,
            x:20+n*40,y:20+n*10,w:10,h:10,shape:'rect',rotation:0,locked:false}));
          t.state().project.parcelBoundary=null;
        }""")
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        for n in range(3):
            upgrade_page.locator(f'[data-group-select="group-{n}"]').check()
        check("group selection uses accessible checkboxes",
              upgrade_page.locator("[data-group-count]").inner_text() == "3 selected")
        before_group = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        upgrade_page.locator("[data-group-x]").fill("5")
        upgrade_page.locator("[data-group-y]").fill("7")
        upgrade_page.locator('[data-group-action="move"]').click()
        moved = upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().map(i=>[i.x,i.y])")
        check("group movement applies one offset to every selected object",
              moved == [[25,27],[65,37],[105,47]])
        upgrade_page.locator('[data-action="undo"]').first.click()
        check("one undo restores the entire group movement",
              upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_group)
        upgrade_page.locator('[data-action="redo"]').first.click()
        check("one redo reapplies the entire group movement",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().map(i=>[i.x,i.y])") == moved)
        upgrade_page.evaluate("window.__acreforgeUpgradeTest.items()[1].locked=true")
        locked_before = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        upgrade_page.locator('[data-group-action="align-left"]').click()
        check("locked group action is rejected without partial mutation",
              "Unlock all" in upgrade_page.locator("[data-group-message]").inner_text()
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == locked_before)
        upgrade_page.evaluate("""boundary => {
          const t=window.__acreforgeUpgradeTest;
          t.items()[1].locked=false;
          boundary.polygons=[[[[0,0],[150,0],[150,100],[0,100],[0,0]]]];
          t.state().project.parcelBoundary=boundary;
        }""", json.loads(boundary_before))
        parcel_before = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        upgrade_page.locator("[data-group-x]").fill("100")
        upgrade_page.locator('[data-group-action="move"]').click()
        check("parcel-invalid group action leaves all selected objects unchanged",
              "outside the imported parcel" in upgrade_page.locator("[data-group-message]").inner_text()
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == parcel_before)
        upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.parcelBoundary=null")
        upgrade_page.locator('[data-group-action="align-top"]').click()
        check("group alignment uses footprint edges",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().map(i=>i.y)") == [27,27,27])
        upgrade_page.locator('[data-action="undo"]').first.click()
        check("one undo restores the entire alignment",
              upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == parcel_before)
        upgrade_page.evaluate("window.__acreforgeUpgradeTest.items()[1].x=45")
        upgrade_page.locator('[data-group-action="distribute-x"]').click()
        check("group distribution gives equal gaps",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().map(i=>i.x)") == [25,65,105])
        upgrade_page.locator('[data-group-x]').fill("0")
        upgrade_page.locator('[data-group-y]').fill("20")
        upgrade_page.locator('[data-group-action="duplicate"]').click()
        check("group duplicate creates separate objects",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().length") == 6
              and upgrade_page.locator("[data-group-count]").inner_text() == "3 selected")
        upgrade_page.locator('[data-action="undo"]').first.click()
        check("group duplication is one undo step",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().length") == 3)
        for n in range(3):
            upgrade_page.locator(f'[data-group-select="group-{n}"]').check()
        upgrade_page.once("dialog", lambda d: d.dismiss())
        upgrade_page.locator('[data-group-action="delete"]').click()
        check("group deletion cancellation preserves all objects",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().length") == 3)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator('[data-group-action="delete"]').click()
        check("confirmed group deletion removes selected objects",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().length") == 0)
        upgrade_page.locator('[data-action="undo"]').first.click()
        check("group deletion is one undo step",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.items().length") == 3)
        upgrade_page.locator('[data-group-select="group-0"]').check()
        upgrade_page.locator("#nav [data-page=dashboard]").click()
        upgrade_page.locator("#content .tabbar [data-page=scenarios]").click()
        upgrade_page.locator('[data-action="switch-scenario"][data-id="other"]').click()
        upgrade_page.locator("#nav [data-page=designer]").click()
        check("group selection clears when switching scenarios",
              upgrade_page.locator("[data-group-count]").inner_text() == "0 selected")
        references = {"type":"FeatureCollection","features":[
            {"type":"Feature","properties":{"kind":"tree","name":"Oak <reference>","secret":"discard-me"},
             "geometry":{"type":"Point","coordinates":[-123,44]}},
            {"type":"Feature","properties":{"kind":"building","name":"Barn"},
             "geometry":{"type":"Polygon","coordinates":[[[-123,44],[-122.999,44],
                 [-122.999,44.001],[-123,44.001],[-123,44]]]}}]}
        before_refs = upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        ref_request_count = len(upgrade_requests)
        upgrade_page.locator("[data-reference-file]").set_input_files({
            "name":"supplied.geojson","mimeType":"application/geo+json","buffer":json.dumps(references).encode()})
        upgrade_page.wait_for_function("() => document.querySelector('[data-reference-message]')?.textContent.includes('Imported 2')")
        saved_refs = upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory")
        check("local reference import retains only approved geometry and metadata, not proposed objects",
              len(saved_refs["features"]) == 2 and saved_refs["source"] == "supplied.geojson"
              and "secret" not in saved_refs["features"][0]["properties"]
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_refs
              and len(upgrade_requests) == ref_request_count
              and "Oak <reference>" in upgrade_page.locator("[data-reference-panel]").inner_text()
              and upgrade_page.locator("[data-reference-panel] reference").count() == 0)
        layer_data = upgrade_page.evaluate("""() => {
          const sources={}, layers=[], t=window.__acreforgeUpgradeTest;
          t.addTerrainLayers({addSource:(id,source)=>sources[id]=source,
            getSource:id=>sources[id], addLayer:layer=>layers.push(layer)});
          return {references:sources['supplied-references'].data,
                  existing:sources['estate-features'].data,
                  layerIds:layers.map(l=>l.id)};
        }""")
        check("reference points and polygons use separate map source and distinct layers",
              len(layer_data["references"]["features"]) == 2
              and all(f["properties"].get("name") != "Oak <reference>"
                      for f in layer_data["existing"]["features"])
              and all(x in layer_data["layerIds"] for x in
                      ("supplied-reference-fill","supplied-reference-line","supplied-reference-point")))
        upgrade_page.locator("[data-reference-visible]").uncheck()
        check("reference visibility is temporary and does not delete inventory",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.referenceCollection().features.length") == 0
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory.features.length") == 2)
        upgrade_page.locator("[data-reference-visible]").check()
        validation = upgrade_page.evaluate("""() => {
          const validate=window.__acreforgeUpgradeTest.normalizeReferenceInventory;
          const valid=(f)=>{try{validate(f);return true}catch(e){return false}};
          const point=(coords,kind='tree')=>({type:'Feature',properties:{kind},geometry:{type:'Point',coordinates:coords}});
          const fc=features=>({type:'FeatureCollection',features});
          return {
            crs:valid({...fc([]),crs:{name:'EPSG:3857'}}),
            badKind:valid(fc([point([0,0],'unknown')])),
            badCoord:valid(fc([point([181,0])])),
            extraDimension:valid(fc([point([0,0,1])])),
            tooMany:valid(fc(Array.from({length:501},()=>point([0,0])))),
            badPolygon:valid(fc([{type:'Feature',properties:{kind:'building'},
              geometry:{type:'Polygon',coordinates:[[[0,0],[1,1],[0,1],[1,0],[0,0]]]}}])),
            holes:valid(fc([{type:'Feature',properties:{kind:'building'},
              geometry:{type:'Polygon',coordinates:[[[0,0],[1,0],[1,1],[0,0]],[[.1,.1],[.2,.1],[.2,.2],[.1,.1]]]}}]))
          };
        }""")
        check("reference validation rejects unsupported CRS, types, coordinates, topology and limits",
              not any(validation.values()))
        upgrade_page.locator("[data-reference-file]").set_input_files({
            "name":"bad.geojson","mimeType":"application/json","buffer":b'{"type":"FeatureCollection","features":[null]}'})
        upgrade_page.wait_for_function("() => document.querySelector('[data-reference-message]')?.textContent.includes('Import failed')")
        check("invalid reference import leaves prior inventory intact",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs)
        upgrade_page.locator("[data-reference-file]").set_input_files({
            "name":"huge.geojson","mimeType":"application/json","buffer":b" "*(2*1024*1024+1)})
        upgrade_page.wait_for_function("() => document.querySelector('[data-reference-message]')?.textContent.includes('2 MiB limit')")
        check("oversized reference import preserves previous inventory",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs)
        upgrade_page.once("dialog", lambda d: d.dismiss())
        upgrade_page.locator("[data-reference-file]").set_input_files({
            "name":"replacement.geojson","mimeType":"application/json","buffer":json.dumps(references).encode()})
        upgrade_page.wait_for_function("() => document.querySelector('[data-reference-message]')?.textContent.includes('cancelled')")
        check("cancelled reference replacement preserves the previous inventory",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs)
        upgrade_page.wait_for_timeout(500)
        upgrade_page.reload()
        upgrade_page.locator("#nav [data-page=designer]").click()
        check("reference inventory survives reload independently of proposed objects",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_refs)
        with upgrade_page.expect_download() as ref_backup_info:
            upgrade_page.locator('[data-action="export"]').first.click()
        backup_path = ref_backup_info.value.path()
        backup_data = json.load(open(backup_path,encoding="utf-8"))
        check("project backup retains the user-supplied reference inventory",
              backup_data["project"]["referenceInventory"] == saved_refs)
        upgrade_page.route("https://**/*", lambda route: route.fulfill(
            status=200, body=terrarium_png(), content_type="image/png",
            headers={"Access-Control-Allow-Origin":"*"}))
        upgrade_page.locator('[data-action="toggle-map-view"]').click()
        upgrade_page.locator('#stateHits path[data-state-map="OR"]').click()
        upgrade_page.wait_for_function(
            "() => !!window.__acreforgeUpgradeTest.terrainMap()?.getSource('supplied-references')",
            timeout=30000)
        check("3D terrain map installs the supplied reference layers and data",
              upgrade_page.evaluate("""() => {
                const m=window.__acreforgeUpgradeTest.terrainMap();
                return !!m.getLayer('supplied-reference-point') &&
                  !!m.getLayer('supplied-reference-line') &&
                  m.getSource('supplied-references')._data.features.length === 2;
              }"""))
        upgrade_page.locator("[data-reference-visible]").uncheck()
        check("reference visibility updates the live map source",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.terrainMap().getSource('supplied-references')._data.features.length") == 0)
        upgrade_page.locator("[data-reference-visible]").check()
        upgrade_page.evaluate("""() => window.__acreforgeUpgradeTest.terrainMap().jumpTo(
          {center:[-123,44],zoom:17,pitch:0,bearing:0})""")
        upgrade_page.wait_for_function("""() => {
          const m=window.__acreforgeUpgradeTest.terrainMap(), p=m.project([-123,44]);
          return m.queryRenderedFeatures(p,{layers:['supplied-reference-point']}).length > 0;
        }""", timeout=30000)
        location_before_ref_click = upgrade_page.evaluate(
            "JSON.stringify(window.__acreforgeUpgradeTest.state().project.locationCoordinates)")
        point_xy = upgrade_page.evaluate("""() => {
          const p=window.__acreforgeUpgradeTest.terrainMap().project([-123,44]);
          return {x:p.x,y:p.y};
        }""")
        upgrade_page.locator("#terrainCanvas canvas").click(position=point_xy)
        check("clicking a reference does not replace the selected project location",
              "Unverified reference" in upgrade_page.locator("[data-reference-message]").inner_text()
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.locationCoordinates)") == location_before_ref_click)
        upgrade_page.locator('[data-reference-focus="0"]').click()
        check("reference list offers explicit map focus without changing proposed objects",
              "Showing supplied tree" in upgrade_page.locator("[data-reference-message]").inner_text()
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_refs)
        upgrade_page.on("dialog", accept_public_dialog)
        with upgrade_page.expect_download() as ref_public_info:
            upgrade_page.get_by_role("button", name="Public export").click()
        ref_public = json.load(open(ref_public_info.value.path(),encoding="utf-8"))
        upgrade_page.remove_listener("dialog", accept_public_dialog)
        check("public export removes reference inventory without altering the project",
              "referenceInventory" not in ref_public["project"]
              and upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs)
        upgrade_page.once("dialog", lambda d: d.dismiss())
        upgrade_page.locator("[data-reference-clear]").click()
        check("cancelled reference removal preserves the inventory",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator("[data-reference-clear]").click()
        check("confirmed reference removal leaves proposed objects untouched",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") is None
              and upgrade_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_refs)
        upgrade_page.once("dialog", lambda d: d.accept())
        upgrade_page.locator("#importFile").set_input_files(backup_path)
        upgrade_page.wait_for_function("() => window.__acreforgeUpgradeTest.state().project.referenceInventory?.features.length === 2")
        check("project backup restore normalizes reference inventory",
              upgrade_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceInventory") == saved_refs)
        check("report and recovery upgrades cause no JavaScript errors", not upgrade_errors)
        upgrade_context.close()
        underlay_context = b.new_context(service_workers="block", accept_downloads=True)
        underlay_page = underlay_context.new_page()
        underlay_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        underlay_errors, underlay_requests = [], []
        underlay_page.on("pageerror", lambda e: underlay_errors.append(str(e)))
        underlay_page.on("request", lambda r: underlay_requests.append(r.url)
                         if not r.url.startswith(("http://127.0.0.1","http://localhost","data:","blob:")) else None)
        underlay_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        underlay_page.locator("#nav [data-page=designer]").click()
        check("old projects open with no underlay",
              underlay_page.locator("[data-underlay-status]").inner_text() == "No reference image.")
        initial_objects = underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        image_bytes = base64.b64decode(underlay_page.evaluate("""() => {
          const c=document.createElement('canvas');c.width=200;c.height=100;
          c.getContext('2d').fillRect(0,0,200,100);return c.toDataURL('image/png').split(',')[1];
        }"""))
        underlay_page.locator("[data-underlay-file]").set_input_files({
            "name":"local.png","mimeType":"image/png","buffer":image_bytes})
        underlay_page.wait_for_function("() => document.querySelector('[data-underlay-status]')?.textContent.includes('Image imported locally')")
        check("local PNG import creates an underlay beneath editable objects",
              underlay_page.locator("[data-reference-underlay]").count() == 1
              and underlay_page.evaluate("""() => {
                const image=document.querySelector('[data-reference-underlay]'), objects=document.querySelector('#mapObjects');
                return image.compareDocumentPosition(objects) & Node.DOCUMENT_POSITION_FOLLOWING
                  && image.getAttribute('pointer-events') === 'none';
              }""")
              and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == initial_objects
              and not underlay_requests)
        original_underlay = underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)")
        underlay_page.locator("[data-calibration-pixels]").fill("50")
        underlay_page.locator("[data-calibration-feet]").fill("100")
        underlay_page.locator("[data-underlay-calibrate]").click()
        underlay_page.wait_for_function("() => document.querySelector('[data-calibration-status]')?.textContent.includes('Dimensions calculated')")
        check("horizontal measured span calculates proportional dimensions without saving or changing objects",
              underlay_page.locator('[data-underlay-form] [name=width]').input_value() == "400"
              and underlay_page.locator('[data-underlay-form] [name=height]').input_value() == "200"
              and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)") == original_underlay
              and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == initial_objects
              and not underlay_requests)
        underlay_page.locator("[data-calibration-axis]").select_option("y")
        underlay_page.locator("[data-calibration-pixels]").fill("25")
        underlay_page.locator("[data-calibration-feet]").fill("50")
        underlay_page.locator("[data-underlay-calibrate]").click()
        underlay_page.wait_for_function("() => document.querySelector('[data-calibration-status]')?.textContent.includes('Dimensions calculated')")
        check("vertical measured span uses image height and preserves native aspect ratio",
              underlay_page.locator('[data-underlay-form] [name=width]').input_value() == "400"
              and underlay_page.locator('[data-underlay-form] [name=height]').input_value() == "200")
        underlay_page.evaluate("""() => {
          window.originalBlobArrayBuffer=Blob.prototype.arrayBuffer;
          Blob.prototype.arrayBuffer=function(){
            return new Promise(resolve=>{window.finishCalibrationRead=()=>resolve(window.originalBlobArrayBuffer.call(this))});
          };
        }""")
        underlay_page.locator("[data-underlay-calibrate]").click()
        underlay_page.wait_for_function("() => typeof window.finishCalibrationRead === 'function'")
        underlay_page.locator('[data-underlay-form] [name=width]').fill("333")
        underlay_page.evaluate("""() => {
          window.finishCalibrationRead();Blob.prototype.arrayBuffer=window.originalBlobArrayBuffer;
        }""")
        underlay_page.wait_for_timeout(100)
        check("late calibration does not overwrite a newer placement edit",
              underlay_page.locator('[data-underlay-form] [name=width]').input_value() == "333"
              and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)") == original_underlay)
        underlay_page.locator('[data-underlay-form] [name=width]').fill("400")
        for label, pixels, feet, reason in [
            ("blank", "", "2", "positive finite"), ("zero", "0", "2", "positive finite"),
            ("non-finite", "NaN", "2", "positive finite"), ("negative distance", "1", "-1", "positive finite"),
            ("span beyond image", "101", "10", "cannot exceed"),
            ("too large", "1", "100001", "between 1 and 100,000"),
            ("too small", "100", ".1", "between 1 and 100,000"),
        ]:
            underlay_page.locator("[data-calibration-pixels]").fill(pixels)
            underlay_page.locator("[data-calibration-feet]").fill(feet)
            underlay_page.locator("[data-underlay-calibrate]").click()
            underlay_page.wait_for_function("reason => document.querySelector('[data-calibration-status]')?.textContent.includes(reason)", arg=reason)
            check(f"underlay calibration rejects {label} without changing placement",
                  underlay_page.locator('[data-underlay-form] [name=width]').input_value() == "400"
                  and underlay_page.locator('[data-underlay-form] [name=height]').input_value() == "200"
                  and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)") == original_underlay
                  and not underlay_requests)
        underlay_page.locator('[data-underlay-form] button[type=submit]').click()
        check("calculated image dimensions apply only after explicit placement",
              underlay_page.locator("[data-reference-underlay]").get_attribute("width") == "400"
              and underlay_page.locator("[data-reference-underlay]").get_attribute("height") == "200")
        underlay_page.wait_for_timeout(500)
        underlay_page.reload()
        underlay_page.locator("#nav [data-page=designer]").click()
        underlay_page.wait_for_selector("[data-reference-underlay]")
        check("calibrated image dimensions persist after reload",
              underlay_page.locator("[data-reference-underlay]").get_attribute("width") == "400"
              and underlay_page.locator("[data-reference-underlay]").get_attribute("height") == "200")
        underlay_page.locator('[data-underlay-form] [name="x"]').fill("120")
        underlay_page.locator('[data-underlay-form] [name="y"]').fill("45")
        underlay_page.locator('[data-underlay-form] [name="width"]').fill("400")
        underlay_page.locator('[data-underlay-form] [name="height"]').fill("200")
        underlay_page.locator('[data-underlay-form] [name="opacity"]').fill("35")
        underlay_page.locator('[data-underlay-form] [name="rotation"]').fill("90")
        underlay_page.locator('[data-underlay-form] button[type=submit]').click()
        check("underlay calibration applies local feet and opacity",
              underlay_page.evaluate("""() => {
                const i=document.querySelector('[data-reference-underlay]');
                return ['x','y','width','height','opacity'].map(x=>i.getAttribute(x));
              }""") == ["120","45","400","200","0.35"])
        check("rotated underlay uses its fixed top-left anchor and clockwise plan coordinates",
              underlay_page.evaluate("""() => {
                const i=document.querySelector('[data-reference-underlay]');
                const m=i.transform.baseVal.consolidate().matrix;
                const p=new DOMPoint(120,45).matrixTransform(m);
                const q=new DOMPoint(520,45).matrixTransform(m);
                return Math.abs(p.x-120)<1e-8 && Math.abs(p.y-45)<1e-8 &&
                       Math.abs(q.x-120)<1e-8 && Math.abs(q.y-445)<1e-8 &&
                       i.getAttribute('pointer-events')==='none';
              }""") and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == initial_objects
              and not underlay_requests)
        for value in ["181", "-181", ""]:
            underlay_page.locator('[data-underlay-form] [name="rotation"]').fill(value)
            underlay_page.locator("[data-underlay-form]").evaluate(
                "(form) => form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))")
            check(f"invalid rotation {value or 'blank'} does not replace saved image placement",
                  underlay_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceUnderlay.rotation") == 90
                  and underlay_page.locator("[data-reference-underlay]").get_attribute("transform") == "rotate(90 120 45)")
        underlay_page.locator('[data-underlay-form] [name="rotation"]').fill("-45.5")
        underlay_page.locator('[data-underlay-form] button[type=submit]').click()
        check("fractional counterclockwise rotation updates only the underlay",
              underlay_page.locator("[data-reference-underlay]").get_attribute("transform") == "rotate(-45.5 120 45)"
              and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == initial_objects)
        underlay_page.locator('[data-action="zoom-in"]').first.click()
        check("underlay keeps local placement and remains non-interactive when zooming",
              underlay_page.evaluate("""() => {
                const i=document.querySelector('[data-reference-underlay]');
                return ['x','y','width','height','pointer-events'].map(x=>i.getAttribute(x));
              }""") == ["120","45","400","200","none"])
        check("underlay rotation remains fixed across flat-plan zoom",
              underlay_page.locator("[data-reference-underlay]").get_attribute("transform") == "rotate(-45.5 120 45)")
        underlay_page.locator("[data-underlay-move]").click()
        check("underlay movement requires explicit mode and enables pointer input only while active",
              underlay_page.locator("[data-underlay-move]").get_attribute("aria-pressed") == "true"
              and underlay_page.locator("[data-reference-underlay]").get_attribute("pointer-events") == "all"
              and underlay_page.evaluate("""() => {
                const image=document.querySelector('[data-reference-underlay]'),objects=document.querySelector('#mapObjects');
                return !!(objects.compareDocumentPosition(image)&Node.DOCUMENT_POSITION_FOLLOWING);
              }"""))
        objects_before_move = underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        underlay_page.evaluate("""() => {
          const svg=document.querySelector('#siteMap'),image=document.querySelector('[data-reference-underlay]');
          const point=(x,y)=>{const p=svg.createSVGPoint();p.x=x;p.y=y;const q=p.matrixTransform(document.querySelector('#mapObjects').getScreenCTM());return{x:q.x,y:q.y}};
          const start=point(200,100),end=point(225,115),options={bubbles:true,cancelable:true,pointerId:73,button:0};
          image.dispatchEvent(new PointerEvent('pointerdown',{...options,clientX:start.x,clientY:start.y}));
          svg.dispatchEvent(new PointerEvent('pointermove',{...options,clientX:end.x,clientY:end.y}));
          svg.dispatchEvent(new PointerEvent('pointerup',{...options,clientX:end.x,clientY:end.y}));
        }""")
        check("dragging the rotated reference image changes only its local anchor",
              underlay_page.evaluate("""before => {
                const u=window.__acreforgeUpgradeTest.state().project.referenceUnderlay;
                const image=document.querySelector('[data-reference-underlay]');
                const matrix=image.transform.baseVal.consolidate().matrix,anchor=new DOMPoint(Number(image.getAttribute('x')),Number(image.getAttribute('y'))).matrixTransform(matrix);
                return Math.abs(u.x-145)<1e-3&&Math.abs(u.y-60)<1e-3
                  &&Math.abs(anchor.x-u.x)<1e-3&&Math.abs(anchor.y-u.y)<1e-3
                  &&document.querySelector('[data-underlay-move-status]').textContent.includes('approximate')
                  &&JSON.stringify(window.__acreforgeUpgradeTest.items())===before;
              }""", objects_before_move))
        underlay_page.evaluate("""() => {
          const svg=document.querySelector('#siteMap'),image=document.querySelector('[data-reference-underlay]');
          const point=(x,y)=>{const p=svg.createSVGPoint();p.x=x;p.y=y;const q=p.matrixTransform(document.querySelector('#mapObjects').getScreenCTM());return{x:q.x,y:q.y}};
          const at=point(200,100),options={bubbles:true,cancelable:true,pointerId:74,button:0};
          image.dispatchEvent(new PointerEvent('pointerdown',{...options,clientX:at.x,clientY:at.y}));
          svg.dispatchEvent(new PointerEvent('pointermove',{...options,clientX:at.x+20,clientY:at.y+20}));
        }""")
        underlay_page.keyboard.press("Escape")
        check("Escape cancels an uncommitted underlay drag and restores normal map input",
              underlay_page.evaluate("""() => {
                const u=window.__acreforgeUpgradeTest.state().project.referenceUnderlay;
                const i=document.querySelector('[data-reference-underlay]'),b=document.querySelector('[data-underlay-move]');
                return Math.abs(u.x-145)<1e-3&&Math.abs(u.y-60)<1e-3
                  &&Math.abs(Number(i.getAttribute('x'))-145)<1e-3&&Math.abs(Number(i.getAttribute('y'))-60)<1e-3
                  &&i.getAttribute('pointer-events')==='none'&&b.getAttribute('aria-pressed')==='false'
                  &&document.querySelector('[data-underlay-move-status]').textContent.includes('cancelled')
                  &&!!(i.compareDocumentPosition(document.querySelector('#mapObjects'))&Node.DOCUMENT_POSITION_FOLLOWING);
              }"""))
        underlay_page.locator('[data-action="zoom-fit"]').first.click()
        underlay_page.locator('[data-underlay-form] [name="visible"]').uncheck()
        underlay_page.locator('[data-underlay-form] button[type=submit]').click()
        check("underlay visibility can be turned off without deleting it",
              underlay_page.locator("[data-reference-underlay]").count() == 0
              and underlay_page.evaluate("!!window.__acreforgeUpgradeTest.state().project.referenceUnderlay"))
        underlay_page.locator('[data-underlay-form] [name="visible"]').check()
        underlay_page.locator('[data-underlay-form] button[type=submit]').click()
        underlay_page.wait_for_timeout(500)
        underlay_page.reload()
        underlay_page.locator("#nav [data-page=designer]").click()
        underlay_page.wait_for_selector("[data-reference-underlay]")
        check("underlay bytes and placement persist across reload without localStorage image data",
              underlay_page.locator("[data-reference-underlay]").get_attribute("width") == "400"
              and underlay_page.locator("[data-reference-underlay]").get_attribute("opacity") == "0.35"
              and underlay_page.evaluate("""() => {
                const u=window.__acreforgeUpgradeTest.state().project.referenceUnderlay;
                const i=document.querySelector('[data-reference-underlay]'),m=i.transform.baseVal.consolidate().matrix;
                const anchor=new DOMPoint(Number(i.getAttribute('x')),Number(i.getAttribute('y'))).matrixTransform(m);
                return Math.abs(u.x-145)<1e-3&&Math.abs(u.y-60)<1e-3
                  &&Math.abs(anchor.x-u.x)<1e-3&&Math.abs(anchor.y-u.y)<1e-3;
              }""")
              and underlay_page.evaluate("""() => {
                const p=JSON.parse(localStorage['oregon-estate-planner-v1']);
                return !!p.project.referenceUnderlay && !JSON.stringify(p).includes('data:image/');
              }"""))
        for label, assignment in [("legacy missing angle", "delete p.project.referenceUnderlay.rotation"),
                                  ("invalid saved angle", "p.project.referenceUnderlay.rotation=999")]:
            underlay_page.evaluate("""assignment => {
              const p=JSON.parse(localStorage['oregon-estate-planner-v1']);
              (new Function('p',assignment))(p);
              localStorage['oregon-estate-planner-v1']=JSON.stringify(p);
            }""", assignment)
            underlay_page.reload()
            underlay_page.locator("#nav [data-page=designer]").click()
            underlay_page.wait_for_selector("[data-reference-underlay]")
            check(f"{label} keeps the image and defaults to zero rotation",
                  underlay_page.evaluate("""() => {
                    const u=window.__acreforgeUpgradeTest.state().project.referenceUnderlay;
                    const i=document.querySelector('[data-reference-underlay]'),m=i.transform.baseVal.consolidate().matrix;
                    const anchor=new DOMPoint(Number(i.getAttribute('x')),Number(i.getAttribute('y'))).matrixTransform(m);
                    return u.rotation===0&&Math.abs(u.x-145)<1e-3&&Math.abs(u.y-60)<1e-3
                      &&Math.abs(m.a-1)<1e-8&&Math.abs(m.b)<1e-8&&Math.abs(m.c)<1e-8&&Math.abs(m.d-1)<1e-8
                      &&Math.abs(anchor.x-u.x)<1e-3&&Math.abs(anchor.y-u.y)<1e-3;
                  }"""))
        underlay_page.locator('[data-underlay-form] [name="rotation"]').fill("-45.5")
        underlay_page.locator('[data-underlay-form] button[type=submit]').click()
        underlay_page.wait_for_timeout(500)
        with underlay_page.expect_download() as image_backup:
            underlay_page.locator('[data-action="export"]').first.click()
        backup_json = json.load(open(image_backup.value.path(),encoding="utf-8"))
        check("project backup contains placement but not reference image bytes",
              bool(backup_json["project"]["referenceUnderlay"])
              and backup_json["project"]["referenceUnderlay"]["rotation"] == -45.5
              and "data:image/" not in json.dumps(backup_json))
        def accept_underlay_dialog(dialog):
            dialog.accept()
        underlay_page.on("dialog", accept_underlay_dialog)
        with underlay_page.expect_download() as image_public:
            underlay_page.get_by_role("button",name="Public export").click()
        image_public_data = json.load(open(image_public.value.path(),encoding="utf-8"))
        underlay_page.remove_listener("dialog", accept_underlay_dialog)
        check("public export removes reference underlay metadata",
              "referenceUnderlay" not in image_public_data["project"])
        underlay_page.evaluate("window.__acreforgeUpgradeTest.scenario().items=[]")
        underlay_page.locator('[data-detail="library"] summary').click()
        underlay_page.locator('[data-palette-item="barn"]').first.click()
        before_ids = set(underlay_page.evaluate("window.__acreforgeUpgradeTest.items().map(i=>i.id)"))
        underlay_page.locator("#siteMap").scroll_into_view_if_needed()
        point = underlay_page.evaluate("""() => {
          const svg=document.querySelector('#siteMap'), point=svg.createSVGPoint();
          point.x=300;point.y=200;
          const screen=point.matrixTransform(document.querySelector('#mapObjects').getScreenCTM());
          return {x:screen.x,y:screen.y};
        }""")
        underlay_page.mouse.click(point["x"],point["y"])
        added_items = underlay_page.evaluate("window.__acreforgeUpgradeTest.items()")
        added = [item for item in added_items if item["id"] not in before_ids]
        check("manual placement over the reference produces an ordinary site object",
              len(added) == 1 and added[0]["type"] == "barn"
              and underlay_page.locator(f'[data-object="{added[0]["id"]}"]').count() == 1)
        if added:
            item_id = added[0]["id"]
            underlay_page.evaluate("""() => {
              window.__acreforgeUpgradeTest.state().project.parcelBoundary=window.__acreforgeSpatialTest.normalizeParcelBoundary({
                coordinates:[[[[-123.005,43.995],[-122.995,43.995],[-122.995,44.005],[-123.005,44.005],[-123.005,43.995]]]],
                source:'test'});
            }""")
            scene_before = underlay_page.evaluate("""id => {
              const f=window.__acreforgeSpatialTest.terrainPlanCollection().features.find(x=>x.id===id);
              return f?.geometry;
            }""",item_id)
            underlay_page.locator('[data-object-field="w"]').fill("155")
            underlay_page.locator('[data-object-field="w"]').dispatch_event("change")
            scene_after = underlay_page.evaluate("""id => {
              const f=window.__acreforgeSpatialTest.terrainPlanCollection().features.find(x=>x.id===id);
              return f?.geometry;
            }""",item_id)
            check("manual 2D edits propagate to existing 3D site geometry",
                  scene_before is not None and scene_after is not None and scene_before != scene_after
                  and underlay_page.evaluate(
                      "id=>window.__acreforgeUpgradeTest.items().find(i=>i.id===id).w",item_id) == 155)
        initial_objects = underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        old_image_meta = underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)")
        underlay_page.once("dialog", lambda d: d.dismiss())
        underlay_page.locator("[data-underlay-file]").set_input_files({
            "name":"replacement.png","mimeType":"image/png","buffer":image_bytes})
        underlay_page.wait_for_function("() => document.querySelector('[data-underlay-status]')?.textContent.includes('cancelled')")
        check("cancelled image replacement preserves existing underlay",
              underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)") == old_image_meta
              and underlay_page.locator("[data-reference-underlay]").count() == 1)
        over_dimensions = bytearray(image_bytes)
        over_dimensions[16:20] = struct.pack(">I", 4097)
        for label, payload in [("invalid", b"not an image"), ("truncated", image_bytes[:24]), ("dimensions", bytes(over_dimensions)),
                               ("size", b" "*(5*1024*1024+1))]:
            underlay_page.locator("[data-underlay-file]").set_input_files({
                "name":label+".png","mimeType":"image/png","buffer":payload})
            underlay_page.wait_for_function("() => document.querySelector('[data-underlay-status]')?.textContent.startsWith('Image import failed:')")
            check(f"underlay rejects {label} image without replacing existing image",
                  underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)") == old_image_meta
                  and underlay_page.locator("[data-reference-underlay]").count() == 1)
        underlay_page.once("dialog", lambda d: d.dismiss())
        underlay_page.locator("[data-underlay-remove]").click()
        check("cancelling underlay removal preserves image", underlay_page.locator("[data-reference-underlay]").count() == 1)
        underlay_page.once("dialog", lambda d: d.accept())
        underlay_page.locator("[data-underlay-remove]").click()
        underlay_page.wait_for_function("() => document.querySelector('[data-underlay-status]')?.textContent.includes('removed')")
        check("confirmed underlay removal clears image without changing site objects",
              underlay_page.locator("[data-reference-underlay]").count() == 0
              and underlay_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == initial_objects
              and not underlay_requests)
        underlay_page.wait_for_timeout(500)
        underlay_page.reload()
        underlay_page.locator("#nav [data-page=designer]").click()
        check("underlay removal persists after reload", underlay_page.locator("[data-reference-underlay]").count() == 0)
        jpeg = base64.b64decode(underlay_page.evaluate("""() => {
          const c=document.createElement('canvas');c.width=2;c.height=2;
          c.getContext('2d').fillRect(0,0,2,2);
          return c.toDataURL('image/jpeg').split(',')[1];
        }"""))
        underlay_page.locator("[data-underlay-file]").set_input_files({
            "name":"local.jpg","mimeType":"image/jpeg","buffer":jpeg})
        underlay_page.wait_for_function("() => document.querySelector('[data-underlay-status]')?.textContent.includes('Image imported locally')")
        check("local JPEG image imports without external requests",
              underlay_page.locator("[data-reference-underlay]").count() == 1 and not underlay_requests)
        old_id = underlay_page.evaluate("window.__acreforgeUpgradeTest.state().project.referenceUnderlay.id")
        underlay_page.once("dialog", lambda d: d.accept())
        underlay_page.locator("[data-underlay-file]").set_input_files({
            "name":"replacement.png","mimeType":"image/png","buffer":image_bytes})
        underlay_page.wait_for_function(
            "id => window.__acreforgeUpgradeTest.state().project.referenceUnderlay.id !== id", arg=old_id)
        underlay_page.wait_for_function("""id => new Promise(resolve => {
          const r=indexedDB.open('acreforge-reference-images');
          r.onsuccess=()=>{const t=r.result.transaction('images');const g=t.objectStore('images').get(id);
            g.onsuccess=()=>{r.result.close();resolve(g.result===undefined)}};
        })""", arg=old_id)
        check("confirmed replacement deletes the previous local image",
              underlay_page.locator("[data-reference-underlay]").count() == 1)
        underlay_page.wait_for_timeout(500)
        saved = underlay_page.evaluate("localStorage['oregon-estate-planner-v1']")
        missing_context = b.new_context(service_workers="block")
        missing_page = missing_context.new_page()
        missing_page.add_init_script(
            "localStorage.setItem('acreforge-guide-seen','1');localStorage.setItem('oregon-estate-planner-v1',"
            + json.dumps(saved) + ");")
        missing_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        missing_page.locator("#nav [data-page=designer]").click()
        missing_page.wait_for_function("() => document.querySelector('[data-underlay-status]')?.textContent.includes('Re-import')")
        check("backup metadata without local image reports re-import",
              missing_page.locator("[data-reference-underlay]").count() == 0)
        before_missing_calibration = missing_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)")
        missing_page.locator("[data-calibration-pixels]").fill("1")
        missing_page.locator("[data-calibration-feet]").fill("10")
        missing_page.locator("[data-underlay-calibrate]").click()
        missing_page.wait_for_function("() => document.querySelector('[data-calibration-status]')?.textContent.includes('re-import')")
        check("calibration of missing image reports re-import and preserves placement",
              missing_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.state().project.referenceUnderlay)") == before_missing_calibration)
        missing_context.close()
        check("underlay workflow produces no JavaScript errors", not underlay_errors)
        underlay_context.close()
        asset_context = b.new_context(service_workers="block", accept_downloads=True)
        asset_page = asset_context.new_page()
        asset_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        asset_errors, asset_requests = [], []
        asset_page.on("pageerror", lambda e: asset_errors.append(str(e)))
        asset_page.on("request", lambda r: asset_requests.append(r.url)
                      if not r.url.startswith(("http://127.0.0.1","http://localhost","data:","blob:")) else None)
        asset_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        asset_page.locator("#nav [data-page=designer]").click()
        check("old project has an empty reusable object library",
              asset_page.evaluate("window.__acreforgeUpgradeTest.state().project.assetPresets") == [])
        asset_page.evaluate("window.__acreforgeUpgradeTest.scenario().items=[]")
        asset_page.locator('[data-detail="library"] summary').click()
        asset_page.locator('[data-palette-item="barn"]').first.click()
        def click_plan(page, x, y):
            page.locator("#siteMap").scroll_into_view_if_needed()
            point = page.evaluate("""p => {
              const svg=document.querySelector('#siteMap'), q=svg.createSVGPoint();
              q.x=p[0];q.y=p[1];const r=q.matrixTransform(document.querySelector('#mapObjects').getScreenCTM());
              return {x:r.x,y:r.y};
            }""", [x,y])
            page.mouse.click(point["x"],point["y"])
        click_plan(asset_page,300,200)
        asset_page.locator('[data-object-field="name"]').fill("Reusable barn")
        asset_page.locator('[data-object-field="name"]').dispatch_event("change")
        asset_page.locator('[data-object-field="w"]').fill("155")
        asset_page.locator('[data-object-field="w"]').dispatch_event("change")
        asset_page.locator("[data-asset-save]").click()
        preset = asset_page.evaluate("window.__acreforgeUpgradeTest.state().project.assetPresets[0]")
        check("save selected object creates bounded reusable project preset",
              preset["name"] == "Reusable barn" and preset["w"] == 155
              and "x" not in preset and "id" in preset and "status" not in preset)
        asset_page.wait_for_timeout(500)
        asset_page.reload(wait_until="domcontentloaded")
        asset_page.locator("#nav [data-page=designer]").click()
        check("reusable presets persist after reload",
              asset_page.locator("[data-asset-place]").count() == 1
              and asset_page.evaluate("window.__acreforgeUpgradeTest.state().project.assetPresets[0].w") == 155)
        with asset_page.expect_download() as asset_backup:
            asset_page.locator('[data-action="export"]').first.click()
        asset_data = json.load(open(asset_backup.value.path(),encoding="utf-8"))
        check("project backups include reusable object presets",
              asset_data["project"]["assetPresets"][0]["name"] == "Reusable barn")
        asset_page.once("dialog", lambda d: d.accept())
        with asset_page.expect_download() as asset_public:
            asset_page.get_by_role("button",name="Public export").click()
        public_data = json.load(open(asset_public.value.path(),encoding="utf-8"))
        check("public export retains disclosed reusable object presets",
              public_data["project"]["assetPresets"][0]["name"] == "Reusable barn")
        invalid_data = json.loads(json.dumps(asset_data))
        invalid_data["project"]["assetPresets"].extend([
            dict(preset, id="bad-dimensions", w=-1),
            dict(preset, id="bad-type", type="constructor"),
            dict(preset, id="bad-color", color='"><script>'),
        ])
        restored_context = b.new_context(service_workers="block")
        restored = restored_context.new_page()
        restored.add_init_script(
            "localStorage.setItem('acreforge-guide-seen','1');localStorage.setItem('oregon-estate-planner-v1',"
            + json.dumps(json.dumps(invalid_data)) + ");")
        restored.goto("http://127.0.0.1:8766/?spatial-test=1")
        check("restored presets discard invalid data and preserve valid settings",
              restored.evaluate("window.__acreforgeUpgradeTest.state().project.assetPresets") == [preset])
        restored_context.close()
        asset_page.locator("[data-asset-place]").click()
        asset_page.once("dialog", lambda d: d.dismiss())
        click_plan(asset_page,280,240)
        check("cancelling an overlapping preset placement preserves objects",
              len(asset_page.evaluate("window.__acreforgeUpgradeTest.items()")) == 1)
        asset_page.locator("[data-asset-place]").click()
        click_plan(asset_page,500,300)
        asset_items = asset_page.evaluate("window.__acreforgeUpgradeTest.items()")
        check("saved preset places a distinct ordinary editable object",
              len(asset_items) == 2 and asset_items[-1]["name"] == "Reusable barn"
              and asset_items[-1]["w"] == 155 and asset_items[-1]["id"] != asset_items[0]["id"]
              and asset_items[-1]["status"] == "Preliminary")
        asset_page.locator('[data-action="undo"]').first.click()
        check("preset placement is undoable without removing the preset",
              len(asset_page.evaluate("window.__acreforgeUpgradeTest.items()")) == 1
              and asset_page.locator("[data-asset-place]").count() == 1)
        asset_page.once("dialog", lambda d: d.dismiss())
        asset_page.locator("[data-asset-delete]").click()
        check("cancelled preset deletion retains the library", asset_page.locator("[data-asset-place]").count() == 1)
        asset_page.once("dialog", lambda d: d.accept())
        asset_page.locator("[data-asset-delete]").click()
        check("confirmed preset deletion leaves placed objects intact",
              asset_page.locator("[data-asset-place]").count() == 0
              and len(asset_page.evaluate("window.__acreforgeUpgradeTest.items()")) == 1)
        check("reusable object workflow makes no external requests or JavaScript errors",
              not asset_requests and not asset_errors)
        asset_context.close()
        view_context = b.new_context(service_workers="block", accept_downloads=True)
        view_page = view_context.new_page()
        view_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        view_errors, view_requests = [], []
        view_page.on("pageerror", lambda e: view_errors.append(str(e)))
        view_page.on("request", lambda r: view_requests.append(r.url)
                     if not r.url.startswith(("http://127.0.0.1","http://localhost","data:","blob:")) else None)
        view_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        view_page.locator("#nav [data-page=designer]").click()
        check("old project starts without saved plan views",
              view_page.evaluate("window.__acreforgeUpgradeTest.state().project.planViews") == [])
        view_page.locator('[data-action="zoom-in"]').first.click()
        view_page.locator('[data-tool="pan"]').click()
        view_page.locator("#siteMap").scroll_into_view_if_needed()
        box = view_page.locator("#siteMap").bounding_box()
        view_page.mouse.move(box["x"]+box["width"]/2,box["y"]+box["height"]/2)
        view_page.mouse.down()
        view_page.mouse.move(box["x"]+box["width"]/2+80,box["y"]+box["height"]/2+50,steps=4)
        view_page.mouse.up()
        before_view = view_page.evaluate("""() => {
          const v=document.querySelector('#siteMap').viewBox.baseVal;
          return [v.x+v.width/2,v.y+v.height/2,v.width,v.height];
        }""")
        before_objects = view_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())")
        view_page.locator('#planViewName').fill('Entrance <overview>')
        view_page.locator('[data-plan-view-form] button').click()
        view = view_page.evaluate("window.__acreforgeUpgradeTest.state().project.planViews[0]")
        check("named view saves zoom and panned local center without changing objects",
              view["name"] == "Entrance <overview>"
              and math.isclose(view["x"],before_view[0],abs_tol=0.01)
              and math.isclose(view["y"],before_view[1],abs_tol=0.01)
              and view_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_objects
              and view_page.locator("[data-plan-views] overview").count() == 0)
        view_page.locator('[data-action="zoom-fit"]').first.click()
        view_page.locator('[data-plan-view-open]').click()
        after_view = view_page.evaluate("""() => {
          const v=document.querySelector('#siteMap').viewBox.baseVal;
          return [v.x+v.width/2,v.y+v.height/2,v.width,v.height];
        }""")
        check("opening a saved view restores plan center and zoom",
              all(math.isclose(a,b,abs_tol=0.01) for a,b in zip(before_view,after_view))
              and view_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_objects)
        view_page.wait_for_timeout(500)
        view_page.reload()
        view_page.locator("#nav [data-page=designer]").click()
        view_page.locator('[data-plan-view-open]').click()
        after_reload = view_page.evaluate("""() => {
          const v=document.querySelector('#siteMap').viewBox.baseVal;
          return [v.x+v.width/2,v.y+v.height/2,v.width,v.height];
        }""")
        check("saved view persists and restores after reload",
              all(math.isclose(a,b,abs_tol=0.01) for a,b in zip(before_view,after_reload)))
        with view_page.expect_download() as view_backup:
            view_page.locator('[data-action="export"]').first.click()
        view_data = json.load(open(view_backup.value.path(),encoding="utf-8"))
        view_page.once("dialog",lambda d:d.accept())
        with view_page.expect_download() as view_public:
            view_page.get_by_role("button",name="Public export").click()
        public_views = json.load(open(view_public.value.path(),encoding="utf-8"))
        check("backups and public exports include disclosed saved views",
              view_data["project"]["planViews"] == [view]
              and public_views["project"]["planViews"] == [view])
        broken = json.loads(json.dumps(view_data))
        broken["project"]["planViews"].extend([
            dict(view,id="bad-zoom",zoom=0),
            dict(view,id="bad-coordinate",x=1000001),
            dict(view,id="bad-name",name=" " * 3),
            dict(view,id=view["id"]),
        ])
        restored_context = b.new_context(service_workers="block")
        restored_view = restored_context.new_page()
        restored_view.add_init_script(
            "localStorage.setItem('acreforge-guide-seen','1');localStorage.setItem('oregon-estate-planner-v1',"
            + json.dumps(json.dumps(broken)) + ");")
        restored_view.goto("http://127.0.0.1:8766/?spatial-test=1")
        check("invalid and duplicate saved views are discarded on restore",
              restored_view.evaluate("window.__acreforgeUpgradeTest.state().project.planViews") == [view])
        restored_view.locator("#nav [data-page=designer]").click()
        restored_view.locator("#planViewName").fill("   ")
        restored_view.locator('[data-plan-view-form] button').click()
        check("whitespace-only view names are rejected",
              len(restored_view.evaluate("window.__acreforgeUpgradeTest.state().project.planViews")) == 1
              and "Enter a view name" in restored_view.locator("[data-plan-view-status]").inner_text())
        restored_view.evaluate("""() => {
          const v=window.__acreforgeUpgradeTest.state().project.planViews[0];
          window.__acreforgeUpgradeTest.state().project.planViews=
            Array.from({length:20},(_,i)=>({...v,id:'view-'+i,name:'View '+i}));
        }""")
        restored_view.locator("#planViewName").fill("Overflow")
        restored_view.locator('[data-plan-view-form] button').click()
        check("saved view count is limited to 20",
              len(restored_view.evaluate("window.__acreforgeUpgradeTest.state().project.planViews")) == 20
              and "at most 20" in restored_view.locator("[data-plan-view-status]").inner_text())
        restored_view.locator('[data-action="toggle-map-view"]').click()
        check("saved flat-plan views cannot be applied to the geographic map",
              restored_view.locator('[data-plan-view-open]').first.is_disabled()
              and restored_view.locator('[data-plan-view-form] button').is_disabled())
        restored_context.close()
        view_page.once("dialog",lambda d:d.dismiss())
        view_page.locator('[data-plan-view-delete]').click()
        check("cancelled view removal preserves bookmark", view_page.locator('[data-plan-view-open]').count() == 1)
        view_page.once("dialog",lambda d:d.accept())
        view_page.locator('[data-plan-view-delete]').click()
        view_page.wait_for_timeout(500)
        view_page.reload()
        view_page.locator("#nav [data-page=designer]").click()
        check("confirmed view removal persists without changing objects",
              view_page.locator('[data-plan-view-open]').count() == 0
              and view_page.evaluate("JSON.stringify(window.__acreforgeUpgradeTest.items())") == before_objects)
        check("saved plan views cause no external requests or JavaScript errors", not view_requests and not view_errors)
        view_context.close()
        sketch_context = b.new_context(service_workers="block")
        sketch = sketch_context.new_page()
        sketch_errors = []
        sketch.on("pageerror", lambda e: sketch_errors.append(str(e)))
        sketch.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        sketch.goto("http://127.0.0.1:8766/?spatial-test=1")
        sketch.evaluate("""() => {
          const api=window.__acreforgeUpgradeTest;
          api.scenario().items=[
            {id:'land1',type:'tree',name:'Tree',x:0,y:0,w:10,h:10,shape:'circle'},
            {id:'land2',type:'tree',name:'Tree',x:20,y:0,w:10,h:10,shape:'circle'},
            {id:'land3',type:'grove',name:'Grove',x:40,y:0,w:20,h:10,shape:'rect'},
            {id:'land4',type:'path',name:'Path',x:0,y:40,w:50,h:4,shape:'rect'},
            {id:'land5',type:'barn',name:'Barn',x:0,y:50,w:20,h:10,shape:'rect'}
          ]; api.save();
        }""")
        sketch.locator("#nav [data-page=designer]").click()
        schedule = sketch.locator("[data-landscape-schedule]")
        schedule.locator("summary").click()
        check("landscape schedule counts objects and reports footprint and path length",
              "4 objects" in schedule.inner_text()
              and "2" in schedule.locator("tr", has_text="Tree / Shade Tree").inner_text()
              and "157 sq ft footprint" in schedule.inner_text()
              and "200 sq ft footprint" in schedule.inner_text()
              and "50 ft length" in schedule.inner_text()
              and "Barn" not in schedule.inner_text()
              and "not individual plants" in schedule.inner_text())
        sketch.locator('[data-detail="objects"] summary').click()
        sketch.locator('[data-select-object="land1"]').click()
        sketch.locator('[data-object-field="shape"]').select_option("rect")
        check("landscape schedule stays open and recalculates after a real object edit",
              schedule.get_attribute("open") is not None
              and "179 sq ft footprint" in schedule.inner_text())
        sketch.locator('#content .tabbar [data-page="homes"]').click()
        panel = sketch.locator("#homeElevation")
        plan_before = sketch.evaluate("""() => JSON.stringify(
          JSON.parse(localStorage['oep-home'] || '{"levels":[{"walls":[],"doors":[],"wins":[],"furn":[],"rooms":[]}]}').levels)""")
        form = panel.locator("[data-elevation-form]")
        for field, value in (("x1", "1"), ("y1", "0"), ("x2", "21"), ("y2", "10")):
            form.locator(f'[name="{field}"]').fill(value)
        form.locator('button[type="submit"]').click()
        check("elevation coordinates add a saved line without changing the floor plan",
              panel.locator("[data-elevation-lines] line").count() == 1
              and sketch.evaluate("JSON.parse(localStorage['oep-home']).elevations.front[0]") == [1, 0, 21, 10]
              and sketch.evaluate("JSON.stringify(JSON.parse(localStorage['oep-home']).levels)") == plan_before)
        panel.locator("[data-elevation-view]").select_option("rear")
        check("elevation sides are independent",
              panel.locator("[data-elevation-lines] line").count() == 0)
        canvas = panel.locator("[data-elevation-canvas]")
        canvas.click(position={"x": 40, "y": 40})
        canvas.click(position={"x": 160, "y": 80})
        check("pointer drawing adds a line on the selected side",
              panel.locator("[data-elevation-lines] line").count() == 1
              and len(sketch.evaluate("JSON.parse(localStorage['oep-home']).elevations.rear")) == 1)
        for field, value in (("x1", "5"), ("y1", "5"), ("x2", "5"), ("y2", "5")):
            form.locator(f'[name="{field}"]').fill(value)
        form.locator('button[type="submit"]').click()
        check("elevation rejects zero-length lines",
              "two different points" in panel.locator("[data-elevation-status]").inner_text()
              and panel.locator("[data-elevation-lines] line").count() == 1)
        sketch.reload()
        sketch.locator("#nav [data-page=designer]").click()
        sketch.locator('#content .tabbar [data-page="homes"]').click()
        panel = sketch.locator("#homeElevation")
        check("elevation sketches persist after reload",
              panel.locator("[data-elevation-lines] line").count() == 1)
        panel.locator("[data-elevation-view]").select_option("rear")
        sketch.once("dialog", lambda d: d.dismiss())
        panel.locator("[data-elevation-clear]").click()
        check("cancelling elevation clear preserves the selected side",
              panel.locator("[data-elevation-lines] line").count() == 1)
        panel.locator("[data-elevation-undo]").click()
        check("removing the last line preserves the other elevation",
              panel.locator("[data-elevation-lines] line").count() == 0
              and len(sketch.evaluate("JSON.parse(localStorage['oep-home']).elevations.front")) == 1)
        panel.locator("[data-elevation-view]").select_option("front")
        sketch.evaluate("""() => {
          window.__elevationSetItem = Storage.prototype.setItem;
          Storage.prototype.setItem = function(k,v) {
            if (k === 'oep-home') throw new Error('test quota failure');
            return window.__elevationSetItem.call(this,k,v);
          };
        }""")
        panel.locator("[data-elevation-undo]").click()
        check("elevation storage failure is reported without losing the line",
              "Could not save" in panel.locator("[data-elevation-status]").inner_text()
              and panel.locator("[data-elevation-lines] line").count() == 1
              and len(sketch.evaluate("JSON.parse(localStorage['oep-home']).elevations.front")) == 1)
        sketch.evaluate("() => { Storage.prototype.setItem = window.__elevationSetItem; }")
        check("landscape and elevation additions produce no JavaScript errors", not sketch_errors)
        sketch_context.close()
        office_context = b.new_context(service_workers="block", reduced_motion="reduce")
        office = office_context.new_page()
        office_errors = []
        office.on("pageerror", lambda e: office_errors.append(str(e)))
        office.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        office.goto("http://127.0.0.1:8766/?spatial-test=1")
        office.locator("#nav [data-page=designer]").click()
        office.locator('#content .tabbar [data-page="homes"]').click()
        def office_point(x, y):
            return office.evaluate("""([x,y]) => {
              const s=document.querySelector('#hbsvg'), p=s.createSVGPoint();
              p.x=x; p.y=y; const q=p.matrixTransform(s.getScreenCTM());
              return {x:q.x,y:q.y};
            }""", [x, y])
        office.locator("#hbrt").select_option(label="Office")
        office.locator('#hb [data-tool="room"]').click()
        start, end = office_point(5, 5), office_point(25, 20)
        office.mouse.move(start["x"], start["y"])
        office.mouse.down()
        office.mouse.move(end["x"], end["y"], steps=4)
        office.mouse.up()
        check("office room can be drawn as an editable floor plan",
              office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].rooms[0].t") == "Office"
              and office.locator('#hbsvg [data-k="room"]').count() == 1)
        office.locator('#hb [data-tool="door"]').click()
        p = office_point(10, 5)
        office.mouse.click(p["x"], p["y"])
        office.locator('#hb [data-tool="win"]').click()
        p = office_point(18, 5)
        office.mouse.click(p["x"], p["y"])
        office.locator('#hb [data-tool="move"]').click()
        office.locator('#hbsvg [data-k="door"] rect').click()
        check("legacy door openings retain their original default width",
              office.locator('[data-opening-in="widthIn"]').input_value() == "36"
              and float(office.locator('#hbsvg [data-k="door"] rect').get_attribute("width")) == 3)
        office.locator('[data-opening-in="widthIn"]').fill("42")
        office.locator('[data-opening-in="widthIn"]').dispatch_event("change")
        office.locator('[data-opening-in="heightIn"]').fill("84")
        office.locator('[data-opening-in="heightIn"]').dispatch_event("change")
        check("door width and height accept inch dimensions and update the plan",
              office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].doors[0].widthIn") == 42
              and office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].doors[0].heightIn") == 84
              and float(office.locator('#hbsvg [data-k="door"] rect').get_attribute("width")) == 3.5)
        office.locator("#hbsvg").scroll_into_view_if_needed()
        p = office_point(18, 5)
        office.mouse.click(p["x"], p["y"])
        office.locator('[data-opening-in="widthIn"]').fill("60")
        office.locator('[data-opening-in="widthIn"]').dispatch_event("change")
        office.locator('[data-opening-in="heightIn"]').fill("48")
        office.locator('[data-opening-in="heightIn"]').dispatch_event("change")
        office.locator('[data-opening-in="widthIn"]').fill("241")
        office.locator('[data-opening-in="widthIn"]').dispatch_event("change")
        check("window dimensions render in feet and reject out-of-range inches",
              office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].wins[0].widthIn") == 60
              and office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].wins[0].heightIn") == 48
              and float(office.locator('#hbsvg [data-k="win"] rect').get_attribute("width")) == 5
              and "1 to 240" in office.locator("[data-building-error]").inner_text())
        office.locator('[data-opening-in="widthIn"]').blur()
        office.locator('#hb [data-tool="move"]').click()
        office.locator('#hbsvg [data-k="room"] rect').click(position={"x": 20, "y": 20})
        office.locator("[data-ceiling-in]").fill("120")
        office.locator("[data-ceiling-in]").dispatch_event("change")
        check("office ceiling is saved and labeled in the floor plan",
              office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].rooms[0].ceilingIn") == 120
              and "ceiling 120 in" in office.locator('#hbsvg [data-k="room"]').text_content())
        office.locator("[data-ceiling-in]").fill("361")
        office.locator("[data-ceiling-in]").dispatch_event("change")
        check("office ceiling rejects values outside the supported range",
              "24 to 360" in office.locator("[data-building-error]").inner_text()
              and office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].rooms[0].ceilingIn") == 120)
        office.locator("[data-ceiling-in]").blur()
        office.locator("#hbq").fill("outlet")
        office.locator('#hb [data-tool="f:outlet"]').click()
        p = office_point(8, 8)
        office.mouse.click(p["x"], p["y"])
        check("office outlet can be placed as a visible editable symbol",
              office.evaluate("JSON.parse(localStorage['oep-home']).levels[0].furn[0].t") == "outlet"
              and office.locator('#hbsvg [data-k="furn"] title').first.text_content() == "Electrical outlet (concept)")
        office.locator("#hbview").click()
        model = office.locator("#hbsvg").inner_html()
        walls_before = office.locator('#hbsvg polygon[fill="#f4efe6"]').evaluate_all(
            "els => els.map(el => el.getAttribute('points'))")
        check("building 3D view renders the office geometry with the new backdrop",
              'hbBackdrop' in model and 'polygon' in model)
        office.locator("#hbview").click()
        office.locator('#hb [data-tool="move"]').click()
        office.locator('#hbsvg [data-k="room"] rect').click(position={"x": 20, "y": 20})
        office.locator("[data-ceiling-in]").fill("180")
        office.locator("[data-ceiling-in]").dispatch_event("change")
        office.locator("#hbview").click()
        check("3D wall geometry changes when the office ceiling height changes",
              office.locator('#hbsvg polygon[fill="#f4efe6"]').count() > 0
              and office.locator('#hbsvg polygon[fill="#f4efe6"]').evaluate_all(
                  "els => els.map(el => el.getAttribute('points'))") != walls_before)
        office.locator("#hbview").click()
        with office.expect_download() as downloaded:
            office.locator("#hbdxf").click()
        with open(downloaded.value.path(), encoding="utf-8") as exported:
            dxf = exported.read()
        check("floor-plan DXF uses edited door and window widths",
              "DOOR-OPENINGS-L1\n10\n8.250\n20\n-5.000\n30\n0\n11\n11.750" in dxf
              and "WINDOWS-L1\n10\n15.500\n20\n-5.000\n30\n0\n11\n20.500" in dxf)
        elevation_form = office.locator("#homeElevation [data-elevation-form]")
        for field, value in (("x1", "1"), ("y1", "0"), ("x2", "21"), ("y2", "10")):
            elevation_form.locator(f'[name="{field}"]').fill(value)
        elevation_form.locator('button[type="submit"]').click()
        with office_context.expect_page() as printed:
            office.locator("#hbprint").click()
        sheets = printed.value
        sheets.wait_for_load_state()
        check("printable sheets include actual floor plan, opening dimensions and outlet",
              sheets.locator("section.sheet").count() == 2
              and "Office" in sheets.locator("section.sheet").first.inner_text()
              and "180 in" in sheets.locator("section.sheet").first.inner_text()
              and "42 × 84" in sheets.locator("section.sheet").first.inner_text()
              and "60 × 48" in sheets.locator("section.sheet").first.inner_text()
              and "8, 8" in sheets.locator("section.sheet").first.inner_text()
              and "not for construction" in sheets.locator("section.sheet").first.inner_text())
        check("printable elevation sheet includes drawn line and coordinates",
              sheets.locator('svg[aria-label="front elevation sketch"] line').count() == 1
              and "1, 0" in sheets.locator("section.sheet").last.inner_text()
              and "21, 10" in sheets.locator("section.sheet").last.inner_text()
              and "not projected" in sheets.locator("section.sheet").last.inner_text())
        sheets.close()
        office.reload()
        office.locator("#nav [data-page=designer]").click()
        office.locator('#content .tabbar [data-page="homes"]').click()
        saved = office.evaluate("JSON.parse(localStorage['oep-home']).levels[0]")
        check("office dimensions and outlet survive a reload",
              saved["rooms"][0]["ceilingIn"] == 180
              and saved["doors"][0]["widthIn"] == 42
              and saved["wins"][0]["heightIn"] == 48
              and saved["furn"][0]["t"] == "outlet"
              and not office_errors)
        office_context.close()
        cad_context = b.new_context(service_workers="block", accept_downloads=True, reduced_motion="reduce")
        cad = cad_context.new_page()
        cad_errors = []
        cad.on("pageerror", lambda e: cad_errors.append(str(e)))
        cad.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        cad.goto("http://127.0.0.1:8766/?spatial-test=1")
        cad.locator("#nav [data-page=designer]").click()
        cad.locator('#content .tabbar [data-page="homes"]').click()
        def cad_run(text):
            cad.locator("#hbcmdin").fill(text)
            cad.locator("#hbcmdin").press("Enter")
        def cad_state():
            return cad.evaluate("JSON.parse(localStorage['oep-home']||'{}')")
        def cad_out():
            return cad.locator("#hbcmdout").inner_text(), cad.locator("#hbcmdout").get_attribute("data-state")
        cad_run("HELP")
        check("CAD command help lists commands, hotkeys and honest DXF/DWG limits",
              all(s in cad_out()[0] for s in ("ROOM x y w h", "DXF", "not DWG", "Ctrl/Cmd+Z")))
        for text, tool in (("WALL", "wall"), ("DOOR", "door"), ("WINDOW", "win"), ("ERASE", "erase"), ("DIM", "dim"), ("ROOM", "room"), ("MOVE", "move")):
            cad_run(text)
            check(f"command {text} selects the {tool} tool",
                  cad.locator(f'#hb [data-tool="{tool}"].on').count() == 1)
        cad_run("ROOM 10 10 12 14 office")
        cad_run("WALL 0 0 20 0")
        cad_run("DIM 0 0 20 0")
        lvl = cad_state()["levels"][0]
        check("coordinate commands create a room, wall and dimension in feet",
              lvl["rooms"][0] == {"x": 10, "y": 10, "w": 12, "h": 14, "t": "Office"}
              and [0, 0, 20, 0] in lvl["walls"] and lvl["dims"] == [[0, 0, 20, 0]])
        before = cad.evaluate("JSON.stringify(JSON.parse(localStorage['oep-home']).levels)")
        for bad in ("BOGUS", "ROOM 1 2", "ROOM 1 1 0 5", "ROOM 1 1 5 5 spaceship", "WALL 0 0 5 5", "WALL 0 0 0 0", "WALL 0 0 99999 0", "LEVEL 9", "ROOM a b c d"):
            cad_run(bad)
            check(f"invalid command '{bad}' reports an error and changes nothing",
                  cad_out()[1] == "error"
                  and cad.evaluate("JSON.stringify(JSON.parse(localStorage['oep-home']).levels)") == before)
        cad_run("UNDO")
        check("UNDO command removes the last drawing", not cad_state()["levels"][0].get("dims"))
        cad_run("REDO")
        check("REDO command restores it", cad_state()["levels"][0]["dims"] == [[0, 0, 20, 0]])
        cad.locator("#content").focus()
        cad.keyboard.press("Control+z")
        check("Ctrl+Z hotkey undoes once", not cad_state()["levels"][0].get("dims"))
        cad.keyboard.press("Control+y")
        check("Ctrl+Y hotkey redoes once", cad_state()["levels"][0]["dims"] == [[0, 0, 20, 0]])
        cad.keyboard.press("3")
        check("number hotkey selects tools", cad.locator('#hb [data-tool="wall"].on').count() == 1)
        cad.keyboard.press("v")
        check("V hotkey toggles to 3D and back", cad.locator("#hbview").inner_text() == "Back to 2D plan")
        cad.keyboard.press("v")
        check("V hotkey returns to 2D", cad.locator("#hbview").inner_text() == "3D view")
        cad_run("3D")
        cad_run("2D")
        check("2D and 3D commands switch the view", cad.locator("#hbview").inner_text() == "3D view")
        cad.locator("#content").focus()
        cad.keyboard.press("f")
        check("F hotkey fits the drawing area", cad_state()["W"] == 72)
        cad.keyboard.press("/")
        check("slash hotkey focuses the command line", cad.evaluate("document.activeElement.id") == "hbcmdin")
        cad.keyboard.type("fvx2")
        check("hotkeys do not fire while typing in the command line",
              cad.locator("#hbcmdin").input_value() == "fvx2" and cad.locator("#hbview").inner_text() == "3D view"
              and cad.locator('#hb [data-tool="wall"].on').count() == 1)
        cad.locator("#hbcmdin").press("Escape")
        cad.locator("#hbcmdin").fill("")
        cad.locator("#hbname").focus()
        cad.keyboard.type("x")
        check("hotkeys do not fire in other text fields", "x" in cad.locator("#hbname").input_value())
        cad.locator("#content").focus()
        with cad.expect_download() as cad_dxf:
            cad.keyboard.press("x")
        cad_text = open(cad_dxf.value.path(), encoding="utf-8").read()
        check("X hotkey exports conceptual ASCII DXF with the commanded geometry",
              cad_dxf.value.suggested_filename.endswith(".dxf") and "NOT FOR CONSTRUCTION" in cad_text
              and "WALLS-L1" in cad_text and "DIMS-L1" in cad_text and "EOF" in cad_text)
        with cad.expect_download() as cad_dxf2:
            cad_run("DXF")
        check("DXF command exports a download", cad_dxf2.value.suggested_filename.endswith(".dxf"))
        cad.keyboard.press("Control+Shift+x")
        check("modified browser shortcuts are not intercepted", cad_state()["levels"][0]["dims"] == [[0, 0, 20, 0]])
        check("CAD commands raised no page errors", not cad_errors)
        check("Space & building builder states free scope and honest DXF/DWG limits and links to CAD Studio",
              "space & building builder" in cad.locator("#hb h2").inner_text().lower()
              and "not DWG" in cad.locator("#cadscope").inner_text()
              and "Free to use" in cad.locator("#cadscope").inner_text()
              and cad.locator("#cadscope [data-page=cad]").count() == 1)
        check("main nav names the CAD Studio entry",
              "CAD Studio" in cad.locator("#nav").inner_text())
        cad.locator("#nav [data-page=dashboard]").click()
        check("dashboard offers CAD Studio and it opens the builder",
              "DXF only" in cad.locator("#cadstudiocard").inner_text())
        cad.locator("#cadstudiocard button").click()
        check("dashboard CAD Studio button opens the drafting workspace", cad.locator("#cadcv").is_visible())
        cad_context.close()
        cs_context = b.new_context(service_workers="block", accept_downloads=True, reduced_motion="reduce", viewport={"width": 1400, "height": 900})
        cs = cs_context.new_page()
        cs_errors = []
        cs.on("pageerror", lambda e: cs_errors.append(str(e)))
        cs.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        cs.goto("http://127.0.0.1:8766/?spatial-test=1")
        cs.locator("#nav [data-page=cad]").click()
        def cs_cmd(text):
            cs.locator("#cadcmd").fill(text)
            cs.locator("#cadcmd").press("Enter")
        def cs_doc():
            return cs.evaluate("JSON.parse(localStorage['acreforge-cad-v1'])")
        def cs_log():
            return cs.locator("#cadlog").inner_text()
        check("CAD Studio opens as its own dark full drafting canvas with command line",
              cs.locator("#cadcv").count() == 1 and cs.locator("#cadcmd").count() == 1
              and cs.locator("#cadlayers .cadlay").count() >= 7 and cs.locator("#cadcv").evaluate("c=>c.width>500&&c.height>300"))
        check("interaction status starts in Ready", cs.locator("#cadmode").get_attribute("data-state") == "READY"
              and cs.locator("#cadmode").inner_text() == "Mode: Ready")
        cs_cmd("LINE")
        check("LINE prompts for the first point", "first point" in cs.locator("#cadprompt").inner_text()
              and cs.locator("#cadmode").get_attribute("data-state") == "POINT"
              and cs.locator("#cadmode").inner_text() == "Mode: Pick point")
        cs_cmd("0,0")
        cs_cmd("@120<0")
        cs_cmd("")
        d = cs_doc()
        ln = [e for e in d["ents"] if e["t"] == "line"]
        check("LINE accepts absolute, polar relative coordinates and Enter to finish",
              len(ln) == 1 and ln[0]["a"] == [0, 0] and abs(ln[0]["b"][0] - 120) < 1e-6 and abs(ln[0]["b"][1]) < 1e-6)
        cs_cmd("RECT"); cs_cmd("200,0"); cs_cmd("@42,60")
        r = [e for e in cs_doc()["ents"] if e["t"] == "pline"][0]
        check("RECT supports inch relative corners",
              r["closed"] and r["pts"][2] == [242, 60])
        cs_cmd("CIRCLE"); cs_cmd("50,50")
        check("interaction status changes from point to number input", cs.locator("#cadmode").get_attribute("data-state") == "NUMBER"
              and cs.locator("#cadmode").inner_text() == "Mode: Enter number")
        cs_cmd("12")
        check("CIRCLE takes center and radius", any(e["t"] == "circle" and e["r"] == 12 for e in cs_doc()["ents"]))
        cs_cmd("ROOM"); cs_cmd("0,200"); cs_cmd("3'6\"")
        check("feet-and-inches notation is rejected", "not accepted" in cs_log().lower() or "feet" in cs_log().lower() or "invalid" in cs_log().lower())
        cs_cmd("ESC") if False else None
        cs.locator("#cadcmd").press("Escape")
        cs_cmd("ROOM"); cs_cmd("0,200"); cs_cmd("@216,288")
        check("interaction status identifies text entry", cs.locator("#cadmode").get_attribute("data-state") == "TEXT"
              and cs.locator("#cadmode").inner_text() == "Mode: Enter text")
        cs_cmd("Living Room")
        d = cs_doc()
        rooms = [e for e in d["ents"] if e["t"] == "room"]
        walls = [e for e in d["ents"] if e["t"] == "wall"]
        check("ROOM creates four walls and a labeled room with exact size and area",
              len(rooms) == 1 and len(walls) == 4 and rooms[0]["name"] == "Living Room"
              and cs.evaluate("AcreCAD.cmd.roomSize(JSON.parse(localStorage['acreforge-cad-v1']).ents.find(e=>e.t==='room'))") == "216\" x 288\""
              and cs.evaluate("Math.round(Math.abs(AcreCAD.core.area(JSON.parse(localStorage['acreforge-cad-v1']).ents.find(e=>e.t==='room').pts))/144)") == 432)
        cs_cmd("DOOR")
        check("interaction status identifies object picking", cs.locator("#cadmode").get_attribute("data-state") == "OBJECT"
              and cs.locator("#cadmode").inner_text() == "Mode: Pick object")
        cs.evaluate("AcreCAD.cmd.clickEnt(AcreCAD.core.doc.ents.find(e=>e.t==='wall'))")
        cs_cmd("36"); cs_cmd("24")
        cs_cmd("WINDOW")
        cs.evaluate("AcreCAD.cmd.clickEnt(AcreCAD.core.doc.ents.filter(e=>e.t==='wall')[1])")
        cs_cmd("48"); cs_cmd("")
        d = cs_doc()
        dr = [e for e in d["ents"] if e["t"] == "door"]; wn = [e for e in d["ents"] if e["t"] == "window"]
        check("DOOR and WINDOW are placed on walls with inch width, offset, sill and head",
              len(dr) == 1 and dr[0]["w"] == 36 and dr[0]["pos"] == 24 and dr[0]["head"] == 80
              and len(wn) == 1 and wn[0]["w"] == 48 and wn[0]["sill"] == 36)
        cs_cmd("DOOR")
        cs.evaluate("AcreCAD.cmd.clickEnt(AcreCAD.core.doc.ents.find(e=>e.t==='wall'))")
        cs_cmd("9999")
        check("oversized opening is rejected", "wider than the wall" in cs_log() and len([e for e in cs_doc()["ents"] if e["t"] == "door"]) == 1)
        cs_cmd("OUTLET"); cs_cmd("30,230"); cs_cmd("18")
        check("OUTLET stores position and height", any(e["t"] == "outlet" and e["h"] == 18 for e in cs_doc()["ents"]))
        cs_cmd("DIM"); cs_cmd("0,200"); cs_cmd("216,200"); cs_cmd("")
        dm = [e for e in cs_doc()["ents"] if e["t"] == "dim"]
        check("DIM creates a dimension with default offset", len(dm) == 1 and dm[0]["off"] == 12)
        cs_cmd("TEXT"); cs_cmd("10,10"); cs_cmd("9"); cs_cmd("NOTE")
        check("TEXT adds annotation", any(e["t"] == "text" and e["s"] == "NOTE" for e in cs_doc()["ents"]))
        cs_cmd("DIST"); cs_cmd("0,0"); cs_cmd("30,40")
        check("DIST reports distance and angle", "50\"" in cs_log() and "53.1" in cs_log())
        cs_cmd("AREA"); cs_cmd("0,0"); cs_cmd("144,0"); cs_cmd("144,144"); cs_cmd("0,144"); cs_cmd("")
        check("AREA reports area and perimeter", "20736" in cs_log() and "sq in" in cs_log())
        n = len(cs_doc()["ents"])
        cs_cmd("UNDO")
        check("UNDO removes the last drawing", cs_doc()["ents"].__len__() == n - 1)
        cs_cmd("REDO")
        check("REDO restores it", len(cs_doc()["ents"]) == n)
        cs_cmd("BOGUS")
        check("unknown commands are reported, not silently accepted", "Unknown command" in cs_log())
        cs_cmd("LINE"); cs_cmd("banana")
        check("invalid point input is rejected and prompt stays", "Invalid input" in cs_log() and "first point" in cs.locator("#cadprompt").inner_text())
        cs.locator("#cadcmd").press("Escape")
        check("Esc cancels the active command and returns to Ready",
              cs.locator("#cadprompt").inner_text() == "Command:"
              and cs.locator("#cadmode").get_attribute("data-state") == "READY")
        # layers
        cs_cmd("LAYER"); cs_cmd("NEW"); cs_cmd("A-TEST")
        cs_cmd("LAYER"); cs_cmd("COLOR"); cs_cmd("A-TEST"); cs_cmd("red")
        cs_cmd("LAYER"); cs_cmd("LTYPE"); cs_cmd("A-TEST"); cs_cmd("DASHED")
        cs_cmd("LINE"); cs_cmd("0,-100"); cs_cmd("50,-100"); cs_cmd("")
        d = cs_doc()
        check("LAYER NEW/COLOR/LTYPE create a current layer and objects land on it",
              d["layers"]["A-TEST"]["color"] == 1 and d["layers"]["A-TEST"]["ltype"] == "DASHED"
              and d["cur"] == "A-TEST" and d["ents"][-1]["layer"] == "A-TEST")
        cs_cmd("LAYER"); cs_cmd("LOCK"); cs_cmd("A-TEST")
        cs_cmd("SELECTALL")
        check("locked layers are excluded from selection", cs.evaluate("AcreCAD.cmd.R.sel.every(id=>AcreCAD.core.byId(id).layer!=='A-TEST')"))
        cs.locator('.cadlay[data-lay="A-WALL"] [data-act="on"]').click()
        check("layer visibility toggle hides objects and persists", cs_doc()["layers"]["A-WALL"]["on"] is False)
        cs.locator('.cadlay[data-lay="A-WALL"] [data-act="on"]').click()
        # snaps
        cs.evaluate("AcreCAD.fit()")
        snap = cs.evaluate("""()=>{const C=AcreCAD.core;
          const a=C.osnap([121,1],5,{osnap:true});const m=C.osnap([60,2],5,{osnap:true});
          const x=C.osnap([100,0],5,{osnap:true});return [a.k,a.p,m.k,m.p,x.k]}""")
        check("object snaps find endpoints and midpoints", snap[0] in ("end", "int") and snap[2] == "mid" and snap[3] == [60, 0])
        isect = cs.evaluate("""()=>{const C=AcreCAD.core;C.doc.ents.push({id:9001,t:'line',a:[60,-20],b:[60,20],layer:'0'});
          const r=C.osnap([61,1],5,{osnap:true});C.doc.ents.pop();return [r.k,r.p]}""")
        check("intersection snap finds line crossings", isect[0] == "int" and isect[1] == [60, 0])
        per = cs.evaluate("AcreCAD.core.osnap([40,30],40,{osnap:false,perp:true,from:[40,30]})")
        check("grid snap rounds to the grid", cs.evaluate("AcreCAD.core.osnap([7,10],0.1,{osnap:false,grid:true}).p")==[6,12])
        check("ortho and polar constrain direction",
              cs.evaluate("AcreCAD.core.constrain([0,0],[10,3],'ortho')") == [10, 0]
              and abs(cs.evaluate("AcreCAD.core.constrain([0,0],[10,9],'polar')")[1] - cs.evaluate("AcreCAD.core.constrain([0,0],[10,9],'polar')")[0]) < 1e-6)
        # mouse: crosshair coordinate readout + click-drawing
        box = cs.locator("#cadcv").bounding_box()
        cs.locator("#cadcmd").fill("")
        cs.mouse.move(box["x"] + 300, box["y"] + 200)
        check("live coordinate readout follows the cursor", "X " in cs.locator("#cadcoord").inner_text())
        nl0 = len([e for e in cs_doc()["ents"] if e["t"] == "line"])
        cs_cmd("LINE")
        cs.mouse.click(box["x"] + 300, box["y"] + 200)
        cs.mouse.click(box["x"] + 400, box["y"] + 200)
        cs.locator("#cadcmd").press("Escape")
        check("canvas clicks supply points to the active command", len([e for e in cs_doc()["ents"] if e["t"] == "line"]) == nl0 + 1)
        # window / crossing selection
        selection_snap_states = {}
        for toggle in ("osnap", "snap"):
            button = cs.locator(f'[data-tg="{toggle}"]')
            selection_snap_states[toggle] = button.get_attribute("aria-pressed") == "true"
            if selection_snap_states[toggle]:
                button.click()
        cs.locator("#cadcv").scroll_into_view_if_needed()
        box = cs.locator("#cadcv").bounding_box()
        cs.evaluate("AcreCAD.cmd.R.sel=[];AcreCAD.fit()")
        cs.mouse.move(box["x"] + 2, box["y"] + 2); cs.mouse.down()
        check("interaction transition table enters drag mode on pointer down",
              cs.locator("#cadmode").get_attribute("data-state") == "DRAG")
        cs.mouse.move(box["x"] + box["width"] - 2, box["y"] + box["height"] - 2, steps=4)
        check("interaction transition table classifies left-to-right window drags",
              cs.locator("#cadmode").get_attribute("data-state") == "WINDOW")
        cs.mouse.up()
        check("dragging right makes a window selection", cs.evaluate("AcreCAD.cmd.R.sel.length")> 3 and cs.evaluate("AcreCAD.state.drag===null"))
        cs.locator("#cadcv").scroll_into_view_if_needed()
        box = cs.locator("#cadcv").bounding_box()
        cs.evaluate("AcreCAD.cmd.R.sel=[];AcreCAD.refresh();AcreCAD.fit()")
        cs.mouse.move(box["x"] + box["width"] - 2, box["y"] + box["height"] - 2); cs.mouse.down()
        cs.mouse.move(box["x"] + 2, box["y"] + 2, steps=4)
        check("interaction transition table classifies right-to-left crossing drags",
              cs.locator("#cadmode").get_attribute("data-state") == "CROSSING")
        cs.mouse.up()
        check("dragging left makes a crossing selection", cs.evaluate("AcreCAD.cmd.R.sel.length")> 3 and cs.evaluate("AcreCAD.state.drag===null"))
        check("finishing a crossing selection returns to selection-ready mode",
              cs.locator("#cadmode").get_attribute("data-state") == "SELECTED")
        for toggle, was_on in selection_snap_states.items():
            if was_on:
                cs.locator(f'[data-tg="{toggle}"]').click()
        cs.evaluate("""() => {
          AcreCAD.cmd.R.sel=[];
          const cv=document.querySelector("#cadcv"),r=cv.getBoundingClientRect();
          cv.dispatchEvent(new MouseEvent("mousedown",{bubbles:true,button:0,clientX:r.right-2,clientY:r.bottom-2}));
          window.dispatchEvent(new MouseEvent("mouseup",{bubbles:true,button:0,clientX:r.left+2,clientY:r.top+2}));
        }""")
        check("selection uses release coordinates if intermediate drag events are coalesced",
              cs.evaluate("AcreCAD.cmd.R.sel.length>3 && AcreCAD.state.drag===null"))
        # MOVE / COPY / ERASE with implied selection
        cs.evaluate("AcreCAD.cmd.R.sel=[AcreCAD.core.doc.ents.find(e=>e.t==='circle').id]")
        cs_cmd("MOVE"); cs_cmd("0,0"); cs_cmd("10,0")
        check("MOVE moves the selected object", cs.evaluate("AcreCAD.core.doc.ents.find(e=>e.t==='circle').c")==[60,50])
        cs_cmd("COPY"); cs_cmd("0,0"); cs_cmd("0,100"); cs_cmd("")
        check("COPY duplicates the object", len([e for e in cs_doc()["ents"] if e["t"] == "circle"]) == 2)
        cs.evaluate("AcreCAD.cmd.R.sel=[AcreCAD.core.doc.ents.filter(e=>e.t==='circle')[1].id]")
        cs_cmd("ERASE")
        check("ERASE removes the selection", len([e for e in cs_doc()["ents"] if e["t"] == "circle"]) == 1)
        # walls erase removes their openings
        wid = cs.evaluate("AcreCAD.core.doc.ents.find(e=>e.t==='door').wall")
        cs.evaluate("AcreCAD.cmd.R.sel=[%d]" % wid)
        cs_cmd("ERASE")
        check("erasing a wall also removes its door", not any(e["t"] == "door" for e in cs_doc()["ents"]))
        # properties panel edit in inches
        cs.evaluate("AcreCAD.cmd.R.sel=[AcreCAD.core.doc.ents.find(e=>e.t==='window').id];AcreCAD.refresh()")
        cs.locator('[data-eprop="w"]').fill("60"); cs.locator('[data-eprop="w"]').press("Tab")
        check("properties panel edits a window width in inches", cs.evaluate("AcreCAD.core.doc.ents.find(e=>e.t==='window').w") == 60)
        cs.locator('[data-eprop="w"]').fill("9999"); cs.locator('[data-eprop="w"]').press("Tab")
        check("properties panel rejects out-of-range values", cs.evaluate("AcreCAD.core.doc.ents.find(e=>e.t==='window').w") == 60)
        cs.locator('[data-prop="ceil"]').fill("9'"); cs.locator('[data-prop="ceil"]').press("Tab")
        check("ceiling height rejects feet notation", cs_doc()["ceil"] == 96)
        cs.locator('[data-prop="ceil"]').fill("108"); cs.locator('[data-prop="ceil"]').press("Tab")
        check("ceiling height accepts inches", cs_doc()["ceil"] == 108)
        cs.evaluate("AcreCAD.core.doc.cur='0'"); cs_cmd("LINE"); cs_cmd("0,500"); cs_cmd("100,500"); cs_cmd("")
        cs.evaluate("AcreCAD.cmd.R.sel=[AcreCAD.core.doc.ents.filter(e=>e.t==='line').pop().id]"); cs_cmd("ROTATE"); cs_cmd("0,500"); cs_cmd("90"); cs.evaluate("AcreCAD.cmd.R.sel=[]")
        rl = [e for e in cs_doc()["ents"] if e["t"] == "line"][-1]
        check("ROTATE turns a line 90 degrees about the base point", abs(rl["b"][0]) < 1e-6 and abs(rl["b"][1] - 600) < 1e-6)
        cs_cmd("ARC"); cs_cmd("300,500"); cs_cmd("320,500"); cs_cmd("300,520")
        check("ARC stores center, radius and angles", any(e["t"] == "arc" and e["r"] == 20 and e["a1"] == 90 and abs(e["r"] - 20) < 1e-6 for e in cs_doc()["ents"]))
        cs_cmd("UNITS"); cs_cmd("mm")
        cs_cmd("DIST"); cs_cmd("0,0"); cs_cmd("25.4,0")
        check("UNITS mm displays millimetres", "mm" in cs_log())
        cs_cmd("UNITS"); cs_cmd("in")
        cs_cmd("LINE"); cs_cmd("0,0"); cs_cmd("300mm,0"); cs_cmd("")
        check("length input accepts a mm suffix and stores inches", abs([e for e in cs_doc()["ents"] if e["t"] == "line"][-1]["b"][0] - 11.811) < 0.01)
        cs_cmd("PROFILE"); cs_cmd("User"); cs_cmd("C")

        check("User profile maps alias C to CIRCLE", "CIRCLE" in cs.locator("#cadprompt").inner_text().upper() or "center" in cs.locator("#cadprompt").inner_text().lower())
        cs.locator("#cadcmd").press("Escape"); cs_cmd("PROFILE"); cs_cmd("Default")
        check("canvas backing store follows devicePixelRatio", cs.evaluate("document.getElementById('cadcv').width") >= cs.evaluate("document.getElementById('cadcv').clientWidth"))
        cs.evaluate("AcreCAD.core.doc.cur='0'"); cs_cmd("LINE"); cs_cmd("0,700"); cs_cmd("100,700"); cs_cmd("")
        ln_id = cs.evaluate("AcreCAD.core.doc.ents.filter(e=>e.t==='line').pop().id")
        cs_cmd("OFFSET"); cs_cmd("10"); cs.evaluate("AcreCAD.cmd.clickEnt(AcreCAD.core.byId(%d))" % ln_id); cs_cmd("50,800"); cs.locator("#cadcmd").press("Escape")
        ol = [e for e in cs_doc()["ents"] if e["t"] == "line"][-1]
        check("OFFSET makes a parallel line at the typed distance", abs(ol["a"][1] - 710) < 1e-6 and ol["id"] != ln_id)
        cs.evaluate("AcreCAD.cmd.R.sel=[%d]" % ln_id); cs_cmd("MIRROR"); cs_cmd("0,0"); cs_cmd("1,0"); cs_cmd("No"); cs.evaluate("AcreCAD.cmd.R.sel=[]")
        ml = [e for e in cs_doc()["ents"] if e["t"] == "line"][-1]
        check("MIRROR about the X axis adds a reflected copy", abs(ml["a"][1] + 700) < 1e-6)
        cs_cmd("RECT"); cs_cmd("1000,0"); cs_cmd("1100,100")
        pid = cs.evaluate("AcreCAD.core.doc.ents.filter(e=>e.t==='pline').pop().id")
        cs_cmd("HATCH"); cs.evaluate("AcreCAD.cmd.clickEnt(AcreCAD.core.byId(%d))" % pid); cs_cmd("ANSI31"); cs_cmd("10")
        check("HATCH creates a hatch object that exports as DXF lines", any(e["t"] == "hatch" for e in cs_doc()["ents"]) and cs.evaluate("AcreCAD.cmd.exportDXF()").count("LINE") > 10)
        cs_cmd("PROFILE"); cs_cmd("User")
        cs.locator("body").click(position={"x": 5, "y": 5}) if False else None
        cs.evaluate("document.activeElement.blur()")
        cs.keyboard.press("Control+Shift+C")
        check("User profile hotkey Ctrl+Shift+C starts CIRCLE", "center" in cs.locator("#cadprompt").inner_text().lower())
        cs.keyboard.press("Escape"); cs_cmd("PROFILE"); cs_cmd("Default")
        check("DXF has ARC entity", "ARC" in cs.evaluate("AcreCAD.cmd.exportDXF()"))
        # persistence
        cs.reload(); cs.locator("#nav [data-page=cad]").click()
        check("drawing persists after reload", len(cs_doc()["ents"]) > 5 and cs.locator("#cadlayers .cadlay").count() >= 8)
        # DXF
        cs_cmd("DXF")
        dxf = cs.evaluate("window.__cadLastDxf")
        check("DXF export is R12 with layer table and LINE/POLYLINE/CIRCLE/TEXT entities and no DWG claim",
              dxf.startswith("0\r\nSECTION") and "AC1009" in dxf and "A-WALL" in dxf and all(k in dxf for k in ("\r\nLINE\r\n", "\r\nPOLYLINE\r\n", "\r\nCIRCLE\r\n", "\r\nTEXT\r\n")) and dxf.rstrip().endswith("EOF"))
        check("DXF contains the room label with size and area", "Living Room 216\" x 288\" 62208 sq in" in dxf)
        cs_cmd("HELP")
        check("CAD help states the limited DXF import/export and conceptual limits",
              "limited ASCII R12 import" in cs.locator("#cadhelptxt").text_content()
              and "DWG" in cs.locator("#cadhelptxt").text_content())
        cs.locator("#cadfs").click()
        check("full viewport toggle fills the screen", cs.locator("#cadwrap.cadfull").count() == 1)
        # Chunk 3: elevations, roof, section, vector PDF
        cs_cmd("ROOF"); cs_cmd("gable"); cs_cmd("6"); cs_cmd("12")
        roof = cs.evaluate("AcreCADSheets.roof()")
        check("ROOF gable 6/12 computes span, rise, ridge and area", roof["type"] == "gable" and roof["pitch"] == 6 and abs(roof["span"] - 240) < 2 and abs(roof["rise"] - 60) < 1 and abs(roof["ridgeLength"] - 312) < 2 and abs(roof["area"] - 2 * 312 * 120 * (1.25 ** 0.5)) < 5)
        hip = cs.evaluate("AcreCADSheets.roof({type:'hip'})"); shed = cs.evaluate("AcreCADSheets.roof({type:'shed'})")
        check("hip, shed, gambrel and barn roofs differ sensibly", hip["ridgeLength"] == 72 and shed["rise"] == 120 and all(cs.evaluate("AcreCADSheets.roof({type:'%s'}).area" % k) > 0 for k in ("gambrel", "barn")))
        els = cs.evaluate("['front','rear','left','right'].map(s=>AcreCADSheets.elevation(s))")
        check("four elevations derive from the plan (front/rear widths 192/264 swap with sides)", len(els) == 4 and abs(els[0]["width"] - els[2]["width"]) > 1 and els[0]["width"] == els[1]["width"] and els[2]["width"] == els[3]["width"])
        check("elevations include door/window openings from the plan", sum(len(e["openings"]) for e in els) >= 1)
        cs_cmd("ELEV")
        check("ELEV reports each elevation", "front elevation" in cs_log() and "right elevation" in cs_log())
        sec = cs.evaluate("AcreCADSheets.section()")
        check("section has wall height and roof profile", sec["height"] > 0 and len(sec["roof"]) >= 3)
        pdf_info = cs.evaluate("AcreCADSheets.build({paper:'ARCH D'})")
        pdf = pdf_info["pdf"]
        check("PDF is a real vector PDF with header, xref and EOF", pdf.startswith("%PDF-1.4") and "xref" in pdf and pdf.rstrip().endswith("%%EOF") and " re S" in pdf and " l S" in pdf)
        check("PDF has 10 sheets with ARCH D 36x24 in MediaBox", pdf_info["pages"] == 10 and "/Count 10" in pdf and "[0 0 2592 1728]" in pdf)
        check("PDF has title block, sheet numbers, north arrow, concept labels and inch units", all(k in pdf for k in ("Sheet 2 of 10", "Units: inches", "(N) Tj", "Electrical plan \\(CONCEPT\\)", "Plumbing plan \\(CONCEPT\\)", "NOT FOR CONSTRUCTION", "Front elevation", "Scale: 1:")))
        check("PDF sheet sizes for Letter, ARCH E, B, A", all(cs.evaluate("AcreCADSheets.build({paper:'%s'}).size" % k) == v for k, v in (("Letter", [11, 8.5]), ("ARCH E", [48, 36]), ("B", [17, 11]), ("A", [11, 8.5]))))
        selected_pdf = cs.evaluate("AcreCADSheets.build({paper:'ARCH D',sheets:['cover','floor-plan']})")
        check("PDF sheet selection keeps only requested sheets in canonical order",
              selected_pdf["pages"] == 2
              and selected_pdf["sheets"] == ["cover", "floor-plan"]
              and "(Floor plan)" in selected_pdf["pdf"]
              and "Sheets: Floor plan." in selected_pdf["pdf"]
              and "Front elevation" not in selected_pdf["pdf"])
        empty_pdf = cs.evaluate("AcreCADSheets.build({sheets:[]})")
        check("PDF export rejects an empty sheet selection",
              empty_pdf["pages"] == 0 and not empty_pdf["pdf"]
              and "at least one" in empty_pdf["message"])
        invalid_pdf = cs.evaluate("AcreCADSheets.build({sheets:['unknown']})")
        check("PDF export rejects unknown sheet identifiers",
              invalid_pdf["pages"] == 0 and not invalid_pdf["pdf"]
              and "unknown sheet" in invalid_pdf["message"])
        preview_pdf = cs.evaluate("""async () => {
          const r = AcreCADSheets.preview({paper:"ARCH D",sheets:["cover","floor-plan"]});
          const data = r.url ? new Uint8Array(await (await fetch(r.url)).arrayBuffer()) : [];
          const text = String.fromCharCode(...data.slice(0, 40));
          const ok = r.pages === 2 && r.sheets.join(",") === "cover,floor-plan"
            && r.url.startsWith("blob:") && text.startsWith("%PDF-1.4");
          URL.revokeObjectURL(r.url);
          return ok;
        }""")
        check("PDF preview builds a local blob containing only selected sheets", preview_pdf)
        png_multi = cs.evaluate("""async () => {
          const r = await AcreCADSheets.renderPNG({paper:"Letter",sheets:["cover","floor-plan"]});
          return !r.blob && r.pages === 0 && r.message.includes("exactly one");
        }""")
        check("PNG export requires exactly one selected drawing sheet", png_multi)
        png_sheet = cs.evaluate("""async () => {
          const r = await AcreCADSheets.renderPNG({paper:"Letter",sheets:["cover"]});
          if (!r.blob) return {ok:false,message:r.message};
          const data = new Uint8Array(await r.blob.arrayBuffer());
          const bitmap = await createImageBitmap(r.blob);
          const canvas = document.createElement("canvas");
          canvas.width = bitmap.width; canvas.height = bitmap.height;
          const ctx = canvas.getContext("2d"); ctx.drawImage(bitmap,0,0); bitmap.close();
          const pixels = ctx.getImageData(0,0,canvas.width,canvas.height).data;
          let ink = false;
          for (let i=0; i<pixels.length; i+=4) if (pixels[i]<220 || pixels[i+1]<220 || pixels[i+2]<220) { ink=true; break; }
          return {ok:r.blob.type==="image/png" && data[0]===137 && data[1]===80
            && r.pages===1 && r.sheets[0]==="cover" && r.width===1056 && r.height===816
            && r.dpi===96 && ink, width:r.width, height:r.height, dpi:r.dpi};
        }""")
        check("PNG renderer creates a paper-sized local image with visible sheet content",
              png_sheet["ok"] and png_sheet["width"] > 0 and png_sheet["height"] > 0)
        paper_before_export = cs.evaluate("AcreCAD.core.doc.paper")
        cs.locator("#cadexportopen").click()
        check("export wizard opens with a PDF format, paper choice, and concept disclosure",
              cs.locator("#cadexport").is_visible()
              and cs.locator("#cadexportformat").input_value() == "pdf"
              and cs.locator("#cadexportpaper").is_visible()
              and cs.locator("[data-cad-export-sheet]").count() == 10
              and cs.locator("[data-cad-export-sheet]:checked").count() == 10
              and cs.locator("#cadexportpaper").input_value() == (paper_before_export or "Letter")
              and "conceptual vector-PDF" in cs.locator("#cadexportdescription").inner_text()
              and "not construction documents" in cs.locator("#cadexport .cadexportlimit").inner_text())
        cs.select_option("#cadexportpaper", "Legal")
        cs.locator("#cadexportcancel").click()
        check("canceling the export wizard leaves the saved paper size unchanged",
              not cs.locator("#cadexport").is_visible()
              and cs.evaluate("AcreCAD.core.doc.paper") == paper_before_export)
        cs.locator("#cadexportopen").click()
        cs.select_option("#cadexportformat", "dxf")
        check("DXF wizard option hides paper and explains inch-based R12 output",
              not cs.locator("#cadexportpaper").is_visible()
              and not cs.locator("#cadexportsheetswrap").is_visible()
              and "R12 DXF" in cs.locator("#cadexportdescription").inner_text()
              and "inches" in cs.locator("#cadexportdescription").inner_text())
        cs.select_option("#cadexportformat", "pdf")
        cs.select_option("#cadexportpaper", "ARCH D")
        for sheet in cs.locator("[data-cad-export-sheet]").all():
            sheet.uncheck()
        check("export wizard requires at least one selected PDF sheet",
              cs.locator("#cadexportgo").is_disabled()
              and cs.locator("#cadexportpreview").is_disabled()
              and "Select at least one PDF sheet" in cs.locator("#cadexportdescription").inner_text())
        cs.locator('[data-cad-export-sheet][value="cover"]').check()
        cs.locator('[data-cad-export-sheet][value="floor-plan"]').check()
        cs.evaluate("""() => {
          window.__cadRevokedPreviewUrls = [];
          window.__cadOriginalRevokeObjectURL = URL.revokeObjectURL.bind(URL);
          URL.revokeObjectURL = url => {
            window.__cadRevokedPreviewUrls.push(url);
            window.__cadOriginalRevokeObjectURL(url);
          };
        }""")
        cs.locator("#cadexportpreview").click()
        preview_url = cs.locator("#cadpdfpreviewframe").get_attribute("src")
        preview_bytes = cs.evaluate("""async url => Array.from(new Uint8Array(await (await fetch(url)).arrayBuffer()).slice(0, 100))""", preview_url)
        check("export wizard previews selected PDF sheets in an embedded local document",
              cs.locator("#cadpdfpreview").is_visible()
              and preview_url.startswith("blob:")
              and bytes(preview_bytes).startswith(b"%PDF-1.4")
              and "2 selected" in cs.locator("#cadpdfpreviewstatus").inner_text()
              and cs.evaluate("AcreCAD.core.doc.paper") == paper_before_export)
        cs.locator("#cadpdfpreviewclose").click()
        check("closing PDF preview revokes its temporary local URL",
              not cs.locator("#cadpdfpreview").is_visible()
              and cs.locator("#cadpdfpreviewframe").get_attribute("src") == "about:blank"
              and cs.evaluate("(url) => window.__cadRevokedPreviewUrls.includes(url)", preview_url))
        cs.locator("#cadexportpreview").click()
        escape_preview_url = cs.locator("#cadpdfpreviewframe").get_attribute("src")
        cs.locator("#cadpdfpreviewclose").focus()
        cs.keyboard.press("Escape")
        cs.locator("#cadpdfpreview").wait_for(state="hidden")
        cs.wait_for_function("(url) => window.__cadRevokedPreviewUrls.includes(url)", arg=escape_preview_url)
        check("dismissing PDF preview with Escape revokes its temporary local URL",
              cs.locator("#cadpdfpreviewframe").get_attribute("src") == "about:blank")
        cs.evaluate("URL.revokeObjectURL=window.__cadOriginalRevokeObjectURL;delete window.__cadRevokedPreviewUrls;delete window.__cadOriginalRevokeObjectURL")
        with cs.expect_download() as dl:
            cs.locator("#cadexportgo").click()
        dpath = dl.value.path(); data = open(dpath, "rb").read()
        check("export wizard downloads only selected vector-PDF sheets and saves paper size",
              dl.value.suggested_filename.endswith(".pdf") and data.startswith(b"%PDF-")
              and b"/Count 2" in data and b"[0 0 2592 1728]" in data
              and b"(Floor plan)" in data and b"(Front elevation)" not in data
              and cs.evaluate("AcreCAD.core.doc.paper") == "ARCH D"
              and not cs.locator("#cadexport").is_visible())
        cs.locator("#cadexportopen").click()
        cs.select_option("#cadexportformat", "png")
        check("PNG wizard requires exactly one sheet and hides PDF preview",
              cs.locator("#cadexportsheetswrap").is_visible()
              and not cs.locator("#cadexportpreview").is_visible()
              and cs.locator("#cadexportgo").is_disabled()
              and "exactly one" in cs.locator("#cadexportdescription").inner_text())
        for sheet in cs.locator("[data-cad-export-sheet]").all():
            sheet.uncheck()
        cs.locator('[data-cad-export-sheet][value="cover"]').check()
        cs.locator('[data-cad-export-sheet][value="floor-plan"]').check()
        check("PNG wizard prevents multi-sheet raster exports",
              cs.locator("#cadexportgo").is_disabled())
        cs.locator('[data-cad-export-sheet][value="floor-plan"]').uncheck()
        cs.select_option("#cadexportpaper", "A3")
        with cs.expect_download() as png_dl:
            cs.locator("#cadexportgo").click()
        png_data = open(png_dl.value.path(), "rb").read()
        cs.wait_for_function("() => AcreCAD.core.doc.paper === 'A3'")
        png_width = int.from_bytes(png_data[16:20], "big") if len(png_data) >= 24 else 0
        png_height = int.from_bytes(png_data[20:24], "big") if len(png_data) >= 24 else 0
        check("export wizard downloads a valid selected-sheet PNG and saves paper size",
              png_dl.value.suggested_filename == "acreforge-cad-cover.png"
              and png_data.startswith(b"\x89PNG\r\n\x1a\n")
              and 0 < png_width <= 4096 and 0 < png_height <= 4096
              and cs.evaluate("AcreCAD.core.doc.paper") == "A3"
              and not cs.locator("#cadexport").is_visible())
        cs.locator("#cadexportopen").click()
        cs.select_option("#cadexportformat", "dxf")
        with cs.expect_download() as dxf_dl:
            cs.locator("#cadexportgo").click()
        dxf_data = open(dxf_dl.value.path(), encoding="utf-8").read()
        check("export wizard downloads R12 DXF without changing the saved paper size",
              dxf_dl.value.suggested_filename.endswith(".dxf") and "AC1009" in dxf_data
              and dxf_data.rstrip().endswith("EOF") and cs.evaluate("AcreCAD.core.doc.paper") == "A3")
        takeoff_context = b.new_context(service_workers="block", accept_downloads=True, reduced_motion="reduce")
        takeoff_page = takeoff_context.new_page()
        takeoff_errors = []
        takeoff_page.on("pageerror", lambda e: takeoff_errors.append(str(e)))
        takeoff_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        takeoff_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        takeoff_page.locator("#nav [data-page=cad]").click()
        takeoff_page.evaluate("""() => {
          const C = AcreCAD.core;
          C.doc.ents = [
            {id:1,t:"wall",a:[0,0],b:[216,0],th:6,layer:"0"},
            {id:2,t:"wall",a:[216,0],b:[216,288],th:6,layer:"0"},
            {id:3,t:"wall",a:[216,288],b:[0,288],th:6,layer:"0"},
            {id:4,t:"wall",a:[0,288],b:[0,0],th:6,layer:"0"},
            {id:5,t:"room",pts:[[0,0],[216,0],[216,288],[0,288]],name:"Takeoff room",layer:"0"},
            {id:6,t:"door",wall:1,pos:24,w:36,sill:0,head:80,layer:"0"},
            {id:7,t:"window",wall:2,pos:48,w:48,sill:36,head:80,layer:"0"}
          ];
          C.doc.ceil = 96;
          C.doc.takeoffRates = {floor:null, wall:null, door:null, window:null};
          C.save();
          AcreCAD.refresh();
        }""")
        takeoff = takeoff_page.evaluate("AcreCADSheets.takeoff()")
        check("CAD takeoff measures room area, wall length and gross wall area",
              takeoff["roomCount"] == 1 and takeoff["floorAreaSqFt"] == 432
              and takeoff["wallLengthFt"] == 84 and takeoff["grossWallAreaSqFt"] == 672
              and takeoff["doorCount"] == 1 and takeoff["windowCount"] == 1)
        takeoff_page.locator("#cadtakeoffopen").click()
        check("takeoff dialog shows measured quantities and warns about exclusions",
              takeoff_page.locator("#cadtakeoff").is_visible()
              and takeoff_page.locator('[data-quantity="floor"]').inner_text() == "432"
              and takeoff_page.locator('[data-quantity="wallLength"]').inner_text() == "84"
              and takeoff_page.locator('[data-quantity="wall"]').inner_text() == "672"
              and "openings are not deducted" in takeoff_page.locator("#cadtakeoff").inner_text())
        for rate_key, rate_value in (("floor", "10"), ("wall", "2"), ("door", "100"), ("window", "50")):
            rate_input = takeoff_page.locator('[data-rate="%s"]' % rate_key)
            rate_input.fill(rate_value)
            rate_input.press("Tab")
        check("user-entered rates calculate only configured categories",
              "5,814.00" in takeoff_page.locator("#cadtakeofftotal").inner_text()
              and takeoff_page.evaluate("AcreCAD.core.doc.takeoffRates.floor === 10 && AcreCAD.core.doc.takeoffRates.wall === 2 && AcreCAD.core.doc.takeoffRates.door === 100 && AcreCAD.core.doc.takeoffRates.window === 50"))
        takeoff_page.locator('[data-rate="floor"]').fill("-1")
        takeoff_page.locator('[data-rate="floor"]').press("Tab")
        check("negative takeoff rates are rejected without overwriting the saved rate",
              "Enter a rate from $0 to $1,000,000." in takeoff_page.locator("#cadtakeofftotal").inner_text()
              and takeoff_page.evaluate("AcreCAD.core.doc.takeoffRates.floor === 10"))
        with takeoff_page.expect_download() as takeoff_dl:
            takeoff_page.locator("#cadtakeoffcsv").click()
        takeoff_bytes = open(takeoff_dl.value.path(), "rb").read()
        takeoff_rows = list(csv.reader(io.StringIO(takeoff_bytes.decode("utf-8"))))
        takeoff_by_category = {row[0]: row for row in takeoff_rows[1:] if row and row[0] != "Note"}
        check("takeoff CSV is parsed with CRLF rows and matching quantities and allowances",
              takeoff_dl.value.suggested_filename == "acreforge-cad-takeoff.csv"
              and b"\r\n" in takeoff_bytes
              and takeoff_rows[0] == ["Category", "Quantity", "Unit", "Rate (USD/unit)", "Allowance (USD)"]
              and takeoff_by_category["Wall length"][1:3] == ["84", "ft"]
              and takeoff_by_category["Floor area"][3:] == ["10", "$4,320.00"]
              and takeoff_by_category["Gross wall area"][3:] == ["2", "$1,344.00"])
        takeoff_page.reload()
        takeoff_page.locator("#nav [data-page=cad]").click()
        takeoff_page.wait_for_selector("#cadcv")
        check("takeoff rates persist across page reload",
              takeoff_page.evaluate("AcreCAD.core.doc.takeoffRates.floor === 10 && AcreCAD.core.doc.takeoffRates.wall === 2 && AcreCAD.core.doc.takeoffRates.door === 100 && AcreCAD.core.doc.takeoffRates.window === 50"))
        takeoff_page.locator("#cadtakeoffopen").click()
        check("reloaded takeoff dialog restores rates and calculated subtotal",
              takeoff_page.locator('[data-rate="floor"]').input_value() == "10"
              and "5,814.00" in takeoff_page.locator("#cadtakeofftotal").inner_text())
        takeoff_page.locator("#cadtakeoffclose").click()
        takeoff_context.close()
        check("takeoff workflow produced no page errors", not takeoff_errors)
        import_context = b.new_context(service_workers="block", accept_downloads=True, reduced_motion="reduce")
        import_page = import_context.new_page()
        import_errors = []
        import_page.on("pageerror", lambda e: import_errors.append(str(e)))
        import_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        import_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        import_page.locator("#nav [data-page=cad]").click()
        import_page.evaluate("""() => {
          const C = AcreCAD.core;
          C.doc.ents = [{id:1,t:"line",a:[0,0],b:[1,1],layer:"0"}];
          C.doc.nid = 2;
          C.save();
          AcreCAD.refresh();
        }""")
        dxf_import = "\r\n".join([
            "0","SECTION","2","HEADER","9","$INSUNITS","70","4","0","ENDSEC",
            "0","SECTION","2","ENTITIES",
            "0","LINE","8","Imported Layer","10","0","20","0","11","254","21","508",
            "0","POLYLINE","8","Imported Layer","66","1","70","1",
            "0","VERTEX","8","Imported Layer","10","0","20","0",
            "0","VERTEX","8","Imported Layer","10","254","20","0",
            "0","VERTEX","8","Imported Layer","10","254","20","508",
            "0","SEQEND",
            "0","CIRCLE","8","Imported Layer","10","50.8","20","76.2","40","25.4",
            "0","ARC","8","Imported Layer","10","0","20","0","40","50.8","50","0","51","90",
            "0","TEXT","8","Imported Layer","10","76.2","20","101.6","40","25.4","1","Imported",
            "0","ELLIPSE","0","ENDSEC","0","EOF",""
        ])
        import_file = {"name":"local-import.dxf","mimeType":"application/dxf","buffer":dxf_import.encode("utf-8")}
        import_page.locator("#cadimportfile").set_input_files(import_file)
        import_page.wait_for_function("!document.querySelector('#cadimportgo').disabled")
        check("DXF import previews supported entities, skips unsupported records, and identifies units",
              "5 supported entities" in import_page.locator("#cadimportstatus").inner_text()
              and "1 unsupported records" in import_page.locator("#cadimportstatus").inner_text()
              and "millimeters" in import_page.locator("#cadimportstatus").inner_text())
        import_page.locator("#cadimportcancel").click()
        check("canceling DXF import preserves the existing drawing and layers",
              import_page.evaluate("AcreCAD.core.doc.ents.length === 1 && Object.keys(AcreCAD.core.doc.layers).length === 11"))
        import_page.locator("#cadimportfile").set_input_files(import_file)
        import_page.wait_for_function("!document.querySelector('#cadimportgo').disabled")
        import_page.locator("#cadimportgo").click()
        imported = import_page.evaluate("""() => {
          const d = AcreCAD.core.doc;
          return {
            entities:d.ents.map(e=>({t:e.t,a:e.a,b:e.b,pts:e.pts,c:e.c,r:e.r,p:e.p,h:e.h,s:e.s,closed:e.closed,layer:e.layer})),
            layers:Object.keys(d.layers)
          };
        }""")
        imported_entities = imported["entities"]
        check("DXF import appends and converts LINE, POLYLINE, CIRCLE, ARC, and TEXT to inches",
              len(imported_entities) == 6 and imported_entities[0]["t"] == "line"
              and imported_entities[1]["t"] == "line" and imported_entities[1]["b"] == [10,20]
              and imported_entities[2]["t"] == "pline" and imported_entities[2]["closed"]
              and imported_entities[2]["pts"] == [[0,0],[10,0],[10,20]]
              and imported_entities[3]["t"] == "circle"
              and all(abs(actual - expected) < 1e-9
                      for actual, expected in zip(imported_entities[3]["c"], [2,3]))
              and abs(imported_entities[3]["r"] - 1) < 1e-9
              and imported_entities[4]["t"] == "arc"
              and abs(imported_entities[4]["r"] - 2) < 1e-9
              and imported_entities[5]["t"] == "text"
              and all(abs(actual - expected) < 1e-9
                      for actual, expected in zip(imported_entities[5]["p"], [3,4]))
              and abs(imported_entities[5]["h"] - 1) < 1e-9
              and imported_entities[5]["s"] == "Imported")
        check("DXF import namespaces source layers and records the skipped entity",
              "DXF-IMPORTED_LAYER" in imported["layers"]
              and "Imported 5 DXF entities; skipped 1 unsupported records." in import_page.locator("#cadlog").inner_text())
        import_page.reload()
        import_page.locator("#nav [data-page=cad]").click()
        import_page.wait_for_selector("#cadcv")
        check("imported DXF entities persist after reload",
              import_page.evaluate("AcreCAD.core.doc.ents.length === 6 && AcreCAD.core.doc.ents.filter(e=>e.t==='pline').length === 1"))
        for invalid_name, invalid_data, expected_error in (
            ("broken.dxf", "not-a-code\r\nbad\r\n", "Invalid DXF group code"),
            ("3d.dxf", "\r\n".join(["0","SECTION","2","ENTITIES","0","LINE","10","0","20","0","30","1","11","10","21","0","31","1","0","ENDSEC","0","EOF",""]), "Only 2D DXF geometry"),
            ("extruded.dxf", "\r\n".join(["0","SECTION","2","ENTITIES","0","LINE","10","0","20","0","11","10","21","0","210","0","220","1","230","0","0","ENDSEC","0","EOF",""]), "Only 2D DXF geometry in the XY plane"),
            ("curved-polyline.dxf", "\r\n".join(["0","SECTION","2","ENTITIES","0","POLYLINE","66","1","70","0","0","VERTEX","10","0","20","0","42","0.5","0","VERTEX","10","10","20","0","0","SEQEND","0","ENDSEC","0","EOF",""]), "Curved DXF polyline segments are not supported")
        ):
            import_page.locator("#cadimportfile").set_input_files({
                "name":invalid_name,"mimeType":"application/dxf","buffer":invalid_data.encode("utf-8")
            })
            import_page.wait_for_function("document.querySelector('#cadimportstatus').textContent.includes('Import not ready:')")
            check("invalid DXF input is rejected without modifying the drawing",
                  expected_error in import_page.locator("#cadimportstatus").inner_text()
                  and import_page.locator("#cadimportgo").is_disabled()
                  and import_page.evaluate("AcreCAD.core.doc.ents.length === 6"))
        import_page.locator("#cadimportcancel").click()
        check("one undo removes the imported DXF batch and its layers",
              import_page.evaluate("AcreCAD.core.undo() && AcreCAD.core.doc.ents.length === 1 && !AcreCAD.core.doc.layers['DXF-IMPORTED_LAYER']"))
        check("DXF import workflow produced no page errors", not import_errors)
        import_context.close()
        quickbuild_context = b.new_context(service_workers="block", accept_downloads=True, reduced_motion="reduce")
        quickbuild_page = quickbuild_context.new_page()
        quickbuild_errors = []
        quickbuild_page.on("pageerror", lambda e: quickbuild_errors.append(str(e)))
        quickbuild_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        quickbuild_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        quickbuild_page.locator("#nav [data-page=cad]").click()
        command_filter = quickbuild_page.locator("#cadtoolfilter")
        initial_commands = quickbuild_page.evaluate("""() => ({
          count:[...document.querySelectorAll('#cadtools [data-cmd]')].filter(b=>!b.hidden).length,
          groups:[...document.querySelectorAll('#cadtools .cadgrp')].filter(g=>!g.hidden).length
        })""")
        check("CAD command filter starts with all commands and groups visible",
              command_filter.is_visible() and initial_commands == {"count":31,"groups":5})
        command_filter.fill("mirror")
        visible_commands = quickbuild_page.evaluate("""() => ({
          commands:[...document.querySelectorAll('#cadtools [data-cmd]')].filter(b=>!b.hidden).map(b=>b.dataset.cmd),
          groups:[...document.querySelectorAll('#cadtools .cadgrp')].filter(g=>!g.hidden).map(g=>g.querySelector('.cadgl').textContent)
        })""")
        check("CAD command filter matches case-insensitive command keywords within their group",
              visible_commands == {"commands":["MIRROR"],"groups":["Modify"]})
        command_filter.fill("room")
        check("CAD command filter also matches visible tool names",
              quickbuild_page.evaluate("[...document.querySelectorAll('#cadtools [data-cmd]')].filter(b=>!b.hidden).map(b=>b.dataset.cmd)") == ["ROOM"])
        command_filter.fill("no-such-command")
        check("CAD command filter exposes an accessible no-match status and hides all groups",
              quickbuild_page.locator("#cadtoolfilterstatus").is_visible()
              and "No CAD commands match" in quickbuild_page.locator("#cadtoolfilterstatus").inner_text()
              and quickbuild_page.evaluate("[...document.querySelectorAll('#cadtools .cadgrp')].every(g=>g.hidden)"))
        command_filter.fill("circle")
        quickbuild_page.locator("#cadfs").click()
        check("CAD command filter is preserved when remounting full viewport",
              quickbuild_page.locator("#cadtoolfilter").input_value() == "circle"
              and quickbuild_page.evaluate("[...document.querySelectorAll('#cadtools [data-cmd]')].filter(b=>!b.hidden).map(b=>b.dataset.cmd)") == ["CIRCLE"])
        quickbuild_page.locator("#cadfs").click()
        command_filter = quickbuild_page.locator("#cadtoolfilter")
        check("CAD command filter survives returning from full viewport",
              not quickbuild_page.evaluate("AcreCAD.state.full")
              and command_filter.input_value() == "circle"
              and quickbuild_page.evaluate("[...document.querySelectorAll('#cadtools [data-cmd]')].filter(b=>!b.hidden).map(b=>b.dataset.cmd)") == ["CIRCLE"])
        quickbuild_page.locator("#cadquickbuildopen").click()
        quickbuild_page.locator("#cadquickbuildcancel").click()
        check("CAD controls remain single-bound after repeated viewport remounts",
              not quickbuild_errors and not quickbuild_page.locator("#cadquickbuild").is_visible())
        command_filter.fill("")
        check("clearing CAD command filter restores all commands and groups",
              quickbuild_page.evaluate("""() => ({
                count:[...document.querySelectorAll('#cadtools [data-cmd]')].filter(b=>!b.hidden).length,
                groups:[...document.querySelectorAll('#cadtools .cadgrp')].filter(g=>!g.hidden).length
              })""") == {"count":31,"groups":5})
        quickbuild_page.evaluate("""() => {
          const C = AcreCAD.core;
          C.doc.ents = [{id:1,t:"line",a:[10,20],b:[70,20],layer:"0"}];
          C.doc.nid = 2;
          C.doc.hist = [];
          C.doc.redo = [];
          C.save();
          AcreCAD.refresh();
        }""")
        baseline_quickbuild = quickbuild_page.evaluate("JSON.stringify(AcreCAD.core.doc.ents)")
        quickbuild_page.locator("#cadquickbuildopen").click()
        check("Quick Build wizard opens with editable layout and dimension fields",
              quickbuild_page.locator("#cadquickbuild").is_visible()
              and quickbuild_page.locator("#cadquickbuildlayout").is_visible()
              and quickbuild_page.locator("#cadquickbuildwidth").input_value() == "40")
        quickbuild_page.locator("#cadquickbuildcancel").click()
        check("canceling Quick Build leaves the drawing unchanged",
              not quickbuild_page.locator("#cadquickbuild").is_visible()
              and quickbuild_page.evaluate("JSON.stringify(AcreCAD.core.doc.ents)") == baseline_quickbuild)
        quickbuild_page.locator("#cadquickbuildopen").click()
        quickbuild_page.locator("#cadquickbuildwidth").fill("17")
        quickbuild_page.locator("#cadquickbuildgo").click()
        check("Quick Build rejects out-of-range dimensions without mutating the drawing",
              "18 to 200 feet" in quickbuild_page.locator("#cadquickbuildstatus").inner_text()
              and quickbuild_page.evaluate("JSON.stringify(AcreCAD.core.doc.ents)") == baseline_quickbuild)
        quickbuild_page.locator("#cadquickbuildwidth").fill("40")
        quickbuild_page.evaluate("AcreCAD.core.doc.layers['A-WALL'].lock = true")
        quickbuild_page.locator("#cadquickbuildgo").click()
        check("Quick Build refuses locked target layers without partial geometry",
              "unlock these layers" in quickbuild_page.locator("#cadquickbuildstatus").inner_text()
              and quickbuild_page.evaluate("JSON.stringify(AcreCAD.core.doc.ents)") == baseline_quickbuild)
        quickbuild_page.evaluate("AcreCAD.core.doc.layers['A-WALL'].lock = false")
        quickbuild_page.evaluate("""() => {
          const C = AcreCAD.core;
          C.doc.ents = [{id:1,t:"line",a:[9999800,20],b:[9999990,20],layer:"0"}];
          C.doc.nid = 2;
          C.doc.hist = [];
          C.doc.redo = [];
          C.save();
        }""")
        edge_baseline = quickbuild_page.evaluate("JSON.stringify(AcreCAD.core.doc.ents)")
        quickbuild_page.locator("#cadquickbuildgo").click()
        check("Quick Build rejects drawings without coordinate room and preserves them",
              "not enough coordinate range" in quickbuild_page.locator("#cadquickbuildstatus").inner_text()
              and quickbuild_page.evaluate("JSON.stringify(AcreCAD.core.doc.ents)") == edge_baseline)
        quickbuild_page.evaluate("""() => {
          const C = AcreCAD.core;
          C.doc.ents = JSON.parse(%s);
          C.doc.nid = 2;
          C.doc.hist = [];
          C.doc.redo = [];
          C.save();
        }""" % json.dumps(baseline_quickbuild))
        for layout, expected_rooms, expected_entities in (("open", 1, 7), ("two", 2, 9), ("three", 3, 11)):
            quickbuild_page.locator("#cadquickbuildlayout").select_option(layout)
            quickbuild_page.locator("#cadquickbuildgo").click()
            built = quickbuild_page.evaluate("""() => {
              const d = AcreCAD.core.doc;
              return {
                entities:d.ents.slice(1).map(e=>({t:e.t,a:e.a,b:e.b,pts:e.pts,name:e.name,layer:e.layer,wall:e.wall,pos:e.pos,w:e.w})),
                saved:JSON.parse(localStorage.getItem(AcreCAD.core.KEY)).ents.length,
                history:d.hist.length,
                layers:Object.keys(d.layers)
              };
            }""")
            check("Quick Build %s layout appends the expected editable plan entities" % layout,
                  len(built["entities"]) == expected_entities
                  and built["saved"] == expected_entities + 1
                  and built["history"] == 1
                  and sum(e["t"] == "room" for e in built["entities"]) == expected_rooms
                  and sum(e["t"] == "wall" for e in built["entities"]) == expected_entities - expected_rooms - 2
                  and sum(e["t"] == "door" for e in built["entities"]) == 1
                  and sum(e["t"] == "window" for e in built["entities"]) == 1
                  and built["entities"][0]["a"] == [190,20]
                  and built["entities"][0]["b"] == [670,20]
                  and all(e["layer"] in built["layers"] for e in built["entities"]))
            check("Quick Build %s layout is removed by one Undo, preserving prior geometry" % layout,
                  quickbuild_page.evaluate("AcreCAD.core.undo() && JSON.stringify(AcreCAD.core.doc.ents) === %s" % json.dumps(baseline_quickbuild)))
            quickbuild_page.locator("#cadquickbuildopen").click()
        quickbuild_page.locator("#cadquickbuildcancel").click()
        check("Quick Build workflow produced no page errors", not quickbuild_errors)
        quickbuild_context.close()
        cs_cmd("PDF"); cs_cmd("Letter")
        check("PDF command honors paper choice", cs.evaluate("AcreCAD.core.doc.paper") == "Letter" and "PDF with 10 page" in cs_log())
        cs.evaluate("AcreCAD.core.doc.cur='0'")
        n0 = cs.evaluate("AcreCAD.core.doc.ents.length")
        cs_cmd("WALL"); cs_cmd("900,900"); cs_cmd("903,900"); cs_cmd("")
        check("Wall of 6 inches or less is rejected with a plain message", cs.evaluate("AcreCAD.core.doc.ents.length") == n0 and "Wall must be longer than 6 inches." in cs_log() and cs.evaluate("AcreCAD.core.health.state") == "WARNING")
        cs_cmd("ROOM"); cs_cmd("900,900"); cs_cmd("910,920")
        check("Room under 24 x 24 inches is rejected", cs.evaluate("AcreCAD.core.doc.ents.length") == n0 and "Room size below minimum dimensions" in cs_log())
        cs_cmd("DOOR"); cs_cmd("")
        check("Door not on a wall is refused with guidance", "Doors must be attached to a wall" in cs_log() and cs.evaluate("AcreCAD.core.doc.ents.length") == n0)
        cs.evaluate("AcreCAD.core.doc.hist=[];AcreCAD.core.doc.redo=[];AcreCAD.cmd.R.sel=[];AcreCAD.refresh()")
        cs_cmd("ERASE")
        check("interaction status identifies multi-object selection", cs.locator("#cadmode").get_attribute("data-state") == "SELECTION"
              and cs.locator("#cadmode").inner_text() == "Mode: Select objects")
        cs.locator("#cadcmd").press("Escape")
        cs_cmd("UNDO")
        check("Undo with nothing to undo says so and changes nothing", "No more actions to undo." in cs_log() and cs.evaluate("AcreCAD.core.doc.ents.length") == n0)
        cs.evaluate("""(()=>{const C=AcreCAD.core;C.clearHealth();window.__origSet=Storage.prototype.setItem;
          Storage.prototype.setItem=function(){const e=new Error('full');e.name='QuotaExceededError';throw e};
          C.add({t:'line',a:[0,0],b:[50,0]});})()""")
        qs = cs.evaluate("({f:AcreCAD.core.health.storageFull,s:AcreCAD.core.health.sev,m:AcreCAD.core.health.msg,own:AcreCAD.core.doc.ents.length})")
        AcreHealthText = cs.evaluate("(AcreCAD.refresh(),document.querySelector('#cadhealth').innerText)")
        check("Browser storage full pauses saving, keeps the drawing, and recommends a backup", qs["f"] and qs["s"] == "CRITICAL" and "Browser storage is full. Exporting backup recommended." in qs["m"] and qs["own"] == n0 + 1 and "Download backup" in AcreHealthText)
        cs.evaluate("(()=>{Storage.prototype.setItem=window.__origSet})()")
        with cs.expect_download() as bdl:
            cs.locator("[data-hl=backup]").click()
        bdata = open(bdl.value.path(), "rb").read()
        check("Backup download is a JSON copy of the drawing", bdl.value.suggested_filename.endswith(".json") and b'"ents"' in bdata and cs.evaluate("AcreCAD.core.health.state") == "RECOVERY")
        cs.evaluate("AcreCAD.core.save()")
        check("Saving resumes when storage is available again", cs.evaluate("AcreCAD.core.health.storageFull") is False)
        rec = cs.evaluate("""(()=>{const C=AcreCAD.core;C.backupNow();const good=JSON.stringify(C.doc.ents.length);
          localStorage.setItem(C.KEY,'{not json');C.load();
          return {n:C.doc.ents.length,good:+good,msg:C.health.msg,rec:C.health.recovered,kept:!!localStorage.getItem(C.KEY+'-corrupt'),st:C.health.state}})()""")
        check("Corrupt saved drawing is restored from the backup and the damaged copy is kept", rec["n"] == rec["good"] and "Recovered from backup created" in rec["rec"] and rec["kept"] and rec["st"] == "RECOVERY")
        cs.evaluate("AcreCAD.core.save()")
        cr = cs.evaluate("""(()=>{const C=AcreCAD.core;C.clearHealth();localStorage.setItem(C.SKEY,JSON.stringify({open:true}));C.load();AcreCAD.refresh();
          return {c:C.health.crashed,t:document.querySelector('#cadhealth').innerText}})()""")
        check("Crash flag shows the Restore / Discard prompt", cr["c"] and "AcreForge closed unexpectedly." in cr["t"] and "Restore previous session?" in cr["t"])
        before = cs.evaluate("AcreCAD.core.doc.ents.length")
        cs.locator("[data-hl=restore]").click()
        check("Restore keeps the drawing and dismisses the prompt", cs.evaluate("AcreCAD.core.health.crashed") is False and cs.evaluate("AcreCAD.core.doc.ents.length") == before)
        cs.evaluate("(()=>{const C=AcreCAD.core;localStorage.setItem(C.SKEY,JSON.stringify({open:true}));C.load();AcreCAD.refresh()})()")
        cs.locator("[data-hl=discard]").click()
        bk = cs.evaluate("JSON.parse(localStorage.getItem(AcreCAD.core.BKEY)).doc.ents.length")
        check("Discard starts fresh, clears takeoff rates, and keeps a backup of the prior drawing",
              cs.evaluate("AcreCAD.core.doc.ents.length") == 0 and bk == before
              and cs.evaluate("Object.values(AcreCAD.core.doc.takeoffRates).every(rate => rate === null)"))
        cs_cmd("ROOM"); cs_cmd("0,0"); cs_cmd("216,288"); cs_cmd("Living Room")
        pf = cs.evaluate("AcreCADSheets.build({paper:'Letter',failSheet:'Plumbing'})")
        check("PDF export skips a failed sheet and reports a partial set", pf["pages"] == 9 and len(pf["failed"]) == 1 and "9 of 10 sheets generated" in pf["message"] and pf["pdf"].startswith("%PDF-"))
        check("Autosave runs after drawing (saved copy matches the drawing)", len(cs_doc()["ents"]) == cs.evaluate("AcreCAD.core.doc.ents.length"))
        cs_cmd("NEW")
        cs.evaluate("()=>{const c=AcreCAD.core;c.doc.cur='0';c.doc.ents.length=0;c.doc.ents.push({t:'wall',a:[0,0],b:[240,0],th:6,layer:'0'},{t:'wall',a:[240,0],b:[240,120],th:6,layer:'0'},{t:'wall',a:[240,120],b:[0,120],th:6,layer:'0'},{t:'wall',a:[0,120],b:[0,0],th:6,layer:'0'});AcreCAD.refresh()}")
        v3m = cs.evaluate("()=>{const m=AcreCAD3D.model();const f=AcreCAD3D.view(m,0,0);const t=AcreCAD3D.view(m,0,90);return {n:m.faces.length,w:Math.round(f.w),h:Math.round(t.h)}}")
        check("3D model builds faces for 4 walls", v3m["n"] >= 20)
        check("3D front view width spans walls", v3m["w"] >= 240 and v3m["w"] <= 340)
        check("3D top view depth spans walls", v3m["h"] >= 120 and v3m["h"] <= 220)
        cs.click("#cad3d")
        check("Split 3D shows linked canvas", cs.evaluate("()=>!document.querySelector('#cad3dwrap').hidden"))
        cs.click("[data-v3=front]")
        check("ViewCube front sets yaw/pitch 0", cs.evaluate("()=>AcreCAD.state.v3.yaw===0&&AcreCAD.state.v3.pitch===0"))
        cs.evaluate("()=>{AcreCAD.core.doc.ents.push({t:'wall',a:[0,0],b:[0,-100],th:6,layer:'0'});AcreCAD.refresh()}")
        check("3D stays linked after plan edit", cs.evaluate("()=>AcreCAD.state.v3.last!==undefined&&!AcreCAD.state.v3.err"))
        cs.click("#cad3d")
        check("Split 3D toggles off", cs.evaluate("()=>document.querySelector('#cad3dwrap').hidden"))
        cs_cmd("VIEW3D")
        check("interaction status identifies option selection", cs.locator("#cadmode").get_attribute("data-state") == "OPTION"
              and cs.locator("#cadmode").inner_text() == "Mode: Choose option")
        cs_cmd("top")
        check("VIEW3D command sets top view and opens split", cs.evaluate("()=>AcreCAD.state.v3.on&&AcreCAD.state.v3.pitch===90"))
        canvas_box = cs.locator("#cadcv").bounding_box()
        cs.mouse.move(canvas_box["x"] + 100, canvas_box["y"] + 100)
        cs.mouse.down(button="middle")
        cs.mouse.move(canvas_box["x"] + 120, canvas_box["y"] + 110)
        check("interaction status reports middle-button panning", cs.locator("#cadmode").get_attribute("data-state") == "PAN"
              and cs.locator("#cadmode").inner_text() == "Mode: Panning")
        cs.mouse.up(button="middle")
        check("finishing a pan returns the mode to Ready", cs.locator("#cadmode").get_attribute("data-state") == "READY")
        check("CAD Studio produced no page errors", not cs_errors)
        cs_context.close()
        rotation_context = b.new_context(service_workers="block", reduced_motion="no-preference")
        rotation = rotation_context.new_page()
        rotation.add_init_script("""(() => {
          localStorage.setItem('acreforge-guide-seen', '1');
          window.__testHidden = false;
          Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.__testHidden});
          window.__sceneDraws = 0;
          const clear = CanvasRenderingContext2D.prototype.clearRect;
          CanvasRenderingContext2D.prototype.clearRect = function(...args) {
            if (this.canvas.id === 'scene3d') window.__sceneDraws++;
            return clear.apply(this, args);
          };
        })();""")
        rotation.goto("http://127.0.0.1:8766/?spatial-test=1")
        rotation.locator('#nav [data-page="designer"]').click()
        rotation.wait_for_timeout(350)
        visible_draws = rotation.evaluate("""() => {
          window.__testHidden = true;
          document.dispatchEvent(new Event('visibilitychange'));
          return window.__sceneDraws;
        }""")
        rotation.wait_for_timeout(350)
        hidden_draws = rotation.evaluate("window.__sceneDraws")
        check("site preview auto-rotation draws while visible and stops while hidden",
              visible_draws >= 2 and hidden_draws == visible_draws)
        rotation.evaluate("document.querySelector('[data-scene-reset]').click()")
        manual_draws = rotation.evaluate("window.__sceneDraws")
        check("hidden site preview still supports explicit redraws", manual_draws > hidden_draws)
        rotation.evaluate("""() => {
          window.__testHidden = false;
          document.dispatchEvent(new Event('visibilitychange'));
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        rotation.wait_for_timeout(350)
        resumed_draws = rotation.evaluate("window.__sceneDraws")
        check("site preview auto-rotation resumes without duplicate timers",
              2 <= resumed_draws - manual_draws <= 4)
        rotation.locator("#nav [data-page=dashboard]").click()
        departed_draws = rotation.evaluate("window.__sceneDraws")
        rotation.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        rotation.wait_for_timeout(250)
        check("site preview does not restart after leaving the designer",
              rotation.evaluate("window.__sceneDraws") == departed_draws)
        rotation_context.close()

        home_context = b.new_context(service_workers="block")
        home = home_context.new_page()
        home_errors = []
        home.on("pageerror", lambda e: home_errors.append(str(e)))
        home.add_init_script("""(() => {
          localStorage.setItem('acreforge-guide-seen', '1');
          window.__testHidden = false;
          Object.defineProperty(document, 'hidden', {configurable: true, get: () => window.__testHidden});
          window.__homeTimers = new Set();
          window.__homeTicks = 0;
          const start = window.setInterval, stop = window.clearInterval;
          window.setInterval = (fn, delay, ...args) => {
            if (delay !== 60) return start(fn, delay, ...args);
            const id = start(() => { window.__homeTicks++; fn(...args); }, delay);
            window.__homeTimers.add(id);
            return id;
          };
          window.clearInterval = id => { window.__homeTimers.delete(id); stop(id); };
        })();""")
        home.goto("http://127.0.0.1:8766/?spatial-test=1")
        home.locator('#nav [data-page="designer"]').click()
        home.locator('#content .tabbar [data-page="homes"]').click()
        home.wait_for_timeout(200)
        check("Home Builder 2D runs no idle rotation timer",
              home.evaluate("window.__homeTimers.size === 0 && window.__homeTicks === 0"))
        home.locator("#hbview").click()
        home.evaluate("""() => {
          window.__homeDraws = 0;
          new MutationObserver(() => window.__homeDraws++)
            .observe(document.getElementById('hbsvg'), {childList: true});
        }""")
        home.wait_for_timeout(250)
        check("Home Builder 3D starts one rotation timer",
              home.evaluate("window.__homeTimers.size === 1 && window.__homeTicks >= 2 && window.__homeDraws >= 2"))
        stopped = home.evaluate("""() => {
          window.__testHidden = true;
          document.dispatchEvent(new Event('visibilitychange'));
          return [window.__homeTicks, window.__homeDraws];
        }""")
        home.wait_for_timeout(200)
        check("hidden Home Builder stops its timer and periodic redraws",
              home.evaluate("window.__homeTimers.size === 0 && [window.__homeTicks, window.__homeDraws]") == stopped)
        home.evaluate("document.getElementById('hbroof').click()")
        check("Home Builder manual preview controls still work while hidden",
              "on" in home.locator("#hbroof").inner_text()
              and home.evaluate("window.__homeTimers.size === 0 && window.__homeDraws") > stopped[1])
        home.evaluate("""() => {
          window.__testHidden = false;
          document.dispatchEvent(new Event('visibilitychange'));
          document.dispatchEvent(new Event('visibilitychange'));
        }""")
        home.wait_for_timeout(200)
        check("visible Home Builder resumes once without duplicate timers",
              home.evaluate("window.__homeTimers.size === 1 && window.__homeTicks") > stopped[0])
        home.locator("#hbview").click()
        check("returning to 2D stops the Home Builder timer",
              home.evaluate("window.__homeTimers.size") == 0)
        home.locator("#hbroof").click()
        check("roof control starts rotation when it switches to 3D",
              home.evaluate("window.__homeTimers.size") == 1)
        home.locator("#nav [data-page=dashboard]").click()
        home.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        check("leaving Home Builder stops its timer without JavaScript errors",
              home.evaluate("window.__homeTimers.size") == 0 and not home_errors)
        home.locator('#nav [data-page="designer"]').click()
        home.locator('#content .tabbar [data-page="homes"]').click()
        check("returning to Home Builder restores its visible 3D rotation",
              home.evaluate("window.__homeTimers.size") == 1)
        home_context.close()

        reduced_context = b.new_context(service_workers="block", reduced_motion="reduce")
        reduced = reduced_context.new_page()
        reduced_errors = []
        reduced.on("pageerror", lambda e: reduced_errors.append(str(e)))
        reduced.add_init_script("""(() => {
          localStorage.setItem('acreforge-guide-seen', '1');
          window.__homeTimers = new Set();
          const start = window.setInterval, stop = window.clearInterval;
          window.setInterval = (fn, delay, ...args) => {
            if (delay !== 60) return start(fn, delay, ...args);
            const id = start(fn, delay, ...args);
            window.__homeTimers.add(id);
            return id;
          };
          window.clearInterval = id => { window.__homeTimers.delete(id); stop(id); };
        })();""")
        reduced.goto("http://127.0.0.1:8766/?spatial-test=1")
        reduced.locator('#nav [data-page="designer"]').click()
        reduced.locator('#content .tabbar [data-page="homes"]').click()
        reduced.locator("#hbview").click()
        reduced.evaluate("""() => {
          window.__homeDraws = 0;
          new MutationObserver(() => window.__homeDraws++)
            .observe(document.getElementById('hbsvg'), {childList: true});
        }""")
        reduced.wait_for_timeout(250)
        check("Home Builder reduced motion prevents automatic rotation and timer",
              reduced.evaluate("window.__homeTimers.size === 0 && window.__homeDraws === 0"))
        reduced.locator("#content").focus()
        reduced.keyboard.press("e")
        reduced.wait_for_function("() => window.__homeDraws > 0")
        check("Home Builder reduced motion preserves manual 3D rotation",
              reduced.evaluate("window.__homeTimers.size === 0 && window.__homeDraws > 0"))
        reduced.emulate_media(reduced_motion="no-preference")
        reduced.wait_for_function("() => window.__homeTimers.size === 1")
        before_resume = reduced.evaluate("window.__homeDraws")
        reduced.wait_for_timeout(200)
        check("Home Builder responds when reduced motion is turned off",
              reduced.evaluate("window.__homeTimers.size === 1 && window.__homeDraws") > before_resume)
        reduced.emulate_media(reduced_motion="reduce")
        reduced.wait_for_function("() => window.__homeTimers.size === 0")
        after_stop = reduced.evaluate("window.__homeDraws")
        reduced.wait_for_timeout(200)
        check("Home Builder stops again when reduced motion is enabled",
              reduced.evaluate("window.__homeTimers.size === 0 && window.__homeDraws") == after_stop
              and not reduced_errors)
        reduced_context.close()

        welcome_context = b.new_context(service_workers="block")
        welcome = welcome_context.new_page()
        welcome_errors, welcome_requests = [], []
        welcome.on("pageerror", lambda e: welcome_errors.append(str(e)))
        welcome.on("request", lambda r: welcome_requests.append(r.url)
                   if not r.url.startswith(("http://127.0.0.1", "http://localhost", "data:", "blob:")) else None)
        welcome.goto("http://127.0.0.1:8766/?spatial-test=1")
        welcome.locator("#afGuide[open]").wait_for()
        check("first launch offers an explicitly named new property and sample project",
              welcome.locator("#afGuide").get_attribute("aria-labelledby") == "afStartTitle"
              and welcome.evaluate("document.activeElement?.matches('[data-start-build]')")
              and "Start a new property" in welcome.locator("[data-start-build]").inner_text()
              and "Explore sample project" in welcome.locator("[data-start-explore]").inner_text()
              and welcome.locator("#afGuide svg[role=img]").count() == 1
              and "not your property" in welcome.locator("#afGuide").inner_text().lower()
              and welcome.evaluate("window.__acreforgeUpgradeTest.items()") == []
              and welcome.evaluate("window.__acreforgeUpgradeTest.scenario().fields") == [])
        welcome.locator("[data-start-build]").click()
        check("new-property path asks for a name and makes the planning idea optional",
              welcome.evaluate("document.activeElement?.id === 'afStartName'")
              and welcome.locator("#afStartName").is_visible()
              and not welcome.locator("#afStartIntent").evaluate("el => el.required")
              and "local, rule-based planner" in welcome.locator("[data-start-form]").inner_text())
        welcome.locator("#afStartName").fill("   ")
        welcome.locator("[data-start-form] button").click()
        check("blank property names are rejected without leaving the welcome dialog",
              welcome.locator("#afGuide[open]").count() == 1
              and not welcome.locator("#afStartName").evaluate("el => el.validity.valid"))
        welcome.locator("#afStartName").fill("Family homestead")
        welcome.locator("#afStartIntent").fill("Family homestead with a garden and barn")
        welcome.locator("[data-start-form] button").click()
        check("new property saves its name and transfers intent without placing a layout",
              welcome.locator("#plPrompt").input_value() == "Family homestead with a garden and barn"
              and welcome.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Family homestead"
              and welcome.evaluate("window.__acreforgeUpgradeTest.items()") == []
              and welcome.evaluate("!window.__acreforgeUpgradeTest.state().plan?.prompt"))
        welcome.locator('[data-pl="gen"]').click()
        check("existing rule-based planner accepts the startup intent",
              welcome.evaluate("window.__acreforgeUpgradeTest.state().plan.prompt")
              == "Family homestead with a garden and barn"
              and welcome.evaluate("window.__acreforgeUpgradeTest.items()") == [])
        welcome.wait_for_timeout(500)
        welcome.reload()
        check("returning project skips welcome and keeps its plan",
              welcome.locator("#afGuide[open]").count() == 0
              and welcome.evaluate("window.__acreforgeUpgradeTest.state().plan.prompt")
              == "Family homestead with a garden and barn")
        welcome.locator("#nav [data-page=dashboard]").click()
        check("Projects dashboard offers the next planning action after returning",
              welcome.locator(".command-map-preview #siteMap").count() == 1
              and welcome.get_by_role("button", name="Open site designer").is_visible()
              and welcome.get_by_role("button", name="Analyze property").is_visible())
        welcome.locator("#afGuideBtn").click()
        check("existing project offers continuation instead of a destructive new-project action",
              "Continue my property" in welcome.locator("[data-start-build]").inner_text())
        welcome.keyboard.press("Escape")
        check("start options can be reopened and dismissed with Escape",
              welcome.locator("#afGuide[open]").count() == 0)
        check("build welcome stays local and produces no JavaScript errors",
              not welcome_errors and not welcome_requests)
        welcome_context.close()

        optional_context = b.new_context(service_workers="block")
        optional = optional_context.new_page()
        optional.goto("http://127.0.0.1:8766/?spatial-test=1")
        optional.locator("#afGuide[open]").wait_for()
        optional.locator("[data-start-build]").click()
        optional.locator("#afStartName").fill("Quiet Acres")
        optional.locator("[data-start-form] button").click()
        check("new property without a planning idea opens the editable designer",
              optional.locator("#afGuide[open]").count() == 0
              and optional.locator("#nav [data-page=designer].active").count() == 1
              and optional.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Quiet Acres"
              and optional.evaluate("window.__acreforgeUpgradeTest.items()") == []
              and optional.evaluate("!window.__acreforgeUpgradeTest.state().plan?.prompt"))
        optional.locator("#nav [data-page=dashboard]").click()
        check("new property can return to its Projects dashboard",
              optional.locator("#nav [data-page=dashboard].active").count() == 1
              and optional.locator(".command-map-preview #siteMap").count() == 1)
        optional_context.close()

        explore_context = b.new_context(service_workers="block", viewport={"width": 390, "height": 844})
        explore = explore_context.new_page()
        explore_errors = []
        explore.on("pageerror", lambda e: explore_errors.append(str(e)))
        explore.goto("http://127.0.0.1:8766/?spatial-test=1")
        explore.locator("#afGuide[open]").wait_for()
        check("mobile start choices fit the viewport and distinguish project from sample",
              explore.evaluate("""() => {
                const d=document.querySelector('#afGuide').getBoundingClientRect();
                return d.left>=0 && d.right<=innerWidth && d.width<=innerWidth;
              }""") and explore.locator("[data-start-build]").is_visible()
              and explore.locator("[data-start-explore]").is_visible()
              and "Start a new property" in explore.locator("[data-start-build]").inner_text()
              and "Explore sample project" in explore.locator("[data-start-explore]").inner_text())
        explore.locator("[data-start-explore]").click()
        explore.wait_for_function("new URL(location.href).searchParams.get('sample') === '1'")
        check("first-time sample opens with its own illustrative data and return actions",
              explore.locator("[data-sample-banner]").is_visible()
              and "Illustrative sample project" in explore.locator("[data-sample-banner]").inner_text()
              and explore.evaluate("JSON.parse(localStorage['oregon-estate-planner-sample-v1']).project.name")
              == "Illustrative Sample Property"
              and explore.evaluate("window.__acreforgeUpgradeTest.items().length") > 0
              and explore.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios[0].items.length") == 0
              and explore.locator("[data-sample-return]").is_visible()
              and explore.locator("[data-sample-reset]").is_visible())
        explore.locator("[data-sample-return]").click()
        explore.wait_for_function("new URL(location.href).searchParams.get('sample') !== '1'")
        check("mobile sample return preserves the separate blank user project",
              explore.evaluate("window.__acreforgeUpgradeTest.items()") == []
              and explore.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).project.name") == "AcreForge"
              and not explore_errors)
        explore_context.close()

        existing_context = b.new_context(service_workers="block")
        existing = existing_context.new_page()
        existing.add_init_script(
            "localStorage.setItem('oregon-estate-planner-v1'," + json.dumps(json.dumps(asset_data)) + ");")
        existing.goto("http://127.0.0.1:8766/?spatial-test=1")
        existing_before = asset_data
        check("existing project without a welcome preference is never treated as a fresh project",
              existing.locator("#afGuide[open]").count() == 0
              and existing.evaluate("window.__acreforgeUpgradeTest.state().project.name") == existing_before["project"]["name"]
              and existing.evaluate("window.__acreforgeUpgradeTest.items()") == existing_before["scenarios"][0]["items"])
        existing.locator("#afGuideBtn").click()
        existing.locator("[data-start-build]").click()
        check("continuing an existing project does not replace its saved objects",
              existing.evaluate("window.__acreforgeUpgradeTest.items()") == existing_before["scenarios"][0]["items"])
        user_before_sample = existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1'])")
        existing.locator("#afGuideBtn").click()
        existing.locator("[data-start-explore]").click()
        existing.wait_for_function("new URL(location.href).searchParams.get('sample') === '1'")
        check("opening sample never overwrites the existing user project",
              existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).project.name")
              == user_before_sample["project"]["name"]
              and existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios[0].items")
              == user_before_sample["scenarios"][0]["items"]
              and existing.evaluate("window.__acreforgeUpgradeTest.items().length") > 0)
        existing.evaluate("() => { window.__acreforgeUpgradeTest.state().project.name='Edited sample'; window.__acreforgeUpgradeTest.save(); }")
        existing.wait_for_timeout(500)
        check("sample edits persist only in the sample storage key",
              existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-sample-v1']).project.name") == "Edited sample"
              and existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).project.name")
              == user_before_sample["project"]["name"])
        existing.locator("[data-sample-return]").click()
        existing.wait_for_function("new URL(location.href).searchParams.get('sample') !== '1'")
        check("returning from sample restores the original user project and dashboard",
              existing.evaluate("window.__acreforgeUpgradeTest.state().project.name")
              == user_before_sample["project"]["name"]
              and existing.evaluate("window.__acreforgeUpgradeTest.items()") == user_before_sample["scenarios"][0]["items"]
              and existing.locator(".command-map-preview #siteMap").count() == 1)
        existing.locator("#afGuideBtn").click()
        existing.locator("[data-start-explore]").click()
        existing.wait_for_function("new URL(location.href).searchParams.get('sample') === '1'")
        check("reopening sample resumes its independent saved state",
              existing.evaluate("window.__acreforgeUpgradeTest.state().project.name") == "Edited sample"
              and existing.evaluate("window.__acreforgeUpgradeTest.items().length") > 0)
        existing.once("dialog", lambda dialog: dialog.accept())
        existing.locator("[data-sample-reset]").click()
        existing.wait_for_function("""() => {
          const sample=JSON.parse(localStorage['oregon-estate-planner-sample-v1'] || 'null');
          return sample?.project?.name === 'Illustrative Sample Property'
            && sample.scenarios[0].items.length > 0;
        }""", timeout=10000)
        check("resetting the sample restores its starter state without changing the user project",
              existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).project.name")
              == user_before_sample["project"]["name"]
              and existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-v1']).scenarios[0].items")
              == user_before_sample["scenarios"][0]["items"]
              and existing.evaluate("JSON.parse(localStorage['oregon-estate-planner-sample-v1']).project.name")
              == "Illustrative Sample Property")
        existing_context.close()
        recovery_context = b.new_context(service_workers="block")
        recovery_page = recovery_context.new_page()
        recovery_page.add_init_script(
            "localStorage.setItem('oregon-estate-planner-recovery-v1',"
            + json.dumps(json.dumps(asset_data)) + ");")
        recovery_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        check("a recovery-only browser is not treated as a fresh launch",
              recovery_page.locator("#afGuide[open]").count() == 0
              and recovery_page.evaluate("!!localStorage.getItem('oregon-estate-planner-recovery-v1')")
              and recovery_page.evaluate("localStorage.getItem('oregon-estate-planner-v1') === null")
              and recovery_page.locator("#saveState").get_attribute("data-status") == "recovery"
              and "restore in Settings" in recovery_page.locator("#saveState").inner_text())
        recovery_context.close()

        status_context = b.new_context(service_workers="block", viewport={"width": 390, "height": 844})
        status_page = status_context.new_page()
        status_page.on("dialog", lambda d: d.dismiss())
        status_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        status_page.locator("#saveState").wait_for(state="attached")
        check("mobile save status remains visible and distinguishes saved state",
              status_page.locator("#saveState").is_visible()
              and status_page.locator("#saveState").get_attribute("data-status") == "saved"
              and "Saved locally" in status_page.locator("#saveState").inner_text())
        status_page.evaluate("""() => {
          window.__acreforgeUpgradeTest.state().project.name='Mobile status property';
          window.__acreforgeUpgradeTest.save();
        }""")
        check("mobile save status visibly reports saving",
              status_page.locator("#saveState").get_attribute("data-status") == "saving"
              and "Saving" in status_page.locator("#saveState").inner_text())
        status_page.wait_for_function("document.querySelector('#saveState').dataset.status === 'saved'", timeout=5000)
        status_page.evaluate("""() => {
          window.originalStorageSet = Storage.prototype.setItem;
          Storage.prototype.setItem = function() { throw new DOMException('Full', 'QuotaExceededError'); };
          window.__acreforgeUpgradeTest.state().project.name='Mobile unsaved property';
          window.__acreforgeUpgradeTest.save();
        }""")
        status_page.wait_for_function("document.querySelector('#saveState').dataset.status === 'problem'", timeout=5000)
        check("mobile save status visibly reports storage failure",
              status_page.locator("#saveState").is_visible()
              and "export a backup" in status_page.locator("#saveState").inner_text())
        status_context.close()

        startup_failure_context = b.new_context(service_workers="block")
        startup_failure = startup_failure_context.new_page()
        startup_failure.on("dialog", lambda d: d.dismiss())
        startup_failure.add_init_script(
            "Storage.prototype.setItem = function() { throw new DOMException('Full', 'QuotaExceededError'); };")
        startup_failure.goto("http://127.0.0.1:8766/?spatial-test=1")
        startup_failure.locator("#saveState").wait_for(state="attached")
        check("initial storage failure is not falsely reported as saved",
              startup_failure.locator("#saveState").get_attribute("data-status") == "problem"
              and "Save problem" in startup_failure.locator("#saveState").inner_text())
        startup_failure_context.close()

        reopen_context = b.new_context(service_workers="block")
        reopen_page = reopen_context.new_page()
        reopen_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        reopen_page.locator("#afGuide[open]").wait_for()
        reopen_page.evaluate("""() => {
          window.__acreforgeUpgradeTest.state().project.name='Close and reopen property';
          window.__acreforgeUpgradeTest.save();
        }""")
        reopen_page.wait_for_function("document.querySelector('#saveState').dataset.status === 'saved'", timeout=5000)
        reopen_page.close()
        reopened_page = reopen_context.new_page()
        reopened_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        check("saved project survives closing and reopening the app in the same browser profile",
              reopened_page.locator("#afGuide[open]").count() == 0
              and reopened_page.evaluate("window.__acreforgeUpgradeTest.state().project.name")
              == "Close and reopen property"
              and "Saved locally" in reopened_page.locator("#saveState").inner_text())
        reopened_page.locator("#nav [data-page=settings]").click()
        check("backup, import and recovery actions are easy to find in Project Settings",
              reopened_page.get_by_role("button", name="Export backup").is_visible()
              and reopened_page.get_by_role("button", name="Download project JSON").is_visible()
              and reopened_page.get_by_role("button", name="Import project JSON").is_visible()
              and reopened_page.get_by_role("button", name="Restore recovery snapshot").is_visible())
        solar_state = reopened_page.evaluate(
            "() => JSON.parse(JSON.stringify(window.__acreforgeUpgradeTest.state()))")
        solar_state["project"]["locationCoordinates"] = None
        solar_state["project"].pop("locationLabel", None)
        reopen_context.close()

        solar_context = b.new_context(timezone_id="America/Denver", service_workers="block")
        solar_page = solar_context.new_page()
        solar_errors = []
        solar_page.on("pageerror", lambda e: solar_errors.append(str(e)))
        solar_page.add_init_script(
            "localStorage.setItem('oregon-estate-planner-v1', "
            + json.dumps(json.dumps(solar_state))
            + "); localStorage.setItem('acreforge-guide-seen','1');")
        solar_page.goto("http://127.0.0.1:8766/?spatial-test=1&sun-test=1")
        solar_page.locator("#nav [data-page=planner]").first.click()
        check("sun preview requires explicit coordinates when the project has no location",
              solar_page.locator("[data-sun-latitude]").input_value() == ""
              and solar_page.locator("[data-sun-longitude]").input_value() == ""
              and "no location is assumed" in solar_page.locator("[data-sun-path]").inner_text().lower())
        solar_page.locator("[data-sun-calculate]").click()
        check("sun preview rejects missing coordinates without producing an estimate",
              "Enter the property's latitude and longitude" in solar_page.locator("[data-sun-error]").inner_text()
              and solar_page.locator("[data-sun-values]").count() == 0)
        solar_page.locator("[data-sun-latitude]").fill("90.01")
        solar_page.locator("[data-sun-longitude]").fill("-105")
        solar_page.locator("[data-sun-datetime]").fill("2024-06-21T13:02")
        solar_page.locator("[data-sun-calculate]").click()
        check("sun preview rejects out-of-range latitude",
              "Latitude must be a number from" in solar_page.locator("[data-sun-error]").inner_text()
              and solar_page.locator("[data-sun-values]").count() == 0)
        solar_page.locator("[data-sun-latitude]").fill("40")
        solar_page.locator("[data-sun-longitude]").fill("180.01")
        solar_page.locator("[data-sun-calculate]").click()
        check("sun preview rejects out-of-range longitude",
              "Longitude must be a number from" in solar_page.locator("[data-sun-error]").inner_text()
              and solar_page.locator("[data-sun-values]").count() == 0)
        solar_page.locator("[data-sun-latitude]").fill("40")
        solar_page.locator("[data-sun-longitude]").fill("-105")
        solar_page.locator("[data-sun-datetime]").fill("2024-06-21T13:02")
        solar_page.locator("[data-sun-calculate]").click()
        solar_values = solar_page.locator("[data-sun-values]")
        solar_azimuth = float(solar_values.get_attribute("data-sun-azimuth"))
        solar_elevation = float(solar_values.get_attribute("data-sun-elevation"))
        sunrise_minute = float(solar_values.get_attribute("data-sunrise"))
        sunset_minute = float(solar_values.get_attribute("data-sunset"))
        check("known June-solstice sun position is plausible in browser-local Mountain time",
              170 <= solar_azimuth <= 190
              and 72 <= solar_elevation <= 75
              and 300 <= sunrise_minute <= 420
              and 1170 <= sunset_minute <= 1320
              and solar_page.locator("[data-sun-path-chart] path[data-solar-path]").count() == 3
              and solar_page.locator("[data-sun-current-marker]").count() == 1
              and "America/Denver" in solar_page.locator("[data-sun-path]").inner_text())
        check("sun preview stays local and does not change saved property coordinates",
              solar_page.evaluate(
                  "JSON.parse(localStorage['oregon-estate-planner-v1']).project.locationCoordinates") is None
              and not solar_errors)
        solar_context.close()
        pqb_context = b.new_context(service_workers="block")
        pqb_page = pqb_context.new_page()
        pqb_errors = []
        pqb_page.on("pageerror", lambda e: pqb_errors.append(str(e)))
        pqb_page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        pqb_page.goto("http://127.0.0.1:8766/?spatial-test=1")
        pqb_page.locator("#nav [data-page=planner]").click()
        pqb_page.locator("[data-pqb=open]").click()
        check("property Quick Build starts with an explicit purpose and five-step progress",
              pqb_page.locator("#propertyquickbuild").is_visible()
              and pqb_page.locator("#pqbtitle").inner_text().strip().lower() == "step 1 of 5"
              and pqb_page.locator('[data-pqb-field="purpose"]').is_visible())
        pqb_page.locator('[data-pqb-field="purpose"]').select_option("homestead")
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="acres"]').fill("20")
        pqb_page.locator('[data-pqb-field="aspect"]').fill("1.5")
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="homeSqft"]').fill("2500")
        pqb_page.locator('[data-pqb-field="bedrooms"]').fill("3")
        pqb_page.locator('[data-pqb-goal="workshop"]').check()
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="spacing"][value="spread"]').check()
        pqb_page.locator('[data-pqb="preview"]').click()
        check("property Quick Build previews cost ranges, site program, and the requested floor plan",
              pqb_page.locator("[data-pqb-results]").is_visible()
              and pqb_page.locator("[data-pqb-cost] article").count() == 3
              and "2,500 sqft house with 3 bedrooms" in pqb_page.locator("[data-pqb-prompt]").inner_text()
              and pqb_page.locator("[data-pqb-floor-plan] svg").get_attribute("aria-label")
              == "Conceptual floor plan for a 2,500 square foot house with 3 bedrooms")
        pqb_page.locator('[data-pqb="apply"]').click()
        pqb_page.locator("[data-pqb-applied]").wait_for()
        pqb_page.wait_for_function("""() => {
          const raw=localStorage.getItem('oregon-estate-planner-v1');
          if(!raw)return false;
          const s=JSON.parse(raw);
          return s.plan?.quickBuild?.purpose === 'homestead'
            && s.plan.layoutSummary?.spacing === 'spread';
        }""", timeout=10000)
        pqb_saved = pqb_page.evaluate("""() => {
          const s=JSON.parse(localStorage['oregon-estate-planner-v1']);
          const items=s.scenarios.find(c=>c.id===s.activeScenario).items.filter(item=>item.fromPlan);
          return {project:s.project,plan:s.plan,types:items.map(item=>item.type),
            count:items.length,bedrooms:document.querySelectorAll('[data-pqb-floor-plan] text').length};
        }""")
        check("applying property Quick Build saves parcel assumptions, spacing, program, and editable layout",
              pqb_saved["project"]["acres"] == 20
              and pqb_saved["plan"]["quickBuild"]["homeSqft"] == 2500
              and pqb_saved["plan"]["quickBuild"]["bedrooms"] == 3
              and pqb_saved["plan"]["quickBuild"]["spacing"] == "spread"
              and pqb_saved["plan"]["layoutSummary"]["home"]["area"] == 2500
              and all(any(re.search(pattern, item_type, re.I) for item_type in pqb_saved["types"])
                      for pattern in ("home", "garden", "shop"))
              and pqb_saved["bedrooms"] >= 3)
        pqb_page.reload()
        pqb_page.locator("#nav [data-page=planner]").click()
        pqb_page.locator("[data-pqb-applied]").wait_for()
        check("property Quick Build floor plan and settings survive reload",
              pqb_page.locator("[data-pqb-applied] [data-pqb-floor-plan] svg").is_visible()
              and pqb_page.evaluate(
                  "JSON.parse(localStorage['oregon-estate-planner-v1']).plan.quickBuild.spacing") == "spread")
        saved_before_cancel = pqb_page.evaluate("localStorage.getItem('oregon-estate-planner-v1')")
        pqb_page.locator("[data-pqb=open]").click()
        pqb_page.locator('[data-pqb="cancel"]').click()
        check("canceling property Quick Build does not change the saved project",
              not pqb_page.locator("#propertyquickbuild").is_visible()
              and pqb_page.evaluate("localStorage.getItem('oregon-estate-planner-v1')") == saved_before_cancel)
        pqb_page.locator("[data-pqb=open]").click()
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="acres"]').fill("0")
        pqb_page.locator('[data-pqb="next"]').click()
        check("invalid acreage is rejected without changing project state",
              "Enter planning acreage from 1 to 1,000" in pqb_page.locator("[data-pqb-error]").inner_text()
              and pqb_page.evaluate("localStorage.getItem('oregon-estate-planner-v1')") == saved_before_cancel)
        pqb_page.locator('[data-pqb="cancel"]').click()
        pqb_page.locator("[data-pqb=open]").click()
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="acres"]').fill("1")
        pqb_page.locator('[data-pqb-field="aspect"]').fill("0.25")
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="homeSqft"]').fill("10000")
        pqb_page.locator('[data-pqb-field="bedrooms"]').fill("3")
        pqb_page.locator('[data-pqb="next"]').click()
        pqb_page.locator('[data-pqb-field="spacing"][value="balanced"]').check()
        pqb_page.locator('[data-pqb="preview"]').click()
        pqb_page.locator('[data-pqb="apply"]').click()
        check("a layout that cannot fit is rejected and leaves the saved project unchanged",
              "does not fit" in pqb_page.locator("[data-pqb-error]").inner_text()
              and pqb_page.evaluate("""() => {
                const s=JSON.parse(localStorage['oregon-estate-planner-v1']);
                return s.project.acres === 20 && s.plan.quickBuild.spacing === 'spread'
                  && s.plan.prompt === %s
                  && s.scenarios.find(c=>c.id===s.activeScenario).items.filter(item=>item.fromPlan).length === %d;
              }""" % (json.dumps(pqb_saved["plan"]["prompt"]), pqb_saved["count"]))
              and not pqb_errors)
        pqb_context.close()
        check("no JS errors after terrain overlays", not errors)
        b.close()
finally:
    srv.terminate()

if errors:
    print("errors:", errors[:3])
sys.exit(1 if fails else 0)
