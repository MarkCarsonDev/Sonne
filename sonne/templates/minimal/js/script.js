document.addEventListener("DOMContentLoaded", function () {
	// On load, read the saved theme from cookie (default to "light" if none exists)
	const savedTheme = getCookie("theme") || "light";
	document.documentElement.setAttribute("data-theme", savedTheme);
	updateThemeIcon(savedTheme);

	initializeLightDarkSwitch();
	initializeKeypressNavigator();
});

function initializeLightDarkSwitch() {
	const themeToggle = document.getElementsByClassName("theme-switch")[0];
	if (!themeToggle) return;

	let isThrottled = false; // Flag for debounce

	themeToggle.addEventListener("click", function () {
		// Prevent toggling too rapidly
		if (isThrottled) return;

		// Set the flag and apply the animation
		isThrottled = true;
		themeToggle.classList.add("debounce-active");

		// Remove the animation and reset the flag after 500ms
		setTimeout(() => {
			isThrottled = false;
			themeToggle.classList.remove("debounce-active");
		}, 500);

		// Toggle the theme and update cookie
		updateLightDark();
	});
}

function updateLightDark() {
	const sunSvg = `
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="5" stroke="var(--icon-color)" stroke-width="1.5"></circle>
        <path d="M12 2V4" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M12 20V22" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M4 12L2 12" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M22 12L20 12" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M19.7778 4.22266L17.5558 6.25424" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M4.22217 4.22266L6.44418 6.25424" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M6.44434 17.5557L4.22211 19.7779" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M19.7778 19.7773L17.5558 17.5551" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
      </svg>`;

	const moonSvg = `
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" clip-rule="evenodd" d="M11.203 6.02337C7.59276 6.99074 5.45107 10.6948 6.41557 14.2943C7.38006 17.8938 11.0868 20.0307 14.6971 19.0634C16.1096 18.6849 17.2975 17.8877 18.1626 16.8409C15.1968 17.3646 12.2709 15.546 11.4775 12.585C10.7644 9.92365 12.0047 7.20008 14.3182 5.92871C13.3186 5.72294 12.2569 5.74098 11.203 6.02337ZM4.96668 14.6825C3.78704 10.2801 6.40707 5.75553 10.8148 4.57448C12.968 3.99752 15.1519 4.3254 16.9581 5.32413L16.6781 6.72587C16.4602 6.75011 16.241 6.79108 16.0218 6.8498C13.6871 7.47537 12.303 9.8703 12.9264 12.1968C13.5497 14.5233 15.9459 15.9053 18.2806 15.2797C18.7257 15.1604 19.1351 14.9774 19.5024 14.7435L20.5991 15.6609C19.6542 17.9633 17.6796 19.8171 15.0853 20.5123C10.6776 21.6933 6.14631 19.085 4.96668 14.6825Z" fill="var(--icon-color)">
        </path>
      </svg>`;

	const themeIcon = document.getElementById("theme-icon");
	if (!themeIcon) return;

	const currentTheme = document.documentElement.getAttribute("data-theme");
	let newTheme;

	if (currentTheme === "light") {
		newTheme = "dark";
		themeIcon.innerHTML = moonSvg;
	} else {
		newTheme = "light";
		themeIcon.innerHTML = sunSvg;
	}

	document.documentElement.setAttribute("data-theme", newTheme);
	// Update the cookie so that the preference persists for 7 days
	setCookie("theme", newTheme, 7);
}

function updateThemeIcon(theme) {
	// This function updates the theme icon without toggling the theme.
	const themeIcon = document.getElementById("theme-icon");
	if (!themeIcon) return;

	const sunSvg = `
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="5" stroke="var(--icon-color)" stroke-width="1.5"></circle>
        <path d="M12 2V4" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M12 20V22" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M4 12L2 12" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M22 12L20 12" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M19.7778 4.22266L17.5558 6.25424" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M4.22217 4.22266L6.44418 6.25424" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M6.44434 17.5557L4.22211 19.7779" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
        <path d="M19.7778 19.7773L17.5558 17.5551" stroke="var(--icon-color)" stroke-width="1.5" stroke-linecap="round"></path>
      </svg>`;
	const moonSvg = `
      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" clip-rule="evenodd" d="M11.203 6.02337C7.59276 6.99074 5.45107 10.6948 6.41557 14.2943C7.38006 17.8938 11.0868 20.0307 14.6971 19.0634C16.1096 18.6849 17.2975 17.8877 18.1626 16.8409C15.1968 17.3646 12.2709 15.546 11.4775 12.585C10.7644 9.92365 12.0047 7.20008 14.3182 5.92871C13.3186 5.72294 12.2569 5.74098 11.203 6.02337ZM4.96668 14.6825C3.78704 10.2801 6.40707 5.75553 10.8148 4.57448C12.968 3.99752 15.1519 4.3254 16.9581 5.32413L16.6781 6.72587C16.4602 6.75011 16.241 6.79108 16.0218 6.8498C13.6871 7.47537 12.303 9.8703 12.9264 12.1968C13.5497 14.5233 15.9459 15.9053 18.2806 15.2797C18.7257 15.1604 19.1351 14.9774 19.5024 14.7435L20.5991 15.6609C19.6542 17.9633 17.6796 19.8171 15.0853 20.5123C10.6776 21.6933 6.14631 19.085 4.96668 14.6825Z" fill="var(--icon-color)">
        </path>
      </svg>`;

	if (theme === "light") {
		themeIcon.innerHTML = sunSvg;
	} else {
		themeIcon.innerHTML = moonSvg;
	}
}

function initializeKeypressNavigator() {
	// Find all elements with the class 'keypress'
	const keypressElements = document.querySelectorAll(".keypress");

	keypressElements.forEach(function (item) {
		const id = item.id.toLowerCase();

		// Check if the ID starts with 'kp'
		if (id && id.startsWith("kp")) {
			// Remove 'kp' prefix and set the rest as the element's content
			let keyChar = id.slice(2);

			// Create an element with class "keypress_icon"
			const span = document.createElement("span");
			span.className = "keycap";

			// Special case for arrow keys: if the keyChar matches "arrowleft" or "arrowright", set the symbol
			if (keyChar === "arrowleft") {
				span.textContent = "←";
				keyChar = "arrowleft";
			} else if (keyChar === "arrowright") {
				span.textContent = "→";
				keyChar = "arrowright";
			} else if (keyChar === "arrowup") {
				span.textContent = "↑";
				keyChar = "arrowup";
			} else if (keyChar === "arrowdown") {
				span.textContent = "↓";
				keyChar = "arrowdown";
			} else {
				// Default behavior for other keys: display the key character as uppercase
				span.textContent = keyChar.toUpperCase();
			}

			item.appendChild(span);

			// Listen for keydown events
			document.addEventListener("keydown", function (event) {
				// Convert the event key to lowercase for comparison.
				const eventKey = event.key.toLowerCase();
				// For arrow keys, event.key will be "ArrowLeft", "ArrowRight", etc.
				if (
					eventKey === keyChar ||
					(keyChar === "arrowleft" && eventKey === "arrowleft") ||
					(keyChar === "arrowright" && eventKey === "arrowright") ||
					(keyChar === "arrowup" && eventKey === "arrowup") ||
					(keyChar === "arrowdown" && eventKey === "arrowdown")
				) {
					const keycap = item.querySelector(".keycap");
					if (keycap) keycap.classList.add("depressed");
					item.click();
				}
			});

			// Listen for keyup events
			document.addEventListener("keyup", function (event) {
				const eventKey = event.key.toLowerCase();
				if (
					eventKey === keyChar ||
					(keyChar === "arrowleft" && eventKey === "arrowleft") ||
					(keyChar === "arrowright" && eventKey === "arrowright") ||
					(keyChar === "arrowup" && eventKey === "arrowup") ||
					(keyChar === "arrowdown" && eventKey === "arrowdown")
				) {
					const keycap = item.querySelector(".keycap");
					if (keycap) keycap.classList.remove("depressed");
				}
			});
		}
	});
}

// Cookie helper functions
function setCookie(name, value, days) {
	let expires = "";
	if (days) {
		let date = new Date();
		date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
		expires = "; expires=" + date.toUTCString();
	}
	document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

function getCookie(name) {
	let nameEQ = name + "=";
	let ca = document.cookie.split(";");
	for (let i = 0; i < ca.length; i++) {
		let c = ca[i];
		while (c.charAt(0) === " ") c = c.substring(1, c.length);
		if (c.indexOf(nameEQ) === 0)
			return c.substring(nameEQ.length, c.length);
	}
	return null;
}

// Image toggle for dithered/original images
function swapImage(imageId, originalSrc, ditheredSrc) {
	const img = document.getElementById(imageId);
	if (!img) return;

	const isOriginal = img.getAttribute("data-original") === "true";

	if (isOriginal) {
		img.src = ditheredSrc;
		img.setAttribute("data-original", "false");
	} else {
		img.src = originalSrc;
		img.setAttribute("data-original", "true");
	}
}
