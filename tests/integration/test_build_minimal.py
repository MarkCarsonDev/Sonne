"""Full builds of the minimal fixture site."""

import logging


class TestMinimalBuild:
    def test_build_produces_pages(self, site_factory, builder):
        site = site_factory("minimal")
        _, out = builder(site)
        index = out / "index.html"
        about = out / "about" / "index.html"  # url_style: directory
        assert index.exists()
        assert about.exists()
        assert "My Minimal Site" in index.read_text(encoding="utf-8")

    def test_static_files_copied(self, site_factory, builder):
        site = site_factory("minimal")
        _, out = builder(site)
        assert (out / "css" / "style.css").exists()

    def test_no_dithering_assets_when_dither_disabled(self, site_factory, builder):
        site = site_factory("minimal")  # minimal config sets images.dither: false
        _, out = builder(site)
        assert not (out / "css" / "dithering.css").exists()
        assert not (out / "js" / "dithering.js").exists()

    def test_output_collision_warns(self, site_factory, caplog, builder):
        site = site_factory("minimal")
        nested = site / "content" / "about"
        nested.mkdir()
        (nested / "index.md").write_text(
            "---\ntitle: Nested\n---\nNested about\n", encoding="utf-8"
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            builder(site)
        assert any("collide" in r.message.lower() for r in caplog.records)
