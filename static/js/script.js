function scrollToElement(elementSelector, instance = 0){
    //Select all elements that match the given selector
    const elements = document.querySelectorAll(elementSelector);
    //Check if there are elements matching the selector and if the requested instance exists
    if(elements.length > instance) {
        const navHeight = document.querySelector('nav').offsetHeight;
        const elementPosition = elements[instance].getBoundingClientRect().top + window.pageYOffset;
        const offsetPosition = elementPosition - navHeight - 210; // Perfect offset - hides button, shows heading
        
        window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
        });
    }
}

const link0 = document.getElementById("link0");
const link1 = document.getElementById("link1");
const link2 = document.getElementById("link2");
const link3 = document.getElementById("link3");

link0.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    closeMenu();
})

link1.addEventListener('click', () => {
    scrollToElement(".header");
    closeMenu();
})

link2.addEventListener('click', () => {
    scrollToElement('.header', 1);
    closeMenu();
})

link3.addEventListener('click', () => {
    scrollToElement('.column');
    closeMenu();
})

// Sticky navigation scroll effect
const nav = document.querySelector('nav');

window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        nav.classList.add('scrolled');
    } else {
        nav.classList.remove('scrolled');
    }
});

// Mobile menu toggle
const menuToggle = document.getElementById('menuToggle');
const navLink = document.querySelector('.nav-link');

menuToggle.addEventListener('click', () => {
    menuToggle.classList.toggle('active');
    navLink.classList.toggle('active');
});

// Close menu function
function closeMenu() {
    menuToggle.classList.remove('active');
    navLink.classList.remove('active');
}

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    if (!nav.contains(e.target)) {
        closeMenu();
    }
});

// Contact Form Handling
document.addEventListener('DOMContentLoaded', function() {
    const contactForm = document.getElementById('contactForm');
    
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Get form values
            const name = document.getElementById('name').value.trim();
            const email = document.getElementById('email').value.trim();
            const phone = document.getElementById('phone').value.trim();
            const service = document.getElementById('service').value;
            const message = document.getElementById('message').value.trim();
            
            // Basic validation
            if (!name || !email || !message) {
                alert('Please fill in all required fields (Name, Email, and Message)');
                return;
            }
            
            // Email validation
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                alert('Please enter a valid email address');
                return;
            }
            
            // Phone validation (if provided)
            if (phone) {
                const phoneRegex = /^[\d\s\+\-\(\)]+$/;
                if (!phoneRegex.test(phone)) {
                    alert('Please enter a valid phone number');
                    return;
                }
            }
            
            // Send data to backend
            fetch('/api/contact', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    email: email,
                    phone: phone,
                    subject: service, // Map service to subject as expected by backend
                    message: message
                })
            })
            .then(response => response.json())
            .then(data => {
                if(data.status === 'success'){
                    alert('Message sent successfully!');
                    contactForm.reset();
                } else {
                    alert('Error: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error sending message. Please try again.');
            });
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