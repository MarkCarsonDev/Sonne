# Changelog

All notable changes to Sonne are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor versions may contain breaking changes, each called out below).

## [0.4.0] - 2026-07-05

Open-source readiness release: test suite, CI, packaging modernization, and a
sweeping bug-fix pass. No config file changes are required to upgrade;
behavior changes are listed under "Changed".

### Added
- MIT `LICENSE` file (the license was previously claimed but not shipped).
- pytest test suite (characterization + regression, 90+ tests) and GitHub
  Actions CI (Linux 3.9/3.11/3.13, Windows 3.13, ruff lint, package smoke
  test). `CONTRIBUTING.md`, `docs/BACKLOG.md`, and this changelog.
- `pyproject.toml`-based packaging (replaces `setup.py`). Wheels now include
  the bundled templates' `sonne.yaml`, `scripts/`, and `data/` files plus
  `schemas/sonne.schema.json`; `MarkupSafe` is declared explicitly.
- `sonne build --yes/-y` to continue past confirmation prompts (CI-friendly);
  template-error prompts now abort with a clear message instead of hanging
  when there is no TTY.
- `sonne/core/deprecations.py`: renamed config keys are aliased with a
  once-per-key warning. `images.parallel_processing` → `images.parallel`,
  `images.max_workers` → `images.parallel_workers` (the old, schema-only
  names never had any effect).
- Config validation: `blog.posts_per_page >= 1`, `serve.port` range, and a
  warning for an `environment` with no `url_style` entry.
- Build warnings for output collisions (two pages writing the same file) and
  for configs adopted from a parent directory.
- JSON schema now covers all keys the code reads: `site.nav`, `site.footer`,
  `site.weather`, `blog.rss.*`, `blog.date_archives`, `blog.archive_template`,
  `images.only_used`/`dither_method`/`dither_colors`/`dither_formats`/
  `dither_sizes`/`dither_cover_images`/`blog_*_max_width`/`webp_method*`/
  `parallel`/`parallel_workers`, `serve`, `solar`, `build.show_page_size`,
  `variables.preserve_prior`.

### Changed
- Minimum supported Python is now 3.9 (3.8 is end-of-life).
- **Lists in user config now replace defaults** instead of extending them:
  `images.formats: [png]` finally means `[png]`, not `[webp, png, png]`.
- **`variables.preserve_prior` is now honored** (it was dead config). By
  default builds start fresh and `sonne_variables.json` is neither read nor
  written; when enabled, only script-produced variables persist — derived
  state (posts, taxonomies) never does.
- **One slugify everywhere** (`sonne/utils/text.py`): post URLs, taxonomy
  pages, and the Jinja `slugify` filter now agree. Tag links for tags with
  underscores previously 404'd; those tag pages keep their URLs and the
  links now match them.
- Filename-derived slugs strip the Jekyll date prefix: a post file
  `2025-01-01-title.md` without front matter now lands at
  `/blog/2025/01/01/title/` instead of `/blog/2025/01/01/2025-01-01-title/`.
- Static images are now actually dithered when `images.dither: true` (a
  positional-default bug disabled static dithering entirely), and dithered
  variants for content images are no longer produced when `dither: false`.
- Regular (non-blog) pages no longer have `<img>` tags rewritten to
  blog-style `dithered/` paths that never exist for them.
- Dithering CSS/JS are emitted only when `images.dither` is enabled, are
  always refreshed from the packaged copies (previously stale-on-upgrade),
  and the 270-line inline duplicate was removed.
- RSS feeds are valid XML: fields are escaped, CDATA removed, and
  `pubDate`/`lastBuildDate` carry the real local UTC offset.
- `page.url` for blog posts is the post's permalink (was the content-relative
  source path — wrong canonical/self links).
- The image cache key includes all dithering/encoding settings (cache format
  v2) — the first build after upgrading reprocesses images once.
- `sonne new` preserves the template's own `sonne.yaml` (name substituted)
  instead of overwriting it with the entire merged default config.
- `sonne serve`: watch rebuilds re-read the config (edits to `sonne.yaml`
  now take effect), the server no longer chdirs into the output directory,
  restarts don't fail with "Address already in use", and `port: 0` /
  explicit hosts are respected.
- The reported generator version now tracks `sonne.__version__` (it was
  frozen at a hardcoded fallback due to a broken import).
- CLI output uses plain ASCII (emoji crashed cp1252 Windows consoles);
  `build` only prints tracebacks with `-v` (matching `new`/`serve`).
- Solar/portfolio special-casing removed from core: `battery`/`weather`/
  `forecast` variables and `projects` data flow through the generic script
  and data mechanisms (templates unaffected).

### Fixed
- Loading a config no longer mutates the global defaults (long-running
  `serve` sessions compounded corrupted state across rebuilds).
- `content/blog-archive/` (and any sibling directory sharing the blog dir's
  name prefix) is rendered instead of silently skipped.
- A post named `year_end_drafts.md` is no longer treated as a draft
  (`_drafts` now matches path components only).
- `../images/…` and dot-prefixed paths in image references are no longer
  corrupted by `lstrip('./')`.
- `images.only_used: true` no longer skips every static image; absolute
  `/images/...` references and template references now count as "used",
  and quoted `cover_img` values are matched.
- `scripts/footer.py` executed twice per build; it now runs once.
- User data files whose entries contain a `data` key are no longer mangled
  by the legacy variable-file format detection.
- Invalid `blog.url_pattern` placeholders log an error naming the
  placeholder and fall back to the default pattern instead of silently
  dropping every post; unparseable dates warn before falling back to file
  timestamps; `posts_per_page: 0` no longer silently produces no index.
- Multiple images in one paragraph are no longer misplaced by the figure
  rewrite; build progress no longer overshoots its step count when the
  blog is disabled.

### Security
- Documented the trust model: `scripts/*.py` execute with full process
  privileges at build time (README "Security" section, CONTRIBUTING).
  Embedded Python stays off by default; its builtin restriction is
  documented as best-effort, not a sandbox.

## [0.3.2] and earlier

Pre-changelog history; see `git log`.
