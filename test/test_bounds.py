"""No test can hang the suite: each of the adapter's tests has its tier's timeout (the core's test/bounds.py)."""
from conftest import bounds


def test_every_test_has_its_tier_timeout(request) -> None:
    items = request.session.items
    assert items
    wrong = [item.nodeid for item in items
             if [mark.args[0] for mark in item.iter_markers("timeout")][:1] != [bounds.TIMEOUTS[bounds.tier(item)]]]
    assert wrong == []


def test_each_test_names_its_tier_in_its_report(request) -> None:
    assert (bounds.TIER_PROPERTY, bounds.tier(request.node)) in request.node.user_properties


# The fixtures by which a test opens a page in Chromium, and those that build a whole Document or
# package for it, which put it in the browser and build tiers by the tier rule (the core's
# spec/design_input/quality.md, Testing boundaries).
OPENS_A_PAGE = "worker_playwright"
BUILDS = {"installed_wheels", "rebuilt"}
BUILD_MODULES = {"test/test_spec_archive_rebuild.py"}


def test_a_test_that_opens_a_page_or_builds_a_whole_document_has_that_tier(request) -> None:
    """A test outside its tier loosens the tier's timeout for every other test of it (bounds.py)."""
    order = list(bounds.TIMEOUTS)
    items = request.session.items
    pages = [item.nodeid for item in items if OPENS_A_PAGE in getattr(item, "fixturenames", ())
             and order.index(bounds.tier(item)) < order.index("browser")]
    builds = [item.nodeid for item in items if (BUILDS & set(getattr(item, "fixturenames", ()))
                                                or item.nodeid.split("::")[0] in BUILD_MODULES)
              and bounds.tier(item) != "build"]
    assert (pages, builds) == ([], [])
