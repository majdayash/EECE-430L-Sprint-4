from ..app import db, ma
import datetime


class AuditLog(db.Model):
    """Immutable append-only audit log for tracking user actions and system events"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)  # Nullable for failed login attempts
    event_type = db.Column(db.String(50), nullable=False)
    success = db.Column(db.Boolean, nullable=False, default=True)
    metadata_json = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45), nullable=True)  # IPv6 max length
    created_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, event_type, success=True, user_id=None, metadata_json=None, ip=None):
        super(AuditLog, self).__init__(
            event_type=event_type,
            success=success,
            user_id=user_id,
            metadata_json=metadata_json,
            ip=ip,
            created_at=datetime.datetime.now()
        )


class AuditLogSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AuditLog
        fields = ("id", "user_id", "event_type", "success", "metadata_json", "ip", "created_at")
        load_instance = True

audit_log_schema = AuditLogSchema()
audit_logs_schema = AuditLogSchema(many=True)
