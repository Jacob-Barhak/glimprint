import argparse
import sys
from pathlib import Path
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv

# Add parent directory to sys.path to allow importing 'app'
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.database import get_db_connection
from app.auth import get_password_hash

# Load env vars
load_dotenv(BASE_DIR / ".env")

def create_admin(username, password, email, update=False):
    # Validate Email
    try:
        valid = validate_email(email)
        email = valid.email
    except EmailNotValidError as e:
        print(f"Error: Invalid email address '{email}': {str(e)}")
        sys.exit(1)

    conn = get_db_connection()
    hashed = get_password_hash(password)

    try:
        # Check if user exists
        existing = conn.execute("SELECT username FROM admins WHERE username = ?", (username,)).fetchone()
        
        if existing:
            if update:
                conn.execute(
                    "UPDATE admins SET password_hash = ?, email = ? WHERE username = ?",
                    (hashed, email, username)
                )
                conn.commit()
                print(f"Successfully updated admin user: {username} ({email})")
            else:
                print(f"Error: Admin user '{username}' already exists. Use --update to overwrite.")
                sys.exit(1)
        else:
            if update:
                print(f"Warning: User '{username}' does not exist, creating new user.")
            
            conn.execute(
                "INSERT INTO admins (username, password_hash, email) VALUES (?, ?, ?)",
                (username, hashed, email)
            )
            conn.commit()
            print(f"Successfully created admin user: {username} ({email})")
            
    except Exception as e:
        print(f"Database Error: {e}")
        sys.exit(1)
    finally:
        conn.close()

def delete_admin(username):
    conn = get_db_connection()
    try:
        cursor = conn.execute("DELETE FROM admins WHERE username = ?", (username,))
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Successfully deleted admin user: {username}")
        else:
            print(f"Error: Admin user '{username}' not found.")
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage admin users.")
    parser.add_argument("username", help="Admin username")
    parser.add_argument("password", nargs="?", help="Admin password (required for create/update)")
    parser.add_argument("email", nargs="?", help="Admin email address (required for create/update)")
    parser.add_argument("--delete", action="store_true", help="Delete the specified user")
    parser.add_argument("--update", action="store_true", help="Update password/email if user exists")

    args = parser.parse_args()

    if args.delete:
        delete_admin(args.username)
    else:
        if not args.password or not args.email:
            parser.error("password and email are required unless --delete is specified")
        create_admin(args.username, args.password, args.email, update=args.update)

