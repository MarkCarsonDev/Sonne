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
from sonne.utils.file_utils import copy_static_files, ensure_dir, copy_template_static_files

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
        
        # Set default paths if not in config
        if 'paths' not in self.config.config:
            self.config.config['paths'] = {}
        
        # Ensure required path keys exist with defaults
        default_paths = {
            'content': 'content',
            'output': 'output',
            'static': 'static',
            'templates': 'templates',
            'data': 'data',
            'cache': '.cache',
            'scripts': 'scripts',
        }
        
        for key, default in default_paths.items():
            if key not in self.config.config['paths'] or not self.config.config['paths'][key]:
                self.config.config['paths'][key] = default
        
        # Normalize paths
        self.paths = {}
        for key, value in self.config.config['paths'].items():
            if value:  # Only add paths that have a value
                if not os.path.isabs(value):
                    full_path = os.path.abspath(os.path.join(self.base_dir, value))
                else:
                    full_path = value
                    
                # Ensure the directory exists for output paths
                if key in ['output', 'cache']:
                    os.makedirs(full_path, exist_ok=True)
                    
                self.paths[key] = full_path
            
        logger.info(f"Using URL style: {self.config.get_url_style()}")
        logger.info(f"Paths: {self.paths}")
        
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
            
            # Load variables - Scripts will be run here
            logger.info("Loading variables...")
            self.variable_manager.load_variables()
            
            # Debug: Print out all variables 
            logger.info("Global variables loaded: " + str(list(self.variable_manager.variables.get('global', {}).keys())))
            logger.info("Site variables loaded: " + str(list(self.variable_manager.variables.get('site', {}).keys())))
            
            # Process blog posts if enabled
            if self.config.get('blog', 'enabled', default=True):
                logger.info("Processing blog posts...")
                self.blog_processor.process_all_posts()
                
            # Process templates and pages
            logger.info("Processing pages...")
            self._process_pages()
            
            # Copy static files
            logger.info("Copying static files...")
            static_dir = self.paths.get('static')
            output_dir = self.paths['output']
            
            # First try user's static directory
            copy_static_files(static_dir, output_dir)
            
            # If it was empty or didn't exist, try template static files
            if not static_dir or not os.path.exists(static_dir):
                logger.info("Copying template static files...")
                copy_template_static_files(self.base_dir, output_dir)
            
            # Process images
            if not skip_images:
                logger.info("Processing images...")
                self.image_processor.process_all(
                    self.paths.get('content', ''),
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
        content_dir = self.paths.get('content')
        
        # Skip if content directory doesn't exist
        if not content_dir or not os.path.exists(content_dir):
            logger.warning(f"Content directory does not exist: {content_dir}")
            return
            
        # Process pages in the content directory, excluding blog directory
        blog_dir_name = self.config.get('blog', 'directory', default='blog')
        blog_dir = os.path.join(content_dir, blog_dir_name) if blog_dir_name else None
        
        for file_path in Path(content_dir).glob('**/*.*'):
            # Skip blog directory, it's handled separately
            if blog_dir and str(file_path).startswith(blog_dir):
                continue
                
            # Process HTML and Markdown files
            if file_path.suffix.lower() in ['.html', '.htm', '.md', '.markdown']:
                try:
                    self._process_page(file_path)
                except Exception as e:
                    logger.error(f"Error processing page {file_path}: {e}")
                    if logger.level <= logging.DEBUG:
                        import traceback
                        traceback.print_exc()
                    
    def _process_page(self, file_path: Path) -> None:
        """Process an individual page file.
        
        Args:
            file_path: Path to the page file.
        """
        # Determine relative path from content directory
        rel_path = file_path.relative_to(self.paths['content'])
        
        # For Markdown files, change extension to .html
        if file_path.suffix.lower() in ['.md', '.markdown']:
            output_rel_path = rel_path.with_suffix('.html')
        else:
            output_rel_path = rel_path
            
        # Get the URL style
        url_style = self.config.get_url_style()
        
        # Format output path based on URL style
        if url_style == 'directory':
            # For directory style, use path/to/file/index.html
            if output_rel_path.stem == 'index':
                # If it's already index.html, keep it as is
                output_path = Path(self.paths['output']) / output_rel_path.parent / 'index.html'
            else:
                # Otherwise, create a directory with index.html
                output_path = Path(self.paths['output']) / output_rel_path.parent / output_rel_path.stem / 'index.html'
        elif url_style == 'html':
            # For HTML style, use path/to/file.html
            output_path = Path(self.paths['output']) / output_rel_path
        else:  # 'clean' style - same as directory for file system
            if output_rel_path.stem == 'index':
                # If it's already index.html, keep it as is
                output_path = Path(self.paths['output']) / output_rel_path.parent / 'index.html'
            else:
                # Otherwise, create a directory with index.html
                output_path = Path(self.paths['output']) / output_rel_path.parent / output_rel_path.stem / 'index.html'
                
        logger.debug(f"Output path for {file_path}: {output_path} (URL style: {url_style})")
            
        # Ensure output directory exists
        ensure_dir(output_path.parent)
        
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Process the page
        is_markdown = file_path.suffix.lower() in ['.md', '.markdown']
        
        # Ensure all global variables are also in the site scope
        for key, value in self.variable_manager.variables.get('global', {}).items():
            if key not in self.variable_manager.variables.get('site', {}):
                self.variable_manager.variables['site'][key] = value
        
        # Get variables with proper structure
        variables = {
            'global': self.variable_manager.variables.get('global', {}),
            'site': self.variable_manager.variables.get('site', {}),
            'page': {}
        }
        
        # Process the page
        front_matter, processed_content = self.template_processor.process_page(
            content, 
            is_markdown,
            str(file_path),
            variables
        )
        
        # Write the processed content to output
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(processed_content)
            
        logger.debug(f"Processed page: {file_path} -> {output_path}")