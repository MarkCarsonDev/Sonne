"""
Core site generation functionality for Sonne.
Coordinates the various processing steps to generate a complete static site.
"""

import os
import shutil
import logging
import time
from pathlib import Path

from sonne.core.config import Config
from sonne.core.variable_manager import VariableManager
from sonne.processors.blog_processor import BlogProcessor
from sonne.processors.template_processor import TemplateProcessor
from sonne.processors.image_processor import ImageProcessor
from sonne.utils.file_utils import copy_static_files, ensure_dir, copy_template_static_files
from sonne.utils.build_stats import BuildStatistics

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
            
        logger.debug(f"URL style: {self.config.get_url_style()}")
        logger.debug(f"Paths: {self.paths}")
        
        # Initialize processors
        self.variable_manager = VariableManager(config, self.base_dir)
        self.template_processor = TemplateProcessor(config, self.paths)
        self.image_processor = ImageProcessor(config, self.paths)
        self.blog_processor = BlogProcessor(config, self.paths, self.template_processor, self.variable_manager, self.image_processor)

        # Build statistics (shared across all processors)
        self.stats = BuildStatistics()

        
    def clean_output(self) -> None:
        """Clean the output directory by removing all files."""
        output_dir = self.paths.get('output')
        if not output_dir or not os.path.exists(output_dir):
            logger.warning(f"Output directory does not exist, nothing to clean: {output_dir}")
            return

        failed_items = []
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    logger.debug(f"Deleted file: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.debug(f"Deleted directory: {item_path}")
            except PermissionError as e:
                logger.error(f"Permission denied when cleaning {item_path}: {e}")
                failed_items.append(item)
            except OSError as e:
                logger.error(f"OS error when cleaning {item_path}: {e}")
                failed_items.append(item)
            except Exception as e:
                logger.error(f"Unexpected error cleaning {item_path}: {e}")
                failed_items.append(item)

        if failed_items:
            logger.warning(f"Failed to clean {len(failed_items)} items: {', '.join(failed_items)}")
        else:
            logger.info(f"Successfully cleaned output directory: {output_dir}")
        
    def generate(self, skip_images: bool = False, skip_cache: bool = False) -> BuildStatistics:
        """Generate the complete static site.

        Args:
            skip_images: Whether to skip image processing.
            skip_cache: Whether to ignore cache and rebuild everything.

        Returns:
            BuildStatistics with timing and metrics for this build.
        """
        self.stats = BuildStatistics()

        # Share the stats object with processors so they can record timings
        self.image_processor.stats = self.stats
        self.blog_processor.stats = self.stats
        self.variable_manager.stats = self.stats

        try:
            # Ensure output directory exists
            ensure_dir(self.paths['output'])

            blog_enabled = self.config.get('blog', 'enabled', default=True)
            step = 0
            total_steps = 5 + (1 if blog_enabled else 0) + (0 if skip_images else 1)

            def step_log(msg):
                nonlocal step
                step += 1
                logger.info(f"[{step}/{total_steps}] {msg}")

            # Step: Collect blog post metadata early so data scripts can reference posts
            if blog_enabled:
                step_log("Collecting post metadata")
                self.blog_processor.collect_post_metadata()
                post_count = len(self.blog_processor.posts)
                logger.info(f"         {post_count} post{'s' if post_count != 1 else ''} found")

            # Step: Run data scripts
            scripts_dir = getattr(self.variable_manager, 'scripts_dir', None)
            script_count = 0
            if scripts_dir and os.path.exists(scripts_dir):
                script_count = len([f for f in os.listdir(scripts_dir) if f.endswith('.py') and not f.startswith('_')])
            step_log(f"Running data scripts  ({script_count} script{'s' if script_count != 1 else ''})")
            _t = time.perf_counter()
            self.variable_manager.load_variables()
            self.stats.record_phase('scripts', time.perf_counter() - _t)
            logger.debug("Global variables: " + str(list(self.variable_manager.variables.get('global', {}).keys())))
            logger.debug("Site variables: " + str(list(self.variable_manager.variables.get('site', {}).keys())))

            # Step: Copy static files
            static_dir = self.paths.get('static')
            output_dir = self.paths['output']
            step_log("Copying static files")
            _t = time.perf_counter()
            copy_static_files(static_dir, output_dir)
            from sonne.utils.file_utils import copy_core_static_files
            copy_core_static_files(output_dir)
            if not static_dir or not os.path.exists(static_dir):
                copy_template_static_files(self.base_dir, output_dir)
            self.stats.record_phase('static_copy', time.perf_counter() - _t)

            # Step: Process images
            if not skip_images:
                content_dir = self.paths.get('content', '')
                img_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
                img_count = sum(
                    1 for r, _, fs in os.walk(content_dir) for f in fs
                    if os.path.splitext(f)[1].lower() in img_exts
                ) if content_dir and os.path.exists(content_dir) else 0
                workers = self.image_processor.config.get('images', 'parallel_workers', default=None)
                max_w = int(workers) if workers else min(4, (os.cpu_count() or 1))
                step_log(f"Processing images  ({img_count} image{'s' if img_count != 1 else ''}, {max_w} workers)")
                _t = time.perf_counter()
                self.image_processor.process_all(content_dir, skip_cache=skip_cache)
                self.stats.record_phase('images', time.perf_counter() - _t)

            # Step: Render blog posts
            if blog_enabled:
                step_log(f"Rendering blog posts  ({post_count} post{'s' if post_count != 1 else ''})")
                _t = time.perf_counter()
                self.blog_processor.process_all_posts()
                self.stats.record_phase('blog', time.perf_counter() - _t)

            # Step: Render pages
            content_dir = self.paths.get('content', '')
            blog_dir_name = self.config.get('blog', 'directory', default='blog')
            page_exts = {'.html', '.htm', '.md', '.markdown'}
            page_count = 0
            if content_dir and os.path.exists(content_dir):
                blog_sub = os.path.join(content_dir, blog_dir_name) if blog_dir_name else None
                for r, _, fs in os.walk(content_dir):
                    if blog_sub and r.startswith(blog_sub):
                        continue
                    page_count += sum(1 for f in fs if os.path.splitext(f)[1].lower() in page_exts)
            step_log(f"Rendering pages  ({page_count} page{'s' if page_count != 1 else ''})")
            _t = time.perf_counter()
            self._process_pages()
            self.stats.record_phase('pages', time.perf_counter() - _t)

            if hasattr(self, '_generate_projects_page'):
                self._generate_projects_page()

            # Step: Finalize
            step_log("Finalizing output")
            _t = time.perf_counter()
            self.variable_manager.save()
            self._create_dithering_assets(output_dir)
            if self.config.get('build', 'show_page_size', default=False):
                self._inject_page_sizes(output_dir)
            self.stats.record_phase('finalize', time.perf_counter() - _t)

            self.stats.finish()
            logger.info("Site generation complete")
            return self.stats

        except Exception as e:
            self.stats.finish()
            logger.error(f"Error generating site: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
            raise

    def _create_dithering_assets(self, output_dir: str) -> None:
        """Create dithering CSS and JS files.
        
        Args:
            output_dir: Output directory path.
        """
        # Create necessary directories
        css_dir = os.path.join(output_dir, 'css')
        js_dir = os.path.join(output_dir, 'js')
        os.makedirs(css_dir, exist_ok=True)
        os.makedirs(js_dir, exist_ok=True)
        
        # Define paths
        dithering_css_output = os.path.join(css_dir, 'dithering.css')
        dithering_js_output = os.path.join(js_dir, 'dithering.js')
        
        # Check if files need to be created or updated
        create_css = not os.path.exists(dithering_css_output)
        create_js = not os.path.exists(dithering_js_output)
        
        if create_css or create_js:
            logger.info("Creating dithering assets...")
            
            if create_css:
                with open(dithering_css_output, 'w', encoding='utf-8') as f:
                    f.write("""/* Image dithering functionality */
.dithered-image-container {
    position: relative;
    display: inline-block;
    overflow: hidden;
    max-width: 100%;
}

.dithered-image-container img {
    max-width: 100%;
    height: auto;
    transition: opacity 0.3s ease;
}

.dither-toggle {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 24px;
    height: 24px;
    background-color: rgba(0, 0, 0, 0.5);
    border-radius: 3px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(3, 1fr);
    gap: 2px;
    padding: 2px;
    cursor: pointer;
    opacity: 0.3;
    transition: opacity 0.3s ease;
    z-index: 10;
}

.dithered-image-container:hover .dither-toggle {
    opacity: 1;
}

.dither-toggle-dot {
    width: 100%;
    height: 100%;
    background-color: #fff;
    border-radius: 1px;
}

.dither-toggle-dot.empty {
    background-color: transparent;
}

.dithered-image-container img.original {
    position: absolute;
    top: 0;
    left: 0;
    opacity: 0;
    pointer-events: none;
}

.dithered-image-container.show-original img.dithered {
    opacity: 0;
    pointer-events: none;
}

.dithered-image-container.show-original img.original {
    opacity: 1;
    pointer-events: auto;
}

.dithered-image-container.show-original .dither-toggle {
    background-color: rgba(255, 255, 255, 0.5);
}

.dithered-image-container.show-original .dither-toggle-dot {
    background-color: #000;
}

.dithered-image-container.show-original .dither-toggle-dot.empty {
    background-color: transparent;
}

/* Make sure images in markdown content are responsive */
.markdown-content img,
article img,
.content img {
    max-width: 100%;
    height: auto;
}

/* For dithered images in gallery layouts */
.gallery .dithered-image-container,
.gallery-item .dithered-image-container {
    display: block;
    width: 100%;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
    .dither-toggle {
        width: 20px;
        height: 20px;
    }
}""")
                
            if create_js:
                with open(dithering_js_output, 'w', encoding='utf-8') as f:
                    f.write(r"""// Toggle dithered/original images
document.addEventListener('DOMContentLoaded', function() {
    // Process all img tags on the page
    processAllImages();
});

function processAllImages() {
    // First, process images that are already in dithered-image-containers
    const containedImages = document.querySelectorAll('.dithered-image-container img.dithered');
    
    // Then find standalone images that need to be processed
    const standaloneImages = document.querySelectorAll('img:not(.dithered):not(.original)');
    
    standaloneImages.forEach(function(img) {
        // Skip SVG images
        if (img.src.endsWith('.svg')) {
            return;
        }
        
        // Create container and controls
        wrapImageWithDitheringControls(img);
    });
    
    // Add click handlers to all toggle buttons
    const toggleButtons = document.querySelectorAll('.dither-toggle');
    toggleButtons.forEach(function(toggle) {
        // Ensure we don't add multiple event listeners
        if (!toggle.hasAttribute('data-has-listener')) {
            toggle.addEventListener('click', function(e) {
                const container = toggle.closest('.dithered-image-container');
                container.classList.toggle('show-original');
                e.stopPropagation();
            });
            toggle.setAttribute('data-has-listener', 'true');
        }
    });
}

function wrapImageWithDitheringControls(img) {
    // Skip if already processed
    if (img.closest('.dithered-image-container')) {
        return;
    }
    
    // Get image attributes
    const src = img.getAttribute('src');
    const alt = img.getAttribute('alt') || 'Image';
    const loading = img.getAttribute('loading') || 'lazy';
    
    // Create container
    const container = document.createElement('div');
    container.className = 'dithered-image-container';
    
    // Create original image path
    let originalSrc = '';
    if (src.includes('_')) {
        // Format: path/filename_size.ext
        const sizeMatch = src.match(/_(\d+)\./);
        if (sizeMatch) {
            const size = sizeMatch[1];
            originalSrc = src.replace(`_${size}.`, `_${size}_original.`);
        } else {
            // No size indicator, just add _original before extension
            const lastDotIndex = src.lastIndexOf('.');
            if (lastDotIndex !== -1) {
                originalSrc = src.substring(0, lastDotIndex) + '_original' + src.substring(lastDotIndex);
            } else {
                // No extension, just append _original
                originalSrc = src + '_original';
            }
        }
    } else {
        // Format: path/filename.ext
        const lastDotIndex = src.lastIndexOf('.');
        if (lastDotIndex !== -1) {
            originalSrc = src.substring(0, lastDotIndex) + '_original' + src.substring(lastDotIndex);
        } else {
            // No extension, just append _original
            originalSrc = src + '_original';
        }
    }
    
    // Create original image element
    const originalImg = document.createElement('img');
    originalImg.src = originalSrc;
    originalImg.className = 'original';
    originalImg.alt = alt;
    originalImg.loading = loading;
    
    // Add dithered class to original image
    img.className = (img.className ? img.className + ' ' : '') + 'dithered';
    
    // Create toggle button
    const toggle = document.createElement('div');
    toggle.className = 'dither-toggle';
    
    // Create dots pattern (X pattern)
    const dotClasses = ['', 'empty', '', 'empty', '', 'empty', '', 'empty', ''];
    dotClasses.forEach(function(className) {
        const dot = document.createElement('div');
        dot.className = 'dither-toggle-dot' + (className ? ' ' + className : '');
        toggle.appendChild(dot);
    });
    
    // Add event listener to toggle
    toggle.addEventListener('click', function(e) {
        container.classList.toggle('show-original');
        e.stopPropagation();
    });
    toggle.setAttribute('data-has-listener', 'true');
    
    // Replace the image with the container
    img.parentNode.insertBefore(container, img);
    container.appendChild(img);
    container.appendChild(originalImg);
    container.appendChild(toggle);
}

// Watch for dynamic content changes
if ('MutationObserver' in window) {
    const observer = new MutationObserver(function(mutations) {
        let needsProcessing = false;
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length) {
                needsProcessing = true;
            }
        });
        
        if (needsProcessing) {
            processAllImages();
        }
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
}""")
                
            logger.info("Created dithering assets in output directory")

    def _inject_page_sizes(self, output_dir: str) -> None:
        """Walk all generated HTML files and inject a page-size label.

        Shows base HTML size with an asterisk; hovering reveals total weight
        including all locally-served images referenced on the page.
        """
        import re as _re

        LABEL_OVERHEAD = 150  # rough bytes for injected markup

        CSS = (
            '<style id="page-size-css">'
            '#page-size-label{'
            'position:fixed;bottom:0.4rem;right:0.6rem;'
            'font-size:0.7rem;font-family:monospace;'
            'opacity:0.35;cursor:default;z-index:9999;'
            '}'
            '#page-size-label:hover{opacity:0.85}'
            '#page-size-label[data-full]::after{'
            'content:attr(data-full);'
            'display:none;'
            'position:absolute;bottom:1.4rem;right:0;'
            'background:var(--bg,#141514);'
            'border:0.1px solid #ffffff33;'
            'padding:0.2rem 0.5rem;'
            'border-radius:0.2em;'
            'white-space:nowrap;'
            'font-size:0.65rem;'
            'opacity:1;'
            '}'
            '#page-size-label[data-full]:hover::after{display:block}'
            '</style>'
        )
        CSS_BYTES = len(CSS.encode('utf-8'))

        img_src_re = _re.compile(
            r'src=["\']([^"\']+\.(?:webp|png|jpg|jpeg|gif|svg))["\']', _re.I
        )

        for root, _dirs, files in os.walk(output_dir):
            for fname in files:
                if not fname.endswith('.html'):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        html = f.read()

                    # Skip if already labelled (e.g. incremental rebuild)
                    if 'page-size-label' in html:
                        continue

                    base_bytes = len(html.encode('utf-8'))
                    total_bytes = base_bytes + CSS_BYTES + LABEL_OVERHEAD

                    # Sum sizes of all locally-referenced images
                    img_bytes = 0
                    for m in img_src_re.finditer(html):
                        src = m.group(1)
                        if src.startswith(('http://', 'https://', 'data:')):
                            continue
                        img_path = (
                            os.path.join(output_dir, src.lstrip('/'))
                            if src.startswith('/')
                            else os.path.join(root, src)
                        )
                        try:
                            img_bytes += os.path.getsize(img_path)
                        except OSError:
                            pass

                    label_text = f'~{total_bytes / 1024:.1f} KB*'
                    if img_bytes:
                        full_text = f'~{(total_bytes + img_bytes) / 1024:.0f} KB with images'
                        label_html = f'<span id="page-size-label" data-full="{full_text}">{label_text}</span>'
                    else:
                        label_html = f'<span id="page-size-label">{label_text}</span>'

                    new_html = html.replace('</body>', CSS + label_html + '</body>', 1)
                    with open(fpath, 'w', encoding='utf-8') as f:
                        f.write(new_html)
                except Exception as e:
                    logger.warning(f"Could not inject page size into {fpath}: {e}")

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