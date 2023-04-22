import os
from collections import defaultdict
from pathlib import Path
from typing import Callable, Union


ImmutableKey = Union[str, int, float, bool, tuple, frozenset, bytes]
KeyFunction = Callable[[object], ImmutableKey]


def _get_files(source=None):
    if source is None:
        source = Path(".")
    for root_dir, dirs, files in os.walk(source):
        for file in files:
            yield os.path.abspath(os.path.join(root_dir, file))


def substring_search(source=None, substring=''):
    for file in _get_files(source):
        if substring in file:
            yield file


def groupby(things, key_fn: KeyFunction):
    grouping = defaultdict(list)
    for thing in things:
        grouping[key_fn(thing)].append(thing)
    return grouping
