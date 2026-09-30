"""all_pages: every content page, available to templates and data scripts."""

from pathlib import Path

import pytest


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def site_with_projects(site_factory):
    """The minimal site (index.md, about.md) plus a projects section."""
    site = site_factory("minimal")
    write(site / "content" / "projects" / "index.md", "---\ntitle: Projects\n---\nAll of them.\n")
    write(
        site / "content" / "projects" / "solar-monitor.md",
        "---\ntitle: Solar Monitor\nfeatured: true\n---\nA project.\n",
    )
    write(site / "content" / "projects" / "untitled.md", "No front matter here.\n")
    return site


def all_pages(generator):
    return generator.variable_manager.variables["global"]["all_pages"]


def by_url(generator):
    return {page["url"]: page for page in all_pages(generator)}


class TestAllPages:
    def test_lists_every_page_sorted_by_url(self, site_with_projects, builder):
        generator, _ = builder(site_with_projects)
        urls = [page["url"] for page in all_pages(generator)]
        assert urls == [
            "/",
            "/about/",
            "/projects/",
            "/projects/solar-monitor/",
            "/projects/untitled/",
        ]

    def test_entries_carry_front_matter_title_and_section(self, site_with_projects, builder):
        generator, _ = builder(site_with_projects)
        project = by_url(generator)["/projects/solar-monitor/"]
        assert project["title"] == "Solar Monitor"
        assert project["featured"] is True
        assert project["section"] == "projects"
        assert project["source_path"].endswith("solar-monitor.md")
        assert by_url(generator)["/about/"]["section"] == ""

    def test_title_defaults_to_the_file_or_folder_name(self, site_with_projects, builder):
        write(site_with_projects / "content" / "notes" / "index.md", "Notes.\n")
        generator, _ = builder(site_with_projects)
        assert by_url(generator)["/projects/untitled/"]["title"] == "untitled"
        assert by_url(generator)["/notes/"]["title"] == "notes"

    @pytest.mark.parametrize("url_style", ["clean", "directory", "html"])
    def test_each_url_is_where_the_page_was_written(self, site_with_projects, builder, url_style):
        generator, output = builder(site_with_projects, {"url_style": url_style})
        for page in all_pages(generator):
            written = output / page["url"].lstrip("/")
            if not page["url"].endswith(".html"):
                written = written / "index.html"
            assert written.is_file(), f"{page['url']} ({url_style}) has no output file"

    def test_page_url_matches_its_all_pages_entry(self, site_with_projects, builder):
        """A page's own page.url and its all_pages url come from one function."""
        write(
            site_with_projects / "templates" / "url_probe.html",
            "<p id='own'>{{ page.url }}</p>"
            "{% for p in all_pages if p.source_path == page.source_path %}"
            "<p id='listed'>{{ p.url }}</p>{% endfor %}",
        )
        write(
            site_with_projects / "content" / "projects" / "probe.md",
            "---\ntitle: Probe\ntemplate: url_probe.html\n---\n",
        )
        _, output = builder(site_with_projects)
        html = (output / "projects" / "probe" / "index.html").read_text(encoding="utf-8")
        assert "<p id='own'>/projects/probe/</p>" in html
        assert "<p id='listed'>/projects/probe/</p>" in html

    def test_templates_can_list_a_section(self, site_with_projects, builder):
        write(
            site_with_projects / "templates" / "section.html",
            "{% for p in all_pages if p.section == 'projects' and p.url != page.url %}"
            "<a href='{{ p.url }}'>{{ p.title }}</a>{% endfor %}",
        )
        index = site_with_projects / "content" / "projects" / "index.md"
        write(index, "---\ntitle: Projects\ntemplate: section.html\n---\n")
        _, output = builder(site_with_projects)
        html = (output / "projects" / "index.html").read_text(encoding="utf-8")
        assert "<a href='/projects/solar-monitor/'>Solar Monitor</a>" in html
        assert "Projects</a>" not in html

    def test_blog_posts_are_left_to_all_blog_posts(self, site_factory, builder):
        site = site_factory("blog")
        generator, _ = builder(site)
        blog_dir = str(Path("content", "blog"))
        assert all(blog_dir not in page["source_path"] for page in all_pages(generator))
        assert generator.variable_manager.variables["global"]["all_blog_posts"]

    def test_data_scripts_can_read_all_pages(self, site_with_projects, builder):
        write(
            site_with_projects / "scripts" / "projects.py",
            "from sonne.script_api import get_variable, sonne_var\n"
            "pages = get_variable('all_pages', [])\n"
            "titles = [p['title'] for p in pages if p['section'] == 'projects']\n"
            "sonne_var('project_titles', titles)\n",
        )
        generator, _ = builder(site_with_projects)
        titles = generator.variable_manager.variables["global"]["project_titles"]
        assert titles == ["Projects", "Solar Monitor", "untitled"]
