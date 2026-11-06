"""In the complete suite a module's tests share one xdist worker (`--dist loadgroup`), so its module
and run-wide fixtures are built, or waited for, once per run rather than once per worker.

Reader: whoever changes how this adapter's tests are spread over the suite's workers.
"""


def test_this_module_runs_in_its_own_modules_group(request) -> None:
    """xdist names a test's group after its id ("…::test@group") when it collects; the module's
    group must be on the test by then. In a run without loadgroup workers the id has no group."""
    distributed = bool(request.config.getoption("loadgroup", False))
    nodeid, _, group = request.node.nodeid.partition("@")

    assert group == (nodeid.split("::")[0] if distributed else "")
