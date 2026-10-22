"""Command-line interface: ``mtool <command> [options]``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from mtool import __version__
from mtool import gencsv, search, stats, web

ENV_BASE_URL = "MTOOL_BASE_URL"


class CliError(Exception):
    """An error reported to the user as ``mtool: error: ...`` with exit code 1."""


# ---------------------------------------------------------------- arg types


def _existing_dir(value: str) -> Path:
    path = Path(value)
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"not a directory: {value!r}")
    return path


def _header(value: str) -> tuple[str, str]:
    name, sep, val = value.partition(":")
    if not sep or not name.strip():
        raise argparse.ArgumentTypeError(f"header must look like 'Name: value', got {value!r}")
    return name.strip(), val.strip()


def _query_param(value: str) -> tuple[str, str]:
    key, sep, val = value.partition("=")
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"query param must look like 'key=value', got {value!r}")
    return key, val


def _json_value(value: str):
    try:
        return json.loads(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not valid JSON: {exc}") from exc


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return number


def _non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not an integer: {value!r}") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return number


def _port(value: str) -> int:
    number = _non_negative_int(value)
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("port must be in 1..65535")
    return number


class HelpAllAction(argparse.Action):
    """Print help for the main parser and every subcommand (like the original --help)."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        parts = [parser.format_help()]
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    parts.append(f"{'-' * 20} {name} {'-' * 20}\n\n{sub.format_help()}")
        parser._print_message("\n".join(parts), sys.stdout)
        parser.exit()


# ------------------------------------------------------------------ parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mtool",
        description="Multi-tool handy command aggregator.",
        epilog="Run 'mtool <command> --help' for command options, or 'mtool --help-all'.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--help-all", action=HelpAllAction, help="show help for all commands")
    sub = parser.add_subparsers(dest="cmd", metavar="<command>")

    # search
    p = sub.add_parser(
        "search",
        help="find files under a directory whose path contains a substring",
        description="Recursively list files under ROOT whose path contains SUBSTRING, "
        "optionally grouped.",
    )
    p.add_argument("root", nargs="?", default=Path("."), type=_existing_dir,
                   help="directory to search (default: current directory)")
    p.add_argument("-s", "--substring", default="",
                   help="substring matched against each file path (default: match all)")
    p.add_argument("-i", "--ignore-case", action="store_true", help="case-insensitive match")
    p.add_argument("-g", "--group-by", choices=search.GROUP_KEYS,
                   help="group results by parent directory, extension, or month "
                   "(creation time where available, else modification time)")
    p.add_argument("-c", "--count", action="store_true",
                   help="print only counts (total, or per group with --group-by)")
    p.add_argument("-a", "--absolute", action="store_true", help="print absolute paths")
    p.add_argument("--hidden", action="store_true", help="include dot-files and dot-directories")
    p.set_defaults(func=cmd_search)

    # stats
    p = sub.add_parser(
        "stats",
        help="summarise the columns of a CSV file",
        description="Print the shape of a CSV file (with header row) and per-column "
        "statistics: mean/median/stdev/min/max for numeric columns, most common values "
        "for text columns.",
    )
    p.add_argument("file", help="CSV file path, or '-' for stdin")
    p.add_argument("-c", "--column", action="append", dest="columns", metavar="COLUMN",
                   help="column to summarise (repeatable; default: all columns)")
    p.add_argument("-d", "--delimiter", default=",", help="field delimiter (default: ',')")
    p.add_argument("--json", action="store_true", help="output JSON instead of text")
    p.set_defaults(func=cmd_stats)

    # web
    p = sub.add_parser(
        "web",
        help="make an HTTP request and print the response",
        description="Make an HTTP request and print status line plus body (JSON is "
        "pretty-printed). Relative URLs such as '/people' are resolved against "
        f"--base-url (env {ENV_BASE_URL}, default {web.DEFAULT_BASE_URL}). "
        "Exits with 1 for HTTP status >= 400.",
    )
    p.add_argument("url", nargs="?", default="/", help="absolute URL or path (default: '/')")
    p.add_argument("-X", "--method", default=web.DEFAULT_METHOD, type=str.upper,
                   choices=web.ALLOWED_METHODS, help="HTTP method (default: GET)")
    p.add_argument("-H", "--header", action="append", type=_header, default=[],
                   metavar="'NAME: VALUE'", help="extra request header (repeatable)")
    p.add_argument("-q", "--query", action="append", type=_query_param, default=[],
                   metavar="KEY=VALUE", help="query string parameter (repeatable)")
    p.add_argument("-d", "--data", type=_json_value, metavar="JSON",
                   help="JSON request body, e.g. '{\"name\": \"Ann\"}'")
    p.add_argument("--csrf", action="store_true",
                   help="first GET the base URL, read its 'csrftoken' cookie and send it as "
                   "X-CSRFToken header and csrfmiddlewaretoken param (Django style)")
    p.add_argument("--base-url", default=None, help="base for relative URLs")
    p.add_argument("-t", "--timeout", type=_positive_float, default=10.0,
                   help="timeout in seconds (default: 10)")
    p.add_argument("-v", "--verbose", action="store_true", help="also print headers sent/received")
    p.set_defaults(func=cmd_web)

    # gencsv
    p = sub.add_parser(
        "gencsv",
        help="generate a synthetic employee CSV (needs Faker)",
        description="Generate fake employee rows (full_name, age, phone, position, company) "
        "with Faker. Requires: pip install 'mtool[gen]'.",
    )
    p.add_argument("-n", "--rows", type=_non_negative_int, default=50,
                   help="number of rows (default: 50)")
    p.add_argument("-o", "--output", help="output file (default: stdout)")
    p.add_argument("--seed", type=int, help="random seed for reproducible output")
    p.add_argument("--locale", default="en_US", help="Faker locale (default: en_US)")
    p.add_argument("--min-age", type=_non_negative_int, default=18, help="minimum age (default: 18)")
    p.add_argument("--max-age", type=_non_negative_int, default=65, help="maximum age (default: 65)")
    p.set_defaults(func=cmd_gencsv)

    # serve
    p = sub.add_parser(
        "serve",
        help="run the toy JSON API server (needs Flask)",
        description="Run a small in-memory JSON API (/, /hello/<name>, /people) for "
        "trying out 'mtool web'. Development server only. Requires: pip install 'mtool[server]'.",
    )
    p.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=_port, default=8000, help="port (default: 8000)")
    p.set_defaults(func=cmd_serve)

    return parser


# ---------------------------------------------------------------- commands


def cmd_search(args: argparse.Namespace, out: TextIO, **_) -> int:
    root: Path = args.root.resolve() if args.absolute else args.root
    paths = (str(p) for p in search.iter_files(root, include_hidden=args.hidden))
    found = search.filter_paths(paths, args.substring, args.ignore_case)
    if args.group_by:
        groups = search.group_paths(found, search.key_function(args.group_by))
        text = search.format_groups(groups, args.group_by, counts_only=args.count)
        if text:
            print(text, file=out)
    elif args.count:
        print(sum(1 for _ in found), file=out)
    else:
        for path in found:
            print(path, file=out)
    return 0


def cmd_stats(args: argparse.Namespace, out: TextIO, stdin: TextIO | None = None, **_) -> int:
    if len(args.delimiter) != 1:
        raise CliError("--delimiter must be a single character")
    try:
        if args.file == "-":
            table = stats.load_table(stdin or sys.stdin, args.delimiter)
        else:
            with open(args.file, newline="", encoding="utf-8-sig") as fh:
                table = stats.load_table(fh, args.delimiter)
    except FileNotFoundError as exc:
        raise CliError(f"no such file: {args.file}") from exc
    except IsADirectoryError as exc:
        raise CliError(f"is a directory: {args.file}") from exc
    except UnicodeDecodeError as exc:
        raise CliError(f"{args.file} is not UTF-8 text") from exc
    except stats.StatsError as exc:
        raise CliError(f"{args.file}: {exc}") from exc
    try:
        summaries = stats.summarize(table, args.columns)
    except stats.StatsError as exc:
        raise CliError(str(exc)) from exc
    if args.json:
        print(json.dumps(stats.summary_as_dict(table, summaries), indent=2), file=out)
    else:
        print(stats.format_summary(table, summaries), file=out)
    return 0


def cmd_web(args: argparse.Namespace, out: TextIO, transport: web.Transport | None = None,
            env: dict | None = None, **_) -> int:
    env = os.environ if env is None else env
    base_url = args.base_url or env.get(ENV_BASE_URL) or web.DEFAULT_BASE_URL
    transport = transport or web.UrllibTransport()
    try:
        token = None
        if args.csrf:
            token = web.fetch_csrf_token(transport, web.resolve_url("/", base_url), args.timeout)
            if token is None:
                print("mtool: warning: no csrftoken cookie received", file=sys.stderr)
        request = web.build_request(
            args.url,
            method=args.method,
            headers=dict(args.header),
            params=_group_params(args.query),
            data=args.data,
            base_url=base_url,
            csrf_token=token,
        )
        response = web.send(request, transport, args.timeout)
    except web.WebError as exc:
        raise CliError(str(exc)) from exc
    print(web.format_response(request, response, verbose=args.verbose), file=out)
    return 0 if response.status < 400 else 1


def _group_params(pairs: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    params: dict[str, list[str]] = {}
    for key, value in pairs:
        params.setdefault(key, []).append(value)
    return params


def cmd_gencsv(args: argparse.Namespace, out: TextIO, provider=None, **_) -> int:
    if args.min_age > args.max_age:
        raise CliError("--min-age must be <= --max-age")
    try:
        provider = provider or gencsv.make_faker(args.locale, args.seed)
    except gencsv.GenError as exc:
        raise CliError(str(exc)) from exc
    rows = gencsv.generate_rows(args.rows, provider, args.min_age, args.max_age)
    if args.output:
        try:
            with open(args.output, "w", newline="", encoding="utf-8") as fh:
                n = gencsv.write_csv(rows, fh)
        except OSError as exc:
            raise CliError(f"cannot write {args.output}: {exc.strerror or exc}") from exc
        print(f"wrote {n} rows to {args.output}", file=sys.stderr)
    else:
        gencsv.write_csv(rows, out)
    return 0


def cmd_serve(args: argparse.Namespace, out: TextIO, **_) -> int:  # pragma: no cover - blocking
    from mtool.server import create_app

    try:
        app = create_app()
    except RuntimeError as exc:
        raise CliError(str(exc)) from exc
    app.run(host=args.host, port=args.port, debug=False)
    return 0


# -------------------------------------------------------------------- main


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None, **deps) -> int:
    """Entry point. ``deps`` lets tests inject fakes (transport, provider, env, stdin)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    out = out or sys.stdout
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return 2
    try:
        return args.func(args, out=out, **deps)
    except CliError as exc:
        print(f"mtool: error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        # e.g. `mtool search | head`; silence the flush error at exit
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
