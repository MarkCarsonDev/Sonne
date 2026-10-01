// Blog JavaScript
document.addEventListener("DOMContentLoaded", function () {
	markCurrentNavigationLink();
	makeWideTablesScrollable();
	markExternalLinks();
});

// Mark the navigation link for the current page (or the blog section) for
// sighted users (.active) and screen readers (aria-current).
function markCurrentNavigationLink() {
	const currentPath = window.location.pathname;
	document.querySelectorAll("nav a").forEach((link) => {
		const linkUrl = link.getAttribute("href");
		if (linkUrl === currentPath) {
			link.classList.add("active");
			link.setAttribute("aria-current", "page");
		} else if (linkUrl === "/blog/" && currentPath.startsWith("/blog/")) {
			link.classList.add("active");
			link.setAttribute("aria-current", "true");
		}
	});
}

// Wrap post tables so wide ones scroll sideways instead of overflowing. The
// wrapper is focusable and named so keyboard users can scroll it too.
function makeWideTablesScrollable() {
	document.querySelectorAll(".post-content table").forEach((table, index) => {
		const wrapper = document.createElement("div");
		wrapper.className = "table-responsive";
		wrapper.setAttribute("role", "region");
		wrapper.setAttribute("tabindex", "0");
		const caption = table.querySelector("caption");
		wrapper.setAttribute(
			"aria-label",
			caption ? caption.textContent.trim() : `Table ${index + 1}`,
		);
		table.parentNode.insertBefore(wrapper, table);
		wrapper.appendChild(table);
	});
}

// Open off-site links in a new tab, and say so: the arrow is decorative and
// the "(opens in a new tab)" text is for screen readers.
function markExternalLinks() {
	document.querySelectorAll(".post-content a").forEach((link) => {
		const href = link.getAttribute("href");
		if (!href || !href.startsWith("http") || href.includes(window.location.hostname)) {
			return;
		}
		link.setAttribute("target", "_blank");
		link.setAttribute("rel", "noopener noreferrer");
		if (link.querySelector(".external-link-icon")) {
			return;
		}
		const icon = document.createElement("span");
		icon.className = "external-link-icon";
		icon.setAttribute("aria-hidden", "true");
		icon.textContent = " ↗";
		const notice = document.createElement("span");
		notice.className = "visually-hidden";
		notice.textContent = " (opens in a new tab)";
		link.append(icon, notice);
	});
}
