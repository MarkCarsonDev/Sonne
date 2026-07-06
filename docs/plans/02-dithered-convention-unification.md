# 02 — Unify the two dithered-image conventions

**Size:** M · **Backlog #13** · **Breaking:** `_original`-suffix URLs go away (CHANGELOG "Changed")

## Context

Two conventions coexist (documented in `sonne/processors/CLAUDE.md`):
*blog*: dithered copy at `<dir>/dithered/<stem>.png`, original keeps its URL,
`<figure>` markup carries `data-original-src`/`data-dithered-src`;
*static*: dithered image AT the main path, original beside it as
`<name>_original<ext>`, and the client (`sonne/static/js/dithering.js`)
string-computes the `_original` URL for standalone images. Two mental models,
two JS code paths, and deep links to a static image URL serve different
pixels depending on the dither setting.

## Design

Adopt the **blog convention everywhere**: originals always keep their URL;
dithered variants live in a `dithered/` sibling directory.

1. `image_processor._process_static_image`: write the original (as-is copy)
   to its real path; write the dithered variant to
   `<dir>/dithered/<stem>.png`. Delete the `_original`-suffix output. Bump
   the static cache-key version prefix.
2. `dithering.js` `wrapImageWithDitheringControls`: replace the `_original`
   suffix computation with the inverse mapping — given `src`, dithered
   candidate is `dirname + '/dithered/' + stem + '.png'`. Standalone images
   now *start* as the original and toggle TO dithered; set the container's
   initial state accordingly (`show-original` default for standalone images,
   preserving the current visual default of dithered-first requires swapping
   `src` to the dithered path onload — decide in PR; recommend: serve
   original first for standalone/static images, it is the less surprising
   default and avoids a flash).
3. Templates/pages referencing `/images/foo.png` now always get the true
   original — pages that WANT the dithered look reference
   `/images/dithered/foo.png` explicitly or rely on the JS toggle.
4. `sonne/processors/CLAUDE.md`: collapse the two-conventions section to one.

## Files

`sonne/processors/image_processor.py` (`_process_static_image`,
`_copy_static_image` interplay), `sonne/static/js/dithering.js`,
`sonne/processors/CLAUDE.md`, `README.md` image docs, `CHANGELOG.md`.

## Tests

- static image with dither on → `images/foo.png` byte-equal to source,
  `images/dithered/foo.png` exists; no `foo_original.png` anywhere;
- dither off → only the plain copy;
- `only_used` interaction: referenced static image produces both files;
- JS contract: assert generated HTML/`dithering.js` agree on the path scheme
  (string-level test: the JS file contains `/dithered/` and no `_original`).

## Compatibility

External deep links to `*_original.*` URLs 404 after this. CHANGELOG
"Changed" entry; optionally a one-release `images.legacy_original_copies`
flag that also emits the old suffix files (default false — only add if a
real need appears).
