"""Every starter template loads the dithering toggle only when dithering is on."""

import pytest

STARTER_TEMPLATES = ["blog", "portfolio", "minimal", "solar"]
DITHERING_CSS = '<link href="/css/dithering.css" rel="stylesheet"/>'
DITHERING_JS = '<script defer="" src="/js/dithering.js"></script>'


def home_page(output):
    return (output / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("template", STARTER_TEMPLATES)
def test_dithering_on_links_the_toggle_assets(site_factory, builder, template):
    _, output = builder(site_factory(template), {("images", "dither"): True})

    page = home_page(output)

    assert DITHERING_CSS in page
    assert DITHERING_JS in page
    assert (output / "css" / "dithering.css").is_file()
    assert (output / "js" / "dithering.js").is_file()


@pytest.mark.parametrize("template", STARTER_TEMPLATES)
def test_dithering_off_links_nothing_missing(site_factory, builder, template):
    _, output = builder(site_factory(template), {("images", "dither"): False})

    page = home_page(output)

    assert "dithering.css" not in page
    assert "dithering.js" not in page
