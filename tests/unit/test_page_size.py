"""Page-size labels injected into generated HTML (build.show_page_size)."""

import re

import pytest

from sonne.utils.page_size import inject_page_size_labels

IMAGE_BYTES = 5000


@pytest.fixture
def output_dir(tmp_path):
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.png").write_bytes(b"\0" * IMAGE_BYTES)
    (images / "my pic.png").write_bytes(b"\0" * IMAGE_BYTES)
    return tmp_path


def labelled(output_dir, body):
    page = output_dir / "page.html"
    page.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    inject_page_size_labels(str(output_dir))
    return page.read_text(encoding="utf-8")


class TestLabelPlacement:
    def test_label_goes_before_the_closing_body_tag(self, output_dir):
        script = "<script>var html = '</body>';</script>"

        html = labelled(output_dir, script)

        assert script in html
        assert html.endswith("</p></aside></body></html>")


class TestImageWeight:
    def test_local_image_counts_toward_full_size(self, output_dir):
        html = labelled(output_dir, '<img src="/images/a.png">')

        assert "KB with images)" in html

    def test_query_string_is_ignored_when_locating_the_image(self, output_dir):
        html = labelled(output_dir, '<img src="/images/a.png?v=2">')

        assert "KB with images)" in html

    def test_percent_encoded_src_is_decoded(self, output_dir):
        html = labelled(output_dir, '<img src="/images/my%20pic.png">')

        assert "KB with images)" in html


class TestLabelAccessibility:
    """Readable without hover, named, and in the page flow (WCAG 1.4.3, 1.4.10, 1.4.13)."""

    def test_full_text_is_shown_without_hover(self, output_dir):
        html = labelled(output_dir, '<img src="/images/a.png">')

        assert re.search(r"<p>Page size: ~[0-9.]+ KB \(~[0-9]+ KB with images\)</p>", html)
        assert "data-full" not in html
        assert ":hover" not in html

    def test_label_is_a_named_region_in_the_page_flow(self, output_dir):
        html = labelled(output_dir, "<p>Content</p>")

        assert '<aside id="page-size-label" aria-label="Page size"' in html
        for covering in ("position", "opacity", "z-index"):
            assert covering not in html
