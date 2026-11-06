"""obs-html serve as a real process for the tests of the answers sink, with every wait bounded.

Reader: a test of obs-html serve (test_serve.py, test_answers_browser.py).

``started`` runs ``python -m obs_html.cli serve ...`` and returns once the command printed its URL,
its first stdout line; ``finished`` waits for its exit. Neither waits longer than ``WAIT`` seconds:
a hanging server fails the test instead of the suite.
"""
from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

WAIT = 30
# Loopback only: no proxy the environment names may carry a request to the local server.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class Served:
    process: subprocess.Popen
    url: str
    lines: queue.Queue = field(repr=False)

    def finished(self) -> tuple[int, str, str]:
        """The exit code, the rest of stdout and stderr once the command exits, within WAIT seconds."""
        try:
            code = self.process.wait(timeout=WAIT)
        except subprocess.TimeoutExpired:
            self.process.kill()
            raise AssertionError(f"test/serving.py: obs-html serve did not exit within {WAIT} s")
        out = []
        while (line := self.lines.get(timeout=WAIT)) is not None:
            out.append(line)
        return code, "".join(out), self.process.stderr.read()

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=WAIT)
        for stream in (self.process.stdout, self.process.stderr):
            stream.close()


def _pump(stream, lines: queue.Queue) -> None:
    for line in stream:
        lines.put(line)
    lines.put(None)


def run(*arguments: object) -> subprocess.CompletedProcess:
    """obs-html serve with ``arguments`` to its exit, within WAIT seconds."""
    return subprocess.run([sys.executable, "-m", "obs_html.cli", "serve", *map(str, arguments)],
                          capture_output=True, text=True, encoding="utf-8", timeout=WAIT, check=False)


def started(artifact: Path, *arguments: object) -> Served:
    """obs-html serve on ``artifact`` with ``arguments``, once it printed its URL."""
    process = subprocess.Popen([sys.executable, "-m", "obs_html.cli", "serve", str(artifact), *map(str, arguments)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=_pump, args=(process.stdout, lines), daemon=True).start()
    try:
        url = lines.get(timeout=WAIT)
    except queue.Empty:
        process.kill()
        raise AssertionError(f"test/serving.py: obs-html serve printed no URL within {WAIT} s")
    if url is None:
        process.wait(timeout=WAIT)
        raise AssertionError(f"test/serving.py: obs-html serve exited {process.returncode}: {process.stderr.read()}")
    return Served(process, url.strip(), lines)


def post(url: str, body: bytes, content_type: str = "application/json") -> tuple[int, dict]:
    """POST ``body`` to ``url``; the status and the JSON the server answered."""
    request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": content_type})
    try:
        with OPENER.open(request, timeout=WAIT) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())
