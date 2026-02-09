from jinja2 import Environment, FileSystemLoader
import sqlite3
import os

TEMPLATES_DIR = "app/templates"
DB_FILE = "app/content/glimprint.db"

env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

conn = sqlite3.connect(DB_FILE)
conn.row_factory = sqlite3.Row

# Render List
try:
    template = env.get_template("seminars.html")
    seminars = conn.execute("SELECT * FROM seminars").fetchall()
    rendered = template.render(seminars=seminars, request={})
    print("Seminars List Rendered Successfully")
    if "Emilia Luca" in rendered:
        print(" - Found sample seminar in list")
except Exception as e:
    print(f"Error rendering seminars list: {e}")

# Render Detail
try:
    slug = "emilia-luca-sunnybrook-research-institute-utricle-microcosm-human-balance"
    template = env.get_template("seminar_detail.html")
    seminar = conn.execute("SELECT * FROM seminars WHERE slug=?", (slug,)).fetchone()
    if seminar:
        rendered = template.render(seminar=seminar, request={})
        print("Seminar Detail Rendered Successfully")
        if "microcosm of human balance" in rendered:
            print(" - Found content in detail page")
    else:
        print("Sample seminar not found for detail render")
except Exception as e:
    print(f"Error rendering seminar detail: {e}")

conn.close()
