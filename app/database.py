import sqlite3
import os
import libsql
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "db" / "glimprint.db"

def dict_factory(cursor, row):
    """
    Convert a database row to a dictionary.
    This ensures compatibility with existing code that expects dict-like access.
    """
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_db_connection():
    """
    Returns a database connection.
    Principally tries to connect to Turso if environment variables are set.
    Falls back to local SQLite database if Turso is not configured or fails.
    """
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")

    if turso_url and turso_token:
        try:
            # Connect to Turso using libsql
            conn = libsql.connect(database=turso_url, auth_token=turso_token)
            
            # libsql might not support row_factory directly on connection.
            # We can rely on the fact that existing code likely uses fetches.
            # However, if code expects dict-like objects from fetchone/fetchall, we need to ensure that.
            # Let's wrap the connection to return a cursor that produces dicts.
            
            original_cursor = conn.cursor

            def cursor_factory():
                cur = original_cursor()
                original_execute = cur.execute
                
                def execute_wrapper(*args, **kwargs):
                    cur.execute(*args, **kwargs)
                    return cur
                
                # Monkey patch fetches to return dicts
                original_fetchone = cur.fetchone
                original_fetchall = cur.fetchall
                
                def fetchone_wrapper():
                    row = original_fetchone()
                    if row is None: return None
                    return dict_factory(cur, row)

                def fetchall_wrapper():
                    rows = original_fetchall()
                    return [dict_factory(cur, row) for row in rows]
                
                cur.fetchone = fetchone_wrapper
                cur.fetchall = fetchall_wrapper
                return cur

            # This is a bit hacky but `libsql` python binding is minimal.
            # Better approach: Just use standard sqlite3 with remote URL if supported, 
            # but libsql package is specific. 
            # If the error is 'builtins.Connection' object has no attribute 'row_factory',
            # it means we can't set it. 
            
            # ALTERNATIVE: The `libsql` package often returns a custom object.
            # Let's try to see if we can just return the connection and handle row conversion 
            # in a utility, OR, more robustly, duplicate the logic.
            
            # Actually, check if `conn.execute` returns a cursor that describes columns.
            pass 
            
            # RE-TRYING SIMPLE APPROACH FIRST:
            # If row_factory attribute fails, we can't use it.
            # But we can try to wrap the connection to intercept cursor creation?
            
            class LibSQLConnectionWrapper:
                def __init__(self, wrapped_conn):
                    self.conn = wrapped_conn
                    
                def cursor(self):
                    return LibSQLCursorWrapper(self.conn.cursor())
                
                def execute(self, sql, params=()):
                    return self.cursor().execute(sql, params)

                def commit(self):
                    self.conn.commit()
                    
                def close(self):
                    self.conn.close()

            class LibSQLCursorWrapper:
                def __init__(self, wrapped_cursor):
                    self.cursor = wrapped_cursor
                
                def execute(self, sql, params=()):
                    self.cursor.execute(sql, params)
                    return self
                    
                def fetchone(self):
                    row = self.cursor.fetchone()
                    if row is None: return None
                    return dict_factory(self.cursor, row)
                
                def fetchall(self):
                    rows = self.cursor.fetchall()
                    return [dict_factory(self.cursor, row) for row in rows]
                
                @property
                def description(self):
                    return self.cursor.description
                
                @property
                def lastrowid(self):
                    return self.cursor.lastrowid

            return LibSQLConnectionWrapper(conn)

        except Exception as e:
            print(f"Warning: Failed to connect to Turso: {str(e)}")
            print("Falling back to local SQLite database.")

    # Fallback to local SQLite
    # Ensure directory exists
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
