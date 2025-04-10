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

try:
    import jinja2
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
            self.jinja_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader([
                    paths.get('templates', ''),
                    # Also add built-in templates
                    os.path.join(os.path.dirname(__file__), '..', 'templates'),
                ]),
                autoescape=jinja2.select_autoescape(['html', 'xml']),
                trim_blocks=True,
                lstrip_blocks=True,
            )
            
            # Add custom filters
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
        
        # Convert Markdown to HTML
        html_content = markdown.markdown(
            content_without_front_matter,
            extensions=self.markdown_extensions
        )
        
        return front_matter, html_content
        
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
        rel_url = os.path.relpath(
            source_path, 
            os.path.join(self.paths.get('content', ''))
        )
        
        # Convert to web path format
        if is_markdown:
            rel_url = rel_url.replace('\\', '/').replace('.md', '.html').replace('.markdown', '.html')
        else:
            rel_url = rel_url.replace('\\', '/')
            
        front_matter['url'] = '/' + rel_url
        
        # Process template
        template_name = front_matter.get('template')
        if template_name and self.jinja_env:
            variables_with_content = dict(variables)
            variables_with_content['content'] = html_content
            variables_with_content['page'] = front_matter
            
            try:
                template = self.jinja_env.get_template(template_name)
                processed_content = template.render(**variables_with_content)
            except jinja2.exceptions.TemplateNotFound:
                logger.warning(f"Template not found: {template_name}")
                # Fall back to simple variable substitution
                from sonne.core.variable_manager import VariableManager
                vm = VariableManager(self.config, '')
                vm.variables = {'global': {}, 'site': variables, 'page': front_matter}
                processed_content = vm.substitute_variables(html_content)
        else:
            # Use simple variable substitution
            from sonne.core.variable_manager import VariableManager
            vm = VariableManager(self.config, '')
            vm.variables = {'global': {}, 'site': variables, 'page': front_matter}
            processed_content = vm.substitute_variables(html_content)
            
        return front_matter, processed_content