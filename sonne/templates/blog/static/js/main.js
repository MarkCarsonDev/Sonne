// Blog JavaScript
document.addEventListener("DOMContentLoaded", function () {
	// Add "active" class to current navigation link
	const currentPath = window.location.pathname;
	const navLinks = document.querySelectorAll("nav a");

	navLinks.forEach((link) => {
		// Check if the link URL is the current path or
		// if it's a blog subpage (i.e. /blog/2025/01/01/...)
		const linkUrl = link.getAttribute("href");
		if (
			linkUrl === currentPath ||
			(linkUrl === "/blog/" && currentPath.startsWith("/blog/"))
		) {
			link.classList.add("active");
		}
	});

	// Add responsive table classes
	const tables = document.querySelectorAll(".post-content table");
	tables.forEach((table) => {
		const wrapper = document.createElement("div");
		wrapper.className = "table-responsive";
		table.parentNode.insertBefore(wrapper, table);
		wrapper.appendChild(table);
	});

	// Add external link indicators
	const postLinks = document.querySelectorAll(".post-content a");
	postLinks.forEach((link) => {
		const href = link.getAttribute("href");
		if (
			href &&
			href.startsWith("http") &&
			!href.includes(window.location.hostname)
		) {
			link.setAttribute("target", "_blank");
			link.setAttribute("rel", "noopener noreferrer");

			// Add external link icon
			if (!link.querySelector(".external-link-icon")) {
				const icon = document.createElement("span");
				icon.className = "external-link-icon";
				icon.innerHTML = " ↗";
				link.appendChild(icon);
			}
		}
	});
});
