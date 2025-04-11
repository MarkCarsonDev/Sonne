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

from sonne.core.config import Config
from sonne.core.site_generator import SiteGenerator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('sonne')

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
@click.pass_context
def build(ctx, path, config, clean, skip_images, skip_cache, dev):
    """Build the static site."""
    try:
        logger.info(f"Building site in {path}")
        
        # Load configuration
        config_path = config or None
        config_obj = Config(config_path)
        
        # Set environment if --dev flag is used
        if dev:
            config_obj.set('environment', value='dev')
            logger.info("Building in development environment")
        
        # Initialize site generator
        generator = SiteGenerator(config_obj, base_dir=path)
        
        # Clean if requested
        if clean:
            output_dir = config_obj.get('paths', 'output')
            logger.info(f"Cleaning output directory: {output_dir}")
            generator.clean_output()
            
        # Generate site
        generator.generate(skip_images=skip_images, skip_cache=skip_cache)
        
        # Calculate elapsed time
        elapsed = time.time() - ctx.obj['start_time']
        output_dir = os.path.abspath(config_obj.get('paths', 'output'))
        
        logger.info(f"Site built successfully in {elapsed:.2f} seconds")
        logger.info(f"Output directory: {output_dir}")
        
    except Exception as e:
        logger.error(f"Error building site: {e}")
        if logger.level <= logging.DEBUG:
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
@click.option('--port', default=8000, help='Port to serve on.')
@click.option('--host', default='localhost', help='Host to serve on.')
@click.option('--browser/--no-browser', default=True, help='Open in browser.')
@click.option('--watch/--no-watch', default=True, help='Watch for changes and rebuild.')
def serve(path, port, host, browser, watch):
    """Serve the site locally for development."""
    try:
        # Get configuration
        config = Config(os.path.join(path, 'sonne.yaml'))
        output_dir = os.path.join(path, config.get('paths', 'output'))
        
        # Check if output directory exists
        if not os.path.exists(output_dir):
            logger.warning(f"Output directory does not exist: {output_dir}")
            logger.warning("Building site first...")
            
            # Build site
            generator = SiteGenerator(config, base_dir=path)
            generator.generate()
        
        # Change to output directory
        os.chdir(output_dir)
        
        # Set up server
        handler = QuietHTTPRequestHandler
        httpd = socketserver.TCPServer((host, port), handler)
        
        # Set up file watching if requested
        if watch:
            try:
                from watchdog.observers import Observer
                from watchdog.events import FileSystemEventHandler
                
                class RebuildHandler(FileSystemEventHandler):
                    def __init__(self, base_dir):
                        self.base_dir = base_dir
                        self.is_building = False
                        
                    def on_any_event(self, event):
                        # Skip if currently building or if the event is in output directory
                        if self.is_building or output_dir in event.src_path:
                            return
                            
                        try:
                            logger.info(f"Change detected: {event.src_path}")
                            logger.info("Rebuilding site...")
                            
                            self.is_building = True
                            generator = SiteGenerator(config, base_dir=self.base_dir)
                            generator.generate(skip_cache=False)  # Use cache for faster rebuilds
                            
                            logger.info("Site rebuilt successfully")
                        except Exception as e:
                            logger.error(f"Error rebuilding site: {e}")
                        finally:
                            self.is_building = False
                
                # Start file watcher
                event_handler = RebuildHandler(path)
                observer = Observer()
                observer.schedule(event_handler, path, recursive=True)
                observer.start()
                logger.info("Watching for changes")
                
            except ImportError:
                logger.warning("watchdog package not installed; file watching disabled")
                logger.warning("Install with: pip install watchdog")
                watch = False
        
        # Open browser if requested
        if browser:
            url = f"http://{host}:{port}"
            threading.Timer(1.0, lambda: webbrowser.open(url)).start()
        
        # Start server
        logger.info(f"Serving site at http://{host}:{port}")
        logger.info("Press Ctrl+C to stop")
        httpd.serve_forever()
        
    except KeyboardInterrupt:
        logger.info("Server stopped")
        if watch:
            observer.stop()
            observer.join()
    except Exception as e:
        logger.error(f"Error serving site: {e}")
        if logger.level <= logging.DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(1)

def main():
    """Main entry point for CLI."""
    cli(obj={})

if __name__ == '__main__':
    main()