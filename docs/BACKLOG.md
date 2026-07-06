# Backlog — issue-ready improvements

Known, deliberately deferred improvements from the 0.4.0 readiness pass.
Each entry is written so it can be pasted into a GitHub issue as-is
(`gh issue create -t "<title>" -F <body>`). File references are as of 0.4.0.

---

## 1. Perf: vectorize LAB k-means dithering
**Labels:** performance
`color_lab` dithering runs a pure-Python per-pixel double loop with a
`to_lab` call per pixel (`sonne/processors/image_processor.py`,
`_lab_kmeans_dither`). On a 1200px image this takes minutes. Vectorize the
Floyd–Steinberg diffusion / nearest-palette lookup with numpy (serpentine
scan or block-based approximation are acceptable trade-offs).

## 2. Perf: cache blog-pipeline image outputs
**Labels:** performance
`BlogProcessor._save_resized` / `_process_blog_image` re-resize and
re-dither every post image on every build. ImageProcessor has a hash-based
cache; the blog pipeline needs the same (share the cache, key on source
hash + transforms + widths + dither settings).

## 3. Perf: single HTML parse per page; inject dither assets only when needed
**Labels:** performance
Each page can be BeautifulSoup-parsed multiple times: `_process_image_tags`,
`inject_dithering_assets`, and per-image size stamping in
`_copy_post_images`. Restructure to one parse/serialize per page, and skip
injecting dithering CSS/JS into pages with no images.

## 4. Perf: related-posts scoring is O(n²) and stores full post dicts
**Labels:** performance
`BlogProcessor._set_navigation_links` scores every post against every other
post and stores complete post dicts in `related_posts`, inflating memory
and the variable payload. Store (title, url, excerpt) refs and consider an
inverted tag index.

## 5. Make blog date formatting configurable / localizable
**Labels:** enhancement, i18n
`'%B %d, %Y'` and English month names are hardcoded in
`blog_processor.py` (`date_formatted`, `date_posted`, date archives).
Add `blog.date_format` (strftime string) and use `site.language` where
sensible. Schema + README + CHANGELOG in lockstep.

## 6. Expose remaining hardcoded constants as config
**Labels:** enhancement
Currently hardcoded: RSS is schema-covered now, but these are not:
JPEG/WebP quality 85, resample-threshold width 400, related-posts count 3,
slug length cap 100 (`sonne/utils/text.py::MAX_SLUG_LENGTH`), `_drafts`
directory name, `assets/images` output subdir. Decide which deserve config
keys and which stay constants.

## 7. Excerpts: implement word-based length option
**Labels:** enhancement
`blog.excerpt_length` is characters and cuts mid-word
(`_generate_excerpt`). Docs/schema now say characters, but a
`blog.excerpt_unit: words|chars` (default chars for compat) would match
what most users expect.

## 8. Embedded-python "safe_builtins" is not a sandbox
**Labels:** security, documentation
`variable_manager.substitute_variables` executes `{p}{#...#}` blocks with a
curated `__builtins__` dict. This is escapable by construction (object
traversal). Either rename/reframe it as "reduced conveniences, NOT a
sandbox" everywhere it appears, or adopt a real sandboxing approach.
README already carries a warning; the code comments still oversell it.

## 9. Unify path normalization (Config.normalize_paths vs SiteGenerator)
**Labels:** refactor
`Config.normalize_paths` duplicates the relative→absolute + mkdir logic
that `SiteGenerator.__init__` implements independently, and is effectively
dead. Pick one owner (suggest: Config), and drop the directory-creation
side effect from anything named "normalize".

## 10. Reconcile project detection with config discovery
**Labels:** refactor, ux
`is_sonne_directory` accepts any dir containing `content/`, `templates/`,
or `static/` (no config needed), while `Config._find_config` walks up 3
parent levels (now with a warning). Decide the real contract: probably
"config file required, parent search opt-in", and make the 3-level depth a
named constant or config.

## 11. Define image/page extension sets once
**Labels:** refactor
`{'.jpg', '.jpeg', '.png', '.gif', '.webp'}` and page-extension sets are
each defined in multiple modules (site_generator, image_processor). Move to
one constants module; consider `.avif`/`.tiff` support while at it
(`.gif` is currently flattened to a static frame — document or fix).

## 12. Remove or implement deprecated no-op image keys
**Labels:** cleanup
`images.grayscale_before_dither` and `images.lazy_loading` are accepted but
never read (schema now marks them DEPRECATED). Either implement them or
remove them via `sonne/core/deprecations.py` with a warning.

## 13. Unify the two dithered-image conventions
**Labels:** refactor, breaking
Blog pipeline: dithered copy at `dithered/<stem>.png`, original keeps its
URL (figure markup with data attributes). Static pipeline: dithered at the
main path + `_original` suffix (client-side `dithering.js` computes the
original path). Unifying on the blog convention requires updating
`sonne/static/js/dithering.js`'s standalone-image path logic and a
CHANGELOG "Changed" entry for `_original` deep links. See
`sonne/processors/CLAUDE.md`.

## 14. Showcase template cleanup
**Labels:** templates, good-first-issue
`sonne/examples/showcase-template` hardcodes `.html` nav URLs
(`/features.html`, `/blog/index.html`) and omits `url_style`, unlike the
bundled templates (directory style). Align it, and add `category.html` /
`categories.html` to the blog template (categories are enabled by default
but their templates are missing, producing warnings).
