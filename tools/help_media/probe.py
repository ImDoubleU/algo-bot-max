"""Inspect local demo controls without allowing API calls or external requests."""

import argparse
import json

from playwright.sync_api import sync_playwright


def safe_route(route):
    url = route.request.url
    if (
        url.startswith("http://127.0.0.1:8766/miniapp") and route.request.method == "GET"
    ) or url.startswith("data:"):
        route.continue_()
    else:
        route.abort()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="admin")
    parser.add_argument("--view", default="admin")
    parser.add_argument("--js", default="")
    args = parser.parse_args()
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1060, "height": 720})
        page.route("**/*", safe_route)
        page.goto(
            f"http://127.0.0.1:8766/miniapp?demo=1&demo_role={args.role}&view={args.view}",
            wait_until="networkidle",
        )
        if args.js:
            page.evaluate(args.js)
        print(page.locator("body").inner_text())
        print(
            json.dumps(
                page.locator("button,input,select,textarea").evaluate_all(
                    'els=>els.filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,id:e.id,name:e.name,text:(e.innerText||e.title||e.placeholder||e.getAttribute("aria-label")||"").slice(0,70)}))'
                ),
                ensure_ascii=False,
            )
        )
        browser.close()


if __name__ == "__main__":
    main()
