from __future__ import annotations

import itertools

import pytest

from mtool.web import PreparedRequest, Response


class FakeTransport:
    """Records requests and replays canned responses (no network)."""

    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.sent: list[PreparedRequest] = []

    def send(self, request, timeout):
        self.sent.append(request)
        self.timeout = timeout
        if self.error is not None:
            raise self.error
        if self.responses:
            return self.responses.pop(0)
        return Response(200, "OK", {"Content-Type": "application/json"}, b'{"ok": true}')


class StubProvider:
    """Deterministic stand-in for faker.Faker."""

    def __init__(self):
        self._n = itertools.count(1)

    def name(self):
        return f"Person {next(self._n)}"

    def pyint(self, min_value=0, max_value=9999):
        return min_value

    def phone_number(self):
        return "555-0100"

    def job(self):
        return "Engineer, software"

    def company(self):
        return "Smith, Jones and Brown"


@pytest.fixture
def fake_transport():
    return FakeTransport()


@pytest.fixture
def stub_provider():
    return StubProvider()


@pytest.fixture
def tree(tmp_path):
    """A small directory tree for search tests."""
    files = [
        "a.py",
        "b.txt",
        "README",
        "pkg/__init__.py",
        "pkg/mod.PY",
        "pkg/data/report.csv",
        ".hidden/secret.py",
        ".dotfile",
    ]
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    return tmp_path
