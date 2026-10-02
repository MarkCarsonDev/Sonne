# Implementation plans

Plans for the open items in [../BACKLOG.md](../BACKLOG.md). Each plan gives
the goal, the design decisions, the files to touch and a test plan.

The plans were written against 0.4.0. The code has been refactored since:
function names and line references in them are out of date, so read the
"Status" column and the current code before starting.

Rules that apply to every plan (see also `/CLAUDE.md`):

- Config keys change in lockstep: `DEFAULT_CONFIG` + `sonne/schemas/sonne.schema.json`
  + `README.md` + `CHANGELOG.md`. Renames and removals go through
  `sonne/core/deprecations.py`.
- Behavior changes ship with updated characterization tests in the same PR.
- Windows is first-class: compare paths by components, and normalize web
  paths with `sonne.utils.path_utils.normalize_web_path`.

| # | Plan | Size | Status |
|---|------|------|--------|
| 04 | [Single-parse HTML pipeline](04-single-parse-html-pipeline.md) | M | Mostly done: a post's HTML is parsed once for size data, and the dithering assets are linked instead of inlined. Left: `TemplateProcessor.finish_page` parses every page when dithering is on. |
| 06 | [Path normalization](06-path-normalization.md) | S | Partly done: `SiteGenerator` uses `Config.normalize_paths`. Left: `normalize_paths` still creates the output and cache directories. |
| 08 | [Dead image config keys](08-dead-config-keys.md) | S | Open. `images.lazy_loading` and `images.grayscale_before_dither` still do nothing. |
| 10 | [Date formats and i18n groundwork](10-date-format-i18n.md) | S/M | Open. |
| 11 | [Word-based excerpts](11-word-excerpts.md) | S | Open. |
| 12 | [Configurable constants](12-configurable-constants.md) | S | Partly done: the constants are named. Left: the config keys (`images.quality`, `blog.related_posts`, `blog.drafts_directory`). |
| 13 | [Related-posts performance](13-related-posts-performance.md) | S | Partly done: tag sets are computed once. Left: scoring is still every post against every other, and `related_posts` holds full post dicts. |
| 14 | [Showcase template cleanup](14-showcase-template-cleanup.md) | S | Partly done: category pages come from the built-in templates, and the content uses real Jinja. Left: the showcase nav hardcodes `.html` URLs and sets no `url_style`; no zero-warnings scaffold test. |

Finished and removed (see the CHANGELOG and `git log`): 01 Jinja
consolidation, 03 blog image caching, 02 dithered-convention unification, 05 faster LAB dither,
07 config discovery contract, 09 extension-set constants.
