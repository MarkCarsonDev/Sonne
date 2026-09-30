"""
Build statistics tracking for Sonne.
Tracks metrics during site generation for reporting.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sonne")

REPORT_RULE = "=" * 60
THIN_RULE = "-" * 60
MAX_LISTED_MESSAGES = 5
SLOWEST_SHOWN = 5
SLOW_IMAGE_SECONDS = 3.0
# The dither method slow enough to deserve a hint (per-pixel error diffusion).
SLOW_DITHER_METHOD = "color_lab"
SLOW_SCRIPT_SECONDS = 2.0
LOW_CACHE_HIT_RATE_PERCENT = 50

# Report order and fixed-width labels for the known build phases; unknown
# phases sort last and are padded to the same width.
PHASE_ORDER = ["images", "blog", "pages", "scripts", "static_copy", "finalize"]
PHASE_LABELS = {
    "scripts": "Scripts     ",
    "static_copy": "Static copy ",
    "images": "Images      ",
    "blog": "Blog posts  ",
    "pages": "Pages       ",
    "finalize": "Finalize    ",
}


@dataclass
class BuildStatistics:
    """Tracks statistics for a site build."""

    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    # Page statistics
    pages_processed: int = 0
    pages_skipped: int = 0  # For incremental builds
    blog_posts_processed: int = 0

    # Image statistics
    images_processed: int = 0
    images_cached: int = 0
    original_image_size: int = 0  # bytes
    processed_image_size: int = 0  # bytes

    # Template statistics
    templates_rendered: int = 0
    template_errors: int = 0

    # File operations
    files_copied: int = 0
    files_deleted: int = 0

    # Cache statistics
    cache_hits: int = 0
    cache_misses: int = 0

    # Validation warnings/errors
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # --- Performance timing ---
    # Phase name -> seconds elapsed
    phase_times: dict[str, float] = field(default_factory=dict)
    # [{file, seconds, method, cached, width, height}]
    image_times: list[dict] = field(default_factory=list)
    # script name -> seconds
    script_times: dict[str, float] = field(default_factory=dict)
    # [{slug, seconds}]
    post_times: list[dict] = field(default_factory=list)

    def finish(self) -> None:
        """Mark the build as finished."""
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        """Get build duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100

    @property
    def image_savings(self) -> int:
        """Calculate bytes saved by image processing."""
        return max(0, self.original_image_size - self.processed_image_size)

    @property
    def image_savings_mb(self) -> float:
        """Get image savings in megabytes."""
        return self.image_savings / (1024 * 1024)

    # --- Recording helpers ---

    def record_phase(self, name: str, seconds: float) -> None:
        self.phase_times[name] = seconds

    def record_image(
        self,
        filename: str,
        seconds: float,
        method: str = "",
        cached: bool = False,
        width: int = 0,
        height: int = 0,
    ) -> None:
        self.image_times.append(
            {
                "file": filename,
                "seconds": seconds,
                "method": method,
                "cached": cached,
                "width": width,
                "height": height,
            }
        )

    def record_script(self, name: str, seconds: float) -> None:
        self.script_times[name] = seconds

    def record_post(self, slug: str, seconds: float) -> None:
        self.post_times.append({"slug": slug, "seconds": seconds})

    # --- Formatting ---

    def format_report(self, verbose: bool = False, perf: bool = False) -> str:
        """Format a human-readable build report.

        Args:
            verbose: Include detailed statistics.
            perf: Include per-phase performance breakdown.

        Returns:
            Multi-line report text.
        """
        lines = self._summary_lines(verbose)
        if perf and self.phase_times:
            lines += self._performance_lines()
        lines.append(REPORT_RULE)
        return "\n".join(lines)

    def _summary_lines(self, verbose: bool) -> list[str]:
        lines = [REPORT_RULE, "Build Complete", REPORT_RULE, f"Duration: {self.duration:.2f}s", ""]
        lines += self._page_lines()
        lines += self._image_lines()
        if verbose:
            lines += self._template_lines()
        lines += self._cache_lines(verbose)
        if verbose:
            lines += self._file_operation_lines()
        lines += self._message_lines("⚠ Warnings", self.warnings, verbose)
        lines += self._message_lines("✗ Errors", self.errors, verbose)
        return lines

    def _page_lines(self) -> list[str]:
        lines = ["Pages:", f"  ✓ Processed: {self.pages_processed}"]
        if self.pages_skipped > 0:
            lines.append(f"  ⊘ Skipped (cached): {self.pages_skipped}")
        if self.blog_posts_processed > 0:
            lines.append(f"  ✓ Blog posts: {self.blog_posts_processed}")
        return [*lines, ""]

    def _image_lines(self) -> list[str]:
        if self.images_processed == 0 and self.images_cached == 0:
            return []
        lines = ["Images:", f"  ✓ Processed: {self.images_processed}"]
        if self.images_cached > 0:
            lines.append(f"  ⊘ Cached: {self.images_cached}")
        if self.image_savings > 0:
            lines.append(f"  ↓ Saved: {self.image_savings_mb:.2f} MB")
        return [*lines, ""]

    def _template_lines(self) -> list[str]:
        lines = ["Templates:", f"  ✓ Rendered: {self.templates_rendered}"]
        if self.template_errors > 0:
            lines.append(f"  ✗ Errors: {self.template_errors}")
        return [*lines, ""]

    def _cache_lines(self, verbose: bool) -> list[str]:
        if not self._cache_was_used():
            return []
        lines = ["Cache:", f"  Hit rate: {self.cache_hit_rate:.1f}%"]
        if verbose:
            lines += [f"  Hits: {self.cache_hits}", f"  Misses: {self.cache_misses}"]
        return [*lines, ""]

    def _cache_was_used(self) -> bool:
        return self.cache_hits + self.cache_misses > 0

    def _file_operation_lines(self) -> list[str]:
        if self.files_copied == 0 and self.files_deleted == 0:
            return []
        lines = ["File Operations:"]
        if self.files_copied > 0:
            lines.append(f"  Copied: {self.files_copied}")
        if self.files_deleted > 0:
            lines.append(f"  Deleted: {self.files_deleted}")
        return [*lines, ""]

    @staticmethod
    def _message_lines(heading: str, messages: list[str], verbose: bool) -> list[str]:
        if not messages:
            return []
        lines = [f"{heading}: {len(messages)}"]
        if verbose:
            lines += [f"  - {message}" for message in messages[:MAX_LISTED_MESSAGES]]
            hidden_count = len(messages) - MAX_LISTED_MESSAGES
            if hidden_count > 0:
                lines.append(f"  ... and {hidden_count} more")
        return [*lines, ""]

    def _performance_lines(self) -> list[str]:
        lines = [THIN_RULE, "Performance Breakdown", THIN_RULE]
        lines += self._phase_lines()
        lines += self._slowest_image_lines()
        lines += self._slowest_post_lines()
        lines += self._script_lines()
        lines += self._hint_lines()
        return lines

    def _phase_lines(self) -> list[str]:
        total_seconds = sum(self.phase_times.values())
        phases = sorted(self.phase_times.items(), key=lambda phase: _phase_rank(phase[0]))
        lines = ["Phases:"]
        for name, seconds in phases:
            percent = (seconds / total_seconds * 100) if total_seconds > 0 else 0
            label = PHASE_LABELS.get(name, f"{name:<12}")
            bar = self._bar(seconds, total_seconds)
            lines.append(f"  {label}  {self._fmt_time(seconds):>7}  {bar}  {percent:3.0f}%")
        return [*lines, ""]

    def _uncached_images(self) -> list[dict]:
        return [timing for timing in self.image_times if not timing["cached"]]

    def _slowest_image_lines(self) -> list[str]:
        uncached = self._uncached_images()
        if not uncached:
            return []
        slowest = sorted(uncached, key=lambda timing: timing["seconds"], reverse=True)
        lines = ["Slowest images:"]
        for timing in slowest[:SLOWEST_SHOWN]:
            name = Path(timing["file"]).name
            elapsed = self._fmt_time(timing["seconds"])
            lines.append(f"  {name:<35}  {elapsed:>7}{_image_details(timing)}")
        return [*lines, ""]

    def _slowest_post_lines(self) -> list[str]:
        if not self.post_times:
            return []
        slowest = sorted(self.post_times, key=lambda timing: timing["seconds"], reverse=True)
        lines = ["Slowest posts:"]
        for timing in slowest[:SLOWEST_SHOWN]:
            lines.append(f"  {timing['slug']:<40}  {self._fmt_time(timing['seconds']):>7}")
        return [*lines, ""]

    def _script_lines(self) -> list[str]:
        if not self.script_times:
            return []
        slowest = sorted(self.script_times.items(), key=lambda script: script[1], reverse=True)
        lines = ["Scripts:"]
        for name, seconds in slowest:
            lines.append(f"  {name:<35}  {self._fmt_time(seconds):>7}")
        return [*lines, ""]

    def _hint_lines(self) -> list[str]:
        hints = self._performance_hints()
        if not hints:
            return []
        return ["Hints:"] + [f"  {hint}" for hint in hints] + [""]

    def _performance_hints(self) -> list[str]:
        hints = []
        slow_images = [
            timing for timing in self._uncached_images() if timing["seconds"] > SLOW_IMAGE_SECONDS
        ]
        if any(timing["method"] == SLOW_DITHER_METHOD for timing in slow_images):
            hints.append(
                f"⚡ Some images took >{SLOW_IMAGE_SECONDS:g}s with {SLOW_DITHER_METHOD}"
                " — try images.dither_method: bayer for faster builds"
            )
        slow_scripts = [
            name for name, seconds in self.script_times.items() if seconds > SLOW_SCRIPT_SECONDS
        ]
        if slow_scripts:
            hints.append(f"⚡ Slow scripts block the build: {', '.join(slow_scripts)}")
        if self._cache_was_used() and self.cache_hit_rate < LOW_CACHE_HIT_RATE_PERCENT:
            hints.append("⚡ Low cache hit rate — run with --skip-cache only when images change")
        return hints

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """Format a duration in the most readable unit."""
        if seconds >= 1.0:
            return f"{seconds:.2f}s"
        if seconds >= 0.001:
            return f"{seconds * 1000:.0f}ms"
        return f"{seconds * 1000:.1f}ms"

    @staticmethod
    def _bar(value: float, total: float, width: int = 24) -> str:
        if total <= 0:
            return "░" * width
        filled = round((value / total) * width)
        filled = max(0, min(width, filled))
        return "█" * filled + "░" * (width - filled)

    def add_warning(self, warning: str) -> None:
        """Add a warning to the build statistics."""
        self.warnings.append(warning)
        logger.warning(warning)

    def add_error(self, error: str) -> None:
        """Add an error to the build statistics."""
        self.errors.append(error)
        logger.error(error)

    def to_dict(self) -> dict:
        """Convert statistics to dictionary format."""
        return {
            "duration": self.duration,
            "pages": {
                "processed": self.pages_processed,
                "skipped": self.pages_skipped,
                "blog_posts": self.blog_posts_processed,
            },
            "images": {
                "processed": self.images_processed,
                "cached": self.images_cached,
                "savings_bytes": self.image_savings,
                "savings_mb": self.image_savings_mb,
            },
            "templates": {
                "rendered": self.templates_rendered,
                "errors": self.template_errors,
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": self.cache_hit_rate,
            },
            "files": {
                "copied": self.files_copied,
                "deleted": self.files_deleted,
            },
            "performance": {
                "phase_times": self.phase_times,
                "script_times": self.script_times,
            },
            "warnings": len(self.warnings),
            "errors": len(self.errors),
        }


def _phase_rank(name: str) -> int:
    return PHASE_ORDER.index(name) if name in PHASE_ORDER else len(PHASE_ORDER)


def _image_details(timing: dict) -> str:
    """Parenthesised dimensions and dither method, or '' when neither is known."""
    dimensions = f"{timing['width']}×{timing['height']}" if timing["width"] else ""
    method = f", {timing['method']}" if timing["method"] else ""
    return f"  ({dimensions}{method})" if (dimensions or method) else ""
