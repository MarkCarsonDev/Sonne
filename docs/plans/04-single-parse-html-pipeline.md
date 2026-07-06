# 04 — One HTML parse per page; conditional dither assets

**Size:** M · **Backlog #3** · **Breaking:** none (byte-identical output is the acceptance bar)

## Context

A page's HTML can be BeautifulSoup-parsed and re-serialized up to three
times: `_process_image_tags` (figure rewrite), per-image size stamping in
`_copy_post_images`, and `inject_dithering_assets` (which BS4-parses every
page even when it has zero images). Each parse/serialize cycle is slow and
each is an opportunity for the parser to normalize markup differently.

## Design

1. **Thread one soup through the blog pass.** In `_render_posts` pass 1,
   parse `post['content']` once, hand the soup to the size-stamping logic
   (today it re-parses per image), serialize once at the end.
   `_process_image_tags` already receives/returns strings from
   `process_markdown` — keep its boundary but make `_copy_post_images`
   operate on a shared soup instead of parse-per-image.
2. **`inject_dithering_assets` becomes cheap-first:** skip entirely when
   `images.dither` is false (config check), and short-circuit with a string
   containment test (`'<img'` not in html → return unchanged) before any
   parsing. When it does inject, do it with a string insertion before
   `</head>` (it appends fixed `<style>/<script>` tags — no DOM knowledge
   needed) instead of a full BS4 round-trip.
3. Keep `html.parser` everywhere (per processors/CLAUDE.md).

## Files

`sonne/processors/blog_processor.py` (`_copy_post_images`),
`sonne/processors/template_processor.py` (`inject_dithering_assets`),
`CHANGELOG.md` (internal/perf note).

## Tests

- Characterization: build the blog fixture before/after — rendered pages are
  byte-identical (this is the whole acceptance test; add a golden comparison
  in the PR branch, not committed);
- page with no images: output contains no dithering `<style>` block when
  dither is off; unchanged behavior when on;
- multi-image post still gets per-image size attributes.

## Compatibility

None user-visible. If exact serialization differs (BS4 attribute ordering),
update pinned tests deliberately and note it — but the string-insertion
approach for injection should reduce, not increase, drift.
