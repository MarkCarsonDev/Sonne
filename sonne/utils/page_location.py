"""Where a content page is written, and the URL it is served at.

Both come from here so a page's URL always matches the file Sonne writes.
"""

from pathlib import PurePath, PurePosixPath

from sonne.utils.constants import MARKDOWN_EXTENSIONS


def page_output_path(rel_source: PurePath, url_style: str) -> PurePosixPath:
    """Output path, relative to the output directory, for a content page.

    Args:
        rel_source: The page's path relative to the content directory.
        url_style: 'html' keeps path/to/page.html; 'clean' and 'directory'
            both write path/to/page/index.html (they differ only in how
            links are formatted), and an index page stays its directory's
            index.html.

    Returns:
        The output path, e.g. ``about/index.html``.
    """
    rel_path = PurePosixPath(rel_source.as_posix())
    if rel_path.suffix.lower() in MARKDOWN_EXTENSIONS:
        rel_path = rel_path.with_suffix(".html")
    if url_style == "html":
        return rel_path
    if rel_path.stem == "index":
        return rel_path.parent / "index.html"
    return rel_path.parent / rel_path.stem / "index.html"


def page_url(output_path: PurePosixPath) -> str:
    """Site URL for an output path, before URL-style formatting.

    A directory's index.html is served at the directory ("/", "/about/");
    any other file at its own path ("/about.html").
    """
    if output_path.name == "index.html":
        directory = output_path.parent.as_posix()
        return "/" if directory == "." else f"/{directory}/"
    return "/" + output_path.as_posix()
