from ..app import db, ma, bcrypt
import datetime


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(30), unique=True, nullable=False)
    hashed_password = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='USER')  # 'USER' or 'ADMIN'
    status = db.Column(db.String(20), nullable=False, default='ACTIVE')  # 'ACTIVE', 'SUSPENDED', 'BANNED'
    created_at = db.Column(db.DateTime)

    def __init__(self, user_name, password, role='USER'):
        super(User, self).__init__(
            user_name=user_name,
            role=role,
            status='ACTIVE',
            created_at=datetime.datetime.now()
        )
        self.hashed_password = bcrypt.generate_password_hash(password)


class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User
        fields = ("id", "user_name", "role", "status", "created_at")
        load_instance = True

user_schema = UserSchema()
