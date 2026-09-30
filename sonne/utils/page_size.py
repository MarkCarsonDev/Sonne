"""
Page-size labels for generated HTML (``build.show_page_size``).

Each page gets a short note after its content with its HTML weight and,
when it references local images, the total including them. The note is plain
text in the page flow: always visible (no hover), in the page's own colours
(WCAG 1.4.3, 1.4.13) and never covering content (1.4.10).
"""

import logging
import os
import re
from urllib.parse import unquote

logger = logging.getLogger("sonne")

LABEL_ID = "page-size-label"

# Rough byte count of the injected note, so the size includes it.
LABEL_OVERHEAD_BYTES = 200

# Inline, so the note needs no stylesheet; it inherits the page's colours.
LABEL_STYLE = "font-size: 0.8em; margin: 1em;"

# Group 1 is the image path, without any ?query or #fragment.
IMAGE_SRC_PATTERN = re.compile(
    r'src=["\']([^"\'?#]+\.(?:webp|png|jpg|jpeg|gif|svg))(?:[?#][^"\']*)?["\']', re.I
)
REMOTE_PREFIXES = ("http://", "https://", "data:")

BYTES_PER_KB = 1024


def inject_page_size_labels(output_dir: str) -> None:
    """Add a page-size label to every generated HTML file under output_dir.

    Files that already carry a label (e.g. untouched since an earlier
    build) are left alone. A file that cannot be read or written is logged and skipped.

    Args:
        output_dir: Root of the generated site.
    """
    for root, _dirs, files in os.walk(output_dir):
        for filename in files:
            if filename.endswith(".html"):
                _label_file(os.path.join(root, filename), output_dir)


def _label_file(html_path: str, output_dir: str) -> None:
    try:
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        if LABEL_ID in html:
            return
        # The last </body> is the real one; earlier ones can sit inside
        # inline scripts or code samples.
        before_body_end, body_end, after_body_end = html.rpartition("</body>")
        if not body_end:
            return
        label = _label_html(html, html_path, output_dir)
        labelled = before_body_end + label + body_end + after_body_end
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(labelled)
    except Exception as e:
        logger.warning(f"Could not inject page size into {html_path}: {e}")


def _label_html(html: str, html_path: str, output_dir: str) -> str:
    """The note: a labelled <aside> ("Page size: ~12.3 KB (~45 KB with images)")."""
    page_bytes = len(html.encode("utf-8")) + LABEL_OVERHEAD_BYTES
    text = f"Page size: ~{page_bytes / BYTES_PER_KB:.1f} KB"
    image_bytes = _local_image_bytes(html, os.path.dirname(html_path), output_dir)
    if image_bytes:
        text += f" (~{(page_bytes + image_bytes) / BYTES_PER_KB:.0f} KB with images)"
    return (
        f'<aside id="{LABEL_ID}" aria-label="Page size" style="{LABEL_STYLE}"><p>{text}</p></aside>'
    )


def _local_image_bytes(html: str, html_dir: str, output_dir: str) -> int:
    """Total size of the local images the page references; missing files count 0."""
    total = 0
    for match in IMAGE_SRC_PATTERN.finditer(html):
        src = match.group(1)
        if src.startswith(REMOTE_PREFIXES):
            continue
        total += _file_size_or_zero(_resolve_image_src(src, html_dir, output_dir))
    return total


def _resolve_image_src(src: str, html_dir: str, output_dir: str) -> str:
    """Filesystem path of an image URL path, percent-encoding decoded."""
    src = unquote(src)
    if src.startswith("/"):
        return os.path.join(output_dir, src.lstrip("/"))
    return os.path.join(html_dir, src)


def _file_size_or_zero(path: str) -> int:
    # A referenced image may legitimately be absent (e.g. skip_images builds).
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
