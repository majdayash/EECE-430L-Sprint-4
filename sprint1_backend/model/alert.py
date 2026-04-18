import datetime
from ..app import db, ma


class Alert(db.Model):
    __tablename__ = "alerts"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    direction = db.Column(db.String(20), nullable=False)  # "USD_LBP" or "LBP_USD"
    threshold = db.Column(db.Float, nullable=False)       # Exchange rate threshold
    condition = db.Column(db.String(10), nullable=False)  # "ABOVE" or "BELOW"
    triggered = db.Column(db.Boolean, default=False, nullable=False)  # Whether alert has been triggered
    triggered_at = db.Column(db.DateTime, nullable=True)  # When alert was triggered
    created_at = db.Column(db.DateTime)

    def __init__(self, user_id, direction, threshold, condition):
        super(Alert, self).__init__(
            user_id=user_id,
            direction=direction,
            threshold=threshold,
            condition=condition,
            triggered=False,
            triggered_at=None,
            created_at=datetime.datetime.now()
        )


class AlertSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Alert
        include_fk = True
        fields = ("id", "user_id", "direction", "threshold", "condition", "triggered", "triggered_at", "created_at")
        load_instance = True

alert_schema = AlertSchema()
alerts_schema = AlertSchema(many=True)
