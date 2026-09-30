"""The bundled solar template builds into working pages."""

import logging
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
        assert '<img alt="Energy-Efficient Web Design Principles" src="/images/vogel.jpg"' in page
        assert (output / "images" / "vogel.jpg").exists()

    def test_scripts_do_not_replace_site_config_values(self, solar_site, builder, caplog):
        with caplog.at_level(logging.WARNING, logger="sonne"):
            builder(solar_site)
        assert "replaces the site variable" not in caplog.text

    def test_projects_page_lists_the_projects(self, solar_site, builder):
        _, output = builder(solar_site)
        page = read_page(output, "projects")
        assert 'href="/projects/project-1/"' in page
        assert "Solar-Powered Monitoring Station" in page
