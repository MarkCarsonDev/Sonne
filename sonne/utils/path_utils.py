"""
Path utility functions for Sonne.
Provides secure path handling, validation, and sanitization.
"""

import logging
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Union

logger = logging.getLogger("sonne")

# "scheme:" at the start of a URL (RFC 3986), e.g. https:, data:, mailto:.
URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

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

# How many directories config discovery examines: the base directory and
# its ancestors.
CONFIG_SEARCH_DEPTH = 3

# Device names Windows reserves regardless of extension.
WINDOWS_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{number}" for number in range(1, 10)]
    + [f"LPT{number}" for number in range(1, 10)]
)

# Characters Windows forbids in filenames (< > : " | ? *) plus control characters.
DANGEROUS_FILENAME_CHARS = r'[<>:"|?*\x00-\x1f\x7f]'


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

    # Replacing separators leaves a single name, so ".." inside it cannot
    # traverse; the strip below turns "." and ".." themselves into "".
    filename = filename.replace("/", replace_char)
    filename = filename.replace("\\", replace_char)

    filename = re.sub(DANGEROUS_FILENAME_CHARS, replace_char, filename)

    # Remove leading/trailing spaces and dots (problematic on Windows)
    filename = filename.strip(". ")

    if Path(filename).stem.upper() in WINDOWS_RESERVED_NAMES:
        filename = f"{replace_char}{filename}"

    return filename or "unnamed"


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
    except (ValueError, RuntimeError, OSError):
        # ValueError: path is not relative to root (or has a NUL byte)
        # RuntimeError: infinite loop in resolution (symlink loops)
        # OSError: the path cannot be resolved (e.g. unavailable drive)
        return False


def sorted_paths(paths: Iterable[Union[str, Path]]) -> list[Path]:
    """Paths in a platform-independent order (case-sensitive, by '/'-joined text).

    Directory listings and globs come back in filesystem order, which
    differs between OSes (and Path ordering itself is case-insensitive on
    Windows only), so anything whose result depends on order sorts first.
    """
    return sorted((Path(path) for path in paths), key=lambda path: path.as_posix())


def is_post_local_raster_image(src: str) -> bool:
    """Whether an image reference is a raster file relative to its page or post.

    Only these get the blog pipeline's resized and dithered copies. The
    template processor (which rewrites <img> markup to the dithered copy)
    and the blog processor (which writes that copy) must agree exactly,
    so both call this.

    Args:
        src: Image reference as written (URL, path, or data: URI).

    Returns:
        False for anything with a URL scheme (http:, https:, data:, ...),
        root-absolute and protocol-relative paths (served from static/), and
        SVGs (checked case-insensitively, ignoring any query or fragment).
    """
    if not src or src.startswith("/") or URL_SCHEME.match(src):
        return False
    path = re.split(r"[?#]", src, maxsplit=1)[0]
    return not path.lower().endswith(".svg")


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


def normalize_web_path(path: Union[str, Path]) -> str:
    """Normalize a filesystem path to a web path (forward slashes).

    Args:
        path: Filesystem path.

    Returns:
        Web-compatible path string.
    """
    return re.sub(r"/+", "/", str(path).replace("\\", "/"))
