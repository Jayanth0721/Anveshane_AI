"""
Seed default users into the database
Run: python seed_users.py
"""
import uuid
from src.database import init_db, SessionLocal, User, UserRole
from src.auth import hash_password

def seed():
    init_db()
    db = SessionLocal()

    users = [
        {
            "id": str(uuid.uuid4()),
            "email": "admin@tender.com",
            "username": "admin",
            "hashed_password": hash_password("Admin@123"),
            "full_name": "Admin User",
            "company_name": "Govt Procurement",
            "role": UserRole.ADMIN,
        },
        {
            "id": str(uuid.uuid4()),
            "email": "contractor@tender.com",
            "username": "contractor",
            "hashed_password": hash_password("Contractor@123"),
            "full_name": "ABC Pvt Ltd",
            "company_name": "ABC Pvt Ltd",
            "role": UserRole.CONTRACTOR,
        },
        {
            "id": str(uuid.uuid4()),
            "email": "contractor2@tender.com",
            "username": "contractor2",
            "hashed_password": hash_password("Contractor@123"),
            "full_name": "XYZ Pvt Ltd",
            "company_name": "XYZ Pvt Ltd",
            "role": UserRole.CONTRACTOR,
        },
    ]

    created = 0
    updated = 0
    for u in users:
        exists = db.query(User).filter(User.email == u["email"]).first()
        if not exists:
            db.add(User(**u))
            created += 1
            print(f"✓ Created: {u['email']} ({u['role'].value})")
        else:
            exists.hashed_password = u["hashed_password"]
            updated += 1
            print(f"  Updated existing password for: {u['email']}")

    db.commit()
    db.close()

    print(f"\n{'='*40}")
    print(f"Done. {created} user(s) created.")
    print(f"{'='*40}")
    print("\nLogin credentials:")
    print("  Admin:      admin@tender.com     / Admin@123")
    print("  Contractor: contractor@tender.com / Contractor@123")

if __name__ == "__main__":
    seed()
