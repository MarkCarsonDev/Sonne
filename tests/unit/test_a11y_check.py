"""sonne.utils.a11y_check: one test per rule, both directions."""

import pytest

from sonne.utils.a11y_check import check_html, check_output_dir


def page(body, head="<title>T</title>", lang=' lang="en"'):
    return f"<!DOCTYPE html><html{lang}><head>{head}</head><body>{body}</body></html>"


def criteria(html):
    return [finding.criterion for finding in check_html(html)]


class TestCleanPage:
    def test_well_formed_page_has_no_findings(self):
        html = page(
            '<h1>T</h1><h2>Sub</h2><img src="a.png" alt="A">'
            '<a href="/x">Read more</a><label for="q">Search</label><input id="q">'
        )

        assert check_html(html) == []


class TestImages:
    def test_image_without_alt(self):
        assert criteria(page('<img src="a.png">')) == ["1.1.1"]

    @pytest.mark.parametrize(
        "img",
        [
            '<img src="a.png" alt="">',
            '<img src="a.png" alt="A">',
            '<img src="a" aria-hidden="true">',
        ],
        ids=["decorative", "described", "hidden"],
    )
    def test_images_with_alt_or_hidden_pass(self, img):
        assert criteria(page(img)) == []


class TestLinksAndButtons:
    @pytest.mark.parametrize(
        "element, criterion",
        [
            ('<a href="/x"></a>', "2.4.4"),
            ('<a href="/x"><img src="i.png" alt=""></a>', "2.4.4"),
            ('<a href="/x"><span aria-hidden="true">&rarr;</span></a>', "2.4.4"),
            ("<button></button>", "4.1.2"),
            ('<input type="button">', "4.1.2"),
        ],
        ids=["empty-link", "decorative-image-only", "hidden-text-only", "empty-button", "input"],
    )
    def test_unnamed(self, element, criterion):
        assert criteria(page(element)) == [criterion]

    @pytest.mark.parametrize(
        "element",
        [
            '<a href="/x">Home</a>',
            '<a href="/x" aria-label="Home"></a>',
            '<a href="/x" aria-labelledby="l"></a><span id="l">Home</span>',
            '<a href="/x" title="Home"></a>',
            '<a href="/x"><img src="h.png" alt="Home"></a>',
            '<a href="/x"><svg><title>Home</title></svg></a>',
            '<a name="anchor"></a>',
            '<a href="/x" aria-hidden="true" tabindex="-1"></a>',
            '<button aria-label="Menu"></button>',
            '<input type="submit">',
            '<input type="button" value="Go">',
        ],
        ids=[
            "text",
            "aria-label",
            "aria-labelledby",
            "title",
            "image-alt",
            "svg-title",
            "anchor-without-href",
            "hidden",
            "button-aria-label",
            "submit-default-name",
            "input-value",
        ],
    )
    def test_named_or_exempt(self, element):
        assert criteria(page(element)) == []


class TestFormControls:
    @pytest.mark.parametrize(
        "control",
        ['<input id="q">', "<select></select>", "<textarea></textarea>", '<input type="email">'],
    )
    def test_unlabelled(self, control):
        assert criteria(page(control)) == ["1.3.1"]

    @pytest.mark.parametrize(
        "control",
        [
            '<label for="q">Search</label><input id="q">',
            "<label>Search <input></label>",
            '<input aria-label="Search">',
            '<textarea aria-labelledby="l"></textarea><p id="l">Message</p>',
            '<input type="hidden" name="token">',
            '<input type="submit" value="Send">',
        ],
        ids=["for", "wrapped", "aria-label", "aria-labelledby", "hidden", "submit"],
    )
    def test_labelled_or_exempt(self, control):
        assert criteria(page(control)) == []


class TestDocument:
    @pytest.mark.parametrize(
        "lang", ["", ' lang=""', ' lang="  "'], ids=["absent", "empty", "blank"]
    )
    def test_missing_language(self, lang):
        assert criteria(page("", lang=lang)) == ["3.1.1"]

    @pytest.mark.parametrize("head", ["", "<title></title>", "<title> </title>"])
    def test_missing_title(self, head):
        assert criteria(page("", head=head)) == ["2.4.2"]

    def test_svg_title_does_not_count_as_page_title(self):
        html = page("<svg><title>Icon</title></svg>", head="")

        assert criteria(html) == ["2.4.2"]

    def test_empty_page_is_one_clear_finding(self):
        [finding] = check_html("  \n")

        assert (finding.criterion, finding.problem) == ("2.4.2", "the page is empty")


class TestIdsAndFocus:
    def test_duplicate_ids_reported_once_each(self):
        findings = check_html(page('<p id="a"></p><p id="a"></p><p id="a"></p><p id="b"></p>'))

        assert [(f.criterion, f.element, f.problem) for f in findings] == [
            ("4.1.1", 'id="a"', "id is used 3 times")
        ]

    def test_positive_tabindex(self):
        assert criteria(page('<div tabindex="2">x</div>')) == ["2.4.3"]

    @pytest.mark.parametrize("value", ["0", "-1", "abc"])
    def test_zero_negative_or_invalid_tabindex_pass(self, value):
        assert criteria(page(f'<div tabindex="{value}">x</div>')) == []


class TestHeadings:
    def test_skipped_level_is_an_advisory(self):
        [finding] = check_html(page("<h1>A</h1><h2>B</h2><h4>C</h4>"))

        assert (finding.criterion, finding.advisory) == ("1.3.1", True)
        assert "h2 to h4" in finding.problem

    @pytest.mark.parametrize(
        "headings",
        ["<h1>A</h1><h2>B</h2><h3>C</h3><h2>D</h2>", "<h2>Page starts at h2</h2><h3>C</h3>"],
        ids=["descending-and-back", "starting-below-h1"],
    )
    def test_no_skip(self, headings):
        assert check_html(page(headings)) == []


class TestReport:
    def test_output_dir_report_counts_pages_and_severities(self, tmp_path):
        (tmp_path / "ok.html").write_text(page("<h1>Fine</h1>"), encoding="utf-8")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "bad.html").write_text(
            page('<img src="a"><h1>A</h1><h3>B</h3>'), encoding="utf-8"
        )
        (tmp_path / "notes.txt").write_text("<img src=a>", encoding="utf-8")

        report = check_output_dir(str(tmp_path))

        assert list(report.pages) == ["sub/bad.html"]
        assert (report.checked_page_count, report.blocking_count, report.advisory_count) == (
            2,
            1,
            1,
        )
        assert report.summary() == ("Accessibility checks: 1 issue and 1 advisory on 1 of 2 pages")
