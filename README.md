# mtool

> **DRAFT** - initial assessment of the 2023 prototype. Not finished yet.

## What this seems to be

A "multi-tool handy command aggregator" (from `pyproject.toml`): one argparse CLI
(`src/main.py`) that gathers small everyday developer helpers as subcommands:

- `search` - walk a directory tree, list files whose absolute path contains a
  substring, optionally grouped by parent directory, extension or ctime month.
- `stats` - load a CSV file and print its shape plus mean/max/min of one column.
- `web` - a tiny curl-like HTTP client (method, JSON headers/params/body,
  optional Django-style CSRF token) that pretty-prints JSON responses.

Supporting pieces: `src/server.py` is a toy Flask JSON API (`/`, `/hello/<name>`,
`/people`) to point `web` at, and `src/gencsv.py` uses Faker to generate a
sample `data/employee.csv` to point `stats` at. A custom `--help` action prints
help for every subcommand at once.

## Current state

What works:

- `search` works (listing and the three grouping modes).
- `stats` works for an integer column (e.g. `age`).
- `server.py` runs and its endpoints behave as written.

What is broken / missing:

- Must be run from inside `src/` (`python main.py`); imports are bare
  (`from constants import ...`) and `subcommands/__init__.py` hacks `sys.path`.
  Not installable, no entry point.
- `web` ignores the "full url" it advertises: the base URL is hardcoded to
  `http://localhost:8000` and the argument is appended as a path.
  `--with_csrf` is broken (`.groups(1)` returns a tuple, and the token is added
  to params after the URL was already built).
- `gencsv.py` writes CSV by hand using Python `repr()` quoting, so the committed
  `employee.csv` is malformed: company names like `'Blake, Bailey and Kane'`
  split into extra columns and every value keeps literal single quotes.
- `stats` crashes with a traceback on any non-integer column, silently does
  nothing for an unknown column, and has no float/empty-value handling.
- Running with no subcommand prints nothing; bad `--source` raises a raw
  `ValueError` instead of an argparse error.
- `requirements.txt` pins wheels via `file:///home/ckjackslack/.cache/pypoetry/...`
  (machine-specific paths); Poetry metadata targets Python 3.8.
- No tests, no README, no .gitignore.

Sensitive data: none found. `employee.csv` is synthetic Faker output (Faker
suffixes like "MD"/"PhD", invalid area codes such as `097-`/`043.`, Faker job
titles and "X and Sons"/"X-Y" companies), not real people.

## TODO / to be finished

- [ ] Redesign as an installable package with a `mtool` entry point
- [ ] Fix `web`, `stats`, `gencsv`; regenerate a valid sample CSV
- [ ] Usage docs, tests
