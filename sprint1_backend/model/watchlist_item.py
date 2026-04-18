import datetime
from ..app import db, ma


class WatchlistItem(db.Model):
    __tablename__ = "watchlist_items"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # Type of watchlist item (e.g., "rate_threshold", "direction")
    payload_json = db.Column(db.Text, nullable=False)  # JSON string containing item-specific data
    created_at = db.Column(db.DateTime)

    def __init__(self, user_id, type, payload_json):
        super(WatchlistItem, self).__init__(
            user_id=user_id,
            type=type,
            payload_json=payload_json,
            created_at=datetime.datetime.now()
        )


class WatchlistItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = WatchlistItem
        include_fk = True
        fields = ("id", "user_id", "type", "payload_json", "created_at")
        load_instance = True

watchlist_item_schema = WatchlistItemSchema()
watchlist_items_schema = WatchlistItemSchema(many=True)
