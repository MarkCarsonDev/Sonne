"""CLI surface via click's CliRunner."""

import logging

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

    def test_perf_report_survives_non_utf8_output(self, tmp_path):
        """--perf on a cp1252 pipe (Windows redirect) must not fail the build."""
        target = tmp_path / "perf"
        CliRunner().invoke(cli, ["new", "-p", str(target), "-t", "minimal"])
        cp1252_runner = CliRunner(charset="cp1252")

        result = cp1252_runner.invoke(cli, ["build", "-p", str(target), "--no-progress", "--perf"])

        assert result.exit_code == 0, result.output
        assert "Performance Breakdown" in result.output

    def test_build_reports_the_sites_own_output_dir(self, runner, tmp_path, monkeypatch, caplog):
        import sonne.cli.commands as commands

        target = tmp_path / "elsewhere"
        runner.invoke(cli, ["new", "-p", str(target), "-t", "minimal"])
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(commands, "console", None)  # plain log output

        with caplog.at_level(logging.INFO, logger="sonne"):
            runner.invoke(cli, ["build", "-p", str(target), "--no-progress"])

        completion = [r.message for r in caplog.records if r.message.startswith("Build complete")]
        assert completion and completion[0].endswith(f"[{target / 'output'}]")

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


class TestWatchRelevance:
    @staticmethod
    def rebuilder_for(site, **paths):
        from sonne.cli.commands import SiteRebuilder
        from sonne.core.config import Config

        config = Config(base_dir=str(site))
        for key, value in paths.items():
            config.set("paths", key, value=value)
        return SiteRebuilder(str(site), config)

    def test_nested_forward_slash_path_is_watched(self, tmp_path):
        rebuilder = self.rebuilder_for(tmp_path, content="src/pages")

        assert rebuilder.affects_site(str(tmp_path / "src" / "pages" / "a.md"))

    def test_dot_prefixed_path_is_watched(self, tmp_path):
        rebuilder = self.rebuilder_for(tmp_path, content="./content")

        assert rebuilder.affects_site(str(tmp_path / "content" / "a.md"))

    def test_absolute_path_is_watched(self, tmp_path):
        rebuilder = self.rebuilder_for(tmp_path, content=str(tmp_path / "abs"))

        assert rebuilder.affects_site(str(tmp_path / "abs" / "a.md"))

    def test_config_file_is_watched(self, tmp_path):
        rebuilder = self.rebuilder_for(tmp_path)

        assert rebuilder.affects_site(str(tmp_path / "sonne.yaml"))

    def test_sibling_with_shared_prefix_is_ignored(self, tmp_path):
        rebuilder = self.rebuilder_for(tmp_path, content="content")

        assert not rebuilder.affects_site(str(tmp_path / "content-drafts" / "a.md"))

    def test_output_changes_are_ignored(self, tmp_path):
        rebuilder = self.rebuilder_for(tmp_path)

        assert not rebuilder.affects_site(str(tmp_path / "output" / "index.html"))


class TestWatchRebuilds:
    def test_change_during_rebuild_triggers_another_rebuild(self, tmp_path, monkeypatch):
        import sonne.cli.commands as commands
        from sonne.core.config import Config

        rebuilder = commands.SiteRebuilder(str(tmp_path), Config(base_dir=str(tmp_path)))
        builds = []

        def rebuild_site(base_dir):
            builds.append(base_dir)
            if len(builds) == 1:
                rebuilder._rebuild()  # the debounce timer fires again mid-build

        monkeypatch.setattr(commands, "_rebuild_site", rebuild_site)

        rebuilder._rebuild()

        assert len(builds) == 2

    def test_moved_file_reports_its_destination(self, tmp_path):
        from types import SimpleNamespace

        from sonne.cli.commands import _paths_touched_by

        event = SimpleNamespace(
            event_type="moved",
            is_directory=False,
            src_path=str(tmp_path / "content" / ".post.md.swp"),
            dest_path=str(tmp_path / "content" / "post.md"),
        )

        assert str(tmp_path / "content" / "post.md") in _paths_touched_by(event)


class TestProgressOutput:
    def test_no_progress_hides_step_lines(self, runner, tmp_path, caplog):
        target = tmp_path / "quiet"
        runner.invoke(cli, ["new", "-p", str(target), "-t", "minimal"])

        with caplog.at_level(logging.INFO, logger="sonne"):
            result = runner.invoke(cli, ["build", "-p", str(target), "--no-progress"])

        assert result.exit_code == 0, result.output
        assert not any(record.getMessage().startswith("[1/") for record in caplog.records)

    def test_step_lines_shown_by_default(self, runner, tmp_path, caplog):
        target = tmp_path / "chatty"
        runner.invoke(cli, ["new", "-p", str(target), "-t", "minimal"])

        with caplog.at_level(logging.INFO, logger="sonne"):
            runner.invoke(cli, ["build", "-p", str(target)])

        assert any(record.getMessage().startswith("[1/") for record in caplog.records)
