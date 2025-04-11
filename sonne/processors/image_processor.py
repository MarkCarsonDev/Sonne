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
            
        # Skip if content directory doesn't exist
        if not os.path.exists(content_dir):
            logger.warning(f"Content directory does not exist: {content_dir}")
            return
            
        # Find all images
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        for ext in image_extensions:
            for file_path in Path(content_dir).glob(f'**/*{ext}'):
                try:
                    # Skip hidden files and directories
                    if any(part.startswith('.') for part in file_path.parts):
                        continue
                        
                    # Process the image
                    self.process_image(str(file_path), skip_cache=skip_cache)
                except Exception as e:
                    logger.error(f"Error processing image {file_path}: {e}")
                    
        # Save cache
        self._save_cache()
        
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
        dither = opts.get('dither', self.config.get('images', 'dither', False))
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
                        
                    # Create a version without dithering
                    normal_resized = resized.copy()
                    
                    # Apply dithering if requested
                    if dither:
                        # Convert to grayscale first if desired
                        if self.config.get('images', 'grayscale_before_dither', False):
                            resized = resized.convert('L')
                        
                        # Use Floyd-Steinberg dithering for better results
                        resized = resized.convert('1', dither=Image.FLOYDSTEINBERG)
                        logger.debug(f"Applied dithering to image: {source_path}")
                        
                    # Save in each requested format
                    for fmt in formats:
                        # Process both regular and dithered versions if dithering is enabled
                        versions_to_process = [('', normal_resized)]
                        if dither:
                            versions_to_process.append(('_dithered', resized))
                        
                        for suffix, img_version in versions_to_process:
                            # Generate output filename
                            output_name = f"{output_filename}_{width}{suffix}.{fmt}"
                            output_path = os.path.join(output_dir, output_name)
                            
                            # Save the image with appropriate format and options
                            try:
                                if fmt == 'webp':
                                    # WebP format requires RGB or RGBA mode
                                    save_img = img_version
                                    if img_version.mode == '1':
                                        save_img = img_version.convert('RGB')
                                    save_img.save(output_path, format='WEBP', quality=85, optimize=optimize)
                                elif fmt == 'png':
                                    # PNG works with all modes
                                    img_version.save(output_path, format='PNG', optimize=optimize)
                                elif fmt in ['jpg', 'jpeg']:
                                    # JPEG requires RGB mode
                                    save_img = img_version
                                    if img_version.mode in ['1', 'L', 'RGBA']:
                                        save_img = img_version.convert('RGB')
                                    save_img.save(output_path, format='JPEG', quality=85, optimize=optimize)
                                else:
                                    # Other formats, try native save
                                    img_version.save(output_path, format=fmt.upper())
                                    
                                logger.debug(f"Saved image: {output_path}")
                                    
                                # Add to results
                                key = size
                                if suffix:
                                    if f"{size}{suffix}" not in results:
                                        results[f"{size}{suffix}"] = {}
                                    results[f"{size}{suffix}"][fmt] = os.path.join('assets', 'images', output_name).replace('\\', '/')
                                else:
                                    if size not in results:
                                        results[size] = {}
                                    results[size][fmt] = os.path.join('assets', 'images', output_name).replace('\\', '/')
                            except Exception as e:
                                logger.error(f"Error saving image in {fmt} format: {e}")
                        
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