"""Markup Sonne generates itself meets the WCAG checks a build-time checker applies.

Covers what Sonne owns: the built-in fallback templates and base page, the
page used when a template is missing, blog figures and the page-size label.
Starter-template markup is out of scope here.
"""

import re
from collections import Counter

import pytest
from bs4 import BeautifulSoup, Tag

POST = (
    "---\ntitle: {title}\ndate: 2025-02-0{day}\ntags: [alpha, beta]\n"
    "categories: [general]\n---\n![A red square](pic{day}.png)\n\nBody text.\n"
)


def accessible_name(element: Tag) -> str:
    """A simplified accessible name: aria-label, else text plus contained img alts."""
    label = element.get("aria-label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    parts = [element.get_text()]
    parts += [str(img.get("alt", "")) for img in element.find_all("img")]
    # Whitespace collapses as in the browser's name computation.
    return " ".join(" ".join(parts).split())


def problems_in(html: str) -> list[str]:
    """WCAG problems a build-time checker flags in one page."""
    soup = BeautifulSoup(html, "html.parser")
    problems = []
    root = soup.find("html")
    if not isinstance(root, Tag) or not root.get("lang"):
        problems.append("html has no lang")
    title = soup.find("title")
    if title is None or not title.get_text(strip=True):
        problems.append("no <title>")
    if soup.find("main") is None:
        problems.append("no <main> landmark")
    for img in soup.find_all("img"):
        if not img.has_attr("alt"):
            problems.append(f"img without alt: {img.get('src')}")
    for element in soup.find_all(["a", "button"]):
        if element.name == "a" and not element.has_attr("href"):
            continue
        if not accessible_name(element):
            problems.append(f"unnamed {element.name}: {element}")
    ids = Counter(str(tag["id"]) for tag in soup.find_all(id=True))
    problems += [f"duplicate id: {name}" for name, count in ids.items() if count > 1]
    for tag in soup.find_all(tabindex=True):
        if int(str(tag["tabindex"])) > 0:
            problems.append(f"positive tabindex: {tag.name}")
    levels = [int(tag.name[1]) for tag in soup.find_all(re.compile(r"^h[1-6]$"))]
    for previous, current in zip(levels, levels[1:]):
        if current > previous + 1:
            problems.append(f"heading skip: h{previous} -> h{current}")
    for link in soup.find_all("a", href=re.compile(r"^#.")):
        if soup.find(id=str(link["href"])[1:]) is None:
            problems.append(f"in-page link to missing id: {link['href']}")
    navs = soup.find_all("nav")
    if len(navs) > 1 and not all(
        nav.get("aria-label") or nav.get("aria-labelledby") for nav in navs
    ):
        problems.append("several <nav>s, not all labelled")
    return problems


@pytest.fixture
def fallback_site(site_factory, image_factory):
    """A blog site with no templates of its own: every page comes from Sonne."""
    site = site_factory("minimal")
    for name in ("base.html", "page.html"):
        (site / "templates" / name).unlink()
    blog = site / "content" / "blog"
    blog.mkdir(parents=True, exist_ok=True)
    for day, title in ((1, "First Post"), (2, "Second Post")):
        (blog / f"2025-02-0{day}-post-{day}.md").write_text(
            POST.format(title=title, day=day), encoding="utf-8"
        )
        image_factory(blog / f"pic{day}.png", size=(32, 32), fmt="PNG")
    return site


BLOG_AND_LABELS = {
    ("blog", "enabled"): True,
    ("images", "dither"): True,
    ("build", "show_page_size"): True,
}


class TestSonneGeneratedPages:
    def test_every_page_passes_the_checks(self, fallback_site, builder):
        _, out = builder(fallback_site, BLOG_AND_LABELS)

        pages = sorted(out.rglob("*.html"))
        assert len(pages) >= 8
        report = {
            page.relative_to(out).as_posix(): problems
            for page in pages
            if (problems := problems_in(page.read_text(encoding="utf-8")))
        }
        assert report == {}

    def test_skip_link_leads_to_main(self, fallback_site, builder):
        _, out = builder(fallback_site, BLOG_AND_LABELS)

        soup = BeautifulSoup(
            (out / "blog" / "tags" / "alpha" / "index.html").read_text(encoding="utf-8"),
            "html.parser",
        )
        skip = soup.find("a", class_="skip-link")
        assert skip is not None and skip["href"] == "#main-content"
        assert soup.find("main", id="main-content") is not None

    def test_term_lists_are_lists(self, fallback_site, builder):
        _, out = builder(fallback_site, BLOG_AND_LABELS)

        for index in ("tags", "categories"):
            html = (out / "blog" / index / "index.html").read_text(encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            term_list = soup.find("ul", class_="tag-cloud")
            assert term_list is not None, index
            assert term_list.get("role") == "list"
            assert term_list.find_all("li")

    def test_read_more_links_name_their_post(self, fallback_site, builder):
        _, out = builder(fallback_site, BLOG_AND_LABELS)

        soup = BeautifulSoup(
            (out / "blog" / "tags" / "alpha" / "index.html").read_text(encoding="utf-8"),
            "html.parser",
        )
        names = sorted(accessible_name(a) for a in soup.find_all("a", class_="read-more"))
        assert names == ["Read More: First Post", "Read More: Second Post"]

    def test_listing_navigation_is_labelled(self, fallback_site, builder):
        _, out = builder(fallback_site, BLOG_AND_LABELS)

        html = (out / "blog" / "2025" / "index.html").read_text(encoding="utf-8")
        assert '<nav aria-label="Blog" class="tag-nav">' in html

    def test_dates_are_machine_readable(self, fallback_site, builder):
        _, out = builder(fallback_site, BLOG_AND_LABELS)

        html = (out / "blog" / "tags" / "alpha" / "index.html").read_text(encoding="utf-8")
        assert re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})">', html)


class TestPageWithoutTemplate:
    """Pages Sonne falls back to when a template is missing or fails."""

    def processor(self, site_factory, builder):
        site = site_factory("minimal")
        generator, _ = builder(site, {("site", "language"): "de"}, skip_images=True)
        return generator.template_processor

    def test_missing_template_page_is_a_valid_document(self, site_factory, builder):
        processor = self.processor(site_factory, builder)

        _, html = processor.process_page(
            "---\ntitle: A & B\ntemplate: missing.html\n---\nHi", True, "x.md", {"page": {}}
        )

        assert problems_in(html) == []
        assert '<html lang="de">' in html
        assert "<title>A &amp; B</title>" in html

    def test_failing_template_page_is_a_valid_document(self, site_factory, builder):
        processor = self.processor(site_factory, builder)
        with open(f"{processor.paths['templates']}/broken.html", "w", encoding="utf-8") as f:
            f.write("{{ 1 / 0 }}")

        _, html = processor.process_page(
            "---\ntitle: T\ntemplate: broken.html\n---\n**kept**", True, "x.md", {"page": {}}
        )

        assert problems_in(html) == []
        assert "<title>Error rendering template</title>" in html
        assert "<p>division by zero</p>" in html
        assert "<strong>kept</strong>" in html


class TestBlogIndexFallback:
    """The built-in blog index: posts, labelled pagination, current page marked."""

    def build(self, fallback_site, builder):
        _, out = builder(fallback_site, {**BLOG_AND_LABELS, ("blog", "posts_per_page"): 1})
        return out

    def pagination(self, out, page):
        path = out / "blog" / ("index.html" if page == 1 else f"page/{page}/index.html")
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        nav = soup.find("nav", attrs={"aria-label": "Pagination"})
        assert isinstance(nav, Tag), f"no labelled pagination on page {page}"
        return nav

    def test_current_page_is_marked(self, fallback_site, builder):
        out = self.build(fallback_site, builder)

        for page in (1, 2):
            current = self.pagination(out, page).find_all("a", attrs={"aria-current": "page"})
            assert [accessible_name(link) for link in current] == [f"Page {page}"]

    def test_links_say_where_they_go(self, fallback_site, builder):
        out = self.build(fallback_site, builder)

        names = [accessible_name(link) for link in self.pagination(out, 1).find_all("a")]
        assert names == ["Page 1", "Page 2", "Next page"]
        names = [accessible_name(link) for link in self.pagination(out, 2).find_all("a")]
        assert names == ["Previous page", "Page 1", "Page 2"]

    def test_posts_are_listed_with_named_read_more_links(self, fallback_site, builder):
        out = self.build(fallback_site, builder)

        soup = BeautifulSoup(
            (out / "blog" / "index.html").read_text(encoding="utf-8"), "html.parser"
        )
        assert [accessible_name(a) for a in soup.find_all("a", class_="read-more")] == [
            "Read More: Second Post"
        ]
