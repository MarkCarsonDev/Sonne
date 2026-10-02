# Backlog

Known improvements that are not done yet. Each has a plan in
[plans/](plans/00-INDEX.md); the index says how much of each plan is
already implemented.

## Performance

- **Parse each page once** ([plan 04](plans/04-single-parse-html-pipeline.md)).
  With dithering on, `TemplateProcessor.finish_page` parses every rendered
  page with BeautifulSoup, including pages without images.
- **Related posts at scale** ([plan 13](plans/13-related-posts-performance.md)).
  Every post is scored against every other post, and `related_posts` stores
  whole post dicts (content included), which inflates what scripts get from
  `get_variable("all_blog_posts")`.

## Features

- **Date formats and month names** ([plan 10](plans/10-date-format-i18n.md)).
  `%B %d, %Y` and English month names are hardcoded for post dates and
  archive titles, so a non-English site cannot change them.
- **Word-based excerpts** ([plan 11](plans/11-word-excerpts.md)).
  `blog.excerpt_length` counts characters and cuts mid-word.
- **Config keys for remaining constants** ([plan 12](plans/12-configurable-constants.md)).
  JPEG/WebP quality (85), the number of related posts (3) and the `_drafts`
  folder name are fixed in code.
- **`images.lazy_loading` and `images.grayscale_before_dither`**
  ([plan 08](plans/08-dead-config-keys.md)). Both are accepted and do
  nothing. Implement the first, remove the second through
  `sonne/core/deprecations.py`.
- **More image formats.** `.avif` and `.tiff` are not processed, and an
  animated `.gif` is flattened to one frame.

## Cleanup

- **`Config.normalize_paths` creates directories** ([plan 06](plans/06-path-normalization.md)).
  Something named "normalize" should only resolve paths; creating the
  output and cache directories belongs to `SiteGenerator`.
- **Showcase example** ([plan 14](plans/14-showcase-template-cleanup.md)).
  Its nav hardcodes `.html` URLs and it sets no `url_style`. A test that
  every starter template builds without warnings is also missing.

## Design

Changes to how Sonne is put together. None has a plan yet.

- **Listing page data only under `page`.** Tag, category, archive and index
  templates get `page.posts`, `page.tag` and so on. Templates that read a
  top-level `posts` or `tag` render "no posts" without a warning. Either
  expose them at the top level too, or make an undefined listing variable
  an error.
- **Remove `variables.flatten_data`.** It defaults to `false` now and only
  exists so sites can keep the old flat names while updating templates.
  Remove it, and the flat code paths in `VariableManager`, through
  `sonne/core/deprecations.py`.
- **Finish the one dithered-image layout.** Static and post images use
  `<dir>/dithered/<name>.png`. Sized content images still use
  `<name>_<width>.<format>` beside `<name>_<width>_original.<format>`, in
  one flat folder (`/assets/images/`). The `<name>_original` copies of
  static images go in 0.6.0.
- **Image references from the rendered post.** Post images are found with
  regular expressions over raw Markdown, with separate code to skip code
  blocks. Collect them from the rendered HTML instead.
- **Who writes `output/images/`.** The static copy and the image pipeline
  both write there. One clash is handled with a skip check
  (`ImageProcessor.owns_static_file`); there is no general rule.
- **Constructors with side effects.** `SiteGenerator.__init__` changes the
  `Config` it is given (fills default paths) and creates directories, and
  the CLI module configures logging when it is imported. See also plan 06.
- **Two path-resolution rules.** `VariableManager` resolves the data and
  scripts folders itself, not through `Config.normalize_paths`.
- **Heading ids can collide.** Markdown's generated heading ids
  (`### Email` gives `id="email"`) can match ids in templates or inline
  HTML and break `<label for>` and anchors. The accessibility check reports
  duplicates; nothing prevents them.
- **Savings for content images in the build report.** A content image
  becomes many variants, so there is no "processed size" to report. Pick a
  definition or leave it out for good.
- **Solar starter ships its own listing templates.** The other starters use
  the built-in ones.

## Packaging

- **The PyPI name `sonne` belongs to another project.** `pip install sonne`
  installs an unrelated terminal-styling library. Publishing needs a
  different distribution name in `pyproject.toml` (the import name and the
  `sonne` command can stay), or the README's install-from-GitHub
  instructions stay as they are.
