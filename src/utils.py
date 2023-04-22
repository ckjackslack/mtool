import argparse
import json
import os
from pathlib import Path


def dict_or_none(obj):
    try:
        if type(obj) is str and not obj:
            return None
        return json.loads(obj)
    except ValueError:
        raise argparse.ArgumentTypeError("Is not valid JSON")


def str_to_path(value):
    if type(value) is not str:
        raise TypeError("Path must be provided as a string.")
    if os.path.isdir(value):
        return Path(value)
    else:
        raise ValueError("Cannot find relevant path.")


def to_json_str(obj):
    return json.dumps(obj, indent=4, sort_keys=True)


def prettyprint(response):
    data = response.read().decode()
    if response.headers.get("Content-Type") == "application/json":
        data = json.loads(data)
        print(to_json_str(data))
    else:
        print(data)