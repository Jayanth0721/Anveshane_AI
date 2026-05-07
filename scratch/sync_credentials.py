
import uuid
import sqlite3
from src.database import SessionLocal, User, UserRole, init_db
from src.auth import hash_password

def update_db():
    init_db()
    db = SessionLocal()

    users_to_sync = [
        {
            "email": "admin@tender.com",
            "username": "admin",
            "password": "Admin@123",
            "full_name": "Admin User",
            "role": UserRole.ADMIN,
            "company_name": "Procurement Dept"
        },
        {
            "email": "contractor@tender.com",
            "username": "contractor",
            "password": "Contractor@123",
            "full_name": "ABC Construction",
            "role": UserRole.CONTRACTOR,
            "company_name": "ABC Pvt Ltd"
        },
        {
            "email": "contractor2@tender.com",
            "username": "contractor2",
            "password": "Contractor@123",
            "full_name": "XYZ Construction",
            "role": UserRole.CONTRACTOR,
            "company_name": "XYZ Pvt Ltd"
        },
        {
            "email": "citizen@tender.com",
            "username": "citizen",
            "password": "Citizen@123",
            "full_name": "Citizen Observer",
            "role": UserRole.CITIZEN,
            "company_name": "Public"
        },
        {
            "email": "test_user1@example.com",
            "username": "test_user1",
            "password": "User@123",
            "full_name": "Test User One",
            "role": UserRole.CITIZEN,
            "company_name": "Test Group"
        }
    ]

    for u_data in users_to_sync:
        user = db.query(User).filter(User.email == u_data["email"]).first()
        if user:
            # Update password and role
            user.hashed_password = hash_password(u_data["password"])
            user.role = u_data["role"]
            user.username = u_data["username"]
            print(f"Updated user: {u_data['email']}")
        else:
            # Create new
            new_user = User(
                id=str(uuid.uuid4()),
                email=u_data["email"],
                username=u_data["username"],
                hashed_password=hash_password(u_data["password"]),
                full_name=u_data["full_name"],
                company_name=u_data["company_name"],
                role=u_data["role"]
            )
            db.add(new_user)
            print(f"Created user: {u_data['email']}")

    db.commit()
    db.close()
    print("Database sync complete.")

if __name__ == "__main__":
    update_db()
