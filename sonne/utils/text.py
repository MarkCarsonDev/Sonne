"""
Text utilities for Sonne.

This module owns the ONE canonical slugify. Post URLs, taxonomy page paths,
and the Jinja ``slugify`` filter must all use it — divergent slug algorithms
previously produced tag links pointing at pages that were never generated.
"""
import re

from sonne.utils.path_utils import sanitize_filename

# Maximum slug length (keeps URLs and filenames manageable)
MAX_SLUG_LENGTH = 100


def slugify(text) -> str:
    """Convert text to a URL- and filesystem-safe slug.

    Semantics match the historical blog slugifier (published post URLs are
    the compatibility contract): lowercase, spaces to hyphens, word
    characters (including underscores) preserved, everything else dropped.

    Args:
        text: Value to slugify (coerced to str).

    Returns:
        Slug string, never empty.
    """
    text = str(text)

    # Basic slug conversion: keep word chars, spaces, hyphens
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[\s]+', '-', text)
    text = re.sub(r'[-]+', '-', text)
    text = text.strip('-')

    # Security sanitization for filesystem use
    text = sanitize_filename(text, replace_char='-')

    if not text:
        text = 'untitled'

    if len(text) > MAX_SLUG_LENGTH:
        text = text[:MAX_SLUG_LENGTH].rstrip('-')

    return text
