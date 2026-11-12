"""Integration tests: undo through the HTTP server, as the browser uses it.

The logic behind the Undo button runs in Python, so these tests check the
boundary the GUI depends on (the action it sends and the field it reads)
rather than driving a real browser.
"""

import json
import re
import threading
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from server import make_server

# Sends one action to the running server and returns its JSON reply.
Post = Callable[[dict[str, Any]], dict[str, Any]]

STATIC = Path(__file__).parent.parent / "static"


@pytest.fixture
def post() -> Iterator[Post]:
    server = make_server(port=0)  # Port 0: any free port.
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/api/action"

    def send(action: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url, json.dumps(action).encode(), {"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request) as response:
            view: dict[str, Any] = json.loads(response.read())
            return view

    yield send
    server.shutdown()
    server.server_close()


def test_undo_over_http_against_the_computer(post: Post) -> None:
    post({"action": "new", "opponent": "computer"})
    post({"action": "move", "source": "e2", "target": "e4"})
    view = post({"action": "computer-move"})
    assert len(view["moves"]) == 2 and view["can_undo"] is True
    view = post({"action": "undo"})
    assert view["moves"] == [] and view["turn"] == "w"
    assert view["can_undo"] is False


def test_undo_over_http_at_the_beginning_is_not_an_error(post: Post) -> None:
    view = post({"action": "undo"})
    assert view["moves"] == [] and view["can_undo"] is False


def test_undo_button_sends_the_undo_action() -> None:
    html = (STATIC / "index.html").read_text()
    button = re.search(r"<button[^>]*id=\"undo\"[^>]*>", html)
    assert button, "index.html has no Undo button"
    assert 'data-action="undo"' in button.group()
    # The button is inside #controls, whose click handler sends data-action.
    controls = html[
        html.index('id="controls"') : html.index("</div>", html.index('id="controls"'))
    ]
    assert 'id="undo"' in controls


def test_undo_button_is_disabled_from_can_undo() -> None:
    script = (STATIC / "app.js").read_text()
    assert "querySelector('#undo').disabled = !state.can_undo" in script
