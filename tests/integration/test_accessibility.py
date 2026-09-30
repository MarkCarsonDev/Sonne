"""The build-time accessibility check (build.accessibility_checks, --a11y-strict)."""

import logging
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from sonne.cli.commands import cli
from sonne.utils.a11y_check import AccessibilityCheckFailed

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_WITHOUT_ALT = '---\ntitle: Pic\n---\n<img src="/images/x.png">\n'
SKIPPED_HEADING = "---\ntitle: Skip\n---\n# Top\n\n#### Too deep\n"


def add_page(site, name, source):
    (site / "content" / name).write_text(source, encoding="utf-8")


def messages(caplog):
    return [record.getMessage() for record in caplog.records]


class TestModes:
    def test_warn_is_the_default_and_the_build_succeeds(self, site_factory, builder, caplog):
        site = site_factory("minimal")
        add_page(site, "pic.md", IMAGE_WITHOUT_ALT)

        with caplog.at_level(logging.INFO, logger="sonne"):
            generator, out = builder(site)

        assert (out / "pic" / "index.html").exists()
        assert generator.accessibility_report.blocking_count == 1
        logged = messages(caplog)
        assert "Accessibility: pic/index.html" in logged
        assert any("[WCAG 1.1.1]" in line and "no alt attribute" in line for line in logged)

    def test_error_mode_fails_after_writing_the_output(self, site_factory, builder):
        site = site_factory("minimal")
        add_page(site, "pic.md", IMAGE_WITHOUT_ALT)

        with pytest.raises(AccessibilityCheckFailed, match="1 accessibility issues"):
            builder(site, {("build", "accessibility_checks"): "error"})

        assert (site / "output" / "pic" / "index.html").exists()

    def test_advisories_alone_do_not_fail_error_mode(self, site_factory, builder):
        site = site_factory("minimal")
        add_page(site, "skip.md", SKIPPED_HEADING)

        generator, _ = builder(site, {("build", "accessibility_checks"): "error"})

        assert generator.accessibility_report.advisory_count == 1

    def test_off_skips_the_check(self, site_factory, builder):
        site = site_factory("minimal")
        add_page(site, "pic.md", IMAGE_WITHOUT_ALT)

        generator, _ = builder(site, {("build", "accessibility_checks"): "off"})

        assert generator.accessibility_report is None

    def test_invalid_mode_warns_and_behaves_like_warn(self, site_factory, builder):
        site = site_factory("minimal")
        add_page(site, "pic.md", IMAGE_WITHOUT_ALT)

        generator, _ = builder(site, {("build", "accessibility_checks"): "strict"})

        assert generator.accessibility_report.blocking_count == 1
        assert any(
            "build.accessibility_checks must be one of" in w for w in generator.config.validate()
        )


class TestReportSize:
    def test_long_reports_are_capped(self, site_factory, builder, caplog):
        site = site_factory("minimal")
        for number in range(12):
            add_page(site, f"pic{number:02d}.md", IMAGE_WITHOUT_ALT)

        with caplog.at_level(logging.INFO, logger="sonne"):
            builder(site)

        logged = messages(caplog)
        assert sum(line.startswith("Accessibility: pic") for line in logged) == 10
        assert "Accessibility: ... and 2 more pages with findings" in logged
        assert "Accessibility checks: 12 issues and 0 advisories on 12 of 14 pages" in logged


class TestCli:
    @pytest.fixture
    def site_with_issue(self, tmp_path):
        target = tmp_path / "cli-site"
        CliRunner().invoke(cli, ["new", "-p", str(target), "-t", "minimal"])
        add_page(target, "pic.md", IMAGE_WITHOUT_ALT)
        return target

    def test_summary_line_in_build_output(self, site_with_issue):
        result = CliRunner().invoke(cli, ["build", "-p", str(site_with_issue), "--no-progress"])

        assert result.exit_code == 0, result.output
        assert "Accessibility checks: 1 issue and 0 advisories on 1 of 3 pages" in result.output

    def test_a11y_strict_fails_the_build(self, site_with_issue):
        result = CliRunner().invoke(
            cli, ["build", "-p", str(site_with_issue), "--no-progress", "--a11y-strict"]
        )

        assert result.exit_code == 1
        assert "accessibility issues found" in result.output


@pytest.mark.parametrize(
    "template",
    [
        "blog",
        "minimal",
        "solar",
        pytest.param(
            "portfolio",
            marks=pytest.mark.xfail(
                strict=True,
                reason="portfolio scaffold: templates/blog_list.html and blog_post.html are "
                "empty, so its blog pages are empty (reported to sonne-ad)",
            ),
        ),
    ],
)
def test_bundled_scaffolds_have_no_blocking_issues(site_factory, builder, template):
    generator, _ = builder(site_factory(template))

    report = generator.accessibility_report
    assert report.blocking_count == 0, {
        page: [f.describe() for f in fs] for page, fs in report.pages.items()
    }


@pytest.mark.xfail(
    strict=True,
    reason="showcase example: templates/tags.html is empty (empty blog/tags page), and the "
    'contact form\'s id="email" collides with the "### Email" heading id (reported to sonne-ad)',
)
def test_showcase_example_has_no_blocking_issues(tmp_path, builder):
    site = tmp_path / "showcase"
    shutil.copytree(REPO_ROOT / "sonne" / "examples" / "showcase-template", site)

    generator, _ = builder(site)

    report = generator.accessibility_report
    assert report.blocking_count == 0, {
        page: [f.describe() for f in fs] for page, fs in report.pages.items()
    }
