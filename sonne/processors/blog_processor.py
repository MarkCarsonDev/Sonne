"""
Blog post processing for Sonne.
Handles parsing, rendering, and generating blog posts and related pages.
"""

import heapq
import logging
import math
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple
from xml.sax.saxutils import escape

from sonne.utils.path_utils import (
    normalize_web_path,
    strip_relative_prefix,
    validate_path_within_root,
)
from sonne.utils.text import slugify

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger("sonne")

DEFAULT_BLOG_DIR = "blog"
DEFAULT_URL_PATTERN = "{year}/{month}/{day}/{slug}"
DEFAULT_POSTS_PER_PAGE = 10
DEFAULT_EXCERPT_LENGTH = 200
RELATED_POSTS_COUNT = 3
# Adjacency only breaks ties: a single shared tag always outranks proximity.
ADJACENCY_WEIGHT = 0.1
JPEG_QUALITY = 85
EPOCH = datetime(1970, 1, 1)
LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo
TAXONOMY_SINGULAR = {"tags": "tag", "categories": "category"}
TAXONOMY_TYPES = tuple(TAXONOMY_SINGULAR)
MONTH_NAMES = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

MARKDOWN_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_IMAGE_SRC = re.compile(r'<img[^>]+src=["\'](([^"\']+))["\']')
QUOTED_IMAGE_TITLE = re.compile(r'\s+"([^"]*)"')
FILENAME_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
FENCED_CODE_BLOCK = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.DOTALL | re.MULTILINE)
INLINE_CODE = re.compile(r"`[^`\n]+`")


@dataclass
class _GeneratedPage:
    """A listing page (index, taxonomy, archive) with no Markdown source."""

    page_data: Dict[str, Any]
    placeholder_html: str
    source_id: str
    rel_path: str


@dataclass
class _PublishedImage:
    """Output locations and sizes of one image copied next to a post."""

    image_ref: str
    rel_path: str
    dithered_rel_path: Optional[str]
    original_kb: Optional[float]
    dithered_kb: Optional[float]

    @property
    def has_both_sizes(self) -> bool:
        return bool(self.original_kb and self.dithered_kb)

    @property
    def reduction_percent(self) -> int:
        return int(round((1 - self.dithered_kb / self.original_kb) * 100))


class BlogProcessor:
    """Processes blog posts and generates blog-related pages."""

    def __init__(
        self,
        config,
        paths: Dict[str, str],
        template_processor,
        variable_manager,
        image_processor=None,
    ):
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

        configured_dir = self.config.get("blog", "directory", default=DEFAULT_BLOG_DIR)
        self.blog_dir = DEFAULT_BLOG_DIR if configured_dir is None else configured_dir
        self.blog_content_dir = os.path.join(self.paths.get("content") or "", self.blog_dir)
        self.blog_output_dir = os.path.join(self.paths.get("output") or "", self.blog_dir)
        os.makedirs(self.blog_output_dir, exist_ok=True)

        self.posts = []
        self.taxonomies = {taxonomy_type: {} for taxonomy_type in TAXONOMY_TYPES}
        self.url_style = self.config.get_url_style()
        logger.debug(f"Using URL style: {self.url_style}")

    def collect_post_metadata(self) -> None:
        """Collect blog post metadata without rendering.

        Runs early in the build so that data scripts can reference blog posts
        by slug or tag.
        """
        logger.info("Collecting blog post metadata...")
        if not os.path.exists(self.blog_content_dir):
            logger.debug(f"Blog directory does not exist: {self.blog_content_dir}")
            return
        self._load_posts()
        if not self.posts:
            logger.debug("No blog posts found")
            return
        logger.info(f"Collected metadata for {len(self.posts)} blog posts")

    def process_all_posts(self) -> None:
        """Render all blog posts and generate indexes, taxonomies, archives and RSS."""
        if not os.path.exists(self.blog_content_dir):
            logger.warning(f"Blog directory does not exist: {self.blog_content_dir}")
            return
        if not self.posts:
            self._load_posts()
            if not self.posts:
                logger.info("No blog posts found")
                return

        self._set_navigation_links()
        self._render_posts()
        self._generate_listing_pages()
        self._generate_rss_feed()
        logger.info(f"Processed {len(self.posts)} blog posts")

    # Post collection

    def _load_posts(self) -> None:
        """Collect, sort and index posts, then publish them as variables."""
        self._collect_posts()
        if not self.posts:
            return
        self.posts.sort(key=_post_sort_key, reverse=True)
        self._build_taxonomies()
        self.variable_manager.set("all_blog_posts", self.posts, "global")
        self.variable_manager.set("all_blog_posts", self.posts, "site")

    def _collect_posts(self) -> None:
        """Parse every post under the blog content directory."""
        for file_path in Path(self.blog_content_dir).glob("**/*.md"):
            if "_drafts" in file_path.parts and not self._include_drafts:
                continue
            try:
                post = self._parse_post(file_path)
            except Exception as e:
                _log_error(f"Error parsing blog post {file_path}: {e}")
                continue
            if post:
                self.posts.append(post)
                logger.debug(f"Collected post: {post['title']} from {file_path}")

    @property
    def _include_drafts(self) -> bool:
        return bool(self.config.get("blog", "include_drafts", default=False))

    def _parse_post(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a blog post file.

        Args:
            file_path: Path to the blog post file.

        Returns:
            Dictionary containing post data, or None if the post is a skipped draft.
        """
        raw_content = file_path.read_text(encoding="utf-8")
        front_matter, html_content = self.template_processor.process_markdown(raw_content)
        if front_matter.get("draft", False) and not self._include_drafts:
            logger.debug(f"Skipping draft post: {file_path}")
            return None

        date = self._post_date(front_matter, file_path)
        modified = self._post_modified_date(front_matter, file_path)
        slug = self._post_slug(front_matter, file_path)
        url = self._post_url(date, slug)
        tags, categories = (
            _split_terms(front_matter.get(taxonomy_type, [])) for taxonomy_type in TAXONOMY_TYPES
        )
        return {
            "title": front_matter.get("title", "Untitled"),
            "date": date,
            "date_str": date.strftime("%Y-%m-%d"),
            "date_formatted": date.strftime("%B %d, %Y"),
            "date_posted": date.strftime("%B %d, %Y"),  # {{ page.date_posted }} in templates
            "modified": modified,
            "date_edited": modified.strftime("%B %d, %Y"),
            "author": front_matter.get(
                "author", self.config.get("site", "author", default="Anonymous")
            ),
            "slug": slug,
            "url": url,
            "full_url": self._format_url("/" + os.path.join(self.blog_dir, url).replace("\\", "/")),
            "content": html_content,
            "raw_content": raw_content,  # scanned later for image references
            "excerpt": self._post_excerpt(front_matter, html_content),
            "tags": tags,
            "categories": categories,
            "featured": front_matter.get("featured", False),
            "template": front_matter.get(
                "template", self.config.get("blog", "template", default="blog_post.html")
            ),
            "cover_img": _first_present(front_matter, "cover_img", "cover_image"),
            "cover_crop": front_matter.get("cover_crop"),
            "cover_rotate": front_matter.get("cover_rotate"),
            "source_path": str(file_path),
            "metadata": front_matter,
        }

    def _post_date(self, front_matter: Dict[str, Any], file_path: Path) -> datetime:
        """Resolve the publish date: front matter, then filename prefix, then file creation."""
        raw_date = _first_present(front_matter, "date", "date_posted")
        if raw_date is None:
            prefix = FILENAME_DATE_PREFIX.match(file_path.stem)
            raw_date = prefix.group(1) if prefix else "auto"
        stat = file_path.stat()
        # st_birthtime exists on macOS/BSD (and Windows on Python 3.12+).
        created = datetime.fromtimestamp(getattr(stat, "st_birthtime", stat.st_mtime))
        return _parse_front_matter_date(raw_date, created, file_path.name)

    def _post_modified_date(self, front_matter: Dict[str, Any], file_path: Path) -> datetime:
        """Resolve the last-edited date; missing or 'auto' means the file's mtime."""
        raw_modified = _first_present(front_matter, "modified", "date_edited", default="auto")
        modified = datetime.fromtimestamp(file_path.stat().st_mtime)
        return _parse_front_matter_date(raw_modified, modified, file_path.name)

    @staticmethod
    def _post_slug(front_matter: Dict[str, Any], file_path: Path) -> str:
        """Resolve the slug: explicit slug, else the title, else the undated filename.

        The Jekyll-style date prefix is stripped from filenames because the
        date is already part of the URL pattern.
        """
        slug = _first_present(front_matter, "slug", "page_url")
        if slug:
            return slug
        title = front_matter.get("title")
        if title is None:
            title = FILENAME_DATE_PREFIX.sub("", file_path.stem)
        return slugify(title)

    def _post_url(self, date: datetime, slug: str) -> str:
        """Expand blog.url_pattern for a post, falling back to the default pattern."""
        url_pattern = (
            self.config.get("blog", "url_pattern", default=DEFAULT_URL_PATTERN)
            or DEFAULT_URL_PATTERN
        )
        placeholders = {
            "year": date.year,
            "month": f"{date.month:02d}",
            "day": f"{date.day:02d}",
            "slug": slug,
        }
        try:
            return url_pattern.format(**placeholders)
        except (KeyError, IndexError) as e:
            logger.error(
                f"Invalid blog.url_pattern '{url_pattern}': unknown placeholder {e}. "
                "Supported placeholders: {year}, {month}, {day}, {slug}. "
                "Falling back to the default pattern."
            )
            return DEFAULT_URL_PATTERN.format(**placeholders)

    def _post_excerpt(self, front_matter: Dict[str, Any], html_content: str) -> str:
        """Use the front-matter excerpt/description, or derive one from the content."""
        excerpt = _first_present(front_matter, "excerpt", "description")
        return excerpt or self._auto_excerpt(html_content)

    def _auto_excerpt(self, html_content: str) -> str:
        length = self.config.get("blog", "excerpt_length", default=DEFAULT_EXCERPT_LENGTH)
        return _excerpt_from_html(html_content, length)

    def _build_taxonomies(self) -> None:
        """Group posts by tag and category and publish the groups as variables."""
        for taxonomy_type in TAXONOMY_TYPES:
            self.taxonomies[taxonomy_type] = self._group_posts_by_term(taxonomy_type)
            self.variable_manager.set(taxonomy_type, self.taxonomies[taxonomy_type], "global")
        logger.debug(
            f"Built taxonomy collections: {len(self.taxonomies['tags'])} tags, "
            f"{len(self.taxonomies['categories'])} categories"
        )

    def _group_posts_by_term(self, taxonomy_type: str) -> Dict[str, Dict[str, Any]]:
        """Group posts by term, merging spellings that share a slug ("Python", "python").

        Such terms share one page, so they must share one entry. The display
        name is the first spelling seen, i.e. the newest post's.

        Returns:
            {display name: {"name", "slug", "posts"}}
        """
        terms_by_slug: Dict[str, Dict[str, Any]] = {}
        for post in self.posts:
            for term in post.get(taxonomy_type, []):
                name = str(term)
                slug = slugify(name)
                entry = terms_by_slug.setdefault(slug, {"name": name, "slug": slug, "posts": []})
                if not entry["posts"] or entry["posts"][-1] is not post:
                    entry["posts"].append(post)
        return {entry["name"]: entry for entry in terms_by_slug.values()}

    # Post rendering

    def _set_navigation_links(self) -> None:
        """Set prev (newer), next (older) and related posts on every post."""
        tag_sets = [set(post.get("tags") or []) for post in self.posts]
        for index, post in enumerate(self.posts):
            post["prev_post"] = self._post_link(index - 1)
            post["next_post"] = self._post_link(index + 1)
            post["related_posts"] = self._related_posts(index, tag_sets)

    def _post_link(self, index: int) -> Optional[Dict[str, str]]:
        if not 0 <= index < len(self.posts):
            return None
        return {"title": self.posts[index]["title"], "url": self.posts[index]["full_url"]}

    def _related_posts(self, index: int, tag_sets: List[set]) -> List[Dict[str, Any]]:
        """Rank other posts by shared tags, breaking ties by closeness in the timeline."""

        def relatedness(other: int) -> float:
            shared_tags = len(tag_sets[index] & tag_sets[other])
            proximity = 1.0 / (abs(index - other) + 1)
            return shared_tags + proximity * ADJACENCY_WEIGHT

        others = (other for other in range(len(self.posts)) if other != index)
        best = heapq.nlargest(RELATED_POSTS_COUNT, others, key=relatedness)
        return [self.posts[other] for other in best]

    def _render_posts(self) -> None:
        """Render individual blog posts in two passes.

        Pass 1 renders content Jinja and publishes images for every post, so
        cover_img_dithered and size stats exist on all posts before any
        template (e.g. a related-posts strip) reads them. Content Jinja runs
        here rather than at metadata collection because only now have data
        scripts populated their variables.
        """
        for post in self.posts:
            try:
                self._render_post_content_jinja(post)
                self._copy_post_images(post, os.path.dirname(self._post_output_path(post)))
            except Exception as e:
                logger.error(f"Error processing images for post {post.get('title', '?')}: {e}")

        for post in self.posts:
            self._render_timed_post(post)

    def _post_output_path(self, post: Dict[str, Any]) -> str:
        return self._get_output_path(os.path.join(self.blog_dir, post["url"].rstrip("/")))

    def _render_timed_post(self, post: Dict[str, Any]) -> None:
        started = time.perf_counter()
        try:
            self._render_post(post)
        except Exception as e:
            _log_error(f"Error rendering blog post {post['title']}: {e}")
        finally:
            if self.stats:
                self.stats.record_post(
                    post.get("slug", post.get("title", "?")), time.perf_counter() - started
                )

    def _render_post(self, post: Dict[str, Any]) -> None:
        self.variable_manager.set_page_variables(post)
        _, rendered = self.template_processor.process_page(
            post["content"], False, post["source_path"], self._template_variables(post)
        )
        output_path = self._post_output_path(post)
        _write_page(output_path, rendered)
        if self.stats:
            self.stats.blog_posts_processed += 1
        logger.debug(f"Rendered blog post: {post['title']} -> {output_path}")

    def _render_post_content_jinja(self, post: Dict[str, Any]) -> None:
        """Re-render a post's content with Jinja when enabled for the post.

        Replaces post['content'] (and a generated excerpt) from raw_content
        via Jinja -> markdown -> image-tag rewrite, with the full variable
        context including script variables.
        """
        front_matter = post.get("metadata", {}) or {}
        if not self.template_processor.content_jinja_enabled(front_matter):
            return
        raw = post.get("raw_content")
        if not raw:
            return

        context = self.template_processor.build_content_context(
            {
                "global": self.variable_manager.variables.get("global", {}),
                "site": self.variable_manager.variables.get("site", {}),
            }
        )
        context["page"] = post
        _, html_content = self.template_processor.process_markdown(
            raw,
            rewrite_dithered=True,
            jinja_context=context,
            source=post.get("source_path", post.get("title", "post")),
        )
        post["content"] = html_content

        # Regenerate an auto-excerpt so {{ ... }} never leaks into it;
        # explicit front-matter excerpts are left alone.
        if not front_matter.get("excerpt") and not front_matter.get("description"):
            post["excerpt"] = self._auto_excerpt(html_content)

    def _template_variables(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build the global/site/page scopes passed to the page template.

        Global variables are also copied into the site scope (without
        overriding site values) for templates that read them from there.
        """
        global_vars = self.variable_manager.variables.get("global", {})
        site_vars = self.variable_manager.variables.get("site", {})
        for key, value in global_vars.items():
            site_vars.setdefault(key, value)
        images_config = self.config.get("images")
        if images_config is not None:
            site_vars["images"] = images_config
        return {"global": global_vars, "site": site_vars, "page": page_data}

    def _get_output_path(self, rel_path: str) -> str:
        """Map a path relative to the output root onto a file for the URL style.

        Args:
            rel_path: Path relative to the output directory.

        Returns:
            'rel_path.html' for the html style, 'rel_path/index.html' otherwise.

        Raises:
            ValueError: If the path escapes the output directory.
        """
        if self.url_style == "html":
            output_path = os.path.join(self.paths["output"], f"{rel_path}.html")
        else:
            output_path = os.path.join(self.paths["output"], rel_path, "index.html")

        if not validate_path_within_root(output_path, self.paths["output"]):
            error_msg = f"Path traversal detected: {rel_path} attempts to escape output directory"
            logger.error(error_msg)
            raise ValueError(error_msg)
        return output_path

    def _format_url(self, url: str) -> str:
        return self.config.format_url(url)

    # Post images

    def _copy_post_images(self, post: Dict[str, Any], output_dir: str) -> None:
        """Publish the images a post references, plus its cover image.

        Each image is copied (resized) to its own relative path and, when
        dithering is on, a dithered PNG is written to a 'dithered/'
        subdirectory beside it. The template processor already pointed the
        post's HTML at those paths; this step adds the size annotations.

        Args:
            post: The blog post data.
            output_dir: The output directory for the blog post.
        """
        try:
            if not _pil_available():
                logger.warning("PIL not available, images will be copied without processing")
            published = [
                image
                for image_ref, transforms in _local_image_refs(post)
                if (image := self._publish_inline_image(post, image_ref, transforms, output_dir))
            ]
            self._annotate_image_sizes(post, published)
            self._publish_cover_image(post, output_dir)
        except Exception as e:
            _log_error(f"Error processing images for post {post.get('title', 'unknown')}: {e}")

    @property
    def _dither_enabled(self) -> bool:
        return bool(self.config.get("images", "dither", default=True)) and _pil_available()

    def _publish_inline_image(
        self, post: Dict[str, Any], image_ref: str, transforms: dict, output_dir: str
    ) -> Optional[_PublishedImage]:
        source_path = _source_image_path(post, image_ref)
        if not os.path.exists(source_path):
            logger.warning(f"Image not found: {source_path} (referenced in {post['title']})")
            return None
        return self._publish_image(
            source_path, image_ref, transforms, output_dir, dither=self._dither_enabled
        )

    def _publish_cover_image(self, post: Dict[str, Any], output_dir: str) -> None:
        """Publish the cover image and record its web paths and sizes on the post."""
        cover_img = post.get("cover_img")
        if not cover_img or _is_external_or_vector(cover_img):
            return
        source_path = _source_image_path(post, cover_img)
        if not os.path.exists(source_path):
            logger.warning(
                f"Cover image not found: {source_path} "
                f"(referenced in {post.get('title', 'unknown')})"
            )
            return

        transforms = {}
        if post.get("cover_crop"):
            transforms["crop"] = post["cover_crop"]
        if post.get("cover_rotate"):
            transforms["rotate"] = post["cover_rotate"]
        dither = self._dither_enabled and self.config.get(
            "images", "dither_cover_images", default=True
        )
        image = self._publish_image(source_path, cover_img, transforms, output_dir, dither=dither)

        dithered_rel = image.dithered_rel_path if image.dithered_kb else image.rel_path
        post["cover_img_original"] = normalize_web_path(image.rel_path)
        post["cover_img_dithered"] = normalize_web_path(dithered_rel)
        post["cover_img_original_kb"] = _format_kb(image.original_kb)
        post["cover_img_dithered_kb"] = _format_kb(image.dithered_kb)
        post["cover_img_reduction"] = str(image.reduction_percent) if image.has_both_sizes else ""

    def _publish_image(
        self, source_path: str, image_ref: str, transforms: dict, output_dir: str, dither: bool
    ) -> _PublishedImage:
        """Write the size-capped original and, if requested, its dithered PNG."""
        rel_path = strip_relative_prefix(image_ref)
        original_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(original_path), exist_ok=True)
        original_max_width = self.config.get("images", "blog_original_max_width", default=1600)
        original_kb = self._save_resized(source_path, original_path, original_max_width, transforms)

        dithered_rel_path = dithered_kb = None
        if dither:
            stem = os.path.splitext(os.path.basename(rel_path))[0]
            dithered_rel_path = os.path.join(os.path.dirname(rel_path), "dithered", stem + ".png")
            dithered_path = os.path.join(output_dir, dithered_rel_path)
            os.makedirs(os.path.dirname(dithered_path), exist_ok=True)
            dithered_max_width = self.config.get("images", "blog_dithered_max_width", default=400)
            dithered_kb = self._save_dithered(
                source_path, dithered_path, dithered_max_width, transforms
            )
        return _PublishedImage(image_ref, rel_path, dithered_rel_path, original_kb, dithered_kb)

    def _annotate_image_sizes(self, post: Dict[str, Any], images: List[_PublishedImage]) -> None:
        """Stamp size data onto the post's already-rewritten <figure> markup.

        process_markdown has already turned each <img> into a <figure> whose
        src points at the dithered copy, so images are found by their
        data-original-src instead of the src the author wrote. The HTML is
        parsed once per post, not once per image.
        """
        images = [image for image in images if image.has_both_sizes]
        if not images:
            return
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(post["content"], "html.parser")
            annotated = [image for image in images if _annotate_image_tag(soup, image)]
            if annotated:
                post["content"] = str(soup)
        except Exception as e:
            logger.warning(f"BS4 size-attr injection failed for {post.get('title', '?')}: {e}")

    def _save_resized(
        self, source_path: str, output_path: str, max_width: int, transforms: dict
    ) -> float:
        """Resize source image to max_width and save it in its original format.

        Falls back to a plain copy if the image cannot be processed.

        Returns:
            Output file size in KB.
        """
        from PIL import Image, ImageOps

        try:
            with Image.open(source_path) as img:
                # Read the format first: exif_transpose returns a copy, and copies have no
                # .format, which used to send every PNG down the JPEG path (B12).
                fmt = img.format or "JPEG"
                img = ImageOps.exif_transpose(img)
                if img.mode not in ("RGB", "RGBA", "L"):
                    keeps_alpha = "A" in img.mode or "transparency" in img.info
                    img = img.convert("RGBA" if keeps_alpha else "RGB")
                resized = _resize_to_width(_apply_transforms(img, transforms), max_width)
                save_options = {"optimize": True}
                if fmt in ("JPEG", "JPG"):
                    save_options["quality"] = JPEG_QUALITY
                    if resized.mode not in ("RGB", "L"):  # JPEG has no alpha channel
                        resized = resized.convert("RGB")
                resized.save(output_path, format=fmt, **save_options)
        except Exception as e:
            logger.error(f"Error saving resized image {source_path}: {e}")
            shutil.copy2(source_path, output_path)
        return _size_kb(output_path)

    def _save_dithered(
        self, source_path: str, dithered_path: str, max_width: int, transforms: dict
    ) -> Optional[float]:
        """Resize and dither an image with the shared ImageProcessor pipeline.

        Args:
            source_path: Source image path.
            dithered_path: Output path for the dithered PNG.
            max_width: Resize to this width before dithering.
            transforms: Transform directives (crop, rotate); may be empty.

        Returns:
            Dithered file size in KB, or None if dithering failed (the source
            is copied to dithered_path instead, and callers show no savings).
        """
        from PIL import Image, ImageOps

        try:
            with Image.open(source_path) as img:
                img = ImageOps.exif_transpose(img)
                resized = _resize_to_width(_apply_transforms(img, transforms), max_width)
                if self.image_processor is not None:
                    dithered = self.image_processor._apply_dither(resized)
                else:
                    dithered = resized.convert("L").convert("P", palette=1, colors=4, dither=1)
                dithered.save(dithered_path, format="PNG", optimize=True)
        except Exception as e:
            logger.error(f"Error processing blog image {source_path}: {e}")
            shutil.copy2(source_path, dithered_path)
            return None
        logger.debug(f"Created dithered PNG: {source_path} -> {dithered_path}")
        return _size_kb(dithered_path)

    # Listing pages

    def _generate_listing_pages(self) -> None:
        """Generate index, taxonomy and date-archive pages; one failure doesn't stop the rest."""
        generators = (
            (self._generate_index_pages, "blog index pages"),
            (self._generate_taxonomy_pages, "taxonomy pages"),
            (self._generate_date_archives, "date archives"),
        )
        for generate, description in generators:
            try:
                generate()
            except Exception as e:
                _log_error(f"Error generating {description}: {e}")

    def _render_generated_page(self, page: _GeneratedPage) -> str:
        """Render a listing page through its template and write it; returns the output path."""
        self.variable_manager.set_page_variables(page.page_data)
        _, rendered = self.template_processor.process_page(
            page.placeholder_html, False, page.source_id, self._template_variables(page.page_data)
        )
        output_path = self._get_output_path(page.rel_path)
        _write_page(output_path, rendered)
        return output_path

    def _generate_index_pages(self) -> None:
        """Generate the paginated blog index: /blog/, /blog/page/2/, ..."""
        posts_per_page = self._posts_per_page()
        total_pages = math.ceil(len(self.posts) / posts_per_page)
        global_vars = self.variable_manager.variables.get("global", {})
        logger.debug(
            f"Using template "
            f"{self.config.get('blog', 'list_template', default='blog_list.html')} "
            f"for blog index pages"
        )

        for page_num in range(1, total_pages + 1):
            start = (page_num - 1) * posts_per_page
            has_next = page_num < total_pages
            page_data = {
                "title": f"Blog - Page {page_num}" if page_num > 1 else "Blog",
                "description": f"Blog posts - Page {page_num} of {total_pages}",
                "posts": self.posts[start : start + posts_per_page],
                "pagination": {
                    "current": page_num,
                    "total": total_pages,
                    "has_prev": page_num > 1,
                    "has_next": has_next,
                    "prev_url": self._index_page_url(page_num - 1) if page_num > 1 else None,
                    "next_url": self._index_page_url(page_num + 1) if has_next else None,
                },
                "url": self._index_page_url(page_num),
            }
            # Index templates read globals (e.g. battery status) from page scope.
            for key, value in global_vars.items():
                page_data.setdefault(key, value)

            rel_path = (
                self.blog_dir
                if page_num == 1
                else os.path.join(self.blog_dir, "page", str(page_num))
            )
            output_path = self._render_generated_page(
                _GeneratedPage(
                    page_data,
                    f"<h1>{page_data['title']}</h1><p>{page_data['description']}</p>",
                    "blog_index",
                    rel_path,
                )
            )
            logger.debug(f"Generated blog index page {page_num}/{total_pages} -> {output_path}")

    def _posts_per_page(self) -> int:
        """Read blog.posts_per_page, falling back to the default for invalid values.

        validate() flags bad values at build start; this guard keeps a bad
        config from silently producing no index pages.
        """
        posts_per_page = self.config.get("blog", "posts_per_page", default=DEFAULT_POSTS_PER_PAGE)
        is_positive_int = (
            isinstance(posts_per_page, int)
            and not isinstance(posts_per_page, bool)
            and posts_per_page >= 1
        )
        if is_positive_int:
            return posts_per_page
        logger.warning(
            f"Invalid blog.posts_per_page ({posts_per_page!r}); using {DEFAULT_POSTS_PER_PAGE}"
        )
        return DEFAULT_POSTS_PER_PAGE

    def _index_page_url(self, page_num: int) -> str:
        blog_url = f"/{self.blog_dir}".rstrip("/")
        return self._format_url(blog_url if page_num == 1 else f"{blog_url}/page/{page_num}")

    def _generate_taxonomy_pages(self) -> None:
        """Generate term and index pages for each enabled taxonomy."""
        for taxonomy_type in TAXONOMY_TYPES:
            if self.config.get("blog", "taxonomies", taxonomy_type, "enabled", default=True):
                self._generate_taxonomy_type_pages(taxonomy_type)

    def _generate_taxonomy_type_pages(self, taxonomy_type: str) -> None:
        """Generate one page per term plus an index of all terms."""
        terms = self.taxonomies[taxonomy_type]
        if not terms:
            logger.info(f"No {taxonomy_type} found, skipping")
            return

        for term in terms.values():
            try:
                self._generate_term_page(taxonomy_type, term)
            except Exception as e:
                _log_error(f"Error generating page for {taxonomy_type} '{term['name']}': {e}")
        try:
            self._generate_taxonomy_index_page(taxonomy_type)
        except Exception as e:
            _log_error(f"Error generating {taxonomy_type} index page: {e}")

    def _generate_term_page(self, taxonomy_type: str, term: Dict[str, Any]) -> None:
        singular = TAXONOMY_SINGULAR[taxonomy_type]
        page_data = {
            "title": f"{term['name']} ({singular.capitalize()})",
            "description": f"Posts with {singular} {term['name']}",
            singular: term["name"],
            f"{singular}_slug": term["slug"],
            "posts": term["posts"],
            "url": self._format_url(f"/{self.blog_dir}/{taxonomy_type}/{term['slug']}"),
        }
        output_path = self._render_generated_page(
            _GeneratedPage(
                page_data,
                f"<!-- {singular.capitalize()} Page: {term['name']} -->",
                f"{singular}_{term['slug']}",
                os.path.join(self.blog_dir, taxonomy_type, term["slug"]),
            )
        )
        logger.debug(f"Generated {singular} page: {term['name']} -> {output_path}")

    def _generate_taxonomy_index_page(self, taxonomy_type: str) -> None:
        page_data = {
            "title": taxonomy_type.capitalize(),
            "description": f"All {taxonomy_type}",
            taxonomy_type: self.taxonomies[taxonomy_type],
            "url": self._format_url(f"/{self.blog_dir}/{taxonomy_type}"),
        }
        output_path = self._render_generated_page(
            _GeneratedPage(
                page_data,
                f"<!-- {taxonomy_type.capitalize()} Index Page -->",
                f"{taxonomy_type}_index",
                os.path.join(self.blog_dir, taxonomy_type),
            )
        )
        logger.debug(f"Generated {taxonomy_type} index page -> {output_path}")

    def _generate_date_archives(self) -> None:
        """Generate year (/blog/YYYY/), month (/blog/YYYY/MM/) and day archive pages."""
        if not self.config.get("blog", "date_archives", default=True) or not self.posts:
            return
        archive_template = self.config.get("blog", "archive_template", default="archive.html")
        for date_parts, posts in self._posts_by_date_prefix().items():
            title = _archive_title(date_parts)
            try:
                output_path = self._render_generated_page(
                    self._archive_page(date_parts, posts, title, archive_template)
                )
                logger.debug(f"Generated archive: {title} -> {output_path}")
            except Exception as e:
                _log_error(f"Error generating archive '{title}': {e}")

    def _posts_by_date_prefix(self) -> Dict[Tuple[str, ...], List[Dict[str, Any]]]:
        """Group posts under ('YYYY',), ('YYYY', 'MM') and ('YYYY', 'MM', 'DD'), newest first.

        Keys are ordered all years, then all months, then all days.
        """
        groups: List[Dict[Tuple[str, ...], List[Dict[str, Any]]]] = [{}, {}, {}]
        for post in self.posts:
            date = post.get("date")
            if not date or not hasattr(date, "year"):
                continue
            parts = (str(date.year), f"{date.month:02d}", f"{date.day:02d}")
            for depth, group in enumerate(groups, start=1):
                group.setdefault(parts[:depth], []).append(post)
        merged = {key: posts for group in groups for key, posts in group.items()}
        for posts in merged.values():
            posts.sort(key=_post_sort_key, reverse=True)
        return merged

    def _archive_page(
        self,
        date_parts: Tuple[str, ...],
        posts: List[Dict[str, Any]],
        title: str,
        archive_template: str,
    ) -> _GeneratedPage:
        year, month, day = (date_parts + (None, None))[:3]
        archive_type = ("year", "month", "day")[len(date_parts) - 1]
        page_data = {
            "title": title,
            "posts": posts,
            "url": self._format_url(f"/{self.blog_dir}/{'/'.join(date_parts)}/"),
            "template": archive_template,
            "archive_type": archive_type,
            "archive_year": year,
            "archive_month": month,
            "archive_month_name": MONTH_NAMES[int(month)] if month else None,
            "archive_day": day,
        }
        return _GeneratedPage(
            page_data,
            f"<!-- Archive: {title} -->",
            "archive_" + "_".join(date_parts),
            os.path.join(self.blog_dir, *date_parts),
        )

    # RSS

    def _generate_rss_feed(self) -> None:
        """Write the RSS 2.0 feed of the newest posts."""
        if not self.config.get("blog", "rss", "enabled", default=True) or not self.posts:
            return
        try:
            rss_path = self.config.get("blog", "rss", "path", default="feed.xml")
            output_path = os.path.join(self.paths["output"], rss_path)
            _write_page(output_path, self._rss_document(rss_path))
            logger.debug(f"Generated RSS feed -> {output_path}")
        except Exception as e:
            _log_error(f"Error generating RSS feed: {e}")

    def _rss_document(self, rss_path: str) -> str:
        """Build the feed XML. All interpolated text is XML-escaped."""
        # Every feed URL is site_url + "/path"; a configured trailing slash
        # would otherwise double it.
        site_url = str(self.config.get("site", "base_url", default="") or "").rstrip("/")
        site_title = self.config.get("site", "title", default="My Sonne Site")
        site_description = self.config.get("site", "description", default="")
        language = self.config.get("site", "language", default="en")
        max_items = self.config.get("blog", "rss", "max_items", default=20)
        items = "".join(self._rss_item(post, site_url) for post in self.posts[:max_items])
        return (
            '<?xml version="1.0" encoding="UTF-8" ?>\n'
            '<rss version="2.0"\n'
            '    xmlns:atom="http://www.w3.org/2005/Atom"\n'
            '    xmlns:media="http://search.yahoo.com/mrss/">\n'
            "<channel>\n"
            f"    <title>{escape(str(site_title))}</title>\n"
            f"    <link>{escape(str(site_url))}</link>\n"
            f"    <description>{escape(str(site_description))}</description>\n"
            f"    <language>{escape(str(language))}</language>\n"
            f"    <lastBuildDate>{_rfc822(datetime.now())}</lastBuildDate>\n"
            f'    <atom:link href="{_xml_attribute(f"{site_url}/{rss_path}")}" '
            'rel="self" type="application/rss+xml" />\n'
            f"{items}"
            "</channel>\n"
            "</rss>\n"
        )

    def _rss_item(self, post: Dict[str, Any], site_url: str) -> str:
        post_url = site_url + post["full_url"]
        author = post.get("author", self.config.get("site", "author", default=""))
        # Prefer the lighter dithered cover, fall back to the original.
        cover_rel = post.get("cover_img_dithered") or post.get("cover_img_original")
        media_tag = ""
        if cover_rel:
            cover_url = f"{post_url.rstrip('/')}/{cover_rel.lstrip('/')}"
            media_tag = f'\n        <media:thumbnail url="{_xml_attribute(cover_url)}" />'
        return (
            "    <item>\n"
            f"        <title>{escape(str(post['title']))}</title>\n"
            f"        <link>{escape(post_url)}</link>\n"
            f'        <guid isPermaLink="true">{escape(post_url)}</guid>\n'
            f"        <pubDate>{_rfc822(post.get('date'))}</pubDate>\n"
            f"        <author>{escape(str(author))}</author>\n"
            f"        <description>{escape(str(post['excerpt']))}</description>"
            f"{media_tag}\n"
            "    </item>\n"
        )


def _log_error(message: str) -> None:
    """Log an error, with the traceback only when debug logging is on."""
    logger.error(message, exc_info=logger.isEnabledFor(logging.DEBUG))


def _write_page(output_path: str, content: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)


def _first_present(mapping: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return the value of the first key present in mapping (even if falsy)."""
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def _post_sort_key(post: Dict[str, Any]) -> datetime:
    """The post's date as a timezone-aware datetime, so all posts compare.

    Front matter may mix plain dates with timezone-aware timestamps
    (``2024-01-05 12:00:00+02:00``); plain ones are read as local time.
    """
    date = post.get("date", "")
    if isinstance(date, datetime):
        return _as_aware(date)
    if all(hasattr(date, part) for part in ("year", "month", "day")):
        return _as_aware(datetime(date.year, date.month, date.day))
    logger.warning(f"Invalid date format for post {post.get('title', 'Unknown')}, using epoch")
    return _as_aware(EPOCH)


def _as_aware(moment: datetime) -> datetime:
    # Attaches the current local offset instead of calling astimezone(),
    # which raises OSError on Windows for naive datetimes near 1970.
    return moment if moment.tzinfo else moment.replace(tzinfo=LOCAL_TIMEZONE)


def _parse_front_matter_date(value: Any, fallback: datetime, source_name: str) -> datetime:
    """Parse a front-matter date; 'auto' or an unusable value yields fallback."""
    if isinstance(value, str):
        return _parse_date_string(value, fallback, source_name)
    if isinstance(value, datetime):
        return value
    if hasattr(value, "year"):
        return datetime(value.year, value.month, value.day)
    return fallback


def _parse_date_string(value: str, fallback: datetime, source_name: str) -> datetime:
    if value.strip().lower() == "auto":
        return fallback
    parts = value.strip().split("-")
    if len(parts) == 3:  # accept unpadded dates like 2024-1-5
        value = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        logger.warning(
            f"Unparseable date '{value}' in {source_name}; "
            "falling back to the file's timestamp (expected YYYY-MM-DD)"
        )
        return fallback


def _split_terms(taxonomy_value: Any) -> List[str]:
    """Normalize a front-matter tags/categories value to a list of strings.

    Strings are split on commas and whitespace; lists are stringified item by item.
    """
    if not taxonomy_value:
        return []
    if isinstance(taxonomy_value, str):
        return [term for term in re.split(r"[,\s]+", taxonomy_value) if term]
    if isinstance(taxonomy_value, list):
        return [str(term).strip() for term in taxonomy_value if str(term).strip()]
    return [str(taxonomy_value).strip()]


def _excerpt_from_html(html_content: str, length: int = DEFAULT_EXCERPT_LENGTH) -> str:
    """Strip tags, collapse whitespace and truncate to length (adding '...')."""
    text = re.sub(r"<[^>]+>", "", html_content)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > length:
        text = text[:length] + "..."
    return text


def _archive_title(date_parts: Tuple[str, ...]) -> str:
    """'2024', 'January 2024' or 'January 5, 2024' for a year/month/day archive."""
    if len(date_parts) == 1:
        return date_parts[0]
    year, month = date_parts[0], MONTH_NAMES[int(date_parts[1])]
    if len(date_parts) == 2:
        return f"{month} {year}"
    return f"{month} {int(date_parts[2])}, {year}"


def _local_image_refs(post: Dict[str, Any]) -> Iterator[Tuple[str, dict]]:
    """Yield (image_ref, transforms) for each local raster image the post references.

    Markdown images come first, then <img> tags. Remote, root-relative and
    SVG images, and anything inside code samples, are skipped. When a path
    appears more than once, the last Markdown title's transforms apply to
    every occurrence.
    """
    content = _without_code(post.get("raw_content", post.get("content", "")))
    image_refs = []
    transforms_by_ref = {}
    for match in MARKDOWN_IMAGE.finditer(content):
        path_with_title = match.group(2).strip()
        image_ref = path_with_title.split()[0] if " " in path_with_title else path_with_title
        title = QUOTED_IMAGE_TITLE.search(path_with_title)
        if title:
            _, transforms = _parse_transforms(title.group(1))
            if transforms:
                transforms_by_ref[image_ref] = transforms
        image_refs.append(image_ref)
    image_refs.extend(match.group(1) for match in HTML_IMAGE_SRC.finditer(content))

    for image_ref in image_refs:
        if not _is_external_or_vector(image_ref):
            yield image_ref, transforms_by_ref.get(image_ref, {})


def _without_code(markdown: str) -> str:
    """Remove fenced code blocks and inline code spans, whose image syntax is only sample text."""
    return INLINE_CODE.sub("", FENCED_CODE_BLOCK.sub("", markdown))


def _is_external_or_vector(image_ref: str) -> bool:
    return image_ref.startswith(("http://", "https://", "/")) or image_ref.endswith(".svg")


def _source_image_path(post: Dict[str, Any], image_ref: str) -> str:
    post_source_dir = os.path.dirname(post.get("source_path", ""))
    return os.path.normpath(os.path.join(post_source_dir, image_ref))


def _annotate_image_tag(soup, image: _PublishedImage) -> bool:
    """Add size data to the <img> for image and its figure caption/button.

    Returns:
        True if a matching <img> was found.
    """
    ref = strip_relative_prefix(image.image_ref)
    for img_tag in soup.find_all("img"):
        original_src = img_tag.get("data-original-src", "")
        if strip_relative_prefix(original_src) == ref or original_src.endswith("/" + ref):
            dithered_size = _format_kb(image.dithered_kb)
            original_size = _format_kb(image.original_kb)
            img_tag["data-dithered-size"] = dithered_size
            img_tag["data-original-size"] = original_size
            img_tag["data-size-reduction"] = str(image.reduction_percent)
            figure = img_tag.find_parent("figure")
            if figure:
                caption = figure.find("span", class_="caption-text")
                if caption:
                    caption.string = (
                        f"{caption.get_text()} · {dithered_size} (−{image.reduction_percent}%)"
                    )
                button = figure.find("button", class_="request-original-btn")
                if button:
                    button["data-original-size"] = original_size
            return True
    logger.debug(f"Could not find img with data-original-src matching {ref} in post HTML")
    return False


def _parse_transforms(title: str) -> Tuple[str, dict]:
    """Split an image title into display text and transform directives.

    Format: "Display title | crop=16:9 rotate=90". Digit-only values become ints.

    Returns:
        (display_title, transforms)
    """
    if "|" not in title:
        return title.strip(), {}
    display, directives = title.split("|", 1)
    transforms = {}
    for token in directives.strip().split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        try:
            transforms[key.strip()] = int(value) if value.isdigit() else value.strip()
        except ValueError:  # isdigit() accepts characters like '²' that int() rejects
            transforms[key.strip()] = value.strip()
    return display.strip(), transforms


def _apply_transforms(img: "Image.Image", transforms: dict) -> "Image.Image":
    """Apply rotate (degrees clockwise) and crop (aspect ratio 'W:H') transforms."""
    if not transforms:
        return img
    if "rotate" in transforms:
        try:
            img = img.rotate(-float(transforms["rotate"]), expand=True)
        except (ValueError, TypeError):
            logger.warning(f"Invalid rotate value: {transforms['rotate']}")
    if "crop" in transforms:
        img = _center_crop_to_ratio(img, str(transforms["crop"]))
    return img


def _center_crop_to_ratio(img: "Image.Image", ratio: str) -> "Image.Image":
    if ":" not in ratio:
        return img
    try:
        width_part, height_part = ratio.split(":", 1)
        target_ratio = float(width_part) / float(height_part)
    except (ValueError, ZeroDivisionError):
        logger.warning(f"Invalid crop ratio: {ratio}")
        return img
    current_ratio = img.width / img.height
    if current_ratio > target_ratio:
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        return img.crop((left, 0, left + new_width, img.height))
    if current_ratio < target_ratio:
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        return img.crop((0, top, img.width, top + new_height))
    return img


def _resize_to_width(img: "Image.Image", max_width: int) -> "Image.Image":
    """Return a copy of img no wider than max_width, preserving aspect ratio."""
    from PIL import Image

    if img.width > max_width:
        height = int(img.height * max_width / img.width)
        return img.resize((max_width, height), Image.LANCZOS)
    return img.copy()


def _pil_available() -> bool:
    try:
        import PIL  # noqa: F401 — availability check only
    except ImportError:
        return False
    return True


def _size_kb(path: str) -> float:
    return os.path.getsize(path) / 1024


def _format_kb(size_kb: Optional[float]) -> str:
    return f"{size_kb:.0f}K" if size_kb else ""


def _xml_attribute(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _rfc822(dt: Any) -> str:
    """Format a datetime as RFC 822 with the local UTC offset (now if not a datetime)."""
    if not isinstance(dt, datetime):
        dt = datetime.now()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
