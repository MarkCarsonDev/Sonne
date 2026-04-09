"""
Command-line interface for Sonne static site generator.
Provides commands for creating, building, and serving static sites.
"""

import click
import os
import sys
import time
import logging
import http.server
import socketserver
import webbrowser
import threading
from pathlib import Path
from shutil import copytree, ignore_patterns
from typing import Optional

try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeRemainingColumn,
    )
    from rich.panel import Panel
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None

from sonne.core.config import Config
from sonne.core.site_generator import SiteGenerator
from sonne.utils.path_utils import is_sonne_directory

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('sonne')

# Initialize rich console if available
console = Console() if RICH_AVAILABLE else None


def check_sonne_directory(path: str, command_name: str = "command") -> bool:
    """Check if directory looks like a Sonne project and provide helpful guidance.

    Args:
        path: Directory path to check.
        command_name: Name of the command being run (for error messages).

    Returns:
        True if appears to be Sonne directory, False otherwise.
    """
    if not is_sonne_directory(path):
        error_msg = f"\n❌ This doesn't appear to be a Sonne project directory.\n"

        if console and RICH_AVAILABLE:
            console.print(Panel(
                "[bold red]Not a Sonne Project[/bold red]\n\n"
                f"The directory [cyan]{path}[/cyan] doesn't contain a Sonne configuration file.\n\n"
                "[bold]To create a new Sonne site:[/bold]\n"
                "  sonne new -p my-site -t blog\n\n"
                "[bold]Expected files:[/bold]\n"
                "  • sonne.yaml or sonne.yml\n"
                "  • content/ directory\n"
                "  • templates/ directory\n",
                title="Error",
                border_style="red"
            ))
        else:
            logger.error(error_msg)
            logger.error(f"The directory {path} doesn't contain a Sonne configuration file.")
            logger.error("")
            logger.error("To create a new Sonne site:")
            logger.error("  sonne new -p my-site -t blog")
            logger.error("")
            logger.error("Expected files:")
            logger.error("  • sonne.yaml or sonne.yml")
            logger.error("  • content/ directory")
            logger.error("  • templates/ directory")

        return False

    return True

# Main CLI group
@click.group()
@click.version_option()
@click.option('--verbose', '-v', count=True, help='Increase verbosity.')
@click.option('--quiet', '-q', is_flag=True, help='Suppress all output except errors.')
@click.pass_context
def cli(ctx, verbose, quiet):
    """Sonne - A minimalist static site generator optimized for low footprint sites.
    
    Designed to create efficient websites with minimal resource requirements.
    """
    # Set up logging based on verbosity
    if quiet:
        logger.setLevel(logging.ERROR)
    else:
        levels = [logging.INFO, logging.DEBUG]
        logger.setLevel(levels[min(verbose, len(levels)-1)])
        
    # Initialize context
    ctx.ensure_object(dict)
    ctx.obj['start_time'] = time.time()

@cli.command()
@click.option('--path', '-p', type=click.Path(exists=True), default=os.getcwd(),
              help='Path to the site directory.')
@click.option('--config', '-c', type=click.Path(exists=False),
              help='Path to the configuration file.')
@click.option('--clean', is_flag=True, help='Clean the output directory before building.')
@click.option('--skip-images', is_flag=True, help='Skip image processing during build.')
@click.option('--skip-cache', is_flag=True, help='Ignore cache and rebuild everything.')
@click.option('--dev', is_flag=True, help='Build site for development environment.')
@click.option('--no-progress', is_flag=True, help='Disable progress bars.')
@click.option('--perf', is_flag=True, help='Show detailed performance breakdown after build.')
@click.pass_context
def build(ctx, path, config, clean, skip_images, skip_cache, dev, no_progress, perf):
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
        # Check if this looks like a Sonne project
        if not check_sonne_directory(path, "build"):
            sys.exit(1)

        if console and RICH_AVAILABLE and not no_progress:
            console.print(f"\n[bold cyan]Building Sonne Site[/bold cyan]")
            console.print(f"[dim]Location: {path}[/dim]\n")
        else:
            logger.info(f"Build started  [{path}]")

        # Load configuration
        config_path = config or None
        config_obj = Config(config_path, base_dir=path)

        # Validate configuration
        validation_warnings = config_obj.validate()
        if validation_warnings:
            if console and RICH_AVAILABLE:
                console.print(f"[yellow]Configuration warnings ({len(validation_warnings)}):[/yellow]")
                for warning in validation_warnings:
                    console.print(f"  [yellow]-[/yellow] {warning}")
                console.print()
            else:
                logger.warning(f"Configuration warnings ({len(validation_warnings)}):")
                for warning in validation_warnings:
                    logger.warning(f"  {warning}")

        # Set environment if --dev flag is used
        if dev:
            config_obj.set('environment', value='dev')
            logger.info("Environment: development")

        # Initialize site generator
        generator = SiteGenerator(config_obj, base_dir=path)

        # Validate templates before building
        template_errors = generator.template_processor.validate_templates()
        if template_errors:
            if console and RICH_AVAILABLE:
                console.print(f"\n[bold red]Template validation errors ({len(template_errors)}):[/bold red]")
                for error in template_errors:
                    console.print(f"  [red]-[/red] {error}")
                console.print()
            else:
                logger.error(f"Template validation errors ({len(template_errors)}):")
                for error in template_errors:
                    logger.error(f"  {error}")

            if not click.confirm("Templates have errors. Continue anyway?", default=False):
                logger.info("Build cancelled")
                sys.exit(1)

        # Clean if requested
        if clean:
            output_dir = config_obj.get('paths', 'output')
            if console and RICH_AVAILABLE:
                console.print(f"[yellow]Cleaning output directory...[/yellow]")
            else:
                logger.info(f"Cleaning output directory  [{output_dir}]")
            generator.clean_output()

        # Generate site
        stats = generator.generate(skip_images=skip_images, skip_cache=skip_cache)

        # Calculate elapsed time
        elapsed = time.time() - ctx.obj['start_time']
        output_dir = os.path.abspath(config_obj.get('paths', 'output'))

        if console and RICH_AVAILABLE:
            console.print(f"\n[bold green]Build complete[/bold green]  ({elapsed:.2f}s)")
            console.print(f"[dim]Output: {output_dir}[/dim]\n")
        else:
            logger.info(f"Build complete  {elapsed:.2f}s  [{output_dir}]")

        # Show performance report if requested
        if perf and stats:
            click.echo(stats.format_report(verbose=True, perf=True))

    except Exception as e:
        if console and RICH_AVAILABLE:
            console.print(f"\n[bold red]Build failed:[/bold red] {e}\n")
        else:
            logger.error(f"Build failed: {e}")

        import traceback
        traceback.print_exc()
        sys.exit(1)

@cli.command()
@click.option('--path', '-p', type=click.Path(), default=os.getcwd(),
              help='Path where the new site will be created.')
@click.option('--template', '-t', type=click.Choice(['blog', 'portfolio', 'minimal', 'solar']),
              default='minimal', help='Site template to use.')
@click.option('--name', '-n', help='Site name (used in configuration).')
@click.option('--force', '-f', is_flag=True, help='Overwrite existing files.')
def new(path, template, name, force):
    """Create a new Sonne site from a template."""
    try:
        site_path = Path(path)
        site_name = name or site_path.name
        
        # Check if directory exists and is not empty
        if site_path.exists() and any(site_path.iterdir()) and not force:
            logger.error(f"Directory exists and is not empty: {site_path}")
            logger.error("Use --force to overwrite existing files")
            sys.exit(1)
            
        logger.info(f"Creating new {template} site: {site_name} at {site_path}")
        
        # Ensure the directory exists
        os.makedirs(site_path, exist_ok=True)
        
        # Get template directory
        template_dir = Path(__file__).parent.parent / 'templates' / template
        if not template_dir.exists():
            logger.error(f"Template not found: {template}")
            sys.exit(1)
            
        # Copy template files
        copytree(template_dir, site_path, dirs_exist_ok=True, 
                 ignore=ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.git'))
        
        # Update configuration with site name
        config_path = site_path / 'sonne.yaml'
        if config_path.exists():
            config = Config(config_path)
            config.set('site', 'title', value=site_name)
            config.save()
        
        logger.info(f"Site created successfully at {site_path}")
        logger.info("To build your site, run: sonne build")
        
    except Exception as e:
        logger.error(f"Error creating site: {e}")
        if logger.level <= logging.DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(1)

class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with quiet logging."""
    
    def log_message(self, format, *args):
        """Suppress log messages unless in debug mode."""
        if logger.level <= logging.DEBUG:
            super().log_message(format, *args)

@cli.command()
@click.option('--path', '-p', type=click.Path(exists=True), default=os.getcwd(),
              help='Path to the site directory.')
@click.option('--port', default=None, type=int, help='Port to serve on.')
@click.option('--host', default=None, help='Host to serve on.')
@click.option('--browser/--no-browser', default=True, help='Open in browser.')
@click.option('--watch/--no-watch', default=True, help='Watch for changes and rebuild.')
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
    try:
        if not check_sonne_directory(path, "serve"):
            sys.exit(1)

        config = Config(base_dir=path)
        if host is None:
            host = config.get('serve', 'host') or 'localhost'
        if port is None:
            port = config.get('serve', 'port') or 8000
        output_dir = os.path.join(path, config.get('paths', 'output'))

        # Always build before serving
        click.echo("Building site...")
        try:
            generator = SiteGenerator(config, base_dir=path)
            generator.generate()
            click.echo("✓ Build complete")
        except Exception as e:
            logger.error(f"Initial build failed: {e}")
            if logger.level <= logging.DEBUG:
                import traceback
                traceback.print_exc()
            sys.exit(1)

        # Serve from output dir
        os.chdir(output_dir)
        handler = QuietHTTPRequestHandler
        httpd = socketserver.TCPServer((host, port), handler)

        # File watching with debounce
        if watch:
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler

                class RebuildHandler(FileSystemEventHandler):
                    DEBOUNCE_SECONDS = 0.4

                    def __init__(self, base_dir, config):
                        self.base_dir = base_dir
                        self.config = config
                        self._lock = threading.Lock()
                        self._pending = None          # pending debounce timer
                        self._building = False

                        self.watch_dirs = [
                            d for d in [
                                config.get('paths', 'content'),
                                config.get('paths', 'data'),
                                config.get('paths', 'scripts'),
                                config.get('paths', 'static'),
                                config.get('paths', 'templates'),
                            ] if d
                        ]
                        self.watch_files = [
                            'sonne.yaml', 'sonne.yml', 'sonne.json', 'sonne.config'
                        ]

                    def _relevant(self, event_path):
                        try:
                            rel = os.path.relpath(event_path, self.base_dir)
                        except ValueError:
                            return False
                        if any(rel == f or rel.startswith(f + os.sep) for f in self.watch_files):
                            return True
                        return any(rel.startswith(d + os.sep) or rel == d for d in self.watch_dirs)

                    def on_any_event(self, event):
                        if event.is_directory:
                            return
                        if not self._relevant(event.src_path):
                            return
                        # Reset debounce timer on every relevant event
                        with self._lock:
                            if self._pending:
                                self._pending.cancel()
                            self._pending = threading.Timer(
                                self.DEBOUNCE_SECONDS, self._rebuild
                            )
                            self._pending.daemon = True
                            self._pending.start()

                    def _rebuild(self):
                        with self._lock:
                            if self._building:
                                return
                            self._building = True
                        try:
                            click.echo("\nChange detected — rebuilding...")
                            generator = SiteGenerator(self.config, base_dir=self.base_dir)
                            generator.generate(skip_cache=False)
                            click.echo("✓ Rebuilt")
                        except Exception as e:
                            click.echo(f"✗ Rebuild failed: {e}")
                            if logger.level <= logging.DEBUG:
                                import traceback
                                traceback.print_exc()
                        finally:
                            with self._lock:
                                self._building = False

                event_handler = RebuildHandler(path, config)
                observer = Observer()
                observer.schedule(event_handler, path, recursive=True)
                observer.start()

                watched = ', '.join(event_handler.watch_dirs + ['config'])
                click.echo(f"Watching: {watched}")

            except ImportError:
                click.echo("watchdog not installed — file watching disabled")
                click.echo("Install with: pip install watchdog")
                watch = False

        url = f"http://{host}:{port}"
        if browser:
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()

        click.echo(f"Serving at {url}  (Ctrl+C to stop)")
        httpd.serve_forever()

    except KeyboardInterrupt:
        click.echo("\nServer stopped")
        if observer is not None:
            observer.stop()
            observer.join()
    except Exception as e:
        logger.error(f"Error: {e}")
        if logger.level <= logging.DEBUG:
            import traceback
            traceback.print_exc()
        if observer is not None:
            observer.stop()
        sys.exit(1)

def main():
    """Main entry point for CLI."""
    cli(obj={})

if __name__ == '__main__':
    main()