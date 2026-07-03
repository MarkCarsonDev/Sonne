"""
Blog post processing for Sonne.
Handles parsing, rendering, and generating blog posts and related pages.
"""

import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List
import math

from sonne.utils.path_utils import sanitize_filename, validate_path_within_root

logger = logging.getLogger('sonne')

class BlogProcessor:
    """Processes blog posts and generates blog-related pages."""
    
    def __init__(self, config, paths: Dict[str, str], template_processor, variable_manager, image_processor=None):
        """Initialize blog processor.

        Args:
            config: Site configuration.
            paths: Dictionary of normalized paths.
            template_processor: Template processor instance.
            variable_manager: Variable manager instance.
            image_processor: ImageProcessor instance for shared dithering pipeline.
        """
        self.config = config
        self.paths = paths
        self.template_processor = template_processor
        self.variable_manager = variable_manager
        self.image_processor = image_processor
        self.stats = None  # Injected by SiteGenerator
        
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

    def collect_post_metadata(self) -> None:
        """Collect blog post metadata without rendering.

        This method collects and processes blog post metadata early in the build
        process so that data scripts can reference blog posts by slug or tag.
        """
        logger.info("Collecting blog post metadata...")

        # Skip if blog directory doesn't exist
        if not os.path.exists(self.blog_content_dir):
            logger.debug(f"Blog directory does not exist: {self.blog_content_dir}")
            return

        # Collect all blog posts
        self._collect_posts()

        # Skip if no posts found
        if not self.posts:
            logger.debug("No blog posts found")
            return

        # Sort posts by date (newest first)
        self._sort_posts()

        # Build taxonomy collections
        self._build_taxonomies()

        # Save posts to global variables (without rendering)
        self.variable_manager.set('all_blog_posts', self.posts, 'global')
        self.variable_manager.set('all_blog_posts', self.posts, 'site')

        logger.info(f"Collected metadata for {len(self.posts)} blog posts")

    def process_all_posts(self) -> None:
        """Process all blog posts."""

        # Skip if blog directory doesn't exist
        if not os.path.exists(self.blog_content_dir):
            logger.warning(f"Blog directory does not exist: {self.blog_content_dir}")
            return

        # If metadata hasn't been collected yet, collect it now
        if not self.posts:
            # Collect all blog posts
            self._collect_posts()

            # Skip if no posts found
            if not self.posts:
                logger.info("No blog posts found")
                return

            # Sort posts by date (newest first)
            self._sort_posts()

            # Build taxonomy collections
            self._build_taxonomies()

            # Save posts to global variables
            self.variable_manager.set('all_blog_posts', self.posts, 'global')
            self.variable_manager.set('all_blog_posts', self.posts, 'site')

        # Set navigation links (next/prev)
        self._set_navigation_links()

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
        
        try:
            # Generate date archive pages (/blog/YYYY/ and /blog/YYYY/MM/)
            self._generate_date_archives()
        except Exception as e:
            logger.error(f"Error generating date archives: {e}")
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
            raw_content = f.read()

        # Process Markdown and extract front matter
        front_matter, html_content = self.template_processor.process_markdown(raw_content)
        
        # Skip draft posts unless include_drafts is enabled
        if front_matter.get('draft', False) and not self.config.get('blog', 'include_drafts', default=False):
            logger.debug(f"Skipping draft post: {file_path}")
            return None
            
        # Helper: file creation time (st_birthtime on macOS/BSD, st_mtime fallback on Linux)
        _stat = file_path.stat()
        _file_ctime = datetime.fromtimestamp(getattr(_stat, 'st_birthtime', _stat.st_mtime))
        _file_mtime = datetime.fromtimestamp(_stat.st_mtime)

        def _parse_date(value, fallback):
            """Parse a date value; 'auto' returns fallback datetime directly."""
            if isinstance(value, str) and value.strip().lower() == 'auto':
                return fallback
            if isinstance(value, str):
                try:
                    parts = value.strip().split('-')
                    if len(parts) == 3:
                        value = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                    return datetime.strptime(value, '%Y-%m-%d')
                except (ValueError, TypeError):
                    return fallback
            if isinstance(value, datetime):
                return value
            if hasattr(value, 'year'):
                return datetime(value.year, value.month, value.day)
            return fallback

        # Process date_posted — 'auto' or missing → file creation time; try filename pattern first
        raw_date = front_matter.get('date', front_matter.get('date_posted', None))
        if raw_date is None:
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})-', file_path.stem)
            raw_date = date_match.group(1) if date_match else 'auto'
        date = _parse_date(raw_date, _file_ctime)
            
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
        
        # Resolve modified/date_edited — missing or 'auto' → file mtime
        raw_modified = front_matter.get('modified', front_matter.get('date_edited', 'auto'))
        modified_date = _parse_date(raw_modified, _file_mtime)

        # Construct post data
        post_data = {
            'title': front_matter.get('title', 'Untitled'),
            'date': date,
            'date_str': date.strftime('%Y-%m-%d'),
            'date_formatted': date.strftime('%B %d, %Y'),
            'date_posted': date.strftime('%B %d, %Y'),   # matches {{ page.date_posted }} in templates
            'modified': modified_date,
            'date_edited': modified_date.strftime('%B %d, %Y'),
            'author': front_matter.get('author', self.config.get('site', 'author', default='Anonymous')),
            'slug': slug,
            'url': url,
            'full_url': full_url,
            'content': html_content,
            'raw_content': raw_content,  # Store raw markdown content for image extraction
            'excerpt': excerpt,
            'tags': tags,
            'categories': categories,
            'featured': front_matter.get('featured', False),
            'template': front_matter.get('template', self.config.get('blog', 'template', default='blog_post.html')),
            'cover_img': front_matter.get('cover_img', front_matter.get('cover_image', None)),
            'cover_crop': front_matter.get('cover_crop', None),
            'cover_rotate': front_matter.get('cover_rotate', None),
            'source_path': str(file_path),
            'metadata': front_matter,
        }
        
        return post_data
        
    def _set_navigation_links(self) -> None:
        """Set next/prev navigation links and related posts for posts."""
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

            # Related posts: prefer tag matches, fall back to adjacent posts
            post_tags = set(post.get('tags') or [])
            scored = []
            for j, other in enumerate(self.posts):
                if j == i:
                    continue
                other_tags = set(other.get('tags') or [])
                shared = len(post_tags & other_tags)
                # Give adjacency a small bonus so nearby posts appear when no tags match
                proximity = 1.0 / (abs(i - j) + 1)
                scored.append((shared + proximity * 0.1, j))
            scored.sort(key=lambda x: x[0], reverse=True)
            post['related_posts'] = [self.posts[j] for _, j in scored[:3]]
                
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

        Raises:
            ValueError: If path escapes output directory (path traversal attempt).
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

        # Security check: ensure output path is within output directory
        if not validate_path_within_root(output_path, self.paths['output']):
            error_msg = f"Path traversal detected: {rel_path} attempts to escape output directory"
            logger.error(error_msg)
            raise ValueError(error_msg)

        return output_path

    def _render_posts(self) -> None:
        """Render individual blog posts.

        Two-pass approach: process all post images first so that cover_img_dithered
        is set on every post before any template is rendered. This ensures related
        posts and other cross-references see the correct image paths regardless of
        the order posts are processed.
        """
        # Pass 1: process images for all posts so cover_img_dithered is populated
        # on every post dict before any template renders related-post strips.
        for post in self.posts:
            try:
                post_url = post['url'].rstrip('/')
                blog_dir = self.config.get('blog', 'directory', default='blog')
                rel_path = os.path.join(blog_dir, post_url)
                output_path = self._get_output_path(rel_path)
                output_dir = os.path.dirname(output_path)
                os.makedirs(output_dir, exist_ok=True)
                self._copy_post_images(post, output_dir)
            except Exception as e:
                logger.error(f"Error processing images for post {post.get('title', '?')}: {e}")

        # Pass 2: render templates now that all posts have complete metadata
        for post in self.posts:
            _t0 = time.perf_counter()
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

                post_url = post['url'].rstrip('/')
                blog_dir = self.config.get('blog', 'directory', default='blog')
                rel_path = os.path.join(blog_dir, post_url)
                output_path = self._get_output_path(rel_path)
                output_dir = os.path.dirname(output_path)

                # Render post
                _, rendered_content = self.template_processor.process_page(
                    post['content'],
                    False,  # Already processed Markdown
                    post['source_path'],
                    variables
                )

                # Write output file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)

                logger.debug(f"Rendered blog post: {post['title']} -> {output_path}")

            except Exception as e:
                logger.error(f"Error rendering blog post {post['title']}: {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()

            finally:
                if self.stats:
                    self.stats.record_post(post.get('slug', post.get('title', '?')), time.perf_counter() - _t0)

    def _copy_post_images(self, post: Dict[str, Any], output_dir: str) -> None:
        """Copy and process images referenced in a blog post.

        Copies the original image to its expected path and saves a dithered PNG
        into a 'dithered/' subdirectory alongside it. The template processor handles
        the dithered/original switching in the rendered HTML using those paths.

        Args:
            post: The blog post data.
            output_dir: The output directory for the blog post.
        """
        try:
            try:
                from PIL import Image
                PIL_AVAILABLE = True
            except ImportError:
                PIL_AVAILABLE = False
                logger.warning("PIL not available, images will be copied without processing")

            content = post.get('raw_content', post.get('content', ''))
            md_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
            html_pattern = r'<img[^>]+src=["\'](([^"\']+))["\']'

            image_refs = []
            img_transforms = {}  # img_path -> transforms dict
            for match in re.finditer(md_pattern, content):
                path_with_title = match.group(2).strip()
                # Extract path (before any quoted title)
                title_match = re.search(r'\s+"([^"]*)"', path_with_title)
                img_path = path_with_title.split()[0] if ' ' in path_with_title else path_with_title
                if title_match:
                    _, transforms = self._parse_transforms(title_match.group(1))
                    if transforms:
                        img_transforms[img_path] = transforms
                image_refs.append(img_path)
            for match in re.finditer(html_pattern, content):
                image_refs.append(match.group(1))

            dither_enabled = self.config.get('images', 'dither', default=True)
            orig_max_w = self.config.get('images', 'blog_original_max_width', default=1600)
            dith_max_w = self.config.get('images', 'blog_dithered_max_width', default=400)

            for img_ref in image_refs:
                if img_ref.startswith(('http://', 'https://', '/')):
                    continue
                if img_ref.endswith('.svg'):
                    continue

                post_source_dir = os.path.dirname(post.get('source_path', ''))
                source_img_path = os.path.normpath(os.path.join(post_source_dir, img_ref))

                if not os.path.exists(source_img_path):
                    logger.warning(f"Image not found: {source_img_path} (referenced in {post['title']})")
                    continue

                rel_img_path = img_ref.lstrip('./')
                original_path = os.path.join(output_dir, rel_img_path)
                os.makedirs(os.path.dirname(original_path), exist_ok=True)

                # Resize and save the "original" (high-res but capped)
                transforms = img_transforms.get(img_ref, {})
                original_kb = self._save_resized(source_img_path, original_path, orig_max_w, transforms)

                dithered_kb = None
                if dither_enabled and PIL_AVAILABLE:
                    img_dir = os.path.dirname(rel_img_path)
                    stem = os.path.splitext(os.path.basename(rel_img_path))[0]
                    dithered_dir = os.path.join(output_dir, img_dir, 'dithered')
                    os.makedirs(dithered_dir, exist_ok=True)
                    dithered_path = os.path.join(dithered_dir, stem + '.png')
                    dithered_kb = self._process_blog_image(source_img_path, dithered_path, dith_max_w, transforms)

                # Inject size info into the already-processed HTML.
                # process_markdown already converted <img src="foo.jpg"> into a
                # <figure> with src rewritten to the dithered path, so we can't
                # match on the original src string.  Instead parse with BS4 and
                # find the img tag by data-original-src, then also update the
                # figcaption caption-text span in place.
                if original_kb and dithered_kb:
                    pct = int(round((1 - dithered_kb / original_kb) * 100))
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(post['content'], 'html.parser')
                        # img_ref may have a leading ./ — normalise for comparison
                        norm_ref = img_ref.lstrip('./')
                        matched = False
                        for img_tag in soup.find_all('img'):
                            orig_src = img_tag.get('data-original-src', '')
                            if orig_src.lstrip('./') == norm_ref or orig_src.endswith('/' + norm_ref):
                                img_tag['data-dithered-size'] = f'{dithered_kb:.0f}K'
                                img_tag['data-original-size'] = f'{original_kb:.0f}K'
                                img_tag['data-size-reduction'] = str(pct)
                                # Update the caption span that was pre-rendered
                                # without size info
                                figure = img_tag.find_parent('figure')
                                if figure:
                                    span = figure.find('span', class_='caption-text')
                                    if span:
                                        label = span.get_text()
                                        span.string = f'{label} · {dithered_kb:.0f}K (−{pct}%)'
                                    # Also stamp the button so JS can show original size
                                    btn = figure.find('button', class_='request-original-btn')
                                    if btn:
                                        btn['data-original-size'] = f'{original_kb:.0f}K'
                                matched = True
                                break
                        if matched:
                            post['content'] = str(soup)
                        else:
                            logger.debug(f"Could not find img with data-original-src matching {norm_ref} in post HTML")
                    except Exception as bs_err:
                        logger.warning(f"BS4 size-attr injection failed for {img_ref}: {bs_err}")

            # --- Cover image processing ---
            cover_img = post.get('cover_img')
            if cover_img and not cover_img.startswith(('http://', 'https://', '/')) and not cover_img.endswith('.svg'):
                dither_cover = self.config.get('images', 'dither_cover_images', default=True)
                post_source_dir = os.path.dirname(post.get('source_path', ''))
                source_path = os.path.normpath(os.path.join(post_source_dir, cover_img))
                if os.path.exists(source_path):
                    rel_path = cover_img.lstrip('./')
                    original_path = os.path.join(output_dir, rel_path)
                    os.makedirs(os.path.dirname(original_path), exist_ok=True)

                    # Build cover transforms from front matter
                    cover_transforms = {}
                    if post.get('cover_crop'):
                        cover_transforms['crop'] = post['cover_crop']
                    if post.get('cover_rotate'):
                        cover_transforms['rotate'] = post['cover_rotate']

                    original_kb = self._save_resized(source_path, original_path, orig_max_w, cover_transforms or None)
                    dithered_kb = None
                    dithered_rel = rel_path  # fallback: use original if no dithering
                    if dither_cover and dither_enabled and PIL_AVAILABLE:
                        img_dir = os.path.dirname(rel_path)
                        stem = os.path.splitext(os.path.basename(rel_path))[0]
                        dithered_dir = os.path.join(output_dir, img_dir, 'dithered')
                        os.makedirs(dithered_dir, exist_ok=True)
                        dithered_rel = os.path.join(img_dir, 'dithered', stem + '.png')
                        dithered_path = os.path.join(output_dir, dithered_rel)
                        dithered_kb = self._process_blog_image(source_path, dithered_path, dith_max_w, cover_transforms or None)

                    post['cover_img_original'] = rel_path
                    post['cover_img_dithered'] = dithered_rel if dithered_kb else rel_path
                    post['cover_img_original_kb'] = f'{original_kb:.0f}K' if original_kb else ''
                    post['cover_img_dithered_kb'] = f'{dithered_kb:.0f}K' if dithered_kb else ''
                    if original_kb and dithered_kb:
                        pct = int(round((1 - dithered_kb / original_kb) * 100))
                        post['cover_img_reduction'] = str(pct)
                    else:
                        post['cover_img_reduction'] = ''
                else:
                    logger.warning(f"Cover image not found: {source_path} (referenced in {post.get('title', 'unknown')})")

        except Exception as e:
            logger.error(f"Error processing images for post {post.get('title', 'unknown')}: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()

    @staticmethod
    def _parse_transforms(title_str: str):
        """Parse transform directives from an image title string.

        Format: "Display title | crop=16:9 rotate=90"
        Returns: (display_title, transforms_dict)
        """
        if '|' not in title_str:
            return title_str.strip(), {}
        display, raw = title_str.split('|', 1)
        transforms = {}
        for token in raw.strip().split():
            if '=' in token:
                k, v = token.split('=', 1)
                try:
                    transforms[k.strip()] = int(v) if v.isdigit() else v.strip()
                except ValueError:
                    transforms[k.strip()] = v.strip()
        return display.strip(), transforms

    @staticmethod
    def _apply_transforms(img: 'Image.Image', transforms: dict) -> 'Image.Image':
        """Apply crop and rotate transforms to a PIL Image.

        Supported keys:
            rotate: degrees (positive = clockwise)
            crop:   aspect ratio string e.g. "16:9"
        """
        if not transforms:
            return img
        if 'rotate' in transforms:
            try:
                img = img.rotate(-float(transforms['rotate']), expand=True)
            except (ValueError, TypeError):
                logger.warning(f"Invalid rotate value: {transforms['rotate']}")
        if 'crop' in transforms:
            ratio_str = str(transforms['crop'])
            if ':' in ratio_str:
                try:
                    wr, hr = ratio_str.split(':', 1)
                    target = float(wr) / float(hr)
                    current = img.width / img.height
                    if current > target:
                        new_w = int(img.height * target)
                        left = (img.width - new_w) // 2
                        img = img.crop((left, 0, left + new_w, img.height))
                    elif current < target:
                        new_h = int(img.width / target)
                        top = (img.height - new_h) // 2
                        img = img.crop((0, top, img.width, top + new_h))
                except (ValueError, ZeroDivisionError):
                    logger.warning(f"Invalid crop ratio: {ratio_str}")
        return img

    def _resize_img(self, img: 'Image.Image', max_width: int) -> 'Image.Image':
        """Return a copy of img resized to max_width, preserving aspect ratio."""
        from PIL import Image
        if img.width > max_width:
            h = int(img.height * max_width / img.width)
            return img.resize((max_width, h), Image.LANCZOS)
        return img.copy()

    def _save_resized(self, source_path: str, output_path: str, max_width: int, transforms: dict = None) -> float:
        """Resize source image to max_width and save, preserving original format.

        Returns:
            File size in KB.
        """
        from PIL import Image, ImageOps
        try:
            with Image.open(source_path) as img:
                img = ImageOps.exif_transpose(img)
                img = img.convert('RGB') if img.mode not in ('RGB', 'RGBA', 'L') else img
                if transforms:
                    img = self._apply_transforms(img, transforms)
                resized = self._resize_img(img, max_width)
                fmt = img.format or 'JPEG'
                save_kw = {'optimize': True}
                if fmt in ('JPEG', 'JPG'):
                    save_kw['quality'] = 85
                resized.save(output_path, format=fmt, **save_kw)
            return os.path.getsize(output_path) / 1024
        except Exception as e:
            logger.error(f"Error saving resized image {source_path}: {e}")
            shutil.copy2(source_path, output_path)
            return os.path.getsize(output_path) / 1024

    def _process_blog_image(self, source_path: str, dithered_path: str, max_width: int = 400, transforms: dict = None) -> float:
        """Resize and dither a blog post image using the shared ImageProcessor pipeline.

        Args:
            source_path: Source image path.
            dithered_path: Output path for the dithered PNG (always .png).
            max_width: Resize to this width before dithering.
            transforms: Optional dict of transform directives (crop, rotate).

        Returns:
            File size in KB.
        """
        from PIL import Image, ImageOps

        try:
            with Image.open(source_path) as img:
                img = ImageOps.exif_transpose(img)
                if transforms:
                    img = self._apply_transforms(img, transforms)
                resized = self._resize_img(img, max_width)
                if self.image_processor is not None:
                    dithered = self.image_processor._apply_dither(resized)
                else:
                    gray = resized.convert('L')
                    dithered = gray.convert('P', palette=1, colors=4, dither=1)
                dithered.save(dithered_path, format='PNG', optimize=True)
                logger.debug(f"Created dithered PNG: {source_path} -> {dithered_path}")
                return os.path.getsize(dithered_path) / 1024

        except Exception as e:
            logger.error(f"Error processing blog image {source_path}: {e}")
            shutil.copy2(source_path, dithered_path)

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
                        f'{singular}_slug': term_data['slug'],
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

    def _generate_date_archives(self) -> None:
        """Generate year (/blog/YYYY/) and year-month (/blog/YYYY/MM/) archive pages."""
        if not self.config.get('blog', 'date_archives', default=True):
            return
        if not self.posts:
            return

        blog_dir = self.config.get('blog', 'directory', default='blog')
        archive_template = self.config.get('blog', 'archive_template', default='archive.html')

        _month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December']

        # Group posts by year, year/month, and year/month/day
        by_year: dict = {}
        by_month: dict = {}
        by_day: dict = {}
        for post in self.posts:
            date = post.get('date')
            if not date or not hasattr(date, 'year'):
                continue
            year_str = str(date.year)
            month_str = f"{date.month:02d}"
            day_str = f"{date.day:02d}"
            by_year.setdefault(year_str, []).append(post)
            by_month.setdefault((year_str, month_str), []).append(post)
            by_day.setdefault((year_str, month_str, day_str), []).append(post)

        def _sorted(posts):
            return sorted(posts, key=lambda p: p.get('date', datetime.min), reverse=True)

        archives = []
        for year_str, posts in by_year.items():
            archives.append({
                'title': year_str,
                'posts': _sorted(posts),
                'rel_path': os.path.join(blog_dir, year_str),
                'url': f'/{blog_dir}/{year_str}/',
                'source_id': f'archive_{year_str}',
                'archive_type': 'year',
                'year': year_str, 'month': None, 'day': None,
            })
        for (year_str, month_str), posts in by_month.items():
            label = f'{_month_names[int(month_str)]} {year_str}'
            archives.append({
                'title': label,
                'posts': _sorted(posts),
                'rel_path': os.path.join(blog_dir, year_str, month_str),
                'url': f'/{blog_dir}/{year_str}/{month_str}/',
                'source_id': f'archive_{year_str}_{month_str}',
                'archive_type': 'month',
                'year': year_str, 'month': month_str, 'day': None,
            })
        for (year_str, month_str, day_str), posts in by_day.items():
            day_label = f'{_month_names[int(month_str)]} {int(day_str)}, {year_str}'
            archives.append({
                'title': day_label,
                'posts': _sorted(posts),
                'rel_path': os.path.join(blog_dir, year_str, month_str, day_str),
                'url': f'/{blog_dir}/{year_str}/{month_str}/{day_str}/',
                'source_id': f'archive_{year_str}_{month_str}_{day_str}',
                'archive_type': 'day',
                'year': year_str, 'month': month_str, 'day': day_str,
            })

        for archive in archives:
            try:
                page_data = {
                    'title': archive['title'],
                    'posts': archive['posts'],
                    'url': archive['url'],
                    'template': archive_template,
                    'archive_type': archive['archive_type'],
                    'archive_year': archive['year'],
                    'archive_month': archive['month'],
                    'archive_month_name': _month_names[int(archive['month'])] if archive['month'] else None,
                    'archive_day': archive['day'],
                }
                if hasattr(self.config, 'format_url'):
                    page_data['url'] = self.config.format_url(page_data['url'])

                self.variable_manager.set_page_variables(page_data)
                variables = {
                    'global': self.variable_manager.variables.get('global', {}),
                    'site': self.variable_manager.variables.get('site', {}),
                    'page': page_data,
                }
                for key, value in variables['global'].items():
                    if key not in variables['site']:
                        variables['site'][key] = value
                if hasattr(self.config, 'config') and 'images' in self.config.config:
                    variables['site']['images'] = self.config.config['images']

                dummy_content = f"<!-- Archive: {archive['title']} -->"
                _, rendered_content = self.template_processor.process_page(
                    dummy_content,
                    False,
                    archive['source_id'],
                    variables,
                )

                output_path = self._get_output_path(archive['rel_path'])
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)
                logger.debug(f"Generated archive: {archive['title']} -> {output_path}")
            except Exception as e:
                logger.error(f"Error generating archive '{archive['title']}': {e}")
                if logger.level <= logging.DEBUG:
                    import traceback
                    traceback.print_exc()

    def _generate_rss_feed(self) -> None:
        """Generate RSS feed for blog posts."""
        try:
            # Check toggle — defaults to enabled
            if not self.config.get('blog', 'rss', 'enabled', default=True):
                return

            # Skip if no posts
            if not self.posts:
                return

            # Get site information
            site_title = self.config.get('site', 'title', default='My Sonne Site')
            site_description = self.config.get('site', 'description', default='')
            site_url = self.config.get('site', 'base_url', default='')
            rss_path = self.config.get('blog', 'rss', 'path', default='feed.xml')
            max_items = self.config.get('blog', 'rss', 'max_items', default=20)

            # Build RSS feed
            rss_items = []

            for post in self.posts[:max_items]:
                post_url = site_url + post['full_url']
                author = post.get('author', self.config.get('site', 'author', default=''))

                # Format post date with timezone if available
                try:
                    pub_date = post['date'].strftime('%a, %d %b %Y %H:%M:%S +0000')
                except:
                    pub_date = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')

                # Cover image — prefer dithered (lighter), fall back to original
                cover_rel = post.get('cover_img_dithered') or post.get('cover_img_original')
                media_tag = ''
                if cover_rel:
                    img_url = f"{post_url.rstrip('/')}/{cover_rel.lstrip('/')}"
                    media_tag = f'\n        <media:thumbnail url="{img_url}" />'

                rss_items.append(
                    f'    <item>\n'
                    f'        <title>{post["title"]}</title>\n'
                    f'        <link>{post_url}</link>\n'
                    f'        <guid isPermaLink="true">{post_url}</guid>\n'
                    f'        <pubDate>{pub_date}</pubDate>\n'
                    f'        <author>{author}</author>\n'
                    f'        <description><![CDATA[{post["excerpt"]}]]></description>'
                    f'{media_tag}\n'
                    f'    </item>\n'
                )

            # Build complete RSS feed
            rss_feed = (
                '<?xml version="1.0" encoding="UTF-8" ?>\n'
                '<rss version="2.0"\n'
                '    xmlns:atom="http://www.w3.org/2005/Atom"\n'
                '    xmlns:media="http://search.yahoo.com/mrss/">\n'
                '<channel>\n'
                f'    <title>{site_title}</title>\n'
                f'    <link>{site_url}</link>\n'
                f'    <description>{site_description}</description>\n'
                f'    <language>{self.config.get("site", "language", default="en")}</language>\n'
                f'    <lastBuildDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")}</lastBuildDate>\n'
                f'    <atom:link href="{site_url}/{rss_path}" rel="self" type="application/rss+xml" />\n'
                + ''.join(rss_items) +
                '</channel>\n'
                '</rss>\n'
            )

            # Write RSS feed to file
            output_path = os.path.join(self.paths['output'], rss_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rss_feed)
                
            logger.debug(f"Generated RSS feed -> {output_path}")
            
        except Exception as e:
            logger.error(f"Error generating RSS feed: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
            
    def _slugify(self, text: str) -> str:
        """Convert text to slug format with security sanitization.

        Args:
            text: Text to convert.

        Returns:
            Slug formatted string, safe for use in URLs and filenames.
        """
        # First ensure text is a string
        text = str(text)

        # First pass: basic slug conversion
        # Remove special characters (keep word chars, spaces, hyphens)
        text = re.sub(r'[^\w\s-]', '', text.lower())
        # Replace spaces with hyphens
        text = re.sub(r'[\s]+', '-', text)
        # Remove multiple hyphens
        text = re.sub(r'[-]+', '-', text)
        # Strip leading/trailing hyphens
        text = text.strip('-')

        # Second pass: security sanitization
        # Use our secure sanitize_filename to catch edge cases
        text = sanitize_filename(text, replace_char='-')

        # Ensure slug isn't empty
        if not text:
            text = 'untitled'

        # Ensure slug isn't too long (max 100 chars for URLs)
        if len(text) > 100:
            text = text[:100].rstrip('-')

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