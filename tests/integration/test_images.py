"""Image pipeline: resizing, dithering, only_used, cache keys."""

import logging

from PIL import Image

from sonne.core.config import Config
from sonne.processors.image_processor import ImageProcessor


class TestContentImages:
    def test_content_image_resized_to_configured_outputs(
        self, site_factory, builder, image_factory
    ):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        _, out = builder(site)
        assets = out / "assets" / "images"
        # blog template config: formats [webp, jpg], sizes [1200, 800, 400]
        assert (assets / "photo_400_original.webp").exists()
        assert (assets / "photo_400_original.jpg").exists()

    def test_dithered_variant_written_when_dither_enabled(
        self, site_factory, builder, image_factory
    ):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        _, out = builder(site, config_overrides={("images", "dither"): True})
        # dithered output is written at the smallest size, webp by default
        assert (out / "assets" / "images" / "photo_400.webp").exists()

    def test_no_dithered_variant_when_dither_disabled(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")  # config has dither: false
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        _, out = builder(site)
        assert not (out / "assets" / "images" / "photo_400.webp").exists()

    def test_changing_dither_settings_busts_cache(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        img = image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        generator, out = builder(site, config_overrides={("images", "dither"): True})
        dithered = out / "assets" / "images" / "photo_400.webp"
        assert dithered.exists()
        dithered.unlink()
        # Same processor instance, changed dithering settings -> must reprocess
        generator.config.set("images", "dither_colors", value=2)
        generator.image_processor.process_image(str(img))
        assert dithered.exists()


class TestCleanRebuild:
    def test_clean_output_with_warm_cache_regenerates_images(
        self, site_factory, builder, image_factory
    ):
        # `sonne build --clean` wipes output but keeps .cache; a cache hit
        # must verify outputs exist or clean rebuilds lose every image.
        import shutil

        from sonne.core.config import Config
        from sonne.core.site_generator import SiteGenerator

        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        _, out = builder(site)
        target = out / "assets" / "images" / "photo_400_original.webp"
        assert target.exists()

        shutil.rmtree(out)  # what --clean does
        cfg = Config(base_dir=str(site))
        SiteGenerator(cfg, base_dir=str(site)).generate()  # warm cache, no skip_cache
        assert target.exists()


class TestOnlyUsed:
    def test_referenced_static_image_still_processed(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32))
        index = site / "content" / "index.md"
        index.write_text(
            index.read_text(encoding="utf-8") + "\n![logo](/images/logo.png)\n",
            encoding="utf-8",
        )
        _, out = builder(
            site,
            config_overrides={
                ("images", "only_used"): True,
                ("images", "dither"): True,
            },
        )
        # static-image processing writes an _original copy alongside the dithered main file
        assert (out / "images" / "logo_original.png").exists()

    def test_unreferenced_content_image_skipped(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "unused.jpg", size=(32, 32))
        _, out = builder(site, config_overrides={("images", "only_used"): True})
        assert not (out / "assets" / "images" / "unused_400_original.webp").exists()


def _add_image_to_post(site, markdown):
    post = site / "content" / "blog" / "2025-02-01-hello-world.md"
    post.write_text(post.read_text(encoding="utf-8") + f"\n{markdown}\n", encoding="utf-8")


def _post_copy(out, name):
    """The copy of a post-relative image written beside the post (not the dithered variant or asset renditions)."""
    found = [
        path
        for path in out.rglob(name)
        if "dithered" not in path.parts and "assets" not in path.parts
    ]
    assert len(found) == 1, found
    return found[0]


class TestPostImageFormats:
    """Post-relative images are resized and saved beside the post in their own format."""

    def test_png_stays_png(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "chart.png", size=(64, 64), fmt="PNG")
        _add_image_to_post(site, "![chart](chart.png)")
        _, out = builder(site)
        with Image.open(_post_copy(out, "chart.png")) as saved:
            assert saved.format == "PNG"

    def test_wide_png_with_transparency_is_resized_and_stays_png(self, site_factory, builder):
        site = site_factory("blog", overlay="blog_site")
        Image.new("RGBA", (2000, 40), (20, 120, 200, 128)).save(
            site / "content" / "blog" / "wide.png", format="PNG"
        )
        _add_image_to_post(site, "![wide](wide.png)")
        _, out = builder(site)
        with Image.open(_post_copy(out, "wide.png")) as saved:
            assert (saved.format, saved.mode, saved.width) == ("PNG", "RGBA", 1600)

    def test_jpeg_stays_jpeg(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        _add_image_to_post(site, "![photo](photo.jpg)")
        _, out = builder(site)
        with Image.open(_post_copy(out, "photo.jpg")) as saved:
            assert saved.format == "JPEG"


class TestStaticImages:
    def test_static_jpeg_is_dithered_in_place(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        source = image_factory(site / "static" / "images" / "vogel.jpg", size=(32, 32), fmt="JPEG")
        _, out = builder(site, config_overrides={("images", "dither"): True})
        dithered = out / "images" / "vogel.jpg"
        with Image.open(dithered) as saved:
            assert saved.format == "JPEG"
        # A failed dither falls back to copying the source unchanged
        assert dithered.read_bytes() != source.read_bytes()

    def test_skip_cache_reprocesses_static_images(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        generator, out = builder(site, config_overrides={("images", "dither"): True})
        target = out / "images" / "logo.png"
        target.write_bytes(b"stale")
        generator.image_processor.process_all(generator.paths["content"], skip_cache=True)
        assert target.read_bytes() != b"stale"


class TestSiteLocation:
    def test_site_inside_dot_directory_processes_images(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site", name=".sites/blog")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        _, out = builder(site)
        assert (out / "assets" / "images" / "photo_400_original.webp").exists()


class TestUnknownDitherMethod:
    def processor(self):
        config = Config()
        config.set("images", "dither_method", value="bogus")
        config.set("images", "dither_colors", value=2)
        return ImageProcessor(config, {})

    def test_fallback_uses_configured_colors(self):
        processor = self.processor()
        gradient = Image.linear_gradient("L").resize((32, 32))
        expected = processor._apply_dither(gradient, "bayer", 2)
        assert processor.dither(gradient).tobytes() == expected.tobytes()

    def test_warns_once_naming_method_and_fallback(self, caplog):
        processor = self.processor()
        image = Image.new("RGB", (8, 8))
        with caplog.at_level(logging.WARNING, logger="sonne"):
            processor.dither(image)
            processor.dither(image)
        warnings = [r.message for r in caplog.records if "bogus" in r.message]
        assert len(warnings) == 1 and "bayer" in warnings[0]
