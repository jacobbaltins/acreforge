"""AcreForge smoke test. Run: python tests/smoke.py  (serves the repo on :8766)"""
import subprocess, sys, time, os, struct, zlib
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
        page.click("[data-page=designer]")
        page.locator('[data-action="toggle-map-view"]').click()
        page.locator('#stateHits path[data-state-map="OR"]').click()
        page.wait_for_selector(".ovbar", timeout=30000)
        for _ in range(6):
            page.locator(".maplibregl-ctrl-zoom-in").evaluate("el => el.click()")
            page.wait_for_timeout(150)
        page.locator('[data-ov="slope"]').check()
        page.locator('[data-ov="contours"]').check()
        page.wait_for_function("document.querySelector('#terrainAnalysisStatus')?.textContent.includes('Elevation sampled')", timeout=30000)
        page.locator('[data-ov-op="slope"]').evaluate("e => { e.value = '50'; e.dispatchEvent(new Event('input', {bubbles:true})); }")
        prefs = page.evaluate("() => JSON.parse(localStorage['acreforge-layerprefs'])")
        check("slope and contour overlays render and persist", prefs["analysis"] == {"slope": True, "contours": True} and prefs["op"]["slope"] == 0.5)
        check("no JS errors after terrain overlays", not errors)
        b.close()
finally:
    srv.terminate()

if errors:
    print("errors:", errors[:3])
sys.exit(1 if fails else 0)
