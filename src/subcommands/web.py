import json
import re
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

from constants import BASE_URL, DEFAULT_METHOD
from utils import prettyprint, to_json_str


def make_request(
    path="",
    method=DEFAULT_METHOD,
    headers=None,
    params=None,
    data=None,
    with_csrf=False,
):
    try:
        if headers is None:
            headers = {}

        if params is None:
            params = {}

        _data = None
        if data is not None:
            _data = json.dumps(data).encode()
            headers.update({"Content-Type": "application/json"})

        url = BASE_URL
        if path:
            url += path

        if isinstance(params, dict) and params:
            params = urlencode(params)
            url += f"?{params}"

        if with_csrf:
            cookie = urlopen(BASE_URL).headers.get("Set-Cookie")
            if cookie is not None:
                csrf = re.search(r"csrftoken=(.*?);", cookie).groups(1)
                params.update({"csrfmiddlewaretoken": csrf})
                headers.update({"X-CSRFToken": csrf})

        request = Request(url, method=method)
        if headers:
            request.headers = headers
        if data:
            request.data = _data
        outcome = f"{method.upper()} {url}"
        response = urlopen(request)
        outcome += f" {response.code}"

        prettyprint(response)
        return response

    except HTTPError as e:
        outcome += f" {e.code}\n"
        outcome += e.read().decode()
    except URLError as e:
        outcome += f" {e.reason}"
    finally:
        print(outcome)
        if data:
            print("Called with:")
            print("DATA:")
            print(to_json_str(data))
        if headers:
            print("HEADERS:")
            print(to_json_str(headers))
        if params:
            print("QUERY STRING:")
            print(to_json_str(params))