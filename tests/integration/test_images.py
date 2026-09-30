"""Image pipeline: resizing, dithering, only_used, cache keys."""

import logging
import re
from pathlib import Path

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


DITHER_ON = {("images", "dither"): True}


class TestStaticImages:
    """static/images: the original at its own URL, a dithered PNG in dithered/."""

    def test_original_keeps_its_url_and_dithered_png_sits_beside_it(
        self, site_factory, builder, image_factory
    ):
        site = site_factory("blog", overlay="blog_site")
        source = image_factory(site / "static" / "images" / "vogel.jpg", size=(32, 32), fmt="JPEG")

        _, out = builder(site, config_overrides=DITHER_ON)

        assert (out / "images" / "vogel.jpg").read_bytes() == source.read_bytes()
        with Image.open(out / "images" / "dithered" / "vogel.png") as dithered:
            assert dithered.format == "PNG"

    def test_legacy_original_copy_is_still_written(self, site_factory, builder, image_factory):
        # Compatibility bridge for pages and links from before this layout;
        # remove this test together with the bridge in Sonne 0.5.0.
        site = site_factory("blog", overlay="blog_site")
        source = image_factory(site / "static" / "images" / "vogel.jpg", size=(32, 32), fmt="JPEG")

        _, out = builder(site, config_overrides=DITHER_ON)

        assert (out / "images" / "vogel_original.jpg").read_bytes() == source.read_bytes()

    def test_skip_cache_reprocesses_static_images(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        generator, out = builder(site, config_overrides=DITHER_ON)
        target = out / "images" / "dithered" / "logo.png"
        target.write_bytes(b"stale")
        generator.image_processor.process_all(generator.paths["content"], skip_cache=True)
        assert target.read_bytes() != b"stale"

    def test_rebuild_keeps_the_dithered_copy_and_registers_it(
        self, site_factory, builder, image_factory
    ):
        site = site_factory("blog", overlay="blog_site")
        source = image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        builder(site, config_overrides=DITHER_ON)

        generator, out = builder(site, config_overrides=DITHER_ON)  # warm cache

        assert (out / "images" / "logo.png").read_bytes() == source.read_bytes()
        assert (out / "images" / "dithered" / "logo.png").is_file()
        assert generator.image_processor.dithered_images.pair_for("/images/logo.png") == (
            "/images/logo.png",
            "/images/dithered/logo.png",
        )


class TestDitheredImageRegistry:
    """The registry holds exactly the images the build dithered."""

    def test_static_and_content_variant_pairs_are_registered(
        self, site_factory, builder, image_factory
    ):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))

        generator, _ = builder(site, config_overrides=DITHER_ON)

        registry = generator.image_processor.dithered_images
        assert registry.pair_for("/images/dithered/logo.png") == (
            "/images/logo.png",
            "/images/dithered/logo.png",
        )
        assert registry.pair_for("/assets/images/photo_400.webp") == (
            "/assets/images/photo_400_original.webp",
            "/assets/images/photo_400.webp",
        )

    def test_nothing_is_registered_without_dithering(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")

        generator, out = builder(site, config_overrides={("images", "dither"): False})

        assert len(generator.image_processor.dithered_images) == 0
        assert (out / "images" / "logo.png").is_file()
        assert not (out / "images" / "dithered").exists()

    def test_image_that_fails_to_dither_is_not_registered(
        self, site_factory, builder, image_factory
    ):
        site = site_factory("blog", overlay="blog_site")
        broken = site / "static" / "images" / "broken.png"
        broken.parent.mkdir(parents=True, exist_ok=True)
        broken.write_bytes(b"not really a png")

        generator, out = builder(site, config_overrides=DITHER_ON)

        assert generator.image_processor.dithered_images.pair_for("/images/broken.png") is None
        assert (out / "images" / "broken.png").read_bytes() == b"not really a png"


class TestStaticFileOwnership:
    """Which static files the image pipeline writes (so the static copy must skip them)."""

    def processor(self, site_factory, builder, config_overrides=None):
        site = site_factory("blog", overlay="blog_site")
        for rel_path in ["images/a.png", "images/sub/b.jpg", "images/icon.svg", "css/c.png"]:
            (site / "static" / rel_path).parent.mkdir(parents=True, exist_ok=True)
            (site / "static" / rel_path).write_bytes(b"x")
        (site / "static" / "images" / ".hidden").mkdir()
        (site / "static" / "images" / ".hidden" / "d.png").write_bytes(b"x")
        generator, _ = builder(site, config_overrides=config_overrides, skip_images=True)
        return generator.image_processor, site / "static"

    def test_raster_images_under_static_images_are_owned(self, site_factory, builder):
        processor, static = self.processor(site_factory, builder)
        assert processor.owns_static_file(str(static / "images" / "a.png"))
        assert processor.owns_static_file(str(static / "images" / "sub" / "b.jpg"))

    def test_other_static_files_are_not_owned(self, site_factory, builder):
        processor, static = self.processor(site_factory, builder)
        for rel_path in ["images/icon.svg", "css/c.png", "images/.hidden/d.png"]:
            assert not processor.owns_static_file(str(static / rel_path)), rel_path

    def test_unreferenced_images_are_not_owned_with_only_used(self, site_factory, builder):
        processor, static = self.processor(site_factory, builder, {("images", "only_used"): True})
        assert not processor.owns_static_file(str(static / "images" / "a.png"))


class TestImageDiscovery:
    def test_uppercase_extensions_are_processed(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "CAMERA.JPG", size=(64, 64), fmt="JPEG")
        _, out = builder(site)
        assert (out / "assets" / "images" / "CAMERA_400_original.webp").exists()


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


class TestBuildStatistics:
    def build(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        overrides = {("images", "dither"): True}
        generator, _ = builder(site, config_overrides=overrides)
        return site, overrides, generator.stats

    def test_first_build_counts_processed_images_as_cache_misses(
        self, site_factory, builder, image_factory
    ):
        _, _, stats = self.build(site_factory, builder, image_factory)
        assert stats.images_processed >= 2
        assert (stats.images_cached, stats.cache_misses) == (0, stats.images_processed)

    def test_rebuild_counts_cached_images_as_cache_hits(self, site_factory, builder, image_factory):
        site, overrides, _ = self.build(site_factory, builder, image_factory)
        generator, _ = builder(site, config_overrides=overrides)
        stats = generator.stats
        assert stats.images_cached >= 2
        assert (stats.images_processed, stats.cache_hits) == (0, stats.images_cached)

    def test_static_image_sizes_are_recorded(self, site_factory, builder, image_factory):
        _, _, stats = self.build(site_factory, builder, image_factory)
        assert stats.original_image_size > 0
        assert stats.processed_image_size > 0


class TestImageWorkload:
    """images_to_process() is exactly what process_all() handles."""

    def site(self, site_factory, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        for hidden_name in ("hidden.jpg", "hidden2.jpg"):
            image_factory(site / "content" / ".drafts" / hidden_name, size=(64, 64))
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        (site / "static" / "images" / "icon.svg").write_text("<svg/>", encoding="utf-8")
        return site

    def test_lists_content_then_static_images_skipping_hidden_and_non_raster(
        self, site_factory, builder, image_factory
    ):
        site = self.site(site_factory, image_factory)
        generator, _ = builder(site, skip_images=True)

        images = generator.image_processor.images_to_process(generator.paths["content"])

        assert [Path(p).name for p in images.content] == ["photo.jpg"]
        assert [Path(p).name for p in images.static] == ["logo.png"]

    def test_only_used_leaves_out_unreferenced_images(self, site_factory, builder, image_factory):
        site = self.site(site_factory, image_factory)
        generator, _ = builder(site, {("images", "only_used"): True}, skip_images=True)

        images = generator.image_processor.images_to_process(generator.paths["content"])

        assert len(images) == 0

    def test_build_processes_exactly_the_listed_images(self, site_factory, builder, image_factory):
        site = self.site(site_factory, image_factory)
        generator, _ = builder(site, {("images", "dither"): True})

        images = generator.image_processor.images_to_process(generator.paths["content"])

        assert generator.stats.images_processed == len(images) == 2

    def test_progress_line_counts_the_images_processed(
        self, site_factory, builder, image_factory, caplog
    ):
        site = self.site(site_factory, image_factory)

        with caplog.at_level(logging.INFO, logger="sonne"):
            builder(site)

        assert any("Processing images  (2 images," in r.message for r in caplog.records)


class TestPagesShowDitheredImages:
    """Built pages point dithered images at the dithered copy and record the original."""

    PAGE = (
        "---\ntitle: Gallery\n---\n"
        "![logo](/images/logo.png)\n\n"
        '<img src="/images/icon.svg" alt="icon">\n\n'
        '<img src="/assets/images/photo_400.webp" alt="photo">\n'
    )

    def build(self, site_factory, builder, image_factory):
        site = site_factory("blog", overlay="blog_site")
        image_factory(site / "static" / "images" / "logo.png", size=(32, 32), fmt="PNG")
        (site / "static" / "images" / "icon.svg").write_text("<svg/>", encoding="utf-8")
        image_factory(site / "content" / "blog" / "photo.jpg", size=(64, 64))
        (site / "content" / "gallery.md").write_text(self.PAGE, encoding="utf-8")
        _, out = builder(site, config_overrides=DITHER_ON)
        page = next((out / "gallery").rglob("index.html"))
        return out, page.read_text(encoding="utf-8")

    def img_tag(self, html, alt):
        match = re.search(rf'<img[^>]*alt="{alt}"[^>]*>', html)
        assert match, f"no <img alt={alt!r}> in page"
        return match.group(0)

    def test_static_image_is_marked(self, site_factory, builder, image_factory):
        _out, html = self.build(site_factory, builder, image_factory)

        tag = self.img_tag(html, "logo")
        assert 'src="/images/dithered/logo.png"' in tag
        assert 'data-original-src="/images/logo.png"' in tag

    def test_sized_variant_is_marked(self, site_factory, builder, image_factory):
        _out, html = self.build(site_factory, builder, image_factory)

        tag = self.img_tag(html, "photo")
        assert 'src="/assets/images/photo_400.webp"' in tag
        assert 'data-original-src="/assets/images/photo_400_original.webp"' in tag

    def test_image_the_build_did_not_dither_is_not_marked(
        self, site_factory, builder, image_factory
    ):
        _out, html = self.build(site_factory, builder, image_factory)

        assert "data-original-src" not in self.img_tag(html, "icon")

    def test_every_marked_url_is_a_real_file(self, site_factory, builder, image_factory):
        out, html = self.build(site_factory, builder, image_factory)

        urls = re.findall(r'(?:src|data-original-src)="(/[^"]+)"', html)
        assert urls
        missing = [url for url in urls if not (out / url.lstrip("/")).is_file()]
        assert missing == []
