"""
Image processing for Sonne.
Handles optimizing, resizing, and converting images.
"""

import os
import re
import json
import shutil
import hashlib
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple, Union

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
            MD5 hash of the file.
        """
        h = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                h.update(chunk)
        return h.hexdigest()
        
    def process_all(self, content_dir: str, skip_cache: bool = False) -> None:
        """Process all images in a directory.
        
        Args:
            content_dir: Directory containing content to scan for images.
            skip_cache: Whether to skip cache and reprocess all images.
        """
        # Skip if PIL is not available
        if not PIL_AVAILABLE:
            return
            
        # Process content directory images
        if content_dir and os.path.exists(content_dir):
            logger.info(f"Processing images in content directory: {content_dir}")
            self._process_directory_images(content_dir, skip_cache)
            
        # Process static/images directory
        static_dir = self.paths.get('static')
        if static_dir and os.path.exists(static_dir):
            static_images_dir = os.path.join(static_dir, 'images')
            if os.path.exists(static_images_dir):
                logger.info(f"Processing images in static/images directory: {static_images_dir}")
                self._process_directory_images(static_images_dir, skip_cache, is_static=True)
            
        # Save cache
        self._save_cache()
    
    def _process_directory_images(self, directory: str, skip_cache: bool = False, is_static: bool = False) -> None:
        """Process all images in a directory.
        
        Args:
            directory: Directory to scan for images.
            skip_cache: Whether to skip cache and reprocess.
            is_static: Whether this is the static/images directory.
        """
        # Find all images
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        for ext in image_extensions:
            for file_path in Path(directory).glob(f'**/*{ext}'):
                try:
                    # Skip hidden files and directories
                    if any(part.startswith('.') for part in file_path.parts):
                        continue
                    
                    # Process the image
                    if is_static:
                        self._process_static_image(str(file_path), skip_cache)
                    else:    
                        self.process_image(str(file_path), skip_cache=skip_cache)
                except Exception as e:
                    logger.error(f"Error processing image {file_path}: {e}")
    
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
            
        # Get dithering flag from config
        dither = self.config.get('images', 'dither', True)
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
        file_hash = self._file_hash(source_path) if not skip_cache else None
        cache_key = f"static:{source_path}:{file_hash}:{dither}"
        
        if not skip_cache and cache_key in self.cache:
            logger.debug(f"Using cached version of static image: {source_path}")
            return
        
        try:
            # Copy original image with _original suffix
            shutil.copy2(source_path, original_path)
            logger.debug(f"Copied original image: {source_path} -> {original_path}")
            
            # Process and save dithered version to the main path
            with Image.open(source_path) as img:
                # Convert to grayscale if specified
                if self.config.get('images', 'grayscale_before_dither', False):
                    img = img.convert('L')
                
                # Apply dithering
                dithered = img.convert('1', dither=Image.FLOYDSTEINBERG)
                
                # Save dithered image to the output path
                dithered.save(output_path, optimize=True)
                logger.debug(f"Saved dithered image: {source_path} -> {output_path}")
                
            # Update cache
            if not skip_cache:
                self.cache[cache_key] = True
                
        except Exception as e:
            logger.error(f"Error processing static image {source_path}: {e}")
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
        shutil.copy2(source_path, output_path)
        logger.debug(f"Copied static image: {source_path} -> {output_path}")
        
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
        dither = opts.get('dither', self.config.get('images', 'dither', True))  # Default to True
        optimize = opts.get('optimize', self.config.get('images', 'optimize', True))
        formats = opts.get('formats', self.config.get('images', 'formats', ['webp', 'png']))
        sizes = opts.get('sizes', self.config.get('images', 'sizes', [1200, 800, 400]))
        
        # Generate output filename if not provided
        if not output_filename:
            output_filename = Path(source_path).stem
            
        # Check cache
        file_hash = self._file_hash(source_path) if not skip_cache else None
        cache_key = f"{source_path}:{file_hash}:{dither}:{optimize}:{'-'.join(formats)}:{'-'.join(map(str, sizes))}"
        
        if not skip_cache and cache_key in self.cache:
            # Return cached results if available
            return self.cache[cache_key]
            
        # Prepare output directory
        output_dir = os.path.join(self.paths['output'], 'assets', 'images')
        os.makedirs(output_dir, exist_ok=True)
        
        # Process the image
        results = {}
        
        try:
            with Image.open(source_path) as img:
                # Convert image to RGB if it's in a different mode for better dithering
                original_mode = img.mode
                if original_mode not in ["RGB", "RGBA"]:
                    img = img.convert("RGB")
                
                # Process each size
                for size in sizes:
                    # Calculate dimensions maintaining aspect ratio
                    width = size
                    if img.width > width:
                        wpercent = (width / float(img.size[0]))
                        height = int((float(img.size[1]) * float(wpercent)))
                        resized = img.resize((width, height), Image.LANCZOS)
                    else:
                        resized = img.copy()
                        
                    # Always save original version (with _original suffix)
                    for fmt in formats:
                        # Generate output filename for original
                        output_name = f"{output_filename}_{width}_original.{fmt}"
                        output_path = os.path.join(output_dir, output_name)
                        
                        try:
                            if fmt == 'webp':
                                resized.save(output_path, format='WEBP', quality=85, optimize=optimize)
                            elif fmt == 'png':
                                resized.save(output_path, format='PNG', optimize=optimize)
                            elif fmt in ['jpg', 'jpeg']:
                                save_img = resized
                                if original_mode in ['1', 'L', 'RGBA'] and fmt in ['jpg', 'jpeg']:
                                    save_img = resized.convert('RGB')
                                save_img.save(output_path, format='JPEG', quality=85, optimize=optimize)
                            else:
                                resized.save(output_path, format=fmt.upper())
                                
                            # Add to results
                            if f"{size}_original" not in results:
                                results[f"{size}_original"] = {}
                            results[f"{size}_original"][fmt] = os.path.join('assets', 'images', output_name).replace('\\', '/')
                        except Exception as e:
                            logger.error(f"Error saving original image in {fmt} format: {e}")
                    
                    # Create dithered version (always for content images)
                    # Make a copy for dithering
                    dithered = resized.copy()
                    
                    # Convert to grayscale first if desired
                    if self.config.get('images', 'grayscale_before_dither', False):
                        dithered = dithered.convert('L')
                    
                    # Use Floyd-Steinberg dithering for better results
                    dithered = dithered.convert('1', dither=Image.FLOYDSTEINBERG)
                    logger.debug(f"Applied dithering to image: {source_path}")
                    
                    # Save dithered version in each format
                    for fmt in formats:
                        # For content images, generated files use standard naming pattern
                        # but the main output is the dithered version by default
                        output_name = f"{output_filename}_{width}.{fmt}"
                        output_path = os.path.join(output_dir, output_name)
                        
                        try:
                            if fmt == 'webp':
                                # WebP format requires RGB or RGBA mode
                                save_img = dithered.convert('RGB')
                                save_img.save(output_path, format='WEBP', quality=85, optimize=optimize)
                            elif fmt == 'png':
                                # PNG works with all modes
                                dithered.save(output_path, format='PNG', optimize=optimize)
                            elif fmt in ['jpg', 'jpeg']:
                                # JPEG requires RGB mode
                                save_img = dithered.convert('RGB')
                                save_img.save(output_path, format='JPEG', quality=85, optimize=optimize)
                            else:
                                # Other formats, try native save
                                dithered.save(output_path, format=fmt.upper())
                                
                            # Add to results
                            if size not in results:
                                results[size] = {}
                            results[size][fmt] = os.path.join('assets', 'images', output_name).replace('\\', '/')
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
            
        return results
        
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
                # Convert the image to grayscale
                img = img.convert('L')
                
                # Apply dithering
                img = img.convert('1')  # Convert to black and white with dithering
                
                # Save the optimized image
                img.save(output_path, optimize=True, format='PNG')
                
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