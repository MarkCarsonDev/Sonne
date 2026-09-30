"""
Command-line interface for Sonne static site generator.
Provides commands for creating, building, and serving static sites.
"""

import click
import functools
import os
import sys
import time
import logging
import http.server
import socketserver
import traceback
import webbrowser
import threading
from pathlib import Path
from shutil import copytree, ignore_patterns
from typing import List

import yaml

try:
    from rich.console import Console
    from rich.panel import Panel

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

from sonne.core.config import Config
from sonne.core.site_generator import SiteGenerator
from sonne.utils.path_utils import is_sonne_directory, CONFIG_FILENAMES

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger("sonne")

# Initialize rich console if available
console = Console() if RICH_AVAILABLE else None

DEFAULT_SERVE_HOST = "localhost"
DEFAULT_SERVE_PORT = 8000
BROWSER_OPEN_DELAY_SECONDS = 1.0
OBSERVER_STOP_TIMEOUT_SECONDS = 5


def _use_rich() -> bool:
    return bool(console and RICH_AVAILABLE)


def _print_traceback_if_verbose() -> None:
    """Show the active exception's traceback, but only with -v."""
    if logger.isEnabledFor(logging.DEBUG):
        traceback.print_exc()


def check_sonne_directory(path: str) -> bool:
    """Check if directory looks like a Sonne project and provide helpful guidance.

    Args:
        path: Directory path to check.

    Returns:
        True if appears to be Sonne directory, False otherwise.
    """
    if is_sonne_directory(path):
        return True

    if _use_rich():
        console.print(
            Panel(
                "[bold red]Not a Sonne Project[/bold red]\n\n"
                f"The directory [cyan]{path}[/cyan] doesn't contain a Sonne configuration file.\n\n"
                "[bold]To create a new Sonne site:[/bold]\n"
                "  sonne new -p my-site -t blog\n\n"
                "[bold]Expected files:[/bold]\n"
                "  • sonne.yaml or sonne.yml\n"
                "  • content/ directory\n"
                "  • templates/ directory\n",
                title="Error",
                border_style="red",
            )
        )
    else:
        # Plain ASCII: emoji raise UnicodeEncodeError on cp1252 Windows consoles
        for line in [
            "\nThis doesn't appear to be a Sonne project directory.\n",
            f"The directory {path} doesn't contain a Sonne configuration file.",
            "",
            "To create a new Sonne site:",
            "  sonne new -p my-site -t blog",
            "",
            "Expected files:",
            "  • sonne.yaml or sonne.yml",
            "  • content/ directory",
            "  • templates/ directory",
        ]:
            logger.error(line)
    return False


def _report_problems(heading: str, problems: List[str], severity: int) -> None:
    """Print a headed list of problems (rich if available, else the log).

    Args:
        heading: Title such as "Configuration warnings".
        problems: One message per problem.
        severity: logging.WARNING (yellow) or logging.ERROR (bold red).
    """
    if _use_rich():
        if severity >= logging.ERROR:
            console.print(f"\n[bold red]{heading} ({len(problems)}):[/bold red]")
            bullet = "[red]-[/red]"
        else:
            console.print(f"[yellow]{heading} ({len(problems)}):[/yellow]")
            bullet = "[yellow]-[/yellow]"
        for problem in problems:
            console.print(f"  {bullet} {problem}")
        console.print()
    else:
        logger.log(severity, f"{heading} ({len(problems)}):")
        for problem in problems:
            logger.log(severity, f"  {problem}")


# Main CLI group
@click.group()
@click.version_option()
@click.option("--verbose", "-v", count=True, help="Increase verbosity.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors.")
@click.pass_context
def cli(ctx, verbose, quiet):
    """Sonne - A minimalist static site generator optimized for low footprint sites.

    Designed to create efficient websites with minimal resource requirements.
    """
    if quiet:
        logger.setLevel(logging.ERROR)
    else:
        levels = [logging.INFO, logging.DEBUG]
        logger.setLevel(levels[min(verbose, len(levels) - 1)])

    ctx.ensure_object(dict)
    ctx.obj["start_time"] = time.time()


@cli.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=os.getcwd(),
    help="Path to the site directory.",
)
@click.option(
    "--config", "-c", type=click.Path(exists=False), help="Path to the configuration file."
)
@click.option("--clean", is_flag=True, help="Clean the output directory before building.")
@click.option("--skip-images", is_flag=True, help="Skip image processing during build.")
@click.option("--skip-cache", is_flag=True, help="Ignore cache and rebuild everything.")
@click.option("--dev", is_flag=True, help="Build site for development environment.")
@click.option("--no-progress", is_flag=True, help="Disable progress bars.")
@click.option("--perf", is_flag=True, help="Show detailed performance breakdown after build.")
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Continue past confirmation prompts (e.g. template errors); for CI.",
)
@click.pass_context
def build(ctx, path, config, clean, skip_images, skip_cache, dev, no_progress, perf, yes):
    """Build the static site.

    This command processes your content, templates, and assets to generate
    a complete static website in the output directory.

    Examples:
        sonne build                    # Build in current directory
        sonne build -p ./my-site      # Build specific directory
        sonne build --clean           # Clean build from scratch
        sonne build --dev             # Build for development
    """
    try:
        if not check_sonne_directory(path):
            sys.exit(1)
        _announce_build(path, no_progress)

        config_obj = _load_build_config(path, config, dev)
        generator = SiteGenerator(config_obj, base_dir=path)
        _confirm_templates_or_exit(generator, yes)

        output_dir = generator.paths["output"]
        if clean:
            _clean_output(generator, output_dir)
        stats = generator.generate(skip_images=skip_images, skip_cache=skip_cache)

        _announce_build_complete(time.time() - ctx.obj["start_time"], output_dir)
        if perf and stats:
            _echo_degrading_unencodable(stats.format_report(verbose=True, perf=True))

    except SystemExit:
        raise
    except Exception as e:
        if _use_rich():
            console.print(f"\n[bold red]Build failed:[/bold red] {e}\n")
        else:
            logger.error(f"Build failed: {e}")
        _print_traceback_if_verbose()
        sys.exit(1)


def _announce_build(path: str, no_progress: bool) -> None:
    if _use_rich() and not no_progress:
        console.print("\n[bold cyan]Building Sonne Site[/bold cyan]")
        console.print(f"[dim]Location: {path}[/dim]\n")
    else:
        logger.info(f"Build started  [{path}]")


def _load_build_config(path: str, config_path: str, dev: bool) -> Config:
    """Load and validate the site config, reporting warnings; apply --dev."""
    config = Config(config_path or None, base_dir=path)
    validation_warnings = config.validate()
    if validation_warnings:
        _report_problems("Configuration warnings", validation_warnings, logging.WARNING)
    if dev:
        config.set("environment", value="dev")
        logger.info("Environment: development")
    return config


def _confirm_templates_or_exit(generator: SiteGenerator, assume_yes: bool) -> None:
    """Report template errors and exit unless the user (or --yes) continues."""
    template_errors = generator.template_processor.validate_templates()
    if not template_errors:
        return
    _report_problems("Template validation errors", template_errors, logging.ERROR)

    if assume_yes:
        logger.warning("Continuing despite template errors (--yes)")
    elif not sys.stdin.isatty():
        # Non-interactive (CI, pipes): don't hang on a prompt
        logger.error(
            "Template errors and no TTY to confirm; pass --yes to continue anyway. Build cancelled"
        )
        sys.exit(1)
    elif not click.confirm("Templates have errors. Continue anyway?", default=False):
        logger.info("Build cancelled")
        sys.exit(1)


def _clean_output(generator: SiteGenerator, output_dir: str) -> None:
    if _use_rich():
        console.print("[yellow]Cleaning output directory...[/yellow]")
    else:
        logger.info(f"Cleaning output directory  [{output_dir}]")
    generator.clean_output()


def _announce_build_complete(elapsed_seconds: float, output_dir: str) -> None:
    if _use_rich():
        console.print(f"\n[bold green]Build complete[/bold green]  ({elapsed_seconds:.2f}s)")
        console.print(f"[dim]Output: {output_dir}[/dim]\n")
    else:
        logger.info(f"Build complete  {elapsed_seconds:.2f}s  [{output_dir}]")


def _echo_degrading_unencodable(text: str) -> None:
    """Echo text, replacing characters stdout's encoding cannot represent.

    Reports use glyphs (✓, █, ⚡) that a cp1252 pipe or redirect on Windows
    cannot encode; printing them must never turn a finished build into a
    failed one.
    """
    encoding = getattr(click.get_text_stream("stdout"), "encoding", None) or "utf-8"
    click.echo(text.encode(encoding, errors="replace").decode(encoding))


@cli.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(),
    default=os.getcwd(),
    help="Path where the new site will be created.",
)
@click.option(
    "--template",
    "-t",
    type=click.Choice(["blog", "portfolio", "minimal", "solar"]),
    default="minimal",
    help="Site template to use.",
)
@click.option("--name", "-n", help="Site name (used in configuration).")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files.")
def new(path, template, name, force):
    """Create a new Sonne site from a template."""
    try:
        site_path = Path(path)
        site_name = name or site_path.name

        if site_path.exists() and any(site_path.iterdir()) and not force:
            logger.error(f"Directory exists and is not empty: {site_path}")
            logger.error("Use --force to overwrite existing files")
            sys.exit(1)

        logger.info(f"Creating new {template} site: {site_name} at {site_path}")
        os.makedirs(site_path, exist_ok=True)
        _copy_site_template(template, site_path)
        _set_site_title(site_path / "sonne.yaml", site_name)

        logger.info(f"Site created successfully at {site_path}")
        logger.info("To build your site, run: sonne build")

    except Exception as e:
        logger.error(f"Error creating site: {e}")
        _print_traceback_if_verbose()
        sys.exit(1)


def _copy_site_template(template: str, site_path: Path) -> None:
    template_dir = Path(__file__).parent.parent / "templates" / template
    if not template_dir.exists():
        logger.error(f"Template not found: {template}")
        sys.exit(1)
    copytree(
        template_dir,
        site_path,
        dirs_exist_ok=True,
        ignore=ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git"),
    )


def _set_site_title(config_path: Path, site_name: str) -> None:
    """Write the site name into the template's own config, if it has one.

    Edits the YAML directly — loading through Config would merge in every
    default and dump the whole tree over the template's minimal config.
    """
    if not config_path.exists():
        return
    with open(config_path, "r", encoding="utf-8") as f:
        site_config = yaml.safe_load(f) or {}
    site_config.setdefault("site", {})["title"] = site_name
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(site_config, f, default_flow_style=False, sort_keys=False)


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with quiet logging."""

    def log_message(self, format, *args):
        """Suppress log messages unless in debug mode."""
        if logger.isEnabledFor(logging.DEBUG):
            super().log_message(format, *args)


class ReuseAddrTCPServer(socketserver.TCPServer):
    """TCPServer that can rebind immediately after a restart (no TIME_WAIT wait)."""

    allow_reuse_address = True


def _rebuild_site(base_dir: str) -> None:
    """Rebuild a site with a freshly loaded config.

    Used by serve --watch: the config file is in the watch set, so each
    rebuild must re-read it rather than reuse the Config captured at
    serve startup.

    Args:
        base_dir: Absolute path to the site directory.
    """
    config = Config(base_dir=base_dir)
    generator = SiteGenerator(config, base_dir=base_dir)
    generator.generate(skip_cache=False)


@cli.command()
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True),
    default=os.getcwd(),
    help="Path to the site directory.",
)
@click.option("--port", default=None, type=int, help="Port to serve on.")
@click.option("--host", default=None, help="Host to serve on.")
@click.option("--browser/--no-browser", default=True, help="Open in browser.")
@click.option("--watch/--no-watch", default=True, help="Watch for changes and rebuild.")
def serve(path, port, host, browser, watch):
    """Serve the site locally for development.

    Always builds the site first, then starts a local web server. With --watch
    enabled (default), the site automatically rebuilds when you make changes to
    content, templates, static files, scripts, or the config.

    Examples:
        sonne serve                        # Serve on http://localhost:8000
        sonne serve --port 3000           # Use different port
        sonne serve --no-browser          # Don't open browser
        sonne serve --no-watch            # Disable auto-rebuild
    """
    observer = None
    httpd = None
    try:
        # Resolve up front: relative paths would otherwise break watch
        # rebuilds and observer scheduling.
        path = os.path.abspath(path)
        if not check_sonne_directory(path):
            sys.exit(1)

        config = Config(base_dir=path)
        host = _configured_or_default(host, config.get("serve", "host"), DEFAULT_SERVE_HOST)
        port = _configured_or_default(port, config.get("serve", "port"), DEFAULT_SERVE_PORT)
        output_path = config.get("paths", "output", default="output")
        output_dir = output_path if os.path.isabs(output_path) else os.path.join(path, output_path)

        _initial_build_or_exit(config, path)

        # Serve the output dir without chdir'ing into it (a chdir broke
        # every later relative-path resolution in watch rebuilds)
        handler = functools.partial(QuietHTTPRequestHandler, directory=output_dir)
        httpd = ReuseAddrTCPServer((host, port), handler)

        if watch:
            observer = _start_watching(path, config)

        url = f"http://{host}:{port}"
        if browser:
            threading.Timer(BROWSER_OPEN_DELAY_SECONDS, lambda: webbrowser.open(url)).start()

        click.echo(f"Serving at {url}  (Ctrl+C to stop)")
        httpd.serve_forever()

    except KeyboardInterrupt:
        click.echo("\nServer stopped")
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        _print_traceback_if_verbose()
        sys.exit(1)
    finally:
        if observer is not None:
            observer.stop()
            observer.join(timeout=OBSERVER_STOP_TIMEOUT_SECONDS)
        if httpd is not None:
            httpd.server_close()


def _configured_or_default(cli_value, config_value, default):
    """The CLI value if given, else the config value if set, else default."""
    if cli_value is not None:
        return cli_value
    if config_value is not None:
        return config_value
    return default


def _initial_build_or_exit(config: Config, path: str) -> None:
    click.echo("Building site...")
    try:
        SiteGenerator(config, base_dir=path).generate()
    except Exception as e:
        logger.error(f"Initial build failed: {e}")
        _print_traceback_if_verbose()
        sys.exit(1)
    click.echo("Build complete")


class SiteRebuilder:
    """Debounced rebuilds of one site in response to file changes.

    Knows which paths matter (the configured source directories and every
    config filename) and coalesces bursts of events into one rebuild.
    Independent of the file-watching library; see _start_watching.
    """

    DEBOUNCE_SECONDS = 0.4

    def __init__(self, base_dir: str, config: Config):
        self.base_dir = base_dir
        self._lock = threading.Lock()
        self._pending = None  # pending debounce timer
        self._building = False
        self._rerun_requested = False  # a change arrived while building

        self.watch_dirs = [
            directory
            for directory in [
                config.get("paths", "content"),
                config.get("paths", "data"),
                config.get("paths", "scripts"),
                config.get("paths", "static"),
                config.get("paths", "templates"),
            ]
            if directory
        ]
        # Same candidate list config discovery uses — a project using
        # .sonne.yaml etc. must also rebuild on config edits.
        self.watch_files = list(CONFIG_FILENAMES)
        self._watched_roots = [
            Path(os.path.normpath(os.path.join(base_dir, watched)))
            for watched in self.watch_dirs + self.watch_files
        ]

    def file_changed(self, changed_path: str) -> None:
        """Schedule a rebuild if changed_path affects the site."""
        if not self.affects_site(changed_path):
            return
        # Reset debounce timer on every relevant event
        with self._lock:
            if self._pending:
                self._pending.cancel()
            self._pending = threading.Timer(self.DEBOUNCE_SECONDS, self._rebuild)
            self._pending.daemon = True
            self._pending.start()

    def affects_site(self, changed_path: str) -> bool:
        """Whether changed_path is a config file or inside a watched directory.

        Compared by path components, so configured paths may use either
        separator, a ./ prefix, or be absolute.
        """
        changed = Path(os.path.abspath(changed_path))
        return any(changed == root or root in changed.parents for root in self._watched_roots)

    def _rebuild(self) -> None:
        """Rebuild; if another change lands mid-build, rebuild again after it.

        The build may already have read the changed file's old contents, so
        a change during a build must not be dropped.
        """
        with self._lock:
            if self._building:
                self._rerun_requested = True
                return
            self._building = True
        try:
            while True:
                self._rebuild_once()
                with self._lock:
                    if not self._rerun_requested:
                        self._building = False
                        return
                    self._rerun_requested = False
        except BaseException:
            # Only abnormal exits get here; the normal exit above already
            # released the flag under the lock.
            with self._lock:
                self._building = self._rerun_requested = False
            raise

    def _rebuild_once(self) -> None:
        try:
            click.echo("\nChange detected — rebuilding...")
            # Fresh Config: the edit may have BEEN the config
            _rebuild_site(self.base_dir)
            click.echo("Rebuilt")
        except Exception as e:
            click.echo(f"Rebuild failed: {e}")
            _print_traceback_if_verbose()


def _paths_touched_by(event) -> List[str]:
    """Paths a watchdog event affects.

    A move reports both ends: editors that save by writing a temp file and
    renaming it over the original produce only a move whose destination is
    the real file. Moves count for directories too (a folder of posts moved
    into content/); other directory events are ignored.
    """
    if event.event_type == "moved":
        return [path for path in (event.src_path, getattr(event, "dest_path", "")) if path]
    return [] if event.is_directory else [event.src_path]


def _start_watching(path: str, config: Config):
    """Start a watchdog observer that feeds a SiteRebuilder.

    Returns:
        The running observer, or None when watchdog is not installed.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        click.echo("watchdog not installed — file watching disabled")
        click.echo("Install with: pip install watchdog")
        return None

    rebuilder = SiteRebuilder(path, config)

    class _WatchdogAdapter(FileSystemEventHandler):
        def on_any_event(self, event):
            for changed_path in _paths_touched_by(event):
                rebuilder.file_changed(changed_path)

    observer = Observer()
    observer.schedule(_WatchdogAdapter(), path, recursive=True)
    observer.start()
    click.echo(f"Watching: {', '.join(rebuilder.watch_dirs + ['config'])}")
    return observer


def main():
    """Main entry point for CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
