"""Claude's artifact viewer as a browser-tier fixture: the known properties of that host.

The artifact is the srcdoc of an iframe sandboxed to scripts only (no `allow-same-origin`, so a
null origin), under a Content Security Policy that blocks every network request, in a host page
whose `prefers-color-scheme` is dark or light and which paints its own canvas in that scheme, as
the viewer does. Whatever the artifact leaves transparent or uncoloured shows the host through.

    page, frame = open_viewer(tmp_path, reader_browser, errors, artifact, "dark")

`errors` collects page errors and console errors, including CSP violations.
"""
import html
from pathlib import Path


HOST_SCHEMES = ("dark", "light")

# Inline scripts, styles and data/blob resources only; no request leaves the page.
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data: blob:; font-src data:; media-src data: blob:; frame-src data: blob:; "
    "connect-src 'none'"
)


def viewer_page(artifact: str, width: int = 1100, height: int = 700) -> str:
    return (
        '<!doctype html><meta charset="utf-8">'
        f'<meta http-equiv="Content-Security-Policy" content="{CONTENT_SECURITY_POLICY}">'
        '<meta name="color-scheme" content="light dark">'
        '<body style="margin:0;background:Canvas;color:CanvasText">'
        f'<iframe id="artifact" sandbox="allow-scripts" style="width:{width}px;height:{height}px;border:0" '
        f'srcdoc="{html.escape(artifact, quote=True)}"></iframe>'
    )


def open_viewer(tmp_path: Path, reader_browser, errors: list[str], artifact: str, host_scheme: str,
                width: int = 1100, init_script: str = ""):
    """Open an artifact in a viewer `width` pixels wide with the host in `host_scheme`; return (page, frame).
    `init_script`, where given, runs in every frame before its own scripts, to stand in for a host's APIs."""
    from playwright.sync_api import expect

    assert host_scheme in HOST_SCHEMES, f"test/browser/viewer.py: host_scheme {host_scheme!r} is not one of {HOST_SCHEMES}"
    host = tmp_path / f"viewer-{host_scheme}.html"
    host.write_text(viewer_page(artifact, width), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": width + 100, "height": 800}, color_scheme=host_scheme)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    if init_script:
        page.add_init_script(init_script)
    page.goto(host.as_uri())
    frame = page.locator("#artifact").element_handle().content_frame()
    expect(frame.locator("html")).to_have_attribute("data-artifact-status", "ready")
    return page, frame
