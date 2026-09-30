"""Where content pages are written and the URLs they are served at."""

from pathlib import PurePosixPath

import pytest

from sonne.utils.page_location import page_output_path, page_url


@pytest.mark.parametrize(
    "source, url_style, output",
    [
        ("index.md", "clean", "index.html"),
        ("about.md", "clean", "about/index.html"),
        ("about.md", "directory", "about/index.html"),
        ("projects/index.md", "directory", "projects/index.html"),
        ("projects/solar.md", "directory", "projects/solar/index.html"),
        ("contact.html", "clean", "contact/index.html"),
        ("about.md", "html", "about.html"),
        ("contact.htm", "html", "contact.htm"),
        ("Notes.MD", "clean", "Notes/index.html"),
    ],
)
def test_output_path_follows_the_url_style(source, url_style, output):
    assert page_output_path(PurePosixPath(source), url_style) == PurePosixPath(output)


@pytest.mark.parametrize(
    "output, url",
    [
        ("index.html", "/"),
        ("about/index.html", "/about/"),
        ("projects/solar/index.html", "/projects/solar/"),
        ("about.html", "/about.html"),
    ],
)
def test_a_directory_index_is_served_at_its_directory(output, url):
    assert page_url(PurePosixPath(output)) == url
