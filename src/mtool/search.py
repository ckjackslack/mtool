"""File search: walk a tree, filter paths by substring, group the results.

Walking the filesystem is kept separate (``iter_files``) from the pure
filtering / grouping functions so the latter can be tested on plain strings.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timezone
from pathlib import Path

GROUP_KEYS = ("parent", "ext", "month")


def iter_files(root: str | os.PathLike[str], include_hidden: bool = False) -> Iterator[Path]:
    """Yield every regular file below ``root`` (recursively), in sorted order.

    Hidden files and directories (dot-prefixed) are skipped unless
    ``include_hidden`` is true.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        if not include_hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        dirnames.sort()
        for name in sorted(filenames):
            if not include_hidden and name.startswith("."):
                continue
            yield Path(dirpath) / name


def matches(path: str, substring: str, ignore_case: bool = False) -> bool:
    """True if ``substring`` occurs in ``path`` (empty substring matches all)."""
    if ignore_case:
        return substring.lower() in path.lower()
    return substring in path


def filter_paths(
    paths: Iterable[str], substring: str = "", ignore_case: bool = False
) -> Iterator[str]:
    """Keep only the paths that contain ``substring``."""
    for path in paths:
        if matches(path, substring, ignore_case):
            yield path


def extension_key(path: str) -> str:
    """Lower-cased extension without the dot, or ``""`` if there is none."""
    return os.path.splitext(path)[1].lstrip(".").lower()


def parent_key(path: str) -> str:
    return os.path.dirname(path)


def month_from_timestamp(ts: float) -> str:
    """Format a POSIX timestamp as ``YYYY-MM`` (UTC)."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")


def file_timestamp(path: str) -> float:
    """Creation time where the OS records it (macOS/BSD), else modification time."""
    st = os.stat(path)
    return getattr(st, "st_birthtime", st.st_mtime)


def make_month_key(timestamp_fn: Callable[[str], float] = file_timestamp) -> Callable[[str], str]:
    return lambda path: month_from_timestamp(timestamp_fn(path))


def key_function(
    group_by: str, timestamp_fn: Callable[[str], float] = file_timestamp
) -> Callable[[str], str]:
    if group_by == "parent":
        return parent_key
    if group_by == "ext":
        return extension_key
    if group_by == "month":
        return make_month_key(timestamp_fn)
    raise ValueError(f"unknown grouping {group_by!r}; expected one of {', '.join(GROUP_KEYS)}")


def group_paths(paths: Iterable[str], key_fn: Callable[[str], str]) -> dict[str, list[str]]:
    """Group paths by ``key_fn``; groups are returned sorted by key."""
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(key_fn(path), []).append(path)
    return {key: groups[key] for key in sorted(groups)}


GROUP_LABELS = {
    "parent": "Parent directory",
    "ext": "Extension",
    "month": "Month",
}


def format_groups(groups: dict[str, list[str]], group_by: str, counts_only: bool = False) -> str:
    """Render grouped results as text."""
    label = GROUP_LABELS.get(group_by, group_by)
    lines: list[str] = []
    for key, items in groups.items():
        shown = key if key else "(none)"
        if counts_only:
            lines.append(f"{len(items):>6}  {shown}")
            continue
        lines.append(f"{label}: {shown} ({len(items)})")
        lines.extend(f"  {item}" for item in items)
        lines.append("")
    return "\n".join(lines).rstrip("\n")
