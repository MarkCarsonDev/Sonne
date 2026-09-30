"""Page-size labels injected into generated HTML (build.show_page_size)."""

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
    @pytest.mark.xfail(strict=True, reason="B49: label inserted before the first </body>")
    def test_label_goes_before_the_closing_body_tag(self, output_dir):
        script = "<script>var html = '</body>';</script>"

        html = labelled(output_dir, script)

        assert script in html
        assert html.endswith("</span></body></html>")


class TestImageWeight:
    def test_local_image_counts_toward_full_size(self, output_dir):
        html = labelled(output_dir, '<img src="/images/a.png">')

        assert 'KB with images"' in html

    @pytest.mark.xfail(strict=True, reason="B49: image src with a query string is ignored")
    def test_query_string_is_ignored_when_locating_the_image(self, output_dir):
        html = labelled(output_dir, '<img src="/images/a.png?v=2">')

        assert 'KB with images"' in html

    @pytest.mark.xfail(strict=True, reason="B49: percent-encoded image src not decoded")
    def test_percent_encoded_src_is_decoded(self, output_dir):
        html = labelled(output_dir, '<img src="/images/my%20pic.png">')

        assert 'KB with images"' in html
