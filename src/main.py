#!/usr/bin/python3
import sys
sys.dont_write_bytecode = True

import argparse
from pathlib import Path

from constants import (
    ALLOWED_METHODS,
    BASE_URL,
    DEFAULT_METHOD,
)
from subcommands.search import substring_search
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
        help="Optionally you can pass query string params"
    )
    web_parser.add_argument(
        "--with_csrf",
        default=False,
        action="store_true",
        help="Send CSRF token headers and parameter if set",
    )

    return mtool_parser.parse_args()


def main():
    parsed_args = cli()

    if parsed_args.cmd == "search":
        for result in substring_search(parsed_args.source, parsed_args.substring):
            print(result)
    elif parsed_args.cmd == "web":
        data = vars(parsed_args)
        del data["cmd"]
        data["path"] = data["url"]
        del data["url"]
        # print(data)
        response = make_request(**data)


if __name__ == '__main__':
    main()