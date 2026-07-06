"""VariableManager: scopes, scripts, data loading, persistence semantics."""

import json
import textwrap


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


class TestSubstitution:
    def test_sonne_variable_replaced(self, tmp_path):
        vm = make_vm(tmp_path)
        vm.set("name", "World", "site")
        assert vm.substitute_variables("Hi {+}{name}") == "Hi World"

    def test_unknown_variable_left_intact(self, tmp_path):
        vm = make_vm(tmp_path)
        assert vm.substitute_variables("Hi {+}{ghost}") == "Hi {+}{ghost}"

    def test_embedded_python_disabled_by_default(self, tmp_path):
        vm = make_vm(tmp_path)
        out = vm.substitute_variables("{p}{# result = 1+1 #}")
        assert "2" not in out
        assert "disabled" in out.lower()


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
