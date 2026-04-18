from ..app import db, ma
import datetime


class UserPreference(db.Model):
    __tablename__ = "user_preferences"
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    default_from_range_hours = db.Column(db.Integer, nullable=False, default=24)  # Default to 24 hours
    default_interval = db.Column(db.String(10), nullable=False, default="hour")  # "hour" or "day"
    default_direction = db.Column(db.String(20), nullable=False, default="USD_LBP")  # "USD_LBP" or "LBP_USD"
    updated_at = db.Column(db.DateTime)

    def __init__(self, user_id, default_from_range_hours=24, default_interval="hour", default_direction="USD_LBP"):
        super(UserPreference, self).__init__(
            user_id=user_id,
            default_from_range_hours=default_from_range_hours,
            default_interval=default_interval,
            default_direction=default_direction,
            updated_at=datetime.datetime.now()
        )


class UserPreferenceSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = UserPreference
        include_fk = True
        fields = ("user_id", "default_from_range_hours", "default_interval", "default_direction", "updated_at")
        load_instance = True

user_preference_schema = UserPreferenceSchema()
