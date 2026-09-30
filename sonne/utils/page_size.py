"""
Page-size labels for generated HTML (``build.show_page_size``).

Each page gets a small fixed-position label with its HTML weight; hovering
reveals the total including locally served images it references.
"""

import logging
import os
import re
from urllib.parse import unquote

logger = logging.getLogger("sonne")

LABEL_ID = "page-size-label"

# Rough byte count of the injected <span>, so the label includes itself.
LABEL_OVERHEAD_BYTES = 150

LABEL_CSS = (
    '<style id="page-size-css">'
    "#page-size-label{"
    "position:fixed;bottom:0.4rem;right:0.6rem;"
    "font-size:0.7rem;font-family:monospace;"
    "opacity:0.35;cursor:default;z-index:9999;"
    "}"
    "#page-size-label:hover{opacity:0.85}"
    "#page-size-label[data-full]::after{"
    "content:attr(data-full);"
    "display:none;"
    "position:absolute;bottom:1.4rem;right:0;"
    "background:var(--bg,#141514);"
    "border:0.1px solid #ffffff33;"
    "padding:0.2rem 0.5rem;"
    "border-radius:0.2em;"
    "white-space:nowrap;"
    "font-size:0.65rem;"
    "opacity:1;"
    "}"
    "#page-size-label[data-full]:hover::after{display:block}"
    "</style>"
)
LABEL_CSS_BYTES = len(LABEL_CSS.encode("utf-8"))

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
        label = LABEL_CSS + _label_html(html, html_path, output_dir)
        labelled = before_body_end + label + body_end + after_body_end
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(labelled)
    except Exception as e:
        logger.warning(f"Could not inject page size into {html_path}: {e}")


def _label_html(html: str, html_path: str, output_dir: str) -> str:
    page_bytes = len(html.encode("utf-8")) + LABEL_CSS_BYTES + LABEL_OVERHEAD_BYTES
    label_text = f"~{page_bytes / BYTES_PER_KB:.1f} KB*"
    image_bytes = _local_image_bytes(html, os.path.dirname(html_path), output_dir)
    if not image_bytes:
        return f'<span id="{LABEL_ID}">{label_text}</span>'
    full_text = f"~{(page_bytes + image_bytes) / BYTES_PER_KB:.0f} KB with images"
    return f'<span id="{LABEL_ID}" data-full="{full_text}">{label_text}</span>'


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
