import os
from pathlib import Path


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