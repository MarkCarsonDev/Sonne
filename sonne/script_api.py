"""
The functions Sonne data scripts call to hand data to templates.

Import them in ``scripts/*.py`` (and ``footer.py``) so editors, type
checkers and linters know where they come from::

    from sonne.script_api import get_variable, sonne_config, sonne_filter, sonne_var

    city = sonne_config("site", "weather", "city", default="Berlin")
    projects = [p for p in get_variable("all_pages", []) if p["section"] == "projects"]
    sonne_var("team", [{"name": "Ada", "role": "Engineer"}])
    sonne_filter("shout", lambda text: str(text).upper())

They only work while Sonne is running the script during a build; each call
goes to the build that is executing the script. Calling them anywhere else
raises RuntimeError. (For backward compatibility the same functions
are also injected into every script as globals, so older scripts without
the import keep working; the import is the preferred, documented form.)
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from PIL import Image

__all__ = [
    "dither_image",
    "get_post",
    "get_variable",
    "sonne_config",
    "sonne_filter",
    "sonne_global",
    "sonne_var",
]

Post = dict[str, Any]


@dataclass(frozen=True)
class ScriptHooks:
    """One build's implementations of the script API (provided by VariableManager)."""

    sonne_var: Callable[[str, Any], None]
    get_post: Callable[[Optional[str], Optional[str]], Optional[Post]]
    sonne_filter: Callable[[str, Callable[..., Any]], None]
    sonne_global: Callable[[str, Any], None]
    sonne_config: Callable[..., Any]
    get_variable: Callable[..., Any]
    dither_image: Callable[["Image.Image"], "Image.Image"]

    def as_globals(self) -> dict[str, Callable[..., Any]]:
        """The hooks by name, for injecting into a script module's globals."""
        return {field.name: getattr(self, field.name) for field in fields(self)}


_active_hooks: ContextVar[Optional[ScriptHooks]] = ContextVar("sonne_script_hooks", default=None)

NOT_IN_A_SCRIPT = (
    "sonne.script_api functions can only be called while Sonne runs a data script "
    "(scripts/*.py or footer.py during `sonne build` / `sonne serve`)"
)


@contextmanager
def running_script(hooks: ScriptHooks) -> Iterator[None]:
    """Route script API calls to hooks for the duration of one script run.

    Used by Sonne's script runner, not by scripts. The previous hooks (none,
    outside a build) are restored afterwards, even if the script raised.

    Args:
        hooks: The running build's hook implementations.
    """
    token = _active_hooks.set(hooks)
    try:
        yield
    finally:
        _active_hooks.reset(token)


def _current_hooks() -> ScriptHooks:
    hooks = _active_hooks.get()
    if hooks is None:
        raise RuntimeError(NOT_IN_A_SCRIPT)
    return hooks


def sonne_var(name: str, value: Any) -> None:
    """Publish a variable to every template (and to content Jinja).

    The variable is available both bare (``{{ name }}``) and as
    ``{{ site.name }}``. A name that matches a site config key or data-file
    key replaces that value, with a warning.

    Args:
        name: Variable name used in templates.
        value: Any value; persisted between builds only when
            ``variables.preserve_prior`` is on (it must then be JSON-able).

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> sonne_var("team", [{"name": "Ada"}])  # doctest: +SKIP
    """
    _current_hooks().sonne_var(name, value)


def get_post(slug: Optional[str] = None, tag: Optional[str] = None) -> Optional[Post]:
    """Look up a blog post collected for this build.

    Args:
        slug: Return the post with this slug.
        tag: When no slug is given, return the newest post with this tag.

    Returns:
        The post's data (title, url, date, tags, excerpt, ...), or None if
        there is no match or no blog.

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> latest = get_post(tag="news")  # doctest: +SKIP
    """
    return _current_hooks().get_post(slug, tag)


def sonne_filter(name: str, fn: Callable[..., Any]) -> None:
    """Register a Jinja filter for all templates (and content Jinja).

    Args:
        name: Filter name, used as ``{{ value | name }}``.
        fn: The filter; receives the value (plus any filter arguments).

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> sonne_filter("shout", lambda text: str(text).upper())  # doctest: +SKIP
    """
    _current_hooks().sonne_filter(name, fn)


def sonne_global(name: str, value: Any) -> None:
    """Register a Jinja global (a value or a callable) for all templates.

    Args:
        name: Global name, used as ``{{ name }}`` or ``{{ name(...) }}``.
        value: The value or function.

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> sonne_global("year_span", lambda start: f"{start}-2026")  # doctest: +SKIP
    """
    _current_hooks().sonne_global(name, value)


def sonne_config(*keys: str, default: Any = None) -> Any:
    """Read a value from the site's configuration (sonne.yaml merged over defaults).

    This is the configuration of the build that is running the script, so
    scripts never need to find and re-read the config file themselves.
    The result is a deep copy: changing it does not affect the build.

    Args:
        *keys: Path to the value, e.g. ``"site", "base_url"``; a single key
            returns a whole section as a dict. With no keys, returns default.
        default: Returned (as given, not copied) when the path does not exist.

    Returns:
        A deep copy of the configured value, or default.

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> city = sonne_config("site", "weather", "city", default="Berlin")  # doctest: +SKIP
    """
    return _current_hooks().sonne_config(*keys, default=default)


def get_variable(name: str, default: Any = None) -> Any:
    """Read a variable of the running build.

    Anything templates can see is readable: collected content
    (``all_pages``, ``all_blog_posts``, ``tags``, ``categories``), data
    files, site config values and variables set by scripts that ran earlier
    (scripts run in file-name order). The result is a deep copy, so
    changing it does not affect the build. Large values are copied on every
    call (``all_blog_posts`` includes each post's rendered content), so
    call it once and keep the result.

    Args:
        name: Variable name, as used in templates.
        default: Returned (as given, not copied) when there is no such variable.

    Returns:
        A deep copy of the variable's value, or default.

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> pages = get_variable("all_pages", [])  # doctest: +SKIP
    """
    return _current_hooks().get_variable(name, default)


def dither_image(image: "Image.Image") -> "Image.Image":
    """Dither an in-memory image with the site's ``images.dither_*`` settings.

    Resize first if needed; the result is ready to save as PNG.

    Args:
        image: A Pillow image, in any mode.

    Returns:
        The dithered image.

    Raises:
        RuntimeError: If called outside a data script run by Sonne.

    Example:
        >>> dither_image(Image.open("cover.jpg")).save("cover.png")  # doctest: +SKIP
    """
    return _current_hooks().dither_image(image)
