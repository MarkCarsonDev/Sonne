"""VariableManager: scopes, scripts, data loading, persistence semantics."""

import json
import logging
import textwrap

import pytest

import sonne
from sonne.core.config import Config
from sonne.core.variable_manager import VariableManager


def make_vm(base_dir):
    return VariableManager(Config(base_dir=str(base_dir)), str(base_dir))


class TestScopes:
    def test_page_beats_site_beats_global(self, tmp_path):
        vm = make_vm(tmp_path)
        vm.set("x", 1, "global")
        vm.set("x", 2, "site")
        vm.set("x", 3, "page")
        assert vm.get("x") == 3
        assert vm.get("x", scope="global") == 1
        assert vm.get_all()["x"] == 3

    def test_missing_returns_default(self, tmp_path):
        vm = make_vm(tmp_path)
        assert vm.get("nope", default="d") == "d"


def write_script(site_dir, name, source):
    scripts = site_dir / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / name).write_text(source, encoding="utf-8")


def shadow_warnings(caplog, name):
    return [r for r in caplog.records if r.levelno == logging.WARNING and f"'{name}'" in r.message]


class TestScriptVariableShadowing:
    """B18: sonne_var replacing a site/config variable must not be silent."""

    def test_shadowing_a_site_config_key_warns_once(self, tmp_path, caplog):
        (tmp_path / "sonne.yaml").write_text("site:\n  weather: sunny\n", encoding="utf-8")
        write_script(
            tmp_path, "w.py", "sonne_var('weather', 'rain')\nsonne_var('weather', 'hail')\n"
        )
        vm = make_vm(tmp_path)

        with caplog.at_level(logging.WARNING, logger="sonne"):
            vm.load_variables()

        assert len(shadow_warnings(caplog, "weather")) == 1

    def test_shadowing_keeps_script_value(self, tmp_path):
        (tmp_path / "sonne.yaml").write_text("site:\n  weather: sunny\n", encoding="utf-8")
        write_script(tmp_path, "w.py", "sonne_var('weather', 'rain')\n")
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert vm.get("weather", scope="site") == "rain"

    def test_new_script_variable_does_not_warn(self, tmp_path, caplog):
        write_script(tmp_path, "w.py", "sonne_var('forecast', 'rain')\n")
        vm = make_vm(tmp_path)

        with caplog.at_level(logging.WARNING, logger="sonne"):
            vm.load_variables()

        assert shadow_warnings(caplog, "forecast") == []

    def test_scripts_sharing_a_variable_do_not_warn(self, tmp_path, caplog):
        write_script(tmp_path, "a.py", "sonne_var('shared', 1)\n")
        write_script(tmp_path, "b.py", "sonne_var('shared', 2)\n")
        vm = make_vm(tmp_path)

        with caplog.at_level(logging.WARNING, logger="sonne"):
            vm.load_variables()

        assert shadow_warnings(caplog, "shared") == []


class TestScriptExtensions:
    def test_scripts_can_register_filters_and_globals(self, tmp_path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "ext.py").write_text(
            "sonne_filter('shout', lambda s: str(s).upper())\n"
            "sonne_global('answer_fn', lambda: 42)\n",
            encoding="utf-8",
        )
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert vm.custom_filters["shout"]("hi") == "HI"
        assert vm.custom_globals["answer_fn"]() == 42

    def test_extensions_reset_between_loads(self, tmp_path):
        vm = make_vm(tmp_path)
        vm.custom_filters["stale"] = str
        vm.load_variables()
        assert "stale" not in vm.custom_filters


class TestDataScripts:
    def test_sonne_var_sets_global_and_site(self, tmp_path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "setvar.py").write_text("sonne_var('answer', 42)\n", encoding="utf-8")
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert vm.get("answer", scope="global") == 42
        assert vm.get("answer", scope="site") == 42

    def test_underscore_scripts_skipped(self, tmp_path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "_helper.py").write_text("sonne_var('nope', 1)\n", encoding="utf-8")
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert vm.get("nope") is None

    def test_footer_custom_marked_html_safe(self, tmp_path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "footer.py").write_text(
            "sonne_var('footer_custom', '<b>hi</b>')\n", encoding="utf-8"
        )
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert hasattr(vm.get("footer_custom"), "__html__")

    def test_footer_script_runs_exactly_once(self, tmp_path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        counter = tmp_path / "count.txt"
        (scripts / "footer.py").write_text(
            textwrap.dedent(f"""
            with open(r'{counter}', 'a') as f:
                f.write('run\\n')
            sonne_var('footer_custom', '<b>x</b>')
        """),
            encoding="utf-8",
        )
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert counter.read_text().count("run") == 1

    def test_footer_in_custom_data_path_found_from_any_cwd(self, tmp_path, monkeypatch):
        (tmp_path / "sonne.yaml").write_text("paths:\n  data: mydata\n", encoding="utf-8")
        (tmp_path / "mydata").mkdir()
        (tmp_path / "mydata" / "footer.py").write_text(
            "sonne_var('footer_custom', '<b>mine</b>')\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path.parent)
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert str(vm.get("footer_custom")) == "<b>mine</b>"

    def test_footer_in_data_dir_runs_and_is_html_safe(self, tmp_path):
        data = tmp_path / "data"
        data.mkdir()
        (data / "footer.py").write_text(
            "sonne_var('footer_custom', '<i>f</i>')\n", encoding="utf-8"
        )
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert hasattr(vm.get("footer_custom", scope="global"), "__html__")
        assert hasattr(vm.get("footer", scope="site")["custom"], "__html__")
        assert str(vm.get("footer", scope="site")["custom"]) == "<i>f</i>"

    def test_broken_footer_falls_through_to_next_candidate(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "footer.py").write_text("raise RuntimeError('x')\n", encoding="utf-8")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "footer.py").write_text(
            "sonne_var('footer_custom', '<b>ok</b>')\n", encoding="utf-8"
        )
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert str(vm.get("footer_custom")) == "<b>ok</b>"


class TestSiteConfigVariables:
    def test_site_config_is_exposed_in_site_scope(self, tmp_path):
        (tmp_path / "sonne.yaml").write_text(
            "site:\n  title: T\n  footer:\n    note: n\n", encoding="utf-8"
        )
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert vm.get("title", scope="site") == "T"
        assert vm.get("footer", scope="site") == {"custom": None, "note": "n"}

    def test_dict_title_uses_its_text(self, tmp_path):
        (tmp_path / "sonne.yaml").write_text("site:\n  title:\n    text: Hi\n", encoding="utf-8")
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert vm.get("title", scope="site") == "Hi"

    def test_blog_variables_survive_reload(self, tmp_path):
        vm = make_vm(tmp_path)
        vm.set("all_blog_posts", [{"slug": "a"}], "global")

        vm.load_variables()

        assert vm.get("all_blog_posts", scope="site") == [{"slug": "a"}]


class TestDataFiles:
    def test_yaml_data_file_loaded_into_site_scope(self, tmp_path):
        data = tmp_path / "data"
        data.mkdir()
        (data / "team.yaml").write_text("team:\n  - name: Ada\n", encoding="utf-8")
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert vm.get("team") == [{"name": "Ada"}]

    def test_csv_loaded_under_file_stem(self, tmp_path):
        data = tmp_path / "data"
        data.mkdir()
        (data / "stats.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert vm.get("stats") == [{"a": "1", "b": "2"}]

    def test_data_key_in_user_data_not_unwrapped(self, tmp_path):
        data = tmp_path / "data"
        data.mkdir()
        (data / "charts.json").write_text(
            json.dumps({"chart1": {"data": [1, 2], "label": "x"}}), encoding="utf-8"
        )
        vm = make_vm(tmp_path)
        vm.load_variables()
        assert vm.get("chart1") == {"data": [1, 2], "label": "x"}


class TestPersistence:
    def test_prior_variables_not_loaded_by_default(self, tmp_path):
        (tmp_path / "sonne_variables.json").write_text(
            json.dumps({"stale": {"data": "old"}}), encoding="utf-8"
        )
        vm = make_vm(tmp_path)  # preserve_prior defaults to False
        vm.load_variables()
        assert vm.get("stale") is None

    def test_save_excludes_derived_state(self, tmp_path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "setvar.py").write_text("sonne_var('mine', 7)\n", encoding="utf-8")
        vm = make_vm(tmp_path)
        vm.variables["global"]["all_blog_posts"] = [{"title": "x"}]
        vm.load_variables()
        vm.config.set("variables", "preserve_prior", value=True)
        vm.save()
        saved = json.loads((tmp_path / "sonne_variables.json").read_text(encoding="utf-8"))
        assert "mine" in saved
        assert "all_blog_posts" not in saved


class TestVersion:
    def test_version_tracks_package_version(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sonne, "__version__", "99.0.0-test")
        vm = make_vm(tmp_path)
        assert vm._get_version() == "99.0.0-test"


class TestDeterministicOrder:
    @pytest.fixture
    def reversed_glob(self, monkeypatch):
        from pathlib import Path

        real_glob = Path.glob
        monkeypatch.setattr(
            Path, "glob", lambda self, pattern: reversed(list(real_glob(self, pattern)))
        )

    def test_data_scripts_run_in_sorted_order(self, tmp_path, reversed_glob):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        for name in ["b.py", "a.py", "c.py"]:
            (scripts / name).write_text("", encoding="utf-8")

        names = [path.name for path in make_vm(tmp_path).data_script_paths()]

        assert names == ["a.py", "b.py", "c.py"]

    def test_later_data_file_wins_in_sorted_order(self, tmp_path, reversed_glob):
        data = tmp_path / "data"
        data.mkdir()
        (data / "a.json").write_text(json.dumps({"x": "from a"}), encoding="utf-8")
        (data / "b.json").write_text(json.dumps({"x": "from b"}), encoding="utf-8")
        vm = make_vm(tmp_path)

        vm.load_variables()

        assert vm.get("x", scope="site") == "from b"
