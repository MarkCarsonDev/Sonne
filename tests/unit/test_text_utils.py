"""Slug generation: pins for the blog slugifier, xfails for unification (B10)."""
import pytest

from sonne.processors.blog_processor import BlogProcessor


def blog_slugify(text):
    # _slugify does not use self, so it can be exercised without constructing
    # the (heavy) BlogProcessor.
    return BlogProcessor._slugify(None, text)


class TestBlogSlugify:
    @pytest.mark.parametrize('text,expected', [
        ('Hello World!', 'hello-world'),
        ('  Spaces   Everywhere  ', 'spaces-everywhere'),
        ('MixedCASE', 'mixedcase'),
        ('snake_case_tag', 'snake_case_tag'),  # underscores preserved
        ('多言語 Title', '多言語-title'),
    ])
    def test_basic_slugs(self, text, expected):
        assert blog_slugify(text) == expected

    def test_slug_is_filesystem_safe(self):
        slug = blog_slugify('a/b\\c: d')
        assert '/' not in slug and '\\' not in slug and ':' not in slug


class TestCanonicalSlugify:
    @pytest.mark.xfail(strict=True, reason="B10: no canonical slugify in sonne.utils.text yet")
    def test_canonical_module_exists_and_matches_blog_semantics(self):
        from sonne.utils.text import slugify
        assert slugify('Hello World!') == 'hello-world'
        assert slugify('snake_case_tag') == 'snake_case_tag'
        assert slugify('Hello World!') == blog_slugify('Hello World!')
        assert slugify('snake_case_tag') == blog_slugify('snake_case_tag')

    @pytest.mark.xfail(strict=True, reason="B10: Jinja slugify filter diverges from blog slugifier")
    def test_jinja_filter_matches_blog_slugifier(self, site_factory):
        from sonne.core.config import Config
        from sonne.core.site_generator import SiteGenerator

        site = site_factory('blog')
        cfg = Config(base_dir=str(site))
        generator = SiteGenerator(cfg, base_dir=str(site))
        jinja_slugify = generator.template_processor.jinja_env.filters['slugify']
        for text in ['Hello World!', 'snake_case_tag', 'Tag With Spaces']:
            assert jinja_slugify(text) == blog_slugify(text)
