# 12 — Sweep of remaining hardcoded constants

**Size:** S · **Backlog #6** · **Breaking:** none

## Context

Leftover magic numbers after the 0.4.0 pass. Not everything deserves a
config key; this plan decides each explicitly.

## Design — disposition table

| Constant | Where | Decision |
|---|---|---|
| JPEG/WebP quality `85` | image_processor save calls | config `images.quality` (int 1–100, default 85), used for BOTH jpeg and webp saves |
| Resample threshold `width <= 400` → BICUBIC | image_processor | named module constant, NOT config (implementation detail) |
| Related-posts count `3` | blog_processor `_set_navigation_links` | config `blog.related_posts` (int ≥ 0, default 3; 0 disables — pairs with plan 13) |
| Slug cap `100` | utils/text.py `MAX_SLUG_LENGTH` | stays a named constant (already is) |
| `_drafts` dir name | blog_processor `_collect_posts` | config `blog.drafts_directory` (default `_drafts`) |
| `assets/images` output subdir | image_processor `process_image` | named constant now; config only if a real request appears |
| Debounce `0.4s` | commands.py RebuildHandler | named class constant (already is) — no change |
| Page-size label overhead `150` | site_generator `_inject_page_sizes` | named constant, no config |

New config keys follow the lockstep rule (DEFAULT_CONFIG + schema + README +
CHANGELOG).

## Files

`sonne/processors/image_processor.py`, `sonne/processors/blog_processor.py`,
`sonne/core/config.py`, schema, README, CHANGELOG.

## Tests

- `images.quality: 60` produces smaller files than default (size inequality
  on a generated photo-like fixture);
- `blog.related_posts: 1` → one related post; `0` → key present, empty list;
- `blog.drafts_directory: unpublished` → `unpublished/` skipped, `_drafts/`
  no longer special.
