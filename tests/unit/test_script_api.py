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
        ],
        ids=["sonne_var", "get_post", "sonne_filter", "sonne_global"],
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
