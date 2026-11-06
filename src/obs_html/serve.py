"""obs-html serve: serve a built artifact on localhost and take the reader's answers from its page.

Reader: whoever changes how answers reach the agent that asked (spec/cli.md, Serving answers;
spec/capabilities/answers.md owns the page's side).

The server binds 127.0.0.1 only and serves the artifact's folder. The URL it prints carries a
random ``obs-answers`` token; the page's canary (canaries/answers.js) finds it there and the page
POSTs the answers payload, one JSON object, to that same URL. A POST without the token, of
another type, malformed or larger than ``execution.serveAnswersMaxBytes`` is refused with an error
naming its field and the remedy, on stderr and in the response; the server keeps waiting. A payload
is written to ``answers.json`` beside the artifact atomically (a temporary file, then a replace).
With ``--wait`` the command prints the payload on stdout, one JSON line, and exits 0; it fails
naming ``--timeout`` when none arrives in time.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import math
import os
import secrets
import sys
import tempfile
import threading
from pathlib import Path
from typing import Sequence
from urllib.parse import parse_qs, quote, urlsplit

from obs_html.config import load_config
from obs_html.errors import InputError, Parser, warn

PROG = "obs-html serve"
HOST = "127.0.0.1"
ANSWERS = "answers.json"
PARAMETER = "obs-answers"
OWNER = "spec/capabilities/answers.md"

EPILOG = f"""Serving answers:
  Serves ARTIFACT and the files beside it on {HOST} only and prints the URL to open, its first
  stdout line; any browser opens it, VS Code's built-in browser too. The page sends the reader's
  answers (obsArtifact.sendAnswers) to this server, which writes them to {ANSWERS} beside
  ARTIFACT, replacing the file at once. A malformed payload is refused and the server waits on.
  Without --wait it serves until stopped (Ctrl+C), writing each payload.
  --wait exits 0 after the first payload and prints it to stdout as one JSON line.
  --timeout S with --wait fails (exit 2) when no payload arrives within S seconds.
  --port N serves on port N; without it, on a free port.
  The answers payload is one JSON object of at most execution.serveAnswersMaxBytes bytes
  (--config FILE merges over the packaged cfg.json); {OWNER} owns its contract.

Examples:
  obs-html serve artifact.html --wait --timeout 3600
  obs-html serve artifact.html --port 8765

Exit status:
  0: an answers payload arrived (--wait), or the server was stopped; 2: invalid options, a port in
  use, or no payload within --timeout.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(prog=PROG, description="Serve a built artifact on localhost and take its reader's answers.",
                    formatter_class=argparse.RawDescriptionHelpFormatter, epilog=EPILOG)
    parser.add_argument("artifact", type=Path, metavar="ARTIFACT", help="Built HTML artifact to serve.")
    parser.add_argument("--port", type=int, default=0, metavar="N", help="Port to serve on (default: a free one).")
    parser.add_argument("--wait", action="store_true",
                        help="Exit after the first answers payload, printing it to stdout as JSON.")
    parser.add_argument("--timeout", type=float, metavar="S", help="With --wait: fail after S seconds without answers.")
    parser.add_argument("--config", type=Path, help="Settings JSON merged over the packaged cfg.json.")
    return parser


class _Server(http.server.ThreadingHTTPServer):
    # Windows lets a second socket take a port in use where the address is reusable.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


def main(argv: Sequence[str]) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    try:
        return _serve(options)
    except InputError as error:
        parser.exit(2, f"{error}\n")


def _serve(options: argparse.Namespace) -> int:
    if not options.artifact.is_file():
        raise InputError(PROG, "ARTIFACT", f"{options.artifact} is no file", "Name a built HTML artifact")
    if not 0 <= options.port <= 65535:
        raise InputError(PROG, "--port", f"{options.port} is no port", "Give a port from 1 to 65535, or drop --port")
    if options.timeout is not None and not options.wait:
        raise InputError(PROG, "--timeout", "is only used with --wait", "Add --wait, or drop --timeout")
    if options.timeout is not None and not (math.isfinite(options.timeout) and options.timeout > 0):
        raise InputError(PROG, "--timeout", f"{options.timeout} is no positive number of seconds",
                         "Give the seconds to wait, for example --timeout 600")
    config = load_config(options.config)
    artifact = options.artifact.resolve()
    token = secrets.token_urlsafe(16)
    arrived: list[dict] = []
    done = threading.Event()

    def received(payload: dict) -> None:
        arrived.append(payload)
        if options.wait:
            done.set()

    handler = functools.partial(_Handler, directory=str(artifact.parent), artifact=artifact, token=token,
                                limit=config.serve_answers_max_bytes, received=received)
    try:
        server = _Server((HOST, options.port), handler)
    except OSError as error:
        raise InputError(PROG, "--port", f"{options.port} cannot be served on {HOST} ({error.strerror or error})",
                         "Name a free port with --port, or drop --port to take any free one") from error
    url = f"http://{HOST}:{server.server_address[1]}/{quote(artifact.name)}?{PARAMETER}={token}"
    print(url, flush=True)
    print(f"{PROG}: open {url} in a browser; answers go to {artifact.parent / ANSWERS}.", file=sys.stderr, flush=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        if not options.wait:
            thread.join()
            return 0
        if not done.wait(options.timeout):
            raise InputError(PROG, "--timeout", f"no answers arrived at {url} within {options.timeout:g} s",
                             "Open the URL, send the answers from the page, and run again with a larger --timeout")
    except KeyboardInterrupt:
        return 0
    finally:
        server.shutdown()
        server.server_close()
    print(json.dumps(arrived[0], ensure_ascii=True), flush=True)
    return 0


class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, artifact: Path, token: str, limit: int, received, **kwargs) -> None:
        self.artifact, self.token, self.limit, self.received = artifact, token, limit, received
        super().__init__(*args, **kwargs)

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        try:
            payload = self._payload()
            _write_atomically(self.artifact.parent / ANSWERS, payload)
        except _Refused as refusal:
            warn(refusal)
            return self._answer(refusal.status, {"error": str(refusal)})
        self._answer(200, {"written": ANSWERS})
        print(f"{PROG}: {ANSWERS} written ({self.artifact.parent / ANSWERS}).", file=sys.stderr, flush=True)
        self.received(payload)

    def _payload(self) -> dict:
        address = urlsplit(self.path)
        if parse_qs(address.query).get(PARAMETER) != [self.token]:
            raise _Refused(403, PARAMETER, "is missing or not this server's token",
                           "Send the answers from the page at the URL obs-html serve printed")
        if address.path != f"/{quote(self.artifact.name)}":
            raise _Refused(404, "path", f"{address.path} is not the served artifact",
                           f"Post the answers to /{quote(self.artifact.name)}")
        if self.headers.get_content_type() != "application/json":
            raise _Refused(415, "Content-Type", f"{self.headers.get_content_type()} is not application/json",
                           f"Send the answers payload as JSON; see {OWNER}")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise _Refused(411, "Content-Length", "is missing", "Send the payload with its length") from None
        if length > self.limit:
            raise _Refused(413, "body", f"has {length} bytes, more than execution.serveAnswersMaxBytes ({self.limit})",
                           "Send fewer answers, or raise the limit in a settings file passed with --config")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _Refused(400, "body", f"is not UTF-8 JSON ({error})", f"Send one JSON object; see {OWNER}") from None
        if not isinstance(payload, dict):
            raise _Refused(400, "body", f"is a JSON {type(payload).__name__}, not an object",
                           f"Send the answers as one JSON object; see {OWNER}")
        return payload

    def _answer(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class _Refused(InputError):
    """A POST the server refuses with HTTP ``status``, naming the field of the request."""

    def __init__(self, status: int, field: str, problem: str, remedy: str) -> None:
        super().__init__(PROG, field, problem, remedy)
        self.status = status


def _write_atomically(path: Path, payload: dict) -> None:
    """``path`` holds ``payload`` or what it held before, never a part: a temporary file beside it replaces it."""
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except OSError as error:
        Path(temporary).unlink(missing_ok=True)
        raise _Refused(500, ANSWERS, f"cannot be written to {path} ({error.strerror or error})",
                       "Make the artifact's folder writable, then send the answers again") from error
