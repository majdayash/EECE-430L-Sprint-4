from ..app import db, ma
import datetime


class Notification(db.Model):
    """User notifications for alerts, trades, and offers"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'alert_triggered', 'trade_completed', 'offer_status_changed'
    message = db.Column(db.String(255), nullable=False)
    metadata_json = db.Column(db.Text, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, user_id, type, message, metadata_json=None):
        super(Notification, self).__init__(
            user_id=user_id,
            type=type,
            message=message,
            metadata_json=metadata_json,
            read_at=None,
            created_at=datetime.datetime.now()
        )


class NotificationSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Notification
        fields = ("id", "user_id", "type", "message", "metadata_json", "read_at", "created_at")
        load_instance = True

notification_schema = NotificationSchema()
notifications_schema = NotificationSchema(many=True)
