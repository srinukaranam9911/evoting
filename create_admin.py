import sys
import os
import getpass
from dotenv import load_dotenv

load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import get_db, hash_password, init_db

def check_admin_exists(username):
    """Check if admin with given username already exists."""
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute(
                'SELECT username FROM admins WHERE username = %s',
                (username,)
            )
            return cursor.fetchone() is not None

def create_admin_account(username, password):
    """Create a new admin account in the database."""
    try:
        hashed_password = hash_password(password)
        
        with get_db() as db:
            with db.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO admins (username, password)
                    VALUES (%s, %s)
                ''', (username, hashed_password))
                db.commit()
        
        return True, "Admin account created successfully!"
    except Exception as e:
        return False, f"Error: {e}"

def list_existing_admins():
    """List all existing admin accounts."""
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute('SELECT id, username, created_at FROM admins ORDER BY created_at')
            admins = cursor.fetchall()
            
            if not admins:
                print("📭 No admin accounts found in the database.")
                return
            
            print("\n📋 Existing Admin Accounts:")
            print("-" * 60)
            print(f"{'ID':<3} {'Username':<15} {'Created At'}")
            print("-" * 60)
            
            for admin in admins:
                created_date = str(admin['created_at'])[:10] if admin['created_at'] else 'Unknown'
                print(f"{admin['id']:<3} {admin['username']:<15} {created_date}")

def delete_admin_account(username):
    """Delete an admin account by username."""
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute('DELETE FROM admins WHERE username = %s', (username,))
            db.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ Admin '{username}' deleted successfully.")
            else:
                print(f"❌ Admin '{username}' not found.")

def change_admin_password(username, new_password):
    """Change password for an existing admin account."""
    hashed_password = hash_password(new_password)
    
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute('UPDATE admins SET password = %s WHERE username = %s', 
                         (hashed_password, username))
            db.commit()
            
            if cursor.rowcount > 0:
                print(f"✅ Password for admin '{username}' updated successfully.")
            else:
                print(f"❌ Admin '{username}' not found.")

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
    
    return username, password

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

def main():
    """Main function to run the admin creation script."""
    print("🚀 Initializing Admin Management Console...")
    
    try:
        # Test database connection
        with get_db() as db:
            print("✅ PostgreSQL database connection established.")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print("Please check your DATABASE_URL environment variable.")
        sys.exit(1)
    
    while True:
        show_menu()
        choice = input("\nEnter your choice (1-6): ").strip()
        
        if choice == '1':
            # Create new admin
            username, password = get_user_input()
            
            # Check for conflicts
            if check_admin_exists(username):
                print(f"❌ Username '{username}' already exists.")
                continue
            
            # Create account
            success, message = create_admin_account(username, password)
            if success:
                print(f"✅ {message}")
                print(f"   👤 Username: {username}")
                print(f"   🔑 Password: {'*' * len(password)}")
            else:
                print(f"❌ {message}")
        
        elif choice == '2':
            # List existing admins
            list_existing_admins()
        
        elif choice == '3':
            # Delete admin account
            list_existing_admins()
            username = input("\nEnter username to delete: ").strip()
            if not username:
                print("❌ No username provided.")
                continue
            
            # Confirm deletion
            confirm = input(f"⚠️  Are you sure you want to delete admin '{username}'? (y/N): ").strip().lower()
            if confirm == 'y':
                delete_admin_account(username)
            else:
                print("❌ Deletion cancelled.")
        
        elif choice == '4':
            # Change admin password
            list_existing_admins()
            username = input("\nEnter username to change password: ").strip()
            if not username:
                print("❌ No username provided.")
                continue
            
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
            
            change_admin_password(username, new_password)
        
        elif choice == '5':
            # Initialize database tables
            try:
                init_db()
                print("✅ All database tables initialized successfully!")
            except Exception as e:
                print(f"❌ Error initializing database: {e}")
        
        elif choice == '6':
            print("👋 Exiting Admin Management Console. Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please enter 1-6.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Script interrupted by user. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
