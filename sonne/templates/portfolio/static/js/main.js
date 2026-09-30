// Portfolio JavaScript
document.addEventListener("DOMContentLoaded", function () {
	setUpMenuToggle();
	setUpPortfolioFilters();
	setUpInPageLinks();
	setUpGalleryLightbox();
	setUpContactFormValidation();
});

const prefersReducedMotion = () =>
	window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Mobile menu: the button reports its state; Escape closes the open menu and
// returns focus to the button.
function setUpMenuToggle() {
	const menuToggle = document.querySelector(".menu-toggle");
	const siteNav = document.querySelector(".site-nav");
	if (!menuToggle || !siteNav) {
		return;
	}
	const setOpen = (open) => {
		menuToggle.classList.toggle("active", open);
		siteNav.classList.toggle("active", open);
		menuToggle.setAttribute("aria-expanded", String(open));
	};
	menuToggle.addEventListener("click", () => {
		setOpen(menuToggle.getAttribute("aria-expanded") !== "true");
	});
	siteNav.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && menuToggle.getAttribute("aria-expanded") === "true") {
			setOpen(false);
			menuToggle.focus();
		}
	});
}

// Category filters: toggle buttons (aria-pressed) that announce how many
// projects are shown.
function setUpPortfolioFilters() {
	const filterButtons = document.querySelectorAll(".filter-btn");
	const portfolioItems = document.querySelectorAll(".portfolio-item");
	const status = document.getElementById("portfolio-status");
	if (!filterButtons.length || !portfolioItems.length) {
		return;
	}
	filterButtons.forEach((button) => {
		button.addEventListener("click", () => {
			filterButtons.forEach((other) => {
				const isChosen = other === button;
				other.classList.toggle("active", isChosen);
				other.setAttribute("aria-pressed", String(isChosen));
			});
			const filter = button.getAttribute("data-filter");
			let shown = 0;
			portfolioItems.forEach((item) => {
				const matches = filter === "all" || item.getAttribute("data-category") === filter;
				item.hidden = !matches;
				shown += matches ? 1 : 0;
			});
			if (status) {
				status.textContent = `Showing ${shown} ${shown === 1 ? "project" : "projects"}`;
			}
		});
	});
}

// In-page links (including the skip link) move keyboard focus to their
// target; they scroll smoothly only when the visitor hasn't asked for
// reduced motion.
function setUpInPageLinks() {
	document.querySelectorAll('a[href^="#"]:not([href="#"])').forEach((link) => {
		link.addEventListener("click", (event) => {
			const target = document.getElementById(link.getAttribute("href").slice(1));
			if (!target) {
				return;
			}
			event.preventDefault();
			if (!target.hasAttribute("tabindex")) {
				target.setAttribute("tabindex", "-1");
			}
			target.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth" });
			target.focus({ preventScroll: true });
			history.pushState(null, "", link.getAttribute("href"));
		});
	});
}

// Gallery lightbox: gallery links open a modal <dialog> (focus stays inside,
// Escape closes it, focus returns to the link). Without JavaScript the links
// simply open the image.
function setUpGalleryLightbox() {
	const galleryLinks = document.querySelectorAll(".gallery-link");
	if (!galleryLinks.length || typeof HTMLDialogElement !== "function") {
		return;
	}
	const dialog = createLightboxDialog();
	const image = dialog.querySelector("img");
	galleryLinks.forEach((link) => {
		link.addEventListener("click", (event) => {
			event.preventDefault();
			const thumbnail = link.querySelector("img");
			image.src = link.getAttribute("href");
			image.alt = thumbnail ? thumbnail.alt : "";
			dialog.returnFocusTo = link;
			dialog.showModal();
		});
	});
}

function createLightboxDialog() {
	const dialog = document.createElement("dialog");
	dialog.className = "lightbox";
	dialog.setAttribute("aria-label", "Image viewer");
	const closeButton = document.createElement("button");
	closeButton.type = "button";
	closeButton.className = "lightbox-close";
	closeButton.setAttribute("aria-label", "Close image viewer");
	closeButton.innerHTML = '<span aria-hidden="true">&times;</span>';
	const content = document.createElement("div");
	content.className = "lightbox-content";
	content.appendChild(document.createElement("img"));
	dialog.append(closeButton, content);
	document.body.appendChild(dialog);

	closeButton.addEventListener("click", () => dialog.close());
	// A click on the backdrop (the dialog itself, not its content) closes it.
	dialog.addEventListener("click", (event) => {
		if (event.target === dialog) {
			dialog.close();
		}
	});
	dialog.addEventListener("close", () => {
		if (dialog.returnFocusTo) {
			dialog.returnFocusTo.focus();
		}
	});
	return dialog;
}

// Contact form: errors are tied to their fields (aria-invalid,
// aria-describedby), announced, and focus moves to the first invalid field.
function setUpContactFormValidation() {
	const contactForm = document.querySelector(".contact-form");
	if (!contactForm) {
		return;
	}
	contactForm.addEventListener("submit", (event) => {
		const checks = [
			[contactForm.querySelector("#name"), (value) => (value ? "" : "Please enter your name")],
			[contactForm.querySelector("#email"), emailError],
			[contactForm.querySelector("#message"), (value) => (value ? "" : "Please enter your message")],
		];
		let firstInvalid = null;
		checks.forEach(([field, validate]) => {
			if (!field) {
				return;
			}
			const message = validate(field.value.trim());
			if (message) {
				showError(field, message);
				firstInvalid = firstInvalid || field;
			} else {
				removeError(field);
			}
		});
		if (firstInvalid) {
			event.preventDefault();
			firstInvalid.focus();
		}
	});
}

function emailError(value) {
	if (!value) {
		return "Please enter your email";
	}
	return isValidEmail(value) ? "" : "Please enter a valid email, like name@example.com";
}

function showError(field, message) {
	removeError(field);
	const error = document.createElement("p");
	error.className = "error-message";
	error.id = `${field.id}-error`;
	error.setAttribute("role", "alert");
	error.textContent = message;
	field.classList.add("error");
	field.setAttribute("aria-invalid", "true");
	field.setAttribute("aria-describedby", error.id);
	field.parentNode.insertBefore(error, field.nextSibling);
}

function removeError(field) {
	field.classList.remove("error");
	field.removeAttribute("aria-invalid");
	field.removeAttribute("aria-describedby");
	const error = document.getElementById(`${field.id}-error`);
	if (error) {
		error.remove();
	}
}

function isValidEmail(email) {
	const re =
		/^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
	return re.test(String(email).toLowerCase());
}
