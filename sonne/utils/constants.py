"""
File-extension sets shared across Sonne (one definition each).

Lowercase suffixes including the dot; compare with
``path.suffix.lower() in IMAGE_EXTENSIONS``. Note: ``.gif`` is currently
flattened to a static frame by the resize pipeline.
"""

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})
MARKDOWN_EXTENSIONS = frozenset({".md", ".markdown"})
PAGE_EXTENSIONS = frozenset({".html", ".htm"}) | MARKDOWN_EXTENSIONS
