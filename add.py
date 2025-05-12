from app import db
from models import User


admin_user = User(
    username="admin",
    email="admin@example.com",
    is_admin=True
)
admin_user.set_password("securepassword")  # Şifreyi hash'lemek için

db.session.add(admin_user)
db.session.commit()