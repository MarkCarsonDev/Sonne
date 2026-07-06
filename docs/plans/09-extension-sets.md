# 09 — Single source of truth for file-extension sets

**Size:** S · **Backlog #11** · **Breaking:** none

## Context

Image extensions (`.jpg/.jpeg/.png/.gif/.webp`) are defined independently in
`site_generator.generate` (image counting) and
`image_processor._process_directory_images`; page extensions
(`.html/.htm/.md/.markdown`) in `site_generator` twice; template extensions
in `template_processor.validate_templates`. Divergence is a matter of time.

## Design

1. New `sonne/utils/constants.py` (or extend `path_utils`):
   `IMAGE_EXTENSIONS`, `PAGE_EXTENSIONS`, `TEMPLATE_EXTENSIONS` as
   frozensets of lowercase suffixes.
2. Replace every inline set/list with the constant; comparisons via
   `path.suffix.lower() in IMAGE_EXTENSIONS`.
3. **Do not** add `.avif`/`.tiff` in the same PR — Pillow support for those
   varies by build; open a follow-up once CI proves encode support on all
   matrix platforms. Document in the module that `.gif` is currently
   flattened to a static frame by the resize pipeline.

## Files

New `sonne/utils/constants.py`; `sonne/core/site_generator.py`,
`sonne/processors/image_processor.py`,
`sonne/processors/template_processor.py`; CHANGELOG internal note.

## Tests

- grep-level guard: unit test asserting the constants module is the only
  definition site (import and compare against the values the processors
  use);
- existing integration suite covers behavior unchanged.
