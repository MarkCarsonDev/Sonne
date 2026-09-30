"""BlogProcessor helpers that need no site build."""

from datetime import datetime
from types import SimpleNamespace

import pytest

import sonne.processors.blog_processor as blog_processor


class TestFileCreationTime:
    def test_windows_without_birthtime_uses_ctime(self, monkeypatch):
        monkeypatch.setattr(blog_processor.os, "name", "nt")
        stat = SimpleNamespace(st_mtime=200.0, st_ctime=100.0)

        assert blog_processor._file_created_at(stat) == datetime.fromtimestamp(100.0)

    def test_posix_without_birthtime_uses_mtime(self, monkeypatch):
        # On POSIX st_ctime is the metadata-change time, not creation time.
        monkeypatch.setattr(blog_processor.os, "name", "posix")
        stat = SimpleNamespace(st_mtime=200.0, st_ctime=100.0)

        assert blog_processor._file_created_at(stat) == datetime.fromtimestamp(200.0)

    def test_birthtime_wins_when_available(self):
        stat = SimpleNamespace(st_birthtime=50.0, st_mtime=200.0, st_ctime=100.0)

        assert blog_processor._file_created_at(stat) == datetime.fromtimestamp(50.0)


# Each case holds one image, ![x](probe.png); the renderer decides whether it
# is a real image or code sample text, and _without_code must agree.
INDENTATION_CASES = {
    "indented code after paragraph": "Para.\n\n    ![x](probe.png)\n\nAfter.\n",
    "tab-indented code": "Para.\n\n\t![x](probe.png)\n",
    "code at document start": "    ![x](probe.png)\n",
    "list item continuation": "- item\n\n    ![x](probe.png)\n\nAfter.\n",
    "numbered list continuation": "1. item\n\n    ![x](probe.png)\n",
    "code nested in list": "- item\n\n        ![x](probe.png)\n",
    "lazy continuation line": "Para\n    ![x](probe.png)\n",
    "paragraph after list": "- item\n\nText\n\n    ![x](probe.png)\n",
    "plain image": "![x](probe.png)\n",
    "fence closed by a longer fence": "```\ncode\n````\n![x](probe.png)\n```\n",
}


class TestCodeDetectionMatchesRenderer:
    @pytest.mark.parametrize("source", INDENTATION_CASES.values(), ids=INDENTATION_CASES.keys())
    def test_image_is_kept_exactly_when_rendered(self, source):
        import markdown

        from sonne.processors.template_processor import MARKDOWN_PARSER_EXTENSIONS

        rendered_as_image = "<img" in markdown.markdown(
            source, extensions=MARKDOWN_PARSER_EXTENSIONS
        )

        assert ("probe.png" in blog_processor._without_code(source)) == rendered_as_image
