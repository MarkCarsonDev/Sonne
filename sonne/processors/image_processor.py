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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger("sonne")

DEFAULT_FORMATS = ["webp", "png"]
DEFAULT_SIZES = [1200, 800, 400]
DEFAULT_DITHER_FORMATS = ["webp"]

# Where sized variants are written, relative to the output root.
VARIANTS_DIR = "assets/images"

# Image modes JPEG can store (dithered palette/1-bit images must convert).
JPEG_MODES = ("L", "RGB", "CMYK")

# Lossy quality for WebP and JPEG variants.
LOSSY_QUALITY = 85

# BICUBIC is visually identical to LANCZOS at small sizes and ~2x faster.
BICUBIC_MAX_WIDTH = 400

HASH_CHUNK_BYTES = 8192

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

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
DEFAULT_MAX_WORKERS = 4

# Files that may reference images, for images.only_used.
REF_SCAN_EXTENSIONS = (".md", ".html", ".htm", ".yaml", ".yml")
IMAGE_REF_PATTERN = re.compile(
    r'!\[.*?\]\(([^)\s"\']+)'  # markdown image
    r'|src=["\']([^"\']+)["\']'  # html src attribute
    r'|cover_img:\s*["\']?([^\s"\']+)'  # front matter cover, optionally quoted
)


@dataclass(frozen=True)
class VariantSettings:
    """Every setting that affects the variants written for a content image."""

    dither: bool
    optimize: bool
    formats: List[str]
    sizes: List[int]
    dither_method: str
    dither_colors: int
    webp_method: int
    webp_method_original: int
    dither_formats: List[str]
    dither_sizes: Set[int]

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

    def __init__(self, config, paths: Dict[str, str]):
        """Initialize image processor.

        Args:
            config: Site configuration.
            paths: Dictionary of normalized paths.
        """
        self.config = config
        self.paths = paths
        self.cache = {}
        self.cache_file = None
        self.stats = None  # Injected by SiteGenerator

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
            with open(self.cache_file, "r", encoding="utf-8") as f:
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
        except (IOError, OSError) as e:
            logger.error(f"Error reading file for hashing {file_path}: {e}")
            # Return a deterministic fallback based on path and mtime
            return hashlib.sha256(f"{file_path}:{os.path.getmtime(file_path)}".encode()).hexdigest()

    def process_all(self, content_dir: str, skip_cache: bool = False) -> None:
        """Process content images and static/images, then save the cache.

        Args:
            content_dir: Directory containing content to scan for images.
            skip_cache: Whether to skip cache and reprocess all images.
        """
        only_used = self.config.get("images", "only_used", default=False)
        used_paths = self._collect_used_images(content_dir) if only_used else None

        if content_dir and os.path.exists(content_dir):
            logger.info(f"Processing images in content directory: {content_dir}")
            self._process_directory_images(content_dir, skip_cache, used_paths=used_paths)

        static_images_dir = self._static_images_dir()
        if static_images_dir:
            logger.info(f"Processing images in static/images directory: {static_images_dir}")
            self._process_directory_images(
                static_images_dir, skip_cache, is_static=True, used_paths=used_paths
            )

        self._save_cache()

    def _static_images_dir(self) -> Optional[str]:
        """The site's static/images directory, if it exists."""
        static_dir = self.paths.get("static")
        if not static_dir:
            return None
        static_images_dir = os.path.join(static_dir, "images")
        return static_images_dir if os.path.exists(static_images_dir) else None

    def _collect_used_images(self, content_dir: str) -> Set[str]:
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
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
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

    def _process_directory_images(
        self,
        directory: str,
        skip_cache: bool = False,
        is_static: bool = False,
        used_paths: Optional[Set[str]] = None,
    ) -> None:
        """Process all images in a directory, optionally in parallel.

        Args:
            directory: Directory to scan for images.
            skip_cache: Whether to skip cache and reprocess.
            is_static: Whether this is the static/images directory.
            used_paths: If set, only process images whose absolute path is in this set.
        """
        image_paths = _find_images(directory, used_paths)
        if not image_paths:
            return
        process = self._process_static_image if is_static else self.process_image
        self._run_for_each(lambda path: process(path, skip_cache=skip_cache), image_paths)

    def _run_for_each(self, process: Callable[[str], Any], image_paths: List[str]) -> None:
        """Run ``process`` on every path, in a thread pool when enabled; log failures."""
        if self.config.get("images", "parallel", default=True) and len(image_paths) > 1:
            with ThreadPoolExecutor(max_workers=self._worker_count()) as executor:
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

    def _worker_count(self) -> int:
        workers = self.config.get("images", "parallel_workers", default=None)
        return int(workers) if workers else min(DEFAULT_MAX_WORKERS, (os.cpu_count() or 1))

    def _process_static_image(self, source_path: str, skip_cache: bool = False) -> None:
        """Dither a static/images image in place, keeping the original as ``*_original``.

        Falls back to a plain copy when dithering is disabled or fails.

        Args:
            source_path: Path to the source image.
            skip_cache: Whether to skip cache and reprocess.
        """
        dither = self.config.get("images", "dither", default=True)
        if not dither:
            self._copy_static_image(source_path)
            return

        output_path = self._static_output_path(source_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        original_path = _with_original_suffix(output_path)
        dither_method = self.config.get("images", "dither_method", default="bayer")
        dither_colors = self.config.get("images", "dither_colors", default=4)
        file_hash = self._file_hash(source_path) if not skip_cache else None
        cache_key = f"static:{source_path}:{file_hash}:{dither}:{dither_method}:{dither_colors}"

        if not skip_cache and cache_key in self.cache:
            # Only honor the hit if the outputs survived (--clean keeps the
            # cache but wipes the output dir)
            if os.path.exists(output_path) and os.path.exists(original_path):
                logger.debug(f"Using cached version of static image: {source_path}")
                return
            logger.debug(
                f"Cache hit for static image {source_path} but outputs missing; reprocessing"
            )

        try:
            self._write_static_pair(
                source_path, output_path, original_path, dither_method, dither_colors
            )
            if not skip_cache:
                self.cache[cache_key] = True
        except (IOError, OSError) as e:
            logger.error(f"I/O error processing static image {source_path}: {e}")
            self._copy_static_image(source_path)
        except Exception as e:
            logger.error(
                f"Unexpected error processing static image {source_path}: {e}",
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )
            self._copy_static_image(source_path)

    def _write_static_pair(
        self,
        source_path: str,
        output_path: str,
        original_path: str,
        dither_method: str,
        dither_colors: int,
    ) -> None:
        """Copy the original beside the output, then write the dithered image."""
        shutil.copy2(source_path, original_path)
        logger.debug(f"Copied original image: {source_path} -> {original_path}")
        with Image.open(source_path) as opened:
            image = ImageOps.exif_transpose(opened)
            dithered = self._apply_dither(image, dither_method, dither_colors)
            _save_in_source_format(dithered, output_path)
        logger.debug(f"Saved dithered image: {source_path} -> {output_path}")

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
        except (IOError, OSError) as e:
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
        options: Optional[Dict[str, Any]] = None,
        skip_cache: bool = False,
    ) -> Dict[str, Dict[str, str]]:
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
                if self.stats:
                    self.stats.record_image(source_path, time.perf_counter() - started, cached=True)
                return cached

        os.makedirs(os.path.join(self.paths["output"], VARIANTS_DIR), exist_ok=True)
        results: Dict[Any, Dict[str, str]] = {}
        width = height = 0
        try:
            with Image.open(source_path) as opened:
                image = ImageOps.exif_transpose(opened)
                width, height = image.size
                stem = output_filename or Path(source_path).stem
                for key, fmt, rel_path in self._write_variants(image, stem, settings):
                    results.setdefault(key, {})[fmt] = rel_path
            if not skip_cache and self.cache_file:
                self.cache[cache_key] = results
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

    def _variant_settings(self, options: Optional[Dict[str, Any]]) -> VariantSettings:
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
    ) -> Iterator[Tuple[Any, str, str]]:
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
        formats: List[str],
        webp_method: int,
        optimize: bool,
        variant_kind: str,
    ) -> Iterator[Tuple[str, str]]:
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
        self, img: "Image.Image", method: str = None, colors: int = None
    ) -> "Image.Image":
        """Apply dithering to an image using the configured (or specified) method.

        Unknown method names fall back to bayer.

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
        elif method in ("grayscale", "palette"):
            return _grayscale_palette_dither(img, colors)
        elif method in ("1bit", "halftone", "floyd_steinberg"):
            return img.convert("L").convert("1", dither=Image.FLOYDSTEINBERG)
        elif method == "threshold":
            return img.convert("L").convert("1", dither=Image.NONE)
        elif method == "color_median":
            return img.convert("RGB").quantize(colors=colors, method=0, dither=1)
        elif method == "color_octree":
            return img.convert("RGB").quantize(colors=colors, method=2, dither=1)
        elif method == "color_lab":
            return _lab_kmeans_dither(img, colors)
        else:
            logger.warning(f"Unknown dither_method '{method}', defaulting to bayer")
            return _bayer_dither(img, DEFAULT_DITHER_COLORS)

    def dither_image(self, input_path: str, output_path: str) -> None:
        """Apply dithering to an image.

        Args:
            input_path: Path to the input image.
            output_path: Path to save the dithered image.
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with Image.open(input_path) as img:
                img = ImageOps.exif_transpose(img)
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


def _joined(values) -> str:
    return "-".join(map(str, values))


def _list_or_default(value, default: List) -> List:
    return value if isinstance(value, list) else default


def _resize_to_width(image: "Image.Image", width: int) -> "Image.Image":
    """Scale down to ``width``, keeping the aspect ratio; never upscale."""
    if image.width <= width:
        return image.copy()
    height = int(image.height * (width / float(image.width)))
    resample = Image.BICUBIC if width <= BICUBIC_MAX_WIDTH else Image.LANCZOS
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


def _files_to_scan_for_refs(directories: List[Optional[str]]) -> Iterator[str]:
    """Files under the existing directories that may reference images, skipping dot-dirs."""
    for directory in directories:
        if not directory or not os.path.exists(directory):
            continue
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file_name in files:
                if file_name.endswith(REF_SCAN_EXTENSIONS):
                    yield os.path.join(root, file_name)


def _find_images(directory: str, used_paths: Optional[Set[str]]) -> List[str]:
    """Image files under a directory, minus hidden ones and (optionally) unused ones."""
    root = Path(directory)
    image_paths = []
    for ext in IMAGE_EXTENSIONS:
        for file_path in root.glob(f"**/*{ext}"):
            # Only parts below the scanned directory: the site itself may
            # live under a dot-directory (e.g. ~/.sites/blog).
            if any(part.startswith(".") for part in file_path.relative_to(root).parts):
                continue
            if used_paths is not None and str(file_path.resolve()) not in used_paths:
                logger.debug(f"Skipping unused image: {file_path}")
                continue
            image_paths.append(str(file_path))
    return image_paths


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
    return out.convert("P", palette=1, colors=levels, dither=0)


def _grayscale_palette_dither(img: "Image.Image", palette_colors: int = 4) -> "Image.Image":
    """Grayscale + Floyd-Steinberg palette dither.

    Args:
        img: Source PIL Image (any mode).
        palette_colors: Number of palette entries (2–256).

    Returns:
        PIL Image in P (palette) mode with a grayscale palette.
    """
    palette_colors = max(MIN_PALETTE_SIZE, min(MAX_PALETTE_SIZE, int(palette_colors)))
    # palette=1 is Image.Palette.ADAPTIVE, dither=1 is Floyd-Steinberg
    return img.convert("L").convert("P", palette=1, colors=palette_colors, dither=1)


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


def _add_scaled(pixel: List[float], err: List[float], sixteenths: int) -> None:
    """Diffuse ``sixteenths``/16 of the error into a neighbouring pixel."""
    for ch in range(3):
        pixel[ch] += err[ch] * sixteenths / 16


def _nearest_centre(lab: Tuple[float, float, float], centres: List[List[float]]) -> int:
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


def _pixel_to_lab(pixel: List[float]) -> Tuple[float, float, float]:
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


def _save_in_source_format(image: "Image.Image", path: str) -> None:
    """Save under the source's own file name, in the format its extension names.

    The static pipeline keeps the dithered image at the original URL (the
    client-side toggle derives ``*_original`` from it), so a JPEG stays a
    JPEG. JPEG cannot store the palette or 1-bit modes dithering produces.
    """
    extension = os.path.splitext(path)[1].lower()
    if Image.registered_extensions().get(extension) == "JPEG" and image.mode not in JPEG_MODES:
        image = image.convert("RGB")
    image.save(path, optimize=True)
