"""
Registry of the images a build dithered.

ImageProcessor fills it while processing images; TemplateProcessor reads it
when finishing each page, to point <img> tags at the dithered copy and record
the original in data-original-src (the markup dithering.js toggles).
"""

import threading
from typing import Optional


class DitheredImages:
    """Registry of the images a build dithered: original URL <-> dithered URL.

    URLs are root-relative ("/images/a.png"). Filled by ImageProcessor
    (possibly from worker threads) and read when pages are rendered.
    """

    def __init__(self) -> None:
        self._dithered_by_original: dict[str, str] = {}
        self._original_by_dithered: dict[str, str] = {}
        self._lock = threading.Lock()

    def add(self, original_url: str, dithered_url: str) -> None:
        with self._lock:
            self._dithered_by_original[original_url] = dithered_url
            self._original_by_dithered[dithered_url] = original_url

    def pair_for(self, url: str) -> Optional[tuple[str, str]]:
        """(original, dithered) URLs for either URL of a pair, or None if not dithered."""
        with self._lock:
            if url in self._dithered_by_original:
                return url, self._dithered_by_original[url]
            if url in self._original_by_dithered:
                return self._original_by_dithered[url], url
        return None

    def __len__(self) -> int:
        with self._lock:
            return len(self._dithered_by_original)
