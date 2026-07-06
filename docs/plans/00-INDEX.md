# Implementation plans — priority order

Full plans for the items in [../BACKLOG.md](../BACKLOG.md) plus the templating
consolidation. Each plan is self-contained: goal, design decisions (made, not
open), files to touch, test plan, and compatibility notes. Grab one, open a
PR, keep the suite green.

Ground rules that apply to every plan (see also `/CLAUDE.md`):

- Config keys change in lockstep: `DEFAULT_CONFIG` + `sonne/schemas/sonne.schema.json`
  + `README.md` + `CHANGELOG.md`. Renames/removals go through `sonne/core/deprecations.py`.
- Behavior changes ship with updated characterization tests in the same PR.
- Windows is first-class: path comparisons by components, web paths normalized
  with `sonne.utils.path_utils.normalize_web_path`.

| # | Plan | Backlog | Size | Why this priority |
|---|------|---------|------|-------------------|
| 01 | [Jinja consolidation](01-jinja-consolidation.md) | #8 (absorbs) | L | Defines the authoring model everything else documents; deletes a dead subsystem |
| 02 | [Dithered-convention unification](02-dithered-convention-unification.md) | #13 | M | Removes the last dual-convention trap before more image work lands |
| 03 | [Blog image caching](03-blog-image-caching.md) | #2 | M | Biggest rebuild-time win on low-power hardware |
| 04 | [Single-parse HTML pipeline](04-single-parse-html-pipeline.md) | #3 | M | Perf + removes a class of parse/serialize drift |
| 05 | [Vectorize LAB dither](05-vectorize-lab-dither.md) | #1 | S/M | Makes color_lab usable (minutes → seconds) |
| 06 | [Path normalization unification](06-path-normalization.md) | #9 | S | Kills duplicated logic before it diverges again |
| 07 | [Config discovery contract](07-config-discovery.md) | #10 | S | Predictable project detection for new users |
| 08 | [Dead config keys](08-dead-config-keys.md) | #12 | S | Honesty of the config surface |
| 09 | [Extension-set constants](09-extension-sets.md) | #11 | S | One definition; unlocks new formats deliberately |
| 10 | [Date formats & i18n groundwork](10-date-format-i18n.md) | #5 | S/M | First non-English site becomes possible |
| 11 | [Word-based excerpts](11-word-excerpts.md) | #7 | S | Matches user expectations; tiny |
| 12 | [Configurable constants](12-configurable-constants.md) | #6 | S | Sweep of remaining magic numbers |
| 13 | [Related-posts performance](13-related-posts-performance.md) | #4 | S | Only matters at scale; cheap to do right |
| 14 | [Showcase template cleanup](14-showcase-template-cleanup.md) | #14 | S | Good first issue; docs-adjacent |

Backlog #8 (safe_builtins honesty) does not get its own plan: plan 01 deletes
the embedded-Python executor outright, which resolves it.
