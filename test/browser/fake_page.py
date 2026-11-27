"""The fake browser's facade: a Page-like object over happy-dom in Node (browser-door.md, The fake browser).

Reader: whoever writes or moves a logic test onto the fake browser, or changes what the facade offers.

test/conftest.py's ``fake_page`` fixture hands a test a :class:`FakePage`, served by the test
worker's one Node process, test/browser/fake-browser.cjs. The facade has what the design lists:
``goto``, ``evaluate``, ``wait_for_function``, ``keyboard.press``, ``mouse``,
``set_viewport_size`` (it reopens the page), ``emulate_media`` and ``set_java_script_enabled``; and ``locator`` with CSS
selectors, its ``first``, ``nth`` and ``filter`` (``has_text``, ``has``), its actions and reads, and
``expect`` for its retried assertions; ``expect_download`` for a file the page downloads and
``expect_popup`` for a new page a link opens; and the browser door's ``replay``, ``reach`` and ``asked``,
through which test/browser/door.py opens a state with its recording and lists what the page asked. Waits and retries run on the page's own clock in the host,
never on wall time. A method the facade lacks fails with :class:`FakeBrowserUnsupported`, naming
the method and the design note; Playwright's text and role selectors do not exist here, so a test
that moves writes them as CSS and a text filter.

Each page error, console message and request reaches the listeners a test added with ``on``, as
Playwright delivers them; a request the page made that leaves the machine is recorded with
test/network_guard.py, which fails the test.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

import network_guard

NOTE = "test/browser/browser-door.md"
HOST = Path(__file__).with_name("fake-browser.cjs")
OWNER = "test/browser/fake_page.py"
# Playwright's defaults: an action's and a wait's timeout, and an assertion's, here on the page's clock.
DEFAULT_TIMEOUT_MS = 30_000
EXPECT_TIMEOUT_MS = 5_000
DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


class FakeBrowserError(Exception):
    """The fake browser refused or failed a request; the message names the host and the remedy."""


class FakeTimeoutError(FakeBrowserError):
    """A wait or an action did not complete within its timeout on the page's clock."""


class FakeBrowserUnsupported(AttributeError):
    """The facade has no such method; the message names it and the design note."""


def unsupported(owner: str, name: str) -> FakeBrowserUnsupported:
    return FakeBrowserUnsupported(
        f"{OWNER}: the fake browser's {owner} has no {name}; it offers what {NOTE} lists under The fake "
        "browser. Remedy: write the step with what the facade has, or keep the test on a real browser and say "
        "why in the note's Classification.")


class PageError(Exception):
    """An uncaught error in the page, as Playwright's ``pageerror`` hands it over."""

    def __init__(self, name: str, message: str, stack: str = "") -> None:
        super().__init__(message)
        self.name = name
        self.message = message
        self.stack = stack


class ConsoleMessage:
    """A console message of the page, as Playwright's ``console`` hands it over."""

    def __init__(self, type_: str, text: str) -> None:
        self.type = type_
        self.text = text

    def __repr__(self) -> str:
        return f"ConsoleMessage({self.type!r}, {self.text!r})"


class Request:
    """A request the page made through happy-dom's fetch, as Playwright's ``request`` hands it over."""

    def __init__(self, url: str) -> None:
        self.url = url

    def __repr__(self) -> str:
        return f"Request({self.url!r})"


class Dialog:
    """A modal dialog the page opened, as Playwright's ``on("dialog")`` hands it: the fake has already
    dismissed it, so accept and dismiss do nothing."""

    def __init__(self, type_: str, message: str) -> None:
        self.type, self.message = type_, message

    def accept(self, prompt_text: str | None = None) -> None:
        pass

    def dismiss(self) -> None:
        pass


class Download:
    """A file the page downloaded, as Playwright's ``download`` hands it over."""

    def __init__(self, filename: str, url: str, data: bytes) -> None:
        self.suggested_filename = filename
        self.url = url
        self._data = data

    def save_as(self, path) -> None:
        Path(path).write_bytes(self._data)


class ExpectedDownload:
    """What ``with page.expect_download() as info`` binds: ``info.value`` is the download once the
    block has ended."""

    def __init__(self, page: FakePage, timeout: float) -> None:
        self._page = page
        self._timeout = timeout
        self._after = 0
        self._value: Download | None = None

    def __enter__(self) -> ExpectedDownload:
        self._after = self._page._call("downloads")
        return self

    def __exit__(self, kind, error, trace) -> None:
        if kind is None:
            done = self._page._call("wait_for_download", after=self._after, timeout=self._timeout)
            self._value = Download(done["filename"], done["url"], base64.b64decode(done["data"]))

    @property
    def value(self) -> Download:
        if self._value is None:
            raise FakeBrowserError(f"{OWNER}: expect_download's value is there once its with block has ended")
        return self._value


class ExpectedPopup:
    """What ``with page.expect_popup() as info`` binds: ``info.value`` is the new page a link of the
    page opened within the block, a fake page of its own at the link's URL, once the block has ended."""

    def __init__(self, page: FakePage, timeout: float) -> None:
        self._page = page
        self._timeout = timeout
        self._after = 0
        self._value: FakePage | None = None

    def __enter__(self) -> ExpectedPopup:
        self._after = self._page._call("popups")
        return self

    def __exit__(self, kind, error, trace) -> None:
        if kind is None:
            url = self._page._call("wait_for_popup", after=self._after, timeout=self._timeout)
            self._value = self._page._browser.new_page(self._page.viewport_size)
            self._value.goto(url, timeout=self._timeout)

    @property
    def value(self) -> FakePage:
        if self._value is None:
            raise FakeBrowserError(f"{OWNER}: expect_popup's value is there once its with block has ended")
        return self._value


# The page events a test may listen to with ``on`` and ``once``.
EVENTS = ("pageerror", "console", "request", "dialog")


class FakeBrowser:
    """The test worker's Node process that hosts happy-dom, started on first use."""

    def __init__(self) -> None:
        self._process = None
        self._stderr = None
        self._serial = 0
        self._lock = threading.Lock()
        self._pages: dict[int, FakePage] = {}

    def _start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        node = "node"
        self._stderr = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
        try:
            self._process = subprocess.Popen([node, str(HOST)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             stderr=self._stderr, text=True, encoding="utf-8", bufsize=1,
                                             env={**os.environ, "NODE_NO_WARNINGS": "1"})
        except FileNotFoundError as error:
            raise FakeBrowserError(f"{OWNER}: node is not on PATH, so the fake browser {HOST.name} cannot start. "
                                   "Remedy: install Node.js 22 or newer.") from error

    def call(self, op: str, page: FakePage | None = None, **fields):
        """Send one request and return its value; the page's events go to its listeners first."""
        with self._lock:
            self._start()
            self._serial += 1
            request = {"id": self._serial, "op": op, **fields}
            if page is not None:
                request["page"] = page.id
            try:
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()
                line = self._process.stdout.readline()
            except (BrokenPipeError, OSError):
                line = ""
            if not line:
                self._stderr.seek(0)
                said = self._stderr.read().strip()
                self._process = None
                raise FakeBrowserError(f"{OWNER}: the fake browser {HOST.name} ended while it answered {op}"
                                       f"{': ' + said if said else ''}. Remedy: run `npm --prefix test/browser ci`; "
                                       "where it ends again, run the test alone and read the host's message.")
            reply = json.loads(line)
        if page is not None:
            page._dispatch(reply.get("events", []))
        if not reply["ok"]:
            error = reply["error"]
            if error.get("kind") == "timeout":
                raise FakeTimeoutError(error["message"])
            if error.get("kind") == "unsupported":
                raise FakeBrowserUnsupported(error["message"])
            if error.get("kind") == "pageerror":
                raise FakeBrowserError(f"{error.get('name', 'Error')}: {error['message']}\n{error.get('stack', '')}".rstrip())
            raise FakeBrowserError(error["message"])
        return reply.get("value")

    def new_page(self, viewport: dict | None = None, color_scheme: str | None = None) -> FakePage:
        viewport = viewport or DEFAULT_VIEWPORT
        media = {"prefersColorScheme": color_scheme} if color_scheme else {}
        identifier = self.call("new_page", viewport=[viewport["width"], viewport["height"]], media=media)
        page = FakePage(self, identifier, viewport)
        self._pages[identifier] = page
        return page

    def close(self) -> None:
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            process.stdin.close()
            process.wait()
        if process is not None:
            process.stdout.close()
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None


class Keyboard:
    def __init__(self, page: FakePage) -> None:
        self._page = page

    def press(self, key: str, delay: float | None = None) -> None:
        self._page._call("keyboard", action="press", key=key)

    def down(self, key: str) -> None:
        self._page._call("keyboard", action="down", key=key)

    def up(self, key: str) -> None:
        self._page._call("keyboard", action="up", key=key)

    def type(self, text: str, delay: float | None = None) -> None:
        self._page._call("keyboard", action="type", text=text)

    def insert_text(self, text: str) -> None:
        self._page._call("keyboard", action="insert_text", text=text)

    def __getattr__(self, name: str):
        raise unsupported("keyboard", name)


class Mouse:
    """The pointer at a point: its target is the element whose box holds it (the door's answers)."""

    def __init__(self, page: FakePage) -> None:
        self._page = page

    def move(self, x: float, y: float, steps: int = 1) -> None:
        self._page._call("mouse", action="move", x=x, y=y)

    def down(self, button: str = "left", click_count: int = 1) -> None:
        self._page._call("mouse", action="down", button=button)

    def up(self, button: str = "left", click_count: int = 1) -> None:
        self._page._call("mouse", action="up", button=button)

    def click(self, x: float, y: float, button: str = "left", click_count: int = 1, delay: float | None = None) -> None:
        self._page._call("mouse", action="click", x=x, y=y, button=button, clickCount=click_count)

    def dblclick(self, x: float, y: float, button: str = "left", delay: float | None = None) -> None:
        self._page._call("mouse", action="dblclick", x=x, y=y, button=button)

    def wheel(self, delta_x: float, delta_y: float) -> None:
        self._page._call("mouse", action="wheel", deltaX=delta_x, deltaY=delta_y)

    def __getattr__(self, name: str):
        raise unsupported("mouse", name)


def _text(value):
    """A text argument as the host reads it: a string, or a regular expression's pattern and flags."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, re.Pattern):
        return {"regex": value.pattern, "flags": "i" if value.flags & re.IGNORECASE else ""}
    raise FakeBrowserError(f"{OWNER}: a text filter is a string or a compiled regular expression, not {value!r}")


def _input_files(files) -> list[dict]:
    """Files for set_input_files, as the host reads them: a path, or a list of paths."""
    import mimetypes

    paths = [files] if isinstance(files, (str, os.PathLike)) else list(files)
    return [{"name": Path(path).name, "mimeType": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
             "data": base64.b64encode(Path(path).read_bytes()).decode("ascii")} for path in paths]


class FakeLocator:
    """A CSS locator over the fake page, resolved anew by every call, as Playwright's locators are."""

    def __init__(self, page: FakePage, chain: list[dict]) -> None:
        self._page = page
        self._chain = chain

    def __repr__(self) -> str:
        return f"<FakeLocator {self._chain!r}>"

    def _with(self, *steps: dict) -> FakeLocator:
        return FakeLocator(self._page, [*self._chain, *steps])

    @staticmethod
    def _filter(has_text=None, has_not_text=None, has=None, has_not=None, visible=None) -> list[dict]:
        rule = {}
        if has_text is not None:
            rule["hasText"] = _text(has_text)
        if has_not_text is not None:
            rule["hasNotText"] = _text(has_not_text)
        if has is not None:
            rule["has"] = has._chain
        if has_not is not None:
            rule["hasNot"] = has_not._chain
        if visible is not None:
            rule["visible"] = visible
        return [{"filter": rule}] if rule else []

    def locator(self, selector: str, has_text=None, has_not_text=None, has=None, has_not=None) -> FakeLocator:
        return self._with({"css": selector}, *self._filter(has_text, has_not_text, has, has_not))

    def filter(self, has_text=None, has_not_text=None, has=None, has_not=None, visible=None) -> FakeLocator:
        return self._with(*self._filter(has_text, has_not_text, has, has_not, visible))

    @property
    def first(self) -> FakeLocator:
        return self._with({"nth": 0})

    @property
    def last(self) -> FakeLocator:
        return self._with({"nth": -1})

    def nth(self, index: int) -> FakeLocator:
        return self._with({"nth": index})

    def count(self) -> int:
        return self._page._call("count", chain=self._chain)

    def all(self) -> list[FakeLocator]:
        return [self.nth(index) for index in range(self.count())]

    def _act(self, action: str, timeout: float | None = None, **fields) -> None:
        self._page._call("act", chain=self._chain, action=action, timeout=self._page._timeout(timeout), **fields)

    def click(self, timeout: float | None = None, button: str = "left", click_count: int = 1, modifiers=None,
              **_) -> None:
        self._act("click", timeout, button=button, clickCount=click_count, modifiers=list(modifiers or []))

    def dblclick(self, timeout: float | None = None, **_) -> None:
        self._act("dblclick", timeout)

    def tap(self, timeout: float | None = None, **_) -> None:
        self._act("tap", timeout)

    def check(self, timeout: float | None = None, **_) -> None:
        self._act("check", timeout)

    def uncheck(self, timeout: float | None = None, **_) -> None:
        self._act("uncheck", timeout)

    def hover(self, timeout: float | None = None, **_) -> None:
        self._act("hover", timeout)

    def fill(self, value: str, timeout: float | None = None, **_) -> None:
        self._act("fill", timeout, value=value)

    def press(self, key: str, timeout: float | None = None, **_) -> None:
        self._act("press", timeout, key=key)

    def focus(self, timeout: float | None = None) -> None:
        self._act("focus", timeout)

    def blur(self, timeout: float | None = None) -> None:
        self._act("blur", timeout)

    def dispatch_event(self, type: str, event_init=None, timeout: float | None = None) -> None:
        self._act("dispatch_event", timeout, type=type)

    def scroll_into_view_if_needed(self, timeout: float | None = None) -> None:
        self._act("scroll_into_view_if_needed", timeout)

    def select_option(self, value=None, label=None, timeout: float | None = None, **_) -> None:
        """Select the options whose value, else whose label, is given, and fire input and change."""
        chosen = value if value is not None else label
        self._act("select_option", timeout, values=list(chosen) if isinstance(chosen, (list, tuple)) else [chosen])

    def set_input_files(self, files, timeout: float | None = None, **_) -> None:
        """Hand a file input the files at these paths, and fire input and change."""
        self._act("set_input_files", timeout, files=_input_files(files))

    def _read(self, what: str, timeout: float | None = None, **fields):
        return self._page._call("read", chain=self._chain, what=what, timeout=self._page._timeout(timeout), **fields)

    def text_content(self, timeout: float | None = None) -> str | None:
        return self._read("text_content", timeout)

    def inner_text(self, timeout: float | None = None) -> str:
        return self._read("inner_text", timeout)

    def inner_html(self, timeout: float | None = None) -> str:
        return self._read("inner_html", timeout)

    def get_attribute(self, name: str, timeout: float | None = None) -> str | None:
        return self._read("get_attribute", timeout, name=name)

    def input_value(self, timeout: float | None = None) -> str:
        return self._read("input_value", timeout)

    def is_visible(self, timeout: float | None = None) -> bool:
        return self._read("is_visible")

    def is_hidden(self, timeout: float | None = None) -> bool:
        return self._read("is_hidden")

    def is_enabled(self, timeout: float | None = None) -> bool:
        return self._read("is_enabled", timeout)

    def is_disabled(self, timeout: float | None = None) -> bool:
        return self._read("is_disabled", timeout)

    def is_checked(self, timeout: float | None = None) -> bool:
        return self._read("is_checked", timeout)

    def bounding_box(self, timeout: float | None = None):
        return self._read("bounding_box", timeout)

    def all_text_contents(self) -> list[str]:
        return self.evaluate_all("elements => elements.map(element => element.textContent)")

    def all_inner_texts(self) -> list[str]:
        return self.evaluate_all("elements => elements.map(element => element.innerText)")

    def evaluate(self, expression: str, arg=None, timeout: float | None = None):
        return self._page._call("evaluate", chain=self._chain, expression=expression, arg=arg,
                                timeout=self._page._timeout(timeout))

    def evaluate_all(self, expression: str, arg=None):
        return self._page._call("evaluate", chain=self._chain, all=True, expression=expression, arg=arg)

    def wait_for(self, state: str = "visible", timeout: float | None = None) -> None:
        self._page._call("wait_for", chain=self._chain, state=state, timeout=self._page._timeout(timeout))

    def __getattr__(self, name: str):
        raise unsupported("locator", name)


class FakePage:
    """A page of the fake browser: one happy-dom window at a time, reopened by goto and set_viewport_size."""

    def __init__(self, browser: FakeBrowser, identifier: int, viewport: dict) -> None:
        self._browser = browser
        self.id = identifier
        self._viewport = dict(viewport)
        self._listeners: dict[str, list] = {}
        self._default_timeout = DEFAULT_TIMEOUT_MS
        self._closed = False
        self.keyboard = Keyboard(self)
        self.mouse = Mouse(self)

    def _call(self, op: str, **fields):
        if self._closed:
            raise FakeBrowserError(f"{OWNER}: the page is closed; {op} needs an open one")
        return self._browser.call(op, self, **fields)

    def _timeout(self, timeout: float | None) -> float:
        return self._default_timeout if timeout is None else timeout

    def _dispatch(self, events: list[dict]) -> None:
        for event in events:
            if event["type"] == "network":
                network_guard.refused(event["host"], event["port"], f"the fake page's request for {event['url']}")
            elif event["type"] == "pageerror":
                self._emit("pageerror", PageError(event["name"], event["message"], event.get("stack", "")))
            elif event["type"] == "console":
                self._emit("console", ConsoleMessage(event["level"], event["text"]))
            elif event["type"] == "request":
                self._emit("request", Request(event["url"]))
            elif event["type"] == "dialog":
                self._emit("dialog", Dialog(event["kind"], event["message"]))

    def _emit(self, name: str, value) -> None:
        for listener, once in list(self._listeners.get(name, [])):
            if once:
                self._listeners[name].remove((listener, once))
            listener(value)

    def on(self, event: str, listener) -> None:
        if event not in EVENTS:
            raise unsupported("page", f"on({event!r})")
        self._listeners.setdefault(event, []).append((listener, False))

    def once(self, event: str, listener) -> None:
        if event not in EVENTS:
            raise unsupported("page", f"once({event!r})")
        self._listeners.setdefault(event, []).append((listener, True))

    def remove_listener(self, event: str, listener) -> None:
        self._listeners[event] = [entry for entry in self._listeners.get(event, []) if entry[0] is not listener]

    def goto(self, url: str, timeout: float | None = None, wait_until: str | None = None, **_) -> None:
        self._call("goto", url=url, timeout=self._timeout(timeout))

    def reload(self, timeout: float | None = None, **_) -> None:
        self.goto(self.url, timeout)

    def evaluate(self, expression: str, arg=None):
        return self._call("evaluate", expression=expression, arg=arg)

    def wait_for_function(self, expression: str, arg=None, timeout: float | None = None, polling=None):
        return self._call("wait_for_function", expression=expression, arg=arg, timeout=self._timeout(timeout))

    def expect_download(self, timeout: float | None = None) -> ExpectedDownload:
        """The file the page downloads within the ``with`` block, a blob: or data: URL a link with a
        ``download`` attribute names; the block's end waits for it on the page's clock."""
        return ExpectedDownload(self, self._timeout(timeout))

    def expect_popup(self, timeout: float | None = None) -> ExpectedPopup:
        """The new page a link with target ``_blank`` opens within the ``with`` block, as Playwright's
        popup; the block's end waits for it on the page's clock and opens it in a fake page of its own."""
        return ExpectedPopup(self, self._timeout(timeout))

    def wait_for_load_state(self, state: str = "load", timeout: float | None = None) -> None:
        """A fake page is loaded once ``goto`` returns, so there is nothing left to wait for."""

    def set_input_files(self, selector: str, files, timeout: float | None = None, **_) -> None:
        self.locator(selector).set_input_files(files, timeout)

    def wait_for_selector(self, selector: str, state: str = "visible", timeout: float | None = None) -> FakeLocator:
        locator = self.locator(selector)
        self._call("wait_for", chain=locator._chain, state=state, strict=False, timeout=self._timeout(timeout))
        return locator.first

    def locator(self, selector: str, has_text=None, has_not_text=None, has=None, has_not=None) -> FakeLocator:
        return FakeLocator(self, []).locator(selector, has_text, has_not_text, has, has_not)

    def set_viewport_size(self, viewport_size: dict) -> None:
        """A new viewport reopens the page at its URL (browser-door.md: the fake opens a page at its
        state's viewport instead of resizing it)."""
        self._viewport = dict(viewport_size)
        self._call("set_viewport_size", viewport=[viewport_size["width"], viewport_size["height"]],
                   timeout=self._default_timeout)

    @property
    def viewport_size(self) -> dict:
        return dict(self._viewport)

    def emulate_media(self, media: str | None = None, color_scheme: str | None = None,
                      reduced_motion: str | None = None, forced_colors: str | None = None, **_) -> None:
        settings = {"mediaType": media, "prefersColorScheme": color_scheme, "prefersReducedMotion": reduced_motion,
                    "forcedColors": forced_colors}
        self._call("emulate_media", media={key: ("screen" if key == "mediaType" and value == "null" else value)
                                           for key, value in settings.items() if value is not None})

    def set_java_script_enabled(self, enabled: bool) -> None:
        """Whether the page runs its own scripts, from the next ``goto`` on: without them it is a frame
        sandboxed without ``allow-scripts``, as Playwright's context option ``java_script_enabled``
        gives. The facade's own evaluate still runs."""
        self._call("set_scripts", enabled=enabled)

    def set_default_timeout(self, timeout: float) -> None:
        self._default_timeout = timeout

    def set_default_navigation_timeout(self, timeout: float) -> None:
        self._default_timeout = timeout

    @property
    def url(self) -> str:
        return self._call("state")["url"]

    def title(self) -> str:
        return self._call("state")["title"]

    def content(self) -> str:
        return self._call("state")["content"]

    def replay(self, recording: dict | None) -> None:
        """Answer from a state's recording from the next ``goto`` on (test/browser/door.py), or, with
        None, from the door's defaults; the page starts at the recording's step 0."""
        self._call("replay", recording=recording)

    def reach(self, step: int) -> None:
        """The test begins the state's step ``step``: the page answers from its recording from now on."""
        self._call("reach", step=step)

    def asked(self) -> dict[int, dict[str, list[str]]]:
        """What the page asked since the last call, by step, expectation and key (browser-door.md,
        Recording and replay): what the recorder measures in Chromium."""
        return {int(step): kinds for step, kinds in self._call("asked").items()}

    def take_defaults(self) -> list[dict]:
        """The default answers the page gave since the last call, each with how often (browser-door.md)."""
        return [] if self._closed else self._call("defaults")

    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if not self._closed:
            self._call("close")
            self._closed = True

    def __getattr__(self, name: str):
        raise unsupported("page", name)


class Assertions:
    """``expect(locator)`` and ``expect(page)``: each assertion is retried on the page's clock until it
    holds or its timeout passes, as Playwright's are."""

    def __init__(self, target, negated: bool = False, timeout: float | None = None) -> None:
        self._target = target
        self._negated = negated
        self._timeout = timeout

    @property
    def not_(self):
        return Assertions(self._target, not self._negated, self._timeout)

    def _check(self, name: str, expected=None, timeout: float | None = None, **fields) -> None:
        page = self._target._page if isinstance(self._target, FakeLocator) else self._target
        chain = self._target._chain if isinstance(self._target, FakeLocator) else None
        if isinstance(expected, (list, tuple)):
            expected = [_text(each) for each in expected]
        elif isinstance(expected, (str, re.Pattern)):
            expected = _text(expected)
        answer = page._call("expect", name=name, chain=chain, expected=expected, negated=self._negated,
                            timeout=timeout if timeout is not None else self._timeout or EXPECT_TIMEOUT_MS, **fields)
        if not answer["pass"]:
            target = f"locator {chain!r}" if chain is not None else "page"
            raise AssertionError(f"{OWNER}: expect({target}).{'not_' if self._negated else ''}{name}"
                                 f"({expected!r}) failed: actual {answer['actual']!r}")

    def to_have_text(self, expected, use_inner_text: bool = False, ignore_case: bool | None = None,
                     timeout: float | None = None) -> None:
        self._check("to_have_text", expected, timeout, useInnerText=use_inner_text, ignoreCase=bool(ignore_case))

    def to_contain_text(self, expected, use_inner_text: bool = False, ignore_case: bool | None = None,
                        timeout: float | None = None) -> None:
        self._check("to_contain_text", expected, timeout, useInnerText=use_inner_text, ignoreCase=bool(ignore_case))

    def to_have_count(self, count: int, timeout: float | None = None) -> None:
        self._check("to_have_count", count, timeout)

    def to_have_attribute(self, name: str, value=None, timeout: float | None = None) -> None:
        self._check("to_have_attribute", value, timeout, attribute=name)

    def to_have_class(self, expected, timeout: float | None = None) -> None:
        self._check("to_have_class", expected, timeout)

    def to_have_value(self, value, timeout: float | None = None) -> None:
        self._check("to_have_value", value, timeout)

    def to_have_id(self, identifier, timeout: float | None = None) -> None:
        self._check("to_have_id", identifier, timeout)

    def to_be_visible(self, visible: bool = True, timeout: float | None = None) -> None:
        self._check("to_be_visible" if visible else "to_be_hidden", None, timeout)

    def to_be_hidden(self, timeout: float | None = None) -> None:
        self._check("to_be_hidden", None, timeout)

    def to_be_attached(self, attached: bool = True, timeout: float | None = None) -> None:
        (self if attached else self.not_)._check("to_be_attached", None, timeout)

    def to_be_checked(self, checked: bool = True, timeout: float | None = None) -> None:
        self._check("to_be_checked", checked, timeout)

    def to_be_enabled(self, enabled: bool = True, timeout: float | None = None) -> None:
        self._check("to_be_enabled" if enabled else "to_be_disabled", None, timeout)

    def to_be_disabled(self, timeout: float | None = None) -> None:
        self._check("to_be_disabled", None, timeout)

    def to_be_focused(self, timeout: float | None = None) -> None:
        self._check("to_be_focused", None, timeout)

    def to_have_url(self, url, timeout: float | None = None) -> None:
        self._check("to_have_url", url, timeout)

    def to_have_title(self, title, timeout: float | None = None) -> None:
        self._check("to_have_title", title, timeout)

    def __getattr__(self, name: str):
        if name.startswith("not_to_"):
            positive = getattr(Assertions(self._target, not self._negated, self._timeout), name[len("not_"):])
            return positive
        raise unsupported("expect()", name)


def expect(target, timeout: float | None = None) -> Assertions:
    """Playwright's ``expect`` for a fake page or one of its locators."""
    if not isinstance(target, (FakeLocator, FakePage)):
        raise FakeBrowserError(f"{OWNER}: expect() takes a fake page or a fake locator, not {target!r}; "
                               "a real Playwright page takes playwright.sync_api.expect")
    return Assertions(target, timeout=timeout)
