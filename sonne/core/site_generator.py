"""
Core site generation functionality for Sonne.
Coordinates the various processing steps to generate a complete static site.
"""

import logging
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from sonne.core.config import DEFAULT_CONFIG, Config
from sonne.core.variable_manager import VariableManager
from sonne.processors.blog_processor import BlogProcessor
from sonne.processors.image_processor import ImageProcessor
from sonne.processors.template_processor import TemplateProcessor
from sonne.utils.a11y_check import (
    AccessibilityCheckFailed,
    AccessibilityReport,
    check_output_dir,
)
from sonne.utils.build_stats import BuildStatistics
from sonne.utils.constants import MARKDOWN_EXTENSIONS, PAGE_EXTENSIONS
from sonne.utils.file_utils import (
    copy_core_static_files,
    copy_static_files,
    copy_template_static_files,
    ensure_dir,
)
from sonne.utils.page_location import page_output_path, page_url
from sonne.utils.page_size import inject_page_size_labels
from sonne.utils.path_utils import sorted_paths, validate_path_within_root

logger = logging.getLogger("sonne")

# Steps every build runs: data scripts, static copy, pages, finalize.
# Accessibility report size: pages listed, and findings shown per page.
MAX_A11Y_PAGES_REPORTED = 10
MAX_A11Y_FINDINGS_PER_PAGE = 5

ALWAYS_RUN_STEP_COUNT = 5
BLOG_STEP_COUNT = 2  # collect metadata + render posts
IMAGE_STEP_COUNT = 1


class SiteGenerator:
    """Main site generation coordinator."""

    def __init__(self, config: Config, base_dir: Optional[str] = None):
        """Initialize site generator with configuration.

        Args:
            config: Site configuration.
            base_dir: Base directory for the site. Defaults to current directory.
        """
        self.config = config
        self.base_dir = os.path.abspath(base_dir or os.getcwd())

        self._fill_missing_paths()
        self.paths = self.config.normalize_paths(self.base_dir)

        logger.debug(f"URL style: {self.config.get_url_style()}")
        logger.debug(f"Paths: {self.paths}")

        self.variable_manager = VariableManager(config, self.base_dir)
        self.template_processor = TemplateProcessor(config, self.paths)
        self.image_processor = ImageProcessor(config, self.paths)
        # Pages point <img> tags at the dithered copies the image pipeline made.
        self.template_processor.dithered_images = self.image_processor.dithered_images
        self.blog_processor = BlogProcessor(
            config, self.paths, self.template_processor, self.variable_manager, self.image_processor
        )

        # Build statistics (shared across all processors)
        self.stats = BuildStatistics()
        # Per-build state, reset by each generate().
        self._progress = _StepProgress(0)
        # Which source file produced each output file, so collisions
        # (about.md vs about/index.md) warn instead of silently
        # last-writer-winning.
        self._written_outputs: dict[str, str] = {}
        # Result of the last build's accessibility check (None when off).
        self.accessibility_report: Optional[AccessibilityReport] = None

    def _fill_missing_paths(self) -> None:
        """Give every standard path key its default when unset or empty."""
        for key, default in DEFAULT_CONFIG["paths"].items():
            if not self.config.get("paths", key):
                self.config.set("paths", key, value=default)

    def clean_output(self) -> None:
        """Clean the output directory by removing all files."""
        output_dir = self.paths.get("output")
        if not output_dir or not os.path.exists(output_dir):
            logger.warning(f"Output directory does not exist, nothing to clean: {output_dir}")
            return

        failed_items = []
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            try:
                _remove_path(item_path)
            except Exception as e:
                logger.error(f"Could not clean {item_path}: {type(e).__name__}: {e}")
                failed_items.append(item)

        if failed_items:
            logger.warning(f"Failed to clean {len(failed_items)} items: {', '.join(failed_items)}")
        else:
            logger.info(f"Successfully cleaned output directory: {output_dir}")

    def generate(
        self, skip_images: bool = False, skip_cache: bool = False, show_progress: bool = True
    ) -> BuildStatistics:
        """Generate the complete static site.

        Args:
            skip_images: Whether to skip image processing.
            skip_cache: Whether to ignore cache and rebuild everything.
            show_progress: Log the "[n/N] step" lines at INFO; when False they
                are logged at DEBUG only (``sonne build --no-progress``).

        Returns:
            BuildStatistics with timing and metrics for this build.

        Raises:
            Exception: Whatever a build phase raised, after logging it.
        """
        self._start_statistics()
        try:
            self._run_build(skip_images, skip_cache, show_progress)
        except Exception as e:
            self.stats.finish()
            logger.error(f"Error generating site: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
            raise
        self.stats.finish()
        logger.info("Site generation complete")
        return self.stats

    def _start_statistics(self) -> None:
        """Start a fresh BuildStatistics and share it with the processors."""
        self.stats = BuildStatistics()
        self.image_processor.stats = self.stats
        self.template_processor.stats = self.stats
        self.blog_processor.stats = self.stats
        self.variable_manager.stats = self.stats

    def _run_build(self, skip_images: bool, skip_cache: bool, show_progress: bool) -> None:
        ensure_dir(self.paths["output"])
        blog_enabled = self.config.get("blog", "enabled", default=True)
        self._progress = _StepProgress(
            _count_build_steps(blog_enabled, skip_images), visible=show_progress
        )

        self._written_outputs = {}
        self.accessibility_report = None

        # Post and page metadata come first so data scripts can reference them.
        if blog_enabled:
            self._collect_post_metadata()
        page_files = self._page_files()
        self._collect_page_metadata(page_files)
        self._run_data_scripts()
        self._copy_static_files(skip_images)
        if not skip_images:
            self._process_images(skip_cache)
        if blog_enabled:
            self._render_posts()
        self._render_pages(page_files)
        self._finalize()

    @contextmanager
    def _timed_phase(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            # A failed phase still reports how long it ran.
            self.stats.record_phase(name, time.perf_counter() - started)

    def _collect_post_metadata(self) -> None:
        self._progress.step("Collecting post metadata")
        self.blog_processor.collect_post_metadata()
        self._progress.detail(f"{_count(len(self.blog_processor.posts), 'post')} found")

    def _collect_page_metadata(self, page_files: list[Path]) -> None:
        """Expose every content page to templates and scripts as ``all_pages``."""
        self._progress.step("Collecting page metadata")
        pages = [page for page in map(self._page_entry, page_files) if page is not None]
        pages.sort(key=lambda page: page["url"])
        self.variable_manager.set("all_pages", pages, "global")
        self._progress.detail(f"{_count(len(pages), 'page')} found")

    def _page_entry(self, file_path: Path) -> Optional[dict[str, Any]]:
        """A page's front matter plus its title, url, section and source path.

        The title defaults to the file name, or the folder name for an index
        page. The section is the page's top-level folder under content/
        ("" for pages at the root). None if the page can't be read.
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                front_matter, _body = self.template_processor.extract_front_matter(f.read())
        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error reading page metadata from {file_path}: {e}")
            return None
        rel_source = file_path.relative_to(self.paths["content"])
        output_path = page_output_path(rel_source, self.config.get_url_style())
        default_title = rel_source.parent.name if rel_source.stem == "index" else rel_source.stem
        return {
            **front_matter,
            "title": front_matter.get("title") or default_title,
            "url": self.config.format_url(page_url(output_path)),
            "section": rel_source.parts[0] if len(rel_source.parts) > 1 else "",
            "source_path": str(file_path),
        }

    def _run_data_scripts(self) -> None:
        script_count = len(self.variable_manager.data_script_paths())
        self._progress.step(f"Running data scripts  ({_count(script_count, 'script')})")
        with self._timed_phase("scripts"):
            self.variable_manager.load_variables()
            # Hand script-registered Jinja filters/globals to the renderer
            self.template_processor.register_extensions(
                self.variable_manager.custom_filters,
                self.variable_manager.custom_globals,
            )
        variables = self.variable_manager.variables
        logger.debug(f"Global variables: {list(variables.get('global', {}).keys())}")
        logger.debug(f"Site variables: {list(variables.get('site', {}).keys())}")

    def _copy_static_files(self, skip_images: bool) -> None:
        static_dir = self.paths.get("static")
        output_dir = self.paths["output"]
        # Files the image step will write (dithered static/images) must not
        # be overwritten with their raw sources first; with --skip-images
        # nothing writes them, so they are copied raw.
        skip = None if skip_images else self.image_processor.owns_static_file
        self._progress.step("Copying static files")
        with self._timed_phase("static_copy"):
            copy_static_files(static_dir, output_dir, skip=skip)
            # Dithering CSS/JS ship with the package (single source of
            # truth) and are only emitted — always refreshed — when
            # dithering is enabled.
            if self.config.get("images", "dither", default=True):
                copy_core_static_files(output_dir)
            if not static_dir or not os.path.exists(static_dir):
                copy_template_static_files(self.base_dir, output_dir)

    def _process_images(self, skip_cache: bool) -> None:
        content_dir = self.paths.get("content", "")
        image_count = _count(len(self.image_processor.images_to_process(content_dir)), "image")
        self._progress.step(
            f"Processing images  ({image_count}, {self.image_processor.worker_count()} workers)"
        )
        with self._timed_phase("images"):
            self.image_processor.process_all(content_dir, skip_cache=skip_cache)

    def _render_posts(self) -> None:
        post_count = _count(len(self.blog_processor.posts), "post")
        self._progress.step(f"Rendering blog posts  ({post_count})")
        with self._timed_phase("blog"):
            self.blog_processor.process_all_posts()

    def _render_pages(self, page_files: list[Path]) -> None:
        self._progress.step(f"Rendering pages  ({_count(len(page_files), 'page')})")
        with self._timed_phase("pages"):
            for file_path in page_files:
                self._process_page_logging_errors(file_path)

    def _finalize(self) -> None:
        self._progress.step("Finalizing output")
        with self._timed_phase("finalize"):
            self.variable_manager.save()
            if self.config.get("build", "show_page_size", default=False):
                inject_page_size_labels(self.paths["output"])
            self._check_accessibility()

    def _check_accessibility(self) -> None:
        """Check every written page for machine-detectable WCAG failures.

        Raises:
            AccessibilityCheckFailed: With build.accessibility_checks: error,
                after reporting, if any non-advisory issue was found.
        """
        mode = self.config.accessibility_check_mode()
        if mode == "off":
            return
        report = check_output_dir(self.paths["output"])
        self.accessibility_report = report
        _log_accessibility_report(report)
        if mode == "error" and report.blocking_count:
            raise AccessibilityCheckFailed(
                f"{report.blocking_count} accessibility issues found "
                "(build.accessibility_checks: error); see the report above"
            )

    def _page_files(self) -> list[Path]:
        """Content pages to render: page-type files outside the blog directory.

        Hidden files and anything in hidden folders (.obsidian/, .git/) are
        skipped, as are directories whose names end in a page extension.
        """
        content_dir = self.paths.get("content")
        if not content_dir or not os.path.exists(content_dir):
            logger.warning(f"Content directory does not exist: {content_dir}")
            return []

        content_root = Path(content_dir)
        # With the blog off, its folder holds ordinary pages.
        blog_dir = None
        if self.config.get("blog", "enabled", default=True):
            blog_dir = Path(content_dir, self.config.blog_directory()).resolve()
        return [
            file_path
            for file_path in sorted_paths(content_root.glob("**/*.*"))
            if file_path.suffix.lower() in PAGE_EXTENSIONS
            and file_path.is_file()
            and not _is_hidden_within(file_path, content_root)
            and not (blog_dir and validate_path_within_root(file_path, blog_dir))
        ]

    def _process_page_logging_errors(self, file_path: Path) -> None:
        try:
            self._process_page(file_path)
        except Exception as e:
            logger.error(
                f"Error processing page {file_path}: {e}",
                exc_info=logger.isEnabledFor(logging.DEBUG),
            )

    def _process_page(self, file_path: Path) -> None:
        """Render one content page and write it to its output path.

        Args:
            file_path: Path to the page file.
        """
        output_path = self._output_path_for(file_path)
        ensure_dir(output_path.parent)

        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        is_markdown = file_path.suffix.lower() in MARKDOWN_EXTENSIONS
        _front_matter, processed_content = self.template_processor.process_page(
            content, is_markdown, str(file_path), self.variable_manager.render_scopes()
        )

        self._record_output(output_path, file_path)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(processed_content)

        self.stats.pages_processed += 1
        logger.debug(f"Processed page: {file_path} -> {output_path}")

    def _output_path_for(self, file_path: Path) -> Path:
        """Where a content page is written, according to the URL style."""
        rel_source = file_path.relative_to(self.paths["content"])
        output_path = Path(self.paths["output"]) / page_output_path(
            rel_source, self.config.get_url_style()
        )
        logger.debug(f"Output path for {file_path}: {output_path}")
        return output_path

    def _record_output(self, output_path: Path, file_path: Path) -> None:
        """Remember which source wrote output_path; warn when two collide (the later wins)."""
        written = self._written_outputs
        out_key = str(output_path)
        prior_source = written.get(out_key)
        if prior_source and prior_source != str(file_path):
            logger.warning(
                f"Page outputs collide: '{file_path}' and '{prior_source}' "
                f"both write to {output_path} — the later file wins"
            )
        written[out_key] = str(file_path)


class _StepProgress:
    """Numbered "[step/total] message" progress lines for one build.

    Hidden progress (--no-progress) is still logged, at DEBUG, so -v shows it.
    """

    def __init__(self, total_steps: int, visible: bool = True):
        self.total_steps = total_steps
        self.current_step = 0
        self.level = logging.INFO if visible else logging.DEBUG

    def step(self, message: str) -> None:
        self.current_step += 1
        logger.log(self.level, f"[{self.current_step}/{self.total_steps}] {message}")

    def detail(self, message: str) -> None:
        """An indented line under the current step."""
        logger.log(self.level, f"         {message}")


def _log_accessibility_report(report: AccessibilityReport) -> None:
    """Findings grouped per page, capped so a large site stays readable."""
    if not report.issue_count:
        logger.info(report.summary())
        return
    for page, findings in list(report.pages.items())[:MAX_A11Y_PAGES_REPORTED]:
        level = logging.WARNING if any(not f.advisory for f in findings) else logging.INFO
        logger.log(level, f"Accessibility: {page}")
        for finding in findings[:MAX_A11Y_FINDINGS_PER_PAGE]:
            prefix = "advisory: " if finding.advisory else ""
            logger.log(level, f"  - {prefix}{finding.describe()}")
        hidden_findings = len(findings) - MAX_A11Y_FINDINGS_PER_PAGE
        if hidden_findings > 0:
            logger.log(level, f"  ... and {hidden_findings} more on this page")
    hidden_pages = len(report.pages) - MAX_A11Y_PAGES_REPORTED
    if hidden_pages > 0:
        logger.warning(f"Accessibility: ... and {hidden_pages} more pages with findings")
    logger.warning(report.summary())


def _count_build_steps(blog_enabled: bool, skip_images: bool) -> int:
    total = ALWAYS_RUN_STEP_COUNT
    if blog_enabled:
        total += BLOG_STEP_COUNT
    if not skip_images:
        total += IMAGE_STEP_COUNT
    return total


def _is_hidden_within(path: Path, root: Path) -> bool:
    """Whether path, or any folder between root and it, starts with a dot."""
    return any(part.startswith(".") for part in path.relative_to(root).parts)


def _count(amount: int, noun: str) -> str:
    """'1 post', '3 posts'."""
    return f"{amount} {noun}{'s' if amount != 1 else ''}"


def _remove_path(path: str) -> None:
    """Delete a file, link or directory tree (nothing if it is none of those)."""
    if os.path.isfile(path) or os.path.islink(path):
        os.unlink(path)
        logger.debug(f"Deleted file: {path}")
    elif os.path.isdir(path):
        shutil.rmtree(path)
        logger.debug(f"Deleted directory: {path}")
