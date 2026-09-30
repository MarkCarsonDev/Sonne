"""
Build-time checks for machine-detectable accessibility failures (WCAG 2.2).

These checks catch structural problems in the generated HTML: images
without alt attributes, unnamed links and buttons, unlabelled form fields,
a missing page language or title, duplicate ids, positive tabindex, and
skipped heading levels. They cannot judge whether alt text is meaningful,
check colour contrast of arbitrary CSS, or verify reading order; passing
them is a floor, not a certificate.
"""

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

# Input types that need no label: not user-editable, or labelled by value/alt.
UNLABELLED_INPUT_TYPES = {"hidden", "submit", "reset", "button", "image"}
# Input types rendered as buttons; submit/reset have a default name.
BUTTON_INPUT_TYPES = {"button", "submit", "reset", "image"}
MAX_SNIPPET_LENGTH = 70


@dataclass(frozen=True)
class Finding:
    """One accessibility problem in a page."""

    criterion: str  # WCAG success criterion, e.g. "1.1.1"
    element: str  # short description of the offending element
    problem: str
    hint: str
    advisory: bool = False  # worth fixing, but never fails a build

    def describe(self) -> str:
        return f"[WCAG {self.criterion}] {self.element}: {self.problem}. {self.hint}"


@dataclass
class AccessibilityReport:
    """Findings for every checked page, keyed by path relative to the output root."""

    pages: dict[str, list[Finding]]
    checked_page_count: int

    @property
    def issue_count(self) -> int:
        return sum(len(findings) for findings in self.pages.values())

    @property
    def blocking_count(self) -> int:
        return sum(not f.advisory for findings in self.pages.values() for f in findings)

    @property
    def advisory_count(self) -> int:
        return self.issue_count - self.blocking_count

    def summary(self) -> str:
        """One line for the build summary."""
        pages = _count(self.checked_page_count, "page")
        if not self.issue_count:
            return f"Accessibility checks: no issues found in {pages}"
        return (
            f"Accessibility checks: {_count(self.blocking_count, 'issue')} and "
            f"{_count(self.advisory_count, 'advisory', 'advisories')} on "
            f"{len(self.pages)} of {pages}"
        )


def check_output_dir(output_dir: str) -> AccessibilityReport:
    """Check every .html file under output_dir.

    Args:
        output_dir: Root of the generated site.

    Returns:
        The report; pages without findings are omitted from report.pages.
    """
    pages: dict[str, list[Finding]] = {}
    checked = 0
    for root, _dirs, files in os.walk(output_dir):
        for filename in sorted(files):
            if not filename.endswith(".html"):
                continue
            path = Path(root, filename)
            findings = check_html(path.read_text(encoding="utf-8", errors="replace"))
            checked += 1
            if findings:
                pages[path.relative_to(output_dir).as_posix()] = findings
    return AccessibilityReport(dict(sorted(pages.items())), checked)


def check_html(html: str) -> list[Finding]:
    """All findings for one HTML document, in rule order."""
    if not html.strip():
        # One clear finding instead of "no language" + "no title".
        return [
            Finding(
                "2.4.2",
                "page",
                "the page is empty",
                "Check the template that renders it; an empty template writes an empty page.",
            )
        ]
    soup = BeautifulSoup(html, "html.parser")
    return (
        _missing_language(soup)
        + _missing_title(soup)
        + _images_without_alt(soup)
        + _unnamed_links_and_buttons(soup)
        + _unlabelled_form_controls(soup)
        + _duplicate_ids(soup)
        + _positive_tabindex(soup)
        + _skipped_heading_levels(soup)
    )


# --- Rules ---------------------------------------------------------------


def _missing_language(soup: BeautifulSoup) -> list[Finding]:
    html = soup.find("html")
    if isinstance(html, Tag) and str(html.get("lang") or "").strip():
        return []
    return [
        Finding(
            "3.1.1",
            "<html>",
            "the page language is not set",
            'Add lang to the <html> element, e.g. <html lang="{{ site.language }}">.',
        )
    ]


def _missing_title(soup: BeautifulSoup) -> list[Finding]:
    titles = [title for title in soup.find_all("title") if not _inside(title, "svg")]
    if any(title.get_text(strip=True) for title in titles):
        return []
    return [
        Finding(
            "2.4.2",
            "<title>",
            "the page has no title" if not titles else "the page title is empty",
            "Give every page a descriptive <title> in its <head>.",
        )
    ]


def _images_without_alt(soup: BeautifulSoup) -> list[Finding]:
    return [
        Finding(
            "1.1.1",
            _snippet(img),
            "image has no alt attribute",
            'Describe the image in alt, or use alt="" if it is purely decorative.',
        )
        for img in soup.find_all("img")
        if img.get("alt") is None and not _is_hidden(img)
    ]


def _unnamed_links_and_buttons(soup: BeautifulSoup) -> list[Finding]:
    findings = []
    for element in soup.find_all(["a", "button", "input"]):
        if _is_hidden(element) or _has_accessible_name(element):
            continue
        if element.name == "a" and element.get("href") is None:
            continue  # a placeholder anchor, not a link
        if element.name == "input":
            input_type = str(element.get("type") or "text").lower()
            if input_type not in BUTTON_INPUT_TYPES or input_type in {"submit", "reset"}:
                continue
        kind = "link" if element.name == "a" else "button"
        findings.append(
            Finding(
                "2.4.4" if kind == "link" else "4.1.2",
                _snippet(element),
                f"{kind} has no accessible name",
                "Give it visible text, an aria-label, or an image with alt text inside.",
            )
        )
    return findings


def _unlabelled_form_controls(soup: BeautifulSoup) -> list[Finding]:
    label_targets = {str(label.get("for")) for label in soup.find_all("label") if label.get("for")}
    findings = []
    for control in soup.find_all(["input", "select", "textarea"]):
        input_type = str(control.get("type") or "text").lower()
        if control.name == "input" and input_type in UNLABELLED_INPUT_TYPES:
            continue
        if _is_hidden(control) or _has_label(control, label_targets):
            continue
        findings.append(
            Finding(
                "1.3.1",
                _snippet(control),
                "form field has no label",
                'Add <label for="..."> (or wrap it in a <label>), or an aria-label.',
            )
        )
    return findings


def _duplicate_ids(soup: BeautifulSoup) -> list[Finding]:
    counts = Counter(str(element.get("id")) for element in soup.find_all(id=True))
    return [
        Finding(
            "4.1.1",
            f'id="{element_id}"',
            f"id is used {count} times",
            "Make every id unique; labels, skip links and ARIA references rely on it.",
        )
        for element_id, count in counts.items()
        if count > 1
    ]


def _positive_tabindex(soup: BeautifulSoup) -> list[Finding]:
    findings = []
    for element in soup.find_all(tabindex=True):
        try:
            tabindex = int(str(element.get("tabindex")).strip())
        except ValueError:
            continue
        if tabindex > 0:
            findings.append(
                Finding(
                    "2.4.3",
                    _snippet(element),
                    f"tabindex={tabindex} changes the keyboard focus order",
                    'Use tabindex="0" (or none) and order the markup instead.',
                )
            )
    return findings


def _skipped_heading_levels(soup: BeautifulSoup) -> list[Finding]:
    findings = []
    previous_level: Optional[int] = None
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if _is_hidden(heading):
            continue
        level = int(heading.name[1])
        if previous_level is not None and level > previous_level + 1:
            findings.append(
                Finding(
                    "1.3.1",
                    _snippet(heading),
                    f"heading level jumps from h{previous_level} to h{level}",
                    f"Use h{previous_level + 1} here, or style a lower level to look smaller.",
                    advisory=True,
                )
            )
        previous_level = level
    return findings


# --- Helpers -------------------------------------------------------------


def _has_accessible_name(element: Tag) -> bool:
    """Visible text, aria-label(ledby), title, a value, or an image/SVG with a name inside."""
    if _visible_text(element):
        return True
    for attribute in ("aria-label", "aria-labelledby", "title"):
        if str(element.get(attribute) or "").strip():
            return True
    if element.name == "input":
        return bool(str(element.get("value") or element.get("alt") or "").strip())
    return any(str(img.get("alt") or "").strip() for img in element.find_all("img"))


def _has_label(control: Tag, label_targets: set[str]) -> bool:
    if control.get("id") is not None and str(control.get("id")) in label_targets:
        return True
    if _inside(control, "label"):
        return True
    return any(
        str(control.get(attribute) or "").strip()
        for attribute in ("aria-label", "aria-labelledby", "title")
    )


def _visible_text(element: Tag) -> str:
    """Text content, leaving out parts hidden from assistive technology."""
    parts = []
    for text in element.find_all(string=True):
        parent = text.parent
        if isinstance(parent, Tag) and _is_hidden(parent, stop_at=element):
            continue
        parts.append(str(text))
    return "".join(parts).strip()


def _is_hidden(element: Tag, stop_at: Optional[Tag] = None) -> bool:
    """Whether element (or an ancestor, up to stop_at) is hidden from assistive technology."""
    node: Optional[Tag] = element
    while isinstance(node, Tag) and node is not stop_at:
        if str(node.get("aria-hidden") or "").lower() == "true" or node.get("hidden") is not None:
            return True
        node = node.parent
    return False


def _inside(element: Tag, tag_name: str) -> bool:
    return element.find_parent(tag_name) is not None


def _snippet(element: Tag) -> str:
    """The element's opening tag, shortened: <img src="a.png">."""
    attributes = " ".join(
        f'{name}="{" ".join(value) if isinstance(value, list) else value}"'
        for name, value in element.attrs.items()
        if name in ("id", "class", "src", "href", "name", "type")
    )
    tag = f"<{element.name}{' ' + attributes if attributes else ''}>"
    return tag if len(tag) <= MAX_SNIPPET_LENGTH else tag[: MAX_SNIPPET_LENGTH - 4] + "...>"


class AccessibilityCheckFailed(Exception):
    """Raised by a build with build.accessibility_checks: error when issues were found."""


def _count(amount: int, singular: str, plural: str = "") -> str:
    """'1 issue', '3 issues'."""
    return f"{amount} {singular if amount == 1 else plural or singular + 's'}"
