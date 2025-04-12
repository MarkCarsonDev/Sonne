"""
Template processing for Sonne.
Handles rendering templates, processing Markdown, and extracting front matter.
"""

import os
import re
import json
import markdown
import yaml
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from bs4 import BeautifulSoup
import re

try:
    import jinja2
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
        self.dithering_enabled = self.config.get('images', 'dither', True)
        
        if JINJA_AVAILABLE and self.jinja_env:
            # Add a global variable for dithering status
            self.jinja_env.globals['dithering_enabled'] = self.dithering_enabled
            
            # Add custom filters for image processing
            self._register_jinja_filters()
            
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
            html_content = self._process_image_tags(html_content)
        
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
        """Process image tags to add dithering support.
        
        Args:
            html_content: HTML content with image tags.
            
        Returns:
            HTML content with processed image tags.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all img tags
        for img in soup.find_all('img'):
            # Skip SVG images
            src = img.get('src', '')
            if src.endswith('.svg'):
                continue
                
            # Get attributes
            alt = img.get('alt', 'Image')
            loading = img.get('loading', 'lazy')
            
            # Create original path
            filename, ext = os.path.splitext(src)
            original_src = f"{filename}_original{ext}"
            
            # Create new container
            container = soup.new_tag('div')
            container['class'] = 'dithered-image-container'
            
            # Create original image
            original_img = soup.new_tag('img')
            original_img['src'] = original_src
            original_img['alt'] = alt
            original_img['loading'] = loading
            original_img['class'] = 'original'
            
            # Add dithered class to original img
            img['class'] = 'dithered'
            
            # Create toggle button
            toggle = soup.new_tag('div')
            toggle['class'] = 'dither-toggle'
            
            # Create dots for toggle button
            dot_classes = ['', 'empty', '', 'empty', '', 'empty', '', 'empty', '']
            for dot_class in dot_classes:
                dot = soup.new_tag('div')
                if dot_class:
                    dot['class'] = f'dither-toggle-dot {dot_class}'
                else:
                    dot['class'] = 'dither-toggle-dot'
                toggle.append(dot)
            
            # Replace original img with container
            img.replace_with(container)
            
            # Add elements to container
            container.append(img)
            container.append(original_img)
            container.append(toggle)
        
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
        
        # First check if there's a template specified in the front matter
        if 'template' in front_matter:
            template_name = front_matter['template']
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
                template_name = self.config.get('blog', 'taxonomies', {}).get('tags', {}).get('list_template', 'tags.html')
            elif source_path.startswith('tag_'):
                template_name = self.config.get('blog', 'taxonomies', {}).get('tags', {}).get('template', 'tag.html')
            elif source_path.startswith('categories_'):
                template_name = self.config.get('blog', 'taxonomies', {}).get('categories', {}).get('list_template', 'categories.html')
            elif source_path.startswith('category_'):
                template_name = self.config.get('blog', 'taxonomies', {}).get('categories', {}).get('template', 'category.html')
        
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

                processed_content = self.inject_dithering_assets(processed_content)
                
                return front_matter, processed_content
                
            except jinja2.exceptions.TemplateNotFound:
                logger.warning(f"Template not found: {template_name}")
                # Fall back to direct HTML content
                processed_content = f"<html><body><h1>{front_matter.get('title', 'Untitled')}</h1>{html_content}</body></html>"
                
            except Exception as e:
                logger.error(f"Error rendering template {template_name}: {e}")
                # Fall back to simple content
                processed_content = f"<html><body><h1>Error rendering template</h1><p>{e}</p><div>{html_content}</div></body></html>"
        else:
            # No template or Jinja not available - use simple HTML
            processed_content = f"<html><body><h1>{front_matter.get('title', 'Untitled')}</h1>{html_content}</body></html>"
            
        return front_matter, processed_content
    
    def inject_dithering_assets(self, html_content: str) -> str:
        """Inject dithering CSS and JS references into HTML content if dithering is enabled.
        
        Args:
            html_content: HTML content to inject into.
            
        Returns:
            HTML content with dithering assets injected.
        """
        # Skip if dithering is disabled
        if not self.config.get('images', 'dither', True):
            return html_content
            
        # Use BeautifulSoup to parse the HTML
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
        
        # Add CSS link to head
        css_link = soup.new_tag('link')
        css_link['rel'] = 'stylesheet'
        css_link['href'] = '/css/dithering.css'
        
        # Check if the CSS is already included
        css_exists = False
        for link in head.find_all('link'):
            if link.get('href') == '/css/dithering.css':
                css_exists = True
                break
                
        if not css_exists:
            head.append(css_link)
        
        # Add JS script to end of body
        js_script = soup.new_tag('script')
        js_script['src'] = '/js/dithering.js'
        js_script['defer'] = True
        
        # Check if the JS is already included
        js_exists = False
        for script in body.find_all('script'):
            if script.get('src') == '/js/dithering.js':
                js_exists = True
                break
                
        if not js_exists:
            body.append(js_script)
        
        # Return the modified HTML
        return str(soup)