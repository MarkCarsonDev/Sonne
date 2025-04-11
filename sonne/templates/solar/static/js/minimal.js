/**
 * Solar Template - Minimal JavaScript
 * Energy-efficient JavaScript with minimal functionality
 */

// Execute code when DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
	// Toggle between dark and light mode
	const themeToggle = document.querySelector(".theme-toggle");
	if (themeToggle) {
		themeToggle.addEventListener("click", function () {
			const currentTheme = document.body.getAttribute("data-theme");
			const newTheme = currentTheme === "dark" ? "light" : "dark";

			// Update theme
			document.body.setAttribute("data-theme", newTheme);

			// Update toggle button icon
			themeToggle.innerHTML = newTheme === "dark" ? "☀️" : "🌙";

			// Store preference if localStorage is available, using minimal operations
			try {
				localStorage.setItem("solarTheme", newTheme);
			} catch (e) {
				// Fail silently if localStorage is not available
			}
		});

		// Check for saved preference
		try {
			const savedTheme = localStorage.getItem("solarTheme");
			if (savedTheme) {
				document.body.setAttribute("data-theme", savedTheme);
				themeToggle.innerHTML = savedTheme === "dark" ? "☀️" : "🌙";
			}
		} catch (e) {
			// Fail silently if localStorage is not available
		}
	}

	// Update battery status if available and simulation is enabled
	const batteryFill = document.querySelector(".battery-fill");
	if (batteryFill && window.location.pathname === "/") {
		// Update battery every 2 minutes (only on homepage to save energy)
		updateBatteryStatus();
		setInterval(updateBatteryStatus, 120000);
	}

	// Lazy load images for better energy efficiency
	lazyLoadImages();
});

/**
 * Updates the battery status using fetch API
 * Only called on homepage to save energy
 */
function updateBatteryStatus() {
	// Simple fetch with minimal options to reduce bandwidth
	fetch("/api/battery-status", {
		method: "GET",
		headers: { Accept: "application/json" },
	})
		.then(function (response) {
			if (response.ok) return response.json();
			throw new Error("Network response was not ok");
		})
		.then(function (data) {
			// Update UI elements with minimal DOM operations
			const batteryFill = document.querySelector(".battery-fill");
			const percentageText = document.querySelector(
				".battery-status span:last-child"
			);

			if (batteryFill && percentageText) {
				batteryFill.style.width = data.percentage + "%";
				percentageText.textContent =
					data.percentage +
					"%" +
					(data.charging ? " (Charging)" : "");
			}
		})
		.catch(function (error) {
			// Fail silently - don't waste energy on error reporting
			console.log("Battery update failed");
		});
}

/**
 * Simple lazy loading implementation that uses minimal resources
 */
function lazyLoadImages() {
	// Check for IntersectionObserver support
	if ("IntersectionObserver" in window) {
		const lazyImages = document.querySelectorAll("img[data-src]");

		// Create observer with minimal options
		const imageObserver = new IntersectionObserver(
			function (entries) {
				entries.forEach(function (entry) {
					if (entry.isIntersecting) {
						const img = entry.target;
						img.src = img.dataset.src;
						img.removeAttribute("data-src");
						imageObserver.unobserve(img);
					}
				});
			},
			{
				// Use higher threshold to load images closer to viewport
				rootMargin: "50px",
				threshold: 0.1,
			}
		);

		lazyImages.forEach(function (img) {
			imageObserver.observe(img);
		});
	} else {
		// Fallback for browsers without IntersectionObserver
		// Just load all images immediately
		const lazyImages = document.querySelectorAll("img[data-src]");
		lazyImages.forEach(function (img) {
			img.src = img.dataset.src;
			img.removeAttribute("data-src");
		});
	}
}
