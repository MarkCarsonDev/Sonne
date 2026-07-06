"""CLI surface via click's CliRunner."""

import pytest
from click.testing import CliRunner

from sonne.cli.commands import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestNew:
    @pytest.mark.parametrize("template", ["minimal", "blog", "portfolio", "solar"])
    def test_new_scaffolds_each_template(self, runner, tmp_path, template):
        target = tmp_path / template
        result = runner.invoke(cli, ["new", "-p", str(target), "-t", template, "-n", "Test Site"])
        assert result.exit_code == 0, result.output
        assert (target / "sonne.yaml").exists()
        assert (target / "content").is_dir()
        assert (target / "templates").is_dir()

    def test_new_refuses_nonempty_dir_without_force(self, runner, tmp_path):
        target = tmp_path / "occupied"
        target.mkdir()
        (target / "existing.txt").write_text("x", encoding="utf-8")
        result = runner.invoke(cli, ["new", "-p", str(target), "-t", "minimal"])
        assert result.exit_code != 0

    def test_new_preserves_template_config(self, runner, tmp_path):
        target = tmp_path / "clean-config"
        result = runner.invoke(cli, ["new", "-p", str(target), "-t", "minimal", "-n", "Test Site"])
        assert result.exit_code == 0, result.output
        text = (target / "sonne.yaml").read_text(encoding="utf-8")
        assert "Test Site" in text
        # default-only sections must not be dumped into the site's config
        assert "security" not in text
        assert "allow_embedded_python" not in text


class TestBuild:
    def test_build_succeeds_on_fresh_site(self, runner, tmp_path):
        target = tmp_path / "buildme"
        runner.invoke(cli, ["new", "-p", str(target), "-t", "minimal"])
        result = runner.invoke(cli, ["build", "-p", str(target), "--no-progress"])
        assert result.exit_code == 0, result.output
        assert (target / "output" / "index.html").exists()

    def test_build_fails_outside_project_dir(self, runner, tmp_path):
        empty = tmp_path / "not-a-site"
        empty.mkdir()
        result = runner.invoke(cli, ["build", "-p", str(empty)])
        assert result.exit_code != 0

    def test_build_has_yes_flag(self, runner):
        result = runner.invoke(cli, ["build", "--help"])
        assert "--yes" in result.output


class TestServeInternals:
    def test_server_allows_address_reuse(self):
        from sonne.cli.commands import ReuseAddrTCPServer

        assert ReuseAddrTCPServer.allow_reuse_address is True

    def test_rebuild_helper_reloads_config(self, site_factory):
        # The watch rebuild must re-read sonne.yaml, not reuse the Config
        # captured at serve startup.
        from sonne.cli.commands import _rebuild_site

        site = site_factory("minimal")
        _rebuild_site(str(site))
        assert (site / "output" / "index.html").exists()
        config_file = site / "sonne.yaml"
        config_file.write_text(
            config_file.read_text(encoding="utf-8").replace("My Minimal Site", "Retitled Site"),
            encoding="utf-8",
        )
        _rebuild_site(str(site))
        html = (site / "output" / "index.html").read_text(encoding="utf-8")
        assert "Retitled Site" in html
