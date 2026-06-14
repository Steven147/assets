"""Static smoke test: verify new buttons are present in editor.html.

We can't unit-test the JS behavior without a browser, but a missing
button ID is the most common regression and is easy to catch here.
"""
import http.client
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
def server_url(tmp_path_factory):
    """Boot the editor server on a free port; yield base URL."""
    # Make sure meta.json and tile_paths.js exist (server normally does this).
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
    """GET an http:// URL via stdlib http.client, one fresh connection per call.

    We avoid urllib.request here because in this environment its keep-alive
    handling against SimpleHTTPRequestHandler (HTTP/1.0 default) raises a
    spurious 502 Bad Gateway even though the response body is fine.
    """
    assert url.startswith("http://")
    # url is like "http://127.0.0.1:54321/pipeline/editor/editor.html"
    after_scheme = url[len("http://"):]
    host_port, _, path = after_scheme.partition("/")
    host, port = host_port.split(":", 1)
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.request("GET", "/" + path, headers={"Connection": "close"})
        resp = conn.getresponse()
        body = resp.read()
        return resp.status, body
    finally:
        conn.close()


def test_editor_html_served(server_url):
    status, body = _get(f"{server_url}/pipeline/editor/editor.html")
    assert status == 200
    text = body.decode("utf-8")
    assert "id=\"sync-meta\"" in text
    assert "id=\"toggle-base\"" in text


def test_meta_served(server_url):
    """Sanity check: the existing meta endpoint still works."""
    status, _ = _get(f"{server_url}/pipeline/editor/meta.json")
    assert status == 200
