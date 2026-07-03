# Processors — module notes

- **Image cache keys must include every setting that affects output**
  (dither method, colors, formats, sizes, webp method, quality...). A cache
  key that omits a setting serves stale images when that setting changes —
  this was a real bug (B4). When adding an image option, add it to the cache
  key and bump the cache version.
- **Canonical dithered-image convention**: the dithered copy lives at
  `<dir>/dithered/<stem>.png`; the original keeps its own path/URL. The
  toggle JS contract is `data-original-src` / `data-dithered-src`. Do not
  reintroduce the old `_original`-suffix convention.
- **Only rewrite `<img>` tags to dithered paths when the dithered file
  actually exists in the output dir** — blog images are produced in pass 1
  (before rendering), so existence checks are reliable at render time.
- **Blog image ordering is two-pass**: images are processed before post
  rendering so `cover_img_dithered` and size stats exist when templates run.
  Don't reorder.
- **BeautifulSoup**: always `BeautifulSoup(html, 'html.parser')` — parser
  choice affects output; lxml/html5lib normalize markup differently and are
  not dependencies.
- **Slugs**: use `sonne.utils.text.slugify` for post URLs, taxonomy pages,
  AND the Jinja `slugify` filter. They must stay identical or tag links 404.
