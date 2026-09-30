import functools
import http.server
import threading

import pytest

import WebDumper


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text(
        '<html><head><link rel="stylesheet" href="style.css">'
        '<script src="app.js"></script></head>'
        '<body><img src="logo.png"></body></html>',
        encoding="utf-8",
    )
    (root / "style.css").write_text("body { color: #000; }", encoding="utf-8")
    (root / "app.js").write_text("console.log('hi');", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(root)
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_download_website_saves_html_and_assets(site, tmp_path):
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    assert (out / "index.html").is_file()
    assert (out / "style.css").read_text(encoding="utf-8") == "body { color: #000; }"
    assert (out / "app.js").read_text(encoding="utf-8") == "console.log('hi');"
    assert (out / "logo.png").read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_download_website_rewrites_asset_paths_to_local(site, tmp_path):
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="style.css"' in html
    assert 'src="app.js"' in html
    assert 'src="logo.png"' in html
    assert "127.0.0.1" not in html


def test_download_website_reuses_existing_folder(site, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    WebDumper.download_website(site, str(out))

    assert (out / "index.html").is_file()


def test_main_builds_hostname_folder(site, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: site)

    WebDumper.main()

    folder = tmp_path / "127.0.0.1_download"
    assert folder.is_dir()
    assert (folder / "index.html").is_file()
