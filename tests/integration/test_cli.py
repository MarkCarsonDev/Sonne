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

    def test_read_only_events_do_not_trigger_rebuild(self):
        # watchdog >= 2.3 emits 'opened'/'closed_no_write' when the build
        # itself reads content files during a rebuild. Reacting to those made
        # every rebuild re-trigger itself into an infinite loop (a single
        # content edit produced an unbroken rebuild cascade).
        from sonne.cli.commands import _watch_event_triggers_rebuild

        base = "/site"
        watch_dirs = ["content"]
        watch_files = ["sonne.yaml"]
        img = "/site/content/articles/img/photo.jpg"

        for read_only in ("opened", "closed_no_write"):
            assert not _watch_event_triggers_rebuild(
                read_only, False, img, base, watch_dirs, watch_files
            )
        # Real mutations to the same watched file still rebuild.
        for mutation in ("modified", "created", "moved", "deleted", "closed"):
            assert _watch_event_triggers_rebuild(
                mutation, False, img, base, watch_dirs, watch_files
            )

    def test_watch_relevance_scopes_to_watched_paths(self):
        from sonne.cli.commands import _watch_event_triggers_rebuild

        base = "/site"
        watch_dirs = ["content"]
        watch_files = ["sonne.yaml"]

        # Output/cache writes are outside the watch set and must be ignored.
        assert not _watch_event_triggers_rebuild(
            "modified", False, "/site/output/index.html", base, watch_dirs, watch_files
        )
        # Config edits rebuild; directory events never do.
        assert _watch_event_triggers_rebuild(
            "modified", False, "/site/sonne.yaml", base, watch_dirs, watch_files
        )
        assert not _watch_event_triggers_rebuild(
            "modified", True, "/site/content", base, watch_dirs, watch_files
        )

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
