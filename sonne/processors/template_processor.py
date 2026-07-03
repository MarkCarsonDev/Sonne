"""
Template processing for Sonne.
Handles rendering templates, processing Markdown, and extracting front matter.
"""

import os
import re
import json
import markdown
import yaml
import logging
from typing import Dict, Any, List, Tuple
from bs4 import BeautifulSoup

try:
    import jinja2
    from jinja2 import TemplateSyntaxError, UndefinedError
    # Try to import Markup from the correct location
    try:
        from markupsafe import Markup
    except ImportError:
        try:
            from jinja2 import Markup
        except ImportError:
            # Fallback if Markup is not available
            class Markup(str):
                pass
    JINJA_AVAILABLE = True
except ImportError:
    JINJA_AVAILABLE = False
    TemplateSyntaxError = None
    UndefinedError = None

logger = logging.getLogger('sonne')

class TemplateProcessor:
    """Processes templates and content files."""
    
    def __init__(self, config, paths: Dict[str, str]):
        """Initialize template processor.
        
        Args:
            config: Site configuration.
            paths: Dictionary of normalized paths.
        """
        self.config = config
        self.paths = paths
        self.markdown_extensions = [
            'markdown.extensions.meta',
            'markdown.extensions.tables',
            'markdown.extensions.fenced_code',
            'markdown.extensions.toc',
            'markdown.extensions.smarty',
            'markdown.extensions.footnotes',
            'markdown.extensions.attr_list',
            'markdown.extensions.def_list',
            'markdown.extensions.abbr',
            'markdown.extensions.sane_lists',
        ]
        
        # Initialize Jinja2 environment if available
        self.jinja_env = None
        if JINJA_AVAILABLE:
            # Make sure templates directory exists
            template_dirs = []
            if 'templates' in paths and paths['templates'] and os.path.exists(paths['templates']):
                template_dirs.append(paths['templates'])
            
            # Also add built-in templates
            built_in_templates = os.path.join(os.path.dirname(__file__), '..', 'templates')
            if os.path.exists(built_in_templates):
                template_dirs.append(built_in_templates)
                
            if template_dirs:
                logger.info(f"Template directories: {template_dirs}")
                
                # Create Jinja environment
                try:
                    self.jinja_env = jinja2.Environment(
                        loader=jinja2.FileSystemLoader(template_dirs),
                        autoescape=jinja2.select_autoescape(['html', 'xml']),
                        trim_blocks=True,
                        lstrip_blocks=True,
                    )
                    
                    # Add custom filters
                    self._register_jinja_filters()
                    
                    logger.info("Jinja environment initialized successfully")
                except Exception as e:
                    logger.error(f"Error initializing Jinja environment: {e}")
                    self.jinja_env = None
            else:
                logger.warning("No template directories found, template processing is disabled")

        # Check if dithering is enabled
        self.dithering_enabled = self.config.get('images', 'dither', default=True)
        logger.info(f"Dithering enabled: {self.dithering_enabled}")

        if JINJA_AVAILABLE and self.jinja_env:
            # Add a global variable for dithering status
            self.jinja_env.globals['dithering_enabled'] = self.dithering_enabled

            # Add custom filters for image processing
            self._register_jinja_filters()

    def validate_templates(self) -> List[str]:
        """Validate all templates for syntax errors.

        Returns:
            List of error messages. Empty list means all templates are valid.
        """
        if not JINJA_AVAILABLE or not self.jinja_env:
            return ["Jinja2 not available, cannot validate templates"]

        errors = []
        templates_dir = self.paths.get('templates')

        if not templates_dir or not os.path.exists(templates_dir):
            return ["Templates directory not found"]

        # Find all template files
        template_extensions = ['.html', '.htm', '.xml', '.txt', '.j2', '.jinja2']
        template_files = []

        for root, dirs, files in os.walk(templates_dir):
            for file in files:
                if any(file.endswith(ext) for ext in template_extensions):
                    rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                    template_files.append(rel_path)

        # Validate each template
        for template_path in template_files:
            try:
                # Try to load the template (this checks syntax)
                template = self.jinja_env.get_template(template_path)

                # Try a basic render with dummy data to catch more issues
                try:
                    # Provide minimal dummy context
                    template.render(site={}, page={}, content='')
                except UndefinedError:
                    # UndefinedError is expected - templates use variables we haven't provided
                    # We're just checking for syntax errors
                    pass
                except Exception as e:
                    # Other errors during rendering (not syntax errors)
                    errors.append(f"{template_path}: Render error - {str(e)}")

            except TemplateSyntaxError as e:
                errors.append(f"{template_path}:{e.lineno}: Syntax error - {e.message}")
            except Exception as e:
                errors.append(f"{template_path}: {str(e)}")

        return errors
            
    def _register_jinja_filters(self) -> None:
        """Register custom Jinja2 filters."""
        if not self.jinja_env:
            return
            
        # Date formatting
        self.jinja_env.filters['date'] = lambda d, fmt='%B %d, %Y': d.strftime(fmt)
        
        # Markdown rendering
        self.jinja_env.filters['markdown'] = lambda text: markdown.markdown(
            text, extensions=self.markdown_extensions
        )
        
        # Word count
        self.jinja_env.filters['word_count'] = lambda text: len(text.split())

        # Slugify — mirrors _slugify in blog_processor
        def _slugify_filter(text: str) -> str:
            import re as _re
            text = str(text).lower()
            text = _re.sub(r'[^\w\s-]', '', text)
            text = _re.sub(r'[\s_]+', '-', text.strip())
            return _re.sub(r'-+', '-', text)
        self.jinja_env.filters['slugify'] = _slugify_filter
        
        # Truncate words
        self.jinja_env.filters['truncate_words'] = lambda text, length=30: ' '.join(
            text.split()[:length]) + ('...' if len(text.split()) > length else '')
        
        def process_image_src(src, alt="Image", loading="lazy"):
            """Process image source to add dithering support if enabled.
            
            Args:
                src: Image source URL
                alt: Image alt text
                loading: Loading attribute value
                
            Returns:
                HTML structure for the image with dithering support if enabled
            """
            if not self.dithering_enabled:
                return f'<img src="{src}" alt="{alt}" loading="{loading}">'
                
            # Extract size and determine original URL
            size_match = re.search(r'_(\d+)\.', src)
            if size_match:
                size = size_match.group(1)
                original_src = src.replace(f'_{size}.', f'_{size}_original.')
            else:
                # Check if it's a standard image (from /images/ directory)
                filename, ext = os.path.splitext(src)
                original_src = f"{filename}_original{ext}"
                
            # Create HTML with dithering container
            html = f"""
            <div class="dithered-image-container">
                <img src="{src}" alt="{alt}" loading="{loading}" class="dithered">
                <img src="{original_src}" alt="{alt}" loading="{loading}" class="original">
                <div class="dither-toggle">
                    <div class="dither-toggle-dot"></div>
                    <div class="dither-toggle-dot empty"></div>
                    <div class="dither-toggle-dot"></div>
                    <div class="dither-toggle-dot empty"></div>
                    <div class="dither-toggle-dot"></div>
                    <div class="dither-toggle-dot empty"></div>
                    <div class="dither-toggle-dot"></div>
                    <div class="dither-toggle-dot empty"></div>
                    <div class="dither-toggle-dot"></div>
                </div>
            </div>
            """
            return Markup(html)
            
        self.jinja_env.filters['process_image'] = process_image_src
            
    def extract_front_matter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Extract front matter from content.
        
        Args:
            content: Content string possibly containing front matter.
            
        Returns:
            Tuple of (front_matter, content_without_front_matter).
        """
        # Check for YAML front matter (---...---)
        yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        yaml_match = re.match(yaml_pattern, content, re.DOTALL)
        
        if yaml_match:
            try:
                front_matter = yaml.safe_load(yaml_match.group(1))
                content_without_front_matter = yaml_match.group(2)
                return front_matter or {}, content_without_front_matter
            except Exception as e:
                logger.error(f"Error parsing YAML front matter: {e}")
                
        # Check for JSON front matter (;;;...;;;)
        json_pattern = r'^;;;\s*\n(.*?)\n;;;\s*\n(.*)$'
        json_match = re.match(json_pattern, content, re.DOTALL)
        
        if json_match:
            try:
                front_matter = json.loads(json_match.group(1))
                content_without_front_matter = json_match.group(2)
                return front_matter, content_without_front_matter
            except Exception as e:
                logger.error(f"Error parsing JSON front matter: {e}")
                
        # No front matter found
        return {}, content
        
    def process_markdown(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Process Markdown content.
        
        Args:
            content: Markdown content.
            
        Returns:
            Tuple of (front_matter, html_content).
        """
        # Extract front matter
        front_matter, content_without_front_matter = self.extract_front_matter(content)
        
        # Replace image paths from /static/images/ to /images/
        content_without_front_matter = self._replace_image_paths(content_without_front_matter)
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(
            content_without_front_matter,
            extensions=self.markdown_extensions
        )
        
        # Process image tags for dithering support
        if self.dithering_enabled:
            logger.debug("Dithering is enabled, processing image tags...")
            html_content = self._process_image_tags(html_content)
            logger.debug(f"After processing images, HTML length: {len(html_content)}")
        else:
            logger.debug("Dithering is disabled, skipping image processing")

        return front_matter, html_content
    
    def _replace_image_paths(self, content: str) -> str:
        """Replace image paths from /static/images/ to /images/.
        
        Args:
            content: Markdown content.
            
        Returns:
            Content with replaced image paths.
        """
        # Replace in markdown image syntax: ![alt](/static/images/img.jpg) -> ![alt](/images/img.jpg)
        pattern = r'!\[(.*?)\]\(/static/images/(.*?)\)'
        replacement = r'![\1](/images/\2)'
        content = re.sub(pattern, replacement, content)
        
        # Also replace in HTML <img> tags
        pattern = r'<img([^>]*?)src="/static/images/(.*?)"([^>]*?)>'
        replacement = r'<img\1src="/images/\2"\3>'
        content = re.sub(pattern, replacement, content)
        
        # Also replace image paths in the front matter content (for YAML and JSON)
        # Handle URLs in the format: "url: /static/images/image.jpg"
        pattern = r'(url:\s*)/static/images/(.*?)(\s)'
        replacement = r'\1/images/\2\3'
        content = re.sub(pattern, replacement, content)
        
        # Handle URLs in the format: "url": "/static/images/image.jpg"
        pattern = r'("url":\s*")/static/images/(.*?)(")'
        replacement = r'\1/images/\2\3'
        content = re.sub(pattern, replacement, content)
        
        return content
    
    def _process_image_tags(self, html_content: str) -> str:
        """Process image tags to add dithering support with captions and original image button.

        Args:
            html_content: HTML content with image tags.

        Returns:
            HTML content with processed image tags.
        """
        # Use html.parser explicitly for consistency and to avoid warnings
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all img tags
        img_tags = soup.find_all('img')
        logger.debug(f"Found {len(img_tags)} image tags to process for dithering")

        for idx, img in enumerate(img_tags):
            # Skip SVG images
            src = img.get('src', '')
            if src.endswith('.svg'):
                continue

            # Get attributes
            alt = img.get('alt', '')
            title = img.get('title', '')
            loading = img.get('loading', 'lazy')
            dithered_kb = img.get('data-dithered-size', '')
            original_kb = img.get('data-original-size', '')
            size_reduction = img.get('data-size-reduction', '')

            # Build dithered and original paths
            path_parts = src.split('/')
            filename = path_parts[-1]
            dir_parts = path_parts[:-1]
            stem = filename.rsplit('.', 1)[0] if '.' in filename else filename
            dithered_src = '/'.join(dir_parts + ['dithered', stem + '.png'])
            original_src = src

            # Figure container
            figure = soup.new_tag('figure')
            figure['class'] = 'dithered-image-figure'
            figure['data-image-id'] = f'img-{idx}'

            img_wrapper = soup.new_tag('div')
            img_wrapper['class'] = 'image-wrapper'

            img['class'] = 'dithered-image active'
            img['data-dithered-src'] = dithered_src
            img['data-original-src'] = original_src
            img['data-image-id'] = f'img-{idx}'
            img['loading'] = loading
            img['src'] = dithered_src

            # Figcaption: "title · Xk (−Y%)" + toggle button
            figcaption = soup.new_tag('figcaption')

            # Strip transform directives from title (format: "Display title | crop=16:9 rotate=90")
            display_title = title.split('|')[0].strip() if title and '|' in title else title
            caption_label = display_title or alt
            if caption_label:
                caption_text = soup.new_tag('span')
                caption_text['class'] = 'caption-text'
                if dithered_kb and size_reduction:
                    caption_text.string = f'{caption_label} · {dithered_kb} (−{size_reduction}%)'
                else:
                    caption_text.string = caption_label
                figcaption.append(caption_text)

            button = soup.new_tag('button')
            button['class'] = 'request-original-btn'
            button['data-image-id'] = f'img-{idx}'
            button['aria-label'] = 'Toggle between dithered and original image'
            if original_kb:
                button['data-original-size'] = original_kb
            # Dithering pattern icon (4×4 bayer halftone) + text
            button_text = soup.new_tag('span')
            button_text['class'] = 'btn-text'
            button_text.string = 'view original'
            # LTM-style quincunx dither icon (4 corners + center)
            dither_icon_svg = soup.new_tag('svg', attrs={
                'class': 'dither-icon-svg',
                'xmlns': 'http://www.w3.org/2000/svg',
                'viewBox': '0 0 100 100',
                'aria-hidden': 'true',
            })
            for rx, ry in [('13.51','13.58'),('37.93','37.86'),('62.21','13.58'),('13.51','62.14'),('62.21','62.14')]:
                rect = soup.new_tag('rect', attrs={'x': rx, 'y': ry, 'width': '24.28', 'height': '24.28', 'fill': 'currentColor'})
                dither_icon_svg.append(rect)
            button.append(dither_icon_svg)
            button.append(button_text)
            figcaption.append(button)

            # Build structure
            # First, we need to remember img's parent before we move it
            parent = img.parent
            parent_index = list(parent.children).index(img)

            # Extract img from current location and add to wrapper
            img_wrapper.append(img.extract())
            figure.append(img_wrapper)

            # Only add figcaption if there's alt text or button
            if alt or True:  # Always add for button
                figure.append(figcaption)

            # Insert figure at the position where img was
            if parent_index < len(list(parent.children)):
                parent.insert(parent_index, figure)
            else:
                parent.append(figure)

        return str(soup)
        
    def process_page(self, content: str, is_markdown: bool, source_path: str, variables: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """Process a page.
        
        Args:
            content: Page content.
            is_markdown: Whether the content is Markdown.
            source_path: Path to the source file.
            variables: Variables to use for substitution.
            
        Returns:
            Tuple of (front_matter, processed_content).
        """
        # Extract front matter and convert Markdown if needed
        if is_markdown:
            front_matter, html_content = self.process_markdown(content)
        else:
            front_matter, html_content = self.extract_front_matter(content)
            
        # Add source path to front matter
        front_matter['source_path'] = source_path
        
        # Add relative URL
        try:
            # For special sources like blog_index, tags_index, etc.
            if isinstance(source_path, str) and not os.path.exists(source_path):
                front_matter['url'] = variables.get('page', {}).get('url', '/')
            else:
                rel_url = os.path.relpath(
                    source_path, 
                    self.paths.get('content', '')
                )
                
                # Convert to web path format
                if is_markdown:
                    rel_url = rel_url.replace('\\', '/').replace('.md', '').replace('.markdown', '')
                else:
                    rel_url = rel_url.replace('\\', '/')
                    
                front_matter['url'] = '/' + rel_url
                
                # Format URL according to URL style configuration
                if hasattr(self.config, 'format_url'):
                    url_before = front_matter['url']
                    front_matter['url'] = self.config.format_url(front_matter['url'])
                    logger.debug(f"Formatted URL: {url_before} -> {front_matter['url']}")
            
        except Exception as e:
            logger.warning(f"Error calculating relative URL for {source_path}: {e}")
            front_matter['url'] = '/'
        
        # Process template
        template_name = None

        # First check if there's a template specified in the front matter,
        # or in the page variables dict (used for programmatically generated pages
        # like date archives where front_matter is empty)
        if 'template' in front_matter:
            template_name = front_matter['template']
        elif variables.get('page', {}).get('template'):
            template_name = variables['page']['template']
        elif isinstance(source_path, str):
            if source_path.endswith('.md'):
                # For blog posts or markdown pages, use appropriate template
                if '/blog/' in source_path:
                    template_name = self.config.get('blog', 'template', default='blog_post.html')
                else:
                    template_name = 'page.html'
            # Special cases for index pages
            elif source_path == 'blog_index':
                template_name = self.config.get('blog', 'list_template', default='blog_list.html')
            elif source_path.startswith('tags_'):
                taxonomies = self.config.get('blog', 'taxonomies', default={})
                tags_config = taxonomies.get('tags', {}) if isinstance(taxonomies, dict) else {}
                template_name = tags_config.get('list_template', 'tags.html')
            elif source_path.startswith('tag_'):
                taxonomies = self.config.get('blog', 'taxonomies', default={})
                tags_config = taxonomies.get('tags', {}) if isinstance(taxonomies, dict) else {}
                template_name = tags_config.get('template', 'tag.html')
            elif source_path.startswith('categories_'):
                taxonomies = self.config.get('blog', 'taxonomies', default={})
                categories_config = taxonomies.get('categories', {}) if isinstance(taxonomies, dict) else {}
                template_name = categories_config.get('list_template', 'categories.html')
            elif source_path.startswith('category_'):
                taxonomies = self.config.get('blog', 'taxonomies', default={})
                categories_config = taxonomies.get('categories', {}) if isinstance(taxonomies, dict) else {}
                template_name = categories_config.get('template', 'category.html')
        
        logger.debug(f"Template for {source_path}: {template_name}")
        
        if template_name and self.jinja_env:
            try:
                # Try to get the template
                template = self.jinja_env.get_template(template_name)
                logger.debug(f"Found template: {template_name}")
                
                # Copy all global variables to both root and site for maximum compatibility
                variables_for_template = {}
                
                # First, add all global variables to root level
                for key, value in variables.get('global', {}).items():
                    variables_for_template[key] = value
                
                # Then add site variables, which might override some globals
                for key, value in variables.get('site', {}).items():
                    variables_for_template[key] = value
                
                # Also ensure site has all global variables
                site_vars = dict(variables.get('site', {}))
                for key, value in variables.get('global', {}).items():
                    if key not in site_vars:
                        site_vars[key] = value
                
                # Make sure 'images' configuration is available at site level
                if 'images' not in site_vars and hasattr(self.config, 'config') and 'images' in self.config.config:
                    site_vars['images'] = self.config.config['images']
                
                # Add structured namespaces
                variables_for_template['site'] = site_vars
                
                # For index or taxonomy pages, use the page data from variables
                if isinstance(source_path, str) and (
                    source_path == 'blog_index' or 
                    source_path.startswith('tag_') or 
                    source_path.startswith('tags_') or
                    source_path.startswith('category_') or
                    source_path.startswith('categories_')):
                    variables_for_template['page'] = variables.get('page', {})
                else:
                    # For regular pages, use the front matter as page variables
                    # but also copy anything from the variables['page'] that doesn't exist in front_matter
                    for key, value in variables.get('page', {}).items():
                        if key not in front_matter:
                            front_matter[key] = value
                    variables_for_template['page'] = front_matter
                
                variables_for_template['content'] = Markup(html_content)  # Mark as safe
                
                # Debug: Print out variables that should be available
                logger.debug(f"Template variables (keys): {list(variables_for_template.keys())}")
                logger.debug(f"Site variables (keys): {list(variables_for_template['site'].keys())}")
                
                # Render the template
                processed_content = template.render(**variables_for_template)
                logger.debug(f"Rendered template {template_name} for {source_path}")

                # Inject dithering assets if enabled
                processed_content = self.inject_dithering_assets(processed_content)

                return front_matter, processed_content

            except jinja2.exceptions.TemplateNotFound:
                logger.warning(f"Template not found: {template_name}")
                # Fall back to direct HTML content
                processed_content = f"<html><body><h1>{front_matter.get('title', 'Untitled')}</h1>{html_content}</body></html>"
                processed_content = self.inject_dithering_assets(processed_content)

            except Exception as e:
                logger.error(f"Error rendering template {template_name}: {e}")
                # Fall back to simple content
                processed_content = f"<html><body><h1>Error rendering template</h1><p>{e}</p><div>{html_content}</div></body></html>"
                processed_content = self.inject_dithering_assets(processed_content)
        else:
            # No template or Jinja not available - use simple HTML
            processed_content = f"<html><body><h1>{front_matter.get('title', 'Untitled')}</h1>{html_content}</body></html>"
            processed_content = self.inject_dithering_assets(processed_content)

        return front_matter, processed_content
    
    def inject_dithering_assets(self, html_content: str) -> str:
        """Inject dithering CSS and JS inline into HTML content if dithering is enabled.

        Args:
            html_content: HTML content to inject into.

        Returns:
            HTML content with dithering assets injected.
        """
        # Skip if dithering is disabled
        if not self.dithering_enabled:
            return html_content

        # Use html.parser explicitly for consistency and to avoid warnings
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check if head tag exists
        head = soup.head
        if not head:
            # Create head if it doesn't exist
            head = soup.new_tag('head')
            if soup.html:
                soup.html.insert(0, head)
            else:
                # Create html tag if it doesn't exist
                html = soup.new_tag('html')
                soup.append(html)
                html.append(head)

        # Check if body tag exists
        body = soup.body
        if not body:
            # Create body if it doesn't exist
            body = soup.new_tag('body')
            if soup.html:
                soup.html.append(body)
            else:
                # Create html tag if it doesn't exist
                html = soup.new_tag('html')
                soup.append(html)
                html.append(body)

        # Inline CSS for dithered images
        css_content = """
/* Dithered image styling - injected by Sonne */
.dithered-image-figure {
    margin: 2rem 0;
}

.dithered-image-figure img {
    width: 100%;
    height: auto;
    display: block;
}

.dithered-image-figure figcaption {
    margin-top: 0.5rem;
    font-family: monospace;
    font-size: 0.75rem;
    opacity: 0.6;
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    flex-wrap: wrap;
}

.caption-text {
    font-style: italic;
}

.request-original-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    padding: 0.2em 0.6em;
    font-size: 0.8rem;
    background: transparent;
    border: 1px solid var(--text-color, #fff);
    border-radius: 0.4em;
    cursor: pointer;
    color: var(--text-color, #fff);
    opacity: 0.5;
    transition: opacity 0.1s, background-color 0.1s;
    font-family: inherit;
}

.request-original-btn:hover {
    opacity: 1;
    background-color: var(--bg-hover, rgba(255,255,255,0.13));
}

.request-original-btn.showing-original {
    opacity: 1;
}

/* Dithering toggle icon (LTM quincunx pattern) */
.dither-icon-svg {
    width: 0.85em;
    height: 0.85em;
    flex-shrink: 0;
    vertical-align: middle;
}

/* Light mode: mix-blend-mode on the figure, not the img,
   so toggling to original disables multiply cleanly */
[data-theme="light"] .dithered-image-figure {
    mix-blend-mode: multiply;
}
[data-theme="light"] .dithered-image-figure.showing-original {
    mix-blend-mode: normal;
}
"""

        # Check if the CSS is already included
        css_exists = False
        for style in head.find_all('style'):
            if style.string and 'Dithered image styling - injected by Sonne' in style.string:
                css_exists = True
                break

        if not css_exists:
            style_tag = soup.new_tag('style')
            style_tag.string = css_content
            head.append(style_tag)

        # Inline JavaScript for image swapping
        js_content = """
// Dithered image functionality - injected by Sonne
(function() {
    'use strict';

    function initializeDitheredImages() {
        const buttons = document.querySelectorAll('.request-original-btn');

        buttons.forEach(function(button) {
            // Track state on button itself
            let showingDithered = true;

            button.addEventListener('click', function() {
                const figure = this.closest('.dithered-image-figure');
                if (!figure) return;

                const img = figure.querySelector('img');
                if (!img) return;

                const ditheredSrc = img.getAttribute('data-dithered-src');
                const originalSrc = img.getAttribute('data-original-src');

                const btnText = this.querySelector('.btn-text');
                // Toggle based on current state
                if (showingDithered) {
                    img.src = originalSrc;
                    const origSize = this.getAttribute('data-original-size');
                    if (btnText) btnText.textContent = origSize ? 'dithered (' + origSize + ')' : 'dithered';
                    this.classList.add('showing-original');
                    figure.classList.add('showing-original');
                    showingDithered = false;
                } else {
                    img.src = ditheredSrc;
                    if (btnText) btnText.textContent = 'view original';
                    this.classList.remove('showing-original');
                    figure.classList.remove('showing-original');
                    showingDithered = true;
                }
            });
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeDitheredImages);
    } else {
        initializeDitheredImages();
    }
})();
"""

        # Check if the JS is already included
        js_exists = False
        for script in body.find_all('script'):
            if script.string and 'Dithered image functionality - injected by Sonne' in script.string:
                js_exists = True
                break

        if not js_exists:
            script_tag = soup.new_tag('script')
            script_tag.string = js_content
            body.append(script_tag)

        # Return the modified HTML
        return str(soup)