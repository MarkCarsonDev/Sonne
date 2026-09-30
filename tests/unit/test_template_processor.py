"""TemplateProcessor page URLs, template selection, and the process_image filter."""

import re

import pytest

from sonne.core.config import Config
from sonne.core.site_generator import SiteGenerator
from sonne.utils.build_stats import BuildStatistics

EMPTY_SCOPES = {"global": {}, "site": {}, "page": {}}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_processor(site, config_overrides=None):
    config = Config(base_dir=str(site))
    for keys, value in (config_overrides or {}).items():
        config.set(*keys, value=value)
    return SiteGenerator(config, base_dir=str(site)).template_processor


def page_url(processor, source):
    front_matter, _ = processor.process_page("# Page\n", True, str(source), EMPTY_SCOPES)
    return front_matter["url"]


@pytest.fixture
def site(site_factory):
    return site_factory("minimal")


class TestPageUrls:
    def test_root_index_page_is_site_root(self, site):
        source = write(site / "content" / "index.md", "# Home\n")
        processor = make_processor(site)
        assert page_url(processor, source) == processor.config.format_url("/")

    def test_nested_index_page_is_its_directory(self, site):
        source = write(site / "content" / "projects" / "index.md", "# Projects\n")
        processor = make_processor(site)
        assert page_url(processor, source) == processor.config.format_url("/projects/")

    def test_only_the_markdown_suffix_is_stripped(self, site):
        source = write(site / "content" / "v1.mdnotes" / "page.md", "# Page\n")
        processor = make_processor(site)
        assert page_url(processor, source) == processor.config.format_url("/v1.mdnotes/page")

    @pytest.mark.parametrize(
        "file_name, url_style, expected_url",
        [
            ("about.html", "clean", "/about"),
            ("about.html", "directory", "/about/"),
            ("about.html", "html", "/about.html"),
            ("docs/index.htm", "clean", "/docs"),
            ("docs/index.htm", "directory", "/docs/"),
        ],
    )
    def test_html_page_url_matches_where_it_is_written(
        self, site, file_name, url_style, expected_url
    ):
        source = write(site / "content" / file_name, "<p>Page</p>")
        processor = make_processor(site, {("url_style",): url_style})
        front_matter, _ = processor.process_page("<p>Page</p>", False, str(source), EMPTY_SCOPES)
        assert front_matter["url"] == expected_url


class TestPostTemplate:
    def test_posts_in_configured_blog_directory_use_post_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "posts" / "hello.md", "# Hello\n")
        processor = make_processor(
            site,
            {
                ("blog", "enabled"): True,  # the minimal template disables the blog
                ("blog", "directory"): "posts",
                ("blog", "template"): "custom_post.html",
            },
        )
        _, html = processor.process_page("# Hello\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" in html

    def test_posts_in_default_blog_directory_use_post_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "blog" / "hello.md", "# Hello\n")
        processor = make_processor(
            site, {("blog", "enabled"): True, ("blog", "template"): "custom_post.html"}
        )
        # str(Path) uses the OS separator: backslashes on Windows
        _, html = processor.process_page("# Hello\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" in html

    def test_blog_folder_uses_page_template_when_blog_disabled(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "blog" / "hello.md", "# Hello\n")
        processor = make_processor(site, {("blog", "template"): "custom_post.html"})
        _, html = processor.process_page("# Hello\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" not in html

    def test_pages_outside_blog_directory_use_page_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "docs" / "blog" / "notes.md", "# Notes\n")
        processor = make_processor(site, {("blog", "template"): "custom_post.html"})
        _, html = processor.process_page("# Notes\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" not in html


class TestMarkdownSuffixes:
    @pytest.mark.parametrize("file_name", ["notes.markdown", "NOTES.MD"])
    def test_markdown_pages_use_page_template(self, site, file_name):
        write(site / "templates" / "page.html", "PAGE-TEMPLATE {{ content }}")
        source = write(site / "content" / file_name, "# Notes\n")
        processor = make_processor(site)
        _, html = processor.process_page("# Notes\n", True, str(source), EMPTY_SCOPES)
        assert "PAGE-TEMPLATE" in html

    def test_markdown_posts_use_post_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "blog" / "hello.markdown", "# Hello\n")
        processor = make_processor(
            site, {("blog", "enabled"): True, ("blog", "template"): "custom_post.html"}
        )
        _, html = processor.process_page("# Hello\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" in html


class TestProcessImageFilter:
    ALT_WITH_MARKUP = 'say "hi" <b>'
    ESCAPED_ALT = 'alt="say &#34;hi&#34; &lt;b&gt;"'

    def render(self, site, dither, src="pic.png"):
        write(
            site / "templates" / "image_filter.html",
            "{{ src | process_image(alt) }}",
        )
        processor = make_processor(site, {("images", "dither"): dither})
        template = processor.jinja_env.get_template("image_filter.html")
        return template.render(src=src, alt=self.ALT_WITH_MARKUP)

    def test_image_the_build_did_not_dither_gets_no_toggle(self, site):
        html = self.render(site, dither=True, src="/images/never-dithered.png")
        assert "dithered-image-container" not in html
        assert '<img src="/images/never-dithered.png"' in html

    def test_plain_image_renders_as_markup_with_escaped_alt(self, site):
        html = self.render(site, dither=False)
        assert '<img src="pic.png"' in html
        assert self.ESCAPED_ALT in html

    def test_dithered_image_escapes_alt(self, site):
        html = self.render(site, dither=True)
        assert '<img src="pic.png"' in html
        assert self.ESCAPED_ALT in html


class TestFinishPage:
    """finish_page marks the <img> tags the build dithered, and only those."""

    def processor(self, site):
        processor = make_processor(site, {("images", "dither"): True})
        processor.dithered_images.add("/images/a.png", "/images/dithered/a.png")
        processor.dithered_images.add(
            "/assets/images/b_400_original.webp", "/assets/images/b_400.webp"
        )
        return processor

    def img(self, html, marker):
        return next(tag for tag in re.findall(r"<img[^>]*>", html) if marker in tag)

    def test_original_src_is_pointed_at_the_dithered_copy(self, site):
        html = self.processor(site).finish_page('<p><img src="/images/a.png?v=2" alt="A"></p>')

        tag = self.img(html, "alt=")
        assert 'src="/images/dithered/a.png?v=2"' in tag
        assert 'data-original-src="/images/a.png?v=2"' in tag

    def test_dithered_variant_src_gets_its_original_recorded(self, site):
        html = self.processor(site).finish_page('<img src="/assets/images/b_400.webp">')

        tag = self.img(html, "b_400")
        assert 'src="/assets/images/b_400.webp"' in tag
        assert 'data-original-src="/assets/images/b_400_original.webp"' in tag

    @pytest.mark.parametrize(
        "src",
        ["/images/other.png", "images/a.png", "//cdn.example.com/images/a.png", "https://x/a.png"],
    )
    def test_images_the_build_did_not_dither_are_left_alone(self, site, src):
        html = self.processor(site).finish_page(f'<img src="{src}">')

        assert "data-original-src" not in html
        assert f'src="{src}"' in html

    def test_already_marked_images_are_left_alone(self, site):
        figure_img = '<img src="dithered/p.png" data-original-src="p.jpg">'

        html = self.processor(site).finish_page(figure_img)

        assert 'src="dithered/p.png"' in html

    def test_shared_assets_are_linked_once(self, site):
        page = (
            '<html><head><link rel="stylesheet" href="/css/dithering.css"></head>'
            '<body><script src="/js/dithering.js" defer></script></body></html>'
        )

        html = self.processor(site).finish_page(page)

        assert html.count("/css/dithering.css") == 1
        assert html.count("/js/dithering.js") == 1

    def test_missing_assets_are_added(self, site):
        html = self.processor(site).finish_page("<html><head></head><body></body></html>")

        assert '<link href="/css/dithering.css" rel="stylesheet"/>' in html
        assert '<script defer="" src="/js/dithering.js"></script>' in html

    def test_nothing_changes_without_dithering(self, site):
        processor = make_processor(site, {("images", "dither"): False})
        processor.dithered_images.add("/images/a.png", "/images/dithered/a.png")
        page = '<img src="/images/a.png">'

        assert processor.finish_page(page) == page


class TestTemplateStatistics:
    def render(self, site, template):
        source = write(site / "content" / "page.md", f"---\ntemplate: {template}\n---\n# Page\n")
        processor = make_processor(site)
        stats = processor.stats = BuildStatistics()
        processor.process_page(source.read_text(encoding="utf-8"), True, str(source), EMPTY_SCOPES)
        return stats

    def test_rendered_template_is_counted(self, site):
        stats = self.render(site, "page.html")
        assert (stats.templates_rendered, stats.template_errors) == (1, 0)

    def test_missing_template_is_counted_as_error(self, site):
        stats = self.render(site, "missing.html")
        assert (stats.templates_rendered, stats.template_errors) == (0, 1)
