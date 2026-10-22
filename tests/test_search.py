import os

import pytest

from mtool import search


def rel(paths, root):
    return [os.path.relpath(str(p), root) for p in paths]


def test_iter_files_skips_hidden_by_default(tree):
    found = rel(search.iter_files(tree), tree)
    assert sorted(found) == sorted(
        ["a.py", "b.txt", "README", "pkg/__init__.py", "pkg/mod.PY", "pkg/data/report.csv"]
    )


def test_iter_files_include_hidden(tree):
    found = rel(search.iter_files(tree, include_hidden=True), tree)
    assert ".hidden/secret.py" in found
    assert ".dotfile" in found


def test_iter_files_is_deterministic(tree):
    assert list(search.iter_files(tree)) == list(search.iter_files(tree))


def test_iter_files_empty_dir(tmp_path):
    assert list(search.iter_files(tmp_path)) == []


@pytest.mark.parametrize(
    "path,sub,ic,expected",
    [
        ("/x/a.py", ".py", False, True),
        ("/x/a.PY", ".py", False, False),
        ("/x/a.PY", ".py", True, True),
        ("/x/a.txt", "", False, True),
    ],
)
def test_matches(path, sub, ic, expected):
    assert search.matches(path, sub, ic) is expected


def test_filter_paths():
    paths = ["a/b.py", "a/c.txt", "d/e.py"]
    assert list(search.filter_paths(paths, ".py")) == ["a/b.py", "d/e.py"]
    assert list(search.filter_paths(paths)) == paths


def test_extension_and_parent_keys():
    assert search.extension_key("a/b.TXT") == "txt"
    assert search.extension_key("a/Makefile") == ""
    assert search.extension_key("a/archive.tar.gz") == "gz"
    assert search.parent_key("a/b/c.py") == "a/b"


def test_month_from_timestamp():
    assert search.month_from_timestamp(0) == "1970-01"
    assert search.month_from_timestamp(1682165805) == "2023-04"


def test_key_function_month_uses_injected_timestamp():
    stamps = {"a": 0.0, "b": 1682165805.0}
    key = search.key_function("month", timestamp_fn=stamps.__getitem__)
    assert key("a") == "1970-01"
    assert key("b") == "2023-04"


def test_key_function_unknown():
    with pytest.raises(ValueError, match="unknown grouping"):
        search.key_function("size")


def test_file_timestamp_real_file(tmp_path):
    f = tmp_path / "f"
    f.write_text("x")
    os.utime(f, (1682165805, 1682165805))
    ts = search.file_timestamp(str(f))
    assert isinstance(ts, float)


def test_group_paths_sorted_by_key():
    groups = search.group_paths(["x/b.py", "x/a.txt", "y/c.py"], search.extension_key)
    assert list(groups) == ["py", "txt"]
    assert groups["py"] == ["x/b.py", "y/c.py"]


def test_format_groups_full_and_counts():
    groups = {"": ["Makefile"], "py": ["a.py", "b.py"]}
    text = search.format_groups(groups, "ext")
    assert "Extension: (none) (1)" in text
    assert "Extension: py (2)" in text
    assert "  a.py" in text
    counts = search.format_groups(groups, "ext", counts_only=True)
    assert counts.splitlines() == ["     1  (none)", "     2  py"]


def test_format_groups_empty():
    assert search.format_groups({}, "ext") == ""
