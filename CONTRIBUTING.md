# Contributing to Sonne

Sonne is a small codebase (about 8k lines of Python) and aims to stay small.

## Getting set up

```bash
git clone https://github.com/MarkCarsonDev/Sonne.git
cd Sonne
python -m venv .venv
# Windows: .venv\Scripts\activate    POSIX: source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.9+ is required. Windows is a first-class platform: CI runs the test
suite there, and path handling must work with both separators.

## Running things

```bash
pytest                      # full test suite
pytest tests/unit           # fast unit tests only
ruff check .                # lint
ruff format --check .       # formatting
pyright                     # type check (what VS Code/Pylance shows)
```

CI runs all four, on Linux (Python 3.9, 3.11, 3.13) and Windows (3.13).
Run all four locally and get them green before you push: CI is a backstop,
not the place to find out. `pip install -e ".[dev]"` installs the exact
ruff and pyright versions CI uses, so local and CI results match.

To try your changes against a real site:

```bash
sonne new -p demo-site -t blog
cd demo-site
sonne build
sonne serve
```

## How we work

- **Tests first.** The suite is a characterization suite: it pins current
  behavior so refactors are safe. If you fix a bug, add a failing test in the
  same PR. If you intentionally change behavior, update the pinned test and
  say so in the PR description and `CHANGELOG.md`.
- **Small PRs.** One logical change per PR; avoid drive-by reformatting.
- **Config keys change in lockstep.** Any config key you add, rename, or
  remove must be updated in all of: `DEFAULT_CONFIG` (`sonne/core/config.py`),
  `sonne/schemas/sonne.schema.json`, `README.md`, and `CHANGELOG.md`. Tests
  check the first three against each other. Renames and removals go through
  `sonne/core/deprecations.py` so old configs keep working with a warning.
- **Compatibility.** Existing sites must keep building. Behavior changes need
  a deprecation path or a clear CHANGELOG "Changed" entry.
- **Changelog.** Every user-visible change gets a line under `[Unreleased]`.
- **README.** It documents what the code does now. When you change behavior
  it describes, change the README in the same PR.

Ideas for what to work on are in [docs/BACKLOG.md](docs/BACKLOG.md).

## Security model

Building a Sonne site executes code: any `*.py` file directly in the site's
`scripts/` directory, and a `footer.py` in its data folder, runs with full
process privileges during `sonne build` and `sonne serve` (the same trust
model as Jekyll plugins). Content rendered through Jinja
(`content.render_jinja`) is a template, not a sandbox. Never build a site you
don't trust, and never point CI at untrusted site content. Don't add code
paths that execute more site files than these without documenting them.

## Code style

- Google-style docstrings; module docstring at the top of every file.
- Library code logs via `logging.getLogger('sonne')`, never `print`. The CLI
  may use `rich`/`click.echo` (mind Windows consoles: plain ASCII output).
- Config access goes through `config.get('section', 'key', default=...)`.
- The package version lives only in `sonne/__init__.py`. Never hardcode it.
- Type hints on public signatures; the code must pass `pyright`.
- One slug function: `sonne/utils/text.py::slugify`.
- Compare paths by components (`pathlib`, `os.path.relpath`), never with
  `str.startswith` on path strings.
