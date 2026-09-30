"""Full builds of the blog fixture site (bundled blog template + overlay posts)."""

import logging

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
