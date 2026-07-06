"""
Path utility functions for Sonne.
Provides secure path handling, validation, and sanitization.
"""

import re
from pathlib import Path
from typing import Optional, Union
import logging

logger = logging.getLogger("sonne")

# Config filenames Sonne recognizes, in discovery order. Single source of
# truth for config discovery, project detection, AND the serve watcher —
# these previously kept three diverging copies.
CONFIG_FILENAMES = [
    "sonne.yaml",
    "sonne.yml",
    "sonne.json",
    ".sonne/config.yaml",
    "sonne.config",
    ".sonne.yaml",
    ".sonne.json",
]


def sanitize_filename(filename: str, replace_char: str = "_") -> str:
    """Sanitize a filename by removing/replacing dangerous characters.

    Args:
        filename: The filename to sanitize.
        replace_char: Character to use for replacing invalid characters.

    Returns:
        Sanitized filename safe for filesystem use.
    """
    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove path separators and parent directory references
    filename = filename.replace("..", "")
    filename = filename.replace("/", replace_char)
    filename = filename.replace("\\", replace_char)

    # Remove other dangerous characters
    # Windows reserved: < > : " | ? *
    # Also remove control characters
    dangerous_chars = r'[<>:"|?*\x00-\x1f\x7f]'
    filename = re.sub(dangerous_chars, replace_char, filename)

    # Remove leading/trailing spaces and dots (problematic on Windows)
    filename = filename.strip(". ")

    # Handle Windows reserved names
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in reserved_names:
        filename = f"{replace_char}{filename}"

    # Ensure filename isn't empty
    if not filename:
        filename = "unnamed"

    return filename


def validate_path_within_root(path: Union[str, Path], root: Union[str, Path]) -> bool:
    """Validate that a path is within a root directory (prevents path traversal).

    Args:
        path: The path to validate.
        root: The root directory path should be within.

    Returns:
        True if path is within root, False otherwise.
    """
    try:
        path = Path(path).resolve()
        root = Path(root).resolve()

        # Check if path is relative to root
        path.relative_to(root)
        return True
    except (ValueError, RuntimeError):
        # ValueError: path is not relative to root
        # RuntimeError: infinite loop in resolution (symlink loops)
        return False


def safe_join(base: Union[str, Path], *paths: Union[str, Path]) -> Optional[Path]:
    """Safely join paths, ensuring result is within base directory.

    Args:
        base: Base directory path.
        *paths: Path components to join.

    Returns:
        Joined path if valid, None if path traversal detected.
    """
    try:
        base = Path(base).resolve()
        joined = base.joinpath(*paths).resolve()

        # Verify the joined path is within base
        if validate_path_within_root(joined, base):
            return joined
        else:
            logger.error(f"Path traversal detected: {paths} escapes {base}")
            return None
    except (ValueError, RuntimeError) as e:
        logger.error(f"Error joining paths {base} + {paths}: {e}")
        return None


def strip_relative_prefix(path: str) -> str:
    """Remove leading ``./`` segments from a relative path string.

    Unlike ``str.lstrip('./')`` (which strips a *character set* and corrupted
    ``../images/a.jpg`` into ``images/a.jpg`` and ``.hidden/`` into
    ``hidden/``), this only removes literal ``./`` prefixes.

    Args:
        path: Relative path string (any separator style).

    Returns:
        Path without leading ``./`` segments; ``../`` prefixes and leading
        dots in filenames are preserved.
    """
    return re.sub(r"^(\./)+", "", path)


def is_sonne_directory(directory: Union[str, Path]) -> bool:
    """Check if a directory appears to be a valid Sonne project.

    Args:
        directory: Directory to check.

    Returns:
        True if directory looks like a Sonne project, False otherwise.
    """
    directory = Path(directory)

    # Check for config file
    has_config = any((directory / f).exists() for f in CONFIG_FILENAMES)

    # Check for typical Sonne directories
    typical_dirs = ["content", "templates", "static"]
    has_typical_structure = any((directory / d).exists() for d in typical_dirs)

    return has_config or has_typical_structure


def get_relative_path_safe(path: Union[str, Path], start: Union[str, Path]) -> Optional[Path]:
    """Get relative path safely, handling edge cases.

    Args:
        path: The path to make relative.
        start: The starting path.

    Returns:
        Relative path, or None if paths are on different drives/not relatable.
    """
    try:
        path = Path(path)
        start = Path(start)
        return path.relative_to(start)
    except (ValueError, TypeError):
        logger.warning(f"Cannot make {path} relative to {start}")
        return None


def normalize_web_path(path: Union[str, Path]) -> str:
    """Normalize a filesystem path to a web path (forward slashes).

    Args:
        path: Filesystem path.

    Returns:
        Web-compatible path string.
    """
    path_str = str(path)
    # Replace backslashes with forward slashes
    web_path = path_str.replace("\\", "/")
    # Remove double slashes
    web_path = re.sub(r"/+", "/", web_path)
    return web_path
