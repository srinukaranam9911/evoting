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
    

# Add this to app.py (replace the previous /setup route if you have it)

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
                .container { background: #f5f5f5; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; }
                .form-group { margin-bottom: 20px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; color: #34495e; }
                input[type="text"], input[type="password"] {
                    width: 100%;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    font-size: 16px;
                    box-sizing: border-box;
                }
                .checkbox { margin: 15px 0; }
                .checkbox input { margin-right: 10px; }
                .btn { 
                    background: #3498db; 
                    color: white; 
                    padding: 12px 25px; 
                    border: none; 
                    border-radius: 5px; 
                    cursor: pointer; 
                    font-size: 16px; 
                    width: 100%;
                    transition: background 0.3s;
                }
                .btn:hover { background: #2980b9; }
                .btn-danger { background: #e74c3c; }
                .btn-danger:hover { background: #c0392b; }
                .warning { 
                    background: #fff3cd; 
                    color: #856404; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 20px 0; 
                    border-left: 4px solid #ffeaa7;
                }
                .info { 
                    background: #d1ecf1; 
                    color: #0c5460; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin: 20px 0;
                    border-left: 4px solid #bee5eb;
                }
                .note { 
                    background: #e8f4f8; 
                    padding: 10px; 
                    border-radius: 5px; 
                    margin-top: 10px;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔐 VoteSecure System Setup</h1>
                
                <div class="warning">
                    <strong>⚠️ Important Security Notice:</strong><br>
                    Do not use default credentials in production! Create a strong username and password.
                </div>
                
                <form method="POST">
                    <div class="form-group">
                        <label for="username">Admin Username:</label>
                        <input type="text" id="username" name="username" 
                               placeholder="Enter admin username" required
                               minlength="3" maxlength="50">
                        <div class="note">Must be at least 3 characters</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="password">Admin Password:</label>
                        <input type="password" id="password" name="password" 
                               placeholder="Enter strong password" required
                               minlength="8">
                        <div class="note">Must be at least 8 characters with letters and numbers</div>
                    </div>
                    
                    <div class="form-group">
                        <label for="confirm_password">Confirm Password:</label>
                        <input type="password" id="confirm_password" name="confirm_password" 
                               placeholder="Confirm password" required>
                    </div>
                    
                    <div class="checkbox">
                        <label>
                            <input type="checkbox" name="force_reset" value="1">
                            Reset existing admin accounts (deletes all existing admins)
                        </label>
                    </div>
                    
                    <div class="info">
                        <strong>What this will do:</strong><br>
                        1. Create all database tables if they don't exist<br>
                        2. Create your admin account<br>
                        3. Remove default admin if exists<br>
                    </div>
                    
                    <button type="submit" class="btn">🚀 Run System Setup</button>
                </form>
            </div>
            
            <script>
                // Client-side password validation
                document.querySelector('form').addEventListener('submit', function(e) {
                    const password = document.getElementById('password').value;
                    const confirm = document.getElementById('confirm_password').value;
                    
                    // Check password length
                    if (password.length < 8) {
                        alert('Password must be at least 8 characters long');
                        e.preventDefault();
                        return;
                    }
                    
                    // Check password contains both letters and numbers
                    if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
                        alert('Password must contain both letters and numbers');
                        e.preventDefault();
                        return;
                    }
                    
                    // Check passwords match
                    if (password !== confirm) {
                        alert('Passwords do not match!');
                        e.preventDefault();
                        return;
                    }
                });
            </script>
        </body>
        </html>
        '''
    
    # POST request - run setup with custom credentials
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    force_reset = request.form.get('force_reset') == '1'
    
    messages = []
    
    # Validate inputs
    if not username or len(username) < 3:
        messages.append("❌ Username must be at least 3 characters")
    
    if not password or len(password) < 8:
        messages.append("❌ Password must be at least 8 characters")
    elif not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        messages.append("❌ Password must contain both letters and numbers")
    
    if password != confirm_password:
        messages.append("❌ Passwords do not match")
    
    if messages:
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Setup Error</title></head>
        <body style="font-family: Arial; padding: 50px;">
            <div style="max-width: 600px; margin: 0 auto; background: #f8d7da; padding: 20px; border-radius: 5px;">
                <h2 style="color: #721c24;">❌ Setup Failed</h2>
                {"<br>".join([f'<p>{msg}</p>' for msg in messages])}
                <br>
                <a href="/setup" style="background: #6c757d; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go Back</a>
            </div>
        </body>
        </html>
        '''
    
    try:
        # Step 1: Initialize database
        init_db()
        messages.append("✅ Database tables created successfully")
        
        # Step 2: Create admin account
        with get_db() as db:
            with db.cursor() as cursor:
                # Delete existing admins if force reset is checked
                if force_reset:
                    cursor.execute("DELETE FROM admins")
                    db.commit()
                    messages.append("✅ Removed all existing admin accounts")
                
                # Check if admin already exists
                cursor.execute("SELECT COUNT(*) FROM admins WHERE username = %s", (username,))
                if cursor.fetchone()['count'] == 0:
                    hashed_password = hash_password(password)
                    cursor.execute(
                        "INSERT INTO admins (username, password) VALUES (%s, %s)",
                        (username, hashed_password)
                    )
                    db.commit()
                    messages.append(f"✅ Admin account created successfully")
                    messages.append(f"   👤 Username: <strong>{username}</strong>")
                    messages.append(f"   🔑 Password: <strong>{'*' * len(password)}</strong>")
                    messages.append("⚠️ IMPORTANT: Change this password after first login!")
                else:
                    messages.append(f"ℹ️ Admin '{username}' already exists")
                    messages.append("⚠️ No new admin was created")
        
        # Step 3: Show database status
        with get_db() as db:
            with db.cursor() as cursor:
                # List all tables
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                messages.append(f"📊 Database contains {len(tables)} tables")
                
                # Count total admins
                cursor.execute("SELECT COUNT(*) as count FROM admins")
                admin_count = cursor.fetchone()['count']
                messages.append(f"👤 Total admin accounts in system: {admin_count}")
                
                # List all admin usernames
                cursor.execute("SELECT username FROM admins ORDER BY username")
                admins = cursor.fetchall()
                if admins:
                    messages.append("📋 Admin accounts:")
                    for admin in admins:
                        messages.append(f"   • {admin['username']}")
        
        success = True
        
    except Exception as e:
        messages.append(f"❌ Error during setup: {str(e)}")
        success = False
    
    # Return results
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>{'Setup Complete' if success else 'Setup Failed'}</title>
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                max-width: 700px; 
                margin: 50px auto; 
                padding: 20px;
                background: #f8f9fa;
            }}
            .container {{ 
                background: white; 
                padding: 40px; 
                border-radius: 10px; 
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            h1 {{ 
                color: {'#155724' if success else '#721c24'}; 
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid {'#d4edda' if success else '#f8d7da'};
                padding-bottom: 15px;
            }}
            .message {{ 
                padding: 12px 15px; 
                margin: 8px 0; 
                border-radius: 5px; 
                border-left: 4px solid;
            }}
            .success {{ 
                background: #d4edda; 
                color: #155724;
                border-left-color: #c3e6cb;
            }}
            .info {{ 
                background: #d1ecf1; 
                color: #0c5460;
                border-left-color: #bee5eb;
            }}
            .warning {{ 
                background: #fff3cd; 
                color: #856404;
                border-left-color: #ffeaa7;
            }}
            .error {{ 
                background: #f8d7da; 
                color: #721c24;
                border-left-color: #f5c6cb;
            }}
            .btn-container {{ 
                text-align: center; 
                margin-top: 30px; 
                padding-top: 20px;
                border-top: 1px solid #eee;
            }}
            .btn {{ 
                background: #3498db; 
                color: white; 
                padding: 12px 25px; 
                text-decoration: none; 
                border-radius: 5px; 
                display: inline-block;
                margin: 0 10px;
                transition: background 0.3s;
            }}
            .btn:hover {{ 
                background: #2980b9; 
                text-decoration: none;
                color: white;
            }}
            .btn-login {{ 
                background: #27ae60;
            }}
            .btn-login:hover {{ 
                background: #219653;
            }}
            .security-note {{
                background: #fff8e1;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
                border: 1px dashed #ffd54f;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>{'✅ Setup Complete!' if success else '❌ Setup Failed'}</h1>
            
            <div class="messages">
                {"".join([f'<div class="message {("success" if "✅" in msg else "warning" if "⚠️" in msg else "info" if "ℹ️" in msg else "error" if "❌" in msg else "info")}">{msg}</div>' for msg in messages])}
            </div>
            
            {f'''
            <div class="security-note">
                <strong>🔒 Security Recommendations:</strong><br>
                1. Bookmark this page: <strong>{request.url_root}admin/login</strong><br>
                2. Delete this setup page after use (remove /setup route from app.py)<br>
                3. Change admin password regularly<br>
                4. Use different credentials for each environment (dev/staging/prod)
            </div>
            ''' if success else ''}
            
            <div class="btn-container">
                {f'<a href="/admin/login" class="btn btn-login">🔐 Go to Admin Login</a>' if success else ''}
                <a href="/setup" class="btn">🔄 Run Setup Again</a>
                <a href="/" class="btn">🏠 Go to Home</a>
            </div>
        </div>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)
