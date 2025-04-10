// Minimal JavaScript
document.addEventListener("DOMContentLoaded", function () {
	// Simple utility to add "active" class to the current page link in navigation
	const currentPath = window.location.pathname;
	const navLinks = document.querySelectorAll("nav a");

	navLinks.forEach((link) => {
		if (link.getAttribute("href") === currentPath) {
			link.classList.add("active");
		}
	});
});
