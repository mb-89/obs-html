"""The branch cleanup (.github/workflows/clean-branches.yml, README "Branch cleanup"): a closed pull
request's head branch goes, and a run by hand removes every branch whose pull request and work issue
are closed, unless a guard holds the branch; each outcome is one line of the run's summary.

Reader: whoever changes which branches obs-html's workflow deletes.

The workflow's script runs here against a fake of GitHub's REST API, the one door it calls.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "clean-branches.yml"
REPOSITORY = "alice/project"
SHA = "b" * 40
MAIN = "c" * 40


def loaded() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    data["on"] = data.pop(True)
    return data


def script() -> str:
    (step,) = loaded()["jobs"]["clean"]["steps"]
    return step["run"]


class Response(io.BytesIO):
    """One answer of urlopen: its status and body."""

    def __init__(self, status: int, body: bytes) -> None:
        super().__init__(body)
        self.status = status


def pull(number: int, branch: str, state: str = "closed", sha: str = SHA, body: str = "",
         head: str = REPOSITORY) -> dict:
    """A pull request as the REST API answers it."""
    return {"number": number, "state": state, "body": body,
            "head": {"ref": branch, "sha": sha, "repo": {"full_name": head} if head else None}}


class GitHub:
    """GitHub's REST API as the script sees it: the repository's branches, its pull requests of
    every state, its issues by number with their state, and every call, with the deletes."""

    def __init__(self, branches: dict[str, str], pulls: list[dict] = (), issues: dict[int, str] = None,
                 default: str = "main", page_size: int = 100) -> None:
        self.branches, self.pulls, self.default = dict(branches), list(pulls), default
        self.issues = issues or {}
        self.page_size = page_size
        self.calls: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def answer(self, status: int, body: object = None) -> Response:
        return Response(status, json.dumps(body).encode() if body is not None else b"")

    def missing(self, request: urllib.request.Request, code: int = 404):
        raise urllib.error.HTTPError(request.full_url, code, "Not Found", {}, None)

    def urlopen(self, request: urllib.request.Request):
        url = urllib.parse.urlsplit(request.full_url)
        path, method = urllib.parse.unquote(url.path), request.get_method()
        query = urllib.parse.parse_qs(url.query)
        self.calls.append((method, path))
        assert url.netloc == "api.example.com"
        assert request.get_header("Authorization") == "Bearer token"
        prefix = f"/repos/{REPOSITORY}"
        if method == "GET" and path == prefix:
            return self.answer(200, {"default_branch": self.default})
        if method == "GET" and path == f"{prefix}/branches":
            names = sorted(self.branches)
            page, size = int(query.get("page", ["1"])[0]), int(query["per_page"][0])
            size = min(size, self.page_size)
            chunk = names[(page - 1) * size:page * size]
            return self.answer(200, [{"name": name, "commit": {"sha": self.branches[name]}} for name in chunk])
        if method == "GET" and path == f"{prefix}/pulls":
            owner, branch = query["head"][0].split(":", 1)
            assert owner == REPOSITORY.split("/")[0]
            state = query["state"][0]
            found = [item for item in self.pulls if item["head"]["ref"] == branch
                     and (state == "all" or item["state"] == state)]
            return self.answer(200, sorted(found, key=lambda item: -item["number"]))
        if method == "GET" and path.startswith(f"{prefix}/pulls/"):
            number = int(path.removeprefix(f"{prefix}/pulls/"))
            found = [item for item in self.pulls if item["number"] == number]
            return self.answer(200, found[0]) if found else self.missing(request)
        if method == "GET" and path.startswith(f"{prefix}/issues/"):
            number = int(path.removeprefix(f"{prefix}/issues/"))
            if number in self.issues:
                return self.answer(200, {"number": number, "state": self.issues[number]})
            if any(item["number"] == number for item in self.pulls):
                return self.answer(200, {"number": number, "state": "closed", "pull_request": {}})
            return self.missing(request)
        if method == "GET" and path.startswith(f"{prefix}/git/ref/heads/"):
            branch = path.removeprefix(f"{prefix}/git/ref/heads/")
            if branch not in self.branches:
                return self.missing(request)
            return self.answer(200, {"object": {"sha": self.branches[branch]}})
        if method == "DELETE" and path.startswith(f"{prefix}/git/refs/heads/"):
            branch = path.removeprefix(f"{prefix}/git/refs/heads/")
            if branch not in self.branches:
                return self.missing(request, 422)
            del self.branches[branch]
            self.deleted.append(branch)
            return self.answer(204)
        raise AssertionError(f"unexpected call {method} {path}")


def run(github: GitHub, tmp_path: Path, event: str, **env: str) -> str:
    """Run the workflow's script on `event` with the step's `env`; its summary."""
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(urllib.request, "urlopen", github.urlopen)
        for name, value in {"GITHUB_TOKEN": "token", "GITHUB_REPOSITORY": REPOSITORY,
                            "GITHUB_API_URL": "https://api.example.com", "GITHUB_EVENT_NAME": event,
                            "GITHUB_STEP_SUMMARY": str(summary), **env}.items():
            patch.setenv(name, value)
        try:
            exec(compile(script(), str(WORKFLOW), "exec"), {"__name__": "__main__"})
        except SystemExit as exited:
            assert exited.code is None, exited.code
    return summary.read_text(encoding="utf-8")


def closed(github: GitHub, tmp_path: Path, branch: str = "topic", number: int = 7,
           head: str = REPOSITORY, sha: str = SHA) -> str:
    """The run on the close of pull request `number`."""
    return run(github, tmp_path, "pull_request", NUMBER=str(number), HEAD_REF=branch, HEAD_SHA=sha,
               HEAD_REPOSITORY=head)


def by_hand(github: GitHub, tmp_path: Path, dry_run: str = "false") -> str:
    """The run by hand."""
    return run(github, tmp_path, "workflow_dispatch", DRY_RUN=dry_run)


# Requirement 1: on pull request close, the head branch is deleted, except `main`.

def test_a_closed_pull_request_s_branch_is_deleted(tmp_path):
    github = GitHub({"topic": SHA, "main": MAIN})
    assert closed(github, tmp_path) == f"Branch cleanup: deleted topic of #7 at {SHA[:12]}.\n"
    assert github.deleted == ["topic"]
    assert github.branches == {"main": MAIN}


@pytest.mark.parametrize("branch", ["main", "trunk", "ccr-session", "claude/topic"])
def test_main_and_the_default_and_session_branches_are_kept_on_close(tmp_path, branch):
    github = GitHub({branch: SHA}, default="trunk")
    assert closed(github, tmp_path, branch=branch) == (
        f"Branch cleanup: kept {branch} of #7: it is a protected branch.\n")
    assert github.deleted == []


def test_a_fork_s_branch_is_kept_without_a_call(tmp_path):
    github = GitHub({"topic": SHA})
    assert closed(github, tmp_path, head="mallory/project") == (
        f"Branch cleanup: kept topic of #7: its head repository mallory/project is not {REPOSITORY}.\n")
    assert github.calls == []


def test_a_branch_another_open_pull_request_heads_is_kept_on_close(tmp_path):
    github = GitHub({"topic": SHA}, [pull(7, "topic"), pull(9, "topic", state="open")])
    assert closed(github, tmp_path) == (
        "Branch cleanup: kept topic of #7: it is the head of the open pull request #9.\n")
    assert github.deleted == []


def test_a_branch_that_moved_since_the_pull_request_s_head_is_kept_on_close(tmp_path):
    github = GitHub({"topic": "d" * 40})
    assert closed(github, tmp_path) == (
        f"Branch cleanup: kept topic of #7: it moved to {'d' * 12} since the pull request's head "
        f"{SHA[:12]}.\n")
    assert github.deleted == []


def test_a_branch_already_gone_on_close_is_a_success_with_a_note(tmp_path):
    github = GitHub({})
    assert closed(github, tmp_path) == "Branch cleanup: topic of #7 is already gone.\n"
    assert not any(method == "DELETE" for method, _ in github.calls)


# Requirement 2: a run by hand deletes every branch whose pull request is closed and whose work issue
# is closed, and lists them.

def test_the_run_by_hand_deletes_each_branch_of_a_closed_pull_request_and_work_issue(tmp_path):
    github = GitHub({"main": MAIN, "one": SHA, "two": "e" * 40},
                    [pull(5, "one", body="Refs https://github.com/alice/project/issues/4\n"),
                     pull(9, "two", sha="e" * 40, body="Fixes #8")],
                    issues={4: "closed", 8: "closed"})
    assert by_hand(github, tmp_path) == (
        "Branch cleanup by hand: deleted 2 branches, kept 1.\n\n"
        f"- deleted one of #5 at {SHA[:12]}: its work issue #4 is closed\n"
        f"- deleted two of #9 at {'e' * 12}: its work issue #8 is closed\n"
        "- kept main: it is a protected branch\n")
    assert github.deleted == ["one", "two"]
    assert github.branches == {"main": MAIN}


def test_a_landing_branch_follows_its_work_pull_request_to_the_work_issue(tmp_path):
    github = GitHub({"land/topic": SHA, "topic": "e" * 40},
                    [pull(6, "topic", sha="e" * 40, body="Refs #4"), pull(7, "land/topic", body="Lands #6")],
                    issues={4: "closed"})
    report = by_hand(github, tmp_path)
    assert f"- deleted land/topic of #7 at {SHA[:12]}: its work issue #4 is closed\n" in report
    assert sorted(github.deleted) == ["land/topic", "topic"]


def test_the_run_by_hand_keeps_what_a_guard_holds_and_says_why(tmp_path):
    github = GitHub({"main": MAIN, "trunk": MAIN, "ccr-x": SHA, "open": SHA, "unnamed": SHA,
                     "issue-open": SHA, "moved": "d" * 40, "no-pull": SHA, "fork": SHA},
                    [pull(1, "open", body="Refs #4"), pull(2, "open", state="open", body="Refs #4"),
                     pull(3, "unnamed", body="no reference"), pull(5, "issue-open", body="Refs #4\nRefs #6"),
                     pull(7, "moved", body="Refs #4"), pull(8, "fork", head="mallory/project", body="Refs #4")],
                    issues={4: "closed", 6: "open"}, default="trunk")
    assert by_hand(github, tmp_path) == (
        "Branch cleanup by hand: deleted 0 branches, kept 9.\n\n"
        "- kept ccr-x: it is a protected branch\n"
        "- kept fork: it has no closed pull request from this repository\n"
        "- kept issue-open: its work issue #6 of #5 is open\n"
        "- kept main: it is a protected branch\n"
        f"- kept moved: it moved to {'d' * 12} since the head {SHA[:12]} of #7\n"
        "- kept no-pull: it has no closed pull request from this repository\n"
        "- kept open: it is the head of the open pull request #2\n"
        "- kept trunk: it is a protected branch\n"
        "- kept unnamed: #3 names no work issue\n")
    assert github.deleted == []
    assert not any(method == "DELETE" for method, _ in github.calls)


def test_the_newest_closed_pull_request_of_a_branch_decides(tmp_path):
    github = GitHub({"topic": "e" * 40},
                    [pull(3, "topic", body="Refs #2"), pull(9, "topic", sha="e" * 40, body="Refs #8")],
                    issues={2: "closed", 8: "open"})
    assert "- kept topic: its work issue #8 of #9 is open\n" in by_hand(github, tmp_path)
    assert github.deleted == []


def test_the_run_by_hand_reads_every_page_of_branches(tmp_path):
    names = {f"b{n}": SHA for n in range(5)}
    github = GitHub({"main": MAIN, **names}, [pull(10 + n, f"b{n}", body="Refs #1") for n in range(5)],
                    issues={1: "closed"}, page_size=2)
    report = by_hand(github, tmp_path)
    assert report.startswith("Branch cleanup by hand: deleted 5 branches, kept 1.\n")
    assert github.branches == {"main": MAIN}


def test_a_dry_run_by_hand_lists_what_it_would_delete_and_deletes_nothing(tmp_path):
    github = GitHub({"main": MAIN, "one": SHA}, [pull(5, "one", body="Refs #4")], issues={4: "closed"})
    assert by_hand(github, tmp_path, dry_run="true") == (
        "Branch cleanup by hand, dry run: would delete 1 branch, kept 1.\n\n"
        f"- would delete one of #5 at {SHA[:12]}: its work issue #4 is closed\n"
        "- kept main: it is a protected branch\n")
    assert github.deleted == [] and not any(method == "DELETE" for method, _ in github.calls)


# The workflow's triggers and permissions, and requirement 3: the README says what it deletes and how
# to switch it off.

def test_the_workflow_runs_on_a_closed_pull_request_and_by_hand_only():
    data = loaded()
    assert set(data["on"]) == {"pull_request", "workflow_dispatch"}
    assert data["on"]["pull_request"] == {"types": ["closed"]}
    assert set(data["on"]["workflow_dispatch"]["inputs"]) == {"dry_run"}
    assert data["permissions"] == {"contents": "write", "pull-requests": "read", "issues": "read"}


def test_the_workflow_is_owned_here_not_a_copy_se_regenerates():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert not text.startswith("# se-workflows:")
    assert WORKFLOW.name != "branch-cleanup.yml"

