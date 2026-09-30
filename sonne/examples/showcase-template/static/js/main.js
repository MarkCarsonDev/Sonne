// Showcase JavaScript
const DARK_MODE_KEY = "sonne-showcase-dark-mode";

// Apply the saved (or system) colour scheme as early as possible.
setDarkMode(savedDarkMode() ?? window.matchMedia("(prefers-color-scheme: dark)").matches);

document.addEventListener("DOMContentLoaded", function () {
	setUpDarkModeToggle();
});

// The toggle is a real button: its pressed state says whether dark mode is on,
// and the choice is remembered for the next visit.
function setUpDarkModeToggle() {
	const toggle = document.querySelector(".dark-mode-toggle");
	if (!toggle) {
		return;
	}
	toggle.setAttribute("aria-pressed", String(document.body.classList.contains("dark-mode")));
	toggle.addEventListener("click", () => {
		const dark = toggle.getAttribute("aria-pressed") !== "true";
		setDarkMode(dark);
		toggle.setAttribute("aria-pressed", String(dark));
		try {
			localStorage.setItem(DARK_MODE_KEY, dark ? "on" : "off");
		} catch (error) {
			// Storage can be unavailable (private mode); the toggle still works.
		}
	});
}

function setDarkMode(dark) {
	const apply = () => document.body.classList.toggle("dark-mode", dark);
	if (document.body) {
		apply();
	} else {
		document.addEventListener("DOMContentLoaded", apply);
	}
}

function savedDarkMode() {
	try {
		const saved = localStorage.getItem(DARK_MODE_KEY);
		return saved === null ? null : saved === "on";
	} catch (error) {
		return null;
	}
}
