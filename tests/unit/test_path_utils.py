"""sonne.utils.path_utils characterization + the B7 relative-prefix helper."""

import pytest

from sonne.utils.path_utils import (
    is_sonne_directory,
    normalize_web_path,
    sanitize_filename,
    validate_path_within_root,
)


class TestSanitizeFilename:
    def test_path_separators_replaced(self):
        assert "/" not in sanitize_filename("a/b")
        assert "\\" not in sanitize_filename("a\\b")

    def test_parent_refs_cannot_traverse(self):
        # Separators are replaced and leading dots stripped, so the result
        # is a single name that cannot climb out of its directory.
        sanitized = sanitize_filename("../../etc/passwd")
        assert "/" not in sanitized and "\\" not in sanitized
        assert not sanitized.startswith(".")

    @pytest.mark.parametrize("name", ["..", ".", "...", " .. "])
    def test_dot_only_names_become_unnamed(self, name):
        assert sanitize_filename(name) == "unnamed"

    def test_double_dots_inside_a_name_are_kept(self):
        assert sanitize_filename("v1..2.txt") == "v1..2.txt"

    def test_windows_reserved_names_prefixed(self):
        assert sanitize_filename("CON.txt") != "CON.txt"

    def test_empty_becomes_unnamed(self):
        assert sanitize_filename("") == "unnamed"


class TestIsSonneDirectory:
    def test_true_with_config_file(self, tmp_path):
        (tmp_path / "sonne.yaml").write_text("site: {}\n", encoding="utf-8")
        assert is_sonne_directory(tmp_path)

    def test_true_with_only_content_dir(self, tmp_path):
        # Pinned current behavior: a bare content/ dir counts as a project.
        (tmp_path / "content").mkdir()
        assert is_sonne_directory(tmp_path)

    def test_false_for_empty_dir(self, tmp_path):
        assert not is_sonne_directory(tmp_path)


class TestPathValidation:
    def test_inside_root(self, tmp_path):
        child = tmp_path / "a" / "b"
        child.mkdir(parents=True)
        assert validate_path_within_root(child, tmp_path)

    def test_outside_root(self, tmp_path):
        assert not validate_path_within_root(tmp_path.parent, tmp_path)


class TestNormalizeWebPath:
    def test_backslashes_converted(self):
        assert normalize_web_path("a\\b\\c.png") == "a/b/c.png"

    def test_double_slashes_collapsed(self):
        assert normalize_web_path("a//b") == "a/b"


class TestStripRelativePrefix:
    def test_helper_preserves_parent_refs_and_dotfiles(self):
        from sonne.utils.path_utils import strip_relative_prefix

        assert strip_relative_prefix("./images/a.jpg") == "images/a.jpg"
        assert strip_relative_prefix("././x.png") == "x.png"
        assert strip_relative_prefix("../images/a.jpg") == "../images/a.jpg"
        assert strip_relative_prefix(".hidden/a.jpg") == ".hidden/a.jpg"
        assert strip_relative_prefix("images/a.jpg") == "images/a.jpg"


class TestIsPostLocalRasterImage:
    @pytest.mark.parametrize(
        "src", ["photo.png", "./images/a.jpg", "../shared/b.webp", "img/c.JPG", "d.png?v=2"]
    )
    def test_relative_raster_images_qualify(self, src):
        from sonne.utils.path_utils import is_post_local_raster_image

        assert is_post_local_raster_image(src)

    @pytest.mark.parametrize(
        "src",
        [
            "",
            "https://example.com/a.png",
            "http://example.com/a.png",
            "//cdn.example.com/a.png",
            "/images/static.png",
            "data:image/png;base64,AAAA",
            "blob:https://example.com/1",
            "logo.svg",
            "LOGO.SVG",
            "icon.svg?v=3",
            "icon.svg#frag",
        ],
    )
    def test_everything_else_does_not(self, src):
        from sonne.utils.path_utils import is_post_local_raster_image

        assert not is_post_local_raster_image(src)


class TestValidatePathWithinRootErrors:
    def test_os_error_while_resolving_means_not_within(self, tmp_path, monkeypatch):
        from pathlib import Path

        def failing_resolve(self, strict=False):
            raise OSError("device not ready")

        monkeypatch.setattr(Path, "resolve", failing_resolve)

        assert validate_path_within_root(tmp_path / "a", tmp_path) is False
