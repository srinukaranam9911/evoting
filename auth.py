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

# REMOVE the duplicate hash_password function from here
# It should only exist in database.py

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(email, otp):
    try:
        # Get email configuration from environment variables
        smtp_server = os.getenv('EMAIL_SERVER', 'smtp.gmail.com')
        port = int(os.getenv('EMAIL_PORT', 587))
        sender_email = os.getenv('EMAIL_USERNAME')
        password = os.getenv('EMAIL_PASSWORD')
        from_email = os.getenv('EMAIL_FROM', sender_email)
        
        print(f"Attempting to send email via {smtp_server}:{port}")
        print(f"From: {sender_email}")
        print(f"To: {email}")
        
        if not sender_email or not password:
            error_msg = "Email credentials not configured. Please check your .env file."
            print(error_msg)
            return False
        
        # Create message
        message = MIMEMultipart("alternative")
        message["Subject"] = "VoteSecure - Email Verification OTP"
        message["From"] = from_email
        message["To"] = email
        
        # HTML email content
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #4361ee, #7209b7); color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .otp {{ font-size: 32px; font-weight: bold; color: #4361ee; text-align: center; margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
                .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>VoteSecure</h1>
                    <p>Email Verification</p>
                </div>
                <h2>Hello!</h2>
                <p>Your One-Time Password (OTP) for email verification is:</p>
                <div class="otp">{otp}</div>
                <p>This OTP will expire in 10 minutes.</p>
                <p>If you didn't request this verification, please ignore this email.</p>
                <div class="footer">
                    <p>&copy; 2023 VoteSecure. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        text = f"""
        VoteSecure - Email Verification
        
        Your One-Time Password (OTP) for email verification is: {otp}
        
        This OTP will expire in 10 minutes.
        
        If you didn't request this verification, please ignore this email.
        
        © 2023 VoteSecure. All rights reserved.
        """
        
        # Add both versions to the message
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        
        # Send email with better error handling
        print("Connecting to SMTP server...")
        server = smtplib.SMTP(smtp_server, port, timeout=30)
        print("Starting TLS...")
        server.starttls()
        print("Logging in...")
        server.login(sender_email, password)
        print("Sending email...")
        server.sendmail(from_email, email, message.as_string())
        server.quit()
        
        print(f"OTP email sent successfully to {email}")
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
        print(f"Unexpected error sending email: {str(e)}")
        return False

def log_audit(action, user_type, user_id, details=None):
    """Log user actions for security auditing"""
    with get_db() as db:
        db.execute('''
            INSERT INTO audit_logs (action, user_type, user_id, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?, ?)
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
        existing_votes = db.execute(
            'SELECT COUNT(*) FROM votes WHERE voter_id = ? AND election_id = ?',
            (voter_id, election_id)
        ).fetchone()[0]
        
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