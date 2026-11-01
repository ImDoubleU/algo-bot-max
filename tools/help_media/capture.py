"""Capture only named demo states and require a visible, bounded target."""

import hashlib
import json
from pathlib import Path

from external import MOCKS, html
from screens import AFTER, SCREENS, Screen

BASE = "http://127.0.0.1:8766"
ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(__file__).parent / ".cache"


class Capture:
    def __init__(self, browser):
        self.browser = browser
        self.page = None
        self.context = None
        self.current = None
        self.records = []
        self.blocked = []
        CACHE.mkdir(exist_ok=True)

    def route(self, route):
        request = route.request
        # No backend endpoints, writes, remote QR services, MAX or email.
        if request.method == "GET" and request.url.startswith(BASE + "/miniapp"):
            route.continue_()
        elif request.url.startswith(("data:", "file:")):
            route.continue_()
        else:
            self.blocked.append({"url": request.url, "method": request.method})
            route.abort()

    def load(self, name):
        if self.current == name:
            return
        if self.context:
            self.context.close()
        screen = SCREENS.get(name, Screen("public", reconstructed=True))
        if name not in SCREENS and name not in MOCKS:
            raise ValueError("Unknown screen: " + name)
        self.context = self.browser.new_context(
            viewport={"width": 390 if screen.mobile else 1060, "height": 740},
            reduced_motion="reduce",
            locale="ru-RU",
        )
        self.context.route("**/*", self.route)
        self.page = self.context.new_page()
        if name in MOCKS:
            self.page.set_content(html(name))
            self.current = name
            return
        self.page.goto(
            f"{BASE}/miniapp?demo=1&demo_role={screen.role}&view={screen.view}&feedback_preview=1",
            wait_until="networkidle",
        )
        self.page.wait_for_function('typeof state!=="undefined" && apiContext.demoMode===true')
        if screen.view == "wallet" and screen.role == "admin":
            self.page.evaluate(
                "applyAdminStudentRegistry(demoAdminStudentRegistry());renderLedger();"
            )
        if screen.js:
            self.page.evaluate("async () => {" + screen.js + "}")
        if name in AFTER:
            self.page.evaluate("async () => {" + AFTER[name] + "}")
        self.page.evaluate(r"""() => {
          document.querySelectorAll('a[href]').forEach(a=>{
            if (/max\.ru|st\.max\.ru/.test(a.href)) {
              a.href='https://example.invalid/DEMO';
              a.textContent=a.textContent.replace(/https?:\/\/\S+/g,
                'https://example.invalid/DEMO');
            }
          });
          document.querySelectorAll('input,textarea').forEach(e=>{
            if (/https?:\/\/[^\s]*max\.ru/.test(e.value)) e.value='https://example.invalid/DEMO';
          });
          document.querySelectorAll('img').forEach(i=>{
            if(/qr|qrcode/i.test(i.alt+' '+i.src) && !/safe-qr-placeholder/.test(i.src)) {
              i.src='/miniapp/static/assets/safe-qr-placeholder.svg';
            }
          });
        }""")
        self.page.wait_for_timeout(120)
        self.current = name

    def locate(self, target):
        if target.startswith(("#", ".", "[")):
            candidates = self.page.locator(target)
        else:
            candidates = self.page.get_by_text(target, exact=True)
        visible = [
            candidates.nth(i) for i in range(candidates.count()) if candidates.nth(i).is_visible()
        ]
        if not visible:
            raise ValueError(f"{self.current}: missing visible target {target!r}")
        # Multiple equal navigation labels are expected on desktop/mobile; use
        # the smallest visible control rather than an ancestor or whole panel.
        visible.sort(key=lambda loc: (lambda b: b["width"] * b["height"])(loc.bounding_box()))
        locator = visible[0]
        if locator.evaluate("e=>e.tagName") == "INPUT" and locator.evaluate("e=>e.type") in (
            "file",
            "checkbox",
        ):
            parent = locator.locator("xpath=..")
            if parent.bounding_box()["width"] < 700:
                locator = parent
        locator.evaluate(
            'e=>e.scrollIntoView({block:"center",inline:"nearest",behavior:"instant"})'
        )
        self.page.wait_for_timeout(80)
        rect = locator.bounding_box()
        if not rect or rect["width"] < 2 or rect["height"] < 2:
            raise ValueError(f"{self.current}: target has no usable bounds: {target}")
        if rect["width"] > 1000 or rect["height"] > 550:
            raise ValueError(f"{self.current}: target too broad: {target} {rect}")
        self.target_clickable = locator.evaluate("""e =>
          e.matches('button,a[href],summary,input[type="checkbox"],input[type="radio"],select')
          || (e.tagName === 'LABEL'
            && Boolean(e.querySelector('input[type="checkbox"],input[type="radio"]')))
        """)
        return rect

    def shot(self, spec):
        name, target = spec.split("@", 1)
        self.load(name)
        rect = self.locate(target)
        from screens import Screen

        screen = SCREENS.get(name, Screen("public", reconstructed=True))
        width = 390 if screen.mobile else 1060
        # Keep the relevant control and nearby context, not an unrelated full dashboard.
        crop_w = width if screen.mobile else min(width, max(640, rect["width"] + 120))
        crop_h = max(320 if screen.mobile else 340, min(640, rect["height"] + 80))
        x = max(0, min(width - crop_w, rect["x"] + rect["width"] / 2 - crop_w / 2))
        if not screen.mobile and rect["x"] < 240 and rect["width"] < 240:
            x = 0
        elif not screen.mobile and rect["x"] >= 240 and x < 240 <= width - crop_w:
            x = 240
        y = max(0, min(740 - crop_h, rect["y"] + rect["height"] / 2 - crop_h / 2))
        if rect["x"] < x or rect["x"] + rect["width"] > x + crop_w:
            raise ValueError(f"{name}: target clipped horizontally: {target} {rect}")
        if rect["y"] < y or rect["y"] + rect["height"] > y + crop_h:
            raise ValueError(f"{name}: target clipped: {target} {rect}")
        key = hashlib.sha1(spec.encode()).hexdigest()[:16]
        path = CACHE / f"source-{key}.png"
        self.page.screenshot(
            path=str(path),
            clip={"x": x, "y": y, "width": crop_w, "height": crop_h},
            animations="disabled",
        )
        record = {
            "spec": spec,
            "path": str(path),
            "rect": {
                "x": rect["x"] - x,
                "y": rect["y"] - y,
                "width": rect["width"],
                "height": rect["height"],
            },
            "width": crop_w,
            "height": crop_h,
            "reconstructed": screen.reconstructed,
            "mobile": screen.mobile,
            "role": screen.role,
            "view": screen.view,
            "clickable": self.target_clickable,
        }
        self.records.append(record)
        return record

    def close(self):
        if self.context:
            self.context.close()


def write_audit(capture, records=None):
    previous_file = CACHE / "capture-audit.json"
    previous = (
        json.loads(previous_file.read_text(encoding="utf-8")) if previous_file.exists() else {}
    )
    (CACHE / "capture-audit.json").write_text(
        json.dumps(
            {
                "targets": capture.records if records is None else records,
                "blocked_requests": capture.blocked or previous.get("blocked_requests", []),
                "guard": "Local unsigned demo GET only; backend, writes and external hosts blocked",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="msedge", headless=True)
        capture = Capture(browser)
        for name in SCREENS:
            try:
                capture.load(name)
                print("OK", name, flush=True)
            except Exception as error:
                print("FAIL", name, str(error).splitlines()[0], flush=True)
        capture.close()
        browser.close()
