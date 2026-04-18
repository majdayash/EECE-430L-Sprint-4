import datetime
from ..app import db, ma


class Offer(db.Model):
    __tablename__ = "offers"
    
    id = db.Column(db.Integer, primary_key=True)
    creator_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    from_currency = db.Column(db.String(10), nullable=False)  # "USD" or "LBP"
    to_currency = db.Column(db.String(10), nullable=False)    # "USD" or "LBP"
    amount_from = db.Column(db.Float, nullable=False)         # Amount of from_currency
    rate = db.Column(db.Float, nullable=False)                # Exchange rate (LBP per USD)
    status = db.Column(db.String(20), nullable=False, default="OPEN")  # OPEN, ACCEPTED, CANCELED
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    def __init__(self, creator_user_id, from_currency, to_currency, amount_from, rate):
        super(Offer, self).__init__(
            creator_user_id=creator_user_id,
            from_currency=from_currency,
            to_currency=to_currency,
            amount_from=amount_from,
            rate=rate,
            status="OPEN",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )


class OfferSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Offer
        include_fk = True
        fields = ("id", "creator_user_id", "from_currency", "to_currency", 
                  "amount_from", "rate", "status", "created_at", "updated_at")
        load_instance = True

offer_schema = OfferSchema()
offers_schema = OfferSchema(many=True)
