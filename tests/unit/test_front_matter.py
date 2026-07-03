"""Front matter extraction and markdown rendering characterization."""
import pytest

from sonne.core.config import Config
from sonne.core.site_generator import SiteGenerator


@pytest.fixture
def template_processor(site_factory):
    site = site_factory('minimal')
    cfg = Config(base_dir=str(site))
    return SiteGenerator(cfg, base_dir=str(site)).template_processor


class TestExtractFrontMatter:
    def test_yaml_front_matter(self, template_processor):
        fm, body = template_processor.extract_front_matter(
            '---\ntitle: Test\ntags:\n  - a\n---\nBody text\n'
        )
        assert fm == {'title': 'Test', 'tags': ['a']}
        assert body.strip() == 'Body text'

    def test_no_front_matter_returns_empty_dict(self, template_processor):
        fm, body = template_processor.extract_front_matter('Just content\n')
        assert fm == {}
        assert body == 'Just content\n'

    def test_date_parsed_as_date_object(self, template_processor):
        fm, _ = template_processor.extract_front_matter(
            '---\ndate: 2025-02-01\n---\nx\n'
        )
        assert fm['date'].year == 2025 and fm['date'].month == 2


class TestProcessMarkdown:
    def test_markdown_rendered_to_html(self, template_processor):
        _, html = template_processor.process_markdown('**bold** text')
        assert '<strong>bold</strong>' in html

    def test_static_image_paths_rewritten(self, template_processor):
        # Pinned behavior: /static/images/ refs become /images/
        _, html = template_processor.process_markdown('![x](/static/images/a.png)')
        assert '/static/images/' not in html
