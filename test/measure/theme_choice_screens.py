"""Screenshots of the Settings bar's Theme select below Appearance, and the page in each theme.

Reader: whoever reviews how the Theme select and a chosen theme look (artifact-ui.md, Styling).

    uv run python adapters/html/test/measure/theme_choice_screens.py [--output DIRECTORY]

It builds a page with the made-up fixture theme (test/fixtures/local-themes) with this checkout's
adapter, opens it in the viewer's frame, opens the Settings bar on the first chapter and writes, at
device scale factor 2, one screenshot for each size, appearance and theme:
``theme-<phone|desktop>-<light|dark>-<default|contrast>.png``, the phone at 390 x 844 and the desktop
at 1280 x 800. The browser is OBS_HTML_TEST_NATIVE_BROWSER where set, else Playwright's own.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

TEST = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(TEST)]

from artifacts import artifact_html  # noqa: E402
from browser.viewer import viewer_page  # noqa: E402
from documents import chapter, document, heading, paragraph  # noqa: E402
from test_local_themes import fixture_choice  # noqa: E402
from playwright.sync_api import expect, sync_playwright  # noqa: E402

SIZES = {"phone": (390, 844), "desktop": (1280, 800)}
CHOOSE = """([selector, value]) => {
    const select = document.querySelector(selector);
    select.value = value;
    select.dispatchEvent(new Event("change"));
}"""


def page_with_themes() -> str:
    text = "A paragraph in the theme's content font and spacing. " * 4
    return artifact_html(document("Themes", chapter("one", "Theme choice", heading(1, "Theme choice"),
                                                    paragraph(text), paragraph(text))), style_choice=fixture_choice())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=Path.cwd(), help="where the screenshots go")
    output = parser.parse_args(argv).output
    output.mkdir(parents=True, exist_ok=True)
    artifact = page_with_themes()
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
            frame.evaluate("() => { obsPages.setPaged(false); obsArtifact.activateChapter('one'); "
                           "obsArtifact.openBar('settings'); }")
            expect(frame.locator("[data-style-select]")).to_be_visible()
            for appearance in ("light", "dark"):
                frame.evaluate(CHOOSE, ["[data-theme-select]", appearance])
                for style in ("default", "contrast"):
                    frame.evaluate(CHOOSE, ["[data-style-select]", style])
                    path = output / f"theme-{name}-{appearance}-{style}.png"
                    page.screenshot(path=path)
                    print(f"Wrote {path}.")
            page.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
