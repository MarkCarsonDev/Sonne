"""BlogProcessor helpers that need no site build."""

from datetime import datetime
from types import SimpleNamespace

import pytest

import sonne.processors.blog_processor as blog_processor


class TestFileCreationTime:
    @pytest.mark.xfail(strict=True, reason="B37: Windows < 3.12 used mtime, not creation time")
    def test_windows_without_birthtime_uses_ctime(self, monkeypatch):
        monkeypatch.setattr(blog_processor.os, "name", "nt")
        stat = SimpleNamespace(st_mtime=200.0, st_ctime=100.0)

        assert blog_processor._file_created_at(stat) == datetime.fromtimestamp(100.0)

    @pytest.mark.xfail(strict=True, reason="B37: helper introduced with the fix")
    def test_posix_without_birthtime_uses_mtime(self, monkeypatch):
        # On POSIX st_ctime is the metadata-change time, not creation time.
        monkeypatch.setattr(blog_processor.os, "name", "posix")
        stat = SimpleNamespace(st_mtime=200.0, st_ctime=100.0)

        assert blog_processor._file_created_at(stat) == datetime.fromtimestamp(200.0)

    @pytest.mark.xfail(strict=True, reason="B37: helper introduced with the fix")
    def test_birthtime_wins_when_available(self):
        stat = SimpleNamespace(st_birthtime=50.0, st_mtime=200.0, st_ctime=100.0)

        assert blog_processor._file_created_at(stat) == datetime.fromtimestamp(50.0)
