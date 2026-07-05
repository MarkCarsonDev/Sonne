"""
Image processing for Sonne.
Handles optimizing, resizing, and converting images.
"""

import os
import re
import json
import shutil
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import logging
from typing import Dict, Any, Optional

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger('sonne')

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
        
        # Check if PIL is available
        if not PIL_AVAILABLE:
            logger.warning("Pillow not installed. Image processing is disabled.")
            logger.warning("Install with: pip install Pillow")
            
        # Setup cache if a cache directory is configured
        if 'cache' in self.paths:
            cache_dir = os.path.join(self.paths['cache'], 'images')
            os.makedirs(cache_dir, exist_ok=True)
            self.cache_file = os.path.join(cache_dir, 'image_cache.json')
            self._load_cache()
            
    def _load_cache(self) -> None:
        """Load image processing cache."""
        if not self.cache_file or not os.path.exists(self.cache_file):
            self.cache = {}
            return
            
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)
        except Exception as e:
            logger.error(f"Error loading image cache: {e}")
            self.cache = {}
            
    def _save_cache(self) -> None:
        """Save image processing cache."""
        if not self.cache_file:
            return
            
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving image cache: {e}")
            
    def _file_hash(self, file_path: str) -> str:
        """Generate a hash of a file to detect changes.

        Args:
            file_path: Path to the file.

        Returns:
            SHA-256 hash of the file (more secure than MD5).
        """
        h = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()
        except (IOError, OSError) as e:
            logger.error(f"Error reading file for hashing {file_path}: {e}")
            # Return a deterministic fallback based on path and mtime
            return hashlib.sha256(f"{file_path}:{os.path.getmtime(file_path)}".encode()).hexdigest()
        
    def _collect_used_images(self, content_dir: str) -> set:
        """Scan content and template files for image references.

        Returns a set of resolved absolute source paths. Absolute references
        (``/images/foo.png``) are mapped back into the static directory,
        which mirrors the output root; relative references resolve against
        the referencing file's directory. Quoted front-matter values
        (``cover_img: "x.jpg"``) are handled.
        """
        used = set()
        img_pattern = re.compile(
            r'!\[.*?\]\(([^)\s"\']+)'          # markdown image
            r'|src=["\']([^"\']+)["\']'         # html src attribute
            r'|cover_img:\s*["\']?([^\s"\']+)'  # front matter cover, optionally quoted
        )
        static_dir = self.paths.get('static')

        def add_ref(ref: str, root: str) -> None:
            if not ref or ref.startswith(('http://', 'https://', 'data:')):
                return
            if ref.startswith('/'):
                # Served from the output root, which mirrors the static dir
                # (the markdown pipeline collapses /static/images -> /images)
                if not static_dir:
                    return
                rel = ref.lstrip('/')
                if rel.startswith('static/'):
                    rel = rel[len('static/'):]
                candidate = Path(static_dir) / rel
            else:
                candidate = Path(root) / ref
            try:
                # resolve() on both sides of the comparison (case/symlinks)
                used.add(str(candidate.resolve()))
            except OSError as e:
                logger.debug(f"Could not resolve image reference {ref}: {e}")

        templates_dir = self.paths.get('templates')
        scan_dirs = [d for d in (content_dir, templates_dir) if d and os.path.exists(d)]
        for scan_dir in scan_dirs:
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for fname in files:
                    if not fname.endswith(('.md', '.html', '.htm', '.yaml', '.yml')):
                        continue
                    try:
                        with open(os.path.join(root, fname), 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        for m in img_pattern.finditer(text):
                            add_ref(m.group(1) or m.group(2) or m.group(3), root)
                    except Exception as e:
                        logger.debug(f"Could not scan {fname} for image refs: {e}")
        return used

    def process_all(self, content_dir: str, skip_cache: bool = False) -> None:
        """Process all images in a directory.

        Args:
            content_dir: Directory containing content to scan for images.
            skip_cache: Whether to skip cache and reprocess all images.
        """
        # Skip if PIL is not available
        if not PIL_AVAILABLE:
            return

        only_used = self.config.get('images', 'only_used', default=False)
        used_paths = self._collect_used_images(content_dir) if only_used else None

        # Process content directory images
        if content_dir and os.path.exists(content_dir):
            logger.info(f"Processing images in content directory: {content_dir}")
            self._process_directory_images(content_dir, skip_cache, used_paths=used_paths)

        # Process static/images directory
        static_dir = self.paths.get('static')
        if static_dir and os.path.exists(static_dir):
            static_images_dir = os.path.join(static_dir, 'images')
            if os.path.exists(static_images_dir):
                logger.info(f"Processing images in static/images directory: {static_images_dir}")
                self._process_directory_images(static_images_dir, skip_cache, is_static=True, used_paths=used_paths)

        # Save cache
        self._save_cache()
    
    def _process_directory_images(self, directory: str, skip_cache: bool = False, is_static: bool = False, used_paths: set = None) -> None:
        """Process all images in a directory, optionally in parallel.

        Args:
            directory: Directory to scan for images.
            skip_cache: Whether to skip cache and reprocess.
            is_static: Whether this is the static/images directory.
            used_paths: If set, only process images whose absolute path is in this set.
        """
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        all_paths = []
        for ext in image_extensions:
            for file_path in Path(directory).glob(f'**/*{ext}'):
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                abs_path = str(file_path.resolve())
                if used_paths is not None and abs_path not in used_paths:
                    logger.debug(f"Skipping unused image: {file_path}")
                    continue
                all_paths.append(str(file_path))

        if not all_paths:
            return

        process_fn = self._process_static_image if is_static else (
            lambda p: self.process_image(p, skip_cache=skip_cache)
        )

        parallel = self.config.get('images', 'parallel', default=True)
        workers = self.config.get('images', 'parallel_workers', default=None)
        max_workers = int(workers) if workers else min(4, (os.cpu_count() or 1))

        if parallel and len(all_paths) > 1:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_fn, p): p for p in all_paths}
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Error processing image {futures[future]}: {e}")
        else:
            for p in all_paths:
                try:
                    process_fn(p)
                except Exception as e:
                    logger.error(f"Error processing image {p}: {e}")
    
    def _process_static_image(self, source_path: str, skip_cache: bool = False) -> None:
        """Process an image from the static/images directory.
        
        Args:
            source_path: Path to the source image.
            skip_cache: Whether to skip cache and reprocess.
        """
        # Skip if PIL is not available
        if not PIL_AVAILABLE:
            # Just copy the file
            self._copy_static_image(source_path)
            return
            
        # Get dithering flag from config. NOTE: Config.get takes *keys with a
        # keyword-only default — a positional True here used to be treated as
        # a key lookup ('images.dither.True'), which returned None and meant
        # static images were never dithered at all.
        dither = self.config.get('images', 'dither', default=True)
        if not dither:
            # If dithering is disabled, just copy the file
            self._copy_static_image(source_path)
            return
        
        # Calculate relative path from static/images
        static_dir = self.paths.get('static')
        rel_path = os.path.relpath(source_path, static_dir)
        
        # Determine output paths
        output_path = os.path.join(self.paths['output'], rel_path)
        output_dir = os.path.dirname(output_path)
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate original path with _original suffix
        filename, ext = os.path.splitext(output_path)
        original_path = f"{filename}_original{ext}"
        
        # Check cache if not skipping
        dither_method = self.config.get('images', 'dither_method', default='bayer')
        dither_colors = self.config.get('images', 'dither_colors', default=4)
        file_hash = self._file_hash(source_path) if not skip_cache else None
        cache_key = f"static:{source_path}:{file_hash}:{dither}:{dither_method}:{dither_colors}"
        
        if not skip_cache and cache_key in self.cache:
            logger.debug(f"Using cached version of static image: {source_path}")
            return
        
        try:
            # Copy original image with _original suffix
            shutil.copy2(source_path, original_path)
            logger.debug(f"Copied original image: {source_path} -> {original_path}")

            # Process and save dithered version to the main path
            img = None
            try:
                img = Image.open(source_path)
                img = ImageOps.exif_transpose(img)

                # Apply configured dithering pipeline
                dithered = self._apply_dither(img, dither_method, dither_colors)

                # Save dithered image to the output path
                dithered.save(output_path, optimize=True)
                logger.debug(f"Saved dithered image: {source_path} -> {output_path}")
            finally:
                # Ensure image is properly closed even on error
                if img is not None:
                    img.close()

            # Update cache
            if not skip_cache:
                self.cache[cache_key] = True

        except (IOError, OSError) as e:
            logger.error(f"I/O error processing static image {source_path}: {e}")
            # Fall back to just copying the file
            self._copy_static_image(source_path)
        except Exception as e:
            logger.error(f"Unexpected error processing static image {source_path}: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
            # Fall back to just copying the file
            self._copy_static_image(source_path)
    
    def _copy_static_image(self, source_path: str) -> None:
        """Copy a static image to the output directory.
        
        Args:
            source_path: Path to the source image.
        """
        # Calculate relative path from static directory
        static_dir = self.paths.get('static')
        rel_path = os.path.relpath(source_path, static_dir)
        
        # Determine output path
        output_path = os.path.join(self.paths['output'], rel_path)
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Copy the file
        try:
            shutil.copy2(source_path, output_path)
            logger.debug(f"Copied static image: {source_path} -> {output_path}")
        except (IOError, OSError) as e:
            logger.error(f"Error copying static image {source_path} to {output_path}: {e}")
        
    def process_image(self, source_path: str, output_filename: Optional[str] = None, 
              options: Optional[Dict[str, Any]] = None, skip_cache: bool = False) -> Dict[str, Dict[str, str]]:
        """Process an image with requested options.
        
        Args:
            source_path: Path to the source image.
            output_filename: Custom output filename (without extension).
            options: Custom processing options.
            skip_cache: Whether to skip cache and reprocess.
            
        Returns:
            Dictionary mapping size -> format -> path.
        """
        # Skip if PIL is not available
        if not PIL_AVAILABLE:
            # Return empty results
            return {}
            
        # Use provided options or defaults
        opts = options or {}
        dither = opts.get('dither', self.config.get('images', 'dither', default=True))  # Default to True
        optimize = opts.get('optimize', self.config.get('images', 'optimize', default=True))

        # Get formats and ensure it's a list
        formats = opts.get('formats', self.config.get('images', 'formats', default=['webp', 'png']))
        if not isinstance(formats, list):
            formats = ['webp', 'png']  # Fallback to default

        # Get sizes and ensure it's a list
        sizes = opts.get('sizes', self.config.get('images', 'sizes', default=[1200, 800, 400]))
        if not isinstance(sizes, list):
            sizes = [1200, 800, 400]  # Fallback to default

        # Generate output filename if not provided
        if not output_filename:
            output_filename = Path(source_path).stem

        # Settings that affect output — ALL of them must be part of the
        # cache key, or changing a setting serves stale variants.
        _dither_method = self.config.get('images', 'dither_method', default='bayer')
        _dither_colors = self.config.get('images', 'dither_colors', default=4)

        # --- Speed config ---
        webp_method          = int(self.config.get('images', 'webp_method',          default=0))
        webp_method_original = int(self.config.get('images', 'webp_method_original', default=4))

        # Formats for dithered saves (default: webp only — smaller, no quality loss vs png)
        dither_formats = self.config.get('images', 'dither_formats', default=['webp'])
        if not isinstance(dither_formats, list):
            dither_formats = ['webp']

        # Sizes to dither at (default: smallest only — dithered is a visual effect, not a srcset)
        dither_sizes_cfg = self.config.get('images', 'dither_sizes', default=None)
        if dither_sizes_cfg and isinstance(dither_sizes_cfg, list):
            dither_sizes = set(dither_sizes_cfg)
        else:
            dither_sizes = {min(sizes)}  # only the smallest by default

        # Check cache ("v2": cache key layout changed when dither settings
        # were added; the version prefix invalidates old entries once)
        file_hash = self._file_hash(source_path) if not skip_cache else None
        cache_key = (
            f"v2:{source_path}:{file_hash}:{dither}:{optimize}"
            f":{'-'.join(map(str, formats))}:{'-'.join(map(str, sizes))}"
            f":{_dither_method}:{_dither_colors}:{webp_method}:{webp_method_original}"
            f":{'-'.join(map(str, dither_formats))}:{'-'.join(map(str, sorted(dither_sizes)))}"
        )

        _t0 = time.perf_counter()

        if not skip_cache and cache_key in self.cache:
            if self.stats:
                self.stats.record_image(source_path, time.perf_counter() - _t0, cached=True)
            return self.cache[cache_key]

        # Prepare output directory
        output_dir = os.path.join(self.paths['output'], 'assets', 'images')
        os.makedirs(output_dir, exist_ok=True)

        # Process the image
        results = {}
        _img_width = _img_height = 0

        try:
            with Image.open(source_path) as img:
                img = ImageOps.exif_transpose(img)
                _img_width, _img_height = img.size
                original_mode = img.mode
                if original_mode not in ["RGB", "RGBA"]:
                    img = img.convert("RGB")

                for size in sizes:
                    width = size
                    # BICUBIC is visually identical to LANCZOS at small sizes and ~2x faster
                    resample = Image.BICUBIC if width <= 400 else Image.LANCZOS
                    if img.width > width:
                        wpercent = width / float(img.size[0])
                        height = int(img.size[1] * wpercent)
                        resized = img.resize((width, height), resample)
                    else:
                        resized = img.copy()

                    # Save original at every size
                    for fmt in formats:
                        output_name = f"{output_filename}_{width}_original.{fmt}"
                        output_path = os.path.join(output_dir, output_name)
                        try:
                            if fmt == 'webp':
                                resized.save(output_path, format='WEBP', quality=85,
                                             method=webp_method_original)
                            elif fmt == 'png':
                                resized.save(output_path, format='PNG', optimize=optimize)
                            elif fmt in ['jpg', 'jpeg']:
                                save_img = resized
                                if original_mode in ['1', 'L', 'RGBA']:
                                    save_img = resized.convert('RGB')
                                save_img.save(output_path, format='JPEG', quality=85, optimize=optimize)
                            else:
                                resized.save(output_path, format=fmt.upper())
                            if f"{size}_original" not in results:
                                results[f"{size}_original"] = {}
                            results[f"{size}_original"][fmt] = os.path.join(
                                'assets', 'images', output_name).replace('\\', '/')
                        except Exception as e:
                            logger.error(f"Error saving original image in {fmt} format: {e}")

                    # Honor images.dither — previously the flag was only in
                    # the cache key and dithered variants were written anyway
                    if not dither:
                        continue

                    # Only dither at configured sizes (default: smallest only)
                    if width not in dither_sizes:
                        continue

                    dithered = self._apply_dither(resized)
                    logger.debug(f"Applied dithering to image: {source_path}")

                    for fmt in dither_formats:
                        output_name = f"{output_filename}_{width}.{fmt}"
                        output_path = os.path.join(output_dir, output_name)
                        try:
                            if fmt == 'webp':
                                save_img = dithered.convert('RGB')
                                save_img.save(output_path, format='WEBP', quality=85,
                                              method=webp_method)
                            elif fmt == 'png':
                                dithered.save(output_path, format='PNG', optimize=optimize)
                            elif fmt in ['jpg', 'jpeg']:
                                save_img = dithered.convert('RGB')
                                save_img.save(output_path, format='JPEG', quality=85, optimize=optimize)
                            else:
                                dithered.save(output_path, format=fmt.upper())
                            if size not in results:
                                results[size] = {}
                            results[size][fmt] = os.path.join(
                                'assets', 'images', output_name).replace('\\', '/')
                        except Exception as e:
                            logger.error(f"Error saving dithered image in {fmt} format: {e}")
                
            # Save to cache
            if not skip_cache and self.cache_file:
                self.cache[cache_key] = results

        except Exception as e:
            logger.error(f"Error processing image {source_path}: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()

        if self.stats:
            self.stats.record_image(
                source_path,
                time.perf_counter() - _t0,
                method=_dither_method,
                cached=False,
                width=_img_width,
                height=_img_height,
            )

        return results
        
    def _apply_dither(self, img: 'Image.Image', method: str = None, colors: int = None) -> 'Image.Image':
        """Apply dithering to an image using the configured (or specified) method.

        Dispatches to the appropriate dithering implementation. Unknown method names
        fall back to bayer (the default).

        Args:
            img: Source PIL Image (any mode).
            method: Dithering method name. If None, reads from config.
            colors: Number of palette levels/colors. If None, reads from config.

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
            method = self.config.get('images', 'dither_method', default='bayer')
        if colors is None:
            colors = self.config.get('images', 'dither_colors', default=4)

        try:
            colors = max(2, min(256, int(colors or 4)))
        except (TypeError, ValueError):
            colors = 4

        method = (method or 'bayer').lower().strip()

        if method == 'bayer':
            return self._bayer_dither(img, colors)
        elif method in ('grayscale', 'palette'):
            return self._grayscale_palette_dither(img, colors)
        elif method in ('1bit', 'halftone', 'floyd_steinberg'):
            return img.convert('L').convert('1', dither=Image.FLOYDSTEINBERG)
        elif method == 'threshold':
            return img.convert('L').convert('1', dither=Image.NONE)
        elif method == 'color_median':
            return img.convert('RGB').quantize(colors=colors, method=0, dither=1)
        elif method == 'color_octree':
            return img.convert('RGB').quantize(colors=colors, method=2, dither=1)
        elif method == 'color_lab':
            return self._lab_kmeans_dither(img, colors)
        else:
            logger.warning(f"Unknown dither_method '{method}', defaulting to bayer")
            return self._bayer_dither(img, 4)

    def _bayer_dither(self, img: 'Image.Image', levels: int = 4) -> 'Image.Image':
        """Ordered Bayer 4×4 dithering on grayscale.

        Produces a regular dot-grid pattern. Compresses very well as PNG and
        avoids the streaky artifacts of error-diffusion on smooth gradients.

        Args:
            img: Source PIL Image (any mode).
            levels: Number of gray levels (2–256).

        Returns:
            PIL Image in P (palette) mode.
        """
        try:
            import numpy as np
        except ImportError:
            logger.warning("numpy not available for Bayer dithering, falling back to grayscale palette")
            return self._grayscale_palette_dither(img, levels)

        levels = max(2, min(256, int(levels)))
        gray = img.convert('L')
        arr = np.array(gray, dtype=float) / 255.0
        bayer = np.array([[ 0,  8,  2, 10],
                          [12,  4, 14,  6],
                          [ 3, 11,  1,  9],
                          [15,  7, 13,  5]], dtype=float) / 16.0
        h, w = arr.shape
        tiled = np.tile(bayer, (h // 4 + 1, w // 4 + 1))[:h, :w]
        step = 1.0 / (levels - 1)
        quantized = np.clip(np.floor(arr / step + tiled) * step, 0.0, 1.0)
        out = Image.fromarray((quantized * 255).astype('uint8'), 'L')
        # Convert to palette mode for better PNG compression (no dither — already applied)
        return out.convert('P', palette=1, colors=levels, dither=0)

    def _grayscale_palette_dither(self, img: 'Image.Image', palette_colors: int = 4) -> 'Image.Image':
        """Grayscale + Floyd-Steinberg palette dither.

        Args:
            img: Source PIL Image (any mode).
            palette_colors: Number of palette entries (2–256).

        Returns:
            PIL Image in P (palette) mode with a grayscale palette.
        """
        palette_colors = max(2, min(256, int(palette_colors)))
        gray = img.convert('L')
        # palette=1 is Image.Palette.ADAPTIVE, dither=1 is Floyd-Steinberg
        return gray.convert('P', palette=1, colors=palette_colors, dither=1)

    def _lab_kmeans_dither(self, img: 'Image.Image', k: int = 4) -> 'Image.Image':
        """Color quantization using k-means clustering in CIELAB color space.

        Minimises perceptual color error rather than RGB distance. Applies
        Floyd-Steinberg error diffusion using the LAB-derived palette.

        Args:
            img: Source PIL Image (any mode).
            k: Number of palette colors.

        Returns:
            PIL Image in P (palette) mode.
        """
        try:
            import numpy as np
        except ImportError:
            logger.warning("numpy not available for LAB k-means, falling back to color_median")
            return img.convert('RGB').quantize(colors=k, method=0, dither=1)

        def srgb_to_linear(c):
            return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

        def linear_to_srgb(c):
            return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)

        def to_lab(rgb_u8):
            rgb = srgb_to_linear(np.clip(rgb_u8.astype(float) / 255.0, 0, 1))
            M = np.array([[0.4124564, 0.3575761, 0.1804375],
                          [0.2126729, 0.7151522, 0.0721750],
                          [0.0193339, 0.1191920, 0.9503041]])
            xyz = rgb @ M.T / np.array([0.95047, 1.0, 1.08883])
            def f(t): return np.where(t > 0.008856, t ** (1/3), 7.787 * t + 16/116)
            fx, fy, fz = f(xyz[..., 0]), f(xyz[..., 1]), f(xyz[..., 2])
            return np.stack([116*fy - 16, 500*(fx-fy), 200*(fy-fz)], axis=-1)

        def from_lab(lab):
            L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
            fy = (L + 16) / 116
            def fi(t): return np.where(t > 0.206897, t**3, (t - 16/116) / 7.787)
            xyz = np.stack([fi(a/500+fy), fi(fy), fi(fy-b/200)], axis=-1)
            xyz *= np.array([0.95047, 1.0, 1.08883])
            M_inv = np.array([[ 3.2404542, -1.5371385, -0.4985314],
                              [-0.9692660,  1.8760108,  0.0415560],
                              [ 0.0556434, -0.2040259,  1.0572252]])
            rgb_lin = np.clip(xyz @ M_inv.T, 0, 1)
            return np.clip(linear_to_srgb(rgb_lin), 0, 1)

        arr = np.array(img.convert('RGB'), dtype=np.uint8)
        H, W, _ = arr.shape
        lab_arr = to_lab(arr)
        pixels = lab_arr.reshape(-1, 3)

        rng = np.random.default_rng(42)
        centres = pixels[rng.choice(len(pixels), k, replace=False)].copy()
        for _ in range(20):
            dists = np.sum((pixels[:, None] - centres[None]) ** 2, axis=-1)
            labels = np.argmin(dists, axis=-1)
            new_c = np.array([pixels[labels == i].mean(0) if (labels == i).any()
                              else centres[i] for i in range(k)])
            if np.allclose(centres, new_c, atol=1e-4):
                break
            centres = new_c

        palette_rgb = (np.clip(from_lab(centres.reshape(1, -1, 3)).reshape(-1, 3), 0, 1) * 255).astype('uint8')

        # Floyd-Steinberg in RGB with LAB-derived palette
        out_arr = arr.astype(float)
        result = np.zeros((H, W), dtype=np.uint8)
        for r in range(H):
            for c in range(W):
                old = out_arr[r, c]
                old_lab = to_lab(old.reshape(1, 1, 3)).reshape(3)
                best = int(np.argmin(np.sum((centres - old_lab) ** 2, axis=-1)))
                result[r, c] = best
                err = old - palette_rgb[best].astype(float)
                if c + 1 < W:
                    out_arr[r, c + 1] += err * 7 / 16
                if r + 1 < H and c - 1 >= 0:
                    out_arr[r + 1, c - 1] += err * 3 / 16
                if r + 1 < H:
                    out_arr[r + 1, c] += err * 5 / 16
                if r + 1 < H and c + 1 < W:
                    out_arr[r + 1, c + 1] += err * 1 / 16

        p_img = Image.fromarray(result, 'P')
        flat = palette_rgb.flatten().tolist() + [0] * (768 - len(palette_rgb.flatten()))
        p_img.putpalette(flat)
        return p_img

    def dither_image(self, input_path: str, output_path: str) -> None:
        """Apply dithering to an image.

        Args:
            input_path: Path to the input image.
            output_path: Path to save the dithered image.
        """
        # Skip if PIL is not available
        if not PIL_AVAILABLE:
            return

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with Image.open(input_path) as img:
                img = ImageOps.exif_transpose(img)
                dithered = self._apply_dither(img)
                dithered.save(output_path, optimize=True, format='PNG')

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