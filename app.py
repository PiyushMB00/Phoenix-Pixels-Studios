from flask import Flask, render_template, request, jsonify
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

@app.route("/api/chat", methods=["POST"])
def chat():
    # Rate limiting
    if is_rate_limited('chat'):
        return jsonify({"response": "You're sending messages too quickly. Please slow down."}), 429

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"response": "Invalid request."}), 400

    user_message = sanitize_input(data.get("message", ""), max_length=500).lower()
    is_intent_aware = data.get("intent_aware", False)
    
    is_proactive = data.get("proactive", False)
    
    if not user_message and not is_intent_aware and not is_proactive:
        return jsonify({"response": "I didn't quite catch that. Could you repeat?"})

    if is_intent_aware:
        return jsonify({"response": "Looks like you’re planning something serious. Want to discuss scope and timelines?"})

    if data.get("proactive", False):
        return jsonify({"response": "You didn’t land here by accident. Want to build something that lasts?"})

    bot_response = get_bot_response(user_message)
    return jsonify({"response": bot_response})

def get_bot_response(message):
    # Expanded Knowledge Base / FAQ
    faqs = {
        "services": "At Phoenix Pixels Studios, we specialize in Web Development, smart IoT Solutions, scalable Cloud Infrastructure, and Technical Consulting.",
        "web": "We build everything from landing pages to complex e-commerce sites using technologies like React and Python. Standard websites start from ₹6,999 and usually take 7-10 days.",
        "iot": "Our IoT expertise includes ESP32/Arduino automation, industrial sensor monitoring, and real-time data dashboards. We bridge the gap between hardware and software.",
        "cloud": "We handle AWS/Azure deployments, database management (Supabase/PostgreSQL), and server scaling to ensure your app stays fast and secure.",
        "pricing": "We have three main tiers: Standard (₹6,999 — 3 pages, mobile-responsive, contact form, 5-7 days delivery), Premium (₹14,999 — up to 6 pages, animated UI, hosting + domain, Razorpay integration, 7-12 days), and Custom (₹24,999+ — unlimited pages, full e-commerce, custom dashboard/API, cloud setup). All packages include responsive design, modern UI, SEO-ready structure, and dedicated support.",
        "standard": "Our Standard package is ₹6,999. It includes 3 professionally designed pages, fully mobile-responsive layout, WhatsApp button integration, contact form setup, essential speed optimization, up to 2 revisions, and delivery in 5-7 days.",
        "premium": "Our Premium package is ₹14,999. It includes up to 6 pages, modern animated UI with premium layout, hosting + domain setup, Razorpay payment integration, WhatsApp inquiry automation, a starter store (up to 10 products), enhanced speed optimization, up to 4 revisions, and delivery in 7-12 days.",
        "custom": "Our Custom package starts from ₹24,999. It includes unlimited pages, full e-commerce store, custom dashboard/API integration, automation + cloud setup, any custom functionality you need, unlimited revisions, and delivery time based on project scope.",
        "contact": "You can email us at phoenixpixelsinc@gmail.com, or fill out the form on our Contact Us page. We typically respond within 24 hours.",
        "hiring": "We're currently hiring for four roles: Frontend Intern (HTML, CSS, JS, React), Backend Developer (Python/Flask or Node.js), UI/UX Designer (Figma expertise, portfolio required), and Cloud Engineer (AWS/Azure & DevOps). Visit our Careers page and apply via the contact form!",
        "about": "Phoenix Pixels Studios is a registered Indian startup (MSME Certified) dedicated to transforming ideas into digital reality with a focus on quality and innovation. Our mission is to empower businesses with accessible, high-performance, and futuristic technology.",
        "process": "Our process is simple: 1. Consultation -> 2. Design Mockup -> 3. Development -> 4. Testing -> 5. Deployment. We keep you updated at every step!",
        "timeline": "A typical landing page takes 3-5 days, while full business websites usually take 10-15 days. Complex IoT or Cloud projects vary based on requirements.",
        "tech": "We use modern tech stacks like React.js, Python Flask, Node.js, Supabase for backend, and ESP32 for IoT hardware projects.",
        "location": "We are based in India and operate as a registered startup, serving clients globally.",
        "projects": "We've worked on several exciting projects! These include: 1) Shrimant Multi Services and Facilities 79 — a comprehensive service provider for skilled labour, painting, graphic design, legal consultation, and printing (coming soon). 2) LawAid X Sanvidhan — a platform empowering citizens with legal knowledge, featuring a law library, AI-powered legal assistant, and SOS Shield. 3) Sahyadricha Chhawa Foundation — supporting cancer patients, orphans, and preserving cultural heritage (coming soon).",
        "lawaid": "LawAid X Sanvidhan is one of our flagship projects. It empowers common citizens with legal knowledge through a comprehensive law library, an AI-powered legal assistant, and a quick SOS Shield feature. Check it out on GitHub!",
        "shrimant": "Shrimant Multi Services and Facilities 79 is a comprehensive service provider platform we're building. It supplies skilled labour and professional services — from expert painting and graphic design to legal consultation and quality printing. Coming soon!",
        "sahyadricha": "Sahyadricha Chhawa Foundation is a project close to our hearts. The foundation supports cancer patients and orphans, gives a stage to hidden talents, and is dedicated to serving humanity and preserving our rich cultural heritage. Coming soon!",
        "college_projects": "We also work on college-sponsored projects! Currently: 1) Brain Disease AI — an AI-powered diagnostic tool that analyzes medical imaging for early detection of neurological conditions. 2) LawAid X Sanvidhan — our legal knowledge platform. 3) Dressify AI — an AI fashion tool that helps users virtually try on dresses and personalize their style in real-time.",
        "brain_ai": "Brain Disease AI is a college-sponsored project — an AI-powered diagnostic tool for brain diseases. It uses advanced machine learning algorithms to analyze medical imaging data, assisting healthcare professionals in early detection and accurate diagnosis of neurological conditions.",
        "dressify": "Dressify AI is a college-sponsored project — an AI-powered fashion tool that helps users select and virtually try out their favorite dresses. You can personalize your style and visualize fit in real-time. Try it out at piyushmb00.github.io/Dressify-AI!",
        "internship": "Yes, we offer a Web Development Internship! Join our program to gain hands-on experience in modern web development. You'll work on real projects, learn industry best practices, and build your portfolio alongside experienced developers. Check the Workshops section on our homepage for more details!",
        "workshops": "We conduct PPS Workshops to empower next-generation developers through high-impact, hands-on learning experiences. Currently, we're running a Web Development Internship program where participants work on real projects. Stay tuned for more upcoming workshops!",
        "partners": "We believe in the power of collaboration! We partner with technology providers, agencies, and businesses to deliver exceptional value. We're currently curating our list of strategic partners. If you're interested in partnering with us, reach out via the Contact page!",
        "origin": "Phoenix Pixels Studios was born from one core truth: Engineering is an art, not a commodity. We saw a world saturated with templates and fragile code, and chose to be the alternative. We prioritize performance over fluff, security over shortcuts, and long-term architecture over quick hacks. Visit our /origin page to learn more!",
        "mission": "Our mission is to empower businesses and individuals with accessible, high-performance, and futuristic technology. We believe in building digital ecosystems that are not just functional but also intuitive and impactful.",
        "why_choose": "Why choose Phoenix Pixels? Four reasons: 1) Quality First — we never compromise on code or design quality. 2) Client Centric — your success is our success. 3) Innovation — we use the latest tech for your competitive edge. 4) Integrity — transparent pricing, honest advice, and secure systems.",
        "consulting": "Our Technical Consulting service offers clear, practical guidance on technology decisions, digital strategy, and project planning. We help you choose the right tools, avoid costly mistakes, and move your project forward with confidence. Smart solutions, honest advice.",
        "msme": "Yes! Phoenix Pixels Studios is an officially registered startup, MSME Certified by the Government of India. We operate as a legitimate, registered business entity.",
        "payment": "We accept payments through multiple modes. For Premium and Custom packages, we integrate Razorpay for seamless payment processing. For specific payment queries, please reach out to us via the Contact page.",
        "refund": "Our refund and terms are outlined in our Terms & Conditions page. We work closely with clients to ensure satisfaction at every stage. For specific concerns, please contact us directly.",
        "portfolio": "You can view our projects right on our homepage! We have a dedicated 'Our Projects' section and a 'College Sponsored Projects' section showcasing our work — including LawAid X Sanvidhan, Brain Disease AI, Dressify AI, and more.",
        "greeting": "Hello! I'm the Phoenix Assistant. I can help you with questions about our services, pricing, projects, internships, or your next digital project. What's on your mind?",
        "gratitude": "You're welcome! We love helping businesses grow. Is there anything else you'd like to know about Phoenix Pixels Studios?",
        "firmness": "We can build fast or build right. We don't do cheap shortcuts. Our pricing reflects real engineering, not templates. Quality has a cost, and we deliver quality.",
        "philosophy": "A phoenix doesn't represent beauty. It represents rebuilding after failure. That's how we approach technology—creating resilient systems that rise stronger.",
        "bye": "Goodbye! It was great chatting with you. Come back anytime you need help with your digital projects. 🔥",
    }

    # Structured keyword-to-FAQ mapping (order matters — specific matches first, general later)
    keyword_intents = [
        # Greetings
        (["hello", "hi", "hey", "greetings", "good morning", "good evening"], "greeting"),
        # Specific Projects (before generic "project")
        (["shrimant", "multi services", "facilities 79"], "shrimant"),
        (["lawaid", "sanvidhan", "law aid"], "lawaid"),
        (["sahyadricha", "chhawa", "foundation", "ngo", "orphan", "cancer"], "sahyadricha"),
        (["brain disease", "brain ai", "neurological", "brain diagnostic"], "brain_ai"),
        (["dressify", "fashion ai", "virtual try", "dress ai"], "dressify"),
        (["college project", "college sponsored", "sponsored project", "student project", "academic project"], "college_projects"),
        (["project", "portfolio", "case study", "built", "showcase"], "projects"),
        # Internship & Workshops
        (["internship", "intern program", "internship program", "join internship", "apply internship"], "internship"),
        (["workshop", "bootcamp", "training", "pps workshop"], "workshops"),
        # Detailed Pricing Tiers
        (["standard package", "basic package", "6999", "starter plan"], "standard"),
        (["premium package", "14999", "premium plan"], "premium"),
        (["custom package", "24999", "custom plan", "enterprise"], "custom"),
        # Services
        (["service", "what do you do", "provide", "offer"], "services"),
        (["website", "web development", "application", "frontend"], "web"),
        (["iot", "automation", "hardware", "arduino", "esp32", "sensor"], "iot"),
        (["cloud", "aws", "server", "azure", "database", "hosting", "deploy"], "cloud"),
        (["consult", "advice", "guidance", "strategy", "technical consulting"], "consulting"),
        # Pricing (general)
        (["price", "cost", "how much", "budget", "package", "plan", "pricing", "rate", "charge", "fee"], "pricing"),
        # Contact
        (["contact", "email", "phone", "reach", "support", "get in touch"], "contact"),
        # Careers
        (["job", "career", "hiring", "intern", "developer", "recruit", "opening", "vacancy", "apply", "resume"], "hiring"),
        # About & Company
        (["who are you", "what is phoenix", "company", "startup", "about"], "about"),
        (["mission", "vision", "goal", "purpose"], "mission"),
        (["why choose", "why phoenix", "why you", "why should i", "advantage", "benefit"], "why_choose"),
        (["msme", "registered", "certified", "legitimate", "legal entity"], "msme"),
        # Process & Timeline
        (["how do you work", "process", "steps", "workflow", "methodology"], "process"),
        (["how long", "duration", "delivery time", "turnaround", "timeline"], "timeline"),
        # Tech Stack
        (["tech", "language", "stack", "platform", "framework", "tools"], "tech"),
        # Location
        (["location", "where", "india", "based", "address", "office"], "location"),
        # Partners
        (["partner", "collaboration", "collaborate", "alliance"], "partners"),
        # Origin Story
        (["origin", "how it started", "founded", "history", "beginning"], "origin"),
        # Payment & Refund
        (["payment", "pay", "razorpay", "upi", "transaction"], "payment"),
        (["refund", "cancel", "money back", "return"], "refund"),
        # Gratitude
        (["thank", "thanks", "awesome", "nice"], "gratitude"),
        # Firmness
        (["cheap", "lowest", "discount", "offer price", "negotiate", "free", "bargain"], "firmness"),
        # Philosophy
        (["what does phoenix mean", "origin of name", "name meaning"], "philosophy"),
        # Bye
        (["bye", "goodbye", "see you", "take care"], "bye"),
    ]

    # ===== PASS 1: Exact substring matching (fast path) =====
    for keywords, faq_key in keyword_intents:
        if any(k in message for k in keywords):
            return faqs[faq_key]

    # ===== PASS 2: Fuzzy matching for misspelled words =====
    # Build a flat list of (keyword, faq_key) for fuzzy comparison
    all_keywords = []
    for keywords, faq_key in keyword_intents:
        for kw in keywords:
            # Only fuzzy-match keywords with 4+ characters (short words cause false positives)
            if len(kw) >= 4:
                all_keywords.append((kw, faq_key))

    # Split user message into words and check multi-word sliding windows
    words = message.split()
    best_score = 0
    best_faq_key = None

    for kw, faq_key in all_keywords:
        kw_word_count = len(kw.split())

        # Create sliding windows of the same word count as the keyword
        for i in range(len(words) - kw_word_count + 1):
            window = " ".join(words[i:i + kw_word_count])
            score = SequenceMatcher(None, window, kw).ratio()

            if score > best_score:
                best_score = score
                best_faq_key = faq_key

    # Threshold: 0.75 means ~75% similarity (catches typos like "intership" -> "internship")
    if best_score >= 0.75 and best_faq_key:
        return faqs[best_faq_key]

    return "I'm here to help with anything regarding Phoenix Pixels Studios! You can ask me about our projects, internships, workshops, pricing packages, technologies we use, or our development process. What would you like to explore?"

if __name__ == "__main__":
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
