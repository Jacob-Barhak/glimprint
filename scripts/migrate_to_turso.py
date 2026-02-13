import os
import sqlite3
import libsql
from pathlib import Path
from dotenv import load_dotenv

# Load env from root
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

DB_PATH = BASE_DIR / "db" / "glimprint.db"

def migrate():
    print("--- Starting Migration to Turso ---")
    
    # 1. Check Configuration
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")
    
    if not turso_url or not turso_token:
        print("ERROR: TURSO_DATABASE_URL and TURSO_AUTH_TOKEN must be set in .env")
        return

    if not DB_PATH.exists():
        print(f"ERROR: Local database not found at {DB_PATH}")
        return

    # 2. Connect to Local DB
    print(f"Reading from local DB: {DB_PATH}")
    local_conn = sqlite3.connect(DB_PATH)
    local_conn.row_factory = sqlite3.Row
    
    # 3. Connect to Turso DB
    print(f"Connecting to Turso: {turso_url}")
    try:
        remote_conn = libsql.connect(database=turso_url, auth_token=turso_token)
    except Exception as e:
        print(f"ERROR: Failed to connect to Turso: {e}")
        return

    # 4. Get Tables
    tables = local_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'").fetchall()
    
    for table_row in tables:
        table_name = table_row["name"]
        print(f"\nProcessing table: {table_name}...")
        
        # Get Schema
        schema = local_conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'").fetchone()
        if schema:
            create_sql = schema["sql"]
            # Create Table on Remote (if not exists)
            try:
                # Basic CREATE IF NOT EXISTS might differ slightly if schema sql doesn't have it
                # But usually exact schema copy is fine if we handle "already exists" error or add IF NOT EXISTS
                if "IF NOT EXISTS" not in create_sql.upper():
                    create_sql = create_sql.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
                
                remote_conn.execute(create_sql)
                print(f"  - Schema ensured.")
            except Exception as e:
                print(f"  - Schema error: {e}")

        # Get Data
        rows = local_conn.execute(f"SELECT * FROM {table_name}").fetchall()
        if not rows:
            print("  - No data to copy.")
            continue
            
        print(f"  - Copying {len(rows)} rows...")
        
        # Insert Data
        # We need to build INSERT statement dynamically
        for row in rows:
            keys = row.keys()
            placeholders = ", ".join(["?"] * len(keys))
            columns = ", ".join(keys)
            values = tuple([row[k] for k in keys])
            
            sql = f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})"
            try:
                remote_conn.execute(sql, values)
            except Exception as e:
                print(f"  - Error inserting row: {e}")
        
        remote_conn.commit()
        print("  - Data copied.")

    print("\n--- Migration Complete ---")
    local_conn.close()
    remote_conn.close()

if __name__ == "__main__":
    migrate()
