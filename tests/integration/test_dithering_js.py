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
  <button type="button" class="request-original-btn" data-original-size="12KB">
  <span class="btn-text">view original</span></button>
</div><figcaption><span class="caption-text">A caption</span></figcaption></figure>
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


def run_page(tmp_path_factory, page_html, switches=()):
    """Load a page next to dithering.js/.css in headless Chromium; return its results JSON.

    Each call gets a fresh browser profile, so localStorage starts empty.
    """
    browser = find_browser()
    if browser is None:
        pytest.skip("no Chromium-family browser available")
    page_dir = tmp_path_factory.mktemp("dithering_js")
    shutil.copy(DITHERING_JS, page_dir / "dithering.js")
    shutil.copy(DITHERING_CSS, page_dir / "dithering.css")
    (page_dir / "page.html").write_text(page_html, encoding="utf-8")

    completed = subprocess.run(
        [
            browser,
            "--headless=new",
            "--disable-gpu",
            f"--user-data-dir={page_dir / 'profile'}",
            *switches,
            "--virtual-time-budget=3000",
            "--dump-dom",
            (page_dir / "page.html").as_uri(),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    match = re.search(r'<pre id="results">(.*?)</pre>', completed.stdout, re.S)
    assert match, f"page produced no results: {completed.stdout[-500:]}"
    return json.loads(html.unescape(match.group(1)))


@pytest.fixture(scope="module")
def harness_results(tmp_path_factory):
    harness = HARNESS.replace("{earlier_build_container}", EARLIER_BUILD_CONTAINER)
    return run_page(tmp_path_factory, harness)


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


# --- "Always show original images" ---------------------------------------------

PREFERENCE_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="dithering.css"></head><body>
<script>
  var errors = [];
  window.addEventListener("error", function (e) { errors.push(String(e.message)); });
  BEFORE
</script>
CONTROLS
<p>Intro</p>
<img id="one" src="/d/one.png" data-original-src="/one.png" alt="One">
<img id="two" src="/d/two.png" data-original-src="/two.png" alt="Two">
<figure class="dithered-image-figure"><div class="image-wrapper">
  <img id="fig" src="p/dithered/f.png" data-dithered-src="p/dithered/f.png"
       data-original-src="p/f.jpg" alt="Fig">
  <button type="button" class="request-original-btn"><span class="btn-text">view original</span></button>
</div></figure>
<pre id="results"></pre>
<script src="dithering.js"></script>
<script>
  setTimeout(function () {
    function showing(id) {
      return document.getElementById(id).closest(".dithered-image-container")
        .classList.contains("show-original");
    }
    function state() {
      var controls = document.querySelectorAll("[data-sonne-original-images]");
      return {
        one: showing("one"),
        two: showing("two"),
        fig: document.getElementById("fig").getAttribute("src"),
        controls: Array.prototype.map.call(controls, function (c) {
          return {
            tag: c.tagName,
            type: c.getAttribute("type"),
            text: c.textContent.trim(),
            pressed: c.getAttribute("aria-pressed"),
            checked: c.tagName === "INPUT" ? c.checked : null,
          };
        }),
        stored: (function () {
          try { return localStorage.getItem("sonne-show-original-images"); }
          catch (e) { return "blocked"; }
        })(),
        api: window.sonneDithering.showsOriginals(),
      };
    }
    var results = { initial: state() };
    var injected = document.querySelector(".sonne-original-images-toggle");
    results.placedBeforeFirstImage = Boolean(injected) &&
      injected.nextElementSibling === document.getElementById("one").closest(".dithered-image-container");
    var toggle = document.querySelector(".dither-toggle");
    var dot = toggle.querySelector(".dither-toggle-dot");
    results.css = {
      transition: getComputedStyle(document.getElementById("one")).transitionDuration,
      toggleForcedColorAdjust: getComputedStyle(toggle).forcedColorAdjust,
      toggleBorder: getComputedStyle(toggle).borderTopStyle,
      dotBackground: getComputedStyle(dot).backgroundColor,
      toggleOpacity: getComputedStyle(toggle).opacity,
    };
    ACTIONS
    results.after = state();
    results.errors = errors;
    document.getElementById("results").textContent = JSON.stringify(results);
  }, 400);
</script></body></html>"""

CLICK_CONTROL = 'document.querySelector("[data-sonne-original-images]").click();'
STORAGE_KEY = "sonne-show-original-images"
FORCED_COLORS = ("--force-high-contrast",)  # forced-colors: active + prefers-contrast: more


def preference_page(before="", controls="", actions=""):
    return (
        PREFERENCE_PAGE.replace("BEFORE", before)
        .replace("CONTROLS", controls)
        .replace("ACTIONS", actions)
    )


@pytest.fixture(scope="module")
def default_preference(tmp_path_factory):
    return run_page(tmp_path_factory, preference_page(actions=CLICK_CONTROL))


@pytest.fixture(scope="module")
def stored_preference(tmp_path_factory):
    before = f'localStorage.setItem("{STORAGE_KEY}", "true");'
    return run_page(tmp_path_factory, preference_page(before=before))


@pytest.fixture(scope="module")
def forced_colors(tmp_path_factory):
    return run_page(tmp_path_factory, preference_page(), FORCED_COLORS)


@pytest.fixture(scope="module")
def forced_colors_with_stored_choice(tmp_path_factory):
    before = f'localStorage.setItem("{STORAGE_KEY}", "false");'
    return run_page(tmp_path_factory, preference_page(before=before), FORCED_COLORS)


@pytest.fixture(scope="module")
def template_checkbox(tmp_path_factory):
    controls = (
        '<label><input type="checkbox" id="pref" data-sonne-original-images>'
        " Show original images</label>"
    )
    actions = 'document.getElementById("pref").click();'
    return run_page(tmp_path_factory, preference_page(controls=controls, actions=actions))


@pytest.fixture(scope="module")
def blocked_storage(tmp_path_factory):
    before = (
        'Object.defineProperty(window, "localStorage", '
        '{ get: function () { throw new Error("storage blocked"); } });'
    )
    return run_page(tmp_path_factory, preference_page(before=before, actions=CLICK_CONTROL))


SHOWING_ALL_DITHERED = {"one": False, "two": False, "fig": "p/dithered/f.png"}
SHOWING_ALL_ORIGINALS = {"one": True, "two": True, "fig": "p/f.jpg"}


def images(state):
    return {key: state[key] for key in ("one", "two", "fig")}


class TestOriginalImagesPreference:
    def test_pages_without_a_control_get_one_labelled_button(self, default_preference):
        assert default_preference["initial"]["controls"] == [
            {
                "tag": "BUTTON",
                "type": "button",
                "text": "Always show original images",
                "pressed": "false",
                "checked": None,
            }
        ]
        assert default_preference["placedBeforeFirstImage"] is True

    def test_dithered_images_are_shown_by_default(self, default_preference):
        assert images(default_preference["initial"]) == SHOWING_ALL_DITHERED

    def test_pressing_the_control_shows_every_original_and_is_remembered(self, default_preference):
        after = default_preference["after"]
        assert images(after) == SHOWING_ALL_ORIGINALS
        assert after["controls"][0]["pressed"] == "true"
        assert after["stored"] == "true"
        assert after["api"] is True

    def test_stored_preference_applies_on_load(self, stored_preference):
        initial = stored_preference["initial"]
        assert images(initial) == SHOWING_ALL_ORIGINALS
        assert initial["controls"][0]["pressed"] == "true"

    def test_template_control_is_used_instead_of_adding_one(self, template_checkbox):
        assert [c["tag"] for c in template_checkbox["initial"]["controls"]] == ["INPUT"]
        assert template_checkbox["initial"]["controls"][0]["checked"] is False
        after = template_checkbox["after"]
        assert images(after) == SHOWING_ALL_ORIGINALS
        assert after["controls"][0]["checked"] is True

    def test_blocked_storage_still_applies_the_choice(self, blocked_storage):
        after = blocked_storage["after"]
        assert images(after) == SHOWING_ALL_ORIGINALS
        assert after["stored"] == "blocked"
        assert blocked_storage["errors"] == []


class TestHighContrastAndForcedColors:
    def test_originals_are_shown_by_default(self, forced_colors):
        assert images(forced_colors["initial"]) == SHOWING_ALL_ORIGINALS
        assert forced_colors["initial"]["controls"][0]["pressed"] == "true"

    def test_a_stored_choice_wins_over_the_system_setting(self, forced_colors_with_stored_choice):
        assert images(forced_colors_with_stored_choice["initial"]) == SHOWING_ALL_DITHERED

    def test_toggle_is_drawn_in_system_colours(self, forced_colors):
        css = forced_colors["css"]
        assert css["toggleForcedColorAdjust"] == "none"
        assert css["toggleBorder"] == "solid"
        assert css["dotBackground"] not in ("rgba(0, 0, 0, 0)", "transparent")


class TestMotionAndContrast:
    def test_reduced_motion_turns_transitions_off(self, default_preference):
        # Headless Chromium reports prefers-reduced-motion: reduce.
        assert default_preference["css"]["transition"] == "0s"

    def test_toggle_is_not_faded(self, default_preference):
        assert default_preference["css"]["toggleOpacity"] == "1"
