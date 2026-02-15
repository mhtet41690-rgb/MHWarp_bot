import sqlite3
import os

# ================= CONFIG =================
# Railway သုံးရင် "/data/users.db"
# Local / VPS စမ်းမယ်ဆို "users.db"
DB_PATH = "/data/users.db"   # ← Railway
# DB_PATH = "users.db"       # ← Local test

# ================= PREPARE FOLDER =================
# /data folder မရှိရင် auto create (Railway အတွက်အရေးကြီး)
db_dir = os.path.dirname(DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

# ================= CREATE DB =================
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    vip INTEGER DEFAULT 0,
    last INTEGER DEFAULT 0
)
""")

conn.commit()
conn.close()

print("✅ SQLite DB created successfully!")
print(f"📁 DB Path: {DB_PATH}")
