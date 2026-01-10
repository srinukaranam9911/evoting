from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import init_db, get_db
from auth import voter_login_required, admin_login_required
import admin_routes
import voter_routes
import os
from datetime import datetime
from dotenv import load_dotenv
import atexit

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key-change-in-production')

# Configure upload folder for Render
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register blueprints
app.register_blueprint(admin_routes.admin_bp)
app.register_blueprint(voter_routes.voter_bp)

@app.route('/')
def index():
    # If user is logged in as voter, redirect to voter dashboard
    if 'voter_id' in session:
        return redirect(url_for('voter_routes.voter_dashboard'))
    # If user is logged in as admin, redirect to admin dashboard
    elif 'admin_id' in session:
        return redirect(url_for('admin_routes.admin_dashboard'))
    # Otherwise show the public home page
    return render_template('index.html')

@app.route('/about')
def about():
    # If user is logged in as voter, redirect to voter dashboard
    if 'voter_id' in session:
        return redirect(url_for('voter_routes.voter_dashboard'))
    # If user is logged in as admin, redirect to admin dashboard
    elif 'admin_id' in session:
        return redirect(url_for('admin_routes.admin_dashboard'))
    # Otherwise show the public about page
    return render_template('about.html')

@app.route('/how-it-works')
def how_it_works():
    # If user is logged in as voter, redirect to voter dashboard
    if 'voter_id' in session:
        return redirect(url_for('voter_routes.voter_dashboard'))
    # If user is logged in as admin, redirect to admin dashboard
    elif 'admin_id' in session:
        return redirect(url_for('admin_routes.admin_dashboard'))
    # Otherwise show the public how-it-works page
    return render_template('how_it_works.html')

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

def init_app():
    """Initialize the application"""
    # Initialize database
    init_db()
    
    # Ensure static/uploads directory exists
    if not os.path.exists('static/uploads'):
        os.makedirs('static/uploads', exist_ok=True)

@app.route('/init-db')
def init_database_route():
    if os.environ.get('FLASK_ENV') == 'production':
        return "Not allowed in production", 403
    
    from database import init_db
    init_db()
    return "Database initialized!", 200

if __name__ == '__main__':
    # Initialize database on startup
    try:
        from database import initialize_database
        initialize_database()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
    
    app.run(debug=True)
