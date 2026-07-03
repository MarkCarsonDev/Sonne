"""Full builds of the blog fixture site (bundled blog template + overlay posts)."""
import logging

import pytest



@pytest.fixture
def blog_build(site_factory, builder):
    site = site_factory('blog', overlay='blog_site')
    generator, out = builder(site)
    return site, generator, out


class TestBlogBuild:
    def test_post_rendered_at_dated_url(self, blog_build, builder):
        _, _, out = blog_build
        post = out / 'blog' / '2025' / '02' / '01' / 'hello-world' / 'index.html'
        assert post.exists()
        assert 'Hello World' in post.read_text(encoding='utf-8')

    def test_blog_index_lists_posts(self, blog_build, builder):
        _, _, out = blog_build
        index = out / 'blog' / 'index.html'
        assert index.exists()
        assert 'Hello World' in index.read_text(encoding='utf-8')

    def test_draft_directory_not_published(self, blog_build, builder):
        _, _, out = blog_build
        assert not any('secret' in p.name for p in out.rglob('*'))

    def test_tag_page_generated(self, blog_build, builder):
        _, _, out = blog_build
        assert any(p.is_dir() and p.name == 'alpha' for p in out.rglob('alpha'))

    def test_regular_pages_still_render(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / 'about' / 'index.html').exists()


class TestBlogKnownBugs:
    @pytest.mark.xfail(strict=True, reason="B1: date prefix from filename leaks into slug/URL")
    def test_filename_date_prefix_stripped_from_slug(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / 'blog' / '2025' / '03' / '05' / 'shiny-day' / 'index.html').exists()

    @pytest.mark.xfail(strict=True, reason="B8: '_drafts' substring match drops year_end_drafts.md")
    def test_post_with_drafts_substring_in_name_is_published(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / 'blog' / '2025' / '04' / '01' / 'year-end-drafts' / 'index.html').exists()

    @pytest.mark.xfail(strict=True, reason="A4: blog-dir exclusion by string prefix swallows blog-archive/")
    def test_sibling_dir_starting_with_blog_name_is_rendered(self, blog_build, builder):
        _, _, out = blog_build
        assert (out / 'blog-archive' / 'note' / 'index.html').exists()

    @pytest.mark.xfail(strict=True, reason="bad url_pattern placeholder drops all posts with no useful error")
    def test_bad_url_pattern_names_the_placeholder(self, site_factory, caplog, builder):
        site = site_factory('blog', overlay='blog_site')
        with caplog.at_level(logging.ERROR, logger='sonne'):
            builder(site, config_overrides={('blog', 'url_pattern'): '{year}/{slugg}'})
        assert any('placeholder' in r.message and 'slugg' in r.message for r in caplog.records)
