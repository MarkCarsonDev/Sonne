/**
 * Solar Template - Minimal JavaScript
 * The only script: a dark/light theme toggle. The saved theme itself is
 * applied by an inline script in base.html before first paint.
 */

document.addEventListener("DOMContentLoaded", function () {
	const themeToggle = document.querySelector(".theme-toggle");
	if (!themeToggle) return;

	showThemeIcon(themeToggle, currentTheme());
	themeToggle.addEventListener("click", function () {
		const newTheme = currentTheme() === "dark" ? "light" : "dark";
		document.documentElement.setAttribute("data-theme", newTheme);
		showThemeIcon(themeToggle, newTheme);
		try {
			localStorage.setItem("solarTheme", newTheme);
		} catch (e) {
			// Storage can be unavailable (private windows); the toggle still works for this page.
		}
	});
});

function currentTheme() {
	return document.documentElement.getAttribute("data-theme");
}

/** The icon shows the theme a click switches to. */
function showThemeIcon(button, theme) {
	button.textContent = theme === "dark" ? "☀️" : "🌙";
}
