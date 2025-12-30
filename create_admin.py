#!/usr/bin/env python3
"""
Admin Account Creation Script for VoteSecure
This script allows you to create admin accounts without running the main Flask application.
"""

import sqlite3
import hashlib
import getpass
import sys
import os
from datetime import datetime

def hash_password(password):
    """Hash a password for storing."""
    return hashlib.sha256(password.encode()).hexdigest()

def init_database():
    """Initialize database connection and ensure tables exist."""
    try:
        db = sqlite3.connect('voting_system.db')
        db.row_factory = sqlite3.Row
        
        # Create all necessary tables if they don't exist
        tables = [
            # Admins table
            '''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Voters table
            '''
            CREATE TABLE IF NOT EXISTS voters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                constituency TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                otp TEXT,
                otp_expiry DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Candidates table
            '''
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                party TEXT NOT NULL,
                constituency TEXT NOT NULL,
                photo BLOB,
                symbol BLOB,
                photo_path TEXT,
                symbol_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Elections table
            '''
            CREATE TABLE IF NOT EXISTS elections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                constituency TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                status TEXT DEFAULT 'upcoming',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Votes table
            '''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                election_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (voter_id) REFERENCES voters (id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES candidates (id) ON DELETE CASCADE,
                FOREIGN KEY (election_id) REFERENCES elections (id) ON DELETE CASCADE,
                UNIQUE(voter_id, election_id)
            )
            '''
        ]
        
        for table_sql in tables:
            db.execute(table_sql)
        
        db.commit()
        return db
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return None

def check_admin_exists(db, username, email):
    """Check if admin with given username or email already exists."""
    try:
        cursor = db.execute(
            'SELECT username, email FROM admins WHERE username = ? OR email = ?',
            (username, email)
        )
        existing = cursor.fetchall()
        
        conflicts = []
        for admin in existing:
            if admin['username'] == username:
                conflicts.append(f"Username '{username}'")
            if admin['email'] == email:
                conflicts.append(f"Email '{email}'")
        
        return conflicts
    except sqlite3.Error as e:
        print(f"❌ Error checking admin existence: {e}")
        return []

def create_admin_account(db, username, password, email):
    """Create a new admin account in the database."""
    try:
        hashed_password = hash_password(password)
        
        db.execute('''
            INSERT INTO admins (username, password, email)
            VALUES (?, ?, ?)
        ''', (username, hashed_password, email))
        
        db.commit()
        return True, "Admin account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Admin account already exists (username or email conflict)."
    except sqlite3.Error as e:
        return False, f"Database error: {e}"

def list_existing_admins(db):
    """List all existing admin accounts."""
    try:
        cursor = db.execute('SELECT id, username, email, created_at FROM admins ORDER BY created_at')
        admins = cursor.fetchall()
        
        if not admins:
            print("📭 No admin accounts found in the database.")
            return
        
        print("\n📋 Existing Admin Accounts:")
        print("-" * 60)
        print(f"{'ID':<3} {'Username':<15} {'Email':<25} {'Created At'}")
        print("-" * 60)
        
        for admin in admins:
            created_date = admin['created_at'][:10] if admin['created_at'] else 'Unknown'
            print(f"{admin['id']:<3} {admin['username']:<15} {admin['email']:<25} {created_date}")
    except sqlite3.Error as e:
        print(f"❌ Error listing admins: {e}")

def get_user_input():
    """Get admin account details from user input."""
    print("\n🎯 Create New Admin Account")
    print("=" * 40)
    
    # Get username
    while True:
        username = input("Enter username: ").strip()
        if username:
            if len(username) >= 3:
                break
            else:
                print("❌ Username must be at least 3 characters long.")
        else:
            print("❌ Username cannot be empty.")
    
    # Get email
    while True:
        email = input("Enter email: ").strip()
        if email:
            if '@' in email and '.' in email:
                break
            else:
                print("❌ Please enter a valid email address.")
        else:
            print("❌ Email cannot be empty.")
    
    # Get password
    while True:
        password = getpass.getpass("Enter password: ").strip()
        if not password:
            print("❌ Password cannot be empty.")
            continue
            
        if len(password) < 6:
            print("❌ Password must be at least 6 characters long.")
            continue
            
        confirm_password = getpass.getpass("Confirm password: ").strip()
        if password == confirm_password:
            break
        else:
            print("❌ Passwords do not match. Please try again.")
    
    return username, password, email

def delete_admin_account(db):
    """Delete an admin account by username."""
    list_existing_admins(db)
    
    username = input("\nEnter username to delete: ").strip()
    if not username:
        print("❌ No username provided.")
        return
    
    # Confirm deletion
    confirm = input(f"⚠️  Are you sure you want to delete admin '{username}'? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Deletion cancelled.")
        return
    
    try:
        cursor = db.execute('DELETE FROM admins WHERE username = ?', (username,))
        db.commit()
        
        if cursor.rowcount > 0:
            print(f"✅ Admin '{username}' deleted successfully.")
        else:
            print(f"❌ Admin '{username}' not found.")
    except sqlite3.Error as e:
        print(f"❌ Error deleting admin: {e}")

def change_admin_password(db):
    """Change password for an existing admin account."""
    list_existing_admins(db)
    
    username = input("\nEnter username to change password: ").strip()
    if not username:
        print("❌ No username provided.")
        return
    
    # Check if admin exists
    admin = db.execute('SELECT id FROM admins WHERE username = ?', (username,)).fetchone()
    if not admin:
        print(f"❌ Admin '{username}' not found.")
        return
    
    # Get new password
    while True:
        new_password = getpass.getpass("Enter new password: ").strip()
        if not new_password:
            print("❌ Password cannot be empty.")
            continue
            
        if len(new_password) < 6:
            print("❌ Password must be at least 6 characters long.")
            continue
            
        confirm_password = getpass.getpass("Confirm new password: ").strip()
        if new_password == confirm_password:
            break
        else:
            print("❌ Passwords do not match. Please try again.")
    
    try:
        hashed_password = hash_password(new_password)
        db.execute('UPDATE admins SET password = ? WHERE username = ?', (hashed_password, username))
        db.commit()
        print(f"✅ Password for admin '{username}' updated successfully.")
    except sqlite3.Error as e:
        print(f"❌ Error updating password: {e}")

def show_menu():
    """Display the main menu."""
    print("\n" + "="*50)
    print("🔐 VoteSecure - Admin Management Console")
    print("="*50)
    print("1. Create new admin account")
    print("2. List existing admin accounts")
    print("3. Delete admin account")
    print("4. Change admin password")
    print("5. Initialize Database (Create all tables)")
    print("6. Exit")
    print("-"*50)

def initialize_database_tables(db):
    """Initialize all database tables."""
    try:
        # Re-run the table creation
        tables = [
            # Admins table
            '''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Voters table
            '''
            CREATE TABLE IF NOT EXISTS voters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                constituency TEXT NOT NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                otp TEXT,
                otp_expiry DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Candidates table
            '''
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                party TEXT NOT NULL,
                constituency TEXT NOT NULL,
                photo BLOB,
                symbol BLOB,
                photo_path TEXT,
                symbol_path TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Elections table
            '''
            CREATE TABLE IF NOT EXISTS elections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                constituency TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                status TEXT DEFAULT 'upcoming',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            ''',
            # Votes table
            '''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                voter_id INTEGER NOT NULL,
                candidate_id INTEGER NOT NULL,
                election_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (voter_id) REFERENCES voters (id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES candidates (id) ON DELETE CASCADE,
                FOREIGN KEY (election_id) REFERENCES elections (id) ON DELETE CASCADE,
                UNIQUE(voter_id, election_id)
            )
            '''
        ]
        
        for table_sql in tables:
            db.execute(table_sql)
        
        db.commit()
        print("✅ All database tables initialized successfully!")
        return True
    except sqlite3.Error as e:
        print(f"❌ Error initializing database tables: {e}")
        return False

def main():
    """Main function to run the admin creation script."""
    print("🚀 Initializing Admin Management Console...")
    
    # Initialize database connection
    db = init_database()
    if not db:
        print("❌ Failed to initialize database connection.")
        sys.exit(1)
    
    print("✅ Database connection established.")
    
    while True:
        show_menu()
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            # Create new admin
            username, password, email = get_user_input()
            
            # Check for conflicts
            conflicts = check_admin_exists(db, username, email)
            if conflicts:
                print(f"❌ {' and '.join(conflicts)} already exist(s).")
                continue
            
            # Create account
            success, message = create_admin_account(db, username, password, email)
            if success:
                print(f"✅ {message}")
                print(f"   👤 Username: {username}")
                print(f"   📧 Email: {email}")
                print(f"   🔑 Password: {'*' * len(password)}")
            else:
                print(f"❌ {message}")
        
        elif choice == '2':
            # List existing admins
            list_existing_admins(db)
        
        elif choice == '3':
            # Delete admin account
            delete_admin_account(db)
        
        elif choice == '4':
            # Change admin password
            change_admin_password(db)
        
        elif choice == '5':
            # Initialize database tables
            if initialize_database_tables(db):
                print("✅ Database tables created successfully!")
        
        elif choice == '6':
            print("👋 Exiting Admin Management Console. Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please enter 1-6.")
        
        input("\nPress Enter to continue...")
    
    db.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Script interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)