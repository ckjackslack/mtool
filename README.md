# mtool

A small "multi-tool handy command aggregator": one CLI that bundles a few
everyday developer helpers as subcommands.

| command  | what it does |
|----------|--------------|
| `search` | recursively list files whose path contains a substring, optionally grouped by parent dir / extension / month |
| `stats`  | shape and per-column statistics of a CSV file (numeric: mean/median/stdev/min/max; text: most common values) |
| `web`    | tiny curl-like HTTP client with JSON body, headers, query params, optional Django-style CSRF token; pretty-prints JSON |
| `gencsv` | generate a synthetic employee CSV with Faker (sample input for `stats`) |
| `serve`  | run a toy in-memory JSON API (`/`, `/hello/<name>`, `/people`) to try `web` against |

It started in 2023 as a single-directory prototype (`src/main.py`, run from inside
`src/`). This version is a rework of it as an installable package. The commands and
their scope are the same, and the git history keeps the original.

## Install

Requires Python >= 3.10. The core (`search`, `stats`, `web`) has no dependencies.

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -e .            # core only
pip install -e '.[all]'     # + Faker (gencsv) and Flask (serve)
pip install -e '.[dev]'     # + pytest
```

`mtool ...` and `python -m mtool ...` are equivalent.

## Usage

`mtool --help` shows the command list, `mtool <command> --help` shows one command's
options, and `mtool --help-all` shows everything at once.

### stats

```console
$ mtool stats examples/employee.csv -c age -c position
Shape: 50 rows x 5 columns

age (numeric)
  count: 50  missing: 0  unique: 32
  mean: 43.08  median: 41  stdev: 13.16
  min: 20  max: 65

position (text)
  count: 50  missing: 0  unique: 49
  top: 'Retail merchandiser' x2, 'Accountant, chartered public finance' x1, 'Advice worker' x1
```

- Leave out `-c` to summarise every column.
- `--json` gives machine-readable output.
- `-d ';'` sets another delimiter.
- `-` as the file reads from stdin.

A column is numeric when every non-empty value parses as a number. Malformed CSV is
reported, not crashed on:

```console
$ mtool stats old_employee.csv     # the prototype's original, badly quoted file
mtool: error: old_employee.csv: line 2: expected 5 fields, got more (unquoted delimiter inside a value?)
$ mtool stats examples/employee.csv -c salary
mtool: error: unknown column 'salary'; available: full_name, age, phone, position, company
```

### search

```console
$ mtool search src -s .py                 # list matching paths
src/mtool/__init__.py
src/mtool/__main__.py
src/mtool/cli.py
...
$ mtool search src -s .py -g ext -c       # counts per extension
     8  py
     8  pyc
$ mtool search src -g parent -s gen       # grouped listing
Parent directory: src/mtool (1)
  src/mtool/gencsv.py
...
```

Options:

- `-i`: case-insensitive matching.
- `-a`: print absolute paths. The substring is matched against the path as it is printed.
- `--hidden`: include dot-files and dot-directories (skipped by default).
- `-g month`: group by creation month where the OS records it (macOS/BSD), otherwise by modification month.

### web + serve

```console
$ mtool serve --port 8000 &               # needs mtool[server]
$ mtool web /people -X POST -d '{"name": "Alice"}'
POST http://localhost:8000/people 201 CREATED

{
    "id": 4,
    "name": "Alice"
}
$ mtool web /people -X POST -d '{"name": "alice"}'; echo $?
POST http://localhost:8000/people 409 CONFLICT

{
    "error": "Given name already exists."
}
1
$ mtool web /hello/world
GET http://localhost:8000/hello/world 200 OK

Hello, World!
$ mtool web /         # with the server stopped
mtool: error: cannot reach http://localhost:8000/: [Errno 111] Connection refused
```

Options:

- `-H 'Name: value'` adds a header (repeatable).
- `-q key=value` adds a query parameter (repeatable).
- `-d JSON` sets the request body.
- `-v` also prints the headers sent and received.
- `-t SECONDS` sets the timeout.
- `--csrf` first GETs the base URL, then sends its `csrftoken` cookie back as the
  `X-CSRFToken` header and the `csrfmiddlewaretoken` parameter.

### gencsv

```console
$ mtool gencsv -n 50 --seed 2023 -o examples/employee.csv    # needs mtool[gen]
wrote 50 rows to examples/employee.csv
```

The output columns are `full_name, age, phone, position, company`. Other options are
`--locale de_DE`, `--min-age` and `--max-age`. Without `-o` the CSV goes to stdout.
`examples/employee.csv` was produced by exactly the command above, so it is entirely
synthetic Faker data and contains no real people.

## Configuration

| setting | how |
|---------|-----|
| base URL for relative `web` URLs | `--base-url`, else env `MTOOL_BASE_URL`, else `http://localhost:8000` |
| server bind address | `mtool serve --host 127.0.0.1 --port 8000` |
| Faker locale / seed | `mtool gencsv --locale ... --seed ...` |

Exit codes:

- `0`: success.
- `1`: runtime error (missing file, bad CSV, connection refused, HTTP status >= 400).
- `2`: bad command-line usage.

## Design

```
src/mtool/
  cli.py     argparse parser, argument validation, maps errors to exit codes
  search.py  iter_files (filesystem) + pure filter/group/format functions
  stats.py   load_table (csv parsing) + pure summarize/format functions
  web.py     pure build_request/resolve_url/format_response + Transport protocol
             (UrllibTransport for real HTTP, fakes in tests)
  gencsv.py  generate_rows(provider) + write_csv; Faker is just one provider
  server.py  PeopleStore (plain Python) + create_app() Flask factory
```

Side effects (filesystem walk, HTTP, Faker, Flask) sit behind small seams.
`mtool.cli.main(argv, out=..., transport=..., provider=..., env=..., stdin=...)`
accepts fakes for each of them, which is how the CLI tests run without a network.
Every server app instance gets its own in-memory store.

## Tests

```sh
pip install -e '.[dev]'
pytest
```

The suite has 142 tests. They use `tmp_path` directory trees, a fake HTTP transport,
a monkeypatched `urlopen`, a stub Faker provider and Flask's test client. They make
no network calls and don't read or write anything outside temporary directories.

## Known limitations

- `stats` loads the whole CSV into memory. It is meant for small and medium files.
- `web` sends request bodies only as JSON. Form encoding, file uploads, auth helpers,
  redirect control and cookie jars are out of scope.
- `serve` is the Flask development server with in-memory data that is lost on exit.
  It is a demo target, not a real service.
- `--csrf` follows the Django cookie and header names. It is tested with fakes only,
  not against a real Django site.
- On Linux `search -g month` uses modification time, because creation time isn't
  available through `os.stat`.
