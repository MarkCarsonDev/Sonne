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
            
        blog_dir = self.config.get('blog', 'directory', 'blog')
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
        self.posts.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Set navigation links (next/prev)
        self._set_navigation_links()
        
        # Build taxonomy collections
        self._build_taxonomies()
        
        # Save posts to global variables
        self.variable_manager.set('all_blog_posts', self.posts, 'global')
        
        # Render individual posts
        self._render_posts()
        
        # Generate index pages
        self._generate_index_pages()
        
        # Generate taxonomy pages
        self._generate_taxonomy_pages()
        
        # Generate RSS feed
        self._generate_rss_feed()
        
        logger.info(f"Processed {len(self.posts)} blog posts")
        
    def _collect_posts(self) -> None:
        """Collect all blog posts."""
        for file_path in Path(self.blog_content_dir).glob('**/*.md'):
            # Skip files in _drafts directory unless include_drafts is enabled
            if '_drafts' in str(file_path) and not self.config.get('blog', 'include_drafts', False):
                continue
                
            try:
                post = self._parse_post(file_path)
                if post:
                    self.posts.append(post)
            except Exception as e:
                logger.error(f"Error parsing blog post {file_path}: {e}")
                
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
        if front_matter.get('draft', False) and not self.config.get('blog', 'include_drafts', False):
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
            else:
                date = date_str
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
        url_pattern = self.config.get('blog', 'url_pattern', '{year}/{month}/{day}/{slug}')
        url = url_pattern.format(
            year=date.year,
            month=f"{date.month:02d}",
            day=f"{date.day:02d}",
            slug=slug
        )
        
        # Generate excerpt
        excerpt = front_matter.get('excerpt', front_matter.get('description', None))
        if not excerpt:
            # Generate excerpt from content
            excerpt_length = self.config.get('blog', 'excerpt_length', 200)
            excerpt = self._generate_excerpt(html_content, excerpt_length)
            
        # Process taxonomies
        tags = self._parse_taxonomy_list(front_matter.get('tags', []))
        categories = self._parse_taxonomy_list(front_matter.get('categories', []))
        
        # Construct post data
        post_data = {
            'title': front_matter.get('title', 'Untitled'),
            'date': date,
            'date_str': date.strftime('%Y-%m-%d'),
            'date_formatted': date.strftime('%B %d, %Y'),
            'modified': front_matter.get('modified', front_matter.get('date_edited', date)),
            'author': front_matter.get('author', self.config.get('site', 'author', 'Anonymous')),
            'slug': slug,
            'url': url,
            'full_url': '/' + os.path.join(self.config.get('blog', 'directory', 'blog'), url).replace('\\', '/'),
            'content': html_content,
            'excerpt': excerpt,
            'tags': tags,
            'categories': categories,
            'featured': front_matter.get('featured', False),
            'template': front_matter.get('template', self.config.get('blog', 'template', 'blog_post.html')),
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
                if tag not in self.taxonomies['tags']:
                    self.taxonomies['tags'][tag] = {
                        'name': tag,
                        'slug': self._slugify(tag),
                        'posts': [],
                    }
                self.taxonomies['tags'][tag]['posts'].append(post)
                
            # Process categories
            for category in post.get('categories', []):
                if category not in self.taxonomies['categories']:
                    self.taxonomies['categories'][category] = {
                        'name': category,
                        'slug': self._slugify(category),
                        'posts': [],
                    }
                self.taxonomies['categories'][category]['posts'].append(post)
                
        # Save taxonomy data to global variables
        self.variable_manager.set('tags', self.taxonomies['tags'], 'global')
        self.variable_manager.set('categories', self.taxonomies['categories'], 'global')
        
    def _render_posts(self) -> None:
        """Render individual blog posts."""
        for post in self.posts:
            try:
                # Set page variables
                self.variable_manager.set_page_variables(post)
                
                # Get all variables
                variables = self.variable_manager.get_all()
                
                # Get template
                template_name = post.get('template')
                
                # Render post
                _, rendered_content = self.template_processor.process_page(
                    post['content'],
                    False,  # Already processed Markdown
                    post['source_path'],
                    variables
                )
                
                # Determine output path
                output_path = os.path.join(self.blog_output_dir, post['url'])
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Write output file
                with open(f"{output_path}.html", 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                    
                logger.debug(f"Rendered blog post: {post['title']} -> {output_path}.html")
                
            except Exception as e:
                logger.error(f"Error rendering blog post {post['title']}: {e}")
                
    def _generate_index_pages(self) -> None:
        """Generate blog index pages with pagination."""
        try:
            # Determine pagination
            posts_per_page = self.config.get('blog', 'posts_per_page', 10)
            total_pages = math.ceil(len(self.posts) / posts_per_page)
            
            # Generate each page
            for page_num in range(1, total_pages + 1):
                # Calculate slice for this page
                start = (page_num - 1) * posts_per_page
                end = start + posts_per_page
                page_posts = self.posts[start:end]
                
                # Prepare pagination data
                pagination = {
                    'current': page_num,
                    'total': total_pages,
                    'has_prev': page_num > 1,
                    'has_next': page_num < total_pages,
                    'prev_url': f"/blog/page/{page_num - 1}" if page_num > 1 else None,
                    'next_url': f"/blog/page/{page_num + 1}" if page_num < total_pages else None,
                }
                
                # Prepare template variables
                page_data = {
                    'title': f"Blog - Page {page_num}" if page_num > 1 else "Blog",
                    'posts': page_posts,
                    'pagination': pagination,
                }
                
                # Set page variables
                self.variable_manager.set_page_variables(page_data)
                
                # Get all variables
                variables = self.variable_manager.get_all()
                
                # Get template
                template_name = self.config.get('blog', 'list_template', 'blog_list.html')
                
                # Fake content for template processor
                content = f"<!-- Blog Index Page {page_num} -->"
                
                # Render page
                _, rendered_content = self.template_processor.process_page(
                    content,
                    False,
                    "blog_index",
                    variables
                )
                
                # Determine output path
                if page_num == 1:
                    # First page goes to index.html
                    output_path = os.path.join(self.blog_output_dir, 'index.html')
                else:
                    # Other pages go to page/N/index.html
                    output_path = os.path.join(self.blog_output_dir, 'page', str(page_num), 'index.html')
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                # Write output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                    
                logger.debug(f"Generated blog index page {page_num}/{total_pages} -> {output_path}")
                
        except Exception as e:
            logger.error(f"Error generating blog index pages: {e}")
            
    def _generate_taxonomy_pages(self) -> None:
        """Generate taxonomy (tags, categories) pages."""
        # Process tags
        if self.config.get('blog', 'taxonomies', {}).get('tags', {}).get('enabled', True):
            self._generate_taxonomy_type_pages('tags')
            
        # Process categories
        if self.config.get('blog', 'taxonomies', {}).get('categories', {}).get('enabled', True):
            self._generate_taxonomy_type_pages('categories')
            
    def _generate_taxonomy_type_pages(self, taxonomy_type: str) -> None:
        """Generate pages for a specific taxonomy type (tags or categories).
        
        Args:
            taxonomy_type: Taxonomy type ('tags' or 'categories').
        """
        try:
            # Get taxonomy configuration
            taxonomy_config = self.config.get('blog', 'taxonomies', {}).get(taxonomy_type, {})
            singular = taxonomy_type[:-1]  # Remove 's' to get singular form
            
            # Skip if no taxonomies of this type
            if not self.taxonomies[taxonomy_type]:
                return
                
            # Generate individual taxonomy pages
            for term_name, term_data in self.taxonomies[taxonomy_type].items():
                # Prepare template variables
                page_data = {
                    'title': f"{term_name} ({singular})",
                    f"{singular}": term_name,
                    'posts': term_data['posts'],
                }
                
                # Set page variables
                self.variable_manager.set_page_variables(page_data)
                
                # Get all variables
                variables = self.variable_manager.get_all()
                
                # Get template
                template_name = taxonomy_config.get('template', f"{singular}.html")
                
                # Fake content for template processor
                content = f"<!-- {singular.capitalize()} Page: {term_name} -->"
                
                # Render page
                _, rendered_content = self.template_processor.process_page(
                    content,
                    False,
                    f"{taxonomy_type}_{self._slugify(term_name)}",
                    variables
                )
                
                # Determine output path
                output_dir = os.path.join(self.blog_output_dir, taxonomy_type, term_data['slug'])
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, 'index.html')
                
                # Write output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                    
                logger.debug(f"Generated {singular} page: {term_name} -> {output_path}")
                
            # Generate taxonomy index page
            page_data = {
                'title': taxonomy_type.capitalize(),
                taxonomy_type: self.taxonomies[taxonomy_type],
            }
            
            # Set page variables
            self.variable_manager.set_page_variables(page_data)
            
            # Get all variables
            variables = self.variable_manager.get_all()
            
            # Get template
            template_name = taxonomy_config.get('list_template', f"{taxonomy_type}.html")
            
            # Fake content for template processor
            content = f"<!-- {taxonomy_type.capitalize()} Index Page -->"
            
            # Render page
            _, rendered_content = self.template_processor.process_page(
                content,
                False,
                f"{taxonomy_type}_index",
                variables
            )
            
            # Determine output path
            output_dir = os.path.join(self.blog_output_dir, taxonomy_type)
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'index.html')
            
            # Write output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
                
            logger.debug(f"Generated {taxonomy_type} index page -> {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating {taxonomy_type} pages: {e}")
            
    def _generate_rss_feed(self) -> None:
        """Generate RSS feed for blog posts."""
        try:
            # Skip if no posts
            if not self.posts:
                return
                
            # Get site information
            site_title = self.config.get('site', 'title', 'My Sonne Site')
            site_description = self.config.get('site', 'description', '')
            site_url = self.config.get('site', 'base_url', '')
            
            # Build RSS feed
            rss_items = []
            
            # Include only the most recent posts (max 20)
            for post in self.posts[:20]:
                post_url = site_url + post['full_url']
                
                rss_items.append(f"""
                <item>
                    <title>{post['title']}</title>
                    <link>{post_url}</link>
                    <guid>{post_url}</guid>
                    <pubDate>{post['date'].strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>
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
                <lastBuildDate>{datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')}</lastBuildDate>
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
            
    def _slugify(self, text: str) -> str:
        """Convert text to slug format.
        
        Args:
            text: Text to convert.
            
        Returns:
            Slug formatted string.
        """
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