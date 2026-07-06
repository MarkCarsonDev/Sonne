# 05 — Vectorize LAB k-means dithering

**Size:** S/M · **Backlog #1** · **Breaking:** none (output may differ pixel-wise; visually equivalent)

## Context

`image_processor._lab_kmeans_dither` runs Floyd–Steinberg diffusion as a
pure-Python per-pixel double loop calling `to_lab` per pixel — minutes for a
1200px image. numpy is already a dependency (Bayer path uses it).

## Design

1. **Palette selection stays as-is** (k-means in LAB on a sampled subset —
   already vectorized).
2. **Nearest-palette lookup:** precompute the palette's LAB centres once;
   per pixel, distance is a (k,3) broadcast — but the serial dependency of
   FS error diffusion prevents full vectorization. Use the standard
   compromise: **row-serpentine processing with per-row vectorization is NOT
   valid for FS** (left-to-right dependency within a row), so choose one of:
   - (a) keep FS but move the inner loop to numpy-friendly code and convert
     `to_lab` to a precomputed operation: convert the palette to RGB once and
     do error diffusion **in RGB** (drop per-pixel LAB conversion — the
     palette was chosen in LAB, which is where the perceptual win lives;
     diffusion space matters far less). This alone removes the per-pixel
     `to_lab` and typically gives 20–50×.
   - (b) optionally offer `dither_method: color_lab_ordered` using a Bayer
     threshold matrix in fully vectorized form for another ~10× when the
     pattern is acceptable.
   Implement (a); note (b) as a follow-up if still slow on target hardware.
3. Add a perf guard test only as a sanity bound (e.g. 512×512 under 5s in
   CI), generous enough to never flake.

## Files

`sonne/processors/image_processor.py` (`_lab_kmeans_dither`), `CHANGELOG.md`.

## Tests

- output is a P-mode image with ≤ configured colors; deterministic given a
  fixed seed (seed the k-means sample RNG — also fixes nondeterministic
  builds with color_lab);
- visual-difference smoke: mean per-pixel delta vs the old implementation on
  a gradient fixture below a loose threshold (run once in the PR, keep the
  threshold test);
- the loose time bound above.

## Compatibility

Byte-level output changes for `color_lab` users (cache key already includes
method; the version bump reprocesses). Note in CHANGELOG.
