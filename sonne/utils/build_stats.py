"""
Build statistics tracking for Sonne.
Tracks metrics during site generation for reporting.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger("sonne")


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
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # --- Performance timing ---
    # Phase name -> seconds elapsed
    phase_times: Dict[str, float] = field(default_factory=dict)
    # [{file, seconds, method, cached, width, height}]
    image_times: List[Dict] = field(default_factory=list)
    # script name -> seconds
    script_times: Dict[str, float] = field(default_factory=dict)
    # [{slug, seconds}]
    post_times: List[Dict] = field(default_factory=list)

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

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """Format a duration in the most readable unit."""
        if seconds >= 1.0:
            return f"{seconds:.2f}s"
        elif seconds >= 0.001:
            return f"{seconds * 1000:.0f}ms"
        else:
            return f"{seconds * 1000:.1f}ms"

    @staticmethod
    def _bar(value: float, total: float, width: int = 24) -> str:
        if total <= 0:
            return "░" * width
        filled = round((value / total) * width)
        filled = max(0, min(width, filled))
        return "█" * filled + "░" * (width - filled)

    def format_report(self, verbose: bool = False, perf: bool = False) -> str:
        """Format a human-readable build report.

        Args:
            verbose: Include detailed statistics.
            perf: Include per-phase performance breakdown.
        """
        lines = []
        lines.append("=" * 60)
        lines.append("Build Complete")
        lines.append("=" * 60)

        # Duration
        lines.append(f"Duration: {self.duration:.2f}s")
        lines.append("")

        # Pages
        lines.append("Pages:")
        lines.append(f"  ✓ Processed: {self.pages_processed}")
        if self.pages_skipped > 0:
            lines.append(f"  ⊘ Skipped (cached): {self.pages_skipped}")
        if self.blog_posts_processed > 0:
            lines.append(f"  ✓ Blog posts: {self.blog_posts_processed}")
        lines.append("")

        # Images
        if self.images_processed > 0 or self.images_cached > 0:
            lines.append("Images:")
            lines.append(f"  ✓ Processed: {self.images_processed}")
            if self.images_cached > 0:
                lines.append(f"  ⊘ Cached: {self.images_cached}")
            if self.image_savings > 0:
                lines.append(f"  ↓ Saved: {self.image_savings_mb:.2f} MB")
            lines.append("")

        # Templates
        if verbose:
            lines.append("Templates:")
            lines.append(f"  ✓ Rendered: {self.templates_rendered}")
            if self.template_errors > 0:
                lines.append(f"  ✗ Errors: {self.template_errors}")
            lines.append("")

        # Cache
        if self.cache_hits > 0 or self.cache_misses > 0:
            lines.append("Cache:")
            lines.append(f"  Hit rate: {self.cache_hit_rate:.1f}%")
            if verbose:
                lines.append(f"  Hits: {self.cache_hits}")
                lines.append(f"  Misses: {self.cache_misses}")
            lines.append("")

        # File operations
        if verbose and (self.files_copied > 0 or self.files_deleted > 0):
            lines.append("File Operations:")
            if self.files_copied > 0:
                lines.append(f"  Copied: {self.files_copied}")
            if self.files_deleted > 0:
                lines.append(f"  Deleted: {self.files_deleted}")
            lines.append("")

        # Warnings and errors
        if self.warnings:
            lines.append(f"⚠ Warnings: {len(self.warnings)}")
            if verbose:
                for warning in self.warnings[:5]:
                    lines.append(f"  - {warning}")
                if len(self.warnings) > 5:
                    lines.append(f"  ... and {len(self.warnings) - 5} more")
            lines.append("")

        if self.errors:
            lines.append(f"✗ Errors: {len(self.errors)}")
            if verbose:
                for error in self.errors[:5]:
                    lines.append(f"  - {error}")
                if len(self.errors) > 5:
                    lines.append(f"  ... and {len(self.errors) - 5} more")
            lines.append("")

        # --- Performance breakdown ---
        if perf and self.phase_times:
            lines.append("-" * 60)
            lines.append("Performance Breakdown")
            lines.append("-" * 60)

            total_timed = sum(self.phase_times.values())

            PHASE_LABELS = {
                "scripts": "Scripts     ",
                "static_copy": "Static copy ",
                "images": "Images      ",
                "blog": "Blog posts  ",
                "pages": "Pages       ",
                "finalize": "Finalize    ",
            }

            phase_order = ["images", "blog", "pages", "scripts", "static_copy", "finalize"]
            shown = sorted(
                self.phase_times.items(),
                key=lambda kv: phase_order.index(kv[0]) if kv[0] in phase_order else 99,
            )

            lines.append("Phases:")
            for name, secs in shown:
                pct = (secs / total_timed * 100) if total_timed > 0 else 0
                label = PHASE_LABELS.get(name, f"{name:<12}")
                bar = self._bar(secs, total_timed)
                lines.append(f"  {label}  {self._fmt_time(secs):>7}  {bar}  {pct:3.0f}%")
            lines.append("")

            # Slowest images
            uncached = [t for t in self.image_times if not t["cached"]]
            if uncached:
                slowest = sorted(uncached, key=lambda t: t["seconds"], reverse=True)[:5]
                lines.append("Slowest images:")
                for t in slowest:
                    name = Path(t["file"]).name
                    dims = f"{t['width']}×{t['height']}" if t["width"] else ""
                    method = f", {t['method']}" if t["method"] else ""
                    extra = f"  ({dims}{method})" if (dims or method) else ""
                    lines.append(f"  {name:<35}  {self._fmt_time(t['seconds']):>7}{extra}")
                lines.append("")

            # Slowest posts
            if self.post_times:
                slowest_posts = sorted(self.post_times, key=lambda t: t["seconds"], reverse=True)[
                    :5
                ]
                lines.append("Slowest posts:")
                for t in slowest_posts:
                    lines.append(f"  {t['slug']:<40}  {self._fmt_time(t['seconds']):>7}")
                lines.append("")

            # Script timings
            if self.script_times:
                lines.append("Scripts:")
                for name, secs in sorted(
                    self.script_times.items(), key=lambda kv: kv[1], reverse=True
                ):
                    lines.append(f"  {name:<35}  {self._fmt_time(secs):>7}")
                lines.append("")

            # Actionable hints
            hints = []
            slow_images = [t for t in uncached if t["seconds"] > 3.0]
            if slow_images:
                methods = {t["method"] for t in slow_images if t["method"]}
                if "lab_kmeans" in methods:
                    hints.append(
                        "⚡ Some images took >3s with lab_kmeans — try dither: bayer for faster builds"
                    )
            slow_scripts = {k: v for k, v in self.script_times.items() if v > 2.0}
            if slow_scripts:
                names = ", ".join(slow_scripts.keys())
                hints.append(f"⚡ Slow scripts block the build: {names}")
            total = self.cache_hits + self.cache_misses
            if total > 0 and self.cache_hit_rate < 50:
                hints.append(
                    "⚡ Low cache hit rate — run with --skip-cache only when images change"
                )
            if hints:
                lines.append("Hints:")
                for h in hints:
                    lines.append(f"  {h}")
                lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def add_warning(self, warning: str) -> None:
        """Add a warning to the build statistics."""
        self.warnings.append(warning)
        logger.warning(warning)

    def add_error(self, error: str) -> None:
        """Add an error to the build statistics."""
        self.errors.append(error)
        logger.error(error)

    def to_dict(self) -> Dict:
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
