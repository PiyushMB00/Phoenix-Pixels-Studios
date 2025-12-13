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
    body = f"Hello {client_name},\n\nThank you for contacting us. We appreciate you taking the time to reach out, Our team has received your message and will get back to you shortly with further information or assistance as needed.\nThank you once again for connecting with us.\n\nRegards,\nPhoenix Pixels Studio"

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

if __name__ == "__main__":
    app.run(debug=True, port=5000)
