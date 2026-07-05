# Processors — module notes

- **Image cache keys must include every setting that affects output**
  (dither method, colors, formats, sizes, webp method, quality...). A cache
  key that omits a setting serves stale images when that setting changes —
  this was a real bug (B4). When adding an image option, add it to the cache
  key and bump the `v<N>:` cache-key version prefix.
- **Two dithered-image conventions exist — know which pipeline you're in:**
  1. *Blog pipeline* (post-local images): dithered copy at
     `<dir>/dithered/<stem>.png`, original keeps its own URL. Server-side
     `<figure>` markup carries `data-original-src`/`data-dithered-src`.
  2. *Static pipeline* (`static/images/`): dithered image at the main path,
     original beside it with an `_original` suffix. The client-side
     `dithering.js` computes the `_original` path for standalone images.
  Don't mix them: only blog markdown gets the server-side dithered rewrite
  (`process_markdown(rewrite_dithered=True)`); regular pages must not (their
  `dithered/` paths would never exist — that was bug B9). Unifying the two
  conventions is a known backlog item; it requires changing dithering.js.
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
