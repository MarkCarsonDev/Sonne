# 11 — Word-based excerpt option

**Size:** S · **Backlog #7** · **Breaking:** none (default preserves today's behavior)

## Context

`blog.excerpt_length` counts characters and truncates mid-word
(`_generate_excerpt`: `text[:length] + '...'`). Docs/schema now say
"characters" honestly, but words are what authors expect.

## Design

1. New config `blog.excerpt_unit: chars | words`, default `chars`
   (compat). With `words`, `_generate_excerpt` splits on whitespace, takes
   `length` words, joins, appends `…` only when truncated.
2. In `chars` mode, stop cutting mid-word: truncate at the last whitespace
   before the limit (bounded scan; if no whitespace, hard cut as today).
   This is a small deliberate behavior improvement — update the pinned
   characterization test in the same PR with a CHANGELOG "Changed" line.
3. Front-matter `excerpt:` continues to bypass generation entirely.

## Files

`sonne/processors/blog_processor.py` (`_generate_excerpt` + its two call
sites pass the unit), `sonne/core/config.py`, schema, README, CHANGELOG.

## Tests

- chars mode: ≤ length, ends on a word boundary, `...` suffix only when cut;
- words mode: exact word count;
- explicit front-matter excerpt untouched;
- RSS description uses the same excerpt (already escaped).
