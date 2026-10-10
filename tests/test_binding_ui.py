"""Exercise real miniapp scripts with controlled access responses."""

import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

MINIAPP = Path(__file__).parents[1] / "app/web/static/miniapp"


@pytest.fixture(scope="module")
def binding_browser():
    playwright = pytest.importorskip("playwright.sync_api")

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = urlsplit(path).path
            if path == "/miniapp":
                return str(MINIAPP / "index.html")
            target = (MINIAPP / path.removeprefix("/miniapp/static/")).resolve()
            return str(target if target.is_relative_to(MINIAPP.resolve())
                       else MINIAPP / "nonexistent")

        def log_message(self, *args):
            pass

    class Server(ThreadingHTTPServer):
        # Chromium loads the miniapp's scripts concurrently; avoid dropped connections.
        request_queue_size = 128

    server = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with playwright.sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel="msedge" if os.name == "nt" else None)
            yield browser, f"http://127.0.0.1:{server.server_port}"
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("scenario", ["parent_required", "expired", "auth", "network", "missing"])
def test_access_screen_mobile_guidance_and_retry(binding_browser, scenario):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": 390, "height": 850})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    attempts = []

    def api(route):
        if "/session" not in route.request.url:
            route.fulfill(status=200, content_type="application/json", body="{}")
            return
        attempts.append(route.request.url)
        if scenario == "network":
            route.abort()
        elif scenario == "auth":
            route.fulfill(status=401, content_type="application/json",
                          body=json.dumps({"detail": "HTTP 401 Unauthorized"}))
        else:
            route.fulfill(status=200, content_type="application/json", body=json.dumps({
                "tenant_slug": "school", "has_access": False, "students": [],
                "access_reason": "access_expired" if scenario == "expired" else "parent_required",
                "access_message": "Привязка сохранена. Обратитесь в школу." if scenario == "expired"
                else "Профиль ученика привязан. Родителю нужно открыть письмо школы.",
                "account": None, "staff_roles": [], "student_roles": [], "orders": [], "ledger": [],
            }))

    page.route(base + "/api/v1/**", api)
    page.goto(base + "/miniapp" + ("" if scenario == "missing" else "?max_user_id=9091"),
              wait_until="networkidle")
    gate = page.locator("#accessGate")
    assert gate.is_visible()
    assert not page.locator(".app-shell").is_visible()
    text = gate.inner_text()
    assert "HTTP" not in text and "401" not in text
    if scenario == "parent_required":
        assert "Осталось подключить родителя" in text
    elif scenario == "expired":
        assert "Привязка сохранена" in text and "Нужно подключить родителя" not in text
    elif scenario == "network":
        assert "Привязка от этого не меняется" in text
    else:
        assert "Откройте кабинет через MAX" in text
    page.locator("#retryAccessButton").click()
    page.wait_for_function("!document.querySelector('#retryAccessButton').disabled")
    assert len(attempts) == (0 if scenario == "missing" else 2)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    page.close()


def test_api_errors_hide_technical_details_and_reset_old_gate_message(binding_browser):
    browser, base = binding_browser
    page = browser.new_page()
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp", wait_until="networkidle")
    result = page.evaluate("""() => {
      const messages = [apiErrorMessage(null, 503), apiErrorMessage('HTTP 400 Bad Request', 400),
        apiErrorMessage('Traceback: SQLSTATE connection failed', 500)];
      applyAccessGate('Old stale message'); state.accessMessage = ''; applyAccessGate();
      return {messages, gate: document.querySelector('#accessGateMessage').textContent};
    }""")
    assert all("HTTP" not in text and "SQLSTATE" not in text for text in result["messages"])
    assert "Old stale message" not in result["gate"]
    page.close()
