"""
URLs of the pages the blog generates.

One home for these rules: BlogProcessor uses them for the pages it writes,
and templates reach the same methods through the Jinja globals blog_url(),
tag_url(), category_url() and archive_url(), so links can never drift from
the pages they point at.
"""

from typing import Optional, Union

from sonne.core.config import Config
from sonne.utils.text import slugify

TAGS = "tags"
CATEGORIES = "categories"


class BlogUrls:
    """Site URLs of the blog index, taxonomy and archive pages.

    URLs follow blog.directory and are formatted for the configured
    url_style, both read at call time.
    """

    def __init__(self, config: Config):
        self._config = config

    def index(self, page: int = 1) -> str:
        """The blog index, or one of its later pages (``/blog/page/2``)."""
        blog_url = f"/{self._blog_dir()}".rstrip("/")
        return self._format(blog_url if page == 1 else f"{blog_url}/page/{page}")

    def tag(self, name: Optional[str] = None) -> str:
        """The page listing posts with this tag; with no tag, the index of all tags."""
        return self._taxonomy(TAGS, name)

    def category(self, name: Optional[str] = None) -> str:
        """The page listing posts in this category; with none, the index of all categories."""
        return self._taxonomy(CATEGORIES, name)

    def term_page(self, taxonomy_type: str, slug: str) -> str:
        """A tag or category page by its already-slugified term."""
        return self._format(f"/{self._blog_dir()}/{taxonomy_type}/{slug}")

    def taxonomy_index(self, taxonomy_type: str) -> str:
        """The index page of all tags or all categories."""
        return self._format(f"/{self._blog_dir()}/{taxonomy_type}")

    def archive(
        self,
        year: Union[int, str],
        month: Union[int, str, None] = None,
        day: Union[int, str, None] = None,
    ) -> str:
        """A year, month or day archive; month and day are zero-padded (1 -> "01")."""
        parts = [str(year)]
        for part in (month, day):
            if part is None:
                break
            parts.append(f"{int(part):02d}")
        return self._format(f"/{self._blog_dir()}/{'/'.join(parts)}/")

    def _taxonomy(self, taxonomy_type: str, name: Optional[str]) -> str:
        if name is None:
            return self.taxonomy_index(taxonomy_type)
        return self.term_page(taxonomy_type, slugify(name))

    def _blog_dir(self) -> str:
        return self._config.blog_directory()

    def _format(self, url: str) -> str:
        return self._config.format_url(url)
