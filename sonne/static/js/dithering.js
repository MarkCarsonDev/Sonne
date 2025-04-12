// Toggle dithered/original images
document.addEventListener("DOMContentLoaded", function () {
	// Process all img tags on the page
	processAllImages();
});

function processAllImages() {
	// First, process images that are already in dithered-image-containers
	const containedImages = document.querySelectorAll(
		".dithered-image-container img.dithered"
	);

	// Then find standalone images that need to be processed
	const standaloneImages = document.querySelectorAll(
		"img:not(.dithered):not(.original)"
	);

	standaloneImages.forEach(function (img) {
		// Skip SVG images
		if (img.src.endsWith(".svg")) {
			return;
		}

		// Create container and controls
		wrapImageWithDitheringControls(img);
	});

	// Add click handlers to all toggle buttons
	const toggleButtons = document.querySelectorAll(".dither-toggle");
	toggleButtons.forEach(function (toggle) {
		// Ensure we don't add multiple event listeners
		if (!toggle.hasAttribute("data-has-listener")) {
			toggle.addEventListener("click", function (e) {
				const container = toggle.closest(".dithered-image-container");
				container.classList.toggle("show-original");
				e.stopPropagation();
			});
			toggle.setAttribute("data-has-listener", "true");
		}
	});
}

function wrapImageWithDitheringControls(img) {
	// Skip if already processed
	if (img.closest(".dithered-image-container")) {
		return;
	}

	// Get image attributes
	const src = img.getAttribute("src");
	const alt = img.getAttribute("alt") || "Image";
	const loading = img.getAttribute("loading") || "lazy";

	// Create container
	const container = document.createElement("div");
	container.className = "dithered-image-container";

	// Create original image path
	let originalSrc = "";
	if (src.includes("_")) {
		// Format: path/filename_size.ext
		const sizeMatch = src.match(/_(\d+)\./);
		if (sizeMatch) {
			const size = sizeMatch[1];
			originalSrc = src.replace(`_${size}.`, `_${size}_original.`);
		} else {
			// No size indicator, just add _original before extension
			const lastDotIndex = src.lastIndexOf(".");
			if (lastDotIndex !== -1) {
				originalSrc =
					src.substring(0, lastDotIndex) +
					"_original" +
					src.substring(lastDotIndex);
			} else {
				// No extension, just append _original
				originalSrc = src + "_original";
			}
		}
	} else {
		// Format: path/filename.ext
		const lastDotIndex = src.lastIndexOf(".");
		if (lastDotIndex !== -1) {
			originalSrc =
				src.substring(0, lastDotIndex) +
				"_original" +
				src.substring(lastDotIndex);
		} else {
			// No extension, just append _original
			originalSrc = src + "_original";
		}
	}

	// Create original image element
	const originalImg = document.createElement("img");
	originalImg.src = originalSrc;
	originalImg.className = "original";
	originalImg.alt = alt;
	originalImg.loading = loading;

	// Add dithered class to original image
	img.className = (img.className ? img.className + " " : "") + "dithered";

	// Create toggle button
	const toggle = document.createElement("div");
	toggle.className = "dither-toggle";

	// Create dots pattern (X pattern)
	const dotClasses = ["", "empty", "", "empty", "", "empty", "", "empty", ""];
	dotClasses.forEach(function (className) {
		const dot = document.createElement("div");
		dot.className =
			"dither-toggle-dot" + (className ? " " + className : "");
		toggle.appendChild(dot);
	});

	// Add event listener to toggle
	toggle.addEventListener("click", function (e) {
		container.classList.toggle("show-original");
		e.stopPropagation();
	});
	toggle.setAttribute("data-has-listener", "true");

	// Replace the image with the container
	img.parentNode.insertBefore(container, img);
	container.appendChild(img);
	container.appendChild(originalImg);
	container.appendChild(toggle);
}

// Watch for dynamic content changes
if ("MutationObserver" in window) {
	const observer = new MutationObserver(function (mutations) {
		let needsProcessing = false;
		mutations.forEach(function (mutation) {
			if (mutation.addedNodes.length) {
				needsProcessing = true;
			}
		});

		if (needsProcessing) {
			processAllImages();
		}
	});

	observer.observe(document.body, {
		childList: true,
		subtree: true,
	});
}
