"""AcreForge smoke test. Run: python tests/smoke.py  (serves the repo on :8766)"""
import subprocess, sys, time, os
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

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(service_workers="block")
        page = ctx.new_page()
        page.add_init_script("localStorage.setItem('acreforge-guide-seen','1')")
        page.on("pageerror", lambda e: errors.append(str(e)))
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
        b.close()
finally:
    srv.terminate()

if errors:
    print("errors:", errors[:3])
sys.exit(1 if fails else 0)
