"""Image pipeline: resizing, dithering, only_used, cache keys."""
import pytest


class TestContentImages:
    def test_content_image_resized_to_configured_outputs(self, site_factory, builder, image_factory):
        site = site_factory('blog', overlay='blog_site')
        image_factory(site / 'content' / 'blog' / 'photo.jpg', size=(64, 64))
        _, out = builder(site)
        assets = out / 'assets' / 'images'
        # blog template config: formats [webp, jpg], sizes [1200, 800, 400]
        assert (assets / 'photo_400_original.webp').exists()
        assert (assets / 'photo_400_original.jpg').exists()

    def test_dithered_variant_written_when_dither_enabled(self, site_factory, builder, image_factory):
        site = site_factory('blog', overlay='blog_site')
        image_factory(site / 'content' / 'blog' / 'photo.jpg', size=(64, 64))
        _, out = builder(site, config_overrides={('images', 'dither'): True})
        # dithered output is written at the smallest size, webp by default
        assert (out / 'assets' / 'images' / 'photo_400.webp').exists()

    @pytest.mark.xfail(strict=True, reason="B3: images.dither=false ignored for content images")
    def test_no_dithered_variant_when_dither_disabled(self, site_factory, builder, image_factory):
        site = site_factory('blog', overlay='blog_site')  # config has dither: false
        image_factory(site / 'content' / 'blog' / 'photo.jpg', size=(64, 64))
        _, out = builder(site)
        assert not (out / 'assets' / 'images' / 'photo_400.webp').exists()

    @pytest.mark.xfail(strict=True, reason="B4: cache key omits dither settings; stale variants served")
    def test_changing_dither_settings_busts_cache(self, site_factory, builder, image_factory):
        site = site_factory('blog', overlay='blog_site')
        img = image_factory(site / 'content' / 'blog' / 'photo.jpg', size=(64, 64))
        generator, out = builder(site, config_overrides={('images', 'dither'): True})
        dithered = out / 'assets' / 'images' / 'photo_400.webp'
        assert dithered.exists()
        dithered.unlink()
        # Same processor instance, changed dithering settings -> must reprocess
        generator.config.set('images', 'dither_colors', value=2)
        generator.image_processor.process_image(str(img))
        assert dithered.exists()


class TestOnlyUsed:
    @pytest.mark.xfail(strict=True, reason="B5: only_used drops all /-prefixed (static) references")
    def test_referenced_static_image_still_processed(self, site_factory, builder, image_factory):
        site = site_factory('blog', overlay='blog_site')
        image_factory(site / 'static' / 'images' / 'logo.png', size=(32, 32))
        index = site / 'content' / 'index.md'
        index.write_text(
            index.read_text(encoding='utf-8') + '\n![logo](/images/logo.png)\n',
            encoding='utf-8',
        )
        _, out = builder(site, config_overrides={
            ('images', 'only_used'): True,
            ('images', 'dither'): True,
        })
        # static-image processing writes an _original copy alongside the dithered main file
        assert (out / 'images' / 'logo_original.png').exists()

    def test_unreferenced_content_image_skipped(self, site_factory, builder, image_factory):
        site = site_factory('blog', overlay='blog_site')
        image_factory(site / 'content' / 'blog' / 'unused.jpg', size=(32, 32))
        _, out = builder(site, config_overrides={('images', 'only_used'): True})
        assert not (out / 'assets' / 'images' / 'unused_400_original.webp').exists()
