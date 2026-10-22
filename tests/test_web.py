import io
import json
import urllib.error

import pytest

from mtool import web
from mtool.web import PreparedRequest, Response

from conftest import FakeTransport


@pytest.mark.parametrize(
    "url,base,expected",
    [
        ("/", "http://localhost:8000", "http://localhost:8000/"),
        ("/people", "http://localhost:8000", "http://localhost:8000/people"),
        ("people", "http://h:1/api/", "http://h:1/api/people"),
        ("/people", "http://h:1/api", "http://h:1/api/people"),
        ("https://example.com/x?y=1", "http://localhost:8000", "https://example.com/x?y=1"),
    ],
)
def test_resolve_url(url, base, expected):
    assert web.resolve_url(url, base) == expected


def test_resolve_url_rejects_bad_scheme_and_base():
    with pytest.raises(web.WebError, match="scheme"):
        web.resolve_url("ftp://host/x")
    with pytest.raises(web.WebError, match="base URL"):
        web.resolve_url("/x", "not-a-url")


def test_add_query_merges_and_repeats():
    assert web.add_query("http://h/p?a=1", {"b": "2"}) == "http://h/p?a=1&b=2"
    assert web.add_query("http://h/p", {"a": ["1", "2"]}) == "http://h/p?a=1&a=2"
    assert web.add_query("http://h/p", {}) == "http://h/p"
    assert web.add_query("http://h/p", {"q": "a b&c"}) == "http://h/p?q=a+b%26c"


def test_build_request_json_body():
    req = web.build_request("/people", "post", data={"name": "Ann"}, base_url="http://h")
    assert req.method == "POST"
    assert req.url == "http://h/people"
    assert json.loads(req.body) == {"name": "Ann"}
    assert req.headers["Content-Type"] == "application/json"


def test_build_request_keeps_explicit_content_type():
    req = web.build_request("/", data=[1], headers={"Content-Type": "application/vnd+json"})
    assert req.headers["Content-Type"] == "application/vnd+json"


def test_build_request_get_without_body():
    req = web.build_request("/x", params={"a": "1"})
    assert req.body is None
    assert req.headers == {}
    assert req.url == "http://localhost:8000/x?a=1"


def test_build_request_with_csrf():
    req = web.build_request("/f", "POST", base_url="http://h", csrf_token="tok")
    assert req.headers["X-CSRFToken"] == "tok"
    assert req.url == "http://h/f?csrfmiddlewaretoken=tok"


def test_build_request_bad_method():
    with pytest.raises(web.WebError, match="method"):
        web.build_request("/", "TRACE")


@pytest.mark.parametrize(
    "cookie,expected",
    [
        ("csrftoken=abc123; expires=Thu; Path=/", "abc123"),
        ("sessionid=x; Path=/, csrftoken=zz9; Path=/", "zz9"),
        ("csrftoken=last", "last"),
        ("mycsrftoken=nope; Path=/", None),
        ("sessionid=x", None),
        (None, None),
        ("", None),
    ],
)
def test_extract_csrf_token(cookie, expected):
    assert web.extract_csrf_token(cookie) == expected


def test_fetch_csrf_token_uses_transport():
    t = FakeTransport([Response(200, "OK", {"set-cookie": "csrftoken=T1; Path=/"}, b"")])
    assert web.fetch_csrf_token(t, "http://h/", 3) == "T1"
    assert t.sent[0].method == "GET" and t.sent[0].url == "http://h/"


def test_response_header_case_insensitive():
    r = Response(200, "OK", {"Content-Type": "text/plain"}, b"")
    assert r.header("content-type") == "text/plain"
    assert r.header("missing") is None


def test_format_body_pretty_json():
    r = Response(200, "OK", {"Content-Type": "application/json; charset=utf-8"}, b'{"b":1,"a":2}')
    assert web.format_body(r) == '{\n    "a": 2,\n    "b": 1\n}'


def test_format_body_invalid_json_falls_back_to_text():
    r = Response(200, "OK", {"Content-Type": "application/json"}, b"{oops")
    assert web.format_body(r) == "{oops"


def test_format_body_text_and_binary_safe():
    r = Response(200, "OK", {"Content-Type": "text/html"}, b"<p>hi \xff</p>")
    assert web.format_body(r) == "<p>hi �</p>"


def test_format_response_verbose():
    req = PreparedRequest("POST", "http://h/p", {"X-A": "1"}, b'{"n": 1}')
    resp = Response(201, "CREATED", {"Content-Type": "text/plain"}, b"done")
    text = web.format_response(req, resp, verbose=True)
    lines = text.splitlines()
    assert lines[0] == "POST http://h/p 201 CREATED"
    assert "  X-A: 1" in lines
    assert '  {"n": 1}' in lines
    assert "  Content-Type: text/plain" in lines
    assert lines[-1] == "done"


def test_format_response_empty_body():
    req = PreparedRequest("HEAD", "http://h/")
    assert web.format_response(req, Response(204, "", {}, b"")) == "HEAD http://h/ 204"


def test_send_uses_given_transport(fake_transport):
    req = PreparedRequest("GET", "http://h/")
    resp = web.send(req, fake_transport, timeout=2.5)
    assert resp.status == 200
    assert fake_transport.sent == [req]
    assert fake_transport.timeout == 2.5


# --- UrllibTransport with urlopen monkeypatched (no network) ---


class _FakeHTTPResponse(io.BytesIO):
    def __init__(self, body, status=200, reason="OK", headers=None):
        super().__init__(body)
        self.status = status
        self.reason = reason
        self.headers = headers or {"Content-Type": "application/json"}


def test_urllib_transport_success(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout):
        captured["req"] = req
        captured["timeout"] = timeout
        return _FakeHTTPResponse(b'{"a": 1}')

    monkeypatch.setattr(web.urllib.request, "urlopen", fake_urlopen)
    req = PreparedRequest("POST", "http://h/p", {"X-Test": "1"}, b"{}")
    resp = web.UrllibTransport().send(req, timeout=4)
    assert resp.status == 200 and resp.body == b'{"a": 1}'
    assert captured["req"].get_method() == "POST"
    assert captured["req"].get_header("X-test") == "1"
    assert captured["req"].data == b"{}"
    assert captured["timeout"] == 4


def test_urllib_transport_http_error_becomes_response(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(
            req.full_url, 404, "NOT FOUND", {"Content-Type": "text/plain"}, io.BytesIO(b"nope")
        )

    monkeypatch.setattr(web.urllib.request, "urlopen", fake_urlopen)
    resp = web.UrllibTransport().send(PreparedRequest("GET", "http://h/x"), 1)
    assert (resp.status, resp.body) == (404, b"nope")


@pytest.mark.parametrize(
    "exc", [urllib.error.URLError("Connection refused"), TimeoutError("timed out")]
)
def test_urllib_transport_connection_errors(monkeypatch, exc):
    def fake_urlopen(req, timeout):
        raise exc

    monkeypatch.setattr(web.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(web.WebError, match="cannot reach http://h/"):
        web.UrllibTransport().send(PreparedRequest("GET", "http://h/"), 1)
