import datetime
from ..app import db, ma


class RateSource(db.Model):
    __tablename__ = "rate_sources"
    
    id = db.Column(db.Integer, primary_key=True)
    direction = db.Column(db.String(20), nullable=False)  # "USD_LBP" or "LBP_USD"
    rate = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), nullable=False)  # "INTERNAL_COMPUTED" or "EXTERNAL_API"
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=True)  # If from transaction
    computed_at = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, direction, rate, source, transaction_id=None):
        super(RateSource, self).__init__(
            direction=direction,
            rate=rate,
            source=source,
            transaction_id=transaction_id,
            computed_at=datetime.datetime.now()
        )


class RateSourceSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = RateSource
        include_fk = True
        fields = ("id", "direction", "rate", "source", "transaction_id", "computed_at")
        load_instance = True

rate_source_schema = RateSourceSchema()
rate_sources_schema = RateSourceSchema(many=True)
