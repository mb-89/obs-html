"""Every chapter of every fixture Document opens and scrolls, on a desktop and a phone, with and
without reduced motion.

Reader: whoever changes the reader runtime, its motion rules, or the chapter sweep
(test/chapter_sweep.py, which owns how a sweep runs).

Each fixture artifact is swept at each viewport by the test process's sweep child, with a hard
timeout a little under the test's own, so a page whose main thread locks fails its test and names the chapter it was on.
The test of a page that locks bounds the locked step by the page's own opening time instead (STALL).
Under reduced motion, a figure chapter of figures.json and of document.json once locked the
page: artifact-ui.md, Accessibility, owns the reduced-motion rule.
"""
import json

import pytest

from artifacts import artifact_html
from chapter_sweep import STALL, VIEWPORTS, Sweeper, compare
from conftest import ROOT

DOCUMENTS = sorted((ROOT / "test" / "fixtures" / "documents").glob("*.json"))
# Seconds the test keeps for itself past the sweep's hard timeout: to build the artifact and to
# report a sweep that timed out before pytest-timeout stops the test.
GRACE = 6


def sweep_timeout(request) -> float:
    return request.node.get_closest_marker("timeout").args[0] - GRACE


@pytest.fixture(scope="session")
def sweeper():
    """The test process's sweep child (test/chapter_sweep.py, Sweeper), kept from one sweep to the next."""
    kept = Sweeper()
    yield kept
    kept.close()


@pytest.mark.browser
@pytest.mark.parametrize("document, viewport", [
    # Each artifact's sweep at each viewport is a test of its own, in a group of its own
    # (test/conftest.py), not after the module's others.
    pytest.param(path, viewport, id=f"{path.stem}-{viewport}",
                 marks=pytest.mark.xdist_group(f"chapter-sweep-{path.stem}-{viewport}"))
    for path in DOCUMENTS for viewport in VIEWPORTS])
def test_every_chapter_opens_and_scrolls_on_desktop_and_phone_with_and_without_reduced_motion(document, viewport,
                                                                                              tmp_path, request,
                                                                                              sweeper):
    artifact = tmp_path / f"{document.stem}.html"
    artifact.write_text(artifact_html(json.loads(document.read_text(encoding="utf-8"))), encoding="utf-8")
    swept = sweeper.sweep(artifact, sweep_timeout(request), viewports=(viewport,))
    assert swept.problems() == [], "\n".join(swept.problems())
    assert all(swept.chapters.values()), f"test/chapter_sweep.py: {document.name} showed no chapter: {swept.chapters}"


# A page that locks its main thread once its one chapter is opened.
LOCKING = """<!doctype html><html data-artifact-status="ready"><body><div data-chapter-scroll></div><script>
globalThis.obsArtifact = {navigationChapters: () => [{slug: "locked"}],
                          activateChapter: () => { for (;;) {} }, whenChapterReady: async () => {}};
</script></body></html>"""
# A page with no chapter that reports, as a console error, the viewport and device scale it was opened at.
REPORTING = """<!doctype html><html data-artifact-status="ready"><head><meta name="viewport" content="width=device-width">
</head><body><script>
globalThis.obsArtifact = {navigationChapters: () => []};
console.error(`${innerWidth} px at device scale ${devicePixelRatio}`);
</script></body></html>"""


@pytest.mark.browser
def test_a_page_that_locks_fails_its_sweep_naming_the_chapter_and_the_next_sweep_runs_in_a_fresh_child(tmp_path,
                                                                                                         request):
    # The locked step is bounded by STALL times the page's own opening time, not by a number of
    # seconds a busy host can use up before the page has even opened.
    locking, reporting = tmp_path / "locking.html", tmp_path / "reporting.html"
    locking.write_text(LOCKING, encoding="utf-8")
    reporting.write_text(REPORTING, encoding="utf-8")
    kept = Sweeper()
    try:
        swept = kept.sweep(locking, sweep_timeout(request), motions=("reduce",), viewports=("phone",), stall=STALL)
        after = kept.sweep(reporting, sweep_timeout(request), motions=("reduce",), viewports=("desktop",))
    finally:
        kept.close()
    assert swept.chapters == {("phone", "reduce"): []}
    assert swept.failure.startswith("the page stopped answering at chapter 'locked' "
                                    f"(phone, prefers-reduced-motion: reduce), opening it: no answer within {STALL:g} "
                                    "times the page's opening time")
    assert (after.failure, after.errors) == (None, [("desktop", "reduce", "1280 px at device scale 1")])


@pytest.mark.browser
def test_each_viewport_is_swept_at_its_width_and_the_phone_at_device_scale_1(tmp_path, sweeper):
    artifact = tmp_path / "reporting.html"
    artifact.write_text(REPORTING, encoding="utf-8")
    swept = {viewport: sweeper.sweep(artifact, 20, motions=("reduce",), viewports=(viewport,)) for viewport in VIEWPORTS}
    assert {viewport: result.errors for viewport, result in swept.items()} == {
        "desktop": [("desktop", "reduce", "1280 px at device scale 1")],
        "phone": [("phone", "reduce", "390 px at device scale 1")]}


def test_compare_counts_the_differing_pixels(tmp_path):
    from PIL import Image

    for name, colour in (("before", "white"), ("after", "white")):
        (tmp_path / name).mkdir()
        Image.new("RGB", (4, 3), colour).save(tmp_path / name / "same.png")
        image = Image.new("RGB", (4, 3), "white")
        if name == "after":
            image.putpixel((1, 1), (0, 0, 0))
        image.save(tmp_path / name / "one.png")
    Image.new("RGB", (1, 1)).save(tmp_path / "after" / "new.png")
    assert compare(tmp_path / "before", tmp_path / "after") == {"new.png": None, "one.png": 1, "same.png": 0}
