# 06 — One owner for path normalization

**Size:** S · **Backlog #9** · **Breaking:** none

## Context

`Config.normalize_paths` and `SiteGenerator.__init__` independently implement
relative→absolute resolution plus mkdir of output/cache. The Config version
is effectively dead (SiteGenerator never calls it), and "normalize" having a
mkdir side effect is a trap.

## Design

1. `Config.normalize_paths(base_dir)` becomes the single implementation and
   **loses the mkdir side effect** — it only resolves paths (including
   filling defaults for missing keys, absorbing SiteGenerator's
   `default_paths` table).
2. `SiteGenerator.__init__` calls it, then creates `output`/`cache` dirs
   itself (explicit `ensure_dir` calls — creation is a generator concern).
3. Delete the duplicated block in `SiteGenerator.__init__`, including its
   direct `self.config.config['paths']` reaches (violates the config-access
   rule in CLAUDE.md).

## Files

`sonne/core/config.py`, `sonne/core/site_generator.py`, `CHANGELOG.md`
(internal note).

## Tests

- Existing integration suite is the main guard (paths feed everything);
- unit: `normalize_paths` fills defaults, resolves relative against
  base_dir, leaves absolutes alone, creates nothing on disk;
- generator still creates output/cache before first use.
