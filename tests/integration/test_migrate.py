"""`sonne migrate`: rewrite deprecated config keys, keeping YAML comments."""

import json
import warnings
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from sonne.cli.commands import cli
from sonne.cli.migrate import plan_migration, write_migration
from sonne.core.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]

OLD_CONFIG = """\
# My site
site:
  title: Demo  # shown in the header
  description: |
    Notes that merely look like settings:
    incremental: true
  nav:
    - text: Home
      url: /

images:
  # speed things up
  max_workers: 2   # old name
  formats: [webp]

build:
  # never did anything
  statistics: true

security:
  csp:
    enabled: true
"""

MIGRATED_CONFIG = """\
# My site
site:
  title: Demo  # shown in the header
  description: |
    Notes that merely look like settings:
    incremental: true
  nav:
    - text: Home
      url: /

images:
  # speed things up
  parallel_workers: 2   # old name
  formats: [webp]
"""


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def old_site(tmp_path):
    (tmp_path / "sonne.yaml").write_text(OLD_CONFIG, encoding="utf-8")
    return tmp_path


def migrate(runner, site, *args):
    return runner.invoke(cli, ["migrate", "-p", str(site), *args])


class TestDryRun:
    def test_lists_changes_and_diff_without_writing(self, runner, old_site):
        result = migrate(runner, old_site)

        assert result.exit_code == 0, result.output
        assert "rename images.max_workers -> images.parallel_workers" in result.output
        assert "remove build.statistics (has no effect)" in result.output
        assert "remove security.csp (has no effect)" in result.output
        assert "+  parallel_workers: 2" in result.output
        assert "Dry run: nothing was written" in result.output
        assert (old_site / "sonne.yaml").read_text(encoding="utf-8") == OLD_CONFIG
        assert not list(old_site.glob("*.bak*"))


class TestWrite:
    def test_rewrites_keeping_comments_and_layout(self, runner, old_site):
        result = migrate(runner, old_site, "--write")

        assert result.exit_code == 0, result.output
        assert (old_site / "sonne.yaml").read_text(encoding="utf-8") == MIGRATED_CONFIG
        assert (old_site / "sonne.yaml.bak").read_text(encoding="utf-8") == OLD_CONFIG
        assert "comments and formatting will NOT be kept" not in result.output

    def test_migrated_config_loads_without_deprecation_warnings(self, runner, old_site):
        migrate(runner, old_site, "--write")

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            config = Config(base_dir=str(old_site))

        assert config.get("images", "parallel_workers") == 2

    def test_second_run_has_nothing_to_do(self, runner, old_site):
        migrate(runner, old_site, "--write")

        result = migrate(runner, old_site)

        assert "already up to date" in result.output

    @pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"], ids=["lf", "crlf"])
    def test_line_endings_and_exact_backup_are_kept(self, tmp_path, line_ending):
        original = b"# keep\nbuild:\n  statistics: true\nsite:\n  title: T\n".replace(
            b"\n", line_ending
        )
        (tmp_path / "sonne.yaml").write_bytes(original)

        write_migration(plan_migration(tmp_path / "sonne.yaml"))

        assert (tmp_path / "sonne.yaml.bak").read_bytes() == original
        expected = b"# keep\nsite:\n  title: T\n".replace(b"\n", line_ending)
        assert (tmp_path / "sonne.yaml").read_bytes() == expected

    def test_existing_backup_is_never_overwritten(self, old_site):
        (old_site / "sonne.yaml.bak").write_text("older backup", encoding="utf-8")

        backup = write_migration(plan_migration(old_site / "sonne.yaml"))

        assert backup.name == "sonne.yaml.bak.1"
        assert (old_site / "sonne.yaml.bak").read_text(encoding="utf-8") == "older backup"


class TestPlans:
    def test_new_key_already_set_wins(self, tmp_path):
        path = tmp_path / "sonne.yaml"
        path.write_text("images:\n  max_workers: 2\n  parallel_workers: 8\n", encoding="utf-8")

        plan = plan_migration(path)

        assert plan.migrated_text == "images:\n  parallel_workers: 8\n"
        assert plan.descriptions() == [
            "remove images.max_workers (images.parallel_workers is already set and takes precedence)"
        ]

    def test_flow_style_falls_back_to_full_rewrite_with_warning(self, runner, tmp_path):
        (tmp_path / "sonne.yaml").write_text(
            "# a comment\nimages: {max_workers: 2, formats: [png]}\n", encoding="utf-8"
        )

        result = migrate(runner, tmp_path, "--write")

        assert "comments and formatting will NOT be kept" in result.output
        migrated = yaml.safe_load((tmp_path / "sonne.yaml").read_text(encoding="utf-8"))
        assert migrated == {"images": {"parallel_workers": 2, "formats": ["png"]}}

    def test_json_config(self, runner, tmp_path):
        (tmp_path / "sonne.json").write_text(
            json.dumps({"site": {"title": "J"}, "build": {"incremental": True}}), encoding="utf-8"
        )

        result = migrate(runner, tmp_path, "--write")

        assert "rewritten with 2-space indentation" in result.output
        assert json.loads((tmp_path / "sonne.json").read_text(encoding="utf-8")) == {
            "site": {"title": "J"}
        }


class TestErrors:
    def test_missing_config_fails(self, runner, tmp_path):
        result = migrate(runner, tmp_path)

        assert result.exit_code != 0
        assert "No Sonne config file found" in result.output

    def test_explicit_config_file(self, runner, tmp_path):
        other = tmp_path / "custom.yaml"
        other.write_text("build:\n  show_progress: false\n", encoding="utf-8")

        result = runner.invoke(cli, ["migrate", "-c", str(other), "--write"])

        assert result.exit_code == 0, result.output
        assert yaml.safe_load(other.read_text(encoding="utf-8")) is None


@pytest.mark.parametrize(
    "config_path",
    sorted(REPO_ROOT.glob("sonne/templates/*/sonne.yaml"))
    + sorted(REPO_ROOT.glob("sonne/examples/*/sonne.yaml")),
    ids=lambda path: path.parent.name,
)
def test_bundled_configs_need_no_migration(config_path):
    assert not plan_migration(config_path).needed
