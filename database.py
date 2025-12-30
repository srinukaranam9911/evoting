
import sqlite3
import os
from datetime import datetime
import hashlib

def get_db():
    conn = sqlite3.connect('voting_system.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    with get_db() as db:
        # Create constituencies table first
        db.execute('''
            CREATE TABLE IF NOT EXISTS constituencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                state TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create voters table WITHOUT aadhar_number
        db.execute('''
            CREATE TABLE IF NOT EXISTS voters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                constituency TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create admins table
        db.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create candidates table
        db.execute('''
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                party TEXT NOT NULL,
                constituency TEXT NOT NULL,
                photo_path TEXT,
                symbol_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create elections table
        db.execute('''
            CREATE TABLE IF NOT EXISTS elections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                constituency TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create votes table
        db.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id INTEGER NOT NULL,
                election_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (voter_id) REFERENCES voters (id),
                FOREIGN KEY (election_id) REFERENCES elections (id),
                FOREIGN KEY (candidate_id) REFERENCES candidates (id),
                UNIQUE(voter_id, election_id)
            )
        ''')
        
        # Create audit_logs table
        db.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                user_type TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add missing columns if they don't exist
        try:
            db.execute('ALTER TABLE elections ADD COLUMN description TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            db.execute('ALTER TABLE votes ADD COLUMN voted_at DATETIME DEFAULT CURRENT_TIMESTAMP')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Try to remove aadhar_number column if it exists
        try:
            db.execute('SELECT aadhar_number FROM voters LIMIT 1')
            print("Migrating voters table to remove aadhar_number...")
            
            db.execute('''
                CREATE TABLE voters_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    constituency TEXT NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            db.execute('''
                INSERT INTO voters_new (id, name, email, password, constituency, is_verified, created_at)
                SELECT id, name, email, password, constituency, is_verified, created_at FROM voters
            ''')
            
            db.execute('DROP TABLE voters')
            db.execute('ALTER TABLE voters_new RENAME TO voters')
            
            print("Voters table migrated successfully")
            
        except sqlite3.OperationalError:
            pass
        
        # Insert Andhra Pradesh constituencies
        ap_constituencies = [
            'Araku', 'Srikakulam', 'Vizianagaram', 'Visakhapatnam', 
            'Anakapalli', 'Kakinada', 'Amalapuram', 'Rajahmundry', 
            'Narasapuram', 'Eluru', 'Machilipatnam', 'Vijayawada', 
            'Guntur', 'Narasaraopet', 'Bapatla', 'Ongole', 
            'Nandyal', 'Kurnool', 'Anantapur', 'Hindupur', 
            'Kadapa', 'Nellore', 'Tirupati', 'Rajampet', 
            'Chittoor'
        ]
        
        for constituency in ap_constituencies:
            db.execute(
                'INSERT OR IGNORE INTO constituencies (name, state) VALUES (?, ?)',
                (constituency, 'Andhra Pradesh')
            )
        
        # Clear any existing sample data from candidates and elections
        db.execute('DELETE FROM candidates')
        db.execute('DELETE FROM elections')
        
        # Insert default admin if not exists
        existing_admin = db.execute(
            'SELECT * FROM admins WHERE username = ?', ('admin',)
        ).fetchone()
        
        if not existing_admin:
            db.execute(
                'INSERT INTO admins (username, password) VALUES (?, ?)',
                ('admin', hash_password('admin123'))
            )
            print("Default admin created: username='admin', password='admin123'")
        
        db.commit()

def get_constituencies():
    """Get all constituencies for dropdowns"""
    with get_db() as db:
        constituencies = db.execute(
            'SELECT name FROM constituencies ORDER BY name'
        ).fetchall()
        return [constituency['name'] for constituency in constituencies]
