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

	// 3x3 grid forming an X: filled corners and centre.
	var TOGGLE_DOT_IS_FILLED = [true, false, true, false, true, false, true, false, true];

	function start() {
		wrapImagesWithin(document.body);
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
		originalImg.alt = img.getAttribute("alt") || "";
		originalImg.loading = img.getAttribute("loading") || "lazy";
		// Only the image on show is exposed to assistive technology.
		originalImg.setAttribute("aria-hidden", "true");

		img.classList.add("dithered");

		img.parentNode.insertBefore(container, img);
		container.appendChild(img);
		container.appendChild(originalImg);
		container.appendChild(createToggle());
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
			var figure = button.closest(BLOG_FIGURE_SELECTOR);
			var img = figure && figure.querySelector("img");
			if (!img) {
				return;
			}
			var isOriginalShown = !button.classList.contains(FIGURE_SHOWING_ORIGINAL_CLASS);
			img.src = img.getAttribute(isOriginalShown ? "data-original-src" : "data-dithered-src");
			button.classList.toggle(FIGURE_SHOWING_ORIGINAL_CLASS, isOriginalShown);
			figure.classList.toggle(FIGURE_SHOWING_ORIGINAL_CLASS, isOriginalShown);
			var label = button.querySelector(".btn-text");
			if (label) {
				label.textContent = isOriginalShown ? ditheredLabel(button) : "view original";
			}
		});
		button.setAttribute(BOUND_ATTRIBUTE, "true");
	}

	function ditheredLabel(button) {
		var originalSize = button.getAttribute("data-original-size");
		return originalSize ? "dithered (" + originalSize + ")" : "dithered";
	}

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
