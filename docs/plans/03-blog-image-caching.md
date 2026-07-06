# 03 — Cache blog-pipeline image outputs

**Size:** M · **Backlog #2** · **Breaking:** none

## Context

`BlogProcessor._save_resized` and `_process_blog_image` re-resize, re-crop,
and re-dither every post image and cover on every build. `ImageProcessor`
already has a persisted hash cache (`.cache/`, key includes source hash and
all output-affecting settings, `v2:` version prefix); the blog pipeline
bypasses it entirely. On low-power build hosts this dominates rebuild time.

## Design

1. Extract the cache mechanics from `ImageProcessor` into a small
   `ImageCache` helper (load/save JSON, `hit(key)`, `store(key, value)`,
   version prefix) — or expose the existing instance; the blog processor
   already receives `image_processor` in its constructor, so **reuse
   `self.image_processor.cache` and `_file_hash`** rather than a new store.
2. Cache key for blog outputs:
   `v1blog:{source_hash}:{max_width}:{transforms_json}:{dither_method}:{dither_colors}:{webp_method}` —
   transforms serialized deterministically (sorted keys). Separate keys for
   the resized-original and the dithered variant.
3. Cache VALUE stores the output file's size-KB (needed for the caption
   stats) — on a hit, verify the output file exists (output dir may have
   been cleaned); if missing, reprocess regardless of hit.
4. `skip_cache=True` (the `--skip-cache` flag) bypasses, mirroring
   `process_image`.
5. Record hits via `stats.record_image(..., cached=True)` so `--perf`
   reflects reality.

## Files

`sonne/processors/blog_processor.py` (`_copy_post_images`, `_save_resized`,
`_process_blog_image` signatures gain cache plumbing),
`sonne/processors/image_processor.py` (expose/reshape cache helper),
`sonne/processors/CLAUDE.md` (cache-key rule already covers this),
`CHANGELOG.md`.

## Tests

- build twice; second build's stats show cached blog images and the outputs'
  mtimes are unchanged;
- changing `images.dither_colors` (or a crop transform in the markdown title)
  busts the cache for that image only;
- deleting an output file with a warm cache → file is regenerated;
- `--skip-cache` regenerates everything.

## Compatibility

Pure speedup. First build after upgrade is a full run (new key namespace).
