# Contributing to Sonne

Thanks for helping out! Sonne is a small codebase (~5k lines) and aims to stay
that way — minimalist output, minimalist internals.

## Getting set up

```bash
git clone https://github.com/MarkCarsonDev/Sonne.git
cd Sonne
python -m venv .venv
# Windows: .venv\Scripts\activate    POSIX: source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.9+ is required. Windows is a first-class platform — CI runs the test
suite there, and path handling must work on both separators.

## Running things

```bash
pytest                      # full test suite
pytest tests/unit           # fast unit tests only
ruff check .                # lint
ruff format --check .       # formatting
```

To try your changes against a real site:

```bash
sonne new -p /tmp/demo -t blog
cd /tmp/demo
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
  remove must be updated in ALL of: `DEFAULT_CONFIG` (`sonne/core/config.py`),
  `sonne/schemas/sonne.schema.json`, `README.md`, and `CHANGELOG.md`.
  Renames go through the deprecation shim (`sonne/core/deprecations.py`) so
  old configs keep working with a warning.
- **Compatibility.** Existing sites must keep building. Behavior changes need
  a deprecation path or a clear CHANGELOG "Changed" entry.
- **Changelog.** Every user-visible change gets a line under `[Unreleased]`.

## Security model (read this)

Building a Sonne site executes code: any `*.py` file in the site's `scripts/`
directory runs with full process privileges during `sonne build`/`serve`
(same trust model as Jekyll plugins or Gatsby config). Never build a site you
don't trust, and never point CI at untrusted site content. The embedded
Python feature (`security.allow_embedded_python`) is off by default and its
builtin restriction is best-effort, not a sandbox.

## Code style

- Google-style docstrings; module docstring at the top of every file.
- Library code logs via `logging.getLogger('sonne')` — never `print`. The CLI
  may use `rich`/`click.echo` (with plain fallbacks; mind Windows consoles).
- Config access goes through `config.get('section', 'key', default=...)`.
- The package version lives only in `sonne/__init__.py` — never hardcode it.
- Type hints on public signatures; not enforced by CI (yet).
