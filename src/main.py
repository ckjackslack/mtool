#!/usr/bin/python3
import sys
sys.dont_write_bytecode = True

import argparse
import os
from datetime import datetime as dt
from pathlib import Path

from constants import (
    ALLOWED_METHODS,
    BASE_URL,
    DEFAULT_METHOD,
)
from subcommands.search import (
    substring_search,
    groupby,
)
from subcommands.stats import show_stats
from subcommands.web import make_request
from parser_utils import MonoHelpAction
from utils import (
    dict_or_none,
    str_to_path,
)


mtool_parser = argparse.ArgumentParser(
    prog=f"python {__file__}",
    add_help=False,
)
mtool_parser.add_argument(
    '--help',
    action=MonoHelpAction,
    help='Print help',
)


def cli():
    global mtool_parser

    subparsers = mtool_parser.add_subparsers(dest="cmd")

    # search parser
    search_parser = subparsers.add_parser(
        "search",
        help="Search given root folder for a file that matches pattern",
        description="Search",
    )
    search_parser.add_argument(
        "--source",
        nargs="?",
        default=Path("."),
        type=str_to_path,
        help="Root path to start searching recursively",
    )
    search_parser.add_argument(
        "--substring",
        nargs="?",
        default="",
        type=str,
        help=(
            "Substring that will be matched against absolute path"
            " of given descendant file from the root path"
        ),
    )
    search_parser.add_argument(
        "--group_by_parent_dir",
        default=False,
        action="store_true",
        help="Group by parent directory",
    )
    search_parser.add_argument(
        "--group_by_extension",
        default=False,
        action="store_true",
        help="Group by file extension",
    )
    search_parser.add_argument(
        "--group_by_created_month_year",
        default=False,
        action="store_true",
        help="Group by created year/month",
    )

    # web parser
    web_parser = subparsers.add_parser(
        "web",
        help="Make http request to given url and capture/print response",
        description="Web Request",
    )
    web_parser.add_argument(
        "url",
        nargs="?",
        default="/",
        type=str,
        help="Provide full url for given resource",
    )
    web_parser.add_argument(
        "--method",
        nargs="?",
        default=DEFAULT_METHOD,
        choices=ALLOWED_METHODS,
        help="HTTP method for request",
    )
    web_parser.add_argument(
        "--headers",
        nargs="?",
        type=dict_or_none,
        help="Optionally you can pass dict of additional headers for the request",
    )
    web_parser.add_argument(
        "--data",
        nargs="?",
        type=dict_or_none,
        help=(
            "If method is not GET|DELETE|OPTIONS, "
            "you can pass data to be sent to the server"
        ),
    )
    web_parser.add_argument(
        "--params",
        nargs="?",
        type=dict_or_none,
        help="Optionally you can pass query string params",
    )
    web_parser.add_argument(
        "--with_csrf",
        default=False,
        action="store_true",
        help="Send CSRF token headers and parameter if set",
    )

    # stats parser
    stats_parser = subparsers.add_parser(
        "stats",
        help="Give statistical information about csv file",
        description="Stats",
    )
    stats_parser.add_argument(
        "--filepath",
        type=str,
        required=True,
        help="CSV filepath",
    )
    stats_parser.add_argument(
        "--column",
        type=str,
        required=True,
        help="Column to generate statistics from",
    )

    return mtool_parser.parse_args()


def execute_search_cmd(parsed_args):
    generator = substring_search(parsed_args.source, parsed_args.substring)
    dict_args = vars(parsed_args)
    do_grouping = any(
        dict_args.get(arg)
        for arg
        in set(dict_args.keys())
        if arg.startswith("group")
    )
    if not do_grouping:
        for result in generator:
            print(result)
    else:
        if parsed_args.group_by_extension:
            key_fn = lambda p: os.path.splitext(p)[1].lstrip(".")
            group = "Extension"
        elif parsed_args.group_by_created_month_year:
            def key_fn(p):
                dt_obj = dt.fromtimestamp(os.stat(p).st_ctime)
                return (dt_obj.year, dt_obj.month)
            group = "Created (year, month)"
        else:
            key_fn = os.path.dirname
            group = "Parent directory"

        for key, files in groupby(generator, key_fn).items():
            print(f"{group}: {key!r}")
            for file in files:
                print(file)
            print()


def execute_web_cmd(parsed_args):
    data = vars(parsed_args)
    del data["cmd"]
    data["path"] = data["url"]
    del data["url"]
    # print(data)
    response = make_request(**data)


def execute_stats_cmd(parsed_args):
    show_stats(parsed_args.filepath, parsed_args.column)


def main():
    parsed_args = cli()

    if parsed_args.cmd == "search":
        execute_search_cmd(parsed_args)
    elif parsed_args.cmd == "web":
        execute_web_cmd(parsed_args)
    elif parsed_args.cmd == "stats":
        execute_stats_cmd(parsed_args)

if __name__ == '__main__':
    main()