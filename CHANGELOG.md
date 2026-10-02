# Changelog

All notable changes to Sonne are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor versions may contain breaking changes, each called out below).

## [Unreleased]

### Added
- **Variables in content**: content files can be rendered through Jinja
  before markdown conversion — variables, loops, filters, includes. Opt-in
  via `content.render_jinja: true` or per-file `jinja: true|false` front
  matter (the per-file key wins either way).
- **Script-registered Jinja extensions**: data scripts get `sonne_filter(name, fn)`
  and `sonne_global(name, value)` alongside `sonne_var`, making real Python
  functions callable from every template and (with content Jinja) every
  content file. Names shadowing built-ins are ignored with a warning.
- `sonne.script_api`: data scripts can `from sonne.script_api import
  sonne_var, get_post, sonne_filter, sonne_global`, so editors,
  Pylance/pyright and ruff resolve them. The functions are typed and
  documented, work while Sonne runs the script during a build, and raise
  `RuntimeError` elsewhere. Scripts using them without the import keep
  working.
- `all_pages` template variable: every content page (front matter plus
  `title`, `url`, `section`, `source_path`), sorted by URL, so templates
  can list non-blog pages, e.g. `{% for p in all_pages if p.section ==
  'projects' %}`. Blog posts stay in `all_blog_posts`. Page URLs and output
  paths now come from one function, so they can no longer disagree.
- `sonne_config(*keys, default=None)` in `sonne.script_api` (and as an
  injected global): data scripts read the running build's configuration,
  e.g. `sonne_config("site", "base_url")`, instead of locating and
  re-reading the config file themselves. Values include defaults, and the
  result is a copy, so scripts can't change the build's configuration.
- Build-time accessibility checks for machine-detectable WCAG 2.2 failures:
  images without alt text, links and buttons without an accessible name,
  unlabelled form fields, a missing page language or title, duplicate ids,
  positive `tabindex`, and skipped heading levels (advisory). Findings are
  reported per page with the WCAG criterion and a fix hint; totals appear
  in the build summary. New setting `build.accessibility_checks`: `warn`
  (default), `error` (fail the build, for CI) or `off`;
  `sonne build --a11y-strict` is `error` for one build.
- The blog, portfolio and minimal starter templates and the showcase
  example meet a WCAG 2.2 AA baseline: skip link, labelled landmarks,
  `aria-current`, one `<h1>` per page, meaningful link text, visible focus,
  forced-colours and reduced-motion support, AA text contrast, and
  keyboard-accessible menus, filters, gallery and form errors. Cover images
  take alt text from `cover_alt` front matter.
- "Always show original images": a visitor setting, remembered in the
  browser, that shows every dithered image's original. `dithering.js` adds
  a small button on pages with dithered images unless the template provides
  its own control (any element with `data-sonne-original-images`); scripts
  can use `window.sonneDithering`. Originals are the default for visitors
  whose system asks for more contrast or uses forced colours.
- A built-in blog index template (fallback) with accessible pagination,
  for sites without their own `blog_list.html`.
- Template helpers `blog_url()`, `tag_url()`, `category_url()` and
  `archive_url()` for linking to blog pages. They follow `blog.directory`
  and `url_style` and slugify terms like the pages themselves. The bundled
  blog and portfolio templates and the showcase example use them.
- Built-in tag, tags, category, categories and archive templates: sites
  without their own get working listing pages, rendered inside the site's
  `base.html` (or a minimal page if there is none), instead of an
  "Untitled" placeholder.
- The `data` namespace: every data file is available in templates as
  `data.<file name>` and every script variable as `data.<name>` (also
  `site.data.*`). New `variables.flatten_data` (default `true`) keeps the
  old flat exposure as well; set it to `false` so data and script variables
  can never replace site config. Two data files with the same name in
  different folders now warn.
- `sonne migrate` updates a site's config file for deprecated keys: renames
  them, removes no-effect or removed ones, and shows a diff. Dry run by
  default; `--write` applies it and keeps a `.bak` backup. YAML comments and
  layout are preserved when possible (it says clearly when they can't be);
  JSON configs are supported.
- `sonne serve --dev` serves the development environment, like
  `sonne build --dev`.
- `sonne serve --watch` warns you to restart it when Sonne itself was
  upgraded or edited while the server was running.
- All starter templates (blog, portfolio, minimal, solar) load
  `dithering.css`/`dithering.js` when `images.dither` is on, so visitors
  can switch between dithered and original images.
- `get_variable(name, default=None)` in `sonne.script_api`: data scripts
  read build data (`all_pages`, `all_blog_posts`, `tags`, data files,
  config values, earlier scripts' variables). It returns a copy.
- `dither_image(image)` in `sonne.script_api`: dither an in-memory Pillow
  image with the site's `images.dither_*` settings.
- Sonne ships a `py.typed` marker (PEP 561), so type checkers use its
  annotations.
- `ImageProcessor.dither(image)`: the supported way for data scripts to
  dither in-memory images with the site's `images.dither_*` settings.
  (`_apply_dither` keeps working.)

### Deprecated
- `/images/<name>_original.<ext>` copies of static images are still written
  for compatibility and will be removed in Sonne 0.6.0; link to
  `/images/<name>.<ext>` for the original.
- `build.incremental`, `build.show_progress` and `build.statistics` have no
  effect and will be removed. They still load, with a warning; use
  `sonne build --no-progress` / `--perf` instead.
- `security.csp` (`enabled`/`directives`) has no effect and will be
  removed; Sonne never added the policy to pages. Send a
  `Content-Security-Policy` header from your web server instead.
- Flat access to data files and script variables (mapping keys merged into
  `site`, script variables at the top level). Use `data.<name>`; set
  `variables.flatten_data: false` to opt in now. The default will become
  `false` in a future release.
- Run `sonne migrate` to see (and with `--write`, apply) the config
  changes for deprecated keys.

### Removed
- `Config.generate_csp_header()` and `Config.get_csp_meta_tag()` (unused).
- The `{+}{variable}` / `{-}{variable}` substitution syntax and the
  `{p}{# ... #}` embedded-Python blocks. These were dead code — nothing in
  the build pipeline ever invoked them, so the markers already rendered
  literally. The build now warns (once per file) when it finds them,
  pointing at the Jinja equivalent.
- The `security.allow_embedded_python` config key (it only gated the dead
  executor). Configs that still set it get a warning naming the
  replacement.
- Unused, undocumented internal helpers `file_utils.get_file_mtime`,
  `is_file_modified`, `get_all_files`, `clean_directory` and
  `path_utils.safe_join`, `get_relative_path_safe`.

### Changed
- A post's own front matter keys are available as `page.<key>` (and
  `post.<key>` in listings), as on a regular page. Before, only a fixed
  list was, and the rest were under `page.metadata`, which still works.
  Keys Sonne sets itself (`url`, `date`, `tags`, `content`, ...) win over
  front matter keys of the same name.
- **Breaking (pre-1.0):** static images keep their original at their own
  URL, and the dithered copy is `<dir>/dithered/<name>.png` (always PNG).
  Before, `/images/a.png` served the dithered image and the original was
  `/images/a_original.png`. Pages still show dithered images: every `<img>`
  pointing at an image the build dithered is rewritten to the dithered
  copy, with the original in `data-original-src`. References outside `<img>`
  (CSS `url()`, `og:image`, RSS, links from other sites) now get the
  original. The static-image cache is rebuilt once.
- The dithering styles and script are no longer inlined into every page;
  pages load `/css/dithering.css` and `/js/dithering.js` (added
  automatically when a page doesn't link them), so pages are smaller.
- The `process_image` template filter renders a plain `<img>`; pages mark
  it like any other image if the build dithered it.
- The built-in tag, category, archive and blog index templates meet WCAG
  2.2 AA: skip link, labelled navigation, term lists as real lists, "Read
  more" links that name the post, and `aria-current` pagination.
- Dithering toggles are fully visible (no longer faded), at least 24×24px,
  usable in forced-colours mode, and without animation under reduced
  motion. Blog figure captions and buttons are no longer semi-transparent.
- Blog post figures: the caption is the figure's accessible name; the
  "view original" button is named by its visible text; figures whose image
  could not be dithered no longer show a toggle that does nothing.
- The page-size note (`build.show_page_size`) is a readable line after the
  page content instead of a faint fixed label with hover-only details.
- Pages written when a template is missing or fails declare their
  language and title and escape their content.
- `solar` scaffold: WCAG 2.2 AA pass: landmarks and skip link, labelled
  navigation, a theme toggle button that follows the system colour scheme,
  AA contrast, visible focus, reduced motion, 24px targets and descriptive
  link names; `cover_alt`/`image_alt` front matter describe covers
  (otherwise decorative).
- Blog links in the bundled templates follow `url_style`: in the clean
  style they no longer end in a slash (`/blog/tags/python`, matching the
  pages' own URLs), in the html style they end in `.html`, and they follow a
  custom `blog.directory` instead of `/blog/`.
- New sites from `sonne new -t blog` / `-t portfolio` no longer include
  tag/tags/category/categories/archive templates; the built-in ones render
  identically. Existing sites' copies still take precedence.
- Script globals named `blog_url`, `tag_url`, `category_url`,
  `archive_url` or `sonne_base_template` are ignored with a warning
  (built-in names win, as for other built-ins).
- Generated listing pages name their template explicitly; template
  selection no longer depends on synthetic source-path prefixes.
- The dithered/original image toggle is a keyboard-operable button
  (labelled "Show original image", state in `aria-pressed`) with a visible
  focus ring; only the image on show is exposed to screen readers. Toggles
  in pages built by older versions are upgraded in place.
- Builds show a new "Collecting page metadata" step (one more `[n/N]`
  line).
- `solar` scaffold: data scripts read settings with `sonne_config`; the
  Projects nav link now leads to a real `/projects/` page listing the
  project pages, and `portfolio.html` shows its page body.
- Sonne requires Pillow 9.1 or newer (typed `Image.Resampling`/`Dither`/
  `Palette` enums; output is unchanged).
- The codebase type-checks with pyright in standard mode (the checker
  behind VS Code/Pylance) and lints with an expanded ruff rule set; both
  run in CI. The bundled solar and showcase scripts import the script API
  and are linted like the rest of the code.
- Error tracebacks in library code now go through the `sonne` logger
  (shown with `-vv`/debug logging) instead of being printed straight to
  stderr.
- `sanitize_filename` keeps `..` inside names (`v1..2.txt` was mangled to
  `v12.txt`); names made only of dots still become `unnamed`. Slugs are
  unaffected.
- The "could not clean" message of `sonne build --clean` names the error type.
- The "Processing images (N images)" progress line counts exactly the
  images the build processes: `static/images` files are included, hidden
  files and (with `images.only_used`) unreferenced images are left out. It
  counted every image file under `content/`.
- An image referenced more than once in a post is resized and dithered once.
- Blog errors from content Jinja are reported as such instead of as "Error
  processing images"; those posts' images are still published.
- An explicit `site.author: null` gives an empty author instead of "None".
- Images with uppercase extensions (`PHOTO.JPG`) are processed on
  case-sensitive filesystems too.
- `color_lab` dithering is about 10x faster, with identical output.
- The build report counts processed and cached images, cache hits and
  misses, static-image byte savings, and templates rendered and failed.
- `dithering.js` scans only newly added content when the page changes,
  instead of the whole document.
- README rewritten against the current code. It now covers every config
  key, config-file discovery, the three image pipelines and their output
  paths, template variables, functions and filters, the script API and
  accessibility. Corrected: Sonne is installed from GitHub (the `sonne`
  package on PyPI is an unrelated project), `sonne serve` rebuilds but does
  not reload the browser, and `-v` goes before the command
  (`sonne -v build`).
- The unreferenced `sonne/static/base.html` is removed.
- `data/footer.py` scripts can call `get_post()`, and their `footer_custom`
  is marked HTML-safe exactly like `scripts/footer.py`.
- A data script's `sonne_var()` that replaces an existing site variable (a
  site config key, data-file key or Sonne default such as `nav`) now logs a
  warning once per key per build; the value is still replaced (B18).
- `solar` scaffold: the weather data script exposes current conditions as
  `current_weather` (was `weather`, which replaced `site.weather` from
  `sonne.yaml`). Custom templates based on the solar scaffold should rename
  `weather.*` to `current_weather.*`.
- `solar` scaffold: removed the unused `solar.*` keys (`theme`,
  `contrast`, `font_size`, `reduce_motion`, `minimize_images`,
  `data_saver`, `weather_update_interval`) — nothing read them. The theme
  toggle is always in the header, the saved theme applies before first
  paint, and the JS no longer polls the nonexistent `/api/battery-status`.

### Fixed
- `sonne serve --watch` no longer rebuilds in an endless loop. watchdog 2.3
  and newer also reports files being read; the build reads the watched
  content, so each rebuild triggered the next. Only changes rebuild now.
- `cover_alt` front matter reaches the `blog` and `portfolio` starter
  templates and the showcase example as `page.cover_alt`; their post covers
  always had empty alt text. (The `solar` template already read it.)
- `portfolio` starter: the blog index and every blog post were blank (the
  templates were empty files), posts lived at `/blog/blog/<slug>/`, the
  category filter never showed any category, and four listed projects
  linked to pages that don't exist (B53).
- Showcase example: the tags index was blank (empty template), and the
  contact form's `email` id collided with a heading's id, so its label was
  ambiguous (B54). The dark-mode button now works (its script was empty),
  and the non-functional menu button is gone.
- `portfolio` starter: footer headings were invisible (same colour as the
  footer background), and the gallery lightbox added a new Escape listener
  every time it opened.
- Dithering toggles appear only on images the build actually dithered.
  `dithering.js` guessed an `_original` URL for every same-origin image, so
  images Sonne never dithered (e.g. a plain `logo.png`) got a toggle that
  showed a broken image (B52).
- Category pages rendered as a bare "Untitled" fallback page: the singular
  of `categories` was computed as `categorie`, so no template matched
  (B13). Category term pages now expose `page.category`.
- Tag and category pages said "No posts found": the bundled templates read
  top-level `tag`/`posts`, which are never set. They now use `page.tag`,
  `page.category` and `page.posts` (B14).
- Tag and category links in bundled templates used `lower|replace`, which
  diverges from the canonical slug, so tags such as "Q&A Night" linked to
  a 404. They now use the `slugify` filter (B15).
- The `blog` and `portfolio` scaffolds shipped without `archive.html` (and
  portfolio without tag/category templates), so date archives and taxonomy
  pages rendered a bare fallback page. Built-in templates now cover them
  (B16).
- Image syntax inside fenced code blocks or inline code in a blog post
  (e.g. a Markdown tutorial) is no longer treated as a real image, which
  logged a spurious "Image not found" warning per sample (B26).
- `sonne build --perf` no longer reports "Build failed" (exit 1) when
  stdout is a non-UTF-8 pipe or redirect (cp1252 on Windows); characters
  that can't be encoded print as `?`.
- The build report counts rendered pages ("Pages: Processed" was always 0)
  and rendered blog posts (the "Blog posts" line never appeared).
- `sonne build -p <site>` reports the site's own output directory; the
  "Build complete" and `--clean` messages resolved `paths.output` against
  the current directory.
- `sonne serve --watch` rebuilds for configured paths written with `/` on
  Windows, with a `./` prefix, or as absolute paths; edits under e.g.
  `content: src/pages` were silently ignored.
- `footer.py` under a relative custom `paths.data` is found relative to the
  site, not the current directory.
- `Config.save()` to an unsupported extension no longer empties the
  existing file.
- Sites without a `static/` directory no longer get `dithering.css`/`.js`
  when `images.dither` is false.
- `sonne serve --watch` no longer drops edits saved while a rebuild is
  running; it rebuilds once more afterwards (B41). It also rebuilds when
  an editor saves by writing a temp file and renaming it over the
  original (B50).
- Data scripts, data files and content pages are processed in a fixed
  alphabetical order, so a site builds the same on Windows, macOS and
  Linux (later data files override earlier ones; data files still load
  JSON, then YAML, then CSV) (B42).
- Files in hidden content folders (e.g. `content/.obsidian/`) are no longer
  published as pages, and a directory named like a page (`notes.md/`) no
  longer causes an error (B43).
- With `blog.enabled: false`, files in the blog folder are rendered as
  ordinary pages with the page template instead of not at all (B44).
- A null or empty `blog.directory` consistently means `blog`; it could turn
  the whole content folder into the blog. `validate()` reports it (B45).
- `blog: {rss: false}` turns the RSS feed off. A plain value where a
  settings section belongs (e.g. `images: yes`) is reported by config
  validation instead of silently discarding the section (it used to crash
  validation) (B46).
- `sonne build --no-progress` no longer prints the `[n/N]` step lines
  (still visible with `-v`) (B48).
- Path checks no longer crash on paths that can't be resolved, e.g. an
  unavailable drive (B51).
- The CLI's default `--path` is the current directory when the command
  runs, not when Sonne was imported.
- `solar` scaffold: a post's cover image stored next to the post gets a
  working dithered/original toggle.
- `solar` scaffold: blog, tag and category links follow `blog.directory`
  and `url_style` (they were hardcoded to `/blog/.../`, so a custom blog
  directory or the clean style produced broken links).
- A post dated with a timezone (e.g. `2024-01-05 12:00:00+02:00`) no
  longer crashes the build when other posts have plain dates; URLs keep the
  written date and RSS keeps the written offset (B31).
- Tags or categories differing only in case ("Python"/"python") share one
  page listing all their posts instead of overwriting each other; the name
  shown is the newest post's spelling (B32).
- RSS `media:thumbnail` URLs point at the published cover with
  `url_style: html` (they were `.../slug.html/images/...`) (B33).
- A trailing slash in `site.base_url` no longer produces `//` in feed
  links (B34).
- A site stored inside any folder named `_drafts` publishes its posts;
  only `_drafts` inside the blog directory marks drafts (B35).
- Post and cover images whose `../` path would land outside the output
  directory are skipped with a warning instead of written there (B36).
- On Windows with Python 3.9–3.11, undated posts use the file's creation
  time rather than its last-modified time (B37).
- When dithering a post image fails, the figure shows the original instead
  of a mislabeled `dithered/<name>.png` holding the original's bytes (B38).
- Image syntax inside indented (4-space) code blocks in posts is ignored,
  like fenced code. `data:` URI and uppercase `.SVG` images in posts no
  longer produce "Image not found" warnings or dithered-path markup.
- The `--perf` build report counts rendered templates.
- Static images (`static/images`) stay dithered on every build. From the
  second build on (including every `sonne serve` rebuild) the undithered
  original was served at the image's URL. The static-image cache now
  verifies its output is still the dithered file, and the static copy no
  longer overwrites images the image pipeline owns, so rebuilds are cache
  hits again (B39).
- `.html`/`.htm` content pages get a `page.url` matching where they are
  written: in the clean and directory URL styles `content/about.html` is
  written to `about/index.html` but `page.url` was `/about.html` (a 404);
  `dir/index.html` is now `/dir/`. The html style is unchanged (B40).
- The `sonne build --perf` hint for slow images fires for
  `images.dither_method: color_lab` (it checked a name never used) and
  names the right setting (B47).
- The page-size label (`build.show_page_size`) goes before the page's last
  `</body>`, not one inside an inline script; images whose `src` has a
  query, fragment or %-encoding now count toward the size (B49).
- Static JPEG images (`static/images/*.jpg`) are dithered again; saving
  failed with "cannot write mode P as JPEG" and the undithered original
  was copied. They stay JPEGs at their original URL (B17).
- Building without the cache (`skip_cache`) also reprocesses
  `static/images`; stale cached dithers were kept (B19).
- Images are processed when the site lives inside a dot-directory (e.g.
  `~/.sites/blog`); every image was silently skipped (B20).
- The warning about removed `{+}{...}`/`{-}{...}`/`{p}{#...#}` markers
  appears on every build, including `sonne serve` rebuilds (B21).
- Page URLs drop only a trailing `.md`/`.markdown` suffix (now matched
  case-insensitively); `content/v1.mdnotes/page.md` became `/v1notes/page`
  (B22).
- Markdown files under the configured `blog.directory` get the post
  template; the check was a `/blog/` substring that failed on Windows and
  with non-default blog directories (B23).
- The `process_image` Jinja filter always returns safe markup with its
  arguments HTML-escaped. With dithering off it rendered as visible
  `<img ...>` text; with dithering on, quotes or `<` in alt text broke the
  page (B24).
- An unknown `images.dither_method` falls back to bayer with the configured
  `dither_colors` (was always 4) and warns once per build instead of once
  per image (B25).
- `index.md` pages get their directory's URL (`/`, `/projects/`) instead of
  `/index`, so `og:url`, canonical links and active-nav checks point at
  real pages (B27).
- Markdown pages with a `.markdown` or uppercase `.MD` extension and no
  front-matter template use `page.html` (or the blog post template under
  `blog.directory`); they rendered as a bare fallback page without the site
  layout (B30).
- `dithering.js` no longer adds a second, broken toggle to blog-post
  figures.
- Clicking the dithering toggle on a linked image no longer follows the link.
- The image toggle and the original image line up with the image even when
  the theme gives images a margin.
- The config JSON schema no longer rejects valid configs: keys with
  defaults are no longer required, custom environments in `url_style` are
  accepted, and BCP 47 language tags such as `zh-Hans`, `es-419` and
  `en-us` are allowed.
- `blog.rss.path` pointing into a subdirectory (e.g. `feeds/blog.xml`)
  failed because the directory was never created.
- `solar` scaffold (affects new `sonne new -t solar` sites): the battery
  script no longer writes debug files to `/tmp` or prints on every build;
  `solar.battery_simulation: false` now reads the real battery (psutil or
  Linux sysfs); the weather script honours `site.weather` (location,
  units) instead of always fetching Fahrenheit for a fixed location, and
  no longer forces DEBUG logging for the whole build; cover, project and
  portfolio images no longer point at nonexistent `*_800_dithered.*`
  files; tag, category and archive pages list their posts.
- Blog posts, related posts and image size annotations are cheaper to
  compute on large blogs (tag sets are precomputed; each post's HTML is
  parsed once rather than once per image).
- Images beside a blog post (and post covers) keep their own format (B12).
  A PNG was re-encoded as JPEG under its `.png` name, and a PNG with
  transparency failed to save and was copied unresized, logging an error.
  JPEG output now always drops any alpha channel first, and palette images
  with transparency keep it.

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
