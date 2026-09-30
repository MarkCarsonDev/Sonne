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


def config_with(tmp_path, *settings):
    """A default Config with each (keys..., value) setting applied."""
    cfg = Config(base_dir=str(tmp_path))
    for *keys, value in settings:
        cfg.set(*keys, value=value)
    return cfg


class TestValidate:
    def test_defaults_are_valid(self, tmp_path):
        assert Config(base_dir=str(tmp_path)).validate() == []

    @pytest.mark.parametrize(
        "setting, expected",
        [
            (("site", {}), "Missing 'site' configuration section"),
            (("site", "title", ""), "Site title is not set"),
            (("site", "base_url", ""), "Site base_url is not set"),
            (("paths", {}), "Missing 'paths' configuration section"),
            (("paths", "templates", ""), "Required path 'templates' is not set"),
            (("images", "formats", "webp"), "images.formats should be a list"),
            (("images", "sizes", 800), "images.sizes should be a list"),
            (("images", "sizes", [800, -1]), "images.sizes should contain only positive integers"),
            (("blog", "directory", ""), "Blog is enabled but directory is not set"),
            (("blog", "template", ""), "Blog is enabled but template is not set"),
            (("blog", "posts_per_page", True), "blog.posts_per_page must be a positive integer"),
            (("serve", "port", 70000), "serve.port must be an integer between 0 and 65535"),
            (("serve", "port", "80"), "serve.port must be an integer between 0 and 65535"),
            (
                ("environment", "staging"),
                "environment 'staging' has no url_style entry; the 'clean' URL style will be used",
            ),
        ],
    )
    def test_each_problem_is_reported(self, tmp_path, setting, expected):
        assert config_with(tmp_path, setting).validate() == [expected]

    def test_disabled_blog_is_not_validated(self, tmp_path):
        cfg = config_with(tmp_path, ("blog", "enabled", False), ("blog", "directory", ""))

        assert cfg.validate() == []


class TestContentSecurityPolicy:
    def test_disabled_by_default(self, tmp_path):
        assert Config(base_dir=str(tmp_path)).get_csp_meta_tag() is None

    def test_enabled_without_directives_gives_nothing(self, tmp_path):
        cfg = config_with(tmp_path, ("security", "csp", "enabled", True))

        assert cfg.generate_csp_header() is None

    def test_list_directives_are_joined_and_invalid_ones_skipped(self, tmp_path):
        directives = {"default-src": ["'self'"], "img-src": ["'self'", "data:"], "bad": "x"}
        cfg = config_with(
            tmp_path,
            ("security", "csp", "enabled", True),
            ("security", "csp", "directives", directives),
        )

        assert cfg.get_csp_meta_tag() == (
            '<meta http-equiv="Content-Security-Policy" '
            "content=\"default-src 'self'; img-src 'self' data:\">"
        )


class TestSave:
    def test_unsupported_extension_leaves_existing_file_intact(self, tmp_path):
        target = tmp_path / "settings.toml"
        target.write_text("keep = true\n", encoding="utf-8")
        cfg = Config(base_dir=str(tmp_path))

        cfg.save(str(target))

        assert target.read_text(encoding="utf-8") == "keep = true\n"

    def test_yaml_round_trip(self, tmp_path):
        cfg = config_with(tmp_path, ("site", "title", "Saved"))
        target = tmp_path / "out" / "sonne.yaml"

        cfg.save(str(target))

        assert Config(str(target), base_dir=str(tmp_path)).get("site", "title") == "Saved"


class TestBlogDirectory:
    @pytest.mark.xfail(strict=True, reason="B45: blog.directory None/'' resolved inconsistently")
    @pytest.mark.parametrize("configured", [None, "", "blog", "posts", "posts/"])
    def test_one_resolution_of_the_blog_directory(self, tmp_path, configured):
        cfg = config_with(tmp_path, ("blog", "directory", configured))

        expected = "posts" if configured and configured.startswith("posts") else "blog"
        assert cfg.blog_directory() == expected

    @pytest.mark.xfail(strict=True, reason="B45: validate does not say which directory is used")
    def test_validate_says_empty_directory_falls_back(self, tmp_path):
        cfg = config_with(tmp_path, ("blog", "directory", ""))

        assert cfg.validate() == ["blog.directory is empty; using 'blog'"]


class TestSectionShapes:
    @pytest.mark.xfail(strict=True, reason="B46: a scalar where a mapping belongs is not flagged")
    @pytest.mark.parametrize("keys", [("images",), ("blog", "taxonomies"), ("serve",)])
    def test_scalar_for_a_mapping_section_warns(self, tmp_path, keys):
        cfg = config_with(tmp_path, (*keys, "yes"))

        assert f"{'.'.join(keys)} should be a mapping (got 'yes')" in cfg.validate()

    @pytest.mark.parametrize("value", [False, True])
    def test_rss_accepts_a_boolean(self, tmp_path, value):
        cfg = config_with(tmp_path, ("blog", "rss", value))

        assert cfg.validate() == []
