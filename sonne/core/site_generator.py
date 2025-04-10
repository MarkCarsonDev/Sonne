"""
Core site generation functionality for Sonne.
Coordinates the various processing steps to generate a complete static site.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from sonne.core.config import Config
from sonne.core.variable_manager import VariableManager
from sonne.processors.blog_processor import BlogProcessor
from sonne.processors.template_processor import TemplateProcessor
from sonne.processors.image_processor import ImageProcessor
from sonne.utils.file_utils import copy_static_files, ensure_dir

logger = logging.getLogger('sonne')

class SiteGenerator:
    """Main site generation coordinator."""
    
    def __init__(self, config: Config, base_dir: str = None):
        """Initialize site generator with configuration.
        
        Args:
            config: Site configuration.
            base_dir: Base directory for the site. Defaults to current directory.
        """
        self.config = config
        self.base_dir = os.path.abspath(base_dir or os.getcwd())
        
        # Normalize paths
        self.paths = config.normalize_paths(self.base_dir)
        
        # Initialize processors
        self.variable_manager = VariableManager(config, self.base_dir)
        self.template_processor = TemplateProcessor(config, self.paths)
        self.blog_processor = BlogProcessor(config, self.paths, self.template_processor, self.variable_manager)
        self.image_processor = ImageProcessor(config, self.paths)
        
    def clean_output(self) -> None:
        """Clean the output directory by removing all files."""
        output_dir = self.paths.get('output')
        if not output_dir or not os.path.exists(output_dir):
            return
            
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                logger.error(f"Error cleaning output directory: {e}")
                
        logger.info(f"Cleaned output directory: {output_dir}")
        
    def generate(self, skip_images: bool = False, skip_cache: bool = False) -> None:
        """Generate the complete static site.
        
        Args:
            skip_images: Whether to skip image processing.
            skip_cache: Whether to ignore cache and rebuild everything.
        """
        try:
            # Ensure output directory exists
            ensure_dir(self.paths['output'])
            
            # Load variables
            logger.info("Loading variables...")
            self.variable_manager.load_variables()
            
            # Process blog posts if enabled
            if self.config.get('blog', 'enabled', True):
                logger.info("Processing blog posts...")
                self.blog_processor.process_all_posts()
                
            # Process templates and pages
            logger.info("Processing pages...")
            self._process_pages()
            
            # Copy static files
            logger.info("Copying static files...")
            copy_static_files(self.paths['static'], self.paths['output'])
            
            # Process images
            if not skip_images:
                logger.info("Processing images...")
                self.image_processor.process_all(
                    os.path.join(self.base_dir, self.config.get('paths', 'content')),
                    skip_cache=skip_cache
                )
                
            # Save variables
            self.variable_manager.save()
            
            logger.info("Site generation completed successfully")
            
        except Exception as e:
            logger.error(f"Error generating site: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
            raise
            
    def _process_pages(self) -> None:
        """Process all pages in the content directory."""
        content_dir = self.paths['content']
        
        # Skip if content directory doesn't exist
        if not os.path.exists(content_dir):
            logger.warning(f"Content directory does not exist: {content_dir}")
            return
            
        # Process pages in the content directory, excluding blog directory
        blog_dir = os.path.join(content_dir, self.config.get('blog', 'directory', 'blog'))
        
        for file_path in Path(content_dir).glob('**/*.*'):
            # Skip blog directory, it's handled separately
            if str(file_path).startswith(blog_dir):
                continue
                
            # Process HTML and Markdown files
            if file_path.suffix.lower() in ['.html', '.htm', '.md', '.markdown']:
                try:
                    self._process_page(file_path)
                except Exception as e:
                    logger.error(f"Error processing page {file_path}: {e}")
                    
    def _process_page(self, file_path: Path) -> None:
        """Process an individual page file.
        
        Args:
            file_path: Path to the page file.
        """
        # Determine output path
        rel_path = file_path.relative_to(self.paths['content'])
        
        # For Markdown files, change extension to .html
        if file_path.suffix.lower() in ['.md', '.markdown']:
            output_path = Path(self.paths['output']) / rel_path.with_suffix('.html')
        else:
            output_path = Path(self.paths['output']) / rel_path
            
        # Ensure output directory exists
        ensure_dir(output_path.parent)
        
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Process the page
        front_matter, processed_content = self.template_processor.process_page(
            content, 
            file_path.suffix.lower() in ['.md', '.markdown'],
            str(file_path),
            self.variable_manager.get_all()
        )
        
        # Write the processed content to output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(processed_content)
            
        logger.debug(f"Processed page: {file_path} -> {output_path}")