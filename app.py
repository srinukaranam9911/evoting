# app.py - Updated version

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

# Initialize database BEFORE registering blueprints
print("Initializing database...")
try:
    init_db()
    print("Database initialized successfully!")
except Exception as e:
    print(f"Warning: Database initialization error: {e}")
    print("The app will continue but database operations may fail.")

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

@app.route('/init-db')
def init_database_route():
    """Manual database initialization endpoint (for emergencies)"""
    try:
        from database import init_db
        init_db()
        return "Database initialized successfully!", 200
    except Exception as e:
        return f"Database initialization failed: {str(e)}", 500
    

@app.route('/setup', methods=['GET', 'POST'])
def setup_system():
    """Setup route to initialize database and create admin without shell"""
    from database import init_db, get_db, hash_password
    
    if request.method == 'GET':
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>VoteSecure Setup</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
                .container { background: #f5f5f5; padding: 30px; border-radius: 10px; }
                h1 { color: #333; }
                .btn { background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
                .btn:hover { background: #45a049; }
                .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 15px 0; }
                .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 15px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔐 VoteSecure Setup</h1>
                <p>This will initialize the database and create an admin account.</p>
                <form method="POST">
                    <p><strong>Admin Username:</strong><br>
                    <input type="text" name="username" value="admin" required></p>
                    <p><strong>Admin Password:</strong><br>
                    <input type="password" name="password" value="admin123" required></p>
                    <p><em>⚠️ Change this password after first login!</em></p>
                    <button type="submit" class="btn">Run Setup</button>
                </form>
            </div>
        </html>
        '''
    
    # POST request - run setup
    username = request.form.get('username', 'admin').strip()
    password = request.form.get('password', 'admin123').strip()
    
    messages = []
    
    try:
        # Step 1: Initialize database
        init_db()
        messages.append("✅ Database tables created successfully")
        
        # Step 2: Create admin account
        with get_db() as db:
            with db.cursor() as cursor:
                # Check if admin already exists
                cursor.execute("SELECT COUNT(*) FROM admins WHERE username = %s", (username,))
                if cursor.fetchone()['count'] == 0:
                    hashed_password = hash_password(password)
                    cursor.execute(
                        "INSERT INTO admins (username, password) VALUES (%s, %s)",
                        (username, hashed_password)
                    )
                    db.commit()
                    messages.append(f"✅ Admin account created: {username}")
                    messages.append("⚠️ IMPORTANT: Change this password after first login!")
                else:
                    messages.append(f"ℹ️ Admin '{username}' already exists")
        
        # Step 3: List all tables
        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                messages.append(f"📊 Database contains {len(tables)} tables")
                
                cursor.execute("SELECT COUNT(*) as count FROM admins")
                admin_count = cursor.fetchone()['count']
                messages.append(f"👤 Total admin accounts: {admin_count}")
        
        success = True
        
    except Exception as e:
        messages.append(f"❌ Error during setup: {str(e)}")
        success = False
    
    # Return results
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Setup Results</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .container {{ background: #f5f5f5; padding: 30px; border-radius: 10px; }}
            h1 {{ color: {'#155724' if success else '#721c24'}; }}
            .message {{ padding: 10px; margin: 5px 0; border-radius: 5px; }}
            .success {{ background: #d4edda; color: #155724; }}
            .info {{ background: #d1ecf1; color: #0c5460; }}
            .warning {{ background: #fff3cd; color: #856404; }}
            .error {{ background: #f8d7da; color: #721c24; }}
            .btn {{ background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{'✅ Setup Complete!' if success else '❌ Setup Failed'}</h1>
            <div class="messages">
                {"".join([f'<div class="message {("success" if "✅" in msg else "warning" if "⚠️" in msg else "info" if "ℹ️" in msg else "error" if "❌" in msg else "info")}">{msg}</div>' for msg in messages])}
            </div>
            <a href="/admin/login" class="btn">Go to Admin Login</a>
        </div>
    </html>
    '''


if __name__ == '__main__':
    app.run(debug=True)
