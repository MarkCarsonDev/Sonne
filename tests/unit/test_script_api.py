"""sonne.script_api: the importable data-script API (sonne_var, get_post, ...)."""

import pytest

from sonne import script_api
from sonne.core.config import Config
from sonne.core.variable_manager import VariableManager

IMPORT_LINE = "from sonne.script_api import get_post, sonne_filter, sonne_global, sonne_var\n"


def make_site(tmp_path, scripts):
    """A site directory whose scripts/ holds the given {filename: source}."""
    (tmp_path / "scripts").mkdir(parents=True)
    for name, source in scripts.items():
        (tmp_path / "scripts" / name).write_text(source, encoding="utf-8")
    return tmp_path


def load(site_dir, posts=None):
    vm = VariableManager(Config(base_dir=str(site_dir)), str(site_dir))
    if posts is not None:
        vm.set("all_blog_posts", posts, "global")
    vm.load_variables()
    return vm


class TestDuringABuild:
    def test_imported_functions_reach_the_running_build(self, tmp_path):
        site = make_site(
            tmp_path,
            {
                "api.py": IMPORT_LINE
                + "sonne_var('team', ['Ada'])\n"
                + "sonne_filter('shout', lambda s: str(s).upper())\n"
                + "sonne_global('answer', 42)\n"
                + "sonne_var('found', get_post(slug='a')['title'])\n"
            },
        )

        vm = load(site, posts=[{"slug": "a", "title": "Post A", "tags": []}])

        assert vm.get("team") == ["Ada"]
        assert vm.custom_filters["shout"]("hi") == "HI"
        assert vm.custom_globals["answer"] == 42
        assert vm.get("found") == "Post A"

    def test_keyword_arguments_match_the_injected_functions(self, tmp_path):
        site = make_site(
            tmp_path,
            {
                "kw.py": IMPORT_LINE
                + "sonne_var(name='x', value=1)\nsonne_filter(name='f', fn=str)\n"
            },
        )

        vm = load(site)

        assert vm.get("x") == 1 and vm.custom_filters["f"] is str

    def test_injected_globals_still_work(self, tmp_path):
        site = make_site(tmp_path, {"legacy.py": "sonne_var('legacy', True)\n"})

        assert load(site).get("legacy") is True

    def test_footer_script_can_use_the_import(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "footer.py").write_text(
            IMPORT_LINE + "sonne_var('footer_custom', '<b>f</b>')\n", encoding="utf-8"
        )

        vm = load(tmp_path)

        assert str(vm.get("footer_custom")) == "<b>f</b>"


class TestOutsideABuild:
    @pytest.mark.parametrize(
        "call",
        [
            lambda: script_api.sonne_var("x", 1),
            lambda: script_api.get_post(slug="a"),
            lambda: script_api.sonne_filter("f", str),
            lambda: script_api.sonne_global("g", 1),
            lambda: script_api.sonne_config("site", "title"),
        ],
        ids=["sonne_var", "get_post", "sonne_filter", "sonne_global", "sonne_config"],
    )
    def test_calls_raise_a_clear_error(self, call):
        with pytest.raises(RuntimeError, match="only be called while Sonne runs a data script"):
            call()


class TestNoLeaks:
    def test_api_is_inactive_after_the_scripts_ran(self, tmp_path):
        load(make_site(tmp_path, {"a.py": IMPORT_LINE + "sonne_var('a', 1)\n"}))

        with pytest.raises(RuntimeError):
            script_api.sonne_var("late", 1)

    def test_api_is_inactive_after_a_script_fails(self, tmp_path):
        load(make_site(tmp_path, {"boom.py": IMPORT_LINE + "raise ValueError('boom')\n"}))

        with pytest.raises(RuntimeError):
            script_api.sonne_var("late", 1)

    def test_builds_do_not_share_hooks(self, tmp_path):
        first = make_site(tmp_path / "one", {"s.py": IMPORT_LINE + "sonne_var('who', 'one')\n"})
        second = make_site(tmp_path / "two", {"s.py": IMPORT_LINE + "sonne_var('who', 'two')\n"})

        vm_one, vm_two = load(first), load(second)

        assert (vm_one.get("who"), vm_two.get("who")) == ("one", "two")

    def test_helper_called_later_reaches_the_script_running_now(self, tmp_path):
        # A script can keep a reference to the API (e.g. in a helper) and
        # call it from a later script; calls go to whichever build is
        # running the current script.
        site = make_site(
            tmp_path,
            {
                "_helpers.py": IMPORT_LINE + "def publish(v):\n    sonne_var('from_helper', v)\n",
                "a.py": "import importlib.util, pathlib\n"
                "spec = importlib.util.spec_from_file_location(\n"
                "    'helpers', pathlib.Path(__file__).with_name('_helpers.py'))\n"
                "helpers = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(helpers)\n"
                "helpers.publish('ok')\n",
            },
        )

        assert load(site).get("from_helper") == "ok"


CONFIG_IMPORT = "from sonne.script_api import sonne_config, sonne_var\n"
SITE_CONFIG = "site:\n  title: Real\n  tagline: null\n  weather:\n    city: Oslo\n"


def site_with_config(tmp_path, scripts):
    (tmp_path / "sonne.yaml").write_text(SITE_CONFIG, encoding="utf-8")
    return make_site(tmp_path, scripts)


class TestSonneConfig:
    def test_returns_configured_values_and_defaults(self, tmp_path):
        site = site_with_config(
            tmp_path,
            {
                "cfg.py": CONFIG_IMPORT
                + "sonne_var('city', sonne_config('site', 'weather', 'city'))\n"
                + "sonne_var('per_page', sonne_config('blog', 'posts_per_page'))\n"
                + "sonne_var('missing', sonne_config('site', 'nope', default='fallback'))\n"
                + "sonne_var('no_keys', sonne_config(default='whole'))\n"
            },
        )

        vm = load(site)

        assert vm.get("city") == "Oslo"
        assert vm.get("per_page") == 10  # built-in default config
        assert vm.get("missing") == "fallback"
        assert vm.get("no_keys") == "whole"

    def test_configured_null_is_returned_not_the_default(self, tmp_path):
        site = site_with_config(
            tmp_path,
            {
                "cfg.py": CONFIG_IMPORT
                + "sonne_var('tagline', sonne_config('site', 'tagline', default='d'))\n"
            },
        )

        assert load(site).get("tagline") is None

    def test_default_is_returned_as_given(self, tmp_path):
        site = site_with_config(
            tmp_path,
            {
                "cfg.py": CONFIG_IMPORT
                + "marker = []\n"
                + "sonne_var('same', sonne_config('site', 'nope', default=marker) is marker)\n"
            },
        )

        assert load(site).get("same") is True

    def test_changing_the_result_does_not_change_the_build_config(self, tmp_path):
        site = site_with_config(
            tmp_path,
            {
                "cfg.py": CONFIG_IMPORT
                + "site_section = sonne_config('site')\n"
                + "site_section['title'] = 'Hacked'\n"
                + "site_section['weather']['city'] = 'Nowhere'\n"
                + "sonne_config('images', 'sizes').append(1)\n"
            },
        )

        vm = load(site)

        assert vm.config.get("site", "title") == "Real"
        assert vm.config.get("site", "weather", "city") == "Oslo"
        assert vm.config.get("images", "sizes") == [1200, 800, 400]

    def test_injected_and_imported_forms_agree(self, tmp_path):
        site = site_with_config(
            tmp_path,
            {
                "imported.py": CONFIG_IMPORT
                + "sonne_var('imported', sonne_config('site', 'weather'))\n",
                "injected.py": "sonne_var('injected', sonne_config('site', 'weather'))\n",
            },
        )

        vm = load(site)

        assert vm.get("imported") == vm.get("injected") == {"city": "Oslo"}
