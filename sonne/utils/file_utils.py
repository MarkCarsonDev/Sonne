"""
File utility functions for Sonne.
Provides utilities for file operations like copying, ensuring directories exist, etc.
"""

import os
import shutil
import logging
import glob
from typing import Callable, Optional, Union

logger = logging.getLogger("sonne")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_STATIC_DIR = os.path.join(PACKAGE_DIR, "static")
BUNDLED_MINIMAL_STATIC_DIR = os.path.join(PACKAGE_DIR, "templates", "minimal", "static")

# Core (package) assets: output subdirectory -> filename pattern.
CORE_ASSET_PATTERNS = {"css": "*.css", "js": "*.js"}


def ensure_dir(directory: Union[str, "os.PathLike[str]"]) -> None:
    """Ensure a directory exists, creating it if necessary.

    Args:
        directory: Path to the directory.
    """
    os.makedirs(directory, exist_ok=True)


def copy_core_static_files(output_dir: str) -> None:
    """Copy the package's own CSS/JS (the dithering assets) to the output directory.

    Args:
        output_dir: Output directory path.
    """
    if not os.path.exists(CORE_STATIC_DIR):
        return
    for subdir, pattern in CORE_ASSET_PATTERNS.items():
        destination = os.path.join(output_dir, subdir)
        os.makedirs(destination, exist_ok=True)
        for asset in glob.glob(os.path.join(CORE_STATIC_DIR, subdir, pattern)):
            shutil.copy2(asset, destination)
    logger.debug(f"Copied core static files to {output_dir}")


def copy_static_files(
    static_dir: Optional[str], output_dir: str, skip: Optional[Callable[[str], bool]] = None
) -> None:
    """Copy static files to the output directory, skipping hidden entries.

    A missing static directory only warns: SiteGenerator then falls back to
    the template's static files (copy_template_static_files), and emits the
    package's dithering assets only when dithering is enabled. A file that
    fails to copy is logged and skipped.

    Args:
        static_dir: Path to the static directory.
        output_dir: Path to the output directory.
        skip: Optional predicate on a source file path; files it accepts are
            not copied (e.g. ImageProcessor.owns_static_file, whose outputs
            the image pipeline writes).
    """
    if not static_dir or not os.path.exists(static_dir):
        logger.warning(f"Static directory does not exist or is not specified: {static_dir}")
        return

    for root, dirs, files in os.walk(static_dir):
        dirs[:] = [d for d in dirs if not _is_hidden(d)]
        rel_path = os.path.relpath(root, static_dir)
        if rel_path != ".":
            ensure_dir(os.path.join(output_dir, rel_path))
        for filename in files:
            source_file = os.path.join(root, filename)
            if _is_hidden(filename) or (skip and skip(source_file)):
                continue
            _copy_static_file(source_file, os.path.join(output_dir, rel_path, filename))


def _is_hidden(name: str) -> bool:
    return name.startswith(".")


def _copy_static_file(source_file: str, dest_file: str) -> None:
    try:
        shutil.copy2(source_file, dest_file)
        logger.debug(f"Copied static file: {source_file} -> {dest_file}")
    except Exception as e:
        logger.error(f"Error copying static file {source_file}: {e}")


def copy_template_static_files(base_dir: str, output_dir: str) -> None:
    """Copy the first template static directory found to the output directory.

    Candidates in order: <site>/templates/static,
    <site>/templates/minimal/static, then the bundled minimal template's.

    Args:
        base_dir: Base directory of the site.
        output_dir: Path to the output directory.
    """
    candidates = [
        os.path.join(base_dir, "templates", "static"),
        os.path.join(base_dir, "templates", "minimal", "static"),
        BUNDLED_MINIMAL_STATIC_DIR,
    ]
    static_dir = next((candidate for candidate in candidates if os.path.exists(candidate)), None)
    if static_dir is None:
        logger.warning("No template static directory found. Some CSS/JS files may be missing.")
        return

    logger.info(f"Found template static directory: {static_dir}")
    copy_static_files(static_dir, output_dir)
