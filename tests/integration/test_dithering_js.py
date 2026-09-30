"""sonne/static/js/dithering.js in a real (headless) browser.

The build points each image it dithered at the dithered copy and records
the original in data-original-src; the script gives exactly those images a
toggle, and wires up the blog figures' "view original" button. Skipped when
no Chromium-family browser is installed.
"""

import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "sonne" / "static"
DITHERING_JS = STATIC / "js" / "dithering.js"
DITHERING_CSS = STATIC / "css" / "dithering.css"

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

# A container as pages built by earlier Sonne versions rendered it
# server-side (the process_image filter), toggle as a <button>.
EARLIER_BUILD_CONTAINER = """
<div class="dithered-image-container" id="server">
  <img src="/x_400.png" alt="X" loading="lazy" class="dithered">
  <img src="/x_400_original.png" alt="X" loading="lazy" class="original" aria-hidden="true">
  <button type="button" class="dither-toggle" aria-pressed="false"
          aria-label="Show original image" title="Show original image">
    <span class="dither-toggle-dot" aria-hidden="true"></span>
    <span class="dither-toggle-dot empty" aria-hidden="true"></span>
    <span class="dither-toggle-dot" aria-hidden="true"></span>
    <span class="dither-toggle-dot empty" aria-hidden="true"></span>
    <span class="dither-toggle-dot" aria-hidden="true"></span>
    <span class="dither-toggle-dot empty" aria-hidden="true"></span>
    <span class="dither-toggle-dot" aria-hidden="true"></span>
    <span class="dither-toggle-dot empty" aria-hidden="true"></span>
    <span class="dither-toggle-dot" aria-hidden="true"></span>
  </button>
</div>
"""

HARNESS = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="dithering.css">
<style>* { transition: none !important; }</style></head><body>
<img id="plain" src="/images/dithered/a.png" data-original-src="/images/a.png" alt="A">
<img id="variant" src="/assets/images/b_800.webp"
     data-original-src="/assets/images/b_800_original.webp">
<img id="query" src="/images/dithered/q.png?v=1.2" data-original-src="/images/q.png?v=1.2">
<img id="unmarked" src="/images/not-dithered.png" alt="never dithered">
<img id="svg" src="/i/logo.svg?v=2">
<img id="external" src="https://example.com/x.png">
<img id="datauri" src="data:image/png;base64,iVBORw0KGgo.AAAA">
<figure class="dithered-image-figure"><div class="image-wrapper">
  <img id="blog" class="dithered-image active" src="post/dithered/p.png"
       data-dithered-src="post/dithered/p.png" data-original-src="post/p.jpg">
</div><figcaption><button class="request-original-btn" data-original-size="12KB">
  <span class="btn-text">view original</span></button></figcaption></figure>
{earlier_build_container}
<div class="dithered-image-container" id="legacy">
  <img src="/y.png" class="dithered"><img src="/y_original.png" class="original">
  <div class="dither-toggle"></div>
</div>
<a href="#navigated"><img id="linked" src="/images/dithered/l.png"
   data-original-src="/images/l.png"></a>
<pre id="results"></pre>
<script src="dithering.js"></script>
<script>
  setTimeout(function () {
    var dynamic = document.createElement("img");
    dynamic.id = "dynamic";
    dynamic.src = "/images/dithered/d.png";
    dynamic.setAttribute("data-original-src", "/images/d.png");
    document.body.appendChild(dynamic);
    var dynamicUnmarked = document.createElement("img");
    dynamicUnmarked.id = "dynamicUnmarked";
    dynamicUnmarked.src = "/images/e.png";
    document.body.appendChild(dynamicUnmarked);
  }, 50);
  setTimeout(function () {
    var results = {};
    function accessibility(container) {
      var toggle = container.querySelector(".dither-toggle");
      return {
        tag: toggle.tagName,
        type: toggle.getAttribute("type"),
        label: toggle.getAttribute("aria-label"),
        pressed: toggle.getAttribute("aria-pressed"),
        ditheredHidden: container.querySelector("img.dithered").getAttribute("aria-hidden"),
        originalHidden: container.querySelector("img.original").getAttribute("aria-hidden"),
        dotsHidden: Array.prototype.every.call(
          toggle.querySelectorAll(".dither-toggle-dot"),
          function (dot) { return dot.getAttribute("aria-hidden") === "true"; }
        ),
      };
    }
    Array.prototype.forEach.call(document.querySelectorAll("img[id]"), function (img) {
      var box = img.closest(".dithered-image-container");
      results[img.id] = box ? box.querySelector("img.original").getAttribute("src") : null;
    });
    var server = document.getElementById("server");
    var serverToggle = server.querySelector(".dither-toggle");
    results.serverBefore = accessibility(server);
    serverToggle.click();
    results.serverToggled = server.classList.contains("show-original");
    results.serverAfter = accessibility(server);
    serverToggle.click();
    results.serverBack = accessibility(server);

    var created = document.getElementById("plain").closest(".dithered-image-container");
    results.createdBefore = accessibility(created);
    created.querySelector(".dither-toggle").click();
    results.createdAfter = accessibility(created);

    var createdToggle = created.querySelector(".dither-toggle");
    createdToggle.focus();
    results.focused = document.activeElement === createdToggle;
    results.focusOutline = getComputedStyle(createdToggle).outlineStyle;

    var legacy = document.getElementById("legacy");
    var legacyToggle = legacy.querySelector(".dither-toggle");
    results.legacy = {
      role: legacyToggle.getAttribute("role"),
      tabIndex: legacyToggle.tabIndex,
      label: legacyToggle.getAttribute("aria-label"),
    };
    legacyToggle.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    results.legacyEnter = legacy.classList.contains("show-original");
    legacyToggle.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    results.legacySpace = legacy.classList.contains("show-original");
    var linkedBox = document.getElementById("linked").closest(".dithered-image-container");
    linkedBox.querySelector(".dither-toggle").click();
    results.linkedToggled = linkedBox.classList.contains("show-original");
    results.hash = location.hash;
    results.toggleCount = document.querySelectorAll(".dither-toggle").length;
    results.focusedOpacity = getComputedStyle(createdToggle).opacity;

    var blogImg = document.getElementById("blog");
    var blogButton = document.querySelector(".request-original-btn");
    blogButton.click();
    results.blogOriginal = {
      src: blogImg.getAttribute("src"),
      label: blogButton.querySelector(".btn-text").textContent,
      figureClass: blogImg.closest("figure").classList.contains("showing-original"),
    };
    blogButton.click();
    results.blogDithered = {
      src: blogImg.getAttribute("src"),
      label: blogButton.querySelector(".btn-text").textContent,
      figureClass: blogImg.closest("figure").classList.contains("showing-original"),
    };
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
    browser = find_browser()
    if browser is None:
        pytest.skip("no Chromium-family browser available")
    page_dir = tmp_path_factory.mktemp("dithering_js")
    shutil.copy(DITHERING_JS, page_dir / "dithering.js")
    shutil.copy(DITHERING_CSS, page_dir / "dithering.css")
    harness = HARNESS.replace("{earlier_build_container}", EARLIER_BUILD_CONTAINER)
    (page_dir / "harness.html").write_text(harness, encoding="utf-8")

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


class TestOnlyPipelineMarkedImages:
    """Only images the build dithered (data-original-src) get a toggle."""

    @pytest.mark.parametrize(
        "image_id, expected_original",
        [
            ("plain", "/images/a.png"),
            ("variant", "/assets/images/b_800_original.webp"),
            ("query", "/images/q.png?v=1.2"),
            ("linked", "/images/l.png"),
            ("dynamic", "/images/d.png"),
        ],
    )
    def test_marked_image_toggles_to_its_recorded_original(
        self, harness_results, image_id, expected_original
    ):
        assert harness_results[image_id] == expected_original

    @pytest.mark.parametrize(
        "image_id", ["unmarked", "dynamicUnmarked", "svg", "external", "datauri"]
    )
    def test_unmarked_image_is_not_wrapped(self, harness_results, image_id):
        assert harness_results[image_id] is None

    def test_blog_figure_images_keep_their_own_markup(self, harness_results):
        assert harness_results["blog"] is None


class TestBlogFigure:
    def test_button_shows_the_original(self, harness_results):
        assert harness_results["blogOriginal"] == {
            "src": "post/p.jpg",
            "label": "dithered (12KB)",
            "figureClass": True,
        }

    def test_button_again_restores_the_dithered_image(self, harness_results):
        assert harness_results["blogDithered"] == {
            "src": "post/dithered/p.png",
            "label": "view original",
            "figureClass": False,
        }


class TestToggle:
    def test_container_from_an_earlier_build_works(self, harness_results):
        assert harness_results["serverToggled"] is True

    def test_toggle_inside_link_does_not_navigate(self, harness_results):
        assert harness_results["linkedToggled"] is True
        assert harness_results["hash"] == ""

    def test_each_container_has_one_toggle(self, harness_results):
        # plain, variant, query, linked, dynamic + earlier-build + legacy
        assert harness_results["toggleCount"] == 7


LABEL = "Show original image"
SHOWING_DITHERED = {
    "tag": "BUTTON",
    "type": "button",
    "label": LABEL,
    "pressed": "false",
    "ditheredHidden": None,
    "originalHidden": "true",
    "dotsHidden": True,
}
SHOWING_ORIGINAL = {
    **SHOWING_DITHERED,
    "pressed": "true",
    "ditheredHidden": "true",
    "originalHidden": None,
}


class TestToggleAccessibility:
    """The toggle is a labelled toggle button; only the image on show is exposed."""

    @pytest.mark.parametrize("markup", ["server", "created"])
    def test_starts_as_an_unpressed_labelled_button(self, harness_results, markup):
        assert harness_results[f"{markup}Before"] == SHOWING_DITHERED

    @pytest.mark.parametrize("markup", ["server", "created"])
    def test_pressing_shows_the_original_and_updates_the_state(self, harness_results, markup):
        assert harness_results[f"{markup}After"] == SHOWING_ORIGINAL

    def test_pressing_again_restores_the_dithered_state(self, harness_results):
        assert harness_results["serverBack"] == SHOWING_DITHERED

    def test_keyboard_focus_is_visible(self, harness_results):
        assert harness_results["focused"] is True
        assert harness_results["focusOutline"] == "solid"
        assert harness_results["focusedOpacity"] == "1"

    def test_legacy_div_toggles_become_keyboard_operable(self, harness_results):
        assert harness_results["legacy"] == {"role": "button", "tabIndex": 0, "label": LABEL}
        assert harness_results["legacyEnter"] is True  # Enter shows the original
        assert harness_results["legacySpace"] is False  # Space toggles back
