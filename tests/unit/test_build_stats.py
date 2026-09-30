"""BuildStatistics: the human-readable build report (pinned verbatim)."""

import pytest

from sonne.utils.build_stats import BuildStatistics

RULE = "=" * 60
THIN_RULE = "-" * 60


def busy_build():
    """A build that exercises every section of the report."""
    stats = BuildStatistics(start_time=100.0, end_time=101.5)
    stats.pages_processed = 4
    stats.pages_skipped = 1
    stats.blog_posts_processed = 2
    stats.images_processed = 3
    stats.images_cached = 2
    stats.original_image_size = 3 * 1024 * 1024
    stats.processed_image_size = 1024 * 1024
    stats.templates_rendered = 6
    stats.template_errors = 1
    stats.files_copied = 5
    stats.files_deleted = 1
    stats.cache_hits = 1
    stats.cache_misses = 3
    stats.warnings = [f"w{i}" for i in range(7)]
    stats.errors = ["e0"]
    stats.record_phase("images", 4.0)
    stats.record_phase("pages", 0.5)
    stats.record_phase("custom", 0.0005)
    stats.record_image("content/a/big.png", 3.5, method="lab_kmeans", width=800, height=600)
    stats.record_image("small.png", 0.02)
    stats.record_image("cached.png", 9.0, cached=True)
    stats.record_post("hello", 0.25)
    stats.record_script("slow.py", 2.5)
    return stats


SUMMARY_LINES = [
    RULE,
    "Build Complete",
    RULE,
    "Duration: 1.50s",
    "",
    "Pages:",
    "  ✓ Processed: 4",
    "  ⊘ Skipped (cached): 1",
    "  ✓ Blog posts: 2",
    "",
    "Images:",
    "  ✓ Processed: 3",
    "  ⊘ Cached: 2",
    "  ↓ Saved: 2.00 MB",
    "",
]


class TestFormatReport:
    def test_empty_build_reports_only_duration_and_pages(self):
        stats = BuildStatistics(start_time=0.0, end_time=0.25)

        report = stats.format_report()

        assert report == "\n".join(
            [
                RULE,
                "Build Complete",
                RULE,
                "Duration: 0.25s",
                "",
                "Pages:",
                "  ✓ Processed: 0",
                "",
                RULE,
            ]
        )

    def test_default_report_summarises_without_details(self):
        report = busy_build().format_report()

        assert report == "\n".join(
            SUMMARY_LINES
            + ["Cache:", "  Hit rate: 25.0%", "", "⚠ Warnings: 7", "", "✗ Errors: 1", "", RULE]
        )

    def test_verbose_perf_report_includes_every_section(self):
        report = busy_build().format_report(verbose=True, perf=True)

        assert report == "\n".join(
            SUMMARY_LINES
            + [
                "Templates:",
                "  ✓ Rendered: 6",
                "  ✗ Errors: 1",
                "",
                "Cache:",
                "  Hit rate: 25.0%",
                "  Hits: 1",
                "  Misses: 3",
                "",
                "File Operations:",
                "  Copied: 5",
                "  Deleted: 1",
                "",
                "⚠ Warnings: 7",
                "  - w0",
                "  - w1",
                "  - w2",
                "  - w3",
                "  - w4",
                "  ... and 2 more",
                "",
                "✗ Errors: 1",
                "  - e0",
                "",
                THIN_RULE,
                "Performance Breakdown",
                THIN_RULE,
                "Phases:",
                "  Images          4.00s  █████████████████████░░░   89%",
                "  Pages           500ms  ███░░░░░░░░░░░░░░░░░░░░░   11%",
                "  custom          0.5ms  ░░░░░░░░░░░░░░░░░░░░░░░░    0%",
                "",
                "Slowest images:",
                "  big.png                                3.50s  (800×600, lab_kmeans)",
                "  small.png                               20ms",
                "",
                "Slowest posts:",
                "  hello                                       250ms",
                "",
                "Scripts:",
                "  slow.py                                2.50s",
                "",
                "Hints:",
                "  ⚡ Some images took >3s with lab_kmeans — try dither: bayer for faster builds",
                "  ⚡ Slow scripts block the build: slow.py",
                "  ⚡ Low cache hit rate — run with --skip-cache only when images change",
                "",
                RULE,
            ]
        )


class TestPerformanceHints:
    @pytest.mark.xfail(strict=True, reason="B47: slow-image hint checks a method name never used")
    def test_slow_color_lab_images_suggest_bayer(self):
        stats = BuildStatistics(start_time=0.0, end_time=5.0)
        stats.record_phase("images", 4.0)
        stats.record_image("photo.png", 3.5, method="color_lab")

        report = stats.format_report(perf=True)

        assert "with color_lab — try images.dither_method: bayer" in report
