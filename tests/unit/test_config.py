"""Characterization + regression tests for sonne.core.config."""

import copy

import pytest
import yaml

import sonne.core.config as config_module
from sonne.core.config import Config


def write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


class TestGetSet:
    def test_defaults_without_config_file(self, tmp_path):
        cfg = Config(base_dir=str(tmp_path))
        assert cfg.config_path is None
        assert cfg.get("site", "title") == "My Sonne Site"
        assert cfg.get("blog", "posts_per_page") == 10
        assert cfg.get("does", "not", "exist", default=5) == 5

    def test_set_creates_nested_keys(self, tmp_path):
        cfg = Config(base_dir=str(tmp_path))
        cfg.set("custom", "nested", "key", value=1)
        assert cfg.get("custom", "nested", "key") == 1

    def test_user_config_overrides_defaults(self, tmp_path):
        write_yaml(tmp_path / "sonne.yaml", {"site": {"title": "Override"}})
        cfg = Config(base_dir=str(tmp_path))
        assert cfg.get("site", "title") == "Override"
        # untouched defaults survive the merge
        assert cfg.get("site", "language") == "en"


class TestConfigDiscovery:
    def test_finds_config_in_base_dir(self, tmp_path):
        write_yaml(tmp_path / "sonne.yaml", {"site": {"title": "Here"}})
        cfg = Config(base_dir=str(tmp_path))
        assert cfg.config_path and cfg.config_path.endswith("sonne.yaml")

    def test_finds_config_in_parent_dir(self, tmp_path):
        # Current (pinned) behavior: config discovery walks up parent dirs.
        write_yaml(tmp_path / "sonne.yaml", {"site": {"title": "Parent"}})
        sub = tmp_path / "sub"
        sub.mkdir()
        cfg = Config(base_dir=str(sub))
        assert cfg.get("site", "title") == "Parent"


class TestUrlStyle:
    def test_default_environment_is_prod_clean(self, tmp_path):
        cfg = Config(base_dir=str(tmp_path))
        assert cfg.get_url_style() == "clean"

    def test_dev_environment_uses_directory(self, tmp_path):
        cfg = Config(base_dir=str(tmp_path))
        cfg.set("environment", value="dev")
        assert cfg.get_url_style() == "directory"

    @pytest.mark.parametrize(
        "style,url,expected",
        [
            ("html", "/about", "/about.html"),
            ("html", "/about/", "/about/index.html"),
            ("directory", "/about", "/about/"),
            ("clean", "/about/", "/about"),
            ("clean", "/", "/"),
        ],
    )
    def test_format_url(self, tmp_path, style, url, expected):
        cfg = Config(base_dir=str(tmp_path))
        cfg.set("url_style", value=style)
        assert cfg.format_url(url) == expected

    def test_external_urls_untouched(self, tmp_path):
        cfg = Config(base_dir=str(tmp_path))
        assert cfg.format_url("https://example.com/x") == "https://example.com/x"


class TestKnownBugs:
    def test_loading_config_does_not_mutate_defaults(self, tmp_path):
        write_yaml(
            tmp_path / "sonne.yaml",
            {
                "images": {"sizes": [100]},
                "site": {"keywords": ["x"]},
            },
        )
        snapshot = copy.deepcopy(config_module.DEFAULT_CONFIG)
        Config(base_dir=str(tmp_path))
        assert config_module.DEFAULT_CONFIG == snapshot

    def test_user_formats_list_replaces_default(self, tmp_path):
        write_yaml(tmp_path / "sonne.yaml", {"images": {"formats": ["png"]}})
        cfg = Config(base_dir=str(tmp_path))
        assert cfg.get("images", "formats") == ["png"]

    def test_validate_rejects_zero_posts_per_page(self, tmp_path):
        cfg = Config(base_dir=str(tmp_path))
        cfg.set("blog", "posts_per_page", value=0)
        assert any("posts_per_page" in w for w in cfg.validate())

    def test_deprecated_key_names_are_aliased(self, tmp_path):
        write_yaml(
            tmp_path / "sonne.yaml",
            {
                "images": {"parallel_processing": False, "max_workers": 2},
            },
        )
        import sonne.core.deprecations  # noqa: F401  (must exist)

        cfg = Config(base_dir=str(tmp_path))
        assert cfg.get("images", "parallel") is False
        assert cfg.get("images", "parallel_workers") == 2
