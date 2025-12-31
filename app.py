from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase credentials not set. Check your .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def send_email_with_attachment(submission_data):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print("Email credentials not set. Skipping email.")
        return

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
        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, text)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_auto_reply(client_email, client_name):
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        return

    subject = "Thank you for contacting us"
    body = f"Hello {client_name},\n\nThank you for contacting Phoenix Pixels Studio. We truly appreciate you taking the time to reach out to us and for showing interest in our services.\n\nThis is to inform you that our team has successfully received your message. We are currently reviewing the details you have shared, and one of our team members will get back to you shortly with further information or assistance as needed.\n\nIf you have any additional details to share or if your inquiry is urgent, please feel free to reply to this email. We will be happy to assist you.\n\nThank you once again for connecting with us. We look forward to working with you.\n\nRegards,\nPhoenix Pixels Studio"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = client_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, client_email, text)
        server.quit()
        print(f"Auto-reply sent to {client_email}")
    except Exception as e:
        print(f"Failed to send auto-reply: {e}")

@app.route("/")
def home():
    # Render your frontend HTML
    return render_template("index.html")

@app.route("/contact")
def contact_page():
    return render_template("ContactUs.html")

@app.route("/api/contact", methods=["POST"])
def contact():
    data = request.get_json()

    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip()
    message = data.get("message", "").strip()

    # Validation
    if not all([name, subject, phone, email, message]):
        return jsonify({"status": "error", "message": "Please fill in all fields."}), 400
    if not phone.isdigit() or len(phone) != 10:
        return jsonify({"status": "error", "message": "Phone number must be exactly 10 digits."}), 400

    try:
        submission_data = {
            "name": name,
            "subject": subject,
            "phone": phone,
            "email": email,
            "message": message
        }
        
        response = supabase.table("contact").insert(submission_data).execute()

        # Send email with attachment
        send_email_with_attachment(submission_data)
        
        # Send auto-reply to client
        send_auto_reply(email, name)

        # supabase-py returns a dict with 'error' key if something went wrong
        if hasattr(response, "error") and response.error:
            return jsonify({"status": "error", "message": str(response.error)}), 500

        return jsonify({"status": "success", "message": "Message sent successfully!"}), 200
    except Exception as e:
        print("Error inserting:", e)
        return jsonify({"status": "error", "message": "Server error."}), 500


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
    data = request.get_json()
    user_message = data.get("message", "").lower().strip()
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
        "pricing": "We have three main tiers: Standard (₹6,999), Premium (₹14,999), and Custom (from ₹24,999). Every project is tailored to your business needs.",
        "contact": "You can email us at phoenixpixelsinc@gmail.com, or fill out the form on our Contact Us page. We typically respond within 24 hours.",
        "hiring": "We're currently looking for talented Frontend Interns and Backend Developers. If you're passionate about tech, send your resume via the Careers page!",
        "about": "Phoenix Pixels Studios is a registered Indian startup (MSME Certified) dedicated to transforming ideas into digital reality with a focus on quality and innovation.",
        "process": "Our process is simple: 1. Consultation -> 2. Design Mockup -> 3. Development -> 4. Testing -> 5. Deployment. We keep you updated at every step!",
        "timeline": "A typical landing page takes 3-5 days, while full business websites usually take 10-15 days. Complex IoT or Cloud projects vary based on requirements.",
        "tech": "We use modern tech stacks like React.js, Python Flask, Node.js, Supabase for backend, and ESP32 for IoT hardware projects.",
        "location": "We are based in India and operate as a registered startup, serving clients globally.",
    }

    # Intent Detection & Responses
    if any(k in message for k in ["hello", "hi", "hey", "greetings"]):
        return "Hello! I'm the Phoenix Assistant. I can help you with questions about our services, pricing, or your next digital project. What's on your mind?"
    
    if any(k in message for k in ["service", "what do you do", "provide", "offer"]):
        return faqs["services"]
    
    if any(k in message for k in ["web", "website", "application", "ui", "ux"]):
        return faqs["web"]
    
    if any(k in message for k in ["iot", "smart", "automation", "hardware", "arduino", "esp32"]):
        return faqs["iot"]
    
    if any(k in message for k in ["cloud", "aws", "server", "azure", "database", "hosting"]):
        return faqs["cloud"]
    
    if any(k in message for k in ["price", "cost", "how much", "budget", "package", "plan", "pricing"]):
        return faqs["pricing"]
    
    if any(k in message for k in ["contact", "email", "phone", "reach", "support", "talk"]):
        return faqs["contact"]
    
    if any(k in message for k in ["job", "career", "hiring", "intern", "developer", "recruit"]):
        return faqs["hiring"]
    
    if any(k in message for k in ["who are you", "what is phoenix", "company", "startup", "info"]):
        return faqs["about"]

    if any(k in message for k in ["how do you work", "process", "steps", "workflow"]):
        return faqs["process"]

    if any(k in message for k in ["time", "how long", "duration", "days", "weeks"]):
        return faqs["timeline"]

    if any(k in message for k in ["tech", "language", "stack", "use", "platform"]):
        return faqs["tech"]

    if any(k in message for k in ["location", "where", "india", "based"]):
        return faqs["location"]

    if any(k in message for k in ["thank", "thanks", "great", "cool"]):
        return "You're welcome! We love helping businesses grow. Is there anything else you'd like to know about Phoenix Pixels Studios?"

    # Firmness / Pricing Logic
    if any(k in message for k in ["cheap", "lowest", "discount", "offer price", "negotiate"]):
        return "We can build fast or build right. We don’t do cheap shortcuts. Our pricing reflects real engineering, not templates."

    # Philosophy / Why Phoenix Logic
    if any(k in message for k in ["why phoenix", "what does phoenix mean", "origin of name"]):
        return "A phoenix doesn’t represent beauty. It represents rebuilding after failure. That’s how we approach technology—creating resilient systems that rise stronger."

    return "I'm here to help with anything regarding Phoenix Pixels Studios! You can ask me about our packages, the technologies we use, or our development process. What would you like to explore?"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
