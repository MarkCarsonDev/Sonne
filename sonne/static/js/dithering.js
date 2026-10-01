// Dithered/original toggles for the images a Sonne build dithered.
//
// Convention: an original keeps its own URL and its dithered copy lives
// beside it (<dir>/dithered/<name>.png, or a sized variant). The build
// points each such <img> at the dithered copy and records the original in
// data-original-src; only images marked that way get a toggle, so nothing
// here guesses URLs and an image the build did not dither is left alone.
//
// Two presentations share that marking:
// - Standalone images are wrapped in a container with a toggle <button>
//   (keyboard and screen-reader operable; aria-pressed says whether the
//   original is showing).
// - Blog post figures (<figure class="dithered-image-figure">) are rendered
//   by the blog pipeline with a caption and a "view original" button, which
//   is wired up here.
//
// Visitor preference "always show original images" (dithered images can be
// hard to read with low vision):
// - Stored in localStorage; without a stored choice it follows
//   prefers-contrast: more and forced-colors: active.
// - Any element with the data-sonne-original-images attribute is a control
//   for it: a <button> (gets aria-pressed) or a checkbox (gets checked).
//   If a page has dithered images and no such control, one small button is
//   added before the first of them.
// - Scripts can use window.sonneDithering.showOriginals(true|false) and
//   .showsOriginals(), and listen for the "sonne:original-images" event.
(function () {
	"use strict";

	var CONTAINER_CLASS = "dithered-image-container";
	var TOGGLE_CLASS = "dither-toggle";
	var SHOW_ORIGINAL_CLASS = "show-original";
	var BOUND_ATTRIBUTE = "data-has-listener";
	var BLOG_FIGURE_SELECTOR = ".dithered-image-figure";
	var FIGURE_BUTTON_SELECTOR = ".request-original-btn";
	var FIGURE_SHOWING_ORIGINAL_CLASS = "showing-original";
	// One fixed name; aria-pressed carries the state ("Show original image,
	// toggle button, pressed"), so the label never contradicts it.
	var TOGGLE_LABEL = "Show original image";

	var PREFERENCE_ATTRIBUTE = "data-sonne-original-images";
	var PREFERENCE_CONTROL_CLASS = "sonne-original-images-toggle";
	var PREFERENCE_CONTROL_LABEL = "Always show original images";
	var PREFERENCE_STORAGE_KEY = "sonne-show-original-images";
	var PREFERENCE_EVENT = "sonne:original-images";
	// Visitors who asked their system for more contrast, or use forced
	// colours (e.g. Windows High Contrast), get the originals by default.
	var ORIGINALS_BY_DEFAULT_QUERIES = ["(prefers-contrast: more)", "(forced-colors: active)"];

	// 3x3 grid forming an X: filled corners and centre.
	var TOGGLE_DOT_IS_FILLED = [true, false, true, false, true, false, true, false, true];

	function start() {
		wrapImagesWithin(document.body);
		addPreferenceControlIfMissing();
		applyPreference();
		followSystemPreference();
		watchForNewImages();
	}

	function wrapImagesWithin(root) {
		imagesWithin(root).filter(isMarkedStandaloneImage).forEach(wrapWithToggle);
		// Containers already in the markup (pages built by earlier Sonne
		// versions) arrive with a toggle that has no listener yet.
		matchesWithin(root, "." + TOGGLE_CLASS).forEach(bindToggle);
		matchesWithin(root, BLOG_FIGURE_SELECTOR + " " + FIGURE_BUTTON_SELECTOR).forEach(
			bindFigureButton
		);
		matchesWithin(root, "[" + PREFERENCE_ATTRIBUTE + "]").forEach(bindPreferenceControl);
	}

	function imagesWithin(root) {
		return matchesWithin(root, "img");
	}

	function matchesWithin(root, selector) {
		var matches = Array.prototype.slice.call(root.querySelectorAll(selector));
		return root.matches(selector) ? [root].concat(matches) : matches;
	}

	// Marked by the build (data-original-src), and not already presented by a
	// container or a blog figure.
	function isMarkedStandaloneImage(img) {
		if (!img.getAttribute("data-original-src")) {
			return false;
		}
		return !img.closest("." + CONTAINER_CLASS) && !img.closest(BLOG_FIGURE_SELECTOR);
	}

	function wrapWithToggle(img) {
		var container = document.createElement("div");
		container.className = CONTAINER_CLASS;
		// Images in a container have no margin (dithering.css), so the
		// original and the toggle line up with the image; the container
		// takes over the image's margin to keep the page's spacing.
		container.style.margin = window.getComputedStyle(img).margin;

		var originalImg = document.createElement("img");
		originalImg.src = img.getAttribute("data-original-src");
		originalImg.className = "original";
		// Both images describe the same picture, so they share its alt text.
		originalImg.alt = img.getAttribute("alt") || "";
		originalImg.loading = img.getAttribute("loading") || "lazy";
		// Only the image on show is exposed to assistive technology.
		originalImg.setAttribute("aria-hidden", "true");

		img.classList.add("dithered");

		img.parentNode.insertBefore(container, img);
		container.appendChild(img);
		container.appendChild(originalImg);
		var toggle = createToggle();
		container.appendChild(toggle);
		if (currentPreference()) {
			showOriginal(container, toggle, true);
		}
	}

	function createToggle() {
		var toggle = document.createElement("button");
		toggle.type = "button";
		toggle.className = TOGGLE_CLASS;
		toggle.setAttribute("aria-pressed", "false");
		toggle.setAttribute("aria-label", TOGGLE_LABEL);
		toggle.title = TOGGLE_LABEL;
		TOGGLE_DOT_IS_FILLED.forEach(function (isFilled) {
			var dot = document.createElement("span");
			dot.className = isFilled ? "dither-toggle-dot" : "dither-toggle-dot empty";
			dot.setAttribute("aria-hidden", "true");
			toggle.appendChild(dot);
		});
		bindToggle(toggle);
		return toggle;
	}

	function bindToggle(toggle) {
		if (toggle.hasAttribute(BOUND_ATTRIBUTE)) {
			return;
		}
		makeOperable(toggle);
		toggle.addEventListener("click", function (event) {
			var container = toggle.closest("." + CONTAINER_CLASS);
			if (container) {
				showOriginal(container, toggle, !container.classList.contains(SHOW_ORIGINAL_CLASS));
			}
			// A toggle inside a link must not also follow the link, nor
			// trigger click handlers (e.g. lightboxes) around the image.
			event.preventDefault();
			event.stopPropagation();
		});
		toggle.setAttribute(BOUND_ATTRIBUTE, "true");
	}

	// Pages built by older Sonne versions render the toggle as a <div>;
	// give those the keyboard and screen-reader behaviour a button has.
	function makeOperable(toggle) {
		if (!toggle.hasAttribute("aria-pressed")) {
			toggle.setAttribute("aria-pressed", "false");
		}
		if (!toggle.hasAttribute("aria-label")) {
			toggle.setAttribute("aria-label", TOGGLE_LABEL);
		}
		if (toggle.tagName === "BUTTON") {
			return;
		}
		toggle.setAttribute("role", "button");
		toggle.tabIndex = 0;
		toggle.addEventListener("keydown", function (event) {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				toggle.click();
			}
		});
	}

	function showOriginal(container, toggle, isOriginalShown) {
		container.classList.toggle(SHOW_ORIGINAL_CLASS, isOriginalShown);
		toggle.setAttribute("aria-pressed", String(isOriginalShown));
		var dithered = container.querySelector("img.dithered");
		var original = container.querySelector("img.original");
		if (dithered) {
			setHidden(dithered, isOriginalShown);
		}
		if (original) {
			setHidden(original, !isOriginalShown);
		}
	}

	function setHidden(img, isHidden) {
		if (isHidden) {
			img.setAttribute("aria-hidden", "true");
		} else {
			img.removeAttribute("aria-hidden");
		}
	}

	// Blog figures swap the image's src in place; the button's text says
	// what a press will show (the original's size when known).
	function bindFigureButton(button) {
		if (button.hasAttribute(BOUND_ATTRIBUTE)) {
			return;
		}
		button.addEventListener("click", function () {
			showFigureOriginal(button, !button.classList.contains(FIGURE_SHOWING_ORIGINAL_CLASS));
		});
		button.setAttribute(BOUND_ATTRIBUTE, "true");
		if (currentPreference()) {
			showFigureOriginal(button, true);
		}
	}

	function showFigureOriginal(button, isOriginalShown) {
		var figure = button.closest(BLOG_FIGURE_SELECTOR);
		var img = figure && figure.querySelector("img");
		if (!img) {
			return;
		}
		img.src = img.getAttribute(isOriginalShown ? "data-original-src" : "data-dithered-src");
		button.classList.toggle(FIGURE_SHOWING_ORIGINAL_CLASS, isOriginalShown);
		figure.classList.toggle(FIGURE_SHOWING_ORIGINAL_CLASS, isOriginalShown);
		var label = button.querySelector(".btn-text");
		if (label) {
			label.textContent = isOriginalShown ? ditheredLabel(button) : "view original";
		}
	}

	function ditheredLabel(button) {
		var originalSize = button.getAttribute("data-original-size");
		return originalSize ? "dithered (" + originalSize + ")" : "dithered";
	}

	// --- "Always show original images" -------------------------------------

	function storedPreference() {
		try {
			var stored = window.localStorage.getItem(PREFERENCE_STORAGE_KEY);
			return stored === "true" || stored === "false" ? stored === "true" : null;
		} catch (e) {
			return null; // storage blocked (private mode, sandbox): use the default
		}
	}

	function systemPrefersOriginals() {
		if (!window.matchMedia) {
			return false;
		}
		return ORIGINALS_BY_DEFAULT_QUERIES.some(function (query) {
			return window.matchMedia(query).matches;
		});
	}

	function showsOriginals() {
		var stored = storedPreference();
		return stored === null ? systemPrefersOriginals() : stored;
	}

	function setShowOriginals(value) {
		try {
			window.localStorage.setItem(PREFERENCE_STORAGE_KEY, String(Boolean(value)));
		} catch (e) {
			// Not persisted, but still applied to this page.
			sessionOverride = Boolean(value);
		}
		applyPreference();
	}

	// Used only when storage is unavailable, so a choice holds for the page.
	var sessionOverride = null;

	function currentPreference() {
		return sessionOverride === null ? showsOriginals() : sessionOverride;
	}

	function applyPreference() {
		var showOriginals = currentPreference();
		matchesWithin(document.body, "." + CONTAINER_CLASS).forEach(function (container) {
			var toggle = container.querySelector("." + TOGGLE_CLASS);
			if (toggle) {
				showOriginal(container, toggle, showOriginals);
			}
		});
		matchesWithin(document.body, BLOG_FIGURE_SELECTOR + " " + FIGURE_BUTTON_SELECTOR).forEach(
			function (button) {
				showFigureOriginal(button, showOriginals);
			}
		);
		matchesWithin(document.body, "[" + PREFERENCE_ATTRIBUTE + "]").forEach(function (control) {
			reflectPreference(control, showOriginals);
		});
		document.dispatchEvent(
			new CustomEvent(PREFERENCE_EVENT, { detail: { showOriginals: showOriginals } })
		);
	}

	function bindPreferenceControl(control) {
		if (control.hasAttribute(BOUND_ATTRIBUTE)) {
			return;
		}
		var isCheckbox = control.tagName === "INPUT" && control.type === "checkbox";
		if (!isCheckbox && control.tagName === "BUTTON") {
			control.type = "button";
		}
		control.addEventListener(isCheckbox ? "change" : "click", function () {
			setShowOriginals(isCheckbox ? control.checked : !currentPreference());
		});
		control.setAttribute(BOUND_ATTRIBUTE, "true");
		reflectPreference(control, currentPreference());
	}

	function reflectPreference(control, showOriginals) {
		if (control.tagName === "INPUT" && control.type === "checkbox") {
			control.checked = showOriginals;
		} else {
			control.setAttribute("aria-pressed", String(showOriginals));
		}
	}

	// Pages whose template has no control of its own get one small button,
	// placed right before the first dithered image it affects.
	function addPreferenceControlIfMissing() {
		if (document.querySelector("[" + PREFERENCE_ATTRIBUTE + "]")) {
			return;
		}
		var first = document.querySelector("." + CONTAINER_CLASS + ", " + BLOG_FIGURE_SELECTOR);
		if (!first) {
			return;
		}
		var control = document.createElement("button");
		control.type = "button";
		control.className = PREFERENCE_CONTROL_CLASS;
		control.setAttribute(PREFERENCE_ATTRIBUTE, "");
		control.textContent = PREFERENCE_CONTROL_LABEL;
		first.parentNode.insertBefore(control, first);
		bindPreferenceControl(control);
	}

	// Without a stored choice, follow the system setting as it changes.
	function followSystemPreference() {
		if (!window.matchMedia) {
			return;
		}
		ORIGINALS_BY_DEFAULT_QUERIES.forEach(function (query) {
			var list = window.matchMedia(query);
			var onChange = function () {
				if (storedPreference() === null && sessionOverride === null) {
					applyPreference();
				}
			};
			if (list.addEventListener) {
				list.addEventListener("change", onChange);
			} else if (list.addListener) {
				list.addListener(onChange);
			}
		});
	}

	window.sonneDithering = {
		showOriginals: setShowOriginals,
		showsOriginals: currentPreference,
	};

	// Only newly added subtrees are scanned, so a page that keeps changing
	// does not re-walk the whole document each time.
	function watchForNewImages() {
		if (!("MutationObserver" in window)) {
			return;
		}
		new MutationObserver(function (mutations) {
			mutations.forEach(function (mutation) {
				mutation.addedNodes.forEach(function (node) {
					if (node.nodeType === Node.ELEMENT_NODE && node.isConnected) {
						wrapImagesWithin(node);
					}
				});
			});
		}).observe(document.body, { childList: true, subtree: true });
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start);
	} else {
		start();
	}
})();
