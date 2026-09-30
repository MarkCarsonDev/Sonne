"""Full builds of the minimal fixture site."""

import logging
import shutil

import pytest


class TestMinimalBuild:
    def test_build_produces_pages(self, site_factory, builder):
        site = site_factory("minimal")
        _, out = builder(site)
        index = out / "index.html"
        about = out / "about" / "index.html"  # url_style: directory
        assert index.exists()
        assert about.exists()
        assert "My Minimal Site" in index.read_text(encoding="utf-8")

    def test_static_files_copied(self, site_factory, builder):
        site = site_factory("minimal")
        _, out = builder(site)
        assert (out / "css" / "style.css").exists()

    def test_no_dithering_assets_when_dither_disabled(self, site_factory, builder):
        site = site_factory("minimal")  # minimal config sets images.dither: false
        _, out = builder(site)
        assert not (out / "css" / "dithering.css").exists()
        assert not (out / "js" / "dithering.js").exists()

    def test_site_without_static_dir_gets_template_assets_only(self, site_factory, builder):
        site = site_factory("minimal")  # dither disabled
        shutil.rmtree(site / "static")

        _, out = builder(site)

        assert (out / "css" / "style.css").exists()  # bundled template fallback
        assert not (out / "css" / "dithering.css").exists()
        assert not (out / "js" / "dithering.js").exists()

    def test_output_collision_warns(self, site_factory, caplog, builder):
        site = site_factory("minimal")
        nested = site / "content" / "about"
        nested.mkdir()
        (nested / "index.md").write_text(
            "---\ntitle: Nested\n---\nNested about\n", encoding="utf-8"
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            builder(site)
        assert any("collide" in r.message.lower() for r in caplog.records)


class TestPageRouting:
    def test_html_url_style_writes_flat_files(self, site_factory, builder):
        site = site_factory("minimal")

        _, out = builder(site, {"url_style": "html"})

        assert (out / "index.html").exists()
        assert (out / "about.html").exists()

    def test_clean_url_style_writes_directory_index(self, site_factory, builder):
        site = site_factory("minimal")

        _, out = builder(site, {"url_style": "clean"})

        assert (out / "about" / "index.html").exists()

    def test_blog_directory_is_not_rendered_as_pages(self, site_factory, builder):
        site = site_factory("minimal")
        page = "---\ntitle: T\n---\nBody\n"
        (site / "content" / "blog").mkdir()
        (site / "content" / "blog" / "post.md").write_text(page, encoding="utf-8")
        (site / "content" / "blog-archive").mkdir()
        (site / "content" / "blog-archive" / "old.md").write_text(page, encoding="utf-8")

        _, out = builder(site)

        assert not (out / "blog" / "post").exists()
        assert (out / "blog-archive" / "old" / "index.html").exists()


class TestPageSizeLabel:
    def test_label_is_injected_when_enabled(self, site_factory, builder):
        site = site_factory("minimal")

        _, out = builder(site, {("build", "show_page_size"): True})

        html = (out / "index.html").read_text(encoding="utf-8")
        assert html.count('<style id="page-size-css">') == 1
        assert '<span id="page-size-label">~' in html
        assert " KB*</span></body>" in html

    def test_label_counts_local_images(self, site_factory, builder, image_factory):
        site = site_factory("minimal")
        image_factory(site / "static" / "img" / "a.png", size=(64, 64))
        (site / "content" / "pic.md").write_text(
            '---\ntitle: Pic\n---\n<img src="/img/a.png">\n', encoding="utf-8"
        )

        _, out = builder(site, {("build", "show_page_size"): True})

        html = (out / "pic" / "index.html").read_text(encoding="utf-8")
        assert 'data-full="~' in html
        assert ' KB with images"' in html

    def test_no_label_by_default(self, site_factory, builder):
        site = site_factory("minimal")

        _, out = builder(site)

        assert "page-size-label" not in (out / "index.html").read_text(encoding="utf-8")


class TestBuildStatistics:
    def test_rendered_pages_are_counted(self, site_factory, builder):
        site = site_factory("minimal")  # index.md + about.md

        generator, _ = builder(site)

        assert generator.stats.pages_processed == 2


def test_rendered_templates_are_counted(site_factory, builder):
    site = site_factory("minimal")

    generator, _ = builder(site)

    assert generator.stats.templates_rendered > 0


class TestPageDiscovery:
    def test_pages_render_in_sorted_order(self, site_factory, builder, monkeypatch):
        from pathlib import Path

        site = site_factory("minimal")
        for name in ["b.md", "a.md", "c.md"]:
            (site / "content" / name).write_text(f"---\ntitle: {name}\n---\nx\n", "utf-8")
        real_glob = Path.glob
        monkeypatch.setattr(
            Path, "glob", lambda self, pattern: reversed(list(real_glob(self, pattern)))
        )
        rendered = []
        from sonne.core.site_generator import SiteGenerator

        real_process_page = SiteGenerator._process_page
        monkeypatch.setattr(
            SiteGenerator,
            "_process_page",
            lambda self, path: rendered.append(path.name) or real_process_page(self, path),
        )

        builder(site)

        assert rendered == sorted(rendered)

    def test_hidden_folders_are_not_pages(self, site_factory, builder):
        site = site_factory("minimal")
        hidden = site / "content" / ".obsidian"
        hidden.mkdir()
        (hidden / "workspace.md").write_text("# notes\n", encoding="utf-8")

        _, out = builder(site)

        assert not (out / ".obsidian").exists()

    def test_directory_named_like_a_page_is_not_rendered(self, site_factory, builder, caplog):
        site = site_factory("minimal")
        (site / "content" / "notes.md").mkdir()

        with caplog.at_level(logging.ERROR, logger="sonne"):
            builder(site)

        assert not [r for r in caplog.records if "notes.md" in r.getMessage()]


class TestDisabledBlogDirectory:
    @pytest.mark.xfail(strict=True, reason="B44: content/blog is skipped even with the blog off")
    def test_blog_folder_renders_as_pages_when_blog_disabled(self, site_factory, builder):
        site = site_factory("minimal")  # blog.enabled: false
        (site / "content" / "blog").mkdir()
        (site / "content" / "blog" / "note.md").write_text("---\ntitle: Note\n---\nHi\n", "utf-8")

        _, out = builder(site)

        assert (out / "blog" / "note" / "index.html").exists()
