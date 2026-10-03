import functools
import http.server
import os
import threading
import time

import pytest

import WebDumper


SITE_FILES = {
    "index.html": (
        '<html><head><link rel="stylesheet" href="style.css">'
        '<script src="app.js"></script></head>'
        '<body><img src="logo.png"></body></html>'
    ),
    "style.css": "body { color: #000; }",
    "app.js": "console.log('hi');",
    "logo.png": b"\x89PNG\r\n\x1a\n",
}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@pytest.fixture
def serve(tmp_path):
    started = []

    def _serve(files):
        root = tmp_path / f"site{len(started)}"
        root.mkdir()
        for name, body in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                target.write_bytes(body)
            else:
                target.write_text(body, encoding="utf-8")

        handler = functools.partial(QuietHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started.append((server, thread))
        return f"http://127.0.0.1:{server.server_address[1]}/"

    yield _serve

    for server, thread in started:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def site(serve):
    return serve(SITE_FILES)


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


def test_download_website_keeps_asset_directory_structure(serve, tmp_path):
    site = serve(
        {
            "index.html": '<img src="/a/logo.png"><img src="/b/logo.png">',
            "a/logo.png": b"IMG-A",
            "b/logo.png": b"IMG-B",
        }
    )
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    assert (out / "a" / "logo.png").read_bytes() == b"IMG-A"
    assert (out / "b" / "logo.png").read_bytes() == b"IMG-B"
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="a/logo.png"' in html
    assert 'src="b/logo.png"' in html


def test_download_website_matches_rel_case_insensitively(serve, tmp_path):
    site = serve(
        {
            "index.html": '<link rel="preload stylesheet" href="main.css">'
            '<link rel="Stylesheet" href="second.css">',
            "main.css": "A",
            "second.css": "B",
        }
    )
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    assert (out / "main.css").read_text(encoding="utf-8") == "A"
    assert (out / "second.css").read_text(encoding="utf-8") == "B"
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="main.css"' in html
    assert 'href="second.css"' in html


def test_download_website_skips_missing_asset_without_writing_error_page(serve, tmp_path):
    site = serve({"index.html": '<img src="missing.gif">'})
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    assert not (out / "missing.gif").exists()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="missing.gif"' in html


def test_download_website_skips_unsupported_and_empty_asset_urls(serve, tmp_path):
    site = serve(
        {
            "index.html": '<img src="data:image/svg+xml,%3Csvg%3E">'
            '<link rel="stylesheet" href="/">'
            '<script src="app.js?v=2"></script>',
            "app.js": "J",
        }
    )
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    assert (out / "app.js").read_text(encoding="utf-8") == "J"
    assert sorted(entry.name for entry in out.iterdir()) == ["app.js", "index.html"]
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="app.js"' in html


def test_download_website_still_rewrites_when_one_asset_fails(serve, tmp_path):
    site = serve(
        {
            "index.html": '<img src="missing.gif"><script src="app.js"></script>',
            "app.js": "J",
        }
    )
    out = tmp_path / "out"
    WebDumper.download_website(site, str(out))

    assert (out / "app.js").read_text(encoding="utf-8") == "J"
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="app.js"' in html


@pytest.mark.parametrize(
    ("segment", "expected"),
    [
        ("example.com", "example.com"),
        ("::1", "__1"),
        ("a<b>c", "a_b_c"),
        ("na me.png", "na me.png"),
        ("trailing.", "trailing"),
        ("...", None),
    ],
)
def test_sanitize_filename(segment, expected):
    assert WebDumper.sanitize_filename(segment) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://h.com/css/main.css", "css/main.css"),
        ("http://h.com/css/main.css?v=2", "css/main.css"),
        ("http://h.com/na%20me.png", "na me.png"),
        ("http://h.com/CON.css", "_CON.css"),
        ("http://h.com/a/../b.css", None),
        ("http://h.com/", None),
        ("http://h.com", None),
        ("data:image/png;base64,AAA", None),
        ("javascript:void(0)", None),
    ],
)
def test_local_asset_path(url, expected):
    result = WebDumper.local_asset_path(url)
    if expected is None:
        assert result is None
    else:
        assert result.replace(os.sep, "/") == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com"),
        ("  example.com/path  ", "https://example.com/path"),
        ("localhost:8000", "http://localhost:8000"),
        ("127.0.0.1:8000", "http://127.0.0.1:8000"),
        ("[::1]:8000", "http://[::1]:8000"),
        ("//cdn.example.com", "https://cdn.example.com"),
        ("http://127.0.0.1:8000/", "http://127.0.0.1:8000/"),
    ],
)
def test_normalize_url_adds_missing_scheme(raw, expected):
    assert WebDumper.normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "   ", "ftp://example.com", "file:///etc/passwd", "https://"]
)
def test_normalize_url_rejects_unusable_input(raw):
    with pytest.raises(ValueError):
        WebDumper.normalize_url(raw)


def test_main_accepts_url_without_scheme(site, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: site.split("//")[1])

    WebDumper.main()

    folder = tmp_path / "127.0.0.1_download"
    assert (folder / "index.html").is_file()


def test_main_reports_invalid_url_without_creating_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "   ")

    with pytest.raises(SystemExit) as failure:
        WebDumper.main()

    assert failure.value.code == 1
    assert list(tmp_path.iterdir()) == []
    assert "No URL entered." in capsys.readouterr().err


def test_main_exits_nonzero_when_the_site_is_unreachable(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: "http://127.0.0.1:1/")

    with pytest.raises(SystemExit) as failure:
        WebDumper.main()

    assert failure.value.code == 1
    assert "Download failed:" in capsys.readouterr().err


def test_main_stops_animation_thread(site, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *_: site)

    WebDumper.main()

    alive = [
        thread.name
        for thread in threading.enumerate()
        if thread.is_alive() and "animate_download" in thread.name
    ]
    assert alive == []


def test_animate_download_returns_when_stop_event_is_set():
    stop_event = threading.Event()
    thread = threading.Thread(
        target=WebDumper.animate_download, args=(stop_event,), daemon=True
    )
    thread.start()
    time.sleep(0.2)
    stop_event.set()
    thread.join(timeout=2)

    assert not thread.is_alive()
