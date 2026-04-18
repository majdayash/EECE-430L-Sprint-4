import datetime
from ..app import db, ma


class RateAnomaly(db.Model):
    __tablename__ = "rate_anomalies"
    
    id = db.Column(db.Integer, primary_key=True)
    direction = db.Column(db.String(20), nullable=False)  # "USD_LBP" or "LBP_USD"
    previous_rate = db.Column(db.Float, nullable=False)
    new_rate = db.Column(db.Float, nullable=False)
    percent_change = db.Column(db.Float, nullable=False)
    time_diff_minutes = db.Column(db.Float, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)
    flagged_at = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    
    def __init__(self, direction, previous_rate, new_rate, percent_change, time_diff_minutes, transaction_id=None, reason=""):
        super(RateAnomaly, self).__init__(
            direction=direction,
            previous_rate=previous_rate,
            new_rate=new_rate,
            percent_change=percent_change,
            time_diff_minutes=time_diff_minutes,
            transaction_id=transaction_id,
            flagged_at=datetime.datetime.now(),
            reason=reason
        )


class RateAnomalySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = RateAnomaly
        include_fk = True
        fields = ("id", "direction", "previous_rate", "new_rate", "percent_change", 
                  "time_diff_minutes", "transaction_id", "flagged_at", "reason")
        load_instance = True

rate_anomaly_schema = RateAnomalySchema()
rate_anomalies_schema = RateAnomalySchema(many=True)
