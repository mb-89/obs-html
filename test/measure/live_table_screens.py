"""Screenshots of a live table after a read, and its line, in Claude's artifact viewer stood in.

Reader: whoever reviews how a live table looks once its current rows arrive (generic-tables.md,
Current data: Status line).

    uv run python adapters/html/test/measure/live_table_screens.py [--output DIRECTORY]

It builds the live-source browser tests' tracker (test/live_viewer.py) with this checkout's adapter,
opens it in the viewer's frame with the stand-in granted (``stand_in``), shows the live chapter and
writes two screenshots at device scale factor 2: ``live-table-phone.png`` at 390 x 844 and
``live-table-desktop.png`` at 1280 x 800, each of the table with its line. The browser is
OBS_HTML_TEST_NATIVE_BROWSER where set, else Playwright's own.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

TEST = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(TEST)]

from artifacts import artifact_html  # noqa: E402
from browser.viewer import viewer_page, with_stand_in  # noqa: E402
from live_viewer import LINE, SHELL, SHOW, stand_in, tracker  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

SIZES = {"phone": (390, 844), "desktop": (1280, 800)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path.cwd(), help="where the screenshots go")
    output = parser.parse_args(argv).output
    output.mkdir(parents=True, exist_ok=True)
    artifact = with_stand_in(artifact_html(tracker()), stand_in())
    executable = os.environ.get("OBS_HTML_TEST_NATIVE_BROWSER")
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
        browser = playwright.chromium.launch(**({"executable_path": executable} if executable else {}))
        for name, (width, height) in SIZES.items():
            host = Path(folder) / f"{name}.html"
            host.write_text(viewer_page(artifact, width, height), encoding="utf-8")
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
            page.goto(host.as_uri())
            frame = page.locator("#artifact").element_handle().content_frame()
            expect(frame.locator("html")).to_have_attribute("data-artifact-status", "ready")
            frame.evaluate(SHOW, "live")
            expect(frame.locator(LINE)).to_have_text("Showing current data")
            frame.locator(SHELL).scroll_into_view_if_needed()
            path = output / f"live-table-{name}.png"
            page.screenshot(path=path)
            print(f"Wrote {path}.")
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
