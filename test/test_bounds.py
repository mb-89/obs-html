"""No test can hang the suite: each of the adapter's tests has its tier's timeout (the core's test/bounds.py)."""
from conftest import bounds


def test_every_test_has_its_tier_timeout(request) -> None:
    items = request.session.items
    assert items
    wrong = [item.nodeid for item in items
             if [mark.args[0] for mark in item.iter_markers("timeout")][:1] != [bounds.TIMEOUTS[bounds.tier(item)]]]
    assert wrong == []
