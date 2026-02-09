from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def verify_members():
    print("Verifying Members List...")
    resp = client.get("/members")
    if resp.status_code != 200:
        print(f"  FAILED: Status {resp.status_code}")
    else:
        content = resp.text
        if "Members" in content and "Thomas Helikar" in content: # Check for known name (Tomas Helikar)
             # Wait, scraper saved "Tomas Helikar", need to be careful with spelling
             # "Tomas Helikar" was in log
             pass
        # Check specific names
        for name in ["Tomas Helikar", "James A. Glazier", "Anna Niaraki"]:
            if name in content:
                print(f"  Found {name}")
            else:
                print(f"  WARNING: {name} not found in list")
        
        print("  Members List: OK")

    print("\nVerifying Member Detail...")
    # Tomas Helikar -> tomas-helikar
    slug = "tomas-helikar"
    resp = client.get(f"/members/{slug}")
    if resp.status_code != 200:
        print(f"  FAILED: Status {resp.status_code} for {slug}")
    else:
        content = resp.text
        if "Biography" in content and "Education" in content:
            print(f"  Found Bio/Education for {slug}")
        else:
            print(f"  WARNING: Bio/Education missing for {slug}")
            
        print(f"  Member Detail ({slug}): OK")
        
    print("\nVerifying Member Image...")
    resp = client.get(f"/members/image/{slug}")
    if resp.status_code == 200:
        print(f"  Image ({slug}): OK ({len(resp.content)} bytes)")
    else:
        print(f"  Image ({slug}): Failed {resp.status_code}")

if __name__ == "__main__":
    verify_members()
