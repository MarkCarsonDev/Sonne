# 08 — Remove the dead image config keys

**Size:** S · **Backlog #12** · **Breaking:** none (keys never did anything)

## Context

`images.lazy_loading` and `images.grayscale_before_dither` are accepted and
schema-documented (now marked DEPRECATED) but never read. `loading="lazy"`
is hardcoded where images are emitted; grayscale conversion is a property of
the chosen `dither_method`.

## Design

1. **`lazy_loading`: implement it** — it's one attribute at two emit sites
   (`_process_image_tags`, the `process_image` Jinja filter) and cover-image
   markup; honor `images.lazy_loading: false` by emitting `loading="eager"`.
   Rationale: trivially real, and eager-loading above-the-fold covers is a
   legitimate want.
2. **`grayscale_before_dither`: remove** via `REMOVED_CONFIG_KEYS` in
   `deprecations.py` (mechanism from plan 01) — grayscale is
   `dither_method: grayscale`; a pre-conversion toggle duplicates that
   surface. Schema entry deleted; warning names the replacement.

## Files

`sonne/processors/template_processor.py`, `sonne/processors/blog_processor.py`
(cover markup), `sonne/core/deprecations.py`, `sonne/core/config.py`
(DEFAULT_CONFIG keeps `lazy_loading`), schema, README, CHANGELOG.

## Tests

- `lazy_loading: false` → generated `<img>` tags carry `loading="eager"`;
  default stays `lazy` (update pinned markup assertions);
- config with `grayscale_before_dither` warns once, builds fine.
