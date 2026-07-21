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
const link5 = document.getElementById("link5");
const link6 = document.getElementById("link6");
const link3 = document.getElementById("link3");

link0.addEventListener("click", () => {
  window.scrollTo({ top: 0, behavior: "smooth" });
  closeMenu();
});

if (link1) {
  link1.addEventListener("click", () => {
    scrollToElement("#what-we-do");
    closeMenu();
  });
}

if (link2) {
  link2.addEventListener("click", () => {
    scrollToElement("#projects");
    closeMenu();
  });
}

if (link5) {
  link5.addEventListener("click", () => {
    scrollToElement("#college-projects");
    closeMenu();
  });
}

if (link6) {
  link6.addEventListener("click", () => {
    scrollToElement("#workshops");
    closeMenu();
  });
}

if (link3) {
  link3.addEventListener("click", () => {
    scrollToElement("#pricing");
    closeMenu();
  });
}

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

// ===== TOAST NOTIFICATION SYSTEM =====
(function () {
  let toastContainer = null;

  function getContainer() {
    if (!toastContainer) {
      toastContainer = document.createElement("div");
      toastContainer.id = "toast-container";
      document.body.appendChild(toastContainer);
    }
    return toastContainer;
  }

  window.showToast = function (message, type = "success", duration = 5000) {
    const container = getContainer();
    const isSuccess = type === "success";

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon">
        <i class="fa-solid ${isSuccess ? "fa-circle-check" : "fa-circle-xmark"}"></i>
      </div>
      <div class="toast-body">
        <div class="toast-title">${isSuccess ? "Message Sent!" : "Oops!"}</div>
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" aria-label="Close">
        <i class="fa-solid fa-xmark"></i>
      </button>
      <div class="toast-progress" style="animation-duration: ${duration}ms;"></div>
    `;

    function dismiss() {
      toast.classList.add("toast-exit");
      toast.addEventListener("animationend", () => toast.remove(), { once: true });
    }

    toast.querySelector(".toast-close").addEventListener("click", dismiss);
    container.appendChild(toast);
    setTimeout(dismiss, duration);
  };
})();

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

      // Get form values
      const name = document.getElementById("name").value.trim();
      const email = document.getElementById("email").value.trim();
      const phone = document.getElementById("phone").value.trim();
      const service = document.getElementById("service").value;
      const message = document.getElementById("message").value.trim();

      // Basic validation
      if (!name || !email || !message) {
        showToast("Please fill in all required fields (Name, Email, and Message)", "error");
        return;
      }

      // Email validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        showToast("Please enter a valid email address.", "error");
        return;
      }

      // Loading State
      submitBtn.disabled = true;
      submitBtn.classList.add("loading");
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending...';

      // Send data to backend
      fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, phone, subject: service, message }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            showToast(
              "Thank you! Your message has been sent. We'll connect with you shortly.",
              "success"
            );
            contactForm.reset();
            submitBtn.innerHTML = '<i class="fa-solid fa-check"></i> Sent!';
            setTimeout(resetButton, 3000);
          } else {
            showToast(data.message || "Something went wrong. Please try again.", "error");
            resetButton();
          }
        })
        .catch((error) => {
          console.error("Error:", error);
          showToast("Network error. Please check your connection and try again.", "error");
          resetButton();
        });

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
        let pages = JSON.parse(sessionStorage.getItem("phoenix_pages") || "{}");
        
        // Track sections (In-memory for Readiness Badge)
        if (path.includes("what-we-do")) sessionActivity.services = true;
        if (path.includes("projects")) sessionActivity.projects = true;
        if (path.includes("pricing")) sessionActivity.pricing = true;

        // Track pages (Session-based for Master Explorer)
        const cleanPath = window.location.pathname;
        // Use more robust checks for path
        if (cleanPath === "/" || cleanPath === "/index.html") pages.home = true;
        if (cleanPath.includes("/about")) pages.about = true;
        if (cleanPath.includes("/contact")) pages.contact = true;
        if (cleanPath.includes("/origin")) pages.origin = true;
        if (cleanPath.includes("/web-development")) pages.web = true;
        
        sessionStorage.setItem("phoenix_pages", JSON.stringify(pages));
        
        // Show Readiness badge (Session based - resets on refresh)
        if (sessionActivity.services && sessionActivity.projects && sessionActivity.pricing) {
            const badge = document.getElementById("qualityBadge");
            if (badge) badge.style.display = "block";
        }

        // Show Master Explorer badge (Session based - resets on close)
        const requiredPages = ["home", "about", "contact", "origin", "web"];
        // Check if all required pages are true
        const allVisited = requiredPages.every(p => pages[p] === true);
        
        if (allVisited) {
            const explorerBadge = document.getElementById("explorerBadge");
            if (explorerBadge) {
                explorerBadge.style.display = "block";
                // Ensure it stacks properly
                explorerBadge.style.marginBottom = "10px";
            }
        }
    };
    window.addEventListener("scroll", trackActivity);
    // Explicitly call once on load to show persistent badges if any (Master Explorer in session)
    trackActivity();

    // 4. Returning Builder Greeting (One-time per session)
    const heroSub = document.getElementById("heroSubheading");
    if (heroSub) {
        const lastVisit = localStorage.getItem("phoenix_last_visit");
        const greetingShown = sessionStorage.getItem("phoenix_greeting_shown");
        const now = Date.now();
        
        // Logic: Return < 24h AND Not shown in this session yet
        if (lastVisit && (now - lastVisit < 24 * 60 * 60 * 1000) && !greetingShown) {
            heroSub.textContent = "Good to see you again.";
            // Mark as shown for this session so it doesn't appear on refresh
            sessionStorage.setItem("phoenix_greeting_shown", "true");
        }
        
        // Update last visit for next time
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

    // 9. PPS Workshops Slider Interactivity
    const initWorkshopsSlider = () => {
        const track = document.querySelector(".workshops-slider-track");
        const prevBtn = document.querySelector(".slider-btn.prev");
        const nextBtn = document.querySelector(".slider-btn.next");
        const dotsContainer = document.querySelector(".slider-dots");
        
        if (!track) return;
        
        const slides = Array.from(track.children);
        if (slides.length === 0) return;
        
        let currentIndex = 0;
        let slideWidth = 0;
        let gap = 24; // 1.5rem default gap
        
        // Calculate items per view dynamically based on CSS
        const getItemsPerView = () => {
            const width = window.innerWidth;
            if (width <= 768) return 1;
            if (width <= 992) return 2;
            return 3;
        };

        const maxIndex = () => {
            const itemsPerView = getItemsPerView();
            return Math.max(0, slides.length - itemsPerView);
        };
        
        const updateSliderPosition = () => {
            if (!slides[0]) return;
            slideWidth = slides[0].getBoundingClientRect().width;
            
            // Get computed style for gap to ensure accuracy
            const computedStyle = window.getComputedStyle(track);
            const computedGap = parseFloat(computedStyle.gap) || gap;
            
            // Limit index within bounds
            const limitIndex = Math.min(currentIndex, maxIndex());
            currentIndex = limitIndex;
            
            const offset = currentIndex * (slideWidth + computedGap);
            track.style.transform = `translateX(-${offset}px)`;
            
            // Update active dot
            const dots = dotsContainer.querySelectorAll(".dot");
            dots.forEach((dot, index) => {
                if (index === currentIndex) {
                    dot.classList.add("active");
                } else {
                    dot.classList.remove("active");
                }
            });

            // Toggle arrow visibility or opacity
            if (prevBtn) {
                if (currentIndex === 0) {
                    prevBtn.style.opacity = "0.3";
                    prevBtn.style.pointerEvents = "none";
                } else {
                    prevBtn.style.opacity = "1";
                    prevBtn.style.pointerEvents = "all";
                }
            }

            if (nextBtn) {
                if (currentIndex >= maxIndex()) {
                    nextBtn.style.opacity = "0.3";
                    nextBtn.style.pointerEvents = "none";
                } else {
                    nextBtn.style.opacity = "1";
                    nextBtn.style.pointerEvents = "all";
                }
            }
        };
        
        // Create Navigation Dots
        const createDots = () => {
            dotsContainer.innerHTML = "";
            const totalDots = maxIndex() + 1;
            
            for (let i = 0; i < totalDots; i++) {
                const dot = document.createElement("div");
                dot.classList.add("dot");
                if (i === currentIndex) dot.classList.add("active");
                dot.addEventListener("click", () => {
                    currentIndex = i;
                    updateSliderPosition();
                    resetAutoPlay();
                });
                dotsContainer.appendChild(dot);
            }
        };
        
        // Next button click
        if (nextBtn) {
            nextBtn.addEventListener("click", () => {
                if (currentIndex < maxIndex()) {
                    currentIndex++;
                    updateSliderPosition();
                }
                resetAutoPlay();
            });
        }
        
        // Prev button click
        if (prevBtn) {
            prevBtn.addEventListener("click", () => {
                if (currentIndex > 0) {
                    currentIndex--;
                    updateSliderPosition();
                }
                resetAutoPlay();
            });
        }
        
        // Responsive listener
        window.addEventListener("resize", () => {
            // Re-create dots and recalculate position as items per view might change
            createDots();
            updateSliderPosition();
        });
        
        // Swipe/touch support
        let startX = 0;
        let isDragging = false;
        
        track.addEventListener("touchstart", (e) => {
            startX = e.touches[0].clientX;
            isDragging = true;
        }, { passive: true });
        
        track.addEventListener("touchend", (e) => {
            if (!isDragging) return;
            const diffX = startX - e.changedTouches[0].clientX;
            
            if (Math.abs(diffX) > 50) { // threshold of 50px
                if (diffX > 0 && currentIndex < maxIndex()) {
                    // Swiped left, show next
                    currentIndex++;
                } else if (diffX < 0 && currentIndex > 0) {
                    // Swiped right, show prev
                    currentIndex--;
                }
                updateSliderPosition();
                resetAutoPlay();
            }
            isDragging = false;
        }, { passive: true });
        
        // Auto Play
        let autoPlayInterval;
        const startAutoPlay = () => {
            autoPlayInterval = setInterval(() => {
                const limit = maxIndex();
                if (currentIndex < limit) {
                    currentIndex++;
                } else {
                    currentIndex = 0;
                }
                updateSliderPosition();
            }, 5000); // Auto scroll every 5s
        };
        
        const resetAutoPlay = () => {
            clearInterval(autoPlayInterval);
            startAutoPlay();
        };
        
        // Pause Auto Play on Hover
        track.addEventListener("mouseenter", () => clearInterval(autoPlayInterval));
        track.addEventListener("mouseleave", startAutoPlay);
        
        // Initial setup
        createDots();
        // Wait slightly for layouts/images to stabilize
        setTimeout(updateSliderPosition, 150);
        startAutoPlay();
    };
    
    initWorkshopsSlider();
});
