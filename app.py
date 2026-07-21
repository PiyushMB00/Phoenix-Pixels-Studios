from flask import Flask, render_template, request, jsonify
from datetime import datetime
from supabase import create_client, Client
import os
import re
import logging
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from difflib import SequenceMatcher

# ===== CONFIGURATION =====
load_dotenv()

app = Flask(__name__)

_flask_secret = os.getenv('FLASK_SECRET_KEY')
_is_production = os.getenv('FLASK_ENV') == 'production'
if not _flask_secret:
    if _is_production:
        raise RuntimeError("FLASK_SECRET_KEY is not set. Cannot start in production without a secret key.")
    _flask_secret = 'dev-only-insecure-fallback-do-not-use-in-production'

app.config['SECRET_KEY'] = _flask_secret
app.config['SESSION_COOKIE_SECURE'] = _is_production
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ===== ENVIRONMENT VARIABLES =====
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials not set. Check your .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logger.info("Supabase client initialized successfully.")

# ===== SECURITY HEADERS =====
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    if os.getenv('FLASK_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ===== RATE LIMITING (simple in-memory, per-IP) =====
from collections import defaultdict
import time

_rate_limit_store = defaultdict(list)
_RATE_LIMITS = {
    'contact': {'max_requests': 5, 'window_seconds': 60},
    'chat': {'max_requests': 20, 'window_seconds': 60},
}
_last_store_cleanup = time.time()

def _cleanup_rate_limit_store():
    """Periodically purge stale keys from the store to prevent unbounded memory growth."""
    global _last_store_cleanup
    now = time.time()
    # Run cleanup at most once every 10 minutes
    if now - _last_store_cleanup < 600:
        return
    _last_store_cleanup = now
    max_window = max(v['window_seconds'] for v in _RATE_LIMITS.values())
    stale_keys = [k for k, timestamps in _rate_limit_store.items()
                  if not any(now - t < max_window for t in timestamps)]
    for k in stale_keys:
        del _rate_limit_store[k]
    if stale_keys:
        logger.info(f"Rate limit store cleanup: removed {len(stale_keys)} stale entries.")

def is_rate_limited(endpoint_key):
    """Check if the current IP is rate-limited for the given endpoint."""
    _cleanup_rate_limit_store()
    ip = request.remote_addr or 'unknown'
    key = f"{endpoint_key}:{ip}"
    now = time.time()
    config = _RATE_LIMITS.get(endpoint_key, {'max_requests': 30, 'window_seconds': 60})

    # Slide the window: drop timestamps older than the window
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < config['window_seconds']]

    if len(_rate_limit_store[key]) >= config['max_requests']:
        return True

    _rate_limit_store[key].append(now)
    return False

# ===== INPUT SANITIZATION =====
def sanitize_input(text, max_length=2000):
    """Strip HTML tags, newlines (header injection prevention), and limit length."""
    if not text:
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', str(text))
    # Strip CR/LF to prevent email header injection (CRLF injection)
    clean = clean.replace('\r', ' ').replace('\n', ' ')
    # Collapse multiple spaces
    clean = re.sub(r'  +', ' ', clean)
    return clean.strip()[:max_length]

# ===== CUSTOM ERROR HANDLERS =====
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal server error: {e}")
    return jsonify({"status": "error", "message": "Something went wrong on our end. Please try again later."}), 500

# ===== HEALTH CHECK =====
@app.route("/health")
def health_check():
    """Health check endpoint for monitoring and deployment platforms."""
    try:
        # Quick Supabase ping
        supabase.table("contact").select("id").limit(1).execute()
        db_status = "connected"
    except Exception:
        db_status = "unreachable"
    return jsonify({"status": "ok", "database": db_status}), 200

def send_email_with_attachment(submission_data):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        logger.warning("Email credentials not set. Skipping admin email.")
        return False

    email_subject = f"New Contact Form Submission: {submission_data.get('subject')}"
    body = f"New submission from {submission_data.get('name')}.\nSee attached file for details."

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = email_subject
    msg.attach(MIMEText(body, 'plain'))

    # Format content for the text file
    file_content = ""
    for key, value in submission_data.items():
        file_content += f"{key.capitalize()}: {value}\n"

    # Create attachment
    attachment = MIMEBase('application', 'octet-stream')
    attachment.set_payload(file_content.encode('utf-8'))
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment; filename="contact_submission.txt"')
    msg.attach(attachment)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, text)
        server.quit()
        logger.info(f"Admin email sent for submission from {submission_data.get('name')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send admin email: {e}")
        return False

def send_auto_reply(client_email, client_name):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not set. Skipping auto-reply.")
        return False

    subject = "Thank you for contacting us"
    body = f"Hello {client_name},\n\nThank you for contacting Phoenix Pixels Studio. We truly appreciate you taking the time to reach out to us and for showing interest in our services.\n\nThis is to inform you that our team has successfully received your message. We are currently reviewing the details you have shared, and one of our team members will get back to you shortly with further information or assistance as needed.\n\nIf you have any additional details to share or if your inquiry is urgent, please feel free to reply to this email. We will be happy to assist you.\n\nThank you once again for connecting with us. We look forward to working with you.\n\nRegards,\nPhoenix Pixels Studio"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = client_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, client_email, text)
        server.quit()
        logger.info(f"Auto-reply sent to {client_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send auto-reply to {client_email}: {e}")
        return False

def send_emails_in_background(submission_data, client_email, client_name):
    """Send both emails in a background thread so the user gets an instant response."""
    def _send():
        send_email_with_attachment(submission_data)
        send_auto_reply(client_email, client_name)
    thread = threading.Thread(target=_send, daemon=True)
    thread.start()

# ===== ROUTES =====
@app.context_processor
def inject_current_year():
    return {"current_year": datetime.now().year}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/contact")
def contact_page():
    return render_template("ContactUs.html")

@app.route("/api/contact", methods=["POST"])
def contact():
    # Rate limiting
    if is_rate_limited('contact'):
        return jsonify({"status": "error", "message": "Too many requests. Please try again in a minute."}), 429

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"status": "error", "message": "Invalid request format."}), 400

    # Sanitize all inputs
    name    = sanitize_input(data.get("name", ""), max_length=100)
    subject = sanitize_input(data.get("subject", ""), max_length=150)
    phone   = re.sub(r'\D', '', data.get("phone", ""))[:15]   # digits only, capped
    email   = sanitize_input(data.get("email", ""), max_length=254)  # RFC 5321 max
    message = sanitize_input(data.get("message", ""), max_length=2000)

    # Validation
    if not all([name, subject, phone, email, message]):
        return jsonify({"status": "error", "message": "Please fill in all fields."}), 400
    if not phone.isdigit() or len(phone) != 10:
        return jsonify({"status": "error", "message": "Phone number must be exactly 10 digits."}), 400

    # Email format validation
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(email_regex, email):
        return jsonify({"status": "error", "message": "Please provide a valid email address."}), 400

    try:
        submission_data = {
            "name": name,
            "subject": subject,
            "phone": phone,
            "email": email,
            "message": message
        }
        
        response = supabase.table("contact").insert(submission_data).execute()

        # Send emails in background (non-blocking)
        send_emails_in_background(submission_data, email, name)

        # supabase-py returns a dict with 'error' key if something went wrong
        if hasattr(response, "error") and response.error:
            logger.error(f"Supabase insert error: {response.error}")
            return jsonify({"status": "error", "message": "Failed to save your message. Please try again."}), 500

        logger.info(f"Contact form submitted by {name} ({email})")
        return jsonify({"status": "success", "message": "Message sent successfully!"}), 200
    except Exception as e:
        logger.error(f"Contact form error: {e}")
        return jsonify({"status": "error", "message": "Server error. Please try again later."}), 500


@app.route("/web-development")
def web_development():
    return render_template("web_development.html")

@app.route("/iot-solutions")
def iot_solutions():
    return render_template("iot_solutions.html")

@app.route("/cloud-infrastructure")
def cloud_infrastructure():
    return render_template("cloud_infrastructure.html")

@app.route("/consulting")
def consulting():
    return render_template("consulting.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/partners")
def partners():
    return render_template("partners.html")

@app.route("/sponsors")
def sponsors():
    return render_template("sponsors.html")

@app.route("/careers")
def careers():
    return render_template("careers.html")

@app.route("/privacy-policy")
def privacy_policy():
    return render_template("support/privacy_policy.html")

@app.route("/terms-conditions")
def terms_conditions():
    return render_template("support/terms_conditions.html")

@app.route("/origin")
def origin():
    return render_template("origin.html")

# ===== VIRTUAL ASSISTANT ENGINE =====
# ===== SESSION STORE =====
# Per-session context: last_intent, lead state, history
_sessions = {}  # session_id -> { last_intent, lead_step, lead_data, history }
_MAX_SESSIONS = 500
_SESSION_TTL = 3600  # 1 hour inactivity

def _get_session(session_id):
    """Return session dict, creating it if needed. Evict old sessions."""
    now = time.time()
    # Evict stale sessions
    stale = [sid for sid, s in _sessions.items() if now - s.get("last_active", 0) > _SESSION_TTL]
    for sid in stale:
        del _sessions[sid]
    # Cap total sessions
    if session_id not in _sessions:
        if len(_sessions) >= _MAX_SESSIONS:
            oldest = min(_sessions, key=lambda sid: _sessions[sid].get("last_active", 0))
            del _sessions[oldest]
        _sessions[session_id] = {
            "last_intent": None,
            "lead_step": None,   # None | "name"|"email"|"phone"|"business"|"requirement"|"budget"|"timeline"
            "lead_data": {},
            "history": [],       # list of {"role": "user"|"bot", "text": "..."}
            "last_active": now,
        }
    _sessions[session_id]["last_active"] = now
    return _sessions[session_id]

# ===== ANALYTICS STORE =====
_analytics = {
    "total_chats": 0,
    "unresolved": 0,
    "intent_counts": defaultdict(int),
    "session_logs": [],     # last 100 log entries
}

def _log_analytics(session_id, intent, resolved, message):
    _analytics["total_chats"] += 1
    if not resolved:
        _analytics["unresolved"] += 1
    if intent:
        _analytics["intent_counts"][intent] += 1
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "session_id": session_id[:8] + "...",
        "intent": intent or "unknown",
        "resolved": resolved,
        "message_snippet": message[:60],
    }
    _analytics["session_logs"].append(entry)
    if len(_analytics["session_logs"]) > 100:
        _analytics["session_logs"] = _analytics["session_logs"][-100:]

# ===== KNOWLEDGE BASE =====
FAQS = {
    # --- Core services ---
    "services": "**🛠 Our Services**\n\nAt Phoenix Pixels Studios, we specialize in:\n• **Web Development** — from landing pages to full e-commerce platforms\n• **IoT Solutions** — ESP32/Arduino automation & real-time dashboards\n• **Cloud Infrastructure** — AWS/Azure deployments & database management\n• **Technical Consulting** — digital strategy & project planning",

    "web": "**🌐 Web Development**\n\nWe build everything from landing pages to complex e-commerce sites.\n\n• **Tech:** React.js, Python Flask, Node.js\n• **Starting at:** ₹6,999\n• **Turnaround:** 7–10 days\n• Includes mobile-responsive design, SEO-ready structure & dedicated support",

    "iot": "**📡 IoT Solutions**\n\nOur IoT expertise bridges hardware and software:\n\n• ESP32 & Arduino automation\n• Industrial sensor monitoring\n• Real-time data dashboards\n• MQTT & cloud data pipelines\n\nIdeal for smart homes, industry 4.0 & campus projects.",

    "cloud": "**☁️ Cloud Infrastructure**\n\nWe handle your entire cloud setup:\n\n• AWS / Azure deployments\n• Supabase & PostgreSQL database management\n• Server scaling & load balancing\n• CI/CD pipeline setup\n• Security hardening & monitoring",

    "consulting": "**🧭 Technical Consulting**\n\nClear, practical guidance for your tech decisions:\n\n• Technology stack selection\n• Digital strategy & roadmaps\n• Project architecture review\n• Cost optimization advice\n\nSmart solutions. Honest advice. No fluff.",

    # --- Pricing ---
    "pricing": "**💰 Pricing Packages**\n\n| Package | Price | Pages | Timeline |\n|---|---|---|---|\n| Standard | ₹6,999 | 3 pages | 5–7 days |\n| Premium | ₹14,999 | Up to 6 | 7–12 days |\n| Custom | ₹24,999+ | Unlimited | As scoped |\n\nAll packages include responsive design, modern UI, SEO-ready structure & dedicated support.",

    "standard": "**📦 Standard Package — ₹6,999**\n\n• 3 professionally designed pages\n• Fully mobile-responsive layout\n• WhatsApp button integration\n• Contact form setup\n• Essential speed optimization\n• Up to 2 revisions\n• ⏱ Delivery in 5–7 days",

    "premium": "**⭐ Premium Package — ₹14,999**\n\n• Up to 6 pages with animated UI\n• Hosting + domain setup\n• Razorpay payment integration\n• WhatsApp inquiry automation\n• Starter store (up to 10 products)\n• Enhanced speed optimization\n• Up to 4 revisions\n• ⏱ Delivery in 7–12 days",

    "custom": "**🚀 Custom Package — ₹24,999+**\n\n• Unlimited pages\n• Full e-commerce store\n• Custom dashboard / API integration\n• Automation + cloud setup\n• Any custom functionality\n• Unlimited revisions\n• ⏱ Timeline based on project scope",

    # --- Company ---
    "about": "**🔥 About Phoenix Pixels Studios**\n\nWe are a registered Indian startup (MSME Certified) dedicated to transforming ideas into digital reality.\n\n• Founded with the belief: *Engineering is an art, not a commodity*\n• Serving clients globally from India\n• Focused on performance, security & long-term architecture\n• MSME Certified | Shop Act Certified",

    "mission": "**🎯 Our Mission**\n\nTo empower businesses and individuals with accessible, high-performance, and futuristic technology.\n\nWe build digital ecosystems that are not just functional — they're intuitive, impactful, and built to last.",

    "origin": "**🌅 The Origin Story**\n\nPhoenix Pixels Studios was born from one core truth: *Engineering is an art, not a commodity.*\n\nWe saw a world saturated with templates and fragile code, and chose to be the alternative.\n\n• Performance over fluff\n• Security over shortcuts\n• Long-term architecture over quick hacks\n\nVisit **/origin** to read the full story.",

    "why_choose": "**✅ Why Choose Phoenix Pixels?**\n\n1. **Quality First** — We never compromise on code or design\n2. **Client Centric** — Your success is our success\n3. **Innovation** — Latest tech for your competitive edge\n4. **Integrity** — Transparent pricing, honest advice, secure systems",

    "msme": "**🏛 Officially Registered**\n\nYes! Phoenix Pixels Studios is:\n• MSME Certified by the Government of India (Udyam)\n• Shop Act Certified Business\n• Operating as a legitimate registered startup",

    # --- Projects ---
    "projects": "**💼 Our Projects**\n\n1. **Shrimant Multi Services & Facilities 79** — Skilled labour, painting, legal consultation, printing *(coming soon)*\n2. **LawAid X Sanvidhan** — Legal knowledge platform with AI assistant & SOS Shield ✅\n3. **Sahyadricha Chhawa Foundation** — Supporting cancer patients, orphans & cultural heritage *(coming soon)*",

    "lawaid": "**⚖️ LawAid X Sanvidhan**\n\nOur flagship project empowering citizens with legal knowledge:\n\n• Comprehensive law library\n• AI-powered legal assistant\n• Quick SOS Shield feature\n• Built for accessibility & public use\n\n🔗 Available on GitHub!",

    "shrimant": "**🔧 Shrimant Multi Services & Facilities 79**\n\nA comprehensive service provider platform:\n\n• Skilled labour supply\n• Expert painting & graphic design\n• Legal consultation\n• Quality printing services\n\n⏳ Coming Soon!",

    "sahyadricha": "**❤️ Sahyadricha Chhawa Foundation**\n\nA project close to our hearts:\n\n• Supporting cancer patients & orphans\n• Giving a stage to hidden talents\n• Preserving rich cultural heritage\n• Serving humanity with purpose\n\n⏳ Coming Soon!",

    "college_projects": "**🎓 College Sponsored Projects**\n\n1. **Brain Disease AI** — ML-powered diagnostic tool for neurological condition detection\n2. **LawAid X Sanvidhan** — Legal knowledge platform\n3. **Dressify AI** — AI fashion tool for virtual dress try-on",

    "brain_ai": "**🧠 Brain Disease AI**\n\nA college-sponsored AI diagnostic tool:\n\n• Analyzes medical imaging data\n• Detects neurological conditions early\n• Uses advanced ML algorithms\n• Assists healthcare professionals in diagnosis",

    "dressify": "**👗 Dressify AI**\n\nA college-sponsored AI fashion tool:\n\n• Virtually try on dresses in real-time\n• Personalize your style\n• AI-powered fit visualization\n\n🔗 Try it: **piyushmb00.github.io/Dressify-AI**",

    # --- Careers & Internships ---
    "internship": "**🎓 Web Development Internship**\n\nWe offer hands-on internship experience:\n\n• Work on real client projects\n• Learn industry best practices\n• Build your portfolio\n• Mentorship from experienced developers\n\n👉 Check the **Workshops** section on our homepage to apply!",

    "workshops": "**🏫 PPS Workshops**\n\nWe empower next-gen developers through high-impact learning:\n\n• **Current Program:** Web Development Internship\n• Real project experience\n• Industry-ready curriculum\n• Certificate on completion\n\nStay tuned for more workshops coming soon!",

    "hiring": "**💼 We're Hiring!**\n\nCurrent open roles:\n\n• **Frontend Intern** — HTML, CSS, JS, React\n• **Backend Developer** — Python/Flask or Node.js\n• **UI/UX Designer** — Figma expertise + portfolio required\n• **Cloud Engineer** — AWS/Azure & DevOps\n\n👉 Visit our **Careers page** and apply via the contact form!",

    # --- Process & Timeline ---
    "process": "**⚙️ Our Development Process**\n\n1. 📞 **Consultation** — Understand your vision & requirements\n2. 🎨 **Design Mockup** — Visual prototype for your approval\n3. 💻 **Development** — Clean, performant code\n4. 🧪 **Testing** — Quality assurance & cross-device checks\n5. 🚀 **Deployment** — Go live with monitoring\n\nWe keep you updated at every step!",

    "timeline": "**⏱ Typical Timelines**\n\n• Landing page: **3–5 days**\n• Full business website: **10–15 days**\n• E-commerce store: **14–21 days**\n• IoT / Cloud project: **Varies by scope**\n\nNeed it faster? Ask us about priority delivery!",

    # --- Tech Stack ---
    "tech": "**🛠 Our Tech Stack**\n\n**Frontend:** React.js, HTML5, CSS3, Vanilla JS\n**Backend:** Python Flask, Node.js\n**Database:** Supabase, PostgreSQL, Firebase\n**Cloud:** AWS, Azure, Google Cloud\n**IoT:** ESP32, Arduino, MQTT\n**AI/ML:** Python, TensorFlow, Gemini API\n**Payments:** Razorpay\n**DevOps:** GitHub Actions, CI/CD pipelines",

    # --- Contact & Support ---
    "contact": "**📬 Contact Us**\n\n• **Email:** phoenixpixelsinc@gmail.com\n• **Contact Form:** Available on our Contact Us page\n• **Response Time:** Within 24 hours\n\nFor urgent matters, email us directly — we're fast!",

    "payment": "**💳 Payment Options**\n\n• Razorpay (UPI, Cards, Net Banking)\n• Bank Transfer (on request)\n• Installment plans available for Custom packages\n\nFor payment queries, reach us via the Contact page.",

    "refund": "**↩️ Refund Policy**\n\nOur refund policy is outlined in our Terms & Conditions page. Key points:\n\n• We work closely with clients to ensure satisfaction at every stage\n• Revisions are included per package\n• For specific concerns, contact us directly — we'll make it right.",

    # --- NEW KB ENTRIES ---
    "seo": "**🔍 SEO Services**\n\nEvery website we build is SEO-ready by default:\n\n• On-page optimization (meta tags, structured data)\n• Performance optimization (Core Web Vitals)\n• Mobile-first indexing compliance\n• Google Analytics & Search Console setup\n• Keyword-ready content structure\n\nAdvanced SEO packages available on request.",

    "maintenance": "**🔧 Website Maintenance**\n\nWe offer post-launch support:\n\n• Bug fixes & content updates\n• Security patches & dependency updates\n• Performance monitoring\n• Monthly maintenance plans available\n\nAsk us about our **Maintenance Retainer** package!",

    "domain_hosting": "**🌍 Domain & Hosting**\n\nWe handle the full setup:\n\n• Domain registration & DNS configuration\n• Shared, VPS & Cloud hosting options\n• SSL certificate setup (HTTPS)\n• Email hosting setup\n• cPanel / server management\n\nIncluded in Premium & Custom packages.",

    "ecommerce": "**🛒 E-Commerce Solutions**\n\nFull online store setup:\n\n• Product catalog & inventory management\n• Razorpay / payment gateway integration\n• Cart, checkout & order management\n• WhatsApp order notifications\n• Admin dashboard\n\nStarter store (10 products) in Premium. Full store in Custom.",

    "mobile": "**📱 Mobile & PWA**\n\nAll our websites are built mobile-first:\n\n• Fully responsive across all screen sizes\n• PWA (Progressive Web App) support available\n• Touch-optimized interactions\n• Fast loading on 3G/4G networks\n\nNative mobile apps available as custom projects.",

    "security": "**🔒 Security Practices**\n\nWe take security seriously:\n\n• HTTPS / SSL on all sites\n• Input sanitization & CSRF protection\n• Secure environment variable management\n• Rate limiting on all APIs\n• Security headers (X-Frame-Options, CSP, etc.)\n• MSME-certified business — your data is safe",

    "nda": "**🔐 Confidentiality & NDA**\n\nWe respect your intellectual property:\n\n• NDA signing available for all Custom projects\n• Client data handled with full confidentiality\n• No code or design shared without written consent\n• Source code delivered to you on project completion",

    "testimonials": "**⭐ Client Reviews**\n\nWe're proud of the work we do and the relationships we build. Our clients appreciate:\n\n• Transparent communication\n• On-time delivery\n• Quality that exceeds expectations\n\nView our projects section to see our work in action! Testimonials coming soon on our website.",

    "referral": "**🤝 Referral Program**\n\nKnow someone who needs a great website?\n\n• Refer a client and earn rewards\n• Referral benefits discussed directly\n• Contact us to learn more\n\nReach out via the Contact page to get started!",

    "social_media": "**📲 Find Us Online**\n\n• **GitHub:** github.com/PiyushMB00\n• **Email:** phoenixpixelsinc@gmail.com\n• Social media profiles coming soon!\n\nStay connected — big announcements are on the way 🔥",

    "quote": "**📋 Get a Custom Quote**\n\nEvery project is unique. Here's how to get started:\n\n1. Fill out our **Contact Form** with your requirements\n2. Or email us directly at **phoenixpixelsinc@gmail.com**\n3. We'll review & send a detailed proposal within 24 hours\n\nNo obligation. No templates. Just honest, scoped pricing.",

    "ai_services": "**🤖 AI & ML Services**\n\nWe build AI-powered solutions:\n\n• Chatbot & virtual assistant development\n• AI image/document analysis tools\n• Gemini / OpenAI API integration\n• ML model integration into web apps\n• Data dashboards with predictive insights\n\nSee our college projects (Brain Disease AI, Dressify AI) for examples!",

    "revision_policy": "**✏️ Revision Policy**\n\n• **Standard:** Up to 2 revisions\n• **Premium:** Up to 4 revisions\n• **Custom:** Unlimited revisions\n\nRevisions are scoped to the agreed design — major scope changes may require a new quote. We always aim for your 100% satisfaction.",

    # --- Civilities ---
    "greeting": "**👋 Welcome to Phoenix Pixels Studios!**\n\nI'm the Phoenix Assistant. I can help you with:\n\n• Services & pricing\n• Projects & portfolio\n• Internships & careers\n• Getting a quote\n• Tech stack & process\n\nWhat's on your mind?",

    "gratitude": "You're welcome! 😊 We love helping businesses grow.\n\nIs there anything else you'd like to know about Phoenix Pixels Studios?",

    "firmness": "**💎 We Build for Longevity**\n\nWe can build fast or build right. We choose both — but never at the cost of quality.\n\nOur pricing reflects:\n• Real engineering time (not templates)\n• Security-first development\n• Responsive, tested, optimized code\n\nQuality has a cost. We deliver quality.",

    "philosophy": "**🦅 The Phoenix Philosophy**\n\nA phoenix doesn't represent beauty. It represents *rebuilding after failure.*\n\nThat's how we approach technology — creating resilient systems that rise stronger from every challenge.\n\n*Engineered, not templated.*",

    "bye": "**Goodbye! 🔥**\n\nIt was great chatting with you. Come back anytime you need help with your digital projects.\n\nBuilders are always welcome here.",
}

# ===== SYNONYM MAP =====
# Maps synonym patterns (pipe-separated) -> canonical FAQ key
SYNONYM_MAP = [
    (["quotation", "estimate", "fee", "charges", "rates", "how much does", "what does it cost", "what is the price", "quote for"], "pricing"),
    (["who made you", "what are you", "tell me about yourself", "introduce yourself"], "about"),
    (["get started", "start a project", "begin", "kickoff", "onboard", "work with you", "hire you"], "process"),
    (["seo", "search engine optimization", "google ranking", "organic traffic", "rank on google"], "seo"),
    (["ecommerce", "e-commerce", "online store", "sell online", "shop online", "razorpay store", "product page"], "ecommerce"),
    (["maintain", "maintenance", "update website", "bug fix", "after launch", "ongoing support", "website support"], "maintenance"),
    (["domain", "hosting plan", "cpanel", "shared hosting", "web hosting", "ssl"], "domain_hosting"),
    (["mobile app", "pwa", "progressive web", "android app", "ios app", "responsive app"], "mobile"),
    (["secure", "ssl certificate", "hack proof", "security audit", "https setup"], "security"),
    (["nda", "confidential", "private project", "sign nda", "intellectual property"], "nda"),
    (["testimonial", "client review", "feedback", "what clients say", "customer review"], "testimonials"),
    (["refer", "referral", "commission", "affiliate program", "refer a friend"], "referral"),
    (["instagram", "twitter", "linkedin", "github", "social media", "social handle"], "social_media"),
    (["get a quote", "request a quote", "quotation form", "send proposal", "project estimate"], "quote"),
    (["artificial intelligence", "machine learning", "ai integration", "openai", "gemini api", "chatbot development"], "ai_services"),
    (["revision", "how many changes", "how many revisions", "change request"], "revision_policy"),
]

# ===== SMART SUGGESTIONS MAP =====
SUGGESTIONS = {
    "greeting":       ["View Our Services", "See Pricing Packages", "Talk to an Expert"],
    "services":       ["Web Development Details", "See Pricing", "Our Projects"],
    "web":            ["View Pricing Packages", "Our Timeline", "Contact Us"],
    "iot":            ["See Our Projects", "IoT Pricing", "Talk to an Expert"],
    "cloud":          ["Cloud Pricing", "Our Tech Stack", "Get a Quote"],
    "consulting":     ["View Pricing", "Start a Project", "Contact Us"],
    "pricing":        ["Standard Package", "Premium Package", "Get a Custom Quote"],
    "standard":       ["Premium Package Details", "Custom Package", "Get Started"],
    "premium":        ["Standard Package", "Custom Package", "Contact Us"],
    "custom":         ["Get a Quote", "Our Process", "Contact Us"],
    "contact":        ["Get a Quote", "View Services", "Our Projects"],
    "internship":     ["Apply via Careers Page", "Workshop Details", "Our Tech Stack"],
    "workshops":      ["Apply for Internship", "Our Projects", "Contact Us"],
    "hiring":         ["View Open Roles", "Apply via Contact Form", "About the Team"],
    "about":          ["Our Origin Story", "Why Choose Us", "Our Projects"],
    "mission":        ["Why Choose Us", "Our Services", "Get Started"],
    "origin":         ["About Us", "Our Projects", "Philosophy"],
    "why_choose":     ["Our Services", "Pricing Packages", "Contact Us"],
    "msme":           ["About Us", "Our Services", "Contact Us"],
    "process":        ["Our Timeline", "Pricing Packages", "Get Started"],
    "timeline":       ["Pricing Packages", "Our Process", "Contact Us"],
    "tech":           ["Our Services", "Our Projects", "Get a Quote"],
    "location":       ["Contact Us", "About Us", "Our Services"],
    "partners":       ["About Us", "Contact Us", "Our Services"],
    "projects":       ["LawAid Project", "Dressify AI", "View Pricing"],
    "lawaid":         ["More Projects", "Our Tech Stack", "Contact Us"],
    "shrimant":       ["More Projects", "Our Services", "Contact Us"],
    "sahyadricha":    ["More Projects", "About Us", "Contact Us"],
    "college_projects": ["Brain Disease AI", "Dressify AI", "Our Services"],
    "brain_ai":       ["Dressify AI", "Our AI Services", "Contact Us"],
    "dressify":       ["Brain Disease AI", "Our AI Services", "Get a Quote"],
    "payment":        ["Pricing Packages", "Get a Quote", "Contact Us"],
    "refund":         ["Terms & Conditions", "Contact Us", "Pricing Packages"],
    "seo":            ["Web Development", "Pricing Packages", "Get a Quote"],
    "maintenance":    ["Pricing Packages", "Contact Us", "Our Process"],
    "domain_hosting": ["Premium Package", "Custom Package", "Contact Us"],
    "ecommerce":      ["Premium Package", "Custom Package", "Get a Quote"],
    "mobile":         ["Web Development", "Our Tech Stack", "Get a Quote"],
    "security":       ["About Us", "Our Tech Stack", "Contact Us"],
    "nda":            ["Custom Package", "Contact Us", "Get a Quote"],
    "testimonials":   ["Our Projects", "About Us", "Contact Us"],
    "referral":       ["Contact Us", "Our Services", "Pricing Packages"],
    "social_media":   ["About Us", "Our Projects", "Contact Us"],
    "quote":          ["View Pricing", "Contact Us", "Our Process"],
    "ai_services":    ["Our Tech Stack", "Custom Package", "Get a Quote"],
    "revision_policy":["Pricing Packages", "Our Process", "Contact Us"],
    "gratitude":      ["View Our Services", "See Pricing", "Get a Quote"],
    "firmness":       ["Pricing Packages", "Why Choose Us", "Contact Us"],
    "philosophy":     ["Our Origin Story", "About Us", "Our Projects"],
    "bye":            ["View Our Services", "See Pricing", "Contact Us"],
    "hiring":         ["View Open Roles", "Apply via Contact Form", "About the Team"],
}

# ===== HIGH-INTENT INTENTS (trigger lead capture) =====
HIGH_INTENT_INTENTS = {"quote", "custom"}

# ===== LEAD COLLECTION STEPS =====
LEAD_STEPS = ["name", "email", "phone", "business", "requirement", "budget", "timeline"]
LEAD_PROMPTS = {
    "name":        "Great! I'd love to help. **What's your name?**",
    "email":       "Nice to meet you, {name}! **What's your email address?** (So we can send you a proposal)",
    "phone":       "Got it! **What's your phone number?** (Optional — for quick follow-up)",
    "business":    "Perfect. **What's your business or project name?**",
    "requirement": "Understood! **Can you briefly describe what you need?** (e.g., e-commerce site, portfolio, IoT dashboard)",
    "budget":      "Thanks for sharing that! **What's your approximate budget?** (e.g., ₹6,999 / ₹14,999 / ₹24,999+)",
    "timeline":    "Almost done! **When do you need it by?** (e.g., 1 month, 3 months, ASAP)",
}
LEAD_DONE_MSG = (
    "**🎉 Thank you, {name}!**\n\n"
    "We've received your details and our team will reach out to you at **{email}** within 24 hours with a tailored proposal.\n\n"
    "In the meantime, feel free to explore our [pricing packages] or [projects]."
)

# ===== KEYWORD INTENTS (exact matching — order matters) =====
KEYWORD_INTENTS = [
    # Greetings
    (["hello", "hi", "hey", "greetings", "good morning", "good evening", "howdy", "sup", "what's up"], "greeting"),
    # Specific Projects
    (["shrimant", "multi services", "facilities 79"], "shrimant"),
    (["lawaid", "sanvidhan", "law aid"], "lawaid"),
    (["sahyadricha", "chhawa", "foundation", "ngo", "orphan", "cancer support"], "sahyadricha"),
    (["brain disease", "brain ai", "neurological", "brain diagnostic"], "brain_ai"),
    (["dressify", "fashion ai", "virtual try", "dress ai"], "dressify"),
    (["college project", "college sponsored", "sponsored project", "student project", "academic project"], "college_projects"),
    (["project", "portfolio", "case study", "built", "showcase", "our work"], "projects"),
    # Internship & Workshops
    (["internship", "intern", "intern program", "internship program", "join internship", "apply internship"], "internship"),
    (["workshop", "bootcamp", "training", "pps workshop", "learning program"], "workshops"),
    # Detailed Pricing Tiers
    (["standard package", "basic package", "6999", "starter plan", "starter package"], "standard"),
    (["premium package", "14999", "premium plan"], "premium"),
    (["custom package", "24999", "custom plan", "enterprise", "custom solution"], "custom"),
    # Services
    (["service", "what do you do", "what do you offer", "provide", "offer"], "services"),
    (["website", "web development", "web app", "application", "frontend", "landing page"], "web"),
    (["iot", "automation", "hardware", "arduino", "esp32", "sensor", "smart device"], "iot"),
    (["cloud", "aws", "azure", "google cloud", "server", "database", "hosting", "deploy", "vps"], "cloud"),
    (["consult", "advice", "guidance", "strategy", "technical consulting", "digital strategy"], "consulting"),
    # AI
    (["ai", "machine learning", "ml", "artificial intelligence", "openai", "gemini", "chatbot"], "ai_services"),
    # SEO
    (["seo", "search engine", "google ranking", "organic", "meta tags"], "seo"),
    # E-commerce
    (["ecommerce", "e-commerce", "online store", "sell online", "shop", "product"], "ecommerce"),
    # Mobile
    (["mobile", "pwa", "android", "ios", "responsive", "progressive web"], "mobile"),
    # Security
    (["secure", "ssl", "https", "security", "hack", "vulnerability"], "security"),
    # Maintenance
    (["maintenance", "maintain", "update site", "bug fix", "after launch", "ongoing"], "maintenance"),
    # Domain & Hosting
    (["domain", "hosting", "cpanel", "web host", "ssl certificate", "server setup"], "domain_hosting"),
    # Pricing (general)
    (["price", "cost", "how much", "budget", "package", "plan", "pricing", "rate", "charge", "fee", "quote"], "pricing"),
    # Contact
    (["contact", "email", "phone", "reach", "support", "get in touch", "talk to someone"], "contact"),
    # Careers
    (["job", "career", "hiring", "developer", "recruit", "opening", "vacancy", "apply", "resume", "work with you"], "hiring"),
    # About & Company
    (["who are you", "what is phoenix", "company", "startup", "about", "about you"], "about"),
    (["mission", "vision", "goal", "purpose", "why you exist"], "mission"),
    (["why choose", "why phoenix", "why you", "why should i", "advantage", "benefit", "best"], "why_choose"),
    (["msme", "registered", "certified", "legitimate", "legal entity", "government registered"], "msme"),
    # Process & Timeline
    (["how do you work", "process", "steps", "workflow", "methodology", "how it works"], "process"),
    (["how long", "duration", "delivery time", "turnaround", "timeline", "when will it be done"], "timeline"),
    # Tech Stack
    (["tech", "language", "stack", "platform", "framework", "tools", "technology used"], "tech"),
    # Location
    (["location", "where", "india", "based", "address", "office", "country"], "location"),
    # Partners
    (["partner", "collaboration", "collaborate", "alliance", "partnership"], "partners"),
    # Origin Story
    (["origin", "how it started", "founded", "history", "beginning", "story"], "origin"),
    # Payment & Refund
    (["payment", "pay", "razorpay", "upi", "transaction", "bank transfer"], "payment"),
    (["refund", "cancel", "money back", "return", "cancellation"], "refund"),
    # NDA
    (["nda", "confidential", "private", "sign nda", "intellectual property"], "nda"),
    # Revision
    (["revision", "changes", "how many changes", "update design"], "revision_policy"),
    # Referral
    (["referral", "refer", "affiliate", "commission"], "referral"),
    # Social
    (["instagram", "twitter", "linkedin", "github", "social", "follow you"], "social_media"),
    # Testimonials
    (["testimonial", "review", "client said", "feedback", "rating"], "testimonials"),
    # Gratitude
    (["thank", "thanks", "awesome", "nice", "great", "helpful", "perfect"], "gratitude"),
    # Firmness
    (["cheap", "lowest", "discount", "offer price", "negotiate", "free", "bargain", "reduce price"], "firmness"),
    # Philosophy
    (["what does phoenix mean", "origin of name", "name meaning", "phoenix meaning"], "philosophy"),
    # Bye
    (["bye", "goodbye", "see you", "take care", "cya", "later"], "bye"),
]

# ===== MULTI-INTENT SPLITTER =====
_MULTI_INTENT_SPLIT_RE = re.compile(
    r'\band\b|\balso\b|\bplus\b|\bwhat about\b|\bthen\b|\badditionally\b|\bmoreover\b',
    re.IGNORECASE
)

def _split_multi_intent(message):
    """Split a message by conjunctions into sub-queries."""
    parts = _MULTI_INTENT_SPLIT_RE.split(message)
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 3]
    return parts if len(parts) > 1 else [message]

# ===== PRE-PROCESSOR =====
def _preprocess(text):
    """Normalize text: lowercase, strip punctuation (except apostrophes), collapse spaces."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s'₹]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ===== NLU ENGINE =====
def _resolve_intent(message, session):
    """
    5-Pass NLU Engine:
    Pass 1: Specific Topic Keyword Match (word-boundary aware, excluding generic greetings)
    Pass 2: Synonym Map Expansion
    Pass 3: Pure Greeting Match (only if no specific topic found)
    Pass 4: Fuzzy SequenceMatcher (typo tolerance)
    Pass 5: Session Context Resolution (follow-ups)
    """
    msg = _preprocess(message)
    words = msg.split()

    def _match_kw(kw, text, word_list):
        if len(kw) <= 3:
            return kw in word_list
        return kw in text

    # --- Pass 1: Specific Topic Keyword Match (non-greeting) ---
    for keywords, faq_key in KEYWORD_INTENTS:
        if faq_key == "greeting":
            continue
        for kw in keywords:
            if _match_kw(kw, msg, words):
                return faq_key, 1.0

    # --- Pass 2: Synonym expansion (non-greeting) ---
    for synonym_list, faq_key in SYNONYM_MAP:
        if faq_key == "greeting":
            continue
        for syn in synonym_list:
            if _match_kw(syn, msg, words):
                return faq_key, 0.9

    # --- Pass 3: Pure Greetings (only if no specific topic was asked) ---
    for keywords, faq_key in KEYWORD_INTENTS:
        if faq_key == "greeting":
            for kw in keywords:
                if kw in words or msg == kw:
                    return "greeting", 1.0

    # --- Pass 4: Fuzzy matching (typo tolerance, skipping short greeting words) ---
    all_keywords = []
    for keywords, faq_key in KEYWORD_INTENTS:
        if faq_key == "greeting":
            continue
        for kw in keywords:
            if len(kw) >= 4:
                all_keywords.append((kw, faq_key))
    for synonym_list, faq_key in SYNONYM_MAP:
        if faq_key == "greeting":
            continue
        for kw in synonym_list:
            if len(kw) >= 5:
                all_keywords.append((kw, faq_key))

    best_score = 0.0
    best_faq_key = None

    for kw, faq_key in all_keywords:
        kw_word_count = len(kw.split())
        for i in range(len(words) - kw_word_count + 1):
            window = " ".join(words[i:i + kw_word_count])
            score = SequenceMatcher(None, window, kw).ratio()
            if score > best_score:
                best_score = score
                best_faq_key = faq_key

    if best_score >= 0.75 and best_faq_key:
        return best_faq_key, round(best_score, 2)

    # --- Pass 5: Context resolution (follow-up messages) ---
    FOLLOWUP_PHRASES = ["more", "tell me more", "what about", "elaborate", "explain", "details", "how", "why", "cost", "pricing"]
    if session.get("last_intent") and any(ph in msg for ph in FOLLOWUP_PHRASES):
        last = session["last_intent"]
        if last in {"web", "iot", "cloud", "consulting", "ecommerce"} and any(p in msg for p in ["cost", "pricing", "how much", "price", "fee", "charge"]):
            return "pricing", 0.65
        return last, 0.60

    return None, 0.0

# ===== LEAD COLLECTION =====
def _process_lead_step(session, message):
    """
    Handle lead collection state machine.
    Returns (response_text, lead_prompt_for_next_step_or_None)
    """
    step = session.get("lead_step")
    lead_data = session.setdefault("lead_data", {})

    if step not in LEAD_STEPS:
        return None, None

    # Store the current answer
    lead_data[step] = message.strip()

    current_idx = LEAD_STEPS.index(step)
    next_idx = current_idx + 1

    if next_idx < len(LEAD_STEPS):
        next_step = LEAD_STEPS[next_idx]
        session["lead_step"] = next_step
        prompt_template = LEAD_PROMPTS[next_step]
        prompt = prompt_template.format(**lead_data)
        return None, prompt
    else:
        # All steps done — wrap up
        session["lead_step"] = None
        name = lead_data.get("name", "there")
        email = lead_data.get("email", "your email")
        done_msg = LEAD_DONE_MSG.format(name=name, email=email)
        # Send lead via email in background
        _send_lead_email_background(lead_data.copy())
        logger.info(f"Lead collected: {lead_data.get('name')} / {lead_data.get('email')}")
        return done_msg, None

def _send_lead_email_background(lead_data):
    """Send collected lead data to EMAIL_RECEIVER in background."""
    def _send():
        if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
            return
        try:
            subject = f"🔥 New Lead from Phoenix Assistant: {lead_data.get('name', 'Unknown')}"
            body = "New lead captured via Phoenix Assistant chatbot:\n\n"
            for k, v in lead_data.items():
                body += f"{k.capitalize()}: {v}\n"
            msg = MIMEMultipart()
            msg['From'] = EMAIL_SENDER
            msg['To'] = EMAIL_RECEIVER
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
            server.quit()
            logger.info(f"Lead email sent for {lead_data.get('name')}")
        except Exception as e:
            logger.error(f"Failed to send lead email: {e}")
    threading.Thread(target=_send, daemon=True).start()

# ===== FALLBACK RESPONSE =====
FALLBACK_RESPONSE = (
    "**Hmm, I'm not sure about that one!** 🤔\n\n"
    "Here's what I *can* help you with:\n\n"
    "• Our **services** & tech stack\n"
    "• **Pricing** packages\n"
    "• **Projects** & portfolio\n"
    "• **Internships** & careers\n"
    "• **Process** & timelines\n"
    "• Getting a **custom quote**\n\n"
    "For anything else, our team is available:\n"
    "📧 **phoenixpixelsinc@gmail.com**\n"
    "Or use the [Contact Us](/contact) page."
)
FALLBACK_SUGGESTIONS = ["View Our Services", "See Pricing Packages", "Contact Us"]

# ===== MAIN CHAT ENDPOINT =====
@app.route("/api/chat", methods=["POST"])
def chat():
    if is_rate_limited('chat'):
        return jsonify({"response": "You're sending messages too quickly. Please slow down.", "suggestions": []}), 429

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"response": "Invalid request.", "suggestions": []}), 400

    # Grab inputs
    raw_message = sanitize_input(data.get("message", ""), max_length=500)
    session_id  = sanitize_input(data.get("session_id", "anonymous"), max_length=64)
    is_intent_aware = data.get("intent_aware", False)
    is_proactive    = data.get("proactive", False)

    # Handle special trigger modes (proactive / intent-aware)
    if is_intent_aware:
        return jsonify({
            "response": "**Looks like you're planning something serious! 🚀**\n\nWant to discuss your project scope, timeline & budget? I can help you pick the right package.",
            "suggestions": ["View Pricing Packages", "Our Process", "Get a Custom Quote"],
            "intent": "proactive_intent",
            "confidence": 1.0,
        })
    if is_proactive:
        return jsonify({
            "response": "**You didn't land here by accident. 🔥**\n\nWant to build something that lasts? Let's talk about your project.",
            "suggestions": ["View Our Services", "See Pricing", "Contact Us"],
            "intent": "proactive",
            "confidence": 1.0,
        })

    if not raw_message:
        return jsonify({"response": "I didn't quite catch that. Could you rephrase?", "suggestions": []})

    session = _get_session(session_id)
    user_msg_lower = raw_message.lower()

    # --- Lead collection in progress ---
    if session.get("lead_step"):
        check_intent, check_conf = _resolve_intent(user_msg_lower, session)
        opt_out_words = {"cancel", "stop", "exit", "no", "skip", "nevermind"}
        if (check_intent and check_conf >= 0.7) or user_msg_lower.strip() in opt_out_words:
            session["lead_step"] = None
        else:
            lead_response, next_prompt = _process_lead_step(session, raw_message)
            if lead_response:
                # Lead collection complete
                _log_analytics(session_id, "lead_complete", True, raw_message)
                return jsonify({
                    "response": lead_response,
                    "suggestions": ["View Our Projects", "See Pricing", "Visit Our Website"],
                    "lead_prompt": None,
                    "intent": "lead_complete",
                    "confidence": 1.0,
                })
            else:
                # More steps needed
                _log_analytics(session_id, f"lead_{session['lead_step']}", True, raw_message)
                return jsonify({
                    "response": "",
                    "suggestions": [],
                    "lead_prompt": next_prompt,
                    "intent": "lead_collecting",
                    "confidence": 1.0,
                })

    # --- Multi-intent splitting ---
    sub_queries = _split_multi_intent(user_msg_lower)
    responses = []
    last_intent = None
    last_confidence = 0.0
    suggestions = []

    for sub in sub_queries:
        intent, confidence = _resolve_intent(sub, session)
        if intent and intent in FAQS:
            responses.append(FAQS[intent])
            last_intent = intent
            last_confidence = confidence
            if not suggestions:
                suggestions = SUGGESTIONS.get(intent, FALLBACK_SUGGESTIONS)
        else:
            if len(sub_queries) == 1:
                # Single unresolved query → full fallback
                responses.append(FALLBACK_RESPONSE)
                suggestions = FALLBACK_SUGGESTIONS
            # For multi-intent, skip unresolved sub-queries silently

    if not responses:
        responses.append(FALLBACK_RESPONSE)
        suggestions = FALLBACK_SUGGESTIONS
        _log_analytics(session_id, None, False, raw_message)
    else:
        _log_analytics(session_id, last_intent, True, raw_message)

    # Update session context
    if last_intent:
        session["last_intent"] = last_intent
        session["history"].append({"role": "user", "text": raw_message})
        if len(session["history"]) > 10:
            session["history"] = session["history"][-10:]

    # Combine multi-intent responses with a separator
    combined_response = "\n\n---\n\n".join(responses)

    # --- Lead capture trigger ---
    lead_prompt = None
    if last_intent in HIGH_INTENT_INTENTS and last_confidence >= 0.7:
        # Only trigger if we haven't already collected a lead in this session
        if not session["lead_data"]:
            session["lead_step"] = LEAD_STEPS[0]
            lead_prompt = LEAD_PROMPTS["name"]

    return jsonify({
        "response": combined_response,
        "suggestions": suggestions[:3],
        "lead_prompt": lead_prompt,
        "intent": last_intent,
        "confidence": last_confidence,
    })

# ===== ANALYTICS ENDPOINT =====
@app.route("/api/analytics")
def analytics():
    """Returns chatbot analytics. Useful for internal monitoring."""
    top_intents = sorted(
        [{"intent": k, "count": v} for k, v in _analytics["intent_counts"].items()],
        key=lambda x: x["count"],
        reverse=True
    )[:10]
    return jsonify({
        "total_chats": _analytics["total_chats"],
        "unresolved_queries": _analytics["unresolved"],
        "top_intents": top_intents,
        "recent_sessions": _analytics["session_logs"][-20:],
    })

if __name__ == "__main__":
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5000)

