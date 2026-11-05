"""Claude-preview-like frames for the browser tier: an artifact as srcdoc of a sandboxed frame."""
import contextlib
import functools
import html
import http.server
import threading
from pathlib import Path


# The two preview-like frames: Claude's preview as srcdoc of a frame sandboxed to scripts only
# (null origin), and as srcdoc of a same-origin frame with the flags a preview host grants,
# served from an http origin as Claude's preview is.
SANDBOXES = {
    "null-origin": "allow-scripts",
    "same-origin": "allow-scripts allow-same-origin allow-popups allow-forms allow-downloads",
}


def preview_wrapper(artifact: str, sandbox: str, width: int = 1100, height: int = 700) -> str:
    return (
        '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><body style="margin:0">'
        f'<iframe id="artifact" sandbox="{sandbox}" style="width:{width}px;height:{height}px;border:0" '
        f'srcdoc="{html.escape(artifact, quote=True)}"></iframe>'
    )


@contextlib.contextmanager
def http_origin(folder: Path):
    """Serve a folder from an http origin for as long as the block runs."""
    handler = functools.partial(QuietHandler, directory=str(folder))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass


def open_preview(tmp_path: Path, reader_browser, errors: list[str], artifact: str, frame_kind: str,
                 origin: str | None = None):
    """Open an artifact in one of the preview-like frames; same-origin frames need an http origin."""
    from playwright.sync_api import expect

    wrapper = tmp_path / f"preview-{frame_kind}.html"
    wrapper.write_text(preview_wrapper(artifact, SANDBOXES[frame_kind]), encoding="utf-8")
    page = reader_browser.new_page(viewport={"width": 1200, "height": 800})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.goto(f"{origin}/{wrapper.name}" if origin else wrapper.as_uri())
    # The iframe's own Frame, not a FrameLocator: its locators resolve in about 3 ms, where a
    # FrameLocator re-resolves the iframe on every call (about 50 ms).
    frame = page.locator("#artifact").element_handle().content_frame()
    expect(frame.locator("html")).to_have_attribute("data-artifact-status", "ready")
    return page, frame


def click_where_visible(page, frame, selector: str) -> None:
    """Click by pointer at the element's visible centre, failing if something else covers it."""
    element = frame.locator(selector).first
    element.scroll_into_view_if_needed()
    covering = element.evaluate("""(element) => {
        const box = element.getBoundingClientRect();
        const top = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
        if (!top || element.contains(top)) return "";
        const owner = top.closest("[data-step], [data-bar], button, a") || top;
        return owner.outerHTML.slice(0, 120);
    }""")
    assert covering == "", f"{selector} is covered at its visible position by {covering}"
    box = element.bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
