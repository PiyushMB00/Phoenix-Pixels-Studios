function scrollToElement(elementSelector, instance = 0) {
  //Select all elements that match the given selector
  const elements = document.querySelectorAll(elementSelector);
  //Check if there are elements matching the selector and if the requested instance exists
  if (elements.length > instance) {
    const navHeight = document.querySelector("nav").offsetHeight;
    const elementPosition =
      elements[instance].getBoundingClientRect().top + window.pageYOffset;
    const offsetPosition = elementPosition - navHeight - 210; // Perfect offset - hides button, shows heading

    window.scrollTo({
      top: offsetPosition,
      behavior: "smooth",
    });
  }
}

const link0 = document.getElementById("link0");
const link1 = document.getElementById("link1");
const link2 = document.getElementById("link2");
const link3 = document.getElementById("link3");

link0.addEventListener("click", () => {
  window.scrollTo({ top: 0, behavior: "smooth" });
  closeMenu();
});

link1.addEventListener("click", () => {
  scrollToElement(".header");
  closeMenu();
});

link2.addEventListener("click", () => {
  scrollToElement(".header", 1);
  closeMenu();
});

link3.addEventListener("click", () => {
  scrollToElement(".column");
  closeMenu();
});

// Sticky navigation scroll effect
const nav = document.querySelector("nav");

window.addEventListener("scroll", () => {
  if (window.scrollY > 50) {
    nav.classList.add("scrolled");
  } else {
    nav.classList.remove("scrolled");
  }
});

// Mobile menu toggle
const menuToggle = document.getElementById("menuToggle");
const navLink = document.querySelector(".nav-link");

menuToggle.addEventListener("click", () => {
  menuToggle.classList.toggle("active");
  navLink.classList.toggle("active");
});

// Close menu function
function closeMenu() {
  menuToggle.classList.remove("active");
  navLink.classList.remove("active");
}

// Close menu when clicking outside
document.addEventListener("click", (e) => {
  if (!nav.contains(e.target)) {
    closeMenu();
  }
});

// Contact Form Handling
document.addEventListener("DOMContentLoaded", function () {
  const contactForm = document.getElementById("contactForm");

  if (contactForm) {
    // Pre-select service based on URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const serviceParam = urlParams.get("service");
    if (serviceParam) {
      const serviceSelect = document.getElementById("service");
      if (serviceSelect) {
        serviceSelect.value = serviceParam;
      }
    }

    contactForm.addEventListener("submit", function (e) {
      e.preventDefault();

      const submitBtn = contactForm.querySelector('button[type="submit"]');
      const originalBtnText = submitBtn.innerText;
      let messageDiv = contactForm.querySelector(".form-message");

      // Create message div if it doesn't exist
      if (!messageDiv) {
        messageDiv = document.createElement("div");
        messageDiv.className = "form-message";
        contactForm.appendChild(messageDiv);
      }

      // Reset message
      messageDiv.style.display = "none";
      messageDiv.className = "form-message";

      // Get form values
      const name = document.getElementById("name").value.trim();
      const email = document.getElementById("email").value.trim();
      const phone = document.getElementById("phone").value.trim();
      const service = document.getElementById("service").value;
      const message = document.getElementById("message").value.trim();

      // Basic validation
      if (!name || !email || !message) {
        showMessage(
          "Please fill in all required fields (Name, Email, and Message)",
          "error"
        );
        return;
      }

      // Email validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        showMessage("Please enter a valid email address", "error");
        return;
      }

      // Loading State
      submitBtn.disabled = true;
      submitBtn.classList.add("loading");
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner"></i> Sending...';

      // Send data to backend
      fetch("/api/contact", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name,
          email: email,
          phone: phone,
          subject: service,
          message: message,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            showMessage(
              "Thank you! Your message has been sent successfully. We will connect with you shortly.",
              "success"
            );
            contactForm.reset();
            submitBtn.innerHTML = "Sent!";

            setTimeout(() => {
              resetButton();
            }, 3000);
          } else {
            showMessage("Error: " + data.message, "error");
            resetButton();
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          showMessage(
            "An error occurred while sending. Please try again.",
            "error"
          );
          resetButton();
        });

      function showMessage(text, type) {
        messageDiv.textContent = text;
        messageDiv.classList.add(type);
        messageDiv.style.display = "block";
      }

      function resetButton() {
        submitBtn.disabled = false;
        submitBtn.classList.remove("loading");
        submitBtn.innerText = originalBtnText;
      }
    });
  }
});

//Backend Integration//

//   const form = document.getElementById('contactForm');
//   const popup = document.getElementById('popup');

//   function showPopup(message, type) {
//     popup.textContent = message;
//     popup.className = `popup ${type}`;
//     popup.style.display = 'block';
//     setTimeout(() => popup.style.display = 'none', 4000);
//   }

//   form.addEventListener('submit', async (e) => {
//     e.preventDefault();

//     const formData = new FormData(form);
//     const payload = Object.fromEntries(formData.entries());

//     try {
//       // ✅ Use relative path so it matches the same origin
//       const res = await fetch('/api/contact', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify(payload)
//       });

//       const result = await res.json();

//       if (result.status === 'success') {
//         showPopup(result.message, 'success');
//         form.reset();
//       } else {
//         showPopup(result.message, 'error');
//       }
//     } catch (err) {
//       console.error(err);
//       showPopup('Network error. Please try again.', 'error');
//     }
//   });
