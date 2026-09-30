// Dithered/original toggle for static-pipeline images.
//
// Static pipeline convention: the dithered image is served at the image's
// own URL and the untouched original beside it with an "_original" suffix
// before the extension (images/a.png -> images/a_original.png, sized
// variants b_800.webp -> b_800_original.webp). Every other same-origin
// raster image is wrapped with a toggle between the two.
//
// Blog figures (<figure class="dithered-image-figure"> with
// data-original-src/data-dithered-src) follow the blog convention and have
// their own inline script; they are left alone here.
(function () {
	"use strict";

	var CONTAINER_CLASS = "dithered-image-container";
	var TOGGLE_CLASS = "dither-toggle";
	var SHOW_ORIGINAL_CLASS = "show-original";
	var BOUND_ATTRIBUTE = "data-has-listener";
	var BLOG_FIGURE_SELECTOR = ".dithered-image-figure";

	// 3x3 grid forming an X: filled corners and centre.
	var TOGGLE_DOT_IS_FILLED = [true, false, true, false, true, false, true, false, true];

	function start() {
		wrapImagesWithin(document.body);
		watchForNewImages();
	}

	function wrapImagesWithin(root) {
		imagesWithin(root).filter(isStandaloneImage).forEach(wrapWithToggle);
		// Server-rendered containers (the process_image filter) arrive
		// with a toggle that has no listener yet.
		togglesWithin(root).forEach(bindToggle);
	}

	function imagesWithin(root) {
		var images = Array.prototype.slice.call(root.querySelectorAll("img"));
		return root.tagName === "IMG" ? [root].concat(images) : images;
	}

	function togglesWithin(root) {
		var toggles = Array.prototype.slice.call(root.querySelectorAll("." + TOGGLE_CLASS));
		return root.classList.contains(TOGGLE_CLASS) ? [root].concat(toggles) : toggles;
	}

	function isStandaloneImage(img) {
		if (img.closest("." + CONTAINER_CLASS) || img.closest(BLOG_FIGURE_SELECTOR)) {
			return false;
		}
		if (img.hasAttribute("data-original-src")) {
			return false;
		}
		var url = sameOriginUrl(img.getAttribute("src"));
		// SVGs are never dithered; other origins have no "_original" twin.
		return url !== null && !/\.svg$/i.test(url.pathname);
	}

	function sameOriginUrl(src) {
		if (!src) {
			return null;
		}
		var url;
		try {
			url = new URL(src, document.baseURI);
		} catch (e) {
			return null;
		}
		if (url.protocol === "data:" || url.protocol === "blob:") {
			return null;
		}
		return url.origin === window.location.origin ? url : null;
	}

	// Insert "_original" before the file name's extension, leaving any
	// directories, query string and fragment untouched.
	function originalSrcFor(src) {
		var suffixStart = src.search(/[?#]/);
		var path = suffixStart === -1 ? src : src.substring(0, suffixStart);
		var suffix = suffixStart === -1 ? "" : src.substring(suffixStart);
		var fileNameStart = path.lastIndexOf("/") + 1;
		var extensionStart = path.lastIndexOf(".");
		if (extensionStart < fileNameStart) {
			return path + "_original" + suffix;
		}
		return (
			path.substring(0, extensionStart) + "_original" + path.substring(extensionStart) + suffix
		);
	}

	function wrapWithToggle(img) {
		var container = document.createElement("div");
		container.className = CONTAINER_CLASS;

		var originalImg = document.createElement("img");
		originalImg.src = originalSrcFor(img.getAttribute("src"));
		originalImg.className = "original";
		originalImg.alt = img.getAttribute("alt") || "Image";
		originalImg.loading = img.getAttribute("loading") || "lazy";

		img.classList.add("dithered");

		img.parentNode.insertBefore(container, img);
		container.appendChild(img);
		container.appendChild(originalImg);
		container.appendChild(createToggle());
	}

	function createToggle() {
		var toggle = document.createElement("div");
		toggle.className = TOGGLE_CLASS;
		TOGGLE_DOT_IS_FILLED.forEach(function (isFilled) {
			var dot = document.createElement("div");
			dot.className = isFilled ? "dither-toggle-dot" : "dither-toggle-dot empty";
			toggle.appendChild(dot);
		});
		bindToggle(toggle);
		return toggle;
	}

	function bindToggle(toggle) {
		if (toggle.hasAttribute(BOUND_ATTRIBUTE)) {
			return;
		}
		toggle.addEventListener("click", function (event) {
			var container = toggle.closest("." + CONTAINER_CLASS);
			if (container) {
				container.classList.toggle(SHOW_ORIGINAL_CLASS);
			}
			// A toggle inside a link must not also follow the link, nor
			// trigger click handlers (e.g. lightboxes) around the image.
			event.preventDefault();
			event.stopPropagation();
		});
		toggle.setAttribute(BOUND_ATTRIBUTE, "true");
	}

	function watchForNewImages() {
		if (!("MutationObserver" in window)) {
			return;
		}
		new MutationObserver(function (mutations) {
			var nodesWereAdded = mutations.some(function (mutation) {
				return mutation.addedNodes.length > 0;
			});
			if (nodesWereAdded) {
				wrapImagesWithin(document.body);
			}
		}).observe(document.body, { childList: true, subtree: true });
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start);
	} else {
		start();
	}
})();
