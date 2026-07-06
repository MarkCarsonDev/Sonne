"""RSS feed generation."""

import xml.etree.ElementTree as ET

import pytest


@pytest.fixture
def rss_out(site_factory, builder):
    site = site_factory("blog", overlay="blog_site")
    _, out = builder(site)
    feeds = list(out.rglob("feed.xml"))
    assert feeds, "no feed.xml generated anywhere in output"
    return feeds[0]


class TestRss:
    def test_feed_exists_and_looks_like_rss(self, rss_out):
        text = rss_out.read_text(encoding="utf-8")
        assert "<rss" in text
        assert "<item>" in text

    def test_feed_is_valid_xml_with_special_chars(self, rss_out):
        tree = ET.parse(rss_out)
        titles = [t.text for t in tree.getroot().iter("title")]
        assert "Tips & Tricks <fast>" in titles

    def test_pubdate_has_real_utc_offset(self, rss_out):
        from email.utils import parsedate_to_datetime

        tree = ET.parse(rss_out)
        dates = [d.text for d in tree.getroot().iter("pubDate")]
        assert dates
        for d in dates:
            parsed = parsedate_to_datetime(d)
            assert parsed.tzinfo is not None
