"""
Image processing for Sonne.
Handles optimizing, resizing, and converting images.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image, ImageOps

from sonne.processors.dithered_images import DitheredImages
from sonne.utils.build_stats import BuildStatistics
from sonne.utils.constants import IMAGE_EXTENSIONS, PAGE_EXTENSIONS

logger = logging.getLogger("sonne")

DEFAULT_FORMATS = ["webp", "png"]
DEFAULT_SIZES = [1200, 800, 400]
DEFAULT_DITHER_FORMATS = ["webp"]

# Where sized variants are written, relative to the output root.
VARIANTS_DIR = "assets/images"

# Lossy quality for WebP and JPEG variants.
LOSSY_QUALITY = 85

# BICUBIC is visually identical to LANCZOS at small sizes and ~2x faster.
BICUBIC_MAX_WIDTH = 400

HASH_CHUNK_BYTES = 8192

# Where a static image's dithered copy lives, relative to the image's directory.
DITHERED_DIR_NAME = "dithered"

# Logged once per build that dithers static images. The "_original" part goes
# away with the compatibility copy in Sonne 0.5.0 (_write_legacy_original_copy).
STATIC_LAYOUT_NOTICE = (
    "Static images keep their original at their own URL; the dithered copy is "
    "<dir>/dithered/<name>.png. The <name>_original copies are still written for "
    "compatibility and will be removed in Sonne 0.5.0."
)

DEFAULT_DITHER_COLORS = 4
MIN_PALETTE_SIZE = 2
MAX_PALETTE_SIZE = 256

# Ordered-dither threshold map, normalised to [0, 1).
BAYER_4X4 = (
    np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=float) / 16.0
)

# sRGB (D65) <-> CIE XYZ matrices and the D65 reference white.
SRGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
XYZ_TO_SRGB = np.array(
    [
        [3.2404542, -1.5371385, -0.4985314],
        [-0.9692660, 1.8760108, 0.0415560],
        [0.0556434, -0.2040259, 1.0572252],
    ]
)
D65_WHITE = np.array([0.95047, 1.0, 1.08883])
_SRGB_TO_XYZ_ROWS = SRGB_TO_XYZ.tolist()
_D65_WHITE_VALUES = D65_WHITE.tolist()

# k-means is seeded so builds are reproducible.
KMEANS_SEED = 42
KMEANS_MAX_ITERATIONS = 20
KMEANS_TOLERANCE = 1e-4

DEFAULT_MAX_WORKERS = 4

# Files that may reference images, for images.only_used.
REF_SCAN_EXTENSIONS = PAGE_EXTENSIONS | {".yaml", ".yml"}
IMAGE_REF_PATTERN = re.compile(
    r'!\[.*?\]\(([^)\s"\']+)'  # markdown image
    r'|src=["\']([^"\']+)["\']'  # html src attribute
    r'|cover_img:\s*["\']?([^\s"\']+)'  # front matter cover, optionally quoted
)


@dataclass(frozen=True)
class ImageWorkload:
    """Source images one process_all() run handles, in processing order."""

    content: list[str]
    static: list[str]

    def __len__(self) -> int:
        return len(self.content) + len(self.static)


@dataclass(frozen=True)
class VariantSettings:
    """Every setting that affects the variants written for a content image."""

    dither: bool
    optimize: bool
    formats: list[str]
    sizes: list[int]
    dither_method: str
    dither_colors: int
    webp_method: int
    webp_method_original: int
    dither_formats: list[str]
    dither_sizes: set[int]

    def cache_key(self, source_path: str, file_hash: Optional[str]) -> str:
        """Cache key covering the source file and every output-affecting setting.

        The "v2" prefix was bumped when dither settings joined the key, so
        entries in the old layout are invalidated once.
        """
        return (
            f"v2:{source_path}:{file_hash}:{self.dither}:{self.optimize}"
            f":{_joined(self.formats)}:{_joined(self.sizes)}"
            f":{self.dither_method}:{self.dither_colors}"
            f":{self.webp_method}:{self.webp_method_original}"
            f":{_joined(self.dither_formats)}:{_joined(sorted(self.dither_sizes))}"
        )


class ImageProcessor:
    """Processes and optimizes images."""

    def __init__(self, config, paths: dict[str, str]):
        """Initialize image processor.

        Args:
            config: Site configuration.
            paths: Dictionary of normalized paths.
        """
        self.config = config
        self.paths = paths
        self.cache = {}
        self.cache_file = None
        self.stats: Optional[BuildStatistics] = None  # Injected by SiteGenerator
        self._warned_dither_methods: set[str] = set()
        self._used_images_by_content_dir: dict[Optional[str], set[str]] = {}
        # Images are processed in a thread pool; guards warnings and stats.
        self._lock = threading.Lock()
        # Filled while processing; TemplateProcessor marks <img> tags from it.
        self.dithered_images = DitheredImages()

        # Setup cache if a cache directory is configured
        if "cache" in self.paths:
            cache_dir = os.path.join(self.paths["cache"], "images")
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_file = os.path.join(cache_dir, "image_cache.json")
            self._load_cache()

    def _load_cache(self) -> None:
        """Load image processing cache."""
        if not self.cache_file or not os.path.exists(self.cache_file):
            self.cache = {}
            return

        try:
            with open(self.cache_file, encoding="utf-8") as f:
                self.cache = json.load(f)
        except Exception as e:
            logger.error(f"Error loading image cache: {e}")
            self.cache = {}

    def _save_cache(self) -> None:
        """Save image processing cache."""
        if not self.cache_file:
            return

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving image cache: {e}")

    def _file_hash(self, file_path: str) -> str:
        """Generate a hash of a file to detect changes.

        Args:
            file_path: Path to the file.

        Returns:
            SHA-256 hex digest of the file.
        """
        digest = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(HASH_CHUNK_BYTES), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError as e:
            logger.error(f"Error reading file for hashing {file_path}: {e}")
            # Return a deterministic fallback based on path and mtime
            return hashlib.sha256(f"{file_path}:{os.path.getmtime(file_path)}".encode()).hexdigest()

    def process_all(self, content_dir: str, skip_cache: bool = False) -> None:
        """Process content images and static/images, then save the cache.

        Args:
            content_dir: Directory containing content to scan for images.
            skip_cache: Whether to skip cache and reprocess all images.
        """
        images = self.images_to_process(content_dir)
        if images.content:
            logger.info(f"Processing images in content directory: {content_dir}")
            self._run_for_each(
                lambda path: self.process_image(path, skip_cache=skip_cache), images.content
            )
        if images.static:
            logger.info(
                f"Processing images in static/images directory: {self._static_images_dir()}"
            )
            if self.config.get("images", "dither", default=True):
                logger.info(STATIC_LAYOUT_NOTICE)
            self._run_for_each(
                lambda path: self._process_static_image(path, skip_cache=skip_cache), images.static
            )
        self._save_cache()

    def images_to_process(self, content_dir: str) -> "ImageWorkload":
        """The images process_all() processes: content images, then static/images.

        Raster images only, skipping hidden files and directories (below the
        scanned directory), and unreferenced images when images.only_used is on.

        Args:
            content_dir: Directory containing content to scan for images.
        """
        used_paths = self._used_image_paths(content_dir)
        content_images = (
            _find_images(content_dir, used_paths)
            if content_dir and os.path.exists(content_dir)
            else []
        )
        static_images_dir = self._static_images_dir()
        static_images = _find_images(static_images_dir, used_paths) if static_images_dir else []
        return ImageWorkload(content=content_images, static=static_images)

    def owns_static_file(self, source_path: str) -> bool:
        """Whether image processing writes this static file's output itself.

        True for the images under static/images that process_all() handles
        (raster, not hidden, and referenced when images.only_used is on).
        A plain static copy must skip these: it would overwrite the dithered
        image with the raw source.

        Args:
            source_path: Path of a file under the static directory.
        """
        static_images_dir = self._static_images_dir()
        if not static_images_dir:
            return False
        root = Path(os.path.abspath(static_images_dir))
        file_path = Path(os.path.abspath(source_path))
        if root not in file_path.parents:
            return False
        used_paths = self._used_image_paths(self.paths.get("content"))
        return _is_processable_image(file_path, root, used_paths)

    def _used_image_paths(self, content_dir: Optional[str]) -> Optional[set[str]]:
        """Referenced image paths when images.only_used is on, else None (use all).

        Memoised per content dir: the static copy and process_all() must
        agree on the same set within one build.
        """
        if not self.config.get("images", "only_used", default=False):
            return None
        if content_dir not in self._used_images_by_content_dir:
            self._used_images_by_content_dir[content_dir] = self._collect_used_images(content_dir)
        return self._used_images_by_content_dir[content_dir]

    def _static_images_dir(self) -> Optional[str]:
        """The site's static/images directory, if it exists."""
        static_dir = self.paths.get("static")
        if not static_dir:
            return None
        static_images_dir = os.path.join(static_dir, "images")
        return static_images_dir if os.path.exists(static_images_dir) else None

    def _collect_used_images(self, content_dir: Optional[str]) -> set[str]:
        """Scan content and template files for image references.

        Returns a set of resolved absolute source paths. Absolute references
        (``/images/foo.png``) are mapped back into the static directory,
        which mirrors the output root; relative references resolve against
        the referencing file's directory. Quoted front-matter values
        (``cover_img: "x.jpg"``) are handled.
        """
        used = set()
        scan_dirs = [content_dir, self.paths.get("templates")]
        for file_path in _files_to_scan_for_refs(scan_dirs):
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                for match in IMAGE_REF_PATTERN.finditer(text):
                    ref = match.group(1) or match.group(2) or match.group(3)
                    resolved = self._resolve_image_ref(ref, os.path.dirname(file_path))
                    if resolved:
                        used.add(resolved)
            except Exception as e:
                logger.debug(f"Could not scan {os.path.basename(file_path)} for image refs: {e}")
        return used

    def _resolve_image_ref(self, ref: str, referencing_dir: str) -> Optional[str]:
        """Absolute source path an image reference points at, or None if not local."""
        if not ref or ref.startswith(("http://", "https://", "data:")):
            return None
        if ref.startswith("/"):
            # Served from the output root, which mirrors the static dir (the
            # markdown pipeline collapses /static/images -> /images).
            static_dir = self.paths.get("static")
            if not static_dir:
                return None
            rel = ref.lstrip("/")
            if rel.startswith("static/"):
                rel = rel[len("static/") :]
            candidate = Path(static_dir) / rel
        else:
            candidate = Path(referencing_dir) / ref
        try:
            # Callers compare against resolve()d paths too (case/symlinks).
            return str(candidate.resolve())
        except OSError as e:
            logger.debug(f"Could not resolve image reference {ref}: {e}")
            return None

    def _run_for_each(self, process: Callable[[str], Any], image_paths: list[str]) -> None:
        """Run ``process`` on every path, in a thread pool when enabled; log failures."""
        if self.config.get("images", "parallel", default=True) and len(image_paths) > 1:
            with ThreadPoolExecutor(max_workers=self.worker_count()) as executor:
                futures = {executor.submit(process, p): p for p in image_paths}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error processing image {futures[future]}: {e}")
        else:
            for image_path in image_paths:
                try:
                    process(image_path)
                except Exception as e:
                    logger.error(f"Error processing image {image_path}: {e}")

    def worker_count(self) -> int:
        """Threads used for image processing: images.parallel_workers, else min(4, CPUs)."""
        workers = self.config.get("images", "parallel_workers", default=None)
        return int(workers) if workers else min(DEFAULT_MAX_WORKERS, (os.cpu_count() or 1))

    def _process_static_image(self, source_path: str, skip_cache: bool = False) -> None:
        """Publish a static/images image: the original at its own URL, plus a dithered copy.

        The dithered PNG goes to ``<dir>/dithered/<stem>.png`` and is recorded
        in dithered_images, so pages can show it and toggle to the original.
        Without dithering (or if it fails) only the original is published.

        Args:
            source_path: Path to the source image.
            skip_cache: Whether to skip cache and reprocess.
        """
        self._copy_static_image(source_path)
        dither = self.config.get("images", "dither", default=True)
        if not dither:
            return

        original_path = self._static_output_path(source_path)
        dithered_path = _dithered_path_for(original_path)
        self._write_legacy_original_copy(source_path, original_path)
        dither_method = self.config.get("images", "dither_method", default="bayer")
        dither_colors = self.config.get("images", "dither_colors", default=4)
        file_hash = self._file_hash(source_path) if not skip_cache else None
        # "static-v2": the dithered copy moved from the image's own URL to dithered/.
        cache_key = f"static-v2:{source_path}:{file_hash}:{dither}:{dither_method}:{dither_colors}"

        if not skip_cache and self._static_cache_hit(cache_key, dithered_path):
            logger.debug(f"Using cached version of static image: {source_path}")
            self._register_static_pair(original_path, dithered_path)
            self._count(images_cached=1, cache_hits=1)
            return

        try:
            self._write_static_dithered(source_path, dithered_path, dither_method, dither_colors)
            if not skip_cache:
                self.cache[cache_key] = _file_signature(dithered_path)
            self._register_static_pair(original_path, dithered_path)
            self._count(
                images_processed=1,
                cache_misses=0 if skip_cache else 1,
                original_image_size=os.path.getsize(source_path),
                processed_image_size=os.path.getsize(dithered_path),
            )
        except Exception as e:
            # The original is already published, so the page just shows it.
            logger.error(
                f"Error dithering static image {source_path}: {e}",
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )

    def _static_cache_hit(self, cache_key: str, dithered_path: str) -> bool:
        """Whether the cached dithered copy is still the file in the output dir.

        The entry records the dithered file's size and mtime; anything else
        at that path (e.g. --clean wiped it) is a miss, as is an entry from
        an older cache layout.
        """
        cached_signature = self.cache.get(cache_key)
        if not isinstance(cached_signature, dict):
            return False
        if _file_signature(dithered_path) == cached_signature:
            return True
        logger.debug(f"Dithered static image changed since it was cached: {dithered_path}")
        return False

    def _write_static_dithered(
        self, source_path: str, dithered_path: str, dither_method: str, dither_colors: int
    ) -> None:
        os.makedirs(os.path.dirname(dithered_path), exist_ok=True)
        with Image.open(source_path) as opened:
            dithered = self._apply_dither(upright_image(opened), dither_method, dither_colors)
            dithered.save(dithered_path, format="PNG", optimize=True)
        logger.debug(f"Saved dithered image: {source_path} -> {dithered_path}")

    def _write_legacy_original_copy(self, source_path: str, original_path: str) -> None:
        """Also publish the original as ``<name>_original<ext>``, its URL before 0.5.0.

        Compatibility bridge for one release, so pages and links built by
        earlier versions keep resolving. REMOVE in Sonne 0.5.0, together with
        the mention in STATIC_LAYOUT_NOTICE.
        """
        legacy_path = _with_original_suffix(original_path)
        try:
            shutil.copy2(source_path, legacy_path)
        except OSError as e:
            logger.error(f"Error copying static image {source_path} to {legacy_path}: {e}")

    def _register_static_pair(self, original_path: str, dithered_path: str) -> None:
        self.dithered_images.add(self._site_url(original_path), self._site_url(dithered_path))

    def _register_variants(self, results: dict[Any, dict[str, str]]) -> None:
        """Record each dithered sized variant with its same-size, same-format original."""
        for key, dithered_by_format in results.items():
            if not isinstance(key, int):
                continue
            originals_by_format = results.get(f"{key}_original", {})
            for fmt, dithered_rel in dithered_by_format.items():
                original_rel = originals_by_format.get(fmt)
                if original_rel:
                    self.dithered_images.add("/" + original_rel, "/" + dithered_rel)

    def _site_url(self, output_path: str) -> str:
        """Root-relative URL of a file in the output directory."""
        return "/" + Path(os.path.relpath(output_path, self.paths["output"])).as_posix()

    def _copy_static_image(self, source_path: str) -> None:
        """Copy a static image to the output directory unchanged.

        Args:
            source_path: Path to the source image.
        """
        output_path = self._static_output_path(source_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            shutil.copy2(source_path, output_path)
            logger.debug(f"Copied static image: {source_path} -> {output_path}")
        except OSError as e:
            logger.error(f"Error copying static image {source_path} to {output_path}: {e}")

    def _static_output_path(self, source_path: str) -> str:
        """Output path mirroring the file's location under the static dir."""
        return os.path.join(
            self.paths["output"], os.path.relpath(source_path, self.paths.get("static"))
        )

    def process_image(
        self,
        source_path: str,
        output_filename: Optional[str] = None,
        options: Optional[dict[str, Any]] = None,
        skip_cache: bool = False,
    ) -> dict[str, dict[str, str]]:
        """Write resized originals and dithered variants of a content image.

        Args:
            source_path: Path to the source image.
            output_filename: Output filename stem; defaults to the source's stem.
            options: Overrides for the ``dither``, ``optimize``, ``formats`` and
                ``sizes`` image settings.
            skip_cache: Whether to skip cache and reprocess.

        Returns:
            Mapping of variant key (``<size>_original`` for originals, the
            integer size for dithered variants) -> format -> output-relative
            path. On an unexpected error, the variants written so far.
        """
        settings = self._variant_settings(options)
        file_hash = None if skip_cache else self._file_hash(source_path)
        cache_key = settings.cache_key(source_path, file_hash)
        started = time.perf_counter()

        if not skip_cache:
            cached = self._cached_variants(cache_key, source_path)
            if cached is not None:
                self._count(images_cached=1, cache_hits=1)
                if self.stats:
                    self.stats.record_image(source_path, time.perf_counter() - started, cached=True)
                self._register_variants(cached)
                return cached

        os.makedirs(os.path.join(self.paths["output"], VARIANTS_DIR), exist_ok=True)
        results: dict[Any, dict[str, str]] = {}
        width = height = 0
        try:
            with Image.open(source_path) as opened:
                image = upright_image(opened)
                width, height = image.size
                stem = output_filename or Path(source_path).stem
                for key, fmt, rel_path in self._write_variants(image, stem, settings):
                    results.setdefault(key, {})[fmt] = rel_path
            if not skip_cache and self.cache_file:
                self.cache[cache_key] = results
            self._register_variants(results)
            self._count(images_processed=1, cache_misses=0 if skip_cache else 1)
        except Exception as e:
            logger.error(
                f"Error processing image {source_path}: {e}",
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )

        if self.stats:
            self.stats.record_image(
                source_path,
                time.perf_counter() - started,
                method=settings.dither_method,
                cached=False,
                width=width,
                height=height,
            )
        return results

    def _variant_settings(self, options: Optional[dict[str, Any]]) -> VariantSettings:
        """Resolve image settings: per-call options, then config, then defaults.

        List-valued settings of the wrong type fall back to their defaults.
        Dithered variants default to the smallest size only, since dithering
        is a visual effect, not a srcset.
        """
        options = options or {}

        def setting(key, default):
            return options.get(key, self.config.get("images", key, default=default))

        sizes = _list_or_default(setting("sizes", DEFAULT_SIZES), DEFAULT_SIZES)
        dither_sizes = self.config.get("images", "dither_sizes", default=None)
        if not (dither_sizes and isinstance(dither_sizes, list)):
            dither_sizes = [min(sizes)]
        return VariantSettings(
            dither=setting("dither", True),
            optimize=setting("optimize", True),
            formats=_list_or_default(setting("formats", DEFAULT_FORMATS), DEFAULT_FORMATS),
            sizes=sizes,
            dither_method=self.config.get("images", "dither_method", default="bayer"),
            dither_colors=self.config.get("images", "dither_colors", default=4),
            webp_method=int(self.config.get("images", "webp_method", default=0)),
            webp_method_original=int(self.config.get("images", "webp_method_original", default=4)),
            dither_formats=_list_or_default(
                self.config.get("images", "dither_formats", default=DEFAULT_DITHER_FORMATS),
                DEFAULT_DITHER_FORMATS,
            ),
            dither_sizes=set(dither_sizes),
        )

    def _cached_variants(self, cache_key: str, source_path: str):
        """Cached results for a key, or None on a miss.

        A hit only counts if every output file still exists: ``sonne build
        --clean`` wipes the output dir but keeps the cache.
        """
        cached = self.cache.get(cache_key)
        if cached is None:
            return None
        if isinstance(cached, dict) and all(
            os.path.exists(os.path.join(self.paths["output"], rel))
            for fmts in cached.values()
            for rel in (fmts.values() if isinstance(fmts, dict) else [])
        ):
            return cached
        logger.debug(f"Cache hit for {source_path} but outputs missing; reprocessing")
        return None

    def _write_variants(
        self, image: "Image.Image", stem: str, settings: VariantSettings
    ) -> Iterator[tuple[Any, str, str]]:
        """Write every size/format variant; yield (variant key, format, path) per file."""
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        for width in settings.sizes:
            resized = _resize_to_width(image, width)
            for fmt, rel_path in self._save_formats(
                resized,
                f"{stem}_{width}_original",
                settings.formats,
                settings.webp_method_original,
                settings.optimize,
                "original",
            ):
                yield f"{width}_original", fmt, rel_path
            if not (settings.dither and width in settings.dither_sizes):
                continue
            dithered = self.dither(resized)
            logger.debug(f"Applied dithering to image {stem} at width {width}")
            for fmt, rel_path in self._save_formats(
                dithered,
                f"{stem}_{width}",
                settings.dither_formats,
                settings.webp_method,
                settings.optimize,
                "dithered",
            ):
                yield width, fmt, rel_path

    def _save_formats(
        self,
        image: "Image.Image",
        name_stem: str,
        formats: list[str],
        webp_method: int,
        optimize: bool,
        variant_kind: str,
    ) -> Iterator[tuple[str, str]]:
        """Save ``image`` in each format; yield (format, output-relative path) per success.

        A format that fails to save is logged and skipped.
        """
        for fmt in formats:
            rel_path = f"{VARIANTS_DIR}/{name_stem}.{fmt}"
            try:
                _save_image(
                    image,
                    os.path.join(self.paths["output"], rel_path),
                    fmt,
                    webp_method=webp_method,
                    optimize=optimize,
                )
            except Exception as e:
                logger.error(f"Error saving {variant_kind} image in {fmt} format: {e}")
                continue
            yield fmt, rel_path

    def dither(self, image: "Image.Image") -> "Image.Image":
        """Dither an image with the site's configured method and palette size.

        This is the supported entry point for data scripts that dither
        in-memory images, e.g. ``ImageProcessor(config, {}).dither(image)``.
        ``_apply_dither(image, method=None, colors=None)`` keeps working for
        existing callers.

        Args:
            image: Source PIL Image (any mode).

        Returns:
            The dithered image, ready to save as PNG.
        """
        return self._apply_dither(image)

    def _apply_dither(
        self, img: "Image.Image", method: Optional[str] = None, colors: Optional[int] = None
    ) -> "Image.Image":
        """Apply dithering to an image using the configured (or specified) method.

        Unknown method names fall back to bayer (with the same palette size)
        and are warned about once.

        Args:
            img: Source PIL Image (any mode).
            method: Dithering method name. If None, reads from config.
            colors: Number of palette levels/colors (clamped to 2-256). If
                None, reads from config.

        Returns:
            PIL Image ready to save as PNG.

        Supported methods (set via images.dither_method in sonne.yaml):
            bayer          — Ordered Bayer 4×4 dither, grayscale.  Best compression. (default)
            grayscale      — Grayscale + Floyd-Steinberg palette dither.
            1bit           — Pure 1-bit black/white Floyd-Steinberg halftone.
            threshold      — Hard 50% threshold, no dithering.
            color_median   — Keep color, reduce palette via RGB Median Cut + FS dither.
            color_octree   — Keep color, reduce palette via RGB Octree + FS dither.
            color_lab      — Keep color, reduce palette via k-means in CIELAB space + FS dither.
        """
        if method is None:
            method = self.config.get("images", "dither_method", default="bayer")
        if colors is None:
            colors = self.config.get("images", "dither_colors", default=4)
        colors = _clamp_palette_size(colors)
        method = (method or "bayer").lower().strip()

        if method == "bayer":
            return _bayer_dither(img, colors)
        if method in ("grayscale", "palette"):
            return _grayscale_palette_dither(img, colors)
        if method in ("1bit", "halftone", "floyd_steinberg"):
            return img.convert("L").convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        if method == "threshold":
            return img.convert("L").convert("1", dither=Image.Dither.NONE)
        if method == "color_median":
            return img.convert("RGB").quantize(
                colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG
            )
        if method == "color_octree":
            return img.convert("RGB").quantize(
                colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG
            )
        if method == "color_lab":
            return _lab_kmeans_dither(img, colors)
        self._warn_unknown_dither_method(method)
        return _bayer_dither(img, colors)

    def _count(self, **increments: int) -> None:
        """Add to BuildStatistics counters, if statistics are being collected.

        Only successes are counted. Byte sizes are recorded for static images
        only: a content image becomes many variants, with no single
        processed size to set against the source.
        """
        if not self.stats:
            return
        with self._lock:
            for counter, amount in increments.items():
                setattr(self.stats, counter, getattr(self.stats, counter) + amount)

    def _warn_unknown_dither_method(self, method: str) -> None:
        """Warn about an unknown dither method once per processor, not per image."""
        with self._lock:
            if method in self._warned_dither_methods:
                return
            self._warned_dither_methods.add(method)
        logger.warning(f"Unknown images.dither_method '{method}'; using 'bayer' instead")

    def dither_image(self, input_path: str, output_path: str) -> None:
        """Apply dithering to an image.

        Args:
            input_path: Path to the input image.
            output_path: Path to save the dithered image.
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with Image.open(input_path) as img:
                img = upright_image(img)
                dithered = self.dither(img)
                dithered.save(output_path, optimize=True, format="PNG")

            logger.debug(f"Dithered image: {input_path} -> {output_path}")
        except Exception as e:
            logger.error(f"Error dithering image {input_path}: {e}")

    def copy_original_image(self, input_path: str, output_path: str) -> None:
        """Copy the original image to the output directory.

        Args:
            input_path: Path to the input image.
            output_path: Path to save the copied image.
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            shutil.copy2(input_path, output_path)
            logger.debug(f"Copied original image: {input_path} -> {output_path}")
        except Exception as e:
            logger.error(f"Error copying original image {input_path}: {e}")


def upright_image(image: "Image.Image") -> "Image.Image":
    """The image rotated/flipped per its EXIF orientation (a copy, or the image itself).

    ImageOps.exif_transpose is typed Optional because it returns None in
    in-place mode; this is the not-in-place call.
    """
    transposed = ImageOps.exif_transpose(image)
    return image if transposed is None else transposed


def _joined(values) -> str:
    return "-".join(map(str, values))


def _list_or_default(value, default: list) -> list:
    return value if isinstance(value, list) else default


def _resize_to_width(image: "Image.Image", width: int) -> "Image.Image":
    """Scale down to ``width``, keeping the aspect ratio; never upscale."""
    if image.width <= width:
        return image.copy()
    height = int(image.height * (width / float(image.width)))
    resample = Image.Resampling.BICUBIC if width <= BICUBIC_MAX_WIDTH else Image.Resampling.LANCZOS
    return image.resize((width, height), resample)


def _save_image(
    image: "Image.Image", path: str, fmt: str, webp_method: int, optimize: bool
) -> None:
    """Save in ``fmt`` (a lowercase extension), converting modes the format can't store."""
    if fmt == "webp":
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        image.save(path, format="WEBP", quality=LOSSY_QUALITY, method=webp_method)
    elif fmt == "png":
        image.save(path, format="PNG", optimize=optimize)
    elif fmt in ("jpg", "jpeg"):
        image.convert("RGB").save(path, format="JPEG", quality=LOSSY_QUALITY, optimize=optimize)
    else:
        image.save(path, format=fmt.upper())


def _files_to_scan_for_refs(directories: list[Optional[str]]) -> Iterator[str]:
    """Files under the existing directories that may reference images, skipping dot-dirs."""
    for directory in directories:
        if not directory or not os.path.exists(directory):
            continue
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file_name in files:
                if os.path.splitext(file_name)[1].lower() in REF_SCAN_EXTENSIONS:
                    yield os.path.join(root, file_name)


def _find_images(directory: str, used_paths: Optional[set[str]]) -> list[str]:
    """Image files under a directory (sorted), minus hidden and (optionally) unused ones."""
    root = Path(directory)
    return [
        str(file_path)
        for file_path in sorted(root.rglob("*"))
        if _is_processable_image(file_path, root, used_paths)
    ]


def _is_processable_image(file_path: Path, root: Path, used_paths: Optional[set[str]]) -> bool:
    """A non-hidden raster image under root, and referenced if used_paths is given."""
    if file_path.suffix.lower() not in IMAGE_EXTENSIONS or not file_path.is_file():
        return False
    # Only parts below the scanned directory: the site itself may live
    # under a dot-directory (e.g. ~/.sites/blog).
    if any(part.startswith(".") for part in file_path.relative_to(root).parts):
        return False
    return used_paths is None or str(file_path.resolve()) in used_paths


def _dithered_path_for(original_path: str) -> str:
    """``<dir>/a.jpg`` -> ``<dir>/dithered/a.png``."""
    directory, file_name = os.path.split(original_path)
    stem = os.path.splitext(file_name)[0]
    return os.path.join(directory, DITHERED_DIR_NAME, stem + ".png")


def _with_original_suffix(path: str) -> str:
    """``x.png`` -> ``x_original.png``."""
    stem, ext = os.path.splitext(path)
    return f"{stem}_original{ext}"


def _clamp_palette_size(colors) -> int:
    """Palette size clamped to 2-256; unparseable values give the default."""
    try:
        return max(MIN_PALETTE_SIZE, min(MAX_PALETTE_SIZE, int(colors or DEFAULT_DITHER_COLORS)))
    except (TypeError, ValueError):
        return DEFAULT_DITHER_COLORS


def _bayer_dither(img: "Image.Image", levels: int = 4) -> "Image.Image":
    """Ordered Bayer 4×4 dithering on grayscale.

    Produces a regular dot-grid pattern. Compresses very well as PNG and
    avoids the streaky artifacts of error-diffusion on smooth gradients.

    Args:
        img: Source PIL Image (any mode).
        levels: Number of gray levels (2–256).

    Returns:
        PIL Image in P (palette) mode.
    """
    levels = max(MIN_PALETTE_SIZE, min(MAX_PALETTE_SIZE, int(levels)))
    gray = np.array(img.convert("L"), dtype=float) / 255.0
    height, width = gray.shape
    thresholds = np.tile(BAYER_4X4, (height // 4 + 1, width // 4 + 1))[:height, :width]
    step = 1.0 / (levels - 1)
    quantized = np.clip(np.floor(gray / step + thresholds) * step, 0.0, 1.0)
    out = Image.fromarray((quantized * 255).astype("uint8"), "L")
    # Palette mode compresses better as PNG; no dither, it is already applied.
    return out.convert("P", palette=Image.Palette.ADAPTIVE, colors=levels, dither=Image.Dither.NONE)


def _grayscale_palette_dither(img: "Image.Image", palette_colors: int = 4) -> "Image.Image":
    """Grayscale + Floyd-Steinberg palette dither.

    Args:
        img: Source PIL Image (any mode).
        palette_colors: Number of palette entries (2–256).

    Returns:
        PIL Image in P (palette) mode with a grayscale palette.
    """
    palette_colors = max(MIN_PALETTE_SIZE, min(MAX_PALETTE_SIZE, int(palette_colors)))
    return img.convert("L").convert(
        "P",
        palette=Image.Palette.ADAPTIVE,
        colors=palette_colors,
        dither=Image.Dither.FLOYDSTEINBERG,
    )


def _lab_kmeans_dither(img: "Image.Image", k: int = 4) -> "Image.Image":
    """Color quantization using k-means clustering in CIELAB color space.

    Minimises perceptual color error rather than RGB distance. Applies
    Floyd-Steinberg error diffusion using the LAB-derived palette.

    Args:
        img: Source PIL Image (any mode).
        k: Number of palette colors.

    Returns:
        PIL Image in P (palette) mode.
    """
    rgb = np.array(img.convert("RGB"), dtype=np.uint8)
    centres = _kmeans_centres(_srgb_to_lab(rgb).reshape(-1, 3), k)
    palette_rgb = (
        np.clip(_lab_to_srgb(centres.reshape(1, -1, 3)).reshape(-1, 3), 0, 1) * 255
    ).astype("uint8")
    indices = _diffuse_to_palette(rgb, centres, palette_rgb)
    paletted = Image.fromarray(indices, "P")
    flat_palette = palette_rgb.flatten().tolist()
    paletted.putpalette(flat_palette + [0] * (768 - len(flat_palette)))
    return paletted


def _kmeans_centres(pixels: np.ndarray, k: int) -> np.ndarray:
    """k cluster centres of (N, 3) LAB pixels (Lloyd's algorithm, seeded start)."""
    rng = np.random.default_rng(KMEANS_SEED)
    centres = pixels[rng.choice(len(pixels), k, replace=False)].copy()
    for _ in range(KMEANS_MAX_ITERATIONS):
        distances = np.sum((pixels[:, None] - centres[None]) ** 2, axis=-1)
        labels = np.argmin(distances, axis=-1)
        new_centres = np.array(
            [pixels[labels == i].mean(0) if (labels == i).any() else centres[i] for i in range(k)]
        )
        if np.allclose(centres, new_centres, atol=KMEANS_TOLERANCE):
            break
        centres = new_centres
    return centres


def _diffuse_to_palette(
    rgb: np.ndarray, centres_lab: np.ndarray, palette_rgb: np.ndarray
) -> np.ndarray:
    """Floyd-Steinberg in RGB, choosing each pixel's palette entry by LAB distance.

    Error diffusion is inherently serial, so this runs per pixel on plain
    Python floats: numpy's per-call overhead on 3-element arrays made it
    thousands of times slower than the other dither methods.

    Returns:
        (H, W) uint8 array of palette indices.
    """
    height, width, _ = rgb.shape
    working = rgb.astype(float).tolist()
    centres = centres_lab.tolist()
    palette = palette_rgb.astype(float).tolist()
    indices = []
    for r in range(height):
        row = working[r]
        below = working[r + 1] if r + 1 < height else None
        index_row = []
        for c in range(width):
            old = row[c]
            best = _nearest_centre(_pixel_to_lab(old), centres)
            index_row.append(best)
            err = [old[ch] - palette[best][ch] for ch in range(3)]
            if c + 1 < width:
                _add_scaled(row[c + 1], err, 7)
            if below is not None:
                if c - 1 >= 0:
                    _add_scaled(below[c - 1], err, 3)
                _add_scaled(below[c], err, 5)
                if c + 1 < width:
                    _add_scaled(below[c + 1], err, 1)
        indices.append(index_row)
    return np.array(indices, dtype=np.uint8).reshape(height, width)


def _add_scaled(pixel: list[float], err: list[float], sixteenths: int) -> None:
    """Diffuse ``sixteenths``/16 of the error into a neighbouring pixel."""
    for ch in range(3):
        pixel[ch] += err[ch] * sixteenths / 16


def _nearest_centre(lab: tuple[float, float, float], centres: list[list[float]]) -> int:
    """Index of the closest centre (squared Euclidean); first wins on ties."""
    best, best_distance = 0, None
    for i, centre in enumerate(centres):
        d0 = centre[0] - lab[0]
        d1 = centre[1] - lab[1]
        d2 = centre[2] - lab[2]
        distance = d0 * d0 + d1 * d1 + d2 * d2
        if best_distance is None or distance < best_distance:
            best, best_distance = i, distance
    return best


def _pixel_to_lab(pixel: list[float]) -> tuple[float, float, float]:
    """Scalar twin of _srgb_to_lab for one (possibly out-of-range) RGB pixel."""
    linear = [_channel_to_linear(min(max(v / 255.0, 0.0), 1.0)) for v in pixel]
    x, y, z = (
        (row[0] * linear[0] + row[1] * linear[1] + row[2] * linear[2]) / white
        for row, white in zip(_SRGB_TO_XYZ_ROWS, _D65_WHITE_VALUES)
    )
    fx, fy, fz = _lab_f(x), _lab_f(y), _lab_f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _channel_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lab_f(t: float) -> float:
    return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116


def _srgb_to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c):
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


def _srgb_to_lab(rgb_u8: np.ndarray) -> np.ndarray:
    """(..., 3) sRGB values in 0-255 (clipped) -> CIELAB."""
    rgb = _srgb_to_linear(np.clip(rgb_u8.astype(float) / 255.0, 0, 1))
    xyz = rgb @ SRGB_TO_XYZ.T / D65_WHITE

    def f(t):
        return np.where(t > 0.008856, t ** (1 / 3), 7.787 * t + 16 / 116)

    fx, fy, fz = f(xyz[..., 0]), f(xyz[..., 1]), f(xyz[..., 2])
    return np.stack([116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)], axis=-1)


def _lab_to_srgb(lab: np.ndarray) -> np.ndarray:
    """(..., 3) CIELAB -> sRGB in [0, 1]."""
    lightness, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (lightness + 16) / 116

    def f_inverse(t):
        return np.where(t > 0.206897, t**3, (t - 16 / 116) / 7.787)

    xyz = np.stack([f_inverse(a / 500 + fy), f_inverse(fy), f_inverse(fy - b / 200)], axis=-1)
    xyz *= D65_WHITE
    rgb_linear = np.clip(xyz @ XYZ_TO_SRGB.T, 0, 1)
    return np.clip(_linear_to_srgb(rgb_linear), 0, 1)


def _file_signature(path: str) -> Optional[dict[str, int]]:
    """Size and modification time of a file, or None if it does not exist."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
