import datetime
from ..app import db, ma


class Wallet(db.Model):
    __tablename__ = "wallets"
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    usd_balance = db.Column(db.Float, nullable=False, default=0.0)
    lbp_balance = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)

    def __init__(self, user_id, usd_balance=0.0, lbp_balance=0.0):
        super(Wallet, self).__init__(
            user_id=user_id,
            usd_balance=usd_balance,
            lbp_balance=lbp_balance,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now()
        )


class WalletSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Wallet
        include_fk = True
        fields = ("user_id", "usd_balance", "lbp_balance", "created_at", "updated_at")
        load_instance = True

wallet_schema = WalletSchema()
wallets_schema = WalletSchema(many=True)
