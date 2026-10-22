import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mtool.cli import main
from mtool.web import Response

from conftest import FakeTransport

EXAMPLE_CSV = Path(__file__).resolve().parent.parent / "examples" / "employee.csv"


def run(argv, **deps):
    out = io.StringIO()
    code = main(argv, out=out, **deps)
    return code, out.getvalue()


# --- general ---


def test_no_command_prints_help_and_exits_2(capsys):
    assert main([]) == 2
    assert "usage: mtool" in capsys.readouterr().err


def test_help_all_lists_every_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help-all"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in ("search", "stats", "web", "gencsv", "serve"):
        assert f"--- {name} ---" in out


def test_version(capsys):
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.startswith("mtool ")


def test_unknown_command_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["frobnicate"])
    assert exc.value.code == 2


def test_python_dash_m_entry_point():
    r = subprocess.run(
        [sys.executable, "-m", "mtool", "--version"], capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0 and r.stdout.startswith("mtool ")


# --- search ---


def test_search_lists_matching_files(tree, monkeypatch):
    monkeypatch.chdir(tree)
    code, out = run(["search", "-s", ".py"])
    assert code == 0
    assert out.splitlines() == ["a.py", "pkg/__init__.py"]


def test_search_ignore_case_and_hidden(tree):
    code, out = run(["search", str(tree), "-s", ".py", "-i", "--hidden"])
    names = sorted(os.path.relpath(p, tree) for p in out.splitlines())
    assert names == [".hidden/secret.py", "a.py", "pkg/__init__.py", "pkg/mod.PY"]


def test_search_absolute(tree, monkeypatch):
    monkeypatch.chdir(tree / "pkg")
    code, out = run(["search", "--absolute", "-s", "report"])
    assert out.strip() == str((tree / "pkg/data/report.csv").resolve())


def test_search_count(tree):
    assert run(["search", str(tree), "-c"]) == (0, "6\n")


def test_search_group_by_ext_counts(tree):
    code, out = run(["search", str(tree), "-g", "ext", "-c"])
    # extensions are case-folded, so pkg/mod.PY counts as "py"
    assert out.splitlines() == ["     1  (none)", "     1  csv", "     3  py", "     1  txt"]


def test_search_group_by_parent(tree, monkeypatch):
    monkeypatch.chdir(tree)
    code, out = run(["search", "-g", "parent", "-s", "pkg"])
    assert "Parent directory: pkg (2)" in out
    assert "Parent directory: pkg/data (1)" in out


def test_search_group_by_month(tree):
    for p in tree.rglob("*"):
        if p.is_file():
            os.utime(p, (1682165805, 1682165805))
    code, out = run(["search", str(tree), "-g", "month", "-c"])
    assert code == 0
    # Linux has no birth time in os.stat -> mtime is used
    if not hasattr(os.stat(tree / "a.py"), "st_birthtime"):
        assert out.strip() == "6  2023-04"


def test_search_no_results_prints_nothing(tree):
    assert run(["search", str(tree), "-s", "zzz"]) == (0, "")
    assert run(["search", str(tree), "-s", "zzz", "-g", "ext"]) == (0, "")


def test_search_missing_dir_is_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["search", str(tmp_path / "nope")])
    assert exc.value.code == 2
    assert "not a directory" in capsys.readouterr().err


# --- stats ---


def test_stats_on_example_csv():
    code, out = run(["stats", str(EXAMPLE_CSV), "-c", "age"])
    assert code == 0
    assert out.startswith("Shape: 50 rows x 5 columns")
    assert "age (numeric)" in out
    assert "min: 20  max: 65" in out


def test_stats_json(tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("x,y\n1,a\n3,b\n")
    code, out = run(["stats", str(f), "--json"])
    data = json.loads(out)
    assert data["rows"] == 2 and data["summary"][0]["mean"] == 2
    assert data["summary"][1]["kind"] == "text"


def test_stats_stdin_and_delimiter():
    code, out = run(["stats", "-", "-d", ";"], stdin=io.StringIO("a;b\n1;2\n3;4\n"))
    assert code == 0 and "Shape: 2 rows x 2 columns" in out


def test_stats_handles_utf8_bom(tmp_path):
    f = tmp_path / "bom.csv"
    f.write_bytes("﻿age\n5\n".encode())
    code, out = run(["stats", str(f), "-c", "age"])
    assert code == 0


@pytest.mark.parametrize(
    "setup,args,msg",
    [
        (None, ["missing.csv"], "no such file"),
        ("dir", ["DIR"], "is a directory"),
        ("bad", ["BAD"], "expected 2 fields"),
        ("good", ["GOOD", "-c", "nope"], "unknown column 'nope'"),
        ("good", ["GOOD", "-d", ";;"], "single character"),
        ("binary", ["BIN"], "not UTF-8"),
        ("empty", ["EMPTY"], "empty"),
    ],
)
def test_stats_errors(tmp_path, monkeypatch, capsys, setup, args, msg):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "DIR").mkdir()
    (tmp_path / "BAD").write_text("a,b\n'x',1,'y, z'\n")
    (tmp_path / "GOOD").write_text("a,b\n1,2\n")
    (tmp_path / "BIN").write_bytes(b"\xff\xfe\x00bad")
    (tmp_path / "EMPTY").write_text("")
    code, _ = run(["stats", *args])
    assert code == 1
    assert msg in capsys.readouterr().err


# --- web ---


def test_web_get_relative_uses_env_base_url():
    t = FakeTransport()
    code, out = run(["web", "/people"], transport=t, env={"MTOOL_BASE_URL": "http://api:9"})
    assert code == 0
    assert t.sent[0].url == "http://api:9/people"
    assert out.splitlines()[0] == "GET http://api:9/people 200 OK"
    assert '"ok": true' in out


def test_web_base_url_flag_beats_env():
    t = FakeTransport()
    run(["web", "x", "--base-url", "http://flag"], transport=t, env={"MTOOL_BASE_URL": "http://env"})
    assert t.sent[0].url == "http://flag/x"


def test_web_default_base_url():
    t = FakeTransport()
    run(["web"], transport=t, env={})
    assert t.sent[0].url == "http://localhost:8000/"


def test_web_post_with_headers_query_and_data():
    t = FakeTransport()
    code, _ = run(
        ["web", "http://h/p", "-X", "post", "-H", "X-A: 1", "-q", "k=v", "-q", "k=w",
         "-d", '{"name": "Ann"}'],
        transport=t, env={},
    )
    req = t.sent[0]
    assert code == 0
    assert req.method == "POST"
    assert req.url == "http://h/p?k=v&k=w"
    assert req.headers["X-A"] == "1"
    assert json.loads(req.body) == {"name": "Ann"}


def test_web_http_error_exit_code():
    t = FakeTransport([Response(409, "CONFLICT", {}, b"dup")])
    code, out = run(["web", "/people"], transport=t, env={})
    assert code == 1
    assert "409 CONFLICT" in out


def test_web_connection_error(capsys):
    from mtool.web import WebError

    t = FakeTransport(error=WebError("cannot reach http://h/: refused"))
    code, out = run(["web", "http://h/"], transport=t, env={})
    assert code == 1 and out == ""
    assert "mtool: error: cannot reach" in capsys.readouterr().err


def test_web_bad_scheme(capsys):
    code, _ = run(["web", "ftp://h/x"], transport=FakeTransport(), env={})
    assert code == 1
    assert "unsupported URL scheme" in capsys.readouterr().err


def test_web_csrf_flow():
    t = FakeTransport([
        Response(200, "OK", {"Set-Cookie": "csrftoken=TOK; Path=/"}, b""),
        Response(200, "OK", {}, b"ok"),
    ])
    code, _ = run(["web", "/form", "-X", "POST", "--csrf"], transport=t,
                  env={"MTOOL_BASE_URL": "http://d"})
    assert code == 0
    assert t.sent[0].url == "http://d/"
    assert t.sent[1].headers["X-CSRFToken"] == "TOK"
    assert t.sent[1].url == "http://d/form?csrfmiddlewaretoken=TOK"


def test_web_csrf_missing_cookie_warns(capsys):
    t = FakeTransport([Response(200, "OK", {}, b""), Response(200, "OK", {}, b"")])
    code, _ = run(["web", "/", "--csrf"], transport=t, env={})
    assert code == 0
    assert "no csrftoken cookie" in capsys.readouterr().err
    assert "X-CSRFToken" not in t.sent[1].headers


@pytest.mark.parametrize(
    "args,msg",
    [
        (["-d", "{bad"], "not valid JSON"),
        (["-H", "NoColon"], "Name: value"),
        (["-q", "novalue"], "key=value"),
        (["-X", "TRACE"], "invalid choice"),
        (["-t", "0"], "must be > 0"),
    ],
)
def test_web_bad_arguments(capsys, args, msg):
    with pytest.raises(SystemExit) as exc:
        main(["web", *args], transport=FakeTransport(), env={})
    assert exc.value.code == 2
    assert msg in capsys.readouterr().err


# --- gencsv ---


def test_gencsv_stdout_with_stub(stub_provider):
    code, out = run(["gencsv", "-n", "2"], provider=stub_provider)
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "full_name,age,phone,position,company"
    assert lines[1] == 'Person 1,18,555-0100,"Engineer, software","Smith, Jones and Brown"'


def test_gencsv_output_file_then_stats(tmp_path, capsys):
    pytest.importorskip("faker")
    f = tmp_path / "emp.csv"
    assert run(["gencsv", "-n", "20", "--seed", "1", "-o", str(f)])[0] == 0
    assert "wrote 20 rows" in capsys.readouterr().err
    code, out = run(["stats", str(f), "-c", "age"])
    assert code == 0 and "Shape: 20 rows x 5 columns" in out


def test_gencsv_seed_is_reproducible():
    pytest.importorskip("faker")
    assert run(["gencsv", "-n", "5", "--seed", "3"]) == run(["gencsv", "-n", "5", "--seed", "3"])


def test_gencsv_age_range_error(capsys, stub_provider):
    code, _ = run(["gencsv", "--min-age", "70", "--max-age", "60"], provider=stub_provider)
    assert code == 1
    assert "--min-age must be <= --max-age" in capsys.readouterr().err


def test_gencsv_unwritable_output(tmp_path, capsys, stub_provider):
    code, _ = run(["gencsv", "-o", str(tmp_path / "no" / "dir.csv")], provider=stub_provider)
    assert code == 1
    assert "cannot write" in capsys.readouterr().err


def test_gencsv_negative_rows_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["gencsv", "-n", "-1"])
    assert exc.value.code == 2


# --- serve (argument parsing only; the server itself is tested via test client) ---


def test_serve_bad_port():
    with pytest.raises(SystemExit) as exc:
        main(["serve", "--port", "70000"])
    assert exc.value.code == 2
