"""
Shared pytest fixtures for the Sonne test suite.

The suite is a characterization suite: it pins current behavior so refactors
are safe. Tests for known bugs assert the FIXED behavior and are marked
``@pytest.mark.xfail(strict=True, reason="Bxx: ...")`` until the fix lands.
"""
import copy
import shutil
from pathlib import Path

import pytest
from PIL import Image

import sonne.core.config as config_module
from sonne.core.config import Config
from sonne.core.site_generator import SiteGenerator

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_TEMPLATES = REPO_ROOT / 'sonne' / 'templates'
FIXTURES = Path(__file__).resolve().parent / 'fixtures'


@pytest.fixture(autouse=True)
def _isolate_default_config():
    """Snapshot/restore DEFAULT_CONFIG around every test.

    Config._load_config currently mutates the module-global DEFAULT_CONFIG
    (shallow copy bug, see test_config). Without this isolation, test results
    would depend on execution order. The mutation bug itself is asserted
    explicitly in its own test.
    """
    snapshot = copy.deepcopy(config_module.DEFAULT_CONFIG)
    yield
    config_module.DEFAULT_CONFIG.clear()
    config_module.DEFAULT_CONFIG.update(copy.deepcopy(snapshot))


def make_image(path, size=(16, 16), color=(200, 60, 60), fmt=None):
    """Generate a tiny test image with Pillow (no binaries in the repo)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', size, color)
    img.save(path, format=fmt)
    return path


@pytest.fixture
def image_factory():
    return make_image


@pytest.fixture
def site_factory(tmp_path):
    """Create a site directory from a bundled template plus optional overlay.

    Usage: site = site_factory('blog', overlay='blog_site')
    Copies sonne/templates/<template> into a temp dir, then copies
    tests/fixtures/<overlay> on top of it.
    """
    def _factory(template='minimal', overlay=None, name=None):
        site_dir = tmp_path / (name or f'site_{template}')
        shutil.copytree(BUNDLED_TEMPLATES / template, site_dir)
        if overlay:
            overlay_dir = FIXTURES / overlay
            if overlay_dir.exists():
                shutil.copytree(overlay_dir, site_dir, dirs_exist_ok=True)
        return site_dir

    return _factory


def build_site(site_dir, config_overrides=None, **generate_kwargs):
    """Load config for a site dir, apply overrides, and run a full build.

    Returns (generator, output_dir).
    """
    config = Config(base_dir=str(site_dir))
    for keys, value in (config_overrides or {}).items():
        if isinstance(keys, str):
            keys = (keys,)
        config.set(*keys, value=value)
    generator = SiteGenerator(config, base_dir=str(site_dir))
    generator.generate(**generate_kwargs)
    return generator, Path(generator.paths['output'])


@pytest.fixture
def builder():
    return build_site
