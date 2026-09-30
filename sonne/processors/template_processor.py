"""
Template processing for Sonne.
Handles rendering templates, processing Markdown, and extracting front matter.
"""

import json
import logging
import os
import re
from pathlib import PurePath
from typing import Any, Dict, List, Optional, Tuple

import jinja2
import markdown
import yaml
from bs4 import BeautifulSoup
from jinja2 import TemplateSyntaxError, UndefinedError
from markupsafe import Markup

from sonne.utils.constants import MARKDOWN_EXTENSIONS
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

# (source-key prefix, taxonomy, template config key, default template)
TAXONOMY_PAGE_TEMPLATES = [
    ("tags_", "tags", "list_template", "tags.html"),
    ("tag_", "tags", "template", "tag.html"),
    ("categories_", "categories", "list_template", "categories.html"),
    ("category_", "categories", "template", "category.html"),
]
GENERATED_PAGE_PREFIXES = tuple(prefix for prefix, *_ in TAXONOMY_PAGE_TEMPLATES)

TEMPLATE_EXTENSIONS = (".html", ".htm", ".xml", ".txt", ".j2", ".jinja2")


def _load_yaml_front_matter(text: str) -> Dict[str, Any]:
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
NON_DITHERABLE_SRC_PREFIXES = ("http://", "https://", "data:", "/")

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

BUILTIN_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

# Markers identify Sonne's injected assets so they are never added twice.
DITHER_CSS_MARKER = "Dithered image styling - injected by Sonne"
DITHER_JS_MARKER = "Dithered image functionality - injected by Sonne"

DITHER_CSS = """
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
    /* currentColor fallback: the button inherits the page's text color when
       the theme doesn't define --text-color (a #fff fallback made the button
       invisible on light themes) */
    border: 1px solid var(--text-color, currentColor);
    border-radius: 0.4em;
    cursor: pointer;
    color: var(--text-color, currentColor);
    opacity: 0.5;
    transition: opacity 0.1s, background-color 0.1s;
    font-family: inherit;
}

.request-original-btn:hover {
    opacity: 1;
    background-color: var(--bg-hover, rgba(128,128,128,0.15));
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

DITHER_JS = """
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
        self.dithering_enabled = self.config.get("images", "dither", default=True)
        logger.info(f"Dithering enabled: {self.dithering_enabled}")
        self.jinja_env = self._create_jinja_env()
        # Per instance, so every build (including `sonne serve` rebuilds)
        # warns once per file.
        self._legacy_marker_warned = set()

    def _create_jinja_env(self) -> jinja2.Environment:
        """Create the Jinja environment: site templates first, then built-ins."""
        template_dirs = [
            directory
            for directory in (self.paths.get("templates"), BUILTIN_TEMPLATES_DIR)
            if directory and os.path.exists(directory)
        ]
        logger.info(f"Template directories: {template_dirs}")
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dirs),
            autoescape=jinja2.select_autoescape(["html", "xml"]),
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
        logger.info("Jinja environment initialized successfully")
        return env

    def _image_markup(self, src, alt="Image", loading="lazy"):
        """Jinja ``process_image`` filter: an <img>, or a dithered/original pair.

        Args:
            src: Image source URL (a sized variant such as ``x_400.webp`` or a
                plain static image).
            alt: Image alt text.
            loading: Loading attribute value.

        Returns:
            HTML for the image, with the dithering toggle when dithering is enabled.
        """
        if not self.dithering_enabled:
            return f'<img src="{src}" alt="{alt}" loading="{loading}">'
        original_src = _original_image_src(src)
        return Markup(f"""
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
            """)

    def validate_templates(self) -> List[str]:
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
            return f"{template_name}: {str(e)}"
        try:
            template.render(site={}, page={}, content="")
        except UndefinedError as e:
            logger.debug(f"{template_name}: undefined variable with empty context ({e})")
        except Exception as e:
            return f"{template_name}: Render error - {str(e)}"
        return None

    def extract_front_matter(self, content: str) -> Tuple[Dict[str, Any], str]:
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

    def register_extensions(self, filters: Dict[str, Any], globals_: Dict[str, Any]) -> None:
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

    def render_content_jinja(self, content: str, context: Dict[str, Any], source: str) -> str:
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

    def build_content_context(self, variables: Dict[str, Any]) -> Dict[str, Any]:
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

    def content_jinja_enabled(self, front_matter: Dict[str, Any]) -> bool:
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
        jinja_context: Dict[str, Any] = None,
        source: str = "<content>",
    ) -> Tuple[Dict[str, Any], str]:
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
            if _has_dithered_variant(img.get("src", "")):
                _wrap_in_dither_figure(soup, img, f"img-{index}")
        return str(soup)

    def process_page(
        self, content: str, is_markdown: bool, source_path: str, variables: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
        """Process a page: render its body, work out its URL, wrap it in a template.

        Args:
            content: Page content.
            is_markdown: Whether the content is Markdown.
            source_path: Path to the source file, or a generated-page key such
                as ``blog_index`` or ``tag_<slug>``.
            variables: Variable scopes (``global``, ``site``, ``page``).

        Returns:
            Tuple of (front_matter, processed_content).
        """
        front_matter, html_content = self._render_body(content, is_markdown, source_path, variables)
        front_matter["source_path"] = source_path
        front_matter["url"] = self._page_url(source_path, is_markdown, variables)
        template_name = self._template_name(front_matter, variables, source_path)
        logger.debug(f"Template for {source_path}: {template_name}")
        if template_name:
            page_html = self._render_with_template(
                template_name, front_matter, html_content, source_path, variables
            )
        else:
            page_html = _untemplated_page(front_matter, html_content)
        return front_matter, self.inject_dithering_assets(page_html)

    def _render_body(
        self, content: str, is_markdown: bool, source_path: str, variables: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
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

    def _page_url(self, source_path: str, is_markdown: bool, variables: Dict[str, Any]) -> str:
        """Site-relative URL of a page; "/" if it cannot be computed."""
        try:
            return self._compute_page_url(source_path, is_markdown, variables)
        except Exception as e:
            logger.warning(f"Error calculating relative URL for {source_path}: {e}")
            return "/"

    def _compute_page_url(
        self, source_path: str, is_markdown: bool, variables: Dict[str, Any]
    ) -> str:
        page_vars = variables.get("page", {}) if isinstance(variables, dict) else {}
        # Blog posts arrive with their permalink already computed; prefer it
        # over the content-relative path, which is never generated for them.
        if isinstance(page_vars, dict) and page_vars.get("full_url"):
            return page_vars["full_url"]
        if isinstance(source_path, str) and not os.path.exists(source_path):
            # Generated pages (blog_index, tag_<slug>, ...) have no file.
            return page_vars.get("url", "/") if isinstance(page_vars, dict) else "/"
        return self._content_file_url(source_path, is_markdown)

    def _content_file_url(self, source_path: str, is_markdown: bool) -> str:
        """URL for a file under the content directory, styled per ``url_style``."""
        rel_path = PurePath(os.path.relpath(source_path, self.paths.get("content", "")))
        if is_markdown and rel_path.suffix.lower() in MARKDOWN_EXTENSIONS:
            rel_path = rel_path.with_suffix("")
        url = "/" + rel_path.as_posix()
        if hasattr(self.config, "format_url"):
            formatted = self.config.format_url(url)
            logger.debug(f"Formatted URL: {url} -> {formatted}")
            url = formatted
        return url

    def _template_name(
        self, front_matter: Dict[str, Any], variables: Dict[str, Any], source_path: str
    ):
        """Pick the page template: front matter, then page variables, then defaults.

        Page variables carry the template for generated pages (e.g. date
        archives) whose front matter is empty.
        """
        if "template" in front_matter:
            return front_matter["template"]
        page_template = variables.get("page", {}).get("template")
        if page_template:
            return page_template
        if isinstance(source_path, str):
            return self._default_template_name(source_path)
        return None

    def _default_template_name(self, source_path: str):
        """Default template for a Markdown source or a generated-page key."""
        if source_path.endswith(".md"):
            if "/blog/" in source_path:
                return self.config.get("blog", "template", default="blog_post.html")
            return "page.html"
        if source_path == "blog_index":
            return self.config.get("blog", "list_template", default="blog_list.html")
        for prefix, taxonomy, template_key, default in TAXONOMY_PAGE_TEMPLATES:
            if source_path.startswith(prefix):
                taxonomy_config = self.config.get("blog", "taxonomies", taxonomy, default={})
                return taxonomy_config.get(template_key, default)
        return None

    def _render_with_template(
        self,
        template_name: str,
        front_matter: Dict[str, Any],
        html_content: str,
        source_path: str,
        variables: Dict[str, Any],
    ) -> str:
        """Render the page through its template, falling back to bare HTML on errors."""
        try:
            template = self.jinja_env.get_template(template_name)
            context = self._template_context(front_matter, html_content, source_path, variables)
            rendered = template.render(**context)
            logger.debug(f"Rendered template {template_name} for {source_path}")
            return rendered
        except jinja2.TemplateNotFound:
            logger.warning(f"Template not found: {template_name}")
            return _untemplated_page(front_matter, html_content)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            return _error_page(e, html_content)

    def _template_context(
        self,
        front_matter: Dict[str, Any],
        html_content: str,
        source_path: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build the page-template context.

        For regular pages the front matter becomes ``page``, filled in (in
        place, so the caller's front matter matches what the template saw)
        with page variables it does not set. Generated pages use the page
        variables as-is.
        """
        context = self.build_content_context(variables)
        site_images = self.config.get("images")
        if "images" not in context["site"] and site_images is not None:
            context["site"]["images"] = site_images
        if _is_generated_page(source_path):
            context["page"] = variables.get("page", {})
        else:
            for key, value in variables.get("page", {}).items():
                front_matter.setdefault(key, value)
            context["page"] = front_matter
        context["content"] = Markup(html_content)
        return context

    def inject_dithering_assets(self, html_content: str) -> str:
        """Inject dithering CSS and JS inline into HTML content if dithering is enabled.

        Each asset is added at most once, so re-injecting is harmless.

        Args:
            html_content: HTML content to inject into.

        Returns:
            HTML content with dithering assets injected.
        """
        if not self.dithering_enabled:
            return html_content

        soup = BeautifulSoup(html_content, "html.parser")
        _append_once(soup, _ensure_head(soup), "style", DITHER_CSS, DITHER_CSS_MARKER)
        _append_once(soup, _ensure_body(soup), "script", DITHER_JS, DITHER_JS_MARKER)
        return str(soup)


def _ensure_head(soup: BeautifulSoup):
    """Return the document's <head>, creating it as the first child of <html>."""
    if not soup.head:
        _html_root(soup).insert(0, soup.new_tag("head"))
    return soup.head


def _ensure_body(soup: BeautifulSoup):
    """Return the document's <body>, creating it as the last child of <html>."""
    if not soup.body:
        _html_root(soup).append(soup.new_tag("body"))
    return soup.body


def _html_root(soup: BeautifulSoup):
    """Return the <html> element, appending one to fragment documents."""
    if not soup.html:
        soup.append(soup.new_tag("html"))
    return soup.html


def _append_once(soup: BeautifulSoup, parent, tag_name: str, text: str, marker: str) -> None:
    """Append an inline <style>/<script> unless one carrying ``marker`` is already there."""
    for existing in parent.find_all(tag_name):
        if existing.string and marker in existing.string:
            return
    tag = soup.new_tag(tag_name)
    tag.string = text
    parent.append(tag)


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


def _original_image_src(src: str) -> str:
    """Map a displayed image URL to its undithered original.

    Sized variants (``x_400.webp``) become ``x_400_original.webp``; other
    images get ``_original`` before the extension.
    """
    size_match = re.search(r"_(\d+)\.", src)
    if size_match:
        size = size_match.group(1)
        return src.replace(f"_{size}.", f"_{size}_original.")
    filename, ext = os.path.splitext(src)
    return f"{filename}_original{ext}"


def _is_html_source_file(source_path) -> bool:
    """Whether a page comes from an existing .html/.htm file under content."""
    return (
        isinstance(source_path, str)
        and source_path.lower().endswith((".html", ".htm"))
        and os.path.exists(source_path)
    )


def _is_generated_page(source_path) -> bool:
    """Whether a source key names a generated blog index or taxonomy page."""
    return isinstance(source_path, str) and (
        source_path == "blog_index" or source_path.startswith(GENERATED_PAGE_PREFIXES)
    )


def _untemplated_page(front_matter: Dict[str, Any], html_content: str) -> str:
    """Minimal page used when no template applies or the template is missing."""
    title = front_matter.get("title", "Untitled")
    return f"<html><body><h1>{title}</h1>{html_content}</body></html>"


def _error_page(error: Exception, html_content: str) -> str:
    """Minimal page used when rendering the template failed."""
    return (
        "<html><body><h1>Error rendering template</h1>"
        f"<p>{error}</p><div>{html_content}</div></body></html>"
    )


def _template_names(templates_dir: str) -> List[str]:
    """Jinja names (always "/"-separated) of every template file under a directory."""
    names = []
    for root, _dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith(TEMPLATE_EXTENSIONS):
                rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                names.append(rel_path.replace(os.sep, "/"))
    return names


def _has_dithered_variant(src: str) -> bool:
    """Whether the blog pipeline generates a dithered copy of this image."""
    return not (src.endswith(".svg") or src.startswith(NON_DITHERABLE_SRC_PREFIXES))


def _dithered_src(src: str) -> str:
    """Blog-pipeline dithered path of an image: ``<dir>/dithered/<stem>.png``."""
    *dir_parts, filename = src.split("/")
    stem = filename.rsplit(".", 1)[0]
    return "/".join(dir_parts + ["dithered", stem + ".png"])


def _wrap_in_dither_figure(soup: BeautifulSoup, img, image_id: str) -> None:
    """Replace ``img`` in the tree with a figure showing its dithered variant."""
    original_src = img.get("src", "")
    dithered_src = _dithered_src(original_src)
    figcaption = _dither_figcaption(soup, img, image_id)

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
    figure.append(img_wrapper)
    figure.append(figcaption)


def _dither_figcaption(soup: BeautifulSoup, img, image_id: str):
    """Caption ("title · 12k (−80%)") plus the dithered/original toggle button."""
    figcaption = soup.new_tag("figcaption")
    caption_text = _caption_text(img)
    if caption_text:
        span = soup.new_tag("span", attrs={"class": "caption-text"})
        span.string = caption_text
        figcaption.append(span)
    figcaption.append(_toggle_button(soup, image_id, img.get("data-original-size", "")))
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
    """Button that swaps between the dithered and the original image."""
    button = soup.new_tag("button", attrs={"class": "request-original-btn"})
    button["data-image-id"] = image_id
    button["aria-label"] = "Toggle between dithered and original image"
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
