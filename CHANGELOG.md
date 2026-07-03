# Changelog

All notable changes to Sonne are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor versions may contain breaking changes, each called out below).

## [Unreleased]

### Added
- MIT `LICENSE` file (the license was previously claimed but not shipped).
- `pyproject.toml`-based packaging (replaces `setup.py`); wheels now include
  the bundled site templates' `sonne.yaml`, `scripts/`, and `data/` files as
  well as `schemas/sonne.schema.json`.
- pytest test suite (characterization + regression) and GitHub Actions CI
  (Linux 3.9/3.11/3.13, Windows 3.13, lint, package smoke test).
- `CONTRIBUTING.md`, `CHANGELOG.md`, and `docs/BACKLOG.md` (issue-ready
  backlog for contributors).

### Changed
- Minimum supported Python is now 3.9 (3.8 is end-of-life).
- Dev tooling consolidated on `ruff` (replaces flake8/black/isort extras).

### Deprecated

### Fixed

### Security
- Documented that `scripts/*.py` data scripts execute with full process
  privileges at build time: only build sites you trust.

## [0.3.2] and earlier

Pre-changelog history; see `git log`.
