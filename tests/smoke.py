"""AcreForge smoke test. Run: python tests/smoke.py  (serves the repo on :8766)"""
import subprocess, sys, time, os, struct, zlib, json, re
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

def terrarium_png():
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    rows = bytearray()
    for y in range(256):
        rows.append(0)
        for x in range(256):
            value = 32768 + 100 + (x + y) * 0.12
            whole = int(value)
            rows.extend((whole // 256, whole % 256, int((value - whole) * 256), 255))
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
        page.route("https://s3.amazonaws.com/elevation-tiles-prod/terrarium/**",
                   lambda route: route.fulfill(status=200, body=dem,
                       content_type="image/png", headers={"Access-Control-Allow-Origin": "*"}))
        land_requests = {"fema": 0, "soil": 0, "epqs": 0}
        land_mode = {"fema_case": "partial-high"}
        elevation_mode = {"case": "mapped"}
        def mock_fema(route):
            land_requests["fema"] += 1
            query = parse_qs(urlparse(route.request.url).query)
            lon, lat = map(float, query["geometry"][0].split(","))
            features = []
            if land_mode["fema_case"] == "partial-high" and abs(lon + 123) < 0.0001 and abs(lat - 44) < 0.0001:
                features = [{"attributes": {"FLD_ZONE": "A", "ZONE_SUBTY": "1% annual chance", "SFHA_T": "T"}}]
            elif land_mode["fema_case"] == "partial-low" and abs(lon + 123) < 0.0001 and abs(lat - 44) < 0.0001:
                features = [{"attributes": {"FLD_ZONE": "X", "ZONE_SUBTY": "Minimal hazard", "SFHA_T": "F"}}]
            route.fulfill(json={"features": features})
        def mock_soil(route):
            land_requests["soil"] += 1
            query = json.loads(route.request.post_data)["query"]
            match = re.search(r"point\((-?[\d.]+)\s+(-?[\d.]+)\)", query)
            if not match:
                route.fulfill(status=400, json={"Message": "Missing sample point"})
                return
            lon = float(match.group(1))
            row = ["Clay loam", "Poorly drained", "D"] if lon > -123 else ["Sandy loam", "Well drained", "A"]
            route.fulfill(json={"Table": [row]})
        def mock_epqs(route):
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
        page.goto("http://localhost:8766/index.html")
        page.wait_for_timeout(800)
        for pg in ["dashboard", "planner", "designer", "reports", "settings"]:
            page.click(f"[data-page={pg}]")
            page.wait_for_timeout(300)
            check("nav " + pg, page.inner_text("body").strip() != "")
        page.click("[data-page=planner]")
        page.fill("#plPrompt","Build a self-sufficient homestead with a house, barn and well")
        page.click("[data-pl=gen]")
        page.wait_for_timeout(900)
        page.click("[data-pl=place]")
        page.wait_for_timeout(900)
        t = page.inner_text("body")
        n = page.evaluate("""()=>{const s=JSON.parse(localStorage['oregon-estate-planner-v1']);
          return s.scenarios.flatMap(c=>c.items).filter(o=>o.fromPlan).length}""")
        check("plan placed items (%d)" % n, n > 0)
        check("no JS errors", not errors)
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
        page.click("[data-page=designer]")
        page.locator('[data-action="toggle-map-view"]').click()
        page.locator('#stateHits path[data-state-map="OR"]').click()
        page.wait_for_selector(".ovbar", timeout=30000)
        for _ in range(6):
            page.locator(".maplibregl-ctrl-zoom-in").evaluate("el => el.click()")
            page.wait_for_timeout(150)
        page.locator('[data-ov="slope"]').check()
        page.locator('[data-ov="contours"]').check()
        page.locator('[data-ov="flood"]').check()
        page.locator('[data-ov="wet"]').check()
        page.wait_for_function("document.querySelector('#terrainAnalysisStatus')?.textContent.includes('Elevation sampled')", timeout=30000)
        for layer, value in [("slope", "50"), ("flood", "45"), ("wet", "55")]:
            page.locator(f'[data-ov-op="{layer}"]').evaluate("(e, value) => { e.value = value; e.dispatchEvent(new Event('input', {bubbles:true})); }", value)
        prefs = page.evaluate("() => JSON.parse(localStorage['acreforge-layerprefs'])")
        expected = {"slope": True, "contours": True, "flood": True, "wet": True}
        check("terrain overlays and opacity save", prefs["analysis"] == expected and prefs["op"]["slope"] == 0.5 and prefs["op"]["flood"] == 0.45 and prefs["op"]["wet"] == 0.55)
        page.reload()
        page.wait_for_timeout(800)
        page.locator('[data-page=designer]').first.click()
        page.locator('[data-action="toggle-map-view"]').click()
        page.locator('#stateHits path[data-state-map="OR"]').click()
        page.wait_for_selector(".ovbar", timeout=30000)
        check("overlay settings restore after reload", all(page.locator(f'[data-ov="{layer}"]').is_checked() for layer in expected) and page.locator('[data-ov-op="flood"]').input_value() == "45" and page.locator('[data-ov-op="wet"]').input_value() == "55")
        check("no JS errors after terrain overlays", not errors)
        b.close()
finally:
    srv.terminate()

if errors:
    print("errors:", errors[:3])
sys.exit(1 if fails else 0)
