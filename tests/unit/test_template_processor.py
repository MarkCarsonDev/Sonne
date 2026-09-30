"""TemplateProcessor page URLs, template selection, and the process_image filter."""

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


class TestPostTemplate:
    def test_posts_in_configured_blog_directory_use_post_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "posts" / "hello.md", "# Hello\n")
        processor = make_processor(
            site,
            {("blog", "directory"): "posts", ("blog", "template"): "custom_post.html"},
        )
        _, html = processor.process_page("# Hello\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" in html

    def test_posts_in_default_blog_directory_use_post_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "blog" / "hello.md", "# Hello\n")
        processor = make_processor(site, {("blog", "template"): "custom_post.html"})
        # str(Path) uses the OS separator: backslashes on Windows
        _, html = processor.process_page("# Hello\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" in html

    def test_pages_outside_blog_directory_use_page_template(self, site):
        write(site / "templates" / "custom_post.html", "CUSTOM-POST {{ content }}")
        source = write(site / "content" / "docs" / "blog" / "notes.md", "# Notes\n")
        processor = make_processor(site, {("blog", "template"): "custom_post.html"})
        _, html = processor.process_page("# Notes\n", True, str(source), EMPTY_SCOPES)
        assert "CUSTOM-POST" not in html


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

    @pytest.mark.parametrize(
        "src, original_src",
        [
            ("/images/b_800.webp", "/images/b_800_original.webp"),
            ("/images/a.png", "/images/a_original.png"),
            pytest.param(
                "/v_1.2/a.png",
                "/v_1.2/a_original.png",
                marks=pytest.mark.xfail(strict=True, reason="B29: _original put after _<digits>."),
            ),
            pytest.param(
                "q.png?v=1.2",
                "q_original.png?v=1.2",
                marks=pytest.mark.xfail(strict=True, reason="B29: _original put in query string"),
            ),
        ],
    )
    def test_original_goes_before_the_file_extension(self, site, src, original_src):
        html = self.render(site, dither=True, src=src)
        assert f'src="{original_src}"' in html

    def test_plain_image_renders_as_markup_with_escaped_alt(self, site):
        html = self.render(site, dither=False)
        assert '<img src="pic.png"' in html
        assert self.ESCAPED_ALT in html

    def test_dithered_image_escapes_alt(self, site):
        html = self.render(site, dither=True)
        assert '<img src="pic.png"' in html
        assert self.ESCAPED_ALT in html


class TestTemplateStatistics:
    def render(self, site, template):
        source = write(site / "content" / "page.md", f"---\ntemplate: {template}\n---\n# Page\n")
        processor = make_processor(site)
        processor.stats = BuildStatistics()
        processor.process_page(source.read_text(encoding="utf-8"), True, str(source), EMPTY_SCOPES)
        return processor.stats

    def test_rendered_template_is_counted(self, site):
        stats = self.render(site, "page.html")
        assert (stats.templates_rendered, stats.template_errors) == (1, 0)

    def test_missing_template_is_counted_as_error(self, site):
        stats = self.render(site, "missing.html")
        assert (stats.templates_rendered, stats.template_errors) == (0, 1)
