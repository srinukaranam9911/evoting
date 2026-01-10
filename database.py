import os
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

# Fix old Render postgres:// URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_db():
    """Get PostgreSQL database connection (local + Render safe)"""
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")

        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set")

        # Fix old postgres:// URLs
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

        # Detect local vs Render
        is_local = "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL

        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=RealDictCursor,
            sslmode="disable" if is_local else "require"
        )
        return conn

    except Exception as e:
        print(f"Database connection error: {e}")
        raise


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Initialize PostgreSQL database schema"""
    with get_db() as db:
        with db.cursor() as cursor:

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS constituencies (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    state VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voters (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    constituency VARCHAR(255) NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    party VARCHAR(255) NOT NULL,
                    constituency VARCHAR(255) NOT NULL,
                    photo_path TEXT,
                    symbol_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS elections (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    constituency VARCHAR(255) NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    id SERIAL PRIMARY KEY,
                    voter_id INTEGER NOT NULL,
                    election_id INTEGER NOT NULL,
                    candidate_id INTEGER NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (voter_id, election_id),
                    FOREIGN KEY (voter_id) REFERENCES voters (id) ON DELETE CASCADE,
                    FOREIGN KEY (election_id) REFERENCES elections (id) ON DELETE CASCADE,
                    FOREIGN KEY (candidate_id) REFERENCES candidates (id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(255) NOT NULL,
                    user_type VARCHAR(50) NOT NULL,
                    user_id INTEGER NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Andhra Pradesh constituencies
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
                cursor.execute(
                    """
                    INSERT INTO constituencies (name, state)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    (constituency, "Andhra Pradesh")
                )

            # REMOVED DEFAULT ADMIN - No admin is created automatically
            print("✅ Database initialized. No default admin created.")

        db.commit()


def get_constituencies():
    """Fetch constituencies"""
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT name FROM constituencies ORDER BY name")
            rows = cursor.fetchall()
            return [row["name"] for row in rows]