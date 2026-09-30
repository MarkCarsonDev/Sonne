"""Accessibility baseline of the blog, portfolio and minimal starter templates.

Every built page must have one <h1>, a working skip link, labelled
navigation landmarks and alt attributes on images (WCAG 2.2 AA basics).
"""

import shutil

import pytest
from bs4 import BeautifulSoup

from tests.conftest import BUNDLED_TEMPLATES, build_site

SCAFFOLDS = ["blog", "portfolio", "minimal"]


@pytest.fixture(scope="module", params=SCAFFOLDS)
def built_pages(request, tmp_path_factory):
    out = build_scaffold(request.param, tmp_path_factory)
    pages = {
        path.relative_to(out).as_posix(): BeautifulSoup(
            path.read_text(encoding="utf-8"), "html.parser"
        )
        for path in out.rglob("*.html")
    }
    assert pages
    return request.param, pages


def build_scaffold(template, tmp_path_factory):
    site = tmp_path_factory.mktemp(template) / "site"
    shutil.copytree(BUNDLED_TEMPLATES / template, site)
    _, out = build_site(site)
    return out


def failing_pages(pages, has_problem):
    return sorted(name for name, soup in pages.items() if has_problem(soup))


def test_every_page_has_exactly_one_h1(built_pages):
    _, pages = built_pages
    assert failing_pages(pages, lambda soup: len(soup.find_all("h1")) != 1) == []


def test_every_page_has_a_skip_link_to_its_main_content(built_pages):
    def lacks_skip_link(soup):
        skip = soup.find("a", class_="skip-link")
        return not skip or skip.get("href") != "#main" or not soup.find("main", id="main")

    _, pages = built_pages
    assert failing_pages(pages, lacks_skip_link) == []


def test_every_navigation_landmark_is_labelled(built_pages):
    def has_unlabelled_nav(soup):
        return any(
            not (nav.get("aria-label") or nav.get("aria-labelledby"))
            for nav in soup.find_all("nav")
        )

    _, pages = built_pages
    assert failing_pages(pages, has_unlabelled_nav) == []


def test_every_image_has_an_alt_attribute(built_pages):
    def has_image_without_alt(soup):
        return any(not img.has_attr("alt") for img in soup.find_all("img"))

    _, pages = built_pages
    assert failing_pages(pages, has_image_without_alt) == []


def test_current_navigation_item_is_announced(built_pages):
    _, pages = built_pages
    home = pages["index.html"]
    assert home.select('nav[aria-label="Main"] a[aria-current="page"]')


@pytest.fixture(scope="module")
def portfolio(tmp_path_factory):
    return build_scaffold("portfolio", tmp_path_factory)


class TestPortfolioScaffold:
    def test_blog_posts_render_at_blog_slug(self, portfolio):
        post = portfolio / "blog" / "the-importance-of-user-centered-design" / "index.html"
        assert "The Importance of User-Centered Design" in post.read_text(encoding="utf-8")

    def test_blog_index_lists_posts(self, portfolio):
        html = (portfolio / "blog" / "index.html").read_text(encoding="utf-8")
        assert "post-summary" in html

    def test_portfolio_offers_a_filter_per_category(self, portfolio):
        soup = BeautifulSoup(
            (portfolio / "portfolio" / "index.html").read_text(encoding="utf-8"), "html.parser"
        )
        filters = [button.get_text(strip=True) for button in soup.select(".filter-btn")]
        assert filters == ["All", "Web Development", "Web Design"]

    def test_every_project_link_leads_to_a_page(self, portfolio):
        soup = BeautifulSoup(
            (portfolio / "portfolio" / "index.html").read_text(encoding="utf-8"), "html.parser"
        )
        for link in soup.select(".portfolio-link"):
            href = str(link["href"])
            assert (portfolio / href.strip("/") / "index.html").exists(), href
