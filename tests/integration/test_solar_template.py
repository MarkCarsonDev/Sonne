"""The bundled solar template builds into working pages."""

import logging
import re
import shutil
import urllib.request
from urllib.error import URLError

import pytest
import yaml


@pytest.fixture
def offline(monkeypatch):
    """Make the weather script fall back to simulated weather."""

    def refuse(*args, **kwargs):
        raise URLError("offline in tests")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


@pytest.fixture
def solar_site(site_factory):
    return site_factory("solar")


def set_weather_units(site_dir, units):
    config_path = site_dir / "sonne.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["site"]["weather"]["units"] = units
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")


def move_blog_to(site_dir, directory):
    """Serve the blog under /<directory>/ with clean (slashless) URLs."""
    config_path = site_dir / "sonne.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["blog"]["directory"] = directory
    config["url_style"] = "clean"
    config["site"]["nav"] = [{"text": "Home", "url": "/"}]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    shutil.move(site_dir / "content" / "blog", site_dir / "content" / directory)


def broken_internal_links(output_dir):
    """Internal hrefs that point at no generated page or file."""
    broken = set()
    for page in output_dir.rglob("*.html"):
        for href in re.findall(r'href="(/[^"#?]*)', page.read_text(encoding="utf-8")):
            target = output_dir / href.strip("/")
            if not (target.is_file() or (target / "index.html").is_file()):
                broken.add(href)
    return broken


def read_page(output_dir, *parts):
    return output_dir.joinpath(*parts, "index.html").read_text(encoding="utf-8")


@pytest.mark.usefixtures("offline")
class TestSolarTemplate:
    def test_tag_page_lists_the_posts_with_that_tag(self, solar_site, builder):
        _, output = builder(solar_site)
        page = read_page(output, "blog", "tags", "sustainable")
        assert "Posts Tagged: sustainable" in page
        assert "Energy-Efficient Web Design Principles" in page

    def test_date_archive_uses_the_archive_template(self, solar_site, builder):
        _, output = builder(solar_site)
        page = read_page(output, "blog", "2025")
        assert 'class="archive-page"' in page
        assert "Energy-Efficient Web Design Principles" in page

    @pytest.mark.parametrize("units, symbol", [("metric", "°C"), ("imperial", "°F")])
    def test_weather_is_shown_in_the_configured_unit(self, solar_site, builder, units, symbol):
        set_weather_units(solar_site, units)
        _, output = builder(solar_site)
        assert symbol in (output / "index.html").read_text(encoding="utf-8")

    def test_post_cover_image_points_at_a_real_file(self, solar_site, builder):
        _, output = builder(solar_site)
        page = read_page(output, "blog", "energy-efficient-web-design-principles")
        # A static image the build dithered: shown dithered, original recorded for
        # the toggle, described by the post's cover_alt
        assert (
            '<img alt="A small bird perched at the top of a leafy tree against a pale sky" '
            'data-original-src="/images/vogel.jpg" src="/images/dithered/vogel.png"'
        ) in page
        assert (output / "images" / "vogel.jpg").exists()
        assert (output / "images" / "dithered" / "vogel.png").exists()

    def test_a_cover_next_to_its_post_names_its_original(self, solar_site, builder, image_factory):
        post_dir = solar_site / "content" / "blog" / "local-cover"
        image_factory(post_dir / "photo.jpg", size=(64, 40))
        (post_dir / "index.md").write_text(
            "---\ntitle: Local Cover\ndate: 2025-02-01\ncover_img: photo.jpg\n---\nBody.\n",
            encoding="utf-8",
        )
        _, output = builder(solar_site)
        page = read_page(output, "blog", "local-cover")
        # dithering.js adds the toggle to images that name their original
        cover = re.search(r"<img[^>]*data-original-src=\"photo.jpg\"[^>]*>", page)
        assert cover is not None
        assert 'alt=""' in cover.group(0)  # decorative without cover_alt
        assert 'src="dithered/photo.png"' in cover.group(0)
        assert (output / "blog" / "local-cover" / "photo.jpg").is_file()
        assert (output / "blog" / "local-cover" / "dithered" / "photo.png").is_file()

    def test_scripts_do_not_replace_site_config_values(self, solar_site, builder, caplog):
        with caplog.at_level(logging.WARNING, logger="sonne"):
            builder(solar_site)
        assert "replaces the site variable" not in caplog.text

    def test_projects_page_lists_the_projects(self, solar_site, builder):
        _, output = builder(solar_site)
        page = read_page(output, "projects")
        assert 'href="/projects/project-1/"' in page
        assert "Solar-Powered Monitoring Station" in page

    def test_blog_links_follow_the_blog_directory_and_url_style(self, solar_site, builder):
        move_blog_to(solar_site, "notes")
        _, output = builder(solar_site)
        assert (output / "notes" / "tags" / "sustainable" / "index.html").is_file()
        assert broken_internal_links(output) == set()


@pytest.mark.usefixtures("offline")
class TestSolarAccessibility:
    """Structure the solar scaffold gives assistive technology (WCAG 2.2 AA)."""

    @pytest.fixture
    def blog_index(self, solar_site, builder):
        _, output = builder(solar_site)
        return read_page(output, "blog")

    def test_skip_link_leads_to_the_main_landmark(self, blog_index):
        assert '<a class="skip-link" href="#main-content">Skip to content</a>' in blog_index
        assert re.search(r'<main[^>]*id="main-content"', blog_index)

    def test_nav_is_labelled_and_marks_the_current_page(self, blog_index):
        assert '<nav aria-label="Main" class="site-nav">' in blog_index
        assert '<a aria-current="page" href="/blog/">Blog</a>' in blog_index

    def test_theme_toggle_is_a_named_toggle_button(self, blog_index):
        toggle = re.search(r'<button[^>]*class="theme-toggle"[^>]*>', blog_index)
        assert toggle is not None
        assert 'type="button"' in toggle.group(0)
        assert 'aria-label="Dark mode"' in toggle.group(0)
        assert 'aria-pressed="false"' in toggle.group(0)

    def test_theme_follows_the_system_until_one_is_chosen(self, blog_index):
        assert re.search(r"<html[^>]*data-theme", blog_index) is None
        assert "@media (prefers-color-scheme: light)" in blog_index

    def test_read_more_links_name_their_post(self, blog_index):
        assert (
            'Read More<span class="sr-only">: Energy-Efficient Web Design Principles</span>'
        ) in blog_index

    def test_status_icons_have_text_alternatives(self, blog_index):
        assert '<span aria-hidden="true" class="battery-icon">' in blog_index
        assert re.search(r'<span aria-label="[^"]+" class="weather-icon" role="img"', blog_index)
