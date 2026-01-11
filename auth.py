from functools import wraps
from flask import session, redirect, url_for, flash, request
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import string
from datetime import datetime, timedelta
from database import get_db, hash_password  # Import from database
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(email, otp):
    """Send OTP email with SSL on port 465 (works on Render)"""
    try:
        # Get email configuration from environment variables
        smtp_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        port = int(os.getenv('EMAIL_PORT', 465))  # Changed to 465
        sender_email = os.getenv('EMAIL_USERNAME')
        password = os.getenv('EMAIL_PASSWORD')
        from_email = os.getenv('EMAIL_FROM', sender_email)
        
        print("=" * 50)
        print("📧 EMAIL SENDING DEBUG INFO")
        print("=" * 50)
        print(f"SMTP Server: {smtp_server}")
        print(f"Port: {port} (SSL)")
        print(f"Sender Email: {'✓ SET' if sender_email else '✗ MISSING'}")
        print(f"Password: {'✓ SET' if password else '✗ MISSING'}")
        print(f"Recipient: {email}")
        print("=" * 50)
        
        if not sender_email or not password:
            print("❌ Email credentials missing")
            return False
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "VoteSecure - Email Verification OTP"
        message["From"] = from_email
        message["To"] = email
        
        # HTML email content (same as before)
        html = f""" ... (keep your HTML content) ... """
        text = f""" ... (keep your text content) ... """
        
        # Add both versions to the message
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        
        # Send email with SSL (not TLS)
        print(f"🔌 Connecting to SMTP server with SSL on port {port}...")
        try:
            # Use SMTP_SSL instead of SMTP for port 465
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=30)
            print("✅ Connected to SMTP server (SSL)")
        except Exception as e:
            print(f"❌ Failed to connect with SSL: {e}")
            return False
        
        try:
            print("🔑 Logging in...")
            server.login(sender_email, password)
            print("✅ Login successful")
        except smtplib.SMTPAuthenticationError:
            print("❌ Authentication failed")
            server.quit()
            return False
        
        try:
            print("📤 Sending email...")
            server.sendmail(from_email, email, message.as_string())
            print(f"✅ Email sent successfully to {email}")
            server.quit()
            return True
        except Exception as e:
            print(f"❌ Failed to send email: {e}")
            server.quit()
            return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
def log_audit(action, user_type, user_id, details=None):
    """Log user actions for security auditing"""
    with get_db() as db:
        with db.cursor() as cursor:  # Create a cursor
            cursor.execute('''
                INSERT INTO audit_logs (action, user_type, user_id, ip_address, user_agent, details)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (action, user_type, user_id, request.remote_addr, 
                  request.headers.get('User-Agent'), details))
            db.commit()

def voter_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'voter_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('voter_routes.voter_login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please log in as admin to access this page', 'error')
            return redirect(url_for('admin_routes.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def check_fraud_risk(voter_id, election_id, action):
    """Simple fraud detection - check for multiple voting attempts"""
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM votes WHERE voter_id = %s AND election_id = %s',
                (voter_id, election_id)
            )
            result = cursor.fetchone()
            existing_votes = result['count'] if result else 0
            
            if existing_votes > 0:
                return False, "You have already voted in this election."
    
    return True, "OK"

def send_winner_email(email, subject, text_content, html_content):
    """Send election winner email"""
    try:
        # Get email configuration from environment variables
        smtp_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        port = int(os.getenv('EMAIL_PORT', 587))
        sender_email = os.getenv('EMAIL_USERNAME')
        password = os.getenv('EMAIL_PASSWORD')
        from_email = os.getenv('EMAIL_FROM', sender_email)
        
        print(f"Attempting to send winner email via {smtp_server}:{port}")
        print(f"From: {sender_email}")
        print(f"To: {email}")
        
        if not sender_email or not password:
            error_msg = "Email credentials not configured. Please check your .env file."
            print(error_msg)
            return False
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = from_email
        message["To"] = email
        
        # Add both versions to the message
        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))
        
        # Send email
        print("Connecting to SMTP server...")
        server = smtplib.SMTP(smtp_server, port, timeout=30)
        print("Starting TLS...")
        server.starttls()
        print("Logging in...")
        server.login(sender_email, password)
        print("Sending winner email...")
        server.sendmail(from_email, email, message.as_string())
        server.quit()
        
        print(f"Winner email sent successfully to {email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP Authentication Error: {e}")
        print("Please check your email and app password in .env file")
        return False
    except smtplib.SMTPConnectError as e:
        print(f"SMTP Connection Error: {e}")
        print("Please check your internet connection and SMTP server settings")
        return False
    except smtplib.SMTPException as e:
        print(f"SMTP Error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error sending winner email: {str(e)}")
        return False
