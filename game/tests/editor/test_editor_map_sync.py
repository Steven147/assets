"""Static smoke test: verify map-grid sync symbols are wired up.

The DOM-coupled JS code (BackgroundAligner / MapEditor) can't be unit-tested
in node without a browser. This catches the most common regressions:
- _setupMapSync / _onMapMove not added
- doubleClickZoom not disabled
- latLngToContainerPoint not called
"""
import http.client
import re
import socketserver
import threading
import time

import pytest

from pipeline.editor.editor_server import (
    write_meta,
    write_tile_paths_to,
    resolve_meta,
    find_free_port,
    EditorHandler,
    EDITOR_DIR,
)


@pytest.fixture(scope="module")
def server_url():
    """Boot the editor server on a free port; yield base URL."""
    meta = resolve_meta(name="htmltest", city="shanghai", rows=3, cols=3)
    write_meta(meta, EDITOR_DIR / "meta.json")
    write_tile_paths_to(EDITOR_DIR / "tile_paths.js")

    port = find_free_port()
    httpd = socketserver.TCPServer(("127.0.0.1", port), EditorHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def _get(url: str) -> tuple[int, bytes]:
    """GET an http:// URL via stdlib http.client. Mirrors test_editor_html._get."""
    assert url.startswith("http://")
    after_scheme = url[len("http://"):]
    host_port, _, path = after_scheme.partition("/")
    host, port = host_port.split(":", 1)
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.request("GET", "/" + path, headers={"Connection": "close"})
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_map_sync_symbols_present(server_url):
    """Editor app must wire up the map-grid sync feature."""
    status, body = _get(f"{server_url}/pipeline/editor/editor_app.js")
    assert status == 200
    text = body.decode("utf-8")
    # Use word-boundary / identifier regexes so substring matches
    # (e.g. "_setupMapSync_X") don't silently pass.
    assert re.search(r"\b_setupMapSync\b", text), "missing _setupMapSync method"
    assert re.search(r"\b_onMapMove\b", text), "missing _onMapMove method"
    assert "latLngToContainerPoint" in text, "missing latLngToContainerPoint call"
    assert "doubleClickZoom: false" in text, "doubleClickZoom not disabled"


def test_painting_mode_symbols_present(server_url):
    """Editor app must wire up the 3 painting modes (dragger/painter/bigger)."""
    # HTML: 3 mode buttons
    _, body = _get(f"{server_url}/pipeline/editor/editor.html")
    html = body.decode("utf-8")
    assert 'id="mode-dragger"' in html, "missing mode-dragger button"
    assert 'id="mode-painter"' in html, "missing mode-painter button"
    assert 'id="mode-bigger"' in html, "missing mode-bigger button"
    # JS: 3 mode handlers + helpers
    _, body = _get(f"{server_url}/pipeline/editor/editor_app.js")
    text = body.decode("utf-8")
    assert re.search(r"\b_setMode\b", text), "missing _setMode method"
    assert re.search(r"\b_paintAt\b", text), "missing _paintAt method"
    assert re.search(r"\b_brushOutline\b", text), "missing _brushOutline field"
    assert "'dragger'" in text and "'painter'" in text and "'bigger'" in text, "missing mode literals"
