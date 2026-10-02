# Backlog

Known improvements that are not done yet. Each has a plan in
[plans/](plans/00-INDEX.md); the index says how much of each plan is
already implemented.

## Performance

- **Cache blog-pipeline image outputs** ([plan 03](plans/03-blog-image-caching.md)).
  Images beside a post, and post covers, are resized and dithered on every
  build. `ImageProcessor` has a hash-based cache; the blog pipeline does not
  use it.
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
- **Project detection and config discovery disagree** ([plan 07](plans/07-config-discovery.md)).
  `is_sonne_directory` accepts any folder containing `content/`,
  `templates/` or `static/`, while config discovery needs a config file in
  the folder or one of two parents. `sonne build` in the wrong folder can
  "succeed" on defaults.
- **Showcase example** ([plan 14](plans/14-showcase-template-cleanup.md)).
  Its nav hardcodes `.html` URLs and it sets no `url_style`. A test that
  every starter template builds without warnings is also missing.

## Packaging

- **The PyPI name `sonne` belongs to another project.** `pip install sonne`
  installs an unrelated terminal-styling library. Publishing needs a
  different distribution name in `pyproject.toml` (the import name and the
  `sonne` command can stay), or the README's install-from-GitHub
  instructions stay as they are.
