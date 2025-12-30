from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import init_db, get_db
from auth import voter_login_required, admin_login_required
import admin_routes
import voter_routes
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DEBUG'] = os.getenv('DEBUG', False)

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

if __name__ == '__main__':
    if not os.path.exists("voting_system.db"):
        init_db()
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=app.config['DEBUG'], host='0.0.0.0', port=5000)