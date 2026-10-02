"""The `data` namespace: data files and script variables under data.<name>.

By default they live only under `data`, so they can never collide with site
config or Sonne's own variables. With variables.flatten_data: true they are
ALSO exposed flat, as before the namespace existed.
"""

import logging

from markupsafe import Markup

from sonne.core.config import Config
from sonne.core.variable_manager import VariableManager


def make_site(tmp_path, config="", data=None, scripts=None):
    (tmp_path / "sonne.yaml").write_text(config, encoding="utf-8")
    for relative, text in (data or {}).items():
        path = tmp_path / "data" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    for name, source in (scripts or {}).items():
        (tmp_path / "scripts").mkdir(exist_ok=True)
        (tmp_path / "scripts" / name).write_text(source, encoding="utf-8")
    return tmp_path


def loaded(site_dir):
    vm = VariableManager(Config(base_dir=str(site_dir)), str(site_dir))
    vm.load_variables()
    return vm


def data_namespace(vm):
    return vm.render_scopes()["global"]["data"]


FLAT_OFF = ""  # the default
FLAT_ON = "variables:\n  flatten_data: true\n"


class TestDataNamespace:
    def test_mapping_data_file_is_available_under_its_file_name(self, tmp_path):
        site = make_site(tmp_path, data={"authors.yaml": "alice: Alice A.\n"})
        assert data_namespace(loaded(site))["authors"] == {"alice": "Alice A."}

    def test_csv_rows_are_available_under_their_file_name(self, tmp_path):
        site = make_site(tmp_path, data={"books.csv": "title,year\nDune,1965\n"})
        assert data_namespace(loaded(site))["books"] == [{"title": "Dune", "year": "1965"}]

    def test_script_variable_is_available_under_its_name(self, tmp_path):
        site = make_site(tmp_path, scripts={"s.py": "sonne_var('weather_now', 'rain')\n"})
        assert data_namespace(loaded(site))["weather_now"] == "rain"

    def test_namespace_is_exposed_to_templates_at_top_level_and_in_site(self, tmp_path):
        site = make_site(tmp_path, data={"authors.yaml": "alice: Alice A.\n"})
        scopes = loaded(site).render_scopes()
        assert scopes["site"]["data"] is scopes["global"]["data"]

    def test_same_file_name_in_two_folders_warns(self, tmp_path, caplog):
        site = make_site(tmp_path, data={"a/people.yaml": "x: 1\n", "b/people.yaml": "y: 2\n"})
        with caplog.at_level(logging.WARNING, logger="sonne"):
            vm = loaded(site)
        assert data_namespace(vm)["people"] == {"y": 2}
        assert any("people" in r.getMessage() for r in caplog.records)


class TestFlattenDataOn:
    """flatten_data: true: the old flat access keeps working."""

    def test_mapping_keys_are_still_merged_into_site(self, tmp_path):
        site = make_site(tmp_path, FLAT_ON, data={"authors.yaml": "alice: Alice A.\n"})
        assert loaded(site).variables["site"]["alice"] == "Alice A."

    def test_script_variable_is_still_a_top_level_global(self, tmp_path):
        site = make_site(tmp_path, FLAT_ON, scripts={"s.py": "sonne_var('weather_now', 'rain')\n"})
        assert loaded(site).variables["global"]["weather_now"] == "rain"


class TestOnlyUnderData:
    """The default."""

    def test_mapping_keys_are_not_merged_into_site(self, tmp_path):
        site = make_site(tmp_path, FLAT_OFF, data={"authors.yaml": "alice: Alice A.\n"})
        vm = loaded(site)
        assert "alice" not in vm.variables["site"]
        assert data_namespace(vm)["authors"] == {"alice": "Alice A."}

    def test_script_variable_cannot_replace_site_config(self, tmp_path, caplog):
        site = make_site(
            tmp_path,
            FLAT_OFF + "site:\n  weather: sunny\n",
            scripts={"s.py": "sonne_var('weather', 'rain')\n"},
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            vm = loaded(site)
        assert vm.variables["site"]["weather"] == "sunny"
        assert data_namespace(vm)["weather"] == "rain"
        assert not any("replaces the site variable" in r.getMessage() for r in caplog.records)

    def test_get_variable_finds_namespaced_script_variables(self, tmp_path):
        site = make_site(
            tmp_path,
            FLAT_OFF,
            scripts={
                "a.py": "sonne_var('first', 1)\n",
                "b.py": "sonne_var('second', get_variable('first') + 1)\n",
            },
        )
        assert data_namespace(loaded(site))["second"] == 2

    def test_footer_script_still_fills_the_footer(self, tmp_path):
        site = make_site(tmp_path, FLAT_OFF)
        (site / "data").mkdir()
        (site / "data" / "footer.py").write_text(
            "sonne_var('footer_custom', '<p>hi</p>')\n", encoding="utf-8"
        )
        vm = loaded(site)
        assert vm.variables["site"]["footer"]["custom"] == Markup("<p>hi</p>")
        assert isinstance(data_namespace(vm)["footer_custom"], Markup)


class TestPersistence:
    def test_script_variables_round_trip_with_flatten_off(self, tmp_path):
        config = "variables:\n  flatten_data: false\n  preserve_prior: true\n"
        site = make_site(tmp_path, config, scripts={"s.py": "sonne_var('count', 3)\n"})
        loaded(site).save()
        (site / "scripts" / "s.py").unlink()
        assert data_namespace(loaded(site))["count"] == 3


def test_templates_read_the_namespace_in_a_real_build(site_factory, builder):
    site = site_factory("minimal")
    (site / "data").mkdir(exist_ok=True)
    (site / "data" / "authors.yaml").write_text("alice: Alice A.\n", encoding="utf-8")
    (site / "content" / "probe.md").write_text(
        "---\ntitle: Probe\njinja: true\n---\nBy {{ data.authors.alice }}\n", encoding="utf-8"
    )
    _, out = builder(site)
    assert "By Alice A." in (out / "probe" / "index.html").read_text(encoding="utf-8")


class TestMovedNameWarning:
    """A template still using a flat name is told where the value is now."""

    def build(self, site_factory, builder, caplog, body, overrides=None):
        site = site_factory("minimal")
        (site / "data").mkdir(exist_ok=True)
        (site / "data" / "authors.yaml").write_text("alice: Alice A.\n", encoding="utf-8")
        (site / "scripts").mkdir(exist_ok=True)
        (site / "scripts" / "s.py").write_text("sonne_var('team', ['Ada'])\n", encoding="utf-8")
        (site / "content" / "probe.md").write_text(
            f"---\ntitle: Probe\njinja: true\n---\n{body}\n", encoding="utf-8"
        )
        with caplog.at_level(logging.WARNING, logger="sonne"):
            _, out = builder(site, config_overrides=overrides)
        html = (out / "probe" / "index.html").read_text(encoding="utf-8")
        return html, [r.getMessage() for r in caplog.records if "under `data` now" in r.message]

    def test_script_variable(self, site_factory, builder, caplog):
        _, warnings = self.build(site_factory, builder, caplog, "[{{ team }}]")

        [warning] = warnings
        assert "'team'" in warning and "{{ data.team }}" in warning

    def test_key_of_a_mapping_data_file(self, site_factory, builder, caplog):
        _, warnings = self.build(site_factory, builder, caplog, "[{{ alice }}]")

        [warning] = warnings
        assert "{{ data.authors.alice }}" in warning

    def test_name_read_through_site(self, site_factory, builder, caplog):
        _, warnings = self.build(site_factory, builder, caplog, "{% if site.team %}x{% endif %}")

        assert len(warnings) == 1

    def test_each_name_warns_once_per_build(self, site_factory, builder, caplog):
        body = "{% if team %}x{% endif %} {% for member in team %}y{% endfor %} [{{ team }}]"

        _, warnings = self.build(site_factory, builder, caplog, body)

        assert len(warnings) == 1

    def test_no_warning_for_an_attribute_of_something_else(self, site_factory, builder, caplog):
        _, warnings = self.build(site_factory, builder, caplog, "[{{ page.team }}]")

        assert warnings == []

    def test_no_warning_for_an_unrelated_undefined_name(self, site_factory, builder, caplog):
        _, warnings = self.build(site_factory, builder, caplog, "[{{ nothing_like_it }}]")

        assert warnings == []

    def test_no_warning_and_the_old_value_with_flatten_data_on(self, site_factory, builder, caplog):
        html, warnings = self.build(
            site_factory,
            builder,
            caplog,
            "[{{ team | join(',') }}]",
            overrides={("variables", "flatten_data"): True},
        )

        assert "[Ada]" in html
        assert warnings == []


class TestRestoredVariables:
    """Variables restored from the variable file (preserve_prior) behave as before."""

    def saved_site(self, tmp_path):
        config = (
            "site:\n  weather: sunny\nvariables:\n  preserve_prior: true\n  flatten_data: true\n"
        )
        site = make_site(tmp_path, config, scripts={"s.py": "sonne_var('weather', 'rain')\n"})
        loaded(site).save()
        return site

    def test_restored_variable_does_not_replace_site_config(self, tmp_path):
        site = self.saved_site(tmp_path)
        (site / "scripts" / "s.py").unlink()
        vm = loaded(site)
        assert vm.variables["site"]["weather"] == "sunny"
        assert data_namespace(vm)["weather"] == "rain"

    def test_restored_variable_does_not_silence_the_shadowing_warning(self, tmp_path, caplog):
        site = self.saved_site(tmp_path)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="sonne"):
            loaded(site)
        assert any("'weather' replaces the site variable" in r.getMessage() for r in caplog.records)
