"""sonne/static/js/dithering.js in a real (headless) browser.

The static pipeline serves the dithered image at the image URL and the
original beside it as ``<name>_original<ext>``; the script wraps standalone
images with a toggle between the two. Skipped when no Chromium-family
browser is installed.
"""

import html
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

DITHERING_JS = Path(__file__).resolve().parents[2] / "sonne" / "static" / "js" / "dithering.js"

BROWSER_CANDIDATES = [
    "chromium",
    "chromium-browser",
    "google-chrome",
    "chrome",
    "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

HARNESS = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body>
<img id="plain" src="/images/a.png" alt="A">
<img id="sized" src="/img/b_800.webp">
<img id="underscore" src="/img/my_pic.jpg">
<img id="query" src="/images/q.png?v=1.2">
<img id="dotdir" src="/v_1.2/a.png">
<img id="svg" src="/i/logo.svg?v=2">
<img id="svgupper" src="/i/LOGO.SVG">
<img id="external" src="https://example.com/x.png">
<img id="datauri" src="data:image/png;base64,iVBORw0KGgo.AAAA">
<figure class="dithered-image-figure"><div class="image-wrapper">
  <img id="blog" class="dithered-image active" src="post/dithered/p.png"
       data-dithered-src="post/dithered/p.png" data-original-src="post/p.jpg">
</div></figure>
<div class="dithered-image-container" id="server">
  <img src="/x_400.png" class="dithered"><img src="/x_400_original.png" class="original">
  <div class="dither-toggle"></div>
</div>
<a href="#navigated"><img id="linked" src="/images/l.png"></a>
<pre id="results"></pre>
<script src="dithering.js"></script>
<script>
  setTimeout(function () {
    var dynamic = document.createElement("img");
    dynamic.id = "dynamic";
    dynamic.src = "/images/d_200.png";
    document.body.appendChild(dynamic);
  }, 50);
  setTimeout(function () {
    var results = {};
    Array.prototype.forEach.call(document.querySelectorAll("img[id]"), function (img) {
      var box = img.closest(".dithered-image-container");
      results[img.id] = box ? box.querySelector("img.original").getAttribute("src") : null;
    });
    var server = document.getElementById("server");
    server.querySelector(".dither-toggle").click();
    results.serverToggled = server.classList.contains("show-original");
    var linkedBox = document.getElementById("linked").closest(".dithered-image-container");
    linkedBox.querySelector(".dither-toggle").click();
    results.linkedToggled = linkedBox.classList.contains("show-original");
    results.hash = location.hash;
    results.toggleCount = document.querySelectorAll(".dither-toggle").length;
    document.getElementById("results").textContent = JSON.stringify(results);
  }, 400);
</script>
</body></html>
"""


def find_browser():
    for candidate in BROWSER_CANDIDATES:
        found = shutil.which(candidate) or (candidate if os.path.isfile(candidate) else None)
        if found:
            return found
    return None


@pytest.fixture(scope="module")
def harness_results(tmp_path_factory):
    import json

    browser = find_browser()
    if browser is None:
        pytest.skip("no Chromium-family browser available")
    page_dir = tmp_path_factory.mktemp("dithering_js")
    shutil.copy(DITHERING_JS, page_dir / "dithering.js")
    (page_dir / "harness.html").write_text(HARNESS, encoding="utf-8")

    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            f"--user-data-dir={page_dir / 'profile'}",
            "--virtual-time-budget=3000",
            "--dump-dom",
            (page_dir / "harness.html").as_uri(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    match = re.search(r'<pre id="results">(.*?)</pre>', completed.stdout, re.S)
    assert match, f"harness produced no results: {completed.stdout[-500:]}"
    return json.loads(html.unescape(match.group(1)))


class TestStandaloneImages:
    @pytest.mark.parametrize(
        "image_id, expected_original",
        [
            ("plain", "/images/a_original.png"),
            ("sized", "/img/b_800_original.webp"),
            ("underscore", "/img/my_pic_original.jpg"),
            ("dynamic", "/images/d_200_original.png"),
        ],
    )
    def test_original_sits_beside_dithered_image(
        self, harness_results, image_id, expected_original
    ):
        assert harness_results[image_id] == expected_original

    def test_query_string_is_kept_after_the_suffix(self, harness_results):
        assert harness_results["query"] == "/images/q_original.png?v=1.2"

    def test_dots_in_directories_are_not_extensions(self, harness_results):
        assert harness_results["dotdir"] == "/v_1.2/a_original.png"


class TestImagesLeftAlone:
    @pytest.mark.parametrize("image_id", ["svg", "svgupper", "external", "datauri"])
    def test_images_without_an_original_twin_are_not_wrapped(self, harness_results, image_id):
        assert harness_results[image_id] is None

    def test_blog_figure_images_keep_their_own_markup(self, harness_results):
        assert harness_results["blog"] is None


class TestToggle:
    def test_server_rendered_toggle_works(self, harness_results):
        assert harness_results["serverToggled"] is True

    @pytest.mark.xfail(strict=True, reason="toggle click inside a link follows the link")
    def test_toggle_inside_link_does_not_navigate(self, harness_results):
        assert harness_results["linkedToggled"] is True
        assert harness_results["hash"] == ""

    def test_each_container_has_one_toggle(self, harness_results):
        # plain, sized, underscore, query, dotdir, linked, dynamic + server
        assert harness_results["toggleCount"] == 8
