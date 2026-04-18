import datetime
from ..app import db, ma


class Trade(db.Model):
    __tablename__ = "trades"
    
    id = db.Column(db.Integer, primary_key=True)
    offer_id = db.Column(db.Integer, db.ForeignKey('offers.id'), nullable=False)
    buyer_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    executed_at = db.Column(db.DateTime)
    
    # Snapshot fields from the offer at time of trade
    from_currency = db.Column(db.String(10), nullable=False)
    to_currency = db.Column(db.String(10), nullable=False)
    amount_from = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)

    def __init__(self, offer_id, buyer_user_id, seller_user_id, from_currency, 
                 to_currency, amount_from, rate):
        super(Trade, self).__init__(
            offer_id=offer_id,
            buyer_user_id=buyer_user_id,
            seller_user_id=seller_user_id,
            from_currency=from_currency,
            to_currency=to_currency,
            amount_from=amount_from,
            rate=rate,
            executed_at=datetime.datetime.now()
        )


class TradeSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Trade
        include_fk = True
        fields = ("id", "offer_id", "buyer_user_id", "seller_user_id", 
                  "executed_at", "from_currency", "to_currency", "amount_from", "rate")
        load_instance = True

trade_schema = TradeSchema()
trades_schema = TradeSchema(many=True)
