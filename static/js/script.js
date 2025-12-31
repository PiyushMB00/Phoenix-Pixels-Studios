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

// AI Chatbot Logic
const chatbotToggle = document.getElementById("chatbotToggle");
const chatbotWindow = document.getElementById("chatbotWindow");
const closeChat = document.getElementById("closeChat");
const chatbotInput = document.getElementById("chatbotInput");
const sendChat = document.getElementById("sendChat");
const chatbotMessages = document.getElementById("chatbotMessages");

chatbotToggle.addEventListener("click", () => {
  chatbotWindow.classList.toggle("active");
  if (chatbotWindow.classList.contains("active")) {
    chatbotInput.focus();
    
    // Proactive strategic message
    if (window.chatbotProactiveFlag && !window.hasSentProactiveMsg) {
        handleSendMessage(false, true); // proactive flag
        window.hasSentProactiveMsg = true;
    }
    // High intent greeting
    else if (window.chatbotIntentFlag && !window.hasSentIntentMsg) {
        handleSendMessage(true);
        window.hasSentIntentMsg = true;
    }
  }
});

closeChat.addEventListener("click", () => {
  chatbotWindow.classList.remove("active");
});

function appendChatMessage(sender, text) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${sender}`;
  messageDiv.textContent = text;
  chatbotMessages.appendChild(messageDiv);
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
  return messageDiv;
}

async function handleSendMessage(intentAware = false, proactive = false) {
  const message = (intentAware || proactive) ? "" : chatbotInput.value.trim();
  if (!message && !intentAware && !proactive) return;

  if (!intentAware && !proactive) appendChatMessage("user", message);
  chatbotInput.value = "";

  // Show Typing indicator
  const typingIndicator = appendChatMessage("bot", "...");
  typingIndicator.classList.add("typing");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
          message: message,
          intent_aware: intentAware,
          proactive: proactive
      }),
    });

    const data = await response.json();

    // Remove typing indicator and show response
    typingIndicator.remove();
    appendChatMessage("bot", data.response);
  } catch (error) {
    console.error("Chat error:", error);
    typingIndicator.remove();
    appendChatMessage(
      "bot",
      "Sorry, I'm having trouble connecting right now. Please try again later!"
    );
  }
}

sendChat.addEventListener("click", handleSendMessage);
chatbotInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") handleSendMessage();
});
// ELITE FEATURES & EASTER EGGS
document.addEventListener("DOMContentLoaded", () => {
    // 1. Hidden Engineering Proof Panel (3-click logo)
    const logo = document.querySelector(".nav-logo img");
    const panel = document.getElementById("engineeringPanel");
    const closePanel = document.getElementById("closePanel");
    let logoClicks = 0;

    if (logo && panel) {
        logo.addEventListener("click", (e) => {
            e.preventDefault();
            logoClicks++;
            if (logoClicks === 3) {
                panel.classList.add("active");
                logoClicks = 0;
            }
            setTimeout(() => { if (logoClicks > 0) logoClicks = 0; }, 2000);
        });
    }

    if (closePanel) {
        closePanel.addEventListener("click", () => panel.classList.remove("active"));
    }

    // 2. Pricing Justification (Hover tooltip)
    const pricingCards = document.querySelectorAll(".pricing .card");
    pricingCards.forEach(card => {
        let hoverTimer;
        card.addEventListener("mouseenter", () => {
            hoverTimer = setTimeout(() => {
                const tooltip = document.createElement("div");
                tooltip.className = "pricing-tooltip";
                tooltip.textContent = "This price reflects real engineering time, not templates.";
                card.appendChild(tooltip);
                
                // Position tooltip
                tooltip.style.bottom = "20px";
                tooltip.style.left = "50%";
                tooltip.style.transform = "translateX(-50%)";
            }, 4000);
        });
        card.addEventListener("mouseleave", () => {
            clearTimeout(hoverTimer);
            const tooltip = card.querySelector(".pricing-tooltip");
            if (tooltip) tooltip.remove();
        });
    });

    // 3. Hidden Badges (Quality & Master Explorer)
    let sessionActivity = { services: false, projects: false, pricing: false }; // In-memory only (resets on refresh)
    
    const trackActivity = () => {
        const path = window.location.hash || window.location.pathname;
        let pages = JSON.parse(localStorage.getItem("phoenix_pages") || "{}");
        
        // Track sections (In-memory for Readiness Badge)
        if (path.includes("what-we-do")) sessionActivity.services = true;
        if (path.includes("projects")) sessionActivity.projects = true;
        if (path.includes("pricing")) sessionActivity.pricing = true;

        // Track pages (Persistent for Master Explorer)
        const cleanPath = window.location.pathname;
        if (cleanPath === "/") pages.home = true;
        if (cleanPath.includes("about")) pages.about = true;
        if (cleanPath.includes("contact")) pages.contact = true;
        if (cleanPath.includes("origin")) pages.origin = true;
        if (cleanPath.includes("web-development")) pages.web = true;
        
        localStorage.setItem("phoenix_pages", JSON.stringify(pages));
        
        // Show Readiness badge (Session based)
        if (sessionActivity.services && sessionActivity.projects && sessionActivity.pricing) {
            const badge = document.getElementById("qualityBadge");
            if (badge) badge.style.display = "block";
        }

        // Show Master Explorer badge (Persistent)
        const requiredPages = ["home", "about", "contact", "origin", "web"];
        const allVisited = requiredPages.every(p => pages[p]);
        if (allVisited) {
            const explorerBadge = document.getElementById("explorerBadge");
            if (explorerBadge) explorerBadge.style.display = "block";
        }
    };
    window.addEventListener("scroll", trackActivity);
    trackActivity();

    // 4. Returning Builder Greeting
    const heroSub = document.getElementById("heroSubheading");
    if (heroSub) {
        const lastVisit = localStorage.getItem("phoenix_last_visit");
        const now = Date.now();
        if (lastVisit && (now - lastVisit < 24 * 60 * 60 * 1000)) {
            heroSub.textContent = "Good to see you again.";
        }
        localStorage.setItem("phoenix_last_visit", now);
    }

    // 5. Micro-Scroll Detail (Hero Subheading)
    window.addEventListener("scroll", () => {
        if (window.scrollY < 200 && heroSub) {
            const factor = 1 - (window.scrollY / 200);
            heroSub.style.letterSpacing = `${(1 - factor) * 1}px`;
            heroSub.style.fontWeight = 400 + (factor * 200);
            heroSub.style.filter = `contrast(${100 + (factor * 20)}%)`;
        }
    });

    // 6. Strategic Chatbot Message (Bottom then Hero)
    let hasReachedBottom = false;
    let chatbotProactiveTriggered = false;
    window.addEventListener("scroll", () => {
        if (chatbotProactiveTriggered) return;
        
        const scrollPos = window.innerHeight + window.scrollY;
        const bottom = document.documentElement.scrollHeight;
        
        if (scrollPos >= bottom - 50) {
            hasReachedBottom = true;
        }
        
        if (hasReachedBottom && window.scrollY < 100) {
            chatbotProactiveTriggered = true;
            window.chatbotProactiveFlag = true;
        }
    });

    // 7. The Unfinished Line (11:11)
    const checkUnfinishedLine = () => {
        const now = new Date();
        const line = document.getElementById("unfinishedLine");
        if (line) {
            if (now.getHours() % 12 === 11 && now.getMinutes() === 11) {
                line.style.display = "block";
            } else {
                line.style.display = "none";
            }
        }
    };
    setInterval(checkUnfinishedLine, 1000);
    checkUnfinishedLine();

    // 8. Hidden Sentence Across Site (Reveal logic)
    // Only reveal all fragments if user clicks a hidden trigger or after certain interaction
    // For now, they remain hidden in DOM as "insider" detail for someone viewing source
    // or we can implement a subtle reveal later if requested.
});
