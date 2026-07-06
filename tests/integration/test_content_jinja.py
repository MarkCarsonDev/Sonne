"""Content Jinja rendering (plan 01): opt-in, overrides, script extensions."""

import logging

import pytest


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def jinja_site(site_factory):
    """Minimal site with a data script providing a var, a global, a filter."""
    site = site_factory("minimal")
    write(
        site / "scripts" / "ext.py",
        "sonne_var('color', 'teal')\n"
        "sonne_global('double', lambda x: x * 2)\n"
        "sonne_filter('shout', lambda s: str(s).upper())\n",
    )
    return site


class TestDefaults:
    def test_braces_render_literally_by_default(self, jinja_site, builder):
        write(
            jinja_site / "content" / "sample.md",
            "---\ntitle: Sample\n---\nColor is {{ color }}.\n",
        )
        _, out = builder(jinja_site)
        html = (out / "sample" / "index.html").read_text(encoding="utf-8")
        assert "{{ color }}" in html

    def test_legacy_markers_warn(self, jinja_site, builder, caplog):
        write(
            jinja_site / "content" / "old.md",
            "---\ntitle: Old\n---\nValue: {+}{color}\n",
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            builder(jinja_site)
        assert any("removed Sonne/Mond markers" in r.message for r in caplog.records)

    def test_removed_security_key_warns(self, site_factory, builder, caplog):
        site = site_factory("minimal")
        config = site / "sonne.yaml"
        config.write_text(
            config.read_text(encoding="utf-8") + "\nsecurity:\n  allow_embedded_python: true\n",
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            builder(site)
        assert any("no longer exists" in r.message for r in caplog.records)


class TestOptIn:
    def test_site_wide_rendering(self, jinja_site, builder):
        write(
            jinja_site / "content" / "sample.md",
            "---\ntitle: Sample\n---\n"
            "Color {{ color }}, doubled {{ double(3) }}, {{ 'hi'|shout }}, title {{ page.title }}.\n",
        )
        _, out = builder(jinja_site, config_overrides={("content", "render_jinja"): True})
        html = (out / "sample" / "index.html").read_text(encoding="utf-8")
        assert "Color teal" in html
        assert "doubled 6" in html
        assert "HI" in html
        assert "title Sample" in html

    def test_per_file_opt_in_overrides_site_off(self, jinja_site, builder):
        write(
            jinja_site / "content" / "sample.md",
            "---\ntitle: Sample\njinja: true\n---\nColor is {{ color }}.\n",
        )
        _, out = builder(jinja_site)  # site default: off
        html = (out / "sample" / "index.html").read_text(encoding="utf-8")
        assert "Color is teal" in html

    def test_per_file_opt_out_overrides_site_on(self, jinja_site, builder):
        write(
            jinja_site / "content" / "sample.md",
            "---\ntitle: Sample\njinja: false\n---\nColor is {{ color }}.\n",
        )
        _, out = builder(jinja_site, config_overrides={("content", "render_jinja"): True})
        html = (out / "sample" / "index.html").read_text(encoding="utf-8")
        assert "{{ color }}" in html

    def test_jinja_error_falls_back_and_logs(self, jinja_site, builder, caplog):
        write(
            jinja_site / "content" / "broken.md",
            "---\ntitle: Broken\njinja: true\n---\n{% if %}\n",
        )
        with caplog.at_level(logging.ERROR, logger="sonne"):
            _, out = builder(jinja_site)
        assert (out / "broken" / "index.html").exists()
        assert any("Jinja error in content" in r.message for r in caplog.records)


class TestBlogPosts:
    def test_post_sees_script_variables(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")
        write(site / "scripts" / "ext.py", "sonne_var('color', 'teal')\n")
        write(
            site / "content" / "blog" / "2025-06-01-jinja-post.md",
            "---\ntitle: Jinja Post\ndate: 2025-06-01\njinja: true\n---\n"
            "The color is {{ color }} and there are {{ all_blog_posts|length }} posts.\n",
        )
        _, out = builder(site)
        post = out / "blog" / "2025" / "06" / "01" / "jinja-post" / "index.html"
        html = post.read_text(encoding="utf-8")
        assert "The color is teal" in html
        assert "{{" not in html

    def test_auto_excerpt_has_no_jinja_markers(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")
        write(site / "scripts" / "ext.py", "sonne_var('color', 'teal')\n")
        write(
            site / "content" / "blog" / "2025-06-02-excerpt-check.md",
            "---\ntitle: Excerpt Check\ndate: 2025-06-02\njinja: true\n---\n"
            "Starts with {{ color }} and continues long enough to excerpt.\n",
        )
        _, out = builder(site)
        index_html = (out / "blog" / "index.html").read_text(encoding="utf-8")
        assert "Starts with teal" in index_html
        assert "{{ color }}" not in index_html


class TestFilterCollisions:
    def test_builtin_filter_not_overridden(self, jinja_site, builder, caplog):
        write(
            jinja_site / "scripts" / "clash.py",
            "sonne_filter('slugify', lambda s: 'HIJACKED')\n",
        )
        write(
            jinja_site / "content" / "sample.md",
            "---\ntitle: Sample\njinja: true\n---\n{{ 'A B'|slugify }}\n",
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            _, out = builder(jinja_site)
        html = (out / "sample" / "index.html").read_text(encoding="utf-8")
        assert "a-b" in html and "HIJACKED" not in html
        assert any("collides" in r.message for r in caplog.records)
