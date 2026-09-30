"""
The functions Sonne data scripts call to hand data to templates.

Import them in ``scripts/*.py`` (and ``footer.py``) so editors, type
checkers and linters know where they come from::

    from sonne.script_api import get_post, sonne_filter, sonne_global, sonne_var

    sonne_var("team", [{"name": "Ada", "role": "Engineer"}])
    sonne_filter("shout", lambda text: str(text).upper())

They only work while Sonne is running the script during a build; each call
goes to the build that is executing the script. Calling them anywhere else
raises RuntimeError. (For backward compatibility the same four functions
are also injected into every script as globals, so older scripts without
the import keep working; the import is the preferred, documented form.)
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from typing import Any, Callable, Optional

__all__ = ["get_post", "sonne_filter", "sonne_global", "sonne_var"]

Post = dict[str, Any]


@dataclass(frozen=True)
class ScriptHooks:
    """One build's implementations of the script API (provided by VariableManager)."""

    sonne_var: Callable[[str, Any], None]
    get_post: Callable[[Optional[str], Optional[str]], Optional[Post]]
    sonne_filter: Callable[[str, Callable[..., Any]], None]
    sonne_global: Callable[[str, Any], None]

    def as_globals(self) -> dict[str, Callable[..., Any]]:
        """The hooks by name, for injecting into a script module's globals."""
        return {name: getattr(self, name) for name in asdict(self)}


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
