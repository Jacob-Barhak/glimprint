from fastapi.testclient import TestClient
from app.main import app
import sys

client = TestClient(app)

def verify_workshops():
    print("Verifying Workshops List...")
    response = client.get("/activities/workshops")
    if response.status_code == 200:
        print("  Workshops List: OK")
        if "July 28" in response.text:
             print("  Found expected date string.")
    else:
        print(f"  Workshops List Failed: {response.status_code}")
        print(response.text[:500])

    # Get a slug
    import sqlite3
    conn = sqlite3.connect("app/content/glimprint.db")
    slug = conn.execute("SELECT slug FROM workshops LIMIT 1").fetchone()[0]
    conn.close()
    
    print(f"Verifying Workshop Detail ({slug})...")
    response = client.get(f"/activities/workshops/{slug}")
    if response.status_code == 200:
        print("  Workshop Detail: OK")
        if "Back to Workshops" in response.text:
             print("  Found Back button.")
    else:
        print(f"  Workshop Detail Failed: {response.status_code}")

if __name__ == "__main__":
    verify_workshops()
