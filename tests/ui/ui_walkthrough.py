"""Browser walkthrough of the real app (Playwright driving the locally installed Microsoft Edge).

Run with the server already started on 127.0.0.1:8765:
    .venv\\Scripts\\python.exe tests\\ui\\ui_walkthrough.py [out_dir]
Exercises: dashboard demo creation -> target analysis -> environment -> optimisation -> generation ->
audio studio (audio decoding) -> export; collects console errors and screenshots.
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "nm_ui")
os.makedirs(OUT, exist_ok=True)


def main():
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge", headless=True)
        pg = b.new_page(viewport={"width": 1500, "height": 950})
        tall = lambda: pg.set_viewport_size({"width": 1500, "height": 2600})
        short = lambda: pg.set_viewport_size({"width": 1500, "height": 950})
        pg.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.goto(BASE)
        pg.wait_for_selector("text=Make the machine recede")
        pg.screenshot(path=os.path.join(OUT, "01_dashboard.png"))
        pg.click("text=Try the drill demo")
        pg.wait_for_selector("text=Run optimisation", timeout=30000)
        # target page with analysis
        pg.click("nav >> text=Target Noise")
        pg.wait_for_selector("text=Analysis ·", timeout=30000)
        time.sleep(1.0)
        tall(); time.sleep(0.6); pg.screenshot(path=os.path.join(OUT, "02_target.png")); short()
        # spectrum editor tab renders
        pg.click("role=tab[name='Spectrum / Lw editor']")
        pg.wait_for_selector("svg[aria-label='Spectral editor']")
        pg.screenshot(path=os.path.join(OUT, "03_editor.png"))
        # environment
        pg.click("nav >> text=Soundscape Designer")
        pg.wait_for_selector("text=Sound sources")
        tall(); time.sleep(0.6); pg.screenshot(path=os.path.join(OUT, "04_soundscape.png")); short()
        # masking: optimise and generate
        pg.click("nav >> text=Masking Laboratory")
        pg.click("text=Run optimisation")
        pg.wait_for_selector("text=Predicted masking in", timeout=60000)
        time.sleep(0.8)
        tall(); time.sleep(0.6); pg.screenshot(path=os.path.join(OUT, "05_masking_opt.png")); short()
        pg.click("button:has-text('Generate soundscape')")
        pg.wait_for_selector("text=Evaluation of the rendered soundscape", timeout=300000)
        time.sleep(1.0)
        tall(); time.sleep(0.6); pg.screenshot(path=os.path.join(OUT, "06_masking_eval.png")); short()
        # audio studio: wait for decode, start playback briefly
        pg.click("nav >> text=Audio Studio")
        pg.wait_for_selector("button:has-text('Play')", timeout=60000)
        pg.wait_for_function("() => !document.body.innerText.includes('Loading…')", timeout=60000)
        pg.click("button:has-text('Play')")
        time.sleep(1.2)
        pg.keyboard.press("1")
        time.sleep(0.4)
        tall(); time.sleep(0.6); pg.screenshot(path=os.path.join(OUT, "07_studio.png")); short()
        pg.keyboard.press(" ")
        # export
        pg.click("nav >> text=Export Center")
        pg.click("button:has-text('Export')")
        pg.wait_for_selector("text=Last export — validation", timeout=120000)
        time.sleep(0.5)
        tall(); time.sleep(0.6); pg.screenshot(path=os.path.join(OUT, "08_export.png")); short()
        valid = pg.locator("text=valid").count()
        failed = pg.locator("text=check failed").count()
        # light theme check
        pg.click("nav >> text=Settings")
        pg.click("role=tab[name='Light']")
        pg.click("nav >> text=Masking Laboratory")
        pg.wait_for_selector("text=Evaluation of the rendered soundscape", timeout=30000)
        time.sleep(0.8)
        pg.screenshot(path=os.path.join(OUT, "09_light.png"))
        pg.click("nav >> text=Settings")
        pg.click("role=tab[name='Dark']")
        b.close()
    print(f"screenshots: {OUT}")
    print(f"export validation badges: valid={valid} failed={failed}")
    print("console errors:", len(errors))
    for e in errors[:20]:
        print("  ", e)
    return 1 if errors or failed else 0


if __name__ == "__main__":
    sys.exit(main())
