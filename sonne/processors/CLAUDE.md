# Processors — module notes

- **Image cache keys must include every setting that affects output**
  (dither method, colors, formats, sizes, webp method, quality...). A cache
  key that omits a setting serves stale images when that setting changes —
  this was a real bug (B4). When adding an image option, add it to the cache
  key and bump the `v<N>:` cache-key version prefix. Post images and covers
  have their own keys (`blog-v1:`, one per output file, in
  `BlogProcessor._image_cache_keys`): the same rule applies there.
- **One dithered-image convention**: an original keeps its own URL; its
  dithered copy sits beside it (`<dir>/dithered/<stem>.png`, or a sized
  variant `x_400.webp` next to `x_400_original.webp`). The image pipeline
  records every pair in `DitheredImages`; `TemplateProcessor.finish_page()`
  points registered root-relative `<img>` tags at the dithered copy and sets
  `data-original-src`; `dithering.js` toggles only `img[data-original-src]`
  — never guess URLs client-side (that gave undithered images broken
  toggles, B52). Blog post figures are marked by the blog pipeline at
  metadata collection (`process_markdown(rewrite_dithered=True)`, blog only;
  regular pages must not use it, B9). Static `<name>_original` copies are a
  compatibility bridge until 0.6.0.
- **Blog image ordering is two-pass**: post images are copied/dithered
  (pass 1) before templates render (pass 2) so `cover_img_dithered` and size
  stats exist at render time. The `<figure>` rewrite happens even earlier,
  at metadata collection — existence checks there are impossible. Don't
  reorder.
- **`Config.get` takes `*keys` with a keyword-only default** — always write
  `config.get('a', 'b', default=X)`. A positional default is silently
  treated as another key segment and returns None (this disabled static
  image dithering entirely for a long time).
- **BeautifulSoup**: always `BeautifulSoup(html, 'html.parser')` — parser
  choice affects output; lxml/html5lib normalize markup differently and are
  not dependencies.
- **Slugs**: `sonne.utils.text.slugify` is used for post URLs, taxonomy
  pages, AND the Jinja `slugify` filter. They must stay identical or tag
  links 404 (three divergent implementations once did exactly that).
- **RSS**: all text interpolated into the feed goes through
  `xml.sax.saxutils.escape`; dates through the local-timezone RFC-822
  helper. No CDATA, no hardcoded `+0000`.
