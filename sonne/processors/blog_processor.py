"""
Blog post processing for Sonne.
Handles parsing, rendering, and generating blog posts and related pages.
"""

import os
import re
import markdown
import shutil
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
import math

logger = logging.getLogger('sonne')

class BlogProcessor:
    """Processes blog posts and generates blog-related pages."""
    
    def __init__(self, config, paths: Dict[str, str], template_processor, variable_manager):
        """Initialize blog processor.
        
        Args:
            config: Site configuration.
            paths: Dictionary of normalized paths.
            template_processor: Template processor instance.
            variable_manager: Variable manager instance.
        """
        self.config = config
        self.paths = paths
        self.template_processor = template_processor
        self.variable_manager = variable_manager
        
        # Blog directory paths - Add safety checks
        content_path = self.paths.get('content', '')
        if content_path is None:
            content_path = ''
            
        output_path = self.paths.get('output', '')
        if output_path is None:
            output_path = ''
            
        blog_dir = self.config.get('blog', 'directory', default='blog')
        if blog_dir is None:
            blog_dir = 'blog'

        self.blog_content_dir = os.path.join(content_path, blog_dir)
        self.blog_output_dir = os.path.join(output_path, blog_dir)
        
        # Ensure blog output directory exists
        os.makedirs(self.blog_output_dir, exist_ok=True)
        
        # Initialize blog data
        self.posts = []
        self.taxonomies = {
            'tags': {},
            'categories': {},
        }
        
        # Cache URL style
        self.url_style = self.config.get_url_style() if hasattr(self.config, 'get_url_style') else 'clean'
        logger.debug(f"Using URL style: {self.url_style}")
        
    def process_all_posts(self) -> None:
        """Process all blog posts."""
        logger.info("Processing blog posts...")
        
        # Skip if blog directory doesn't exist
        if not os.path.exists(self.blog_content_dir):
            logger.warning(f"Blog directory does not exist: {self.blog_content_dir}")
            return
            
        # Collect all blog posts
        self._collect_posts()
        
        # Skip if no posts found
        if not self.posts:
            logger.info("No blog posts found")
            return
            
        # Sort posts by date (newest first)
        self._sort_posts()
        
        # Set navigation links (next/prev)
        self._set_navigation_links()
        
        # Build taxonomy collections
        self._build_taxonomies()
        
        # Save posts to global variables
        self.variable_manager.set('all_blog_posts', self.posts, 'global')
        
        # Render individual posts
        self._render_posts()
        
        try:
            # Generate index pages
            self._generate_index_pages()
        except Exception as e:
            logger.error(f"Error generating blog index pages: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
        
        try:
            # Generate taxonomy pages
            self._generate_taxonomy_pages()
        except Exception as e:
            logger.error(f"Error generating taxonomy pages: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
        
        # Generate RSS feed
        self._generate_rss_feed()
        
        logger.info(f"Processed {len(self.posts)} blog posts")
    
    def _sort_posts(self) -> None:
        """Sort posts by date (newest first)."""
        def get_sort_date(post):
            date_val = post.get('date', '')
            if isinstance(date_val, datetime):
                return date_val
            elif hasattr(date_val, 'year') and hasattr(date_val, 'month') and hasattr(date_val, 'day'):
                # Convert date to datetime
                return datetime(date_val.year, date_val.month, date_val.day)
            else:
                logger.warning(f"Invalid date format for post {post.get('title', 'Unknown')}, using epoch")
                return datetime(1970, 1, 1)  # Default for invalid dates

        self.posts.sort(key=get_sort_date, reverse=True)
        logger.debug(f"Sorted {len(self.posts)} posts by date")
        
    def _collect_posts(self) -> None:
        """Collect all blog posts."""
        for file_path in Path(self.blog_content_dir).glob('**/*.md'):
            # Skip files in _drafts directory unless include_drafts is enabled
            if '_drafts' in str(file_path) and not self.config.get('blog', 'include_drafts', default=False):
                continue
                
            try:
                post = self._parse_post(file_path)
                if post:
                    self.posts.append(post)
                    logger.debug(f"Collected post: {post['title']} from {file_path}")
            except Exception as e:
                logger.error(f"Error parsing blog post {file_path}: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()
                
    def _parse_post(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a blog post file.
        
        Args:
            file_path: Path to the blog post file.
            
        Returns:
            Dictionary containing post data, or None if post should be skipped.
        """
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Process Markdown and extract front matter
        front_matter, html_content = self.template_processor.process_markdown(content)
        
        # Skip draft posts unless include_drafts is enabled
        if front_matter.get('draft', False) and not self.config.get('blog', 'include_drafts', default=False):
            logger.debug(f"Skipping draft post: {file_path}")
            return None
            
        # Process date
        date_str = front_matter.get('date', front_matter.get('date_posted', None))
        if not date_str:
            # Try to extract date from filename (YYYY-MM-DD-title.md)
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})-', file_path.stem)
            if date_match:
                date_str = date_match.group(1)
            else:
                # Use file modification time as fallback
                date_str = datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d')
                
        try:
            if isinstance(date_str, str):
                date = datetime.strptime(date_str, '%Y-%m-%d')
            elif isinstance(date_str, datetime):
                date = date_str
            elif hasattr(date_str, 'year') and hasattr(date_str, 'month') and hasattr(date_str, 'day'):
                # If it's a date object, convert to datetime
                date = datetime(date_str.year, date_str.month, date_str.day)
            else:
                date = datetime.now()
        except (ValueError, TypeError):
            logger.warning(f"Invalid date format in {file_path}, using current date")
            date = datetime.now()
            
        # Process slug
        slug = front_matter.get('slug', front_matter.get('page_url', None))
        if not slug:
            # Generate slug from title or filename
            title = front_matter.get('title', file_path.stem)
            slug = self._slugify(title)
            
        # Build URL based on pattern
        url_pattern = self.config.get('blog', 'url_pattern', default='{year}/{month}/{day}/{slug}')
        if not url_pattern:
            url_pattern = '{year}/{month}/{day}/{slug}'  # Set a default if None
            
        url = url_pattern.format(
            year=date.year,
            month=f"{date.month:02d}",
            day=f"{date.day:02d}",
            slug=slug
        )
        
        # Format URL according to URL style configuration
        blog_dir = self.config.get('blog', 'directory', default='blog')
        full_url = '/' + os.path.join(blog_dir, url).replace('\\', '/')
        
        # Apply URL style formatting if available
        if hasattr(self.config, 'format_url'):
            full_url = self.config.format_url(full_url)
        
        # Generate excerpt
        excerpt = front_matter.get('excerpt', front_matter.get('description', None))
        if not excerpt:
            # Generate excerpt from content
            excerpt_length = self.config.get('blog', 'excerpt_length', default=200)
            excerpt = self._generate_excerpt(html_content, excerpt_length)
            
        # Process taxonomies - convert all tags and categories to strings
        tags = [str(tag) for tag in self._parse_taxonomy_list(front_matter.get('tags', []))]
        categories = [str(cat) for cat in self._parse_taxonomy_list(front_matter.get('categories', []))]
        
        # Construct post data
        post_data = {
            'title': front_matter.get('title', 'Untitled'),
            'date': date,
            'date_str': date.strftime('%Y-%m-%d'),
            'date_formatted': date.strftime('%B %d, %Y'),
            'modified': front_matter.get('modified', front_matter.get('date_edited', date)),
            'author': front_matter.get('author', self.config.get('site', 'author', default='Anonymous')),
            'slug': slug,
            'url': url,
            'full_url': full_url,
            'content': html_content,
            'excerpt': excerpt,
            'tags': tags,
            'categories': categories,
            'featured': front_matter.get('featured', False),
            'template': front_matter.get('template', self.config.get('blog', 'template', default='blog_post.html')),
            'cover_img': front_matter.get('cover_img', front_matter.get('cover_image', None)),
            'source_path': str(file_path),
            'metadata': front_matter,
        }
        
        return post_data
        
    def _set_navigation_links(self) -> None:
        """Set next/prev navigation links for posts."""
        for i, post in enumerate(self.posts):
            # Previous post (newer)
            if i > 0:
                post['prev_post'] = {
                    'title': self.posts[i-1]['title'],
                    'url': self.posts[i-1]['full_url'],
                }
            else:
                post['prev_post'] = None
                
            # Next post (older)
            if i < len(self.posts) - 1:
                post['next_post'] = {
                    'title': self.posts[i+1]['title'],
                    'url': self.posts[i+1]['full_url'],
                }
            else:
                post['next_post'] = None
                
    def _build_taxonomies(self) -> None:
        """Build taxonomy collections from posts."""
        # Reset taxonomies
        self.taxonomies = {
            'tags': {},
            'categories': {},
        }
        
        # Collect taxonomies from posts
        for post in self.posts:
            # Process tags
            for tag in post.get('tags', []):
                tag_name = str(tag)  # Ensure the tag is a string
                if tag_name not in self.taxonomies['tags']:
                    self.taxonomies['tags'][tag_name] = {
                        'name': tag_name,
                        'slug': self._slugify(tag_name),
                        'posts': [],
                    }
                self.taxonomies['tags'][tag_name]['posts'].append(post)
                
            # Process categories
            for category in post.get('categories', []):
                category_name = str(category)  # Ensure the category is a string
                if category_name not in self.taxonomies['categories']:
                    self.taxonomies['categories'][category_name] = {
                        'name': category_name,
                        'slug': self._slugify(category_name),
                        'posts': [],
                    }
                self.taxonomies['categories'][category_name]['posts'].append(post)
                
        # Convert taxonomies to regular dictionaries to ensure they're serializable
        serializable_tags = {}
        for tag_name, tag_data in self.taxonomies['tags'].items():
            serializable_tags[str(tag_name)] = {
                'name': tag_data['name'],
                'slug': tag_data['slug'],
                'posts': tag_data['posts']
            }
        
        serializable_categories = {}
        for cat_name, cat_data in self.taxonomies['categories'].items():
            serializable_categories[str(cat_name)] = {
                'name': cat_data['name'],
                'slug': cat_data['slug'],
                'posts': cat_data['posts']
            }
        
        # Replace with serializable versions
        self.taxonomies['tags'] = serializable_tags
        self.taxonomies['categories'] = serializable_categories
        
        # Save taxonomy data to global variables
        self.variable_manager.set('tags', self.taxonomies['tags'], 'global')
        self.variable_manager.set('categories', self.taxonomies['categories'], 'global')
        
        logger.debug(f"Built taxonomy collections: {len(self.taxonomies['tags'])} tags, {len(self.taxonomies['categories'])} categories")
    def _get_output_path(self, rel_path: str, is_index: bool = False) -> str:
        """Get the output file path based on URL style.
        
        Args:
            rel_path: Relative path from the output directory
            is_index: Whether this is an index page
            
        Returns:
            Full output file path
        """
        if self.url_style == 'directory':
            # For directory style, use path/to/file/index.html
            if is_index:
                output_path = os.path.join(self.paths['output'], rel_path, 'index.html')
            else:
                output_path = os.path.join(self.paths['output'], rel_path, 'index.html')
        elif self.url_style == 'html':
            # For HTML style, use path/to/file.html
            if is_index:
                output_path = os.path.join(self.paths['output'], f"{rel_path}.html")
            else:
                output_path = os.path.join(self.paths['output'], f"{rel_path}.html")
        else:  # 'clean' style - same as directory for file system
            # For clean URLs, use path/to/file/index.html
            if is_index:
                output_path = os.path.join(self.paths['output'], rel_path, 'index.html')
            else:
                output_path = os.path.join(self.paths['output'], rel_path, 'index.html')
                
        return output_path

    def _render_posts(self) -> None:
        """Render individual blog posts."""
        for post in self.posts:
            try:
                # Set page variables
                self.variable_manager.set_page_variables(post)
                
                # Get all variables
                variables = {
                    'global': self.variable_manager.variables.get('global', {}),
                    'site': self.variable_manager.variables.get('site', {}),
                    'page': post
                }
                
                # Add all global variables to site level for compatibility
                for key, value in variables['global'].items():
                    if key not in variables['site']:
                        variables['site'][key] = value
                
                # Make sure 'images' configuration is available
                if hasattr(self.config, 'config') and 'images' in self.config.config:
                    variables['site']['images'] = self.config.config['images']
                
                # Get template
                template_name = post.get('template', self.config.get('blog', 'template', default='blog_post.html'))
                
                # Render post
                _, rendered_content = self.template_processor.process_page(
                    post['content'],
                    False,  # Already processed Markdown
                    post['source_path'],
                    variables
                )
                
                # Clean the post URL for consistency
                post_url = post['url'].rstrip('/')
                blog_dir = self.config.get('blog', 'directory', default='blog')
                rel_path = os.path.join(blog_dir, post_url)
                                
                # Determine output path based on URL style
                output_path = self._get_output_path(rel_path)
                
                logger.debug(f"Output path for blog post: {output_path}")
                
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Write output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                    
                logger.debug(f"Rendered blog post: {post['title']} -> {output_path}")
                
            except Exception as e:
                logger.error(f"Error rendering blog post {post['title']}: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()

    def _generate_index_pages(self) -> None:
        """Generate blog index pages with pagination."""
        # Determine pagination
        posts_per_page = self.config.get('blog', 'posts_per_page', default=10)
        total_pages = math.ceil(len(self.posts) / posts_per_page)
        
        # Get base blog URL and directory
        blog_dir = self.config.get('blog', 'directory', default='blog')
        blog_url = f"/{blog_dir}"
        blog_url = blog_url.rstrip('/')  # Ensure no trailing slash for consistency
        
        # Generate each page
        for page_num in range(1, total_pages + 1):
            # Calculate slice for this page
            start = (page_num - 1) * posts_per_page
            end = start + posts_per_page
            page_posts = self.posts[start:end]
            
            # Format pagination URLs
            if page_num > 1:
                # Pagination URL for current page
                pagination_url = f"{blog_url}/page/{page_num}"
                if hasattr(self.config, 'format_url'):
                    pagination_url = self.config.format_url(pagination_url)
                    
                # Previous page URL
                if page_num > 2:
                    prev_url = self.config.format_url(f"{blog_url}/page/{page_num - 1}") if hasattr(self.config, 'format_url') else f"{blog_url}/page/{page_num - 1}"
                else:
                    # First page is at the blog root
                    prev_url = self.config.format_url(blog_url) if hasattr(self.config, 'format_url') else blog_url
            else:
                pagination_url = blog_url
                if hasattr(self.config, 'format_url'):
                    pagination_url = self.config.format_url(pagination_url)
                prev_url = None
            
            # Next page URL
            if page_num < total_pages:
                next_url = self.config.format_url(f"{blog_url}/page/{page_num + 1}") if hasattr(self.config, 'format_url') else f"{blog_url}/page/{page_num + 1}"
            else:
                next_url = None
            
            # Prepare pagination data
            pagination = {
                'current': page_num,
                'total': total_pages,
                'has_prev': page_num > 1,
                'has_next': page_num < total_pages,
                'prev_url': prev_url,
                'next_url': next_url,
            }
            
            # Prepare template variables
            page_data = {
                'title': f"Blog - Page {page_num}" if page_num > 1 else "Blog",
                'description': f"Blog posts - Page {page_num} of {total_pages}",
                'posts': page_posts,
                'pagination': pagination,
                'url': pagination_url,
            }
            
            # Set page variables
            self.variable_manager.set_page_variables(page_data)
            
            # Add battery and other global variables to the page scope
            for key, value in self.variable_manager.variables.get('global', {}).items():
                if key not in page_data:
                    page_data[key] = value
            
            # Get all variables with proper structure
            variables = {
                'global': self.variable_manager.variables.get('global', {}),
                'site': self.variable_manager.variables.get('site', {}),
                'page': page_data
            }
            
            # Also add global variables to site scope
            for key, value in variables['global'].items():
                if key not in variables['site']:
                    variables['site'][key] = value
            
            # Make sure 'images' configuration is available
            if hasattr(self.config, 'config') and 'images' in self.config.config:
                variables['site']['images'] = self.config.config['images']
            
            # Get template
            template_name = self.config.get('blog', 'list_template', default='blog_list.html')
            logger.debug(f"Using template {template_name} for blog index page {page_num}")
            
            # Create dummy content for template processor
            # We're using HTML content here since we want the template processor
            # to treat this as non-Markdown content that's already been processed
            dummy_content = f"<h1>{page_data['title']}</h1><p>{page_data['description']}</p>"
            
            # Render page
            _, rendered_content = self.template_processor.process_page(
                dummy_content,
                False,
                "blog_index",
                variables
            )
            
            # Determine output path based on page number and URL style
            if page_num == 1:
                # First page
                rel_path = blog_dir
            else:
                # Pagination pages
                rel_path = os.path.join(blog_dir, 'page', str(page_num))
            
            output_path = self._get_output_path(rel_path, is_index=(page_num == 1))
                    
            logger.debug(f"Output path for blog index page {page_num}: {output_path}")
                    
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
            # Write output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
                
            logger.debug(f"Generated blog index page {page_num}/{total_pages} -> {output_path}")
    
    def _generate_taxonomy_pages(self) -> None:
        """Generate taxonomy (tags, categories) pages."""
        # Process tags
        if self.config.get('blog', 'taxonomies', default={}).get('tags', {}).get('enabled', True):
            self._generate_taxonomy_type_pages('tags')
                
        # Process categories
        if self.config.get('blog', 'taxonomies', default={}).get('categories', {}).get('enabled', True):
            self._generate_taxonomy_type_pages('categories')
            
    def _generate_taxonomy_type_pages(self, taxonomy_type: str) -> None:
        """Generate pages for a specific taxonomy type (tags or categories)."""
        try:
            # Get taxonomy configuration
            taxonomy_config = self.config.get('blog', 'taxonomies', default={}).get(taxonomy_type, {})
            singular = taxonomy_type[:-1]  # Remove 's' to get singular form
            
            # Skip if no taxonomies of this type
            if not self.taxonomies[taxonomy_type]:
                logger.info(f"No {taxonomy_type} found, skipping")
                return
                
            # Ensure taxonomies are in the correct format (string keys, dict values)
            safe_taxonomies = {}
            for key, value in self.taxonomies[taxonomy_type].items():
                str_key = str(key)  # Force keys to be strings
                if isinstance(value, dict):
                    safe_taxonomies[str_key] = value
            
            # Use the safe version
            for term_name, term_data in safe_taxonomies.items():
                try:
                    # Ensure term_name is a string and not a dict
                    if isinstance(term_name, dict):
                        logger.warning(f"Found dict as term_name, converting to string: {term_name}")
                        term_name = str(term_name)
                    
                    # Prepare template variables
                    page_data = {
                        'title': f"{term_name} ({singular.capitalize()})",
                        'description': f"Posts with {singular} {term_name}",
                        singular: term_name,  # Use the string, not f-string formatting
                        'posts': term_data['posts'],
                        'url': f"/{self.config.get('blog', 'directory', default='blog')}/{taxonomy_type}/{term_data['slug']}",
                    }
                    
                    # Format URL according to style
                    if hasattr(self.config, 'format_url'):
                        page_data['url'] = self.config.format_url(page_data['url'])
                    
                    # Set page variables
                    self.variable_manager.set_page_variables(page_data)
                    
                    # Get all variables with proper structure
                    variables = {
                        'global': self.variable_manager.variables.get('global', {}),
                        'site': self.variable_manager.variables.get('site', {}),
                        'page': page_data
                    }
                    
                    # Add global variables to site level for compatibility
                    for key, value in variables['global'].items():
                        if key not in variables['site']:
                            variables['site'][key] = value
                    
                    # Make sure 'images' is available if defined in config
                    if hasattr(self.config, 'config') and 'images' in self.config.config:
                        variables['site']['images'] = self.config.config['images']
                    
                    # Get template
                    template_name = taxonomy_config.get('template', f"{singular}.html")
                    
                    # Dummy content for template processor
                    dummy_content = f"<!-- {singular.capitalize()} Page: {term_name} -->"
                    
                    # Render page - use correct source path identifier
                    source_path = f"{singular}_{self._slugify(term_name)}"
                    _, rendered_content = self.template_processor.process_page(
                        dummy_content,
                        False,
                        source_path,
                        variables
                    )
                    
                    # Determine relative path
                    blog_dir = self.config.get('blog', 'directory', default='blog')
                    slug = term_data['slug']
                    rel_path = os.path.join(blog_dir, taxonomy_type, slug)
                    
                    # Get output path based on URL style
                    output_path = self._get_output_path(rel_path)
                        
                    # Ensure output directory exists
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Write output file
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(rendered_content)
                        
                    logger.debug(f"Generated {singular} page: {term_name} -> {output_path}")
                except Exception as e:
                    logger.error(f"Error generating page for {taxonomy_type} '{term_name}': {e}")
                    if logger.level <= logging.DEBUG:
                        import traceback
                        traceback.print_exc()
            
            # Generate taxonomy index page
            try:
                page_data = {
                    'title': taxonomy_type.capitalize(),
                    'description': f"All {taxonomy_type}",
                    taxonomy_type: safe_taxonomies,  # Use the safe dictionary
                    'url': f"/{self.config.get('blog', 'directory', default='blog')}/{taxonomy_type}",
                }
                
                # Format URL according to style
                if hasattr(self.config, 'format_url'):
                    page_data['url'] = self.config.format_url(page_data['url'])
                
                # Set page variables
                self.variable_manager.set_page_variables(page_data)
                
                # Get all variables with proper structure
                variables = {
                    'global': self.variable_manager.variables.get('global', {}),
                    'site': self.variable_manager.variables.get('site', {}),
                    'page': page_data
                }
                
                # Add global variables to site level for compatibility
                for key, value in variables['global'].items():
                    if key not in variables['site']:
                        variables['site'][key] = value
                
                # Make sure 'images' is available if defined in config
                if hasattr(self.config, 'config') and 'images' in self.config.config:
                    variables['site']['images'] = self.config.config['images']
                
                # Get template
                template_name = taxonomy_config.get('list_template', f"{taxonomy_type}.html")
                
                # Fake content for template processor
                dummy_content = f"<!-- {taxonomy_type.capitalize()} Index Page -->"
                
                # Render page - use correct source path identifier
                source_path = f"{taxonomy_type}_index"
                _, rendered_content = self.template_processor.process_page(
                    dummy_content,
                    False,
                    source_path,
                    variables
                )
                
                # Determine relative path
                blog_dir = self.config.get('blog', 'directory', default='blog')
                rel_path = os.path.join(blog_dir, taxonomy_type)
                
                # Get output path based on URL style
                output_path = self._get_output_path(rel_path)
                    
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Write output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                    
                logger.debug(f"Generated {taxonomy_type} index page -> {output_path}")
            except Exception as e:
                logger.error(f"Error generating {taxonomy_type} index page: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()
                
        except Exception as e:
            logger.error(f"Error generating {taxonomy_type} pages: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()

    def _generate_rss_feed(self) -> None:
        """Generate RSS feed for blog posts."""
        try:
            # Skip if no posts
            if not self.posts:
                return
                
            # Get site information
            site_title = self.config.get('site', 'title', default='My Sonne Site')
            site_description = self.config.get('site', 'description', default='')
            site_url = self.config.get('site', 'base_url', default='')
            
            # Build RSS feed
            rss_items = []
            
            # Include only the most recent posts (max 20)
            for post in self.posts[:20]:
                post_url = site_url + post['full_url']
                
                # Format post date with timezone if available
                try:
                    pub_date = post['date'].strftime('%a, %d %b %Y %H:%M:%S +0000')
                except:
                    pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
                
                rss_items.append(f"""
                <item>
                    <title>{post['title']}</title>
                    <link>{post_url}</link>
                    <guid>{post_url}</guid>
                    <pubDate>{pub_date}</pubDate>
                    <description><![CDATA[{post['excerpt']}]]></description>
                </item>
                """)
                
            # Build complete RSS feed
            rss_feed = f"""<?xml version="1.0" encoding="UTF-8" ?>
            <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
            <channel>
                <title>{site_title}</title>
                <link>{site_url}</link>
                <description>{site_description}</description>
                <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')}</lastBuildDate>
                <atom:link href="{site_url}/feed.xml" rel="self" type="application/rss+xml" />
                {"".join(rss_items)}
            </channel>
            </rss>
            """
            
            # Write RSS feed to file
            output_path = os.path.join(self.paths['output'], 'feed.xml')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rss_feed)
                
            logger.debug(f"Generated RSS feed -> {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating RSS feed: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
            
    def _slugify(self, text: str) -> str:
        """Convert text to slug format.
        
        Args:
            text: Text to convert.
            
        Returns:
            Slug formatted string.
        """
        # First ensure text is a string
        text = str(text)
        # Remove special characters
        text = re.sub(r'[^\w\s-]', '', text.lower())
        # Replace spaces with hyphens
        text = re.sub(r'[\s]+', '-', text)
        # Remove multiple hyphens
        text = re.sub(r'[-]+', '-', text)
        # Strip leading/trailing hyphens
        text = text.strip('-')
        return text
        
    def _generate_excerpt(self, html_content: str, length: int = 200) -> str:
        """Generate an excerpt from HTML content.
        
        Args:
            html_content: HTML content to extract excerpt from.
            length: Maximum length of excerpt in characters.
            
        Returns:
            Plain text excerpt.
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        # Replace multiple whitespace with single space
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate to length
        if len(text) > length:
            text = text[:length] + '...'
            
        return text
        
    def _parse_taxonomy_list(self, taxonomy_value: Any) -> List[str]:
        """Parse taxonomy value to a list of strings.
        
        Args:
            taxonomy_value: Taxonomy value from front matter.
            
        Returns:
            List of taxonomy terms.
        """
        if not taxonomy_value:
            return []
            
        if isinstance(taxonomy_value, str):
            # Split comma or space-separated string
            return [term.strip() for term in re.split(r'[,\s]+', taxonomy_value) if term.strip()]
            
        if isinstance(taxonomy_value, list):
            return [str(term).strip() for term in taxonomy_value if str(term).strip()]
            
        # Single value (not a list or string)
        return [str(taxonomy_value).strip()]