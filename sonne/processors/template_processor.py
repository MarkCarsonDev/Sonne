"""
Template processing for Sonne.
Handles rendering templates, processing Markdown, and extracting front matter.
"""

import json
import logging
import os
import re
from collections.abc import Iterator
from pathlib import PurePath
from typing import Any, Callable, NoReturn, Optional

import jinja2
import markdown
import yaml
from bs4 import BeautifulSoup, Tag
from jinja2 import TemplateSyntaxError, UndefinedError
from markupsafe import Markup

from sonne.processors.blog_urls import BlogUrls
from sonne.processors.dithered_images import DitheredImages
from sonne.utils.build_stats import BuildStatistics
from sonne.utils.constants import MARKDOWN_EXTENSIONS
from sonne.utils.page_location import page_output_path, page_url
from sonne.utils.path_utils import is_post_local_raster_image, validate_path_within_root
from sonne.utils.text import slugify

logger = logging.getLogger("sonne")

# Python-Markdown extensions (parser plugins, not file suffixes).
MARKDOWN_PARSER_EXTENSIONS = [
    "markdown.extensions.meta",
    "markdown.extensions.tables",
    "markdown.extensions.fenced_code",
    "markdown.extensions.toc",
    "markdown.extensions.smarty",
    "markdown.extensions.footnotes",
    "markdown.extensions.attr_list",
    "markdown.extensions.def_list",
    "markdown.extensions.abbr",
    "markdown.extensions.sane_lists",
]

TEMPLATE_EXTENSIONS = (".html", ".htm", ".xml", ".txt", ".j2", ".jinja2")


def _load_yaml_front_matter(text: str) -> dict[str, Any]:
    return yaml.safe_load(text) or {}


# (syntax name, pattern with (front matter, body) groups, parser)
FRONT_MATTER_FORMATS = [
    ("YAML", re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL), _load_yaml_front_matter),
    ("JSON", re.compile(r"^;;;\s*\n(.*?)\n;;;\s*\n(.*)$", re.DOTALL), json.loads),
]

# Images under static/images/ are served from /images/. Rewrites apply to
# Markdown images, HTML <img> tags, and "url:" values in YAML/JSON blocks.
STATIC_IMAGE_REWRITES = [
    (re.compile(r"!\[(.*?)\]\(/static/images/(.*?)\)"), r"![\1](/images/\2)"),
    (re.compile(r'<img([^>]*?)src="/static/images/(.*?)"([^>]*?)>'), r'<img\1src="/images/\2"\3>'),
    (re.compile(r"(url:\s*)/static/images/(.*?)(\s)"), r"\1/images/\2\3"),
    (re.compile(r'("url":\s*")/static/images/(.*?)(")'), r"\1/images/\2\3"),
]

# Only images next to a post get dithered variants from the blog pipeline.

# The toggle button's quincunx dither icon: (x, y) of each square cell.
DITHER_ICON_CELLS = [
    ("13.51", "13.58"),
    ("37.93", "37.86"),
    ("62.21", "13.58"),
    ("13.51", "62.14"),
    ("62.21", "62.14"),
]
DITHER_ICON_CELL_SIZE = "24.28"

# Legacy substitution/embedded-python markers. These syntaxes were removed
# (they were never wired into the build); markers found in content now
# render literally, so the author is warned once per file.
LEGACY_MARKER_RE = re.compile(r"\{\+\}\{|\{-\}\{|\{p\}\{#")

# Markup.format escapes every interpolated value.
# Page used when a page has no template, or its template fails: still a valid
# document with a language, a title and a main landmark.
MINIMAL_PAGE = Markup(
    "<!DOCTYPE html>\n"
    '<html lang="{language}"><head><meta charset="utf-8"><title>{title}</title></head>'
    "<body><main><h1>{title}</h1>{body}</main></body></html>"
)
PLAIN_IMAGE_MARKUP = Markup('<img src="{src}" alt="{alt}" loading="{loading}">')
BUILTIN_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
# Last on the search path: tag/tags/category/categories/archive pages for
# sites that do not ship their own.
FALLBACK_TEMPLATES_DIR = os.path.join(BUILTIN_TEMPLATES_DIR, "_fallback")
SITE_BASE_TEMPLATE = "base.html"
FALLBACK_BASE_TEMPLATE = "sonne_fallback_base.html"

# The shared dithering assets (sonne/static, copied to the output by the build).
# A page that does not link them gets them added; bundled templates link them.
DITHERING_STYLESHEET_URL = "/css/dithering.css"
DITHERING_SCRIPT_URL = "/js/dithering.js"


class TemplateProcessor:
    """Processes templates and content files."""

    def __init__(self, config, paths: dict[str, str]):
        """Initialize template processor.

        Args:
            config: Site configuration.
            paths: Dictionary of normalized paths.
        """
        self.config = config
        self.paths = paths
        self.stats: Optional[BuildStatistics] = None  # Injected by SiteGenerator
        # The images this build dithered; SiteGenerator shares the ImageProcessor's.
        self.dithered_images = DitheredImages()
        self.dithering_enabled = self.config.get("images", "dither", default=True)
        logger.info(f"Dithering enabled: {self.dithering_enabled}")
        # Bare names that moved under `data` (name -> where it is now); a
        # template that still uses one gets a warning saying so, once.
        self._names_under_data: dict[str, str] = {}
        self._names_hinted: set[str] = set()
        self.jinja_env = self._create_jinja_env()
        # Per instance, so every build (including `sonne serve` rebuilds)
        # warns once per file.
        self._legacy_marker_warned = set()

    def _create_jinja_env(self) -> jinja2.Environment:
        """Create the Jinja environment: site templates, then built-ins, then fallbacks."""
        template_dirs = [
            directory
            for directory in (
                self.paths.get("templates"),
                BUILTIN_TEMPLATES_DIR,
                FALLBACK_TEMPLATES_DIR,
            )
            if directory and os.path.exists(directory)
        ]
        logger.info(f"Template directories: {template_dirs}")
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dirs),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            undefined=_undefined_with_data_hints(self._names_under_data, self._names_hinted),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        env.filters.update(
            {
                "date": _format_date,
                "markdown": _render_markdown,
                "word_count": _word_count,
                # Must be the canonical slugify the blog uses for post URLs
                # and taxonomy pages, or template-built tag links 404.
                "slugify": slugify,
                "truncate_words": _truncate_words,
                "process_image": self._image_markup,
            }
        )
        env.globals["dithering_enabled"] = self.dithering_enabled
        # What the fallback templates extend: the site's base.html when the
        # search path has one, else a minimal built-in page.
        env.globals["sonne_base_template"] = (
            SITE_BASE_TEMPLATE
            if _template_exists(env, SITE_BASE_TEMPLATE)
            else FALLBACK_BASE_TEMPLATE
        )
        blog_urls = BlogUrls(self.config)
        env.globals.update(
            {
                # Links to generated blog pages; they follow blog.directory
                # and url_style, and slugify terms like the pages themselves.
                "blog_url": blog_urls.index,
                "tag_url": blog_urls.tag,
                "category_url": blog_urls.category,
                "archive_url": blog_urls.archive,
            }
        )
        logger.info("Jinja environment initialized successfully")
        return env

    def _image_markup(self, src, alt="Image", loading="lazy"):
        """Jinja ``process_image`` filter: an escaped <img> tag.

        If the build dithered the image, finishing the page points the tag at
        the dithered copy and records the original for the toggle, as for any
        other <img>.

        Args:
            src: Image source URL (a static image or a sized variant).
            alt: Image alt text.
            loading: Loading attribute value.

        Returns:
            Markup for the image. All arguments are HTML-escaped.
        """
        return PLAIN_IMAGE_MARKUP.format(src=src, alt=alt, loading=loading)

    def validate_templates(self) -> list[str]:
        """Validate all site templates for syntax and render errors.

        Each template is loaded (syntax check) and rendered with an empty
        context. Undefined variables are expected with that context and are
        not reported.

        Returns:
            List of error messages. Empty list means all templates are valid.
        """
        templates_dir = self.paths.get("templates")
        if not templates_dir or not os.path.exists(templates_dir):
            return ["Templates directory not found"]
        errors = [self._template_error(name) for name in _template_names(templates_dir)]
        return [error for error in errors if error]

    def _template_error(self, template_name: str) -> Optional[str]:
        """Error message for one template, or None if it loads and renders."""
        try:
            template = self.jinja_env.get_template(template_name)
        except TemplateSyntaxError as e:
            return f"{template_name}:{e.lineno}: Syntax error - {e.message}"
        except Exception as e:
            return f"{template_name}: {e!s}"
        try:
            template.render(site={}, page={}, content="")
        except UndefinedError as e:
            logger.debug(f"{template_name}: undefined variable with empty context ({e})")
        except Exception as e:
            return f"{template_name}: Render error - {e!s}"
        return None

    def extract_front_matter(self, content: str) -> tuple[dict[str, Any], str]:
        """Extract YAML (``---``) or JSON (``;;;``) front matter from content.

        Front matter that fails to parse is logged and treated as absent.

        Args:
            content: Content string possibly containing front matter.

        Returns:
            Tuple of (front_matter, content_without_front_matter).
        """
        for syntax, pattern, parse in FRONT_MATTER_FORMATS:
            match = pattern.match(content)
            if not match:
                continue
            try:
                return parse(match.group(1)), match.group(2)
            except Exception as e:
                logger.error(f"Error parsing {syntax} front matter: {e}")
        return {}, content

    def _warn_legacy_markers(self, content: str, source: str) -> None:
        """Warn once per source file about removed {+}{}/{-}{}/{p}{# syntax."""
        if source in self._legacy_marker_warned:
            return
        if LEGACY_MARKER_RE.search(content):
            self._legacy_marker_warned.add(source)
            logger.warning(
                f"{source} contains removed Sonne/Mond markers ({{+}}{{...}}, "
                f"{{-}}{{...}} or {{p}}{{#...#}}); these render literally now. "
                "Use Jinja instead: {{ variable }} with content.render_jinja "
                "(or `jinja: true` front matter), and data scripts with "
                "sonne_global()/sonne_filter() for Python."
            )

    def hint_names_under_data(self, names: dict[str, str]) -> None:
        """Set the bare names that now live under `data`, for this build's warnings.

        Args:
            names: Bare name -> where it is now, e.g. {"team": "data.team"}.
        """
        self._names_under_data.clear()
        self._names_under_data.update(names)
        self._names_hinted.clear()

    def register_extensions(self, filters: dict[str, Any], globals_: dict[str, Any]) -> None:
        """Register script-provided Jinja filters and globals.

        Called by SiteGenerator after data scripts run. Names that collide
        with built-in filters/globals are ignored with a warning.

        Args:
            filters: Mapping of filter name -> callable.
            globals_: Mapping of global name -> value or callable.
        """
        for name, fn in (filters or {}).items():
            if name in self.jinja_env.filters:
                logger.warning(f"Script filter '{name}' collides with a built-in filter; ignored")
                continue
            self.jinja_env.filters[name] = fn
        for name, value in (globals_ or {}).items():
            if name in self.jinja_env.globals:
                logger.warning(f"Script global '{name}' collides with a built-in global; ignored")
                continue
            self.jinja_env.globals[name] = value

    def render_content_jinja(self, content: str, context: dict[str, Any], source: str) -> str:
        """Render a content body through Jinja before markdown conversion.

        Note: unlike .html templates, from_string templates are NOT
        autoescaped (select_autoescape keys off the template name), so
        HTML-bearing variables insert raw — the right semantic for markdown
        source. Errors log and fall back to the unrendered content
        (log-and-continue house style).

        Args:
            content: Raw content body (front matter already stripped).
            context: Template context (same shape the page template gets).
            source: Source path for error messages.

        Returns:
            Rendered content, or the original on error.
        """
        try:
            return self.jinja_env.from_string(content).render(**context)
        except Exception as e:
            logger.error(f"Jinja error in content {source}: {e}; rendering without Jinja")
            return content

    def build_content_context(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Build the Jinja context for content rendering.

        Mirrors template rendering: global and site variables are available
        bare, plus a merged `site` namespace. `page` is filled by the caller
        (post dict) or defaulted to the file's front matter.
        """
        variables = variables if isinstance(variables, dict) else {}
        global_vars = variables.get("global", {}) or {}
        site_vars = variables.get("site", {}) or {}
        context = {}
        context.update(global_vars)
        context.update(site_vars)
        merged_site = dict(site_vars)
        for key, value in global_vars.items():
            merged_site.setdefault(key, value)
        context["site"] = merged_site
        return context

    def content_jinja_enabled(self, front_matter: dict[str, Any]) -> bool:
        """Whether content Jinja applies to a file, honoring the override.

        Per-file front matter `jinja: true|false` beats the site-wide
        `content.render_jinja` setting (default false).
        """
        per_file = front_matter.get("jinja")
        if isinstance(per_file, bool):
            return per_file
        return bool(self.config.get("content", "render_jinja", default=False))

    def process_markdown(
        self,
        content: str,
        rewrite_dithered: bool = True,
        jinja_context: Optional[dict[str, Any]] = None,
        source: str = "<content>",
    ) -> tuple[dict[str, Any], str]:
        """Process Markdown content.

        Args:
            content: Markdown content.
            rewrite_dithered: Rewrite <img> tags to the blog pipeline's
                dithered paths (``<dir>/dithered/<stem>.png``). Only the blog
                pipeline creates those files, so this must be False for
                regular pages — their images would otherwise 404.
            jinja_context: When given AND content Jinja is enabled for this
                file (config default or `jinja:` front matter), the body is
                rendered through Jinja before markdown conversion.
            source: Source path for warnings/errors.

        Returns:
            Tuple of (front_matter, html_content).
        """
        # Extract front matter
        front_matter, content_without_front_matter = self.extract_front_matter(content)

        self._warn_legacy_markers(content_without_front_matter, source)

        # Optional Jinja pass over the raw body
        if jinja_context is not None and self.content_jinja_enabled(front_matter):
            context = dict(jinja_context)
            context.setdefault("page", front_matter)
            content_without_front_matter = self.render_content_jinja(
                content_without_front_matter, context, source
            )

        # Replace image paths from /static/images/ to /images/
        content_without_front_matter = self._replace_image_paths(content_without_front_matter)

        # Convert Markdown to HTML
        html_content = _render_markdown(content_without_front_matter)

        # Process image tags for dithering support
        if self.dithering_enabled and rewrite_dithered:
            logger.debug("Dithering is enabled, processing image tags...")
            html_content = self._process_image_tags(html_content)
            logger.debug(f"After processing images, HTML length: {len(html_content)}")
        else:
            logger.debug("Dithered img rewrite skipped (disabled or non-blog content)")

        return front_matter, html_content

    def _replace_image_paths(self, content: str) -> str:
        """Rewrite /static/images/ references to /images/, where they are served.

        Args:
            content: Markdown content.

        Returns:
            Content with replaced image paths.
        """
        for pattern, replacement in STATIC_IMAGE_REWRITES:
            content = pattern.sub(replacement, content)
        return content

    def _process_image_tags(self, html_content: str) -> str:
        """Wrap post-local images in a dithered figure with caption and toggle button.

        Args:
            html_content: HTML content with image tags.

        Returns:
            HTML content with processed image tags.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        img_tags = soup.find_all("img")
        logger.debug(f"Found {len(img_tags)} image tags to process for dithering")
        # Ids number every <img>, including skipped ones, so they stay stable.
        for index, img in enumerate(img_tags):
            if is_post_local_raster_image(_attribute_text(img, "src")):
                _wrap_in_dither_figure(soup, img, f"img-{index}")
        return str(soup)

    def process_page(
        self, content: str, is_markdown: bool, source_path: str, variables: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Process a content page or blog post: render its body, work out its URL, template it.

        Listing pages without a source file use render_generated_page().

        Args:
            content: Page content.
            is_markdown: Whether the content is Markdown.
            source_path: Path to the source file.
            variables: Variable scopes (``global``, ``site``, ``page``).

        Returns:
            Tuple of (front_matter, processed_content).
        """
        front_matter, html_content = self._render_body(content, is_markdown, source_path, variables)
        front_matter["source_path"] = source_path
        front_matter["url"] = self._page_url(source_path, variables)
        template_name = self._template_name(front_matter, variables, source_path)
        logger.debug(f"Template for {source_path}: {template_name}")
        if template_name:
            page_html = self._render_with_template(
                template_name,
                front_matter,
                html_content,
                variables,
                page_factory=lambda: _with_page_variables(front_matter, variables),
            )
        else:
            page_html = _untemplated_page(front_matter, html_content, self._language())
        return front_matter, self.finish_page(page_html)

    def render_generated_page(
        self,
        template_name: str,
        page: dict[str, Any],
        placeholder_html: str,
        variables: dict[str, Any],
    ) -> str:
        """Render a listing page that has no source file (blog index, taxonomy, archive).

        The caller names the template (config overrides included), and
        ``page`` reaches the template unchanged; its ``url`` is the page URL.

        Args:
            template_name: Template to render, e.g. the configured blog.list_template.
            page: The template's ``page`` variable.
            placeholder_html: Body used as ``content``, and in the fallback page
                when the template is missing.
            variables: Variable scopes (``global``, ``site``).

        Returns:
            The complete page HTML.
        """
        logger.debug(f"Template for generated page {page.get('url')}: {template_name}")
        page_html = self._render_with_template(
            template_name, {}, placeholder_html, variables, page_factory=lambda: page
        )
        return self.finish_page(page_html)

    def _render_body(
        self, content: str, is_markdown: bool, source_path: str, variables: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Split off front matter and render the body (Markdown, content Jinja).

        Regular pages must not have their images rewritten to blog-style
        dithered paths; only the blog pipeline generates those files.
        """
        if is_markdown:
            return self.process_markdown(
                content,
                rewrite_dithered=False,
                jinja_context=self.build_content_context(variables),
                source=str(source_path),
            )
        front_matter, html_content = self.extract_front_matter(content)
        # Blog posts also arrive here (pre-rendered, is_markdown=False, .md
        # source) and must not get a second Jinja pass.
        if _is_html_source_file(source_path):
            self._warn_legacy_markers(html_content, str(source_path))
            if self.content_jinja_enabled(front_matter):
                context = self.build_content_context(variables)
                context.setdefault("page", front_matter)
                html_content = self.render_content_jinja(html_content, context, str(source_path))
        return front_matter, html_content

    def _page_url(self, source_path: str, variables: dict[str, Any]) -> str:
        """Site-relative URL of a page; "/" if it cannot be computed."""
        try:
            return self._compute_page_url(source_path, variables)
        except Exception as e:
            logger.warning(f"Error calculating relative URL for {source_path}: {e}")
            return "/"

    def _compute_page_url(self, source_path: str, variables: dict[str, Any]) -> str:
        page_vars = variables.get("page", {}) if isinstance(variables, dict) else {}
        # Blog posts arrive with their permalink already computed; prefer it
        # over the content-relative path, which is never generated for them.
        if isinstance(page_vars, dict) and page_vars.get("full_url"):
            return page_vars["full_url"]
        if isinstance(source_path, str) and not os.path.exists(source_path):
            # Content rendered without a file on disk: trust the page URL given.
            return page_vars.get("url", "/") if isinstance(page_vars, dict) else "/"
        return self._content_file_url(source_path)

    def _content_file_url(self, source_path: str) -> str:
        """URL for a file under the content directory, styled per ``url_style``."""
        rel_source = PurePath(os.path.relpath(source_path, self.paths.get("content", "")))
        output_path = page_output_path(rel_source, self.config.get_url_style())
        return self.config.format_url(page_url(output_path))

    def _template_name(
        self, front_matter: dict[str, Any], variables: dict[str, Any], source_path: str
    ):
        """Pick the page template: front matter, then page variables, then defaults.

        Page variables carry the template for blog posts, whose rendered
        content has no front matter.
        """
        if "template" in front_matter:
            return front_matter["template"]
        page_template = variables.get("page", {}).get("template")
        if page_template:
            return page_template
        if isinstance(source_path, str):
            return self._default_template_name(source_path)
        return None

    def _default_template_name(self, source_path: str) -> Optional[str]:
        """Default template for a Markdown source: the post template, else page.html."""
        if PurePath(source_path).suffix.lower() not in MARKDOWN_EXTENSIONS:
            return None
        if self._is_blog_post(source_path):
            return self.config.get("blog", "template", default="blog_post.html")
        return "page.html"

    def _is_blog_post(self, source_path: str) -> bool:
        """Whether a source file is a blog post: under the blog directory, blog enabled.

        With the blog off, files in its folder are ordinary pages.
        """
        content_dir = self.paths.get("content")
        if not content_dir or not self.config.get("blog", "enabled", default=True):
            return False
        blog_dir = os.path.join(content_dir, self.config.blog_directory())
        return validate_path_within_root(source_path, blog_dir)

    def _render_with_template(
        self,
        template_name: str,
        front_matter: dict[str, Any],
        html_content: str,
        variables: dict[str, Any],
        page_factory: Callable[[], dict[str, Any]],
    ) -> str:
        """Render the page through its template, falling back to bare HTML on errors.

        Args:
            template_name: Template to render.
            front_matter: Supplies the title of the fallback page.
            html_content: The page body, passed to the template as ``content``.
            variables: Variable scopes (``global``, ``site``).
            page_factory: Builds the template's ``page`` variable; called only
                once the template has been found.
        """
        try:
            template = self.jinja_env.get_template(template_name)
            context = self._template_context(page_factory(), html_content, variables)
            rendered = template.render(**context)
            logger.debug(f"Rendered template {template_name}")
            self._count("templates_rendered")
            return rendered
        except jinja2.TemplateNotFound:
            logger.warning(f"Template not found: {template_name}")
            self._count("template_errors")
            return _untemplated_page(front_matter, html_content, self._language())
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            self._count("template_errors")
            return _error_page(e, html_content, self._language())

    def _language(self) -> str:
        """The site's language for pages Sonne builds itself (site.language, else "en")."""
        language = self.config.get("site", "language", default="en")
        return language if isinstance(language, str) and language else "en"

    def _count(self, counter: str) -> None:
        """Increment a BuildStatistics counter, if statistics are being collected."""
        if self.stats:
            setattr(self.stats, counter, getattr(self.stats, counter) + 1)

    def _template_context(
        self, page: dict[str, Any], html_content: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """The page-template context: global/site variables, ``page`` and ``content``."""
        context = self.build_content_context(variables)
        site_images = self.config.get("images")
        if "images" not in context["site"] and site_images is not None:
            context["site"]["images"] = site_images
        context["page"] = page
        context["content"] = Markup(html_content)
        return context

    def finish_page(self, html_content: str) -> str:
        """Apply dithering to a rendered page, when dithering is enabled.

        Every <img> whose root-relative src the build dithered is pointed at
        the dithered copy, with the original in data-original-src; only those
        images get a toggle from dithering.js. The page is also made to load
        the shared dithering stylesheet and script if it does not already.
        Blog post figures are marked by the blog pipeline and left as they are.

        Args:
            html_content: A complete rendered page.

        Returns:
            The page HTML.
        """
        if not self.dithering_enabled:
            return html_content
        soup = BeautifulSoup(html_content, "html.parser")
        for img in soup.find_all("img"):
            self._mark_if_dithered(img)
        _ensure_stylesheet_link(soup, DITHERING_STYLESHEET_URL)
        _ensure_script(soup, DITHERING_SCRIPT_URL)
        return str(soup)

    def _mark_if_dithered(self, img: Tag) -> None:
        """Point an <img> at its dithered copy and record the original, if dithered."""
        if img.has_attr("data-original-src"):
            return
        src = _attribute_text(img, "src")
        if not src.startswith("/") or src.startswith("//"):
            return
        path, suffix = _split_url_suffix(src)
        pair = self.dithered_images.pair_for(path)
        if pair is None:
            return
        original_url, dithered_url = pair
        img["src"] = dithered_url + suffix
        img["data-original-src"] = original_url + suffix


def _undefined_with_data_hints(
    names_under_data: dict[str, str], hinted: set[str]
) -> type[jinja2.Undefined]:
    """Jinja's Undefined, plus a warning when the missing name moved under `data`.

    A template written for the flat names renders nothing (or fails) once
    data files and script variables are only under `data`; the warning
    names the variable and where it is now. Each name warns once per build.

    Args:
        names_under_data: Bare name -> where it is now; read at render time.
        hinted: Names already warned about.
    """

    class UndefinedWithDataHint(jinja2.Undefined):
        __slots__ = ()

        def _hint(self) -> None:
            name = self._undefined_name
            if not isinstance(name, str) or name in hinted or name not in names_under_data:
                return
            # A top-level name, or site.<name>; not some other object's attribute.
            owner = self._undefined_obj
            if owner is not jinja2.utils.missing and not _is_site_scope(owner):
                return
            hinted.add(name)
            logger.warning(
                f"Template variable '{name}' is not defined: data files and script "
                f"variables are under `data` now. Use {{{{ {names_under_data[name]} }}}}, or "
                "set variables.flatten_data: true to keep the old names for now."
            )

        def _fail_with_undefined_error(self, *args: Any, **kwargs: Any) -> NoReturn:
            self._hint()
            return super()._fail_with_undefined_error(*args, **kwargs)

        def __str__(self) -> str:
            self._hint()
            return super().__str__()

        def __iter__(self) -> Iterator[Any]:
            self._hint()
            return super().__iter__()

        def __bool__(self) -> bool:
            self._hint()
            return super().__bool__()

    return UndefinedWithDataHint


def _is_site_scope(value: Any) -> bool:
    """Whether value is the `site` variable templates get (it carries Sonne's generator keys)."""
    return isinstance(value, dict) and "generator_version" in value


def _ensure_head(soup: BeautifulSoup) -> Tag:
    """Return the document's <head>, creating it as the first child of <html>."""
    head = soup.head
    if head is None:
        head = soup.new_tag("head")
        _html_root(soup).insert(0, head)
    return head


def _ensure_body(soup: BeautifulSoup) -> Tag:
    """Return the document's <body>, creating it as the last child of <html>."""
    body = soup.body
    if body is None:
        body = soup.new_tag("body")
        _html_root(soup).append(body)
    return body


def _html_root(soup: BeautifulSoup) -> Tag:
    """Return the <html> element, appending one to fragment documents."""
    html = soup.html
    if html is None:
        html = soup.new_tag("html")
        soup.append(html)
    return html


def _ensure_stylesheet_link(soup: BeautifulSoup, href: str) -> None:
    """Add <link rel="stylesheet" href=...> to <head> unless a link to it is present."""
    for link in soup.find_all("link"):
        if _attribute_text(link, "href") == href:
            return
    _ensure_head(soup).append(soup.new_tag("link", attrs={"rel": "stylesheet", "href": href}))


def _ensure_script(soup: BeautifulSoup, src: str) -> None:
    """Add <script src=... defer> to <body> unless a script with that src is present."""
    for script in soup.find_all("script"):
        if _attribute_text(script, "src") == src:
            return
    _ensure_body(soup).append(soup.new_tag("script", attrs={"src": src, "defer": ""}))


def _split_url_suffix(url: str) -> tuple[str, str]:
    """``/a.png?v=2#x`` -> (``/a.png``, ``?v=2#x``)."""
    split = re.search(r"[?#]", url)
    return (url[: split.start()], url[split.start() :]) if split else (url, "")


def _format_date(value, fmt="%B %d, %Y") -> str:
    """Jinja ``date`` filter."""
    return value.strftime(fmt)


def _render_markdown(text: str) -> str:
    """Convert Markdown to HTML with Sonne's extension set."""
    return markdown.markdown(text, extensions=MARKDOWN_PARSER_EXTENSIONS)


def _word_count(text: str) -> int:
    """Jinja ``word_count`` filter."""
    return len(text.split())


def _truncate_words(text: str, length: int = 30) -> str:
    """Jinja ``truncate_words`` filter: first ``length`` words, "..." if cut."""
    words = text.split()
    return " ".join(words[:length]) + ("..." if len(words) > length else "")


def _is_html_source_file(source_path) -> bool:
    """Whether a page comes from an existing .html/.htm file under content."""
    return (
        isinstance(source_path, str)
        and source_path.lower().endswith((".html", ".htm"))
        and os.path.exists(source_path)
    )


def _with_page_variables(front_matter: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
    """A content page's ``page``: its front matter, filled in from the page variables.

    Fills the front matter in place, so the caller's front matter matches
    what the template saw.
    """
    for key, value in variables.get("page", {}).items():
        front_matter.setdefault(key, value)
    return front_matter


def _untemplated_page(front_matter: dict[str, Any], html_content: str, language: str) -> str:
    """Minimal page used when no template applies or the template is missing."""
    title = str(front_matter.get("title", "Untitled"))
    return _minimal_page(title, Markup(html_content), language)


def _error_page(error: Exception, html_content: str, language: str) -> str:
    """Minimal page used when rendering the template failed."""
    body = Markup("<p>{}</p><div>{}</div>").format(str(error), Markup(html_content))
    return _minimal_page("Error rendering template", body, language)


def _minimal_page(title: str, body: Markup, language: str) -> str:
    """A complete, valid page: language, title and a main landmark (title escaped)."""
    return MINIMAL_PAGE.format(language=language, title=title, body=body)


def _template_exists(env: jinja2.Environment, name: str) -> bool:
    """Whether the loader can find a template, without compiling it."""
    if env.loader is None:
        return False
    try:
        env.loader.get_source(env, name)
    except jinja2.TemplateNotFound:
        return False
    return True


def _template_names(templates_dir: str) -> list[str]:
    """Jinja names (always "/"-separated) of every template file under a directory."""
    names = []
    for root, _dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith(TEMPLATE_EXTENSIONS):
                rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                names.append(rel_path.replace(os.sep, "/"))
    return names


def _attribute_text(tag: Tag, name: str) -> str:
    """A single-valued attribute's text ("" when absent)."""
    value = tag.get(name)
    return value if isinstance(value, str) else ""


def _dithered_src(src: str) -> str:
    """Blog-pipeline dithered path of an image: ``<dir>/dithered/<stem>.png``."""
    *dir_parts, filename = src.split("/")
    stem = filename.rsplit(".", 1)[0]
    return "/".join([*dir_parts, "dithered", stem + ".png"])


def _wrap_in_dither_figure(soup: BeautifulSoup, img, image_id: str) -> None:
    """Replace ``img`` in the tree with a figure showing its dithered variant."""
    original_src = img.get("src", "")
    dithered_src = _dithered_src(original_src)
    figcaption = _dither_figcaption(soup, img)
    toggle = _toggle_button(soup, image_id, img.get("data-original-size", ""))

    img["class"] = "dithered-image active"
    img["data-dithered-src"] = dithered_src
    img["data-original-src"] = original_src
    img["data-image-id"] = image_id
    img["loading"] = img.get("loading", "lazy")
    img["src"] = dithered_src

    figure = soup.new_tag("figure", attrs={"class": "dithered-image-figure"})
    figure["data-image-id"] = image_id
    img_wrapper = soup.new_tag("div", attrs={"class": "image-wrapper"})
    # Anchor the figure at the img's position while the img is still in the
    # tree, then move the img inside it.
    img.insert_before(figure)
    img_wrapper.append(img.extract())
    img_wrapper.append(toggle)
    figure.append(img_wrapper)
    if figcaption is not None:
        figure.append(figcaption)


def _dither_figcaption(soup: BeautifulSoup, img) -> Optional[Tag]:
    """The figure's caption ("title · 12k (−80%)"), or None if there is no text for one.

    The <figcaption> holds only the caption, so it is the figure's accessible
    name; the toggle button sits with the image instead.
    """
    caption_text = _caption_text(img)
    if not caption_text:
        return None
    figcaption = soup.new_tag("figcaption")
    span = soup.new_tag("span", attrs={"class": "caption-text"})
    span.string = caption_text
    figcaption.append(span)
    return figcaption


def _caption_text(img) -> str:
    """Caption from the title (or alt), with the size saving when known.

    Titles may carry transform directives after a pipe
    ("Display title | crop=16:9 rotate=90"); only the display part is shown.
    """
    title = img.get("title", "")
    display_title = title.split("|")[0].strip() if title and "|" in title else title
    label = display_title or img.get("alt", "")
    dithered_size = img.get("data-dithered-size", "")
    size_reduction = img.get("data-size-reduction", "")
    if label and dithered_size and size_reduction:
        return f"{label} · {dithered_size} (−{size_reduction}%)"
    return label


def _toggle_button(soup: BeautifulSoup, image_id: str, original_size: str):
    """Button that swaps between the dithered and the original image.

    Its accessible name is its visible text ("view original", then
    "dithered (12KB)"), which names what a press shows (WCAG 2.5.3).
    """
    button = soup.new_tag("button", attrs={"class": "request-original-btn", "type": "button"})
    button["data-image-id"] = image_id
    if original_size:
        button["data-original-size"] = original_size
    button.append(_dither_icon(soup))
    label = soup.new_tag("span", attrs={"class": "btn-text"})
    label.string = "view original"
    button.append(label)
    return button


def _dither_icon(soup: BeautifulSoup):
    """Inline SVG of the quincunx dither pattern (4 corners + center)."""
    icon = soup.new_tag(
        "svg",
        attrs={
            "class": "dither-icon-svg",
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": "0 0 100 100",
            "aria-hidden": "true",
        },
    )
    for x, y in DITHER_ICON_CELLS:
        cell = {
            "x": x,
            "y": y,
            "width": DITHER_ICON_CELL_SIZE,
            "height": DITHER_ICON_CELL_SIZE,
            "fill": "currentColor",
        }
        icon.append(soup.new_tag("rect", attrs=cell))
    return icon
