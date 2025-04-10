// Portfolio JavaScript
document.addEventListener("DOMContentLoaded", function () {
	// Mobile Navigation Toggle
	const menuToggle = document.querySelector(".menu-toggle");
	const siteNav = document.querySelector(".site-nav");

	if (menuToggle && siteNav) {
		menuToggle.addEventListener("click", function () {
			menuToggle.classList.toggle("active");
			siteNav.classList.toggle("active");
			menuToggle.setAttribute(
				"aria-expanded",
				menuToggle.classList.contains("active")
			);
		});
	}

	// Portfolio Filters
	const filterButtons = document.querySelectorAll(".filter-btn");
	const portfolioItems = document.querySelectorAll(".portfolio-item");

	if (filterButtons.length && portfolioItems.length) {
		filterButtons.forEach((button) => {
			button.addEventListener("click", () => {
				// Remove active class from all buttons
				filterButtons.forEach((btn) => btn.classList.remove("active"));

				// Add active class to clicked button
				button.classList.add("active");

				// Get filter value
				const filter = button.getAttribute("data-filter");

				// Filter items
				portfolioItems.forEach((item) => {
					if (
						filter === "all" ||
						item.getAttribute("data-category") === filter
					) {
						item.style.display = "block";
					} else {
						item.style.display = "none";
					}
				});
			});
		});
	}

	// Smooth Scroll
	const scrollLinks = document.querySelectorAll(
		'a[href^="#"]:not([href="#"])'
	);

	scrollLinks.forEach((link) => {
		link.addEventListener("click", function (e) {
			const target = document.querySelector(this.getAttribute("href"));

			if (target) {
				e.preventDefault();
				target.scrollIntoView({
					behavior: "smooth",
				});
			}
		});
	});

	// Project Gallery Lightbox
	const galleryItems = document.querySelectorAll(".gallery-item img");

	if (galleryItems.length) {
		galleryItems.forEach((item) => {
			item.addEventListener("click", function () {
				// Create lightbox
				const lightbox = document.createElement("div");
				lightbox.className = "lightbox";

				// Create image container
				const imgContainer = document.createElement("div");
				imgContainer.className = "lightbox-content";

				// Create image
				const img = document.createElement("img");
				img.src = this.src;

				// Create close button
				const closeBtn = document.createElement("button");
				closeBtn.className = "lightbox-close";
				closeBtn.innerHTML = "&times;";

				// Append elements
				imgContainer.appendChild(img);
				lightbox.appendChild(closeBtn);
				lightbox.appendChild(imgContainer);
				document.body.appendChild(lightbox);

				// Add active class
				setTimeout(() => {
					lightbox.classList.add("active");
				}, 10);

				// Close lightbox
				closeBtn.addEventListener("click", function () {
					lightbox.classList.remove("active");
					setTimeout(() => {
						document.body.removeChild(lightbox);
					}, 300);
				});

				// Close on click outside image
				lightbox.addEventListener("click", function (e) {
					if (e.target === lightbox) {
						closeBtn.click();
					}
				});

				// Close on escape key
				document.addEventListener("keydown", function (e) {
					if (e.key === "Escape") {
						closeBtn.click();
					}
				});
			});
		});
	}

	// Form Validation
	const contactForm = document.querySelector(".contact-form");

	if (contactForm) {
		contactForm.addEventListener("submit", function (e) {
			let isValid = true;

			// Get form fields
			const name = contactForm.querySelector("#name");
			const email = contactForm.querySelector("#email");
			const message = contactForm.querySelector("#message");

			// Validate name
			if (!name.value.trim()) {
				isValid = false;
				showError(name, "Please enter your name");
			} else {
				removeError(name);
			}

			// Validate email
			if (!email.value.trim()) {
				isValid = false;
				showError(email, "Please enter your email");
			} else if (!isValidEmail(email.value)) {
				isValid = false;
				showError(email, "Please enter a valid email");
			} else {
				removeError(email);
			}

			// Validate message
			if (!message.value.trim()) {
				isValid = false;
				showError(message, "Please enter your message");
			} else {
				removeError(message);
			}

			// Prevent form submission if invalid
			if (!isValid) {
				e.preventDefault();
			}
		});
	}

	// Helper function to show error
	function showError(field, message) {
		// Remove existing error
		removeError(field);

		// Add error class
		field.classList.add("error");

		// Create error message
		const error = document.createElement("div");
		error.className = "error-message";
		error.innerText = message;

		// Insert error after field
		field.parentNode.insertBefore(error, field.nextSibling);
	}

	// Helper function to remove error
	function removeError(field) {
		// Remove error class
		field.classList.remove("error");

		// Remove error message
		const error = field.parentNode.querySelector(".error-message");
		if (error) {
			error.parentNode.removeChild(error);
		}
	}

	// Helper function to validate email
	function isValidEmail(email) {
		const re =
			/^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
		return re.test(String(email).toLowerCase());
	}
});
