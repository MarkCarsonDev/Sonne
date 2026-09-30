"""Full builds of the blog fixture site (bundled blog template + overlay posts)."""

import logging
import re

import pytest


@pytest.fixture
def blog_build(site_factory, builder):
    site = site_factory("blog", overlay="blog_site")
    generator, out = builder(site)
    return site, generator, out


class TestBlogBuild:
    def test_post_rendered_at_dated_url(self, blog_build, builder):
        _, _, out = blog_build
        post = out / "blog" / "2025" / "02" / "01" / "hello-world" / "index.html"
        assert post.exists()
        assert "Hello World" in post.read_text(encoding="utf-8")

    def test_blog_index_lists_posts(self, blog_build, builder):
        _, _, out = blog_build
        index = out / "blog" / "index.html"
        assert index.exists()
        assert "Hello World" in index.read_text(encoding="utf-8")

    def test_draft_directory_not_published(self, blog_build, builder):
        _, _, out = blog_build
        assert not any("secret" in p.name for p in out.rglob("*"))

    def test_tag_page_generated(self, blog_build, builder):
        _, _, out = blog_build
        assert any(p.is_dir() and p.name == "alpha" for p in out.rglob("alpha"))

    def test_regular_pages_still_render(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / "about" / "index.html").exists()


class TestBlogKnownBugs:
    def test_filename_date_prefix_stripped_from_slug(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / "blog" / "2025" / "03" / "05" / "shiny-day" / "index.html").exists()

    def test_post_with_drafts_substring_in_name_is_published(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / "blog" / "2025" / "04" / "01" / "year-end-drafts" / "index.html").exists()

    def test_sibling_dir_starting_with_blog_name_is_rendered(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / "blog-archive" / "note" / "index.html").exists()

    def test_bad_url_pattern_names_the_placeholder(self, site_factory, caplog, builder):
        site = site_factory("blog", overlay="blog_site")
        with caplog.at_level(logging.ERROR, logger="sonne"):
            builder(site, config_overrides={("blog", "url_pattern"): "{year}/{slugg}"})
        assert any("placeholder" in r.message and "slugg" in r.message for r in caplog.records)


class TestTaxonomyAndArchivePages:
    def test_category_page_lists_its_posts(self, blog_build):
        _, _, out = blog_build
        html = (out / "blog" / "categories" / "general" / "index.html").read_text(encoding="utf-8")
        assert "general" in html and "Hello World" in html

    def test_tag_page_lists_its_posts(self, blog_build):
        _, _, out = blog_build
        html = (out / "blog" / "tags" / "alpha" / "index.html").read_text(encoding="utf-8")
        assert "Posts Tagged: alpha" in html and "Hello World" in html

    def test_post_tag_links_use_canonical_slug(self, blog_build):
        _, _, out = blog_build
        post = out / "blog" / "2025" / "02" / "02" / "tips-tricks-fast" / "index.html"
        assert 'href="/blog/tags/qa-night/"' in post.read_text(encoding="utf-8")

    def test_date_archive_lists_its_posts(self, blog_build):
        _, _, out = blog_build
        html = (out / "blog" / "2025" / "02" / "index.html").read_text(encoding="utf-8")
        assert "February 2025" in html and "Hello World" in html


CODE_SAMPLE_POST = """---
title: Code Sample
date: 2025-05-01
---

Real image: ![Red](red.png)

```markdown
![Example](not-a-real-file.png)
```

Inline too: `![x](also-missing.png)`
"""


class TestPostImagesInCode:
    @pytest.fixture
    def code_sample_build(self, site_factory, builder, image_factory, caplog):
        site = site_factory("blog", overlay="blog_site")
        post_dir = site / "content" / "blog"
        (post_dir / "2025-05-01-code-sample.md").write_text(CODE_SAMPLE_POST, encoding="utf-8")
        image_factory(post_dir / "red.png")
        with caplog.at_level(logging.WARNING, logger="sonne"):
            _, out = builder(site)
        return out, [record.getMessage() for record in caplog.records]

    def test_real_image_is_published(self, code_sample_build):
        out, _ = code_sample_build
        assert (out / "blog" / "2025" / "05" / "01" / "code-sample" / "red.png").exists()

    def test_image_syntax_in_code_is_ignored(self, code_sample_build):
        _, messages = code_sample_build
        assert not any("Image not found" in message for message in messages)


def test_build_report_counts_rendered_posts(blog_build):
    _, generator, _ = blog_build
    assert generator.stats.blog_posts_processed == len(generator.blog_processor.posts) > 0


def write_post(site, name, front_matter, body="Body text.\n"):
    """Write a post into the site's blog directory (or a subdirectory of it)."""
    path = site / "content" / "blog" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front_matter.strip()}\n---\n\n{body}", encoding="utf-8")
    return path


def feed_thumbnail_urls(out):
    return re.findall(r'<media:thumbnail url="([^"]+)"', (out / "feed.xml").read_text("utf-8"))


class TestPostDates:
    def test_timezone_aware_and_plain_dates_build_together(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")
        write_post(site, "zoned.md", "title: Zoned\ndate: 2024-01-05 12:00:00+02:00")

        _, out = builder(site)

        assert (out / "blog" / "2024" / "01" / "05" / "zoned" / "index.html").exists()
        assert "+0200</pubDate>" in (out / "feed.xml").read_text(encoding="utf-8")


class TestTaxonomyTerms:
    def test_case_variant_tags_share_one_page(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")
        write_post(site, "upper.md", "title: Upper Post\ndate: 2025-06-01\ntags: [Python]")
        write_post(site, "lower.md", "title: Lower Post\ndate: 2025-06-02\ntags: [python]")

        generator, out = builder(site)

        html = (out / "blog" / "tags" / "python" / "index.html").read_text(encoding="utf-8")
        assert "Upper Post" in html and "Lower Post" in html
        # One entry, named with the newest post's spelling.
        tags = generator.blog_processor.taxonomies["tags"]
        assert [name for name in tags if name.lower() == "python"] == ["python"]

    def test_post_listing_both_spellings_is_listed_once(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")
        write_post(site, "both.md", "title: Both\ndate: 2025-06-01\ntags: [Python, python]")

        generator, _ = builder(site)

        assert len(generator.blog_processor.taxonomies["tags"]["Python"]["posts"]) == 1


class TestFeedUrls:
    @pytest.fixture
    def cover_site(self, site_factory, image_factory):
        site = site_factory("blog", overlay="blog_site")
        write_post(site, "covered.md", "title: Covered\ndate: 2025-06-03\ncover_img: images/c.png")
        image_factory(site / "content" / "blog" / "images" / "c.png")
        return site

    @pytest.mark.parametrize("url_style", ["clean", "directory", "html"])
    def test_feed_thumbnail_points_at_published_cover(self, cover_site, builder, url_style):
        _, out = builder(cover_site, {"url_style": url_style})

        [thumbnail] = feed_thumbnail_urls(out)
        assert (out / thumbnail.removeprefix("http://localhost/")).exists()

    def test_trailing_slash_base_url_gives_single_slashes(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")

        _, out = builder(site, {("site", "base_url"): "https://example.com/"})

        feed = (out / "feed.xml").read_text(encoding="utf-8")
        assert "https://example.com/blog/" in feed
        assert "example.com//" not in feed


class TestDraftsAndPaths:
    def test_site_inside_a_drafts_folder_publishes_posts(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site", name="_drafts/site")

        _, out = builder(site)

        assert (out / "blog" / "2025" / "02" / "01" / "hello-world" / "index.html").exists()

    def test_post_image_cannot_escape_output_dir(
        self, site_factory, builder, image_factory, tmp_path
    ):
        site = site_factory("blog", overlay="blog_site")
        # Source resolves (from content/blog/a/b/c/d/e/) to tmp_path/escape.png; the same
        # ref from the post's output dir (output/blog/2025/06/04/deep/) lands above tmp_path.
        ref = "../" * 8 + "b36_escape.png"
        write_post(site, "a/b/c/d/e/deep.md", "title: Deep\ndate: 2025-06-04", f"![x]({ref})\n")
        image_factory(tmp_path / "b36_escape.png")
        escaped = tmp_path.parent / "b36_escape.png"

        try:
            builder(site)
            assert not escaped.exists()
        finally:
            escaped.unlink(missing_ok=True)


class TestDitherFailure:
    def test_failed_dither_links_the_original(
        self, site_factory, builder, image_factory, monkeypatch
    ):
        from sonne.processors.image_processor import ImageProcessor

        def broken_dither(self, image):
            raise RuntimeError("dither failed")

        monkeypatch.setattr(ImageProcessor, "dither", broken_dither)
        site = site_factory("blog", overlay="blog_site")
        write_post(site, "photo.md", "title: Photo\ndate: 2025-06-05", "![Red](red.jpg)\n")
        image_factory(site / "content" / "blog" / "red.jpg", fmt="JPEG")

        _, out = builder(site, {("images", "dither"): True})

        post_dir = out / "blog" / "2025" / "06" / "05" / "photo"
        assert not (post_dir / "dithered" / "red.png").exists()
        assert 'src="red.jpg"' in (post_dir / "index.html").read_text(encoding="utf-8")
