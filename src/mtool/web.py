"""A tiny curl-like HTTP client.

Request building and response formatting are pure functions; the actual I/O
goes through a ``Transport`` (``UrllibTransport`` by default) so it can be
replaced with a fake in tests.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_METHOD = "GET"
ALLOWED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
CSRF_COOKIE = "csrftoken"
CSRF_HEADER = "X-CSRFToken"


class WebError(Exception):
    """Raised for user-facing request problems (bad URL, connection refused...)."""


@dataclass
class PreparedRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes | None = None


@dataclass
class Response:
    status: int
    reason: str
    headers: dict[str, str]
    body: bytes

    def header(self, name: str) -> str | None:
        lname = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lname:
                return value
        return None


class Transport(Protocol):
    def send(self, request: PreparedRequest, timeout: float) -> Response: ...


def resolve_url(url: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """Absolute URLs pass through; anything else is joined onto ``base_url``.

    ``"/people"`` -> ``"http://localhost:8000/people"``; ``"example.com"`` is
    treated as a path, so give a scheme for other hosts.
    """
    parts = urlsplit(url)
    if parts.scheme and parts.netloc:
        if parts.scheme not in ("http", "https"):
            raise WebError(f"unsupported URL scheme {parts.scheme!r}")
        return url
    base = urlsplit(base_url)
    if base.scheme not in ("http", "https") or not base.netloc:
        raise WebError(f"invalid base URL {base_url!r}")
    return urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))


def add_query(url: str, params: Mapping[str, Any] | None) -> str:
    """Merge ``params`` into the query string of ``url``."""
    if not params:
        return url
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            query.extend((key, str(v)) for v in value)
        else:
            query.append((key, str(value)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def build_request(
    url: str,
    method: str = DEFAULT_METHOD,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, Any] | None = None,
    data: Any = None,
    base_url: str = DEFAULT_BASE_URL,
    csrf_token: str | None = None,
) -> PreparedRequest:
    """Build a request. ``data`` (any JSON-serialisable value) is sent as JSON."""
    method = method.upper()
    if method not in ALLOWED_METHODS:
        raise WebError(f"unsupported method {method!r}")
    final_headers = {str(k): str(v) for k, v in (headers or {}).items()}
    params = dict(params or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        final_headers.setdefault("Content-Type", "application/json")
    if csrf_token:
        final_headers[CSRF_HEADER] = csrf_token
        params["csrfmiddlewaretoken"] = csrf_token
    full_url = add_query(resolve_url(url, base_url), params)
    return PreparedRequest(method=method, url=full_url, headers=final_headers, body=body)


_CSRF_RE = re.compile(rf"(?:^|[;,\s]){CSRF_COOKIE}=([^;,\s]+)")


def extract_csrf_token(set_cookie: str | None) -> str | None:
    """Pull a Django-style ``csrftoken`` value out of a Set-Cookie header."""
    if not set_cookie:
        return None
    match = _CSRF_RE.search(set_cookie)
    return match.group(1) if match else None


def fetch_csrf_token(transport: Transport, url: str, timeout: float) -> str | None:
    """GET ``url`` and return the CSRF cookie it sets, if any."""
    response = transport.send(PreparedRequest("GET", url), timeout)
    return extract_csrf_token(response.header("Set-Cookie"))


def format_body(response: Response) -> str:
    """Decode the body; pretty-print it when it is JSON."""
    text = response.body.decode("utf-8", errors="replace")
    content_type = (response.header("Content-Type") or "").split(";")[0].strip().lower()
    if content_type == "application/json" or content_type.endswith("+json"):
        try:
            return json.dumps(json.loads(text), indent=4, sort_keys=True)
        except ValueError:
            return text
    return text


def format_response(request: PreparedRequest, response: Response, verbose: bool = False) -> str:
    lines = [f"{request.method} {request.url} {response.status} {response.reason}".rstrip()]
    if verbose:
        if request.headers:
            lines.append("Request headers:")
            lines.extend(f"  {k}: {v}" for k, v in request.headers.items())
        if request.body is not None:
            lines.append("Request body:")
            lines.append("  " + request.body.decode("utf-8", errors="replace"))
        lines.append("Response headers:")
        lines.extend(f"  {k}: {v}" for k, v in response.headers.items())
    body = format_body(response)
    if body:
        lines.append("")
        lines.append(body)
    return "\n".join(lines)


class UrllibTransport:
    """Real transport using the standard library. HTTP errors become Responses."""

    def send(self, request: PreparedRequest, timeout: float) -> Response:
        req = urllib.request.Request(
            request.url, data=request.body, headers=request.headers, method=request.method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return Response(resp.status, resp.reason or "", dict(resp.headers), resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read() if exc.fp is not None else b""
            return Response(exc.code, str(exc.reason or ""), dict(exc.headers or {}), body)
        except urllib.error.URLError as exc:
            raise WebError(f"cannot reach {request.url}: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise WebError(f"cannot reach {request.url}: {exc}") from exc


def send(
    request: PreparedRequest, transport: Transport | None = None, timeout: float = 10.0
) -> Response:
    return (transport or UrllibTransport()).send(request, timeout)
