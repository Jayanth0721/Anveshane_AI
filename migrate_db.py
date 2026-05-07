"""
Migrate existing DB: add new columns to tenders table and citizen role support
Run: python migrate_db.py
"""
import sqlite3

conn = sqlite3.connect("tender_system.db")
cur = conn.cursor()

# Add new columns to tenders (ignore if already exist)
new_columns = [
    ("duration_days",      "INTEGER"),
    ("investment_amount",  "TEXT"),
    ("penalty_per_day",    "TEXT"),
    ("penalty_max_days",   "INTEGER DEFAULT 180"),
    ("work_location",      "TEXT"),
    ("awarded_to",         "TEXT"),
    ("awarded_at",         "DATETIME"),
]

existing = [row[1] for row in cur.execute("PRAGMA table_info(tenders)").fetchall()]

for col, col_type in new_columns:
    if col not in existing:
        cur.execute(f"ALTER TABLE tenders ADD COLUMN {col} {col_type}")
        print(f"  + Added column: tenders.{col}")
    else:
        print(f"  ✓ Already exists: tenders.{col}")

# Add citizen user if not present
import uuid, sys
sys.path.insert(0, ".")
conn.commit()
conn.close()

# Now use SQLAlchemy to add citizen user
from src.database import SessionLocal, User, UserRole, init_db
from src.auth import hash_password

init_db()
db = SessionLocal()

citizen_email = "citizen@tender.com"
exists = db.query(User).filter(User.email == citizen_email).first()
if not exists:
    db.add(User(
        id=str(uuid.uuid4()),
        email=citizen_email,
        username="citizen",
        hashed_password=hash_password("Citizen@123"),
        full_name="Public Citizen",
        company_name=None,
        role=UserRole.CITIZEN,
    ))
    db.commit()
    print("  + Created citizen user")
else:
    print("  ✓ Citizen user already exists")

db.close()

print("\n✅ Migration complete!")
print("\nAll credentials:")
print("  Admin:      admin@tender.com      / Admin@123")
print("  Contractor: contractor@tender.com  / Contractor@123")
print("  Citizen:    citizen@tender.com     / Citizen@123")
