# 07 — Config discovery / project detection contract

**Size:** S · **Backlog #10** · **Breaking:** stricter project detection (deliberate, CHANGELOG "Changed")

## Context

`is_sonne_directory` accepts any directory containing `content/`,
`templates/`, or `static/` — no config needed — while `Config._find_config`
walks up 3 parent levels (now warning when it adopts a parent's config). The
two disagree about what a project is; the parent walk plus loose detection
lets `sonne build` in a random directory "succeed" against defaults.

## Design

Contract: **a Sonne project is a directory whose config file is in that
directory or an ancestor within SEARCH_DEPTH; a bare content/ dir is a hint,
not a project.**

1. `path_utils.CONFIG_SEARCH_DEPTH = 3` named constant; `_find_config` uses it.
2. `is_sonne_directory` requires a config file (same `CONFIG_FILENAMES`,
   same upward walk, same depth — share one helper `find_config_file(base)`
   in `path_utils` that returns the path, used by both `Config` and
   `is_sonne_directory`). The "typical dirs" check downgrades to shaping the
   error message ("found content/ but no sonne.yaml — create one or run
   sonne new").
3. `check_sonne_directory`'s guidance text updated accordingly.

## Files

`sonne/utils/path_utils.py` (shared `find_config_file`),
`sonne/core/config.py` (`_find_config` delegates),
`sonne/cli/commands.py` (error copy), tests, `README.md` note,
`CHANGELOG.md` "Changed".

## Tests

- dir with only `content/` → build refuses with the improved message
  (updates the pinned `test_true_with_only_content_dir` — deliberate
  behavior change, same PR);
- config in parent within depth → detected, warning fires (existing test);
- config beyond depth → not a project.

## Compatibility

Sites that relied on building with zero config and only a content dir now
get an actionable error; `sonne new` output always includes a config, so
bundled-template users are unaffected.
