/**
 * Solar Template - Minimal JavaScript
 * The only script: a dark/light theme toggle. A saved theme is applied by an
 * inline script in base.html before first paint; with none saved, the page
 * follows the visitor's system setting (prefers-color-scheme).
 */

document.addEventListener("DOMContentLoaded", function () {
	const themeToggle = document.querySelector(".theme-toggle");
	if (!themeToggle) return;

	showTheme(themeToggle, currentTheme());
	themeToggle.addEventListener("click", function () {
		const newTheme = currentTheme() === "dark" ? "light" : "dark";
		document.documentElement.setAttribute("data-theme", newTheme);
		showTheme(themeToggle, newTheme);
		try {
			localStorage.setItem("solarTheme", newTheme);
		} catch (e) {
			// Storage can be unavailable (private windows); the toggle still works for this page.
		}
	});
	// Until the visitor picks a theme, follow system changes too.
	window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", function () {
		showTheme(themeToggle, currentTheme());
	});
});

/** The saved theme, or the system's when none is saved. */
function currentTheme() {
	const saved = document.documentElement.getAttribute("data-theme");
	if (saved) return saved;
	return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/**
 * The button is named "Dark mode" and pressed in the dark theme; its icon
 * shows the theme a click switches to.
 */
function showTheme(button, theme) {
	button.setAttribute("aria-pressed", String(theme === "dark"));
	const icon = button.querySelector(".theme-toggle-icon");
	if (icon) icon.textContent = theme === "dark" ? "☀️" : "🌙";
}
