from flask import Flask, request, jsonify, abort, make_response
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_bcrypt import Bcrypt
import jwt
import datetime
import os
import csv
import io
from flask_cors import CORS
import logging
from werkzeug.exceptions import HTTPException
from dateutil import parser
from sqlalchemy import func
from functools import wraps


from .db_config import DB_CONFIG 

app = Flask(__name__)
load_dotenv()

# CORS for common local dev servers (Live Server, React, Vite, etc.)
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5501",
    "http://127.0.0.1:5501",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]
CORS(
    app,
    resources={r"/*": {"origins": allowed_origins}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.logger.setLevel(logging.INFO)

#Config
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
SECRET_KEY = os.getenv("JWT_SECRET_KEY") or app.config["SECRET_KEY"]

app.config["SQLALCHEMY_DATABASE_URI"] = DB_CONFIG
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

#Extensions
db = SQLAlchemy(app)
ma = Marshmallow(app)
bcrypt = Bcrypt(app)

# Check both config and environment for rate limiting
def is_rate_limiting_enabled():
    # Check environment variable first (for tests)
    env_enabled = os.getenv('RATELIMIT_ENABLED', 'True')
    if env_enabled.lower() == 'false':
        return False
    # Check app config
    return app.config.get("RATELIMIT_ENABLED", True)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["60 per minute"],
    storage_uri="memory://",
    enabled=lambda: is_rate_limiting_enabled()  # Lambda wrapper for proper evaluation
)

#Import models AFTER extensions 
from .model.user import User, user_schema
from .model.transaction import Transaction, transaction_schema, transactions_schema
from .model.offer import Offer, offer_schema, offers_schema
from .model.trade import Trade, trade_schema, trades_schema
from .model.alert import Alert, alert_schema, alerts_schema
from .model.watchlist_item import WatchlistItem, watchlist_item_schema, watchlist_items_schema
from .model.user_preference import UserPreference, user_preference_schema
from .model.audit_log import AuditLog, audit_log_schema, audit_logs_schema
from .model.notification import Notification, notification_schema, notifications_schema
from .model.rate_source import RateSource, rate_source_schema, rate_sources_schema
from .model.rate_anomaly import RateAnomaly, rate_anomaly_schema, rate_anomalies_schema
from .model.wallet import Wallet, wallet_schema, wallets_schema
import json

# Audit logging helper
def log_audit_event(event_type, success=True, user_id=None, metadata=None):
    """Create an immutable audit log entry"""
    try:
        ip = request.remote_addr
        metadata_json = json.dumps(metadata) if metadata else None
        
        audit_log = AuditLog(
            event_type=event_type,
            success=success,
            user_id=user_id,
            metadata_json=metadata_json,
            ip=ip
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Failed to log audit event: {e}")
        # Don't fail the main operation if audit logging fails
        pass

# Notification helper
def create_notification(user_id, type, message, metadata=None):
    """Create a notification for a user"""
    try:
        metadata_json = json.dumps(metadata) if metadata else None
        
        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            metadata_json=metadata_json
        )
        db.session.add(notification)
        db.session.commit()
        app.logger.info(f"Created notification for user_id={user_id}: {type}")
    except Exception as e:
        app.logger.error(f"Failed to create notification: {e}")
        # Don't fail the main operation if notification creation fails
        pass

# Alert checking job (mock async)
def check_and_trigger_alerts():
    """Check all active alerts and trigger notifications if conditions are met"""
    try:
        # Get current rates (last 3 hours of transactions)
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=3)
        recent_transactions = Transaction.query.filter(Transaction.added_date >= cutoff).all()
        
        if not recent_transactions:
            return  # No recent data to compute rates
        
        # Compute rates for both directions
        usd_to_lbp_txs = [t for t in recent_transactions if t.usd_to_lbp]
        lbp_to_usd_txs = [t for t in recent_transactions if not t.usd_to_lbp]
        
        rates = {}
        if usd_to_lbp_txs:
            avg_rate = sum(t.lbp_amount / t.usd_amount for t in usd_to_lbp_txs) / len(usd_to_lbp_txs)
            rates['USD_LBP'] = avg_rate
        
        if lbp_to_usd_txs:
            avg_rate = sum(t.lbp_amount / t.usd_amount for t in lbp_to_usd_txs) / len(lbp_to_usd_txs)
            rates['LBP_USD'] = avg_rate
        
        # Check all active alerts
        active_alerts = Alert.query.filter_by(triggered=False).all()
        
        for alert in active_alerts:
            direction_rate = rates.get(alert.direction)
            if direction_rate is None:
                continue  # No data for this direction
            
            # Check if alert should trigger
            should_trigger = False
            if alert.condition == "ABOVE" and direction_rate >= alert.threshold:
                should_trigger = True
            elif alert.condition == "BELOW" and direction_rate <= alert.threshold:
                should_trigger = True
            
            if should_trigger:
                # Mark alert as triggered
                alert.triggered = True
                alert.triggered_at = datetime.datetime.now()
                
                # Create notification
                message = f"Alert triggered: {alert.direction} rate is {direction_rate:.2f} (threshold: {alert.threshold:.2f})"
                create_notification(
                    user_id=alert.user_id,
                    notification_type="alert_triggered",
                    message=message,
                    metadata={
                        "alert_id": alert.id,
                        "direction": alert.direction,
                        "threshold": float(alert.threshold),
                        "current_rate": float(direction_rate)
                    }
                )
                
                app.logger.info(f"Alert triggered: alert_id={alert.id} for user_id={alert.user_id}")
        
        db.session.commit()
        
    except Exception as e:
        app.logger.error(f"Error in check_and_trigger_alerts: {e}")
        db.session.rollback()


# Outlier detection configuration
OUTLIER_THRESHOLD_PERCENT = 20.0  # Flag if rate changes > 20% 
OUTLIER_TIME_WINDOW_MINUTES = 10.0  # Within 10 minutes


def detect_rate_outlier(usd_amount, lbp_amount, usd_to_lbp):
    """
    Detect if a new transaction would create an outlier rate.
    Returns (is_outlier: bool, anomaly_info: dict or None)
    """
    try:
        new_rate = lbp_amount / usd_amount
        direction = "USD_LBP" if usd_to_lbp else "LBP_USD"
        
        # Get the most recent rate in this direction
        cutoff = datetime.datetime.now() - datetime.timedelta(minutes=OUTLIER_TIME_WINDOW_MINUTES)
        
        # Get recent transactions for this direction
        if usd_to_lbp:
            recent_txs = Transaction.query.filter(
                Transaction.usd_to_lbp == True,
                Transaction.added_date >= cutoff
            ).order_by(Transaction.added_date.desc()).all()
        else:
            recent_txs = Transaction.query.filter(
                Transaction.usd_to_lbp == False,
                Transaction.added_date >= cutoff
            ).order_by(Transaction.added_date.desc()).all()
        
        if not recent_txs:
            # No recent data, cannot determine outlier
            return False, None
        
        # Calculate average rate from recent transactions
        avg_rate = sum(tx.lbp_amount / tx.usd_amount for tx in recent_txs) / len(recent_txs)
        
        # Calculate percent change
        percent_change = abs((new_rate - avg_rate) / avg_rate * 100)
        
        # Check if it exceeds threshold
        if percent_change > OUTLIER_THRESHOLD_PERCENT:
            # Get time difference to most recent transaction
            most_recent = recent_txs[0]
            time_diff = (datetime.datetime.now() - most_recent.added_date).total_seconds() / 60.0
            
            anomaly_info = {
                "direction": direction,
                "previous_rate": avg_rate,
                "new_rate": new_rate,
                "percent_change": percent_change,
                "time_diff_minutes": time_diff,
                "reason": f"Rate change of {percent_change:.2f}% exceeds threshold of {OUTLIER_THRESHOLD_PERCENT}% within {OUTLIER_TIME_WINDOW_MINUTES} minutes"
            }
            return True, anomaly_info
        
        return False, None
        
    except Exception as e:
        app.logger.error(f"Error in detect_rate_outlier: {e}")
        return False, None


def record_rate_source(direction, rate, source="INTERNAL_COMPUTED", transaction_id=None):
    """Record a rate computation in the rate_sources table"""
    try:
        rate_source = RateSource(
            direction=direction,
            rate=rate,
            source=source,
            transaction_id=transaction_id
        )
        db.session.add(rate_source)
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error recording rate source: {e}")
        db.session.rollback()


# Auth helpers
def get_user_from_token():
    """Get User object from Bearer token and check if banned"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401, description="Missing or invalid Bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        abort(401, description="Invalid Bearer token")

    user_id = payload.get("sub")
    if not user_id:
        abort(401, description="Invalid Bearer token")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        abort(401, description="Invalid Bearer token")
    
    # Query user from database
    user = User.query.get(user_id)
    if not user:
        abort(401, description="Invalid user")
    
    # Check if user is banned
    if user.status == 'BANNED':
        abort(401, description="Your account has been banned")
    
    return user

def get_user_id_from_token() -> int:
    """Get user ID from token and check if banned"""
    user = get_user_from_token()
    return user.id

def get_user_id_from_optional_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return None
    if not auth_header.startswith("Bearer "):
        abort(401, description="Missing or invalid Bearer token")

    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        abort(401, description="Invalid Bearer token")

    user_id = payload.get("sub")
    if not user_id:
        abort(401, description="Invalid Bearer token")

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        abort(401, description="Invalid Bearer token")
    
    # Check if user is banned
    user = User.query.get(user_id)
    if user and user.status == 'BANNED':
        abort(401, description="Your account has been banned")
    
    return user_id

def create_token(user_id: int) -> str:
    payload = {
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=4),
        "iat": datetime.datetime.utcnow(),
        "sub": str(user_id)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token.decode("utf-8") if isinstance(token, bytes) else token

def require_role(required_role):
    """Decorator to require specific role for endpoint access"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_user_from_token()
            
            # Check if user has required role
            if user.role != required_role:
                abort(403, description="Insufficient permissions")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes 
@app.route("/transaction", methods=["POST"])
@limiter.limit("5 per minute")
def add_transaction():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    if "usd_amount" not in data or "lbp_amount" not in data:
        return jsonify({"error": "Missing field: usd_amount or lbp_amount"}), 400

    try:
        usd_amount = float(data["usd_amount"])
        lbp_amount = float(data["lbp_amount"])
    except (TypeError, ValueError):
        return jsonify({"error": "usd_amount and lbp_amount must be numbers"}), 400

    if usd_amount <= 0 or lbp_amount <= 0:
        return jsonify({"error": "Amounts must be > 0"}), 400

    usd_to_lbp = None
    transaction_type = data.get("transaction_type")
    if transaction_type is not None:
        if transaction_type not in ("usd-to-lbp", "lbp-to-usd"):
            return jsonify({"error": "transaction_type must be 'usd-to-lbp' or 'lbp-to-usd'"}), 400
        usd_to_lbp = (transaction_type == "usd-to-lbp")
    elif "usd_to_lbp" in data:
        usd_to_lbp = data.get("usd_to_lbp")
        if type(usd_to_lbp) is not bool:
            return jsonify({"error": "usd_to_lbp must be boolean (true/false)"}), 400
    else:
        return jsonify({"error": "Missing field: transaction_type"}), 400

    # Detect outliers BEFORE creating transaction
    is_outlier, anomaly_info = detect_rate_outlier(usd_amount, lbp_amount, usd_to_lbp)
    
    if is_outlier:
        # Record the anomaly
        anomaly = RateAnomaly(
            direction=anomaly_info["direction"],
            previous_rate=anomaly_info["previous_rate"],
            new_rate=anomaly_info["new_rate"],
            percent_change=anomaly_info["percent_change"],
            time_diff_minutes=anomaly_info["time_diff_minutes"],
            transaction_id=None,  # Transaction not created yet
            reason=anomaly_info["reason"]
        )
        db.session.add(anomaly)
        db.session.commit()
        
        app.logger.warning(f"Transaction blocked due to outlier: {anomaly_info['reason']}")
        
        return jsonify({
            "error": "Transaction rejected: Rate anomaly detected",
            "reason": anomaly_info["reason"],
            "previous_rate": anomaly_info["previous_rate"],
            "your_rate": anomaly_info["new_rate"],
            "percent_change": anomaly_info["percent_change"]
        }), 400

    # Feature 13: Wallet balance validation
    user_id = get_user_id_from_token()  # Changed from optional to required
    
    # Get or create wallet
    wallet = Wallet.query.get(user_id)
    if not wallet:
        wallet = Wallet(user_id=user_id, usd_balance=0.0, lbp_balance=0.0)
        db.session.add(wallet)
        db.session.flush()  # Get the wallet ID before checking balance
    
    # Check sufficient balance
    if usd_to_lbp:
        # Converting USD to LBP: need USD
        if wallet.usd_balance < usd_amount:
            return jsonify({
                "error": "Insufficient funds",
                "message": f"You need {usd_amount} USD but only have {wallet.usd_balance} USD",
                "required": usd_amount,
                "available": wallet.usd_balance,
                "currency": "USD"
            }), 400
        # Deduct USD, add LBP
        wallet.usd_balance -= usd_amount
        wallet.lbp_balance += lbp_amount
    else:
        # Converting LBP to USD: need LBP
        if wallet.lbp_balance < lbp_amount:
            return jsonify({
                "error": "Insufficient funds",
                "message": f"You need {lbp_amount} LBP but only have {wallet.lbp_balance} LBP",
                "required": lbp_amount,
                "available": wallet.lbp_balance,
                "currency": "LBP"
            }), 400
        # Deduct LBP, add USD
        wallet.lbp_balance -= lbp_amount
        wallet.usd_balance += usd_amount
    
    wallet.updated_at = datetime.datetime.now()

    # Create transaction
    t = Transaction(
        usd_amount=usd_amount,
        lbp_amount=lbp_amount,
        usd_to_lbp=usd_to_lbp,
        user_id=user_id
    )
    db.session.add(t)
    db.session.commit()

    # Record rate source
    direction = "USD_LBP" if usd_to_lbp else "LBP_USD"
    rate = lbp_amount / usd_amount
    record_rate_source(direction, rate, "INTERNAL_COMPUTED", t.id)

    # Log transaction submission
    log_audit_event("transaction_submitted", success=True, user_id=user_id,
                   metadata={"transaction_id": t.id, "usd_amount": usd_amount, 
                            "lbp_amount": lbp_amount, "usd_to_lbp": usd_to_lbp})

    # Check and trigger alerts (mock async job)
    check_and_trigger_alerts()

    app.logger.info(
        "Transaction created id=%s usd=%s lbp=%s usd_to_lbp=%s user_id=%s",
        t.id,
        usd_amount,
        lbp_amount,
        usd_to_lbp,
        user_id
    )

    return jsonify({"ok": True, "transaction": transaction_schema.dump(t)}), 201


@app.route("/transaction", methods=["GET"])
def get_transactions():
    user_id = get_user_id_from_token()
    user_transactions = Transaction.query.filter_by(user_id=user_id).all()
    return jsonify(transactions_schema.dump(user_transactions)), 200


@app.route("/transactions/export", methods=["GET"])
def export_transactions():
    """Export user's transactions as CSV with optional date filtering"""
    user_id = get_user_id_from_token()
    
    # Get optional query parameters
    from_date_str = request.args.get('from')
    to_date_str = request.args.get('to')
    
    # Build query
    query = Transaction.query.filter_by(user_id=user_id)
    
    # Apply date filters if provided
    if from_date_str:
        try:
            from_date = parser.parse(from_date_str)
            query = query.filter(Transaction.added_date >= from_date)
            app.logger.info("Filtering transactions from %s", from_date)
        except (ValueError, parser.ParserError) as e:
            abort(400, description=f"Invalid 'from' date format: {from_date_str}")
    
    if to_date_str:
        try:
            to_date = parser.parse(to_date_str)
            # Include the entire end date by adding 1 day and using < instead of <=
            to_date_end = to_date + datetime.timedelta(days=1)
            query = query.filter(Transaction.added_date < to_date_end)
            app.logger.info("Filtering transactions to %s", to_date)
        except (ValueError, parser.ParserError) as e:
            abort(400, description=f"Invalid 'to' date format: {to_date_str}")
    
    # Get transactions ordered by date
    transactions = query.order_by(Transaction.added_date.asc()).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['ID', 'USD Amount', 'LBP Amount', 'Direction', 'Date', 'Exchange Rate'])
    
    # Write data rows
    for tx in transactions:
        direction = 'USD→LBP' if tx.usd_to_lbp else 'LBP→USD'
        # Calculate exchange rate
        if tx.usd_to_lbp:
            rate = tx.lbp_amount / tx.usd_amount if tx.usd_amount else 0
        else:
            rate = tx.lbp_amount / tx.usd_amount if tx.usd_amount else 0
        
        # Format date as YYYY-MM-DD HH:MM:SS
        date_str = tx.added_date.strftime('%Y-%m-%d %H:%M:%S') if tx.added_date else ''
        
        writer.writerow([
            tx.id,
            f'{tx.usd_amount:.2f}',
            f'{tx.lbp_amount:.2f}',
            direction,
            date_str,
            f'{rate:.2f}'
        ])
    
    # Create response with CSV content
    csv_content = output.getvalue()
    output.close()
    
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    
    app.logger.info("Exported %s transactions for user_id=%s", len(transactions), user_id)
    
    return response, 200


@app.route("/exchangeRate", methods=["GET"])
def exchange_rate():
    # Check and trigger alerts (mock async job)
    check_and_trigger_alerts()
    
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(hours=72)

    usd_to_lbp_tx = Transaction.query.filter(
        Transaction.added_date.between(start_date, end_date),
        Transaction.usd_to_lbp == True
    ).all()

    lbp_to_usd_tx = Transaction.query.filter(
        Transaction.added_date.between(start_date, end_date),
        Transaction.usd_to_lbp == False
    ).all()

    sell_usd_rate = None
    if usd_to_lbp_tx:
        total_usd = sum(t.usd_amount for t in usd_to_lbp_tx)
        total_lbp = sum(t.lbp_amount for t in usd_to_lbp_tx)
        sell_usd_rate = (total_lbp / total_usd) if total_usd else None

    buy_usd_rate = None
    if lbp_to_usd_tx:
        total_usd = sum(t.usd_amount for t in lbp_to_usd_tx)
        total_lbp = sum(t.lbp_amount for t in lbp_to_usd_tx)
        buy_usd_rate = (total_lbp / total_usd) if total_usd else None

    app.logger.info("Exchange rates buy_usd=%s sell_usd=%s", buy_usd_rate, sell_usd_rate)

    return jsonify({
        "buy_usd": buy_usd_rate,
        "sell_usd": sell_usd_rate,
        "usd_to_lbp": sell_usd_rate,
        "lbp_to_usd": buy_usd_rate
    }), 200


@app.route("/user", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    if "user_name" not in data or "password" not in data:
        return jsonify({"error": "Missing user_name or password"}), 400

    user_name = data["user_name"]
    password = data["password"]
    role = data.get("role", "USER")  # Optional role parameter, defaults to USER

    if not isinstance(user_name, str) or not user_name.strip():
        return jsonify({"error": "user_name must be a non-empty string"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password must be a non-empty string"}), 400
    
    # Validate role if provided
    if role not in ("USER", "ADMIN"):
        return jsonify({"error": "role must be 'USER' or 'ADMIN'"}), 400

    if User.query.filter_by(user_name=user_name).first():
        return jsonify({"error": "user_name already exists"}), 409

    u = User(user_name=user_name, password=password, role=role)
    db.session.add(u)
    db.session.commit()

    return jsonify(user_schema.dump(u)), 201


@app.route("/authentication", methods=["POST"])
@limiter.limit("5 per minute")
def authenticate():
    data = request.get_json(silent=True)
    if not data or "user_name" not in data or "password" not in data:
        return jsonify({"error": "Request body must include user_name and password"}), 400

    user_name = data["user_name"]
    password = data["password"]

    user = User.query.filter_by(user_name=user_name).first()
    if not user:
        # Log failed login attempt - user not found
        log_audit_event("login_attempt", success=False, user_id=None, 
                       metadata={"user_name": user_name, "reason": "user_not_found"})
        abort(403, description="Invalid credentials")

    if not bcrypt.check_password_hash(user.hashed_password, password):
        # Log failed login attempt - wrong password
        log_audit_event("login_attempt", success=False, user_id=user.id, 
                       metadata={"user_name": user_name, "reason": "invalid_password"})
        abort(403, description="Invalid credentials")
    
    # Check if user is banned
    if user.status == 'BANNED':
        # Log failed login attempt - banned user
        log_audit_event("login_attempt", success=False, user_id=user.id, 
                       metadata={"user_name": user_name, "reason": "banned"})
        abort(401, description="Your account has been banned")

    # Log successful login
    log_audit_event("login_attempt", success=True, user_id=user.id, 
                   metadata={"user_name": user_name})

    token = create_token(user.id)
    return jsonify({"token": token, "user": user_schema.dump(user)}), 200


def bucket_transactions_by_time(transactions, interval):
    """
    Bucket transactions by time interval and calculate statistics.
    
    Args:
        transactions: List of Transaction objects
        interval: 'hour' or 'day'
    
    Returns:
        List of dictionaries with time bucket statistics
    """
    if not transactions:
        return []
    
    # Determine bucket size in seconds
    bucket_seconds = 3600 if interval == 'hour' else 86400
    
    # Group transactions by time bucket
    buckets = {}
    
    for tx in transactions:
        # Calculate the bucket timestamp (round down to nearest interval)
        timestamp = tx.added_date
        if interval == 'hour':
            # Round down to the start of the hour
            bucket_time = timestamp.replace(minute=0, second=0, microsecond=0)
        else:  # day
            # Round down to the start of the day
            bucket_time = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate exchange rate
        rate = tx.lbp_amount / tx.usd_amount if tx.usd_amount > 0 else 0
        
        # Initialize bucket if not exists
        if bucket_time not in buckets:
            buckets[bucket_time] = {
                'rates': [],
                'count': 0
            }
        
        # Add rate to bucket
        buckets[bucket_time]['rates'].append(rate)
        buckets[bucket_time]['count'] += 1
    
    # Calculate statistics for each bucket and format result
    result = []
    for bucket_time in sorted(buckets.keys()):
        bucket_data = buckets[bucket_time]
        rates = bucket_data['rates']
        
        result.append({
            'timestamp': bucket_time.isoformat(),
            'avg_rate': round(sum(rates) / len(rates), 2),
            'min_rate': round(min(rates), 2),
            'max_rate': round(max(rates), 2),
            'count': bucket_data['count']
        })
    
    return result


@app.route("/history/rate", methods=["GET"])
def exchange_rate_history():
    """
    Get time-series data of exchange rates bucketed by hour or day.
    Uses user preferences as defaults when query params are missing.
    """
    # Authenticate user
    user_id = get_user_id_from_token()
    
    # Get query parameters
    from_param = request.args.get("from")
    to_param = request.args.get("to")
    interval = request.args.get("interval")
    
    # If any parameter is missing, load user preferences
    if not from_param or not to_param or not interval:
        # Query for user preferences (create defaults if missing)
        prefs = UserPreference.query.get(user_id)
        if not prefs:
            prefs = UserPreference(user_id=user_id)
            db.session.add(prefs)
            db.session.commit()
        
        # Apply defaults from preferences
        if not interval:
            interval = prefs.default_interval
            app.logger.info("Using default interval from preferences: %s", interval)
        
        if not to_param:
            to_date = datetime.datetime.now()
        else:
            try:
                to_date = parser.isoparse(to_param)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid ISO datetime format for 'to' parameter"}), 400
        
        if not from_param:
            # Use preference to calculate from_date
            from_date = to_date - datetime.timedelta(hours=prefs.default_from_range_hours)
            app.logger.info("Using default from_range_hours from preferences: %s hours", prefs.default_from_range_hours)
        else:
            try:
                from_date = parser.isoparse(from_param)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid ISO datetime format for 'from' parameter"}), 400
    else:
        # All parameters provided, validate them
        if interval not in ["hour", "day"]:
            return jsonify({"error": "interval must be 'hour' or 'day'"}), 400
        
        # Parse datetime parameters
        try:
            from_date = parser.isoparse(from_param)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid ISO datetime format for 'from' parameter"}), 400
        
        try:
            to_date = parser.isoparse(to_param)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid ISO datetime format for 'to' parameter"}), 400
    
    # Validate interval (in case it came from preferences)
    if interval not in ["hour", "day"]:
        return jsonify({"error": "interval must be 'hour' or 'day'"}), 400
    
    # Validate from < to
    if from_date >= to_date:
        return jsonify({"error": "from date must be earlier than to date"}), 400
    
    # Query all transactions in the date range (both directions for comprehensive history)
    transactions = Transaction.query.filter(
        Transaction.added_date.between(from_date, to_date)
    ).order_by(Transaction.added_date).all()
    
    # Check if data exists
    if not transactions:
        return jsonify({"error": "No transaction data found for the specified range"}), 404
    
    # Bucket transactions by time interval
    time_series_data = bucket_transactions_by_time(transactions, interval)
    
    app.logger.info(
        "History data calculated for user_id=%s interval=%s from=%s to=%s buckets=%s",
        user_id,
        interval,
        from_date,
        to_date,
        len(time_series_data)
    )
    
    return jsonify(time_series_data), 200


# ============================================================================
# Analytics Endpoint
# ============================================================================

def calculate_analytics(transactions, direction):
    """
    Calculate analytics metrics for a list of transactions in a specific direction.
    
    Args:
        transactions: List of Transaction objects
        direction: "USD_LBP" or "LBP_USD"
    
    Returns:
        Dictionary with analytics data or None if no matching transactions
    """
    if not transactions:
        return None
    
    # Filter transactions by direction
    if direction == "USD_LBP":
        filtered_txs = [tx for tx in transactions if tx.usd_to_lbp]
    elif direction == "LBP_USD":
        filtered_txs = [tx for tx in transactions if not tx.usd_to_lbp]
    else:
        return None
    
    if not filtered_txs:
        return None
    
    # Calculate exchange rates
    rates = []
    for tx in filtered_txs:
        if tx.usd_amount > 0:
            rate = tx.lbp_amount / tx.usd_amount
            rates.append(rate)
    
    if not rates:
        return None
    
    # Calculate basic statistics
    min_rate = round(min(rates), 2)
    max_rate = round(max(rates), 2)
    avg_rate = round(sum(rates) / len(rates), 2)
    count = len(rates)
    
    # Calculate percentage change (from first to last transaction)
    if len(rates) >= 2:
        first_rate = rates[0]
        last_rate = rates[-1]
        percentage_change = round(((last_rate - first_rate) / first_rate) * 100, 2)
    else:
        percentage_change = 0
    
    # Calculate volatility (standard deviation)
    if len(rates) >= 2:
        variance = sum((r - avg_rate) ** 2 for r in rates) / len(rates)
        volatility = round(variance ** 0.5, 2)
    else:
        volatility = 0
    
    # Determine trend
    if abs(percentage_change) < 1:
        trend = "flat"
    elif percentage_change > 0:
        trend = "up"
    else:
        trend = "down"
    
    return {
        "min": min_rate,
        "max": max_rate,
        "avg": avg_rate,
        "count": count,
        "percentage_change": percentage_change,
        "volatility": volatility,
        "trend": trend
    }


@app.route("/analytics/rate", methods=["GET"])
def analytics_rate():
    """
    Get analytics for exchange rates in a specific direction and time range.
    Uses user preferences as defaults when query params are missing.
    """
    # Authenticate user
    user_id = get_user_id_from_token()
    
    # Get query parameters
    from_param = request.args.get("from")
    to_param = request.args.get("to")
    direction = request.args.get("direction")
    
    # If any parameter is missing, load user preferences
    if not from_param or not to_param or not direction:
        # Query for user preferences (create defaults if missing)
        prefs = UserPreference.query.get(user_id)
        if not prefs:
            prefs = UserPreference(user_id=user_id)
            db.session.add(prefs)
            db.session.commit()
        
        # Apply defaults from preferences
        if not direction:
            direction = prefs.default_direction
            app.logger.info("Using default direction from preferences: %s", direction)
        
        if not to_param:
            to_date = datetime.datetime.now()
        else:
            try:
                to_date = parser.isoparse(to_param)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid ISO datetime format for 'to' parameter"}), 400
        
        if not from_param:
            # Use preference to calculate from_date
            from_date = to_date - datetime.timedelta(hours=prefs.default_from_range_hours)
            app.logger.info("Using default from_range_hours from preferences: %s hours", prefs.default_from_range_hours)
        else:
            try:
                from_date = parser.isoparse(from_param)
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid ISO datetime format for 'from' parameter"}), 400
    else:
        # All parameters provided, validate them
        if direction not in ["USD_LBP", "LBP_USD"]:
            return jsonify({"error": "direction must be 'USD_LBP' or 'LBP_USD'"}), 400
        
        # Parse datetime parameters
        try:
            from_date = parser.isoparse(from_param)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid ISO datetime format for 'from' parameter"}), 400
        
        try:
            to_date = parser.isoparse(to_param)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid ISO datetime format for 'to' parameter"}), 400
    
    # Validate direction (in case it came from preferences)
    if direction not in ["USD_LBP", "LBP_USD"]:
        return jsonify({"error": "direction must be 'USD_LBP' or 'LBP_USD'"}), 400
    
    # Validate from < to
    if from_date >= to_date:
        return jsonify({"error": "from date must be earlier than to date"}), 400
    
    # Query all transactions in the date range
    transactions = Transaction.query.filter(
        Transaction.added_date.between(from_date, to_date)
    ).order_by(Transaction.added_date).all()
    
    # Calculate analytics
    analytics = calculate_analytics(transactions, direction)
    
    # Check if data exists
    if analytics is None:
        return jsonify({"error": "No transaction data found for the specified range and direction"}), 404
    
    app.logger.info(
        "Analytics calculated for user_id=%s direction=%s from=%s to=%s count=%s",
        user_id,
        direction,
        from_date,
        to_date,
        analytics['count']
    )
    
    return jsonify(analytics), 200


# ============================================================================
# P2P Marketplace Endpoints
# ============================================================================

@app.route("/market/offers", methods=["POST"])
def create_offer():
    """Create a new marketplace offer"""
    user_id = get_user_id_from_token()
    
    data = request.get_json()
    if not data:
        abort(400, description="Request body is required")
    
    # Required fields
    from_currency = data.get("from_currency")
    to_currency = data.get("to_currency")
    amount_from = data.get("amount_from")
    rate = data.get("rate")
    
    # Validate required fields
    if not all([from_currency, to_currency, amount_from is not None, rate is not None]):
        abort(400, description="Missing required fields: from_currency, to_currency, amount_from, rate")
    
    # Validate currencies
    if from_currency not in ["USD", "LBP"] or to_currency not in ["USD", "LBP"]:
        abort(400, description="from_currency and to_currency must be 'USD' or 'LBP'")
    
    if from_currency == to_currency:
        abort(400, description="from_currency and to_currency must be different")
    
    # Validate amounts are positive
    try:
        amount_from = float(amount_from)
        rate = float(rate)
    except (TypeError, ValueError):
        abort(400, description="amount_from and rate must be numeric")
    
    if amount_from <= 0 or rate <= 0:
        abort(400, description="amount_from and rate must be positive")
    
    # Create offer
    offer = Offer(
        creator_user_id=user_id,
        from_currency=from_currency,
        to_currency=to_currency,
        amount_from=amount_from,
        rate=rate
    )
    
    db.session.add(offer)
    db.session.commit()
    
    # Log offer posted
    log_audit_event("offer_posted", success=True, user_id=user_id,
                   metadata={"offer_id": offer.id, "from_currency": from_currency,
                            "to_currency": to_currency, "amount_from": amount_from, "rate": rate})
    
    app.logger.info("Offer created: id=%s user_id=%s %s→%s amount=%s rate=%s",
                    offer.id, user_id, from_currency, to_currency, amount_from, rate)
    
    return jsonify(offer_schema.dump(offer)), 201


@app.route("/market/offers", methods=["GET"])
def list_offers():
    """List all OPEN offers with optional currency filter"""
    user_id = get_user_id_from_token()
    
    # Optional filters
    from_currency = request.args.get("from_currency")
    to_currency = request.args.get("to_currency")
    
    # Base query: only OPEN offers
    query = Offer.query.filter_by(status="OPEN")
    
    # Apply filters if provided
    if from_currency:
        if from_currency not in ["USD", "LBP"]:
            abort(400, description="from_currency must be 'USD' or 'LBP'")
        query = query.filter_by(from_currency=from_currency)
    
    if to_currency:
        if to_currency not in ["USD", "LBP"]:
            abort(400, description="to_currency must be 'USD' or 'LBP'")
        query = query.filter_by(to_currency=to_currency)
    
    offers = query.order_by(Offer.created_at.desc()).all()
    
    app.logger.info("Listed %s OPEN offers for user_id=%s", len(offers), user_id)
    
    return jsonify(offers_schema.dump(offers)), 200


@app.route("/market/offers/<int:offer_id>/accept", methods=["POST"])
@limiter.limit("5 per minute")
def accept_offer(offer_id):
    """Accept an offer and create a trade (atomic transaction with wallet balances)"""
    user_id = get_user_id_from_token()
    
    # Find the offer with row-level lock (FOR UPDATE) to prevent race conditions
    offer = Offer.query.filter_by(id=offer_id).with_for_update().first()
    if not offer:
        abort(404, description="Offer not found")
    
    # Feature 13: Race condition prevention - check status AFTER locking
    if offer.status != "OPEN":
        abort(400, description=f"Cannot accept offer with status {offer.status}")
    
    # Cannot accept your own offer
    if offer.creator_user_id == user_id:
        abort(400, description="Cannot accept your own offer")
    
    # Determine buyer and seller based on currency direction
    # If offer is USD→LBP: creator is selling USD (seller), accepter is buying USD (buyer)
    # If offer is LBP→USD: creator is selling LBP (buyer), accepter is buying LBP (seller)
    if offer.from_currency == "USD":
        seller_user_id = offer.creator_user_id
        buyer_user_id = user_id
    else:
        buyer_user_id = offer.creator_user_id
        seller_user_id = user_id
    
    # Feature 13: Get or create wallets for both users
    buyer_wallet = Wallet.query.get(buyer_user_id)
    if not buyer_wallet:
        buyer_wallet = Wallet(user_id=buyer_user_id, usd_balance=0.0, lbp_balance=0.0)
        db.session.add(buyer_wallet)
        db.session.flush()
    
    seller_wallet = Wallet.query.get(seller_user_id)
    if not seller_wallet:
        seller_wallet = Wallet(user_id=seller_user_id, usd_balance=0.0, lbp_balance=0.0)
        db.session.add(seller_wallet)
        db.session.flush()
    
    # Feature 13: Validate balances and calculate amounts
    if offer.from_currency == "USD":
        # Seller gives USD, gets LBP
        # Buyer gives LBP, gets USD
        usd_amount = offer.amount_from
        lbp_amount = offer.amount_from * offer.rate
        
        # Check seller has enough USD
        if seller_wallet.usd_balance < usd_amount:
            abort(400, description=f"Insufficient funds: Seller needs {usd_amount} USD but only has {seller_wallet.usd_balance} USD")
        
        # Check buyer has enough LBP
        if buyer_wallet.lbp_balance < lbp_amount:
            abort(400, description=f"Insufficient funds: Buyer needs {lbp_amount} LBP but only has {buyer_wallet.lbp_balance} LBP")
        
        # Update wallets
        seller_wallet.usd_balance -= usd_amount
        seller_wallet.lbp_balance += lbp_amount
        buyer_wallet.lbp_balance -= lbp_amount
        buyer_wallet.usd_balance += usd_amount
        
    else:  # from_currency == "LBP"
        # Seller gives LBP, gets USD
        # Buyer gives USD, gets LBP
        lbp_amount = offer.amount_from
        usd_amount = offer.amount_from / offer.rate  # rate is LBP per USD
        
        # Check seller has enough LBP
        if seller_wallet.lbp_balance < lbp_amount:
            abort(400, description=f"Insufficient funds: Seller needs {lbp_amount} LBP but only has {seller_wallet.lbp_balance} LBP")
        
        # Check buyer has enough USD
        if buyer_wallet.usd_balance < usd_amount:
            abort(400, description=f"Insufficient funds: Buyer needs {usd_amount} USD but only has {buyer_wallet.usd_balance} USD")
        
        # Update wallets
        seller_wallet.lbp_balance -= lbp_amount
        seller_wallet.usd_balance += usd_amount
        buyer_wallet.usd_balance -= usd_amount
        buyer_wallet.lbp_balance += lbp_amount
    
    seller_wallet.updated_at = datetime.datetime.now()
    buyer_wallet.updated_at = datetime.datetime.now()
    
    try:
        # Atomic transaction: update offer + create trade + update wallets
        offer.status = "ACCEPTED"
        offer.updated_at = datetime.datetime.now()
        
        trade = Trade(
            offer_id=offer.id,
            buyer_user_id=buyer_user_id,
            seller_user_id=seller_user_id,
            from_currency=offer.from_currency,
            to_currency=offer.to_currency,
            amount_from=offer.amount_from,
            rate=offer.rate
        )
        
        db.session.add(trade)
        db.session.commit()
        
        # Log offer accepted
        log_audit_event("offer_accepted", success=True, user_id=user_id,
                       metadata={"offer_id": offer.id, "trade_id": trade.id,
                                "buyer_user_id": buyer_user_id, "seller_user_id": seller_user_id})
        
        # Create notifications for both parties
        create_notification(
            user_id=offer.creator_user_id,
            type="trade_completed",
            message=f"Your offer #{offer.id} was accepted and a trade was completed",
            metadata={"offer_id": offer.id, "trade_id": trade.id, "role": "creator"}
        )
        create_notification(
            user_id=user_id,
            type="trade_completed",
            message=f"You accepted offer #{offer.id} and completed a trade",
            metadata={"offer_id": offer.id, "trade_id": trade.id, "role": "acceptor"}
        )
        
        app.logger.info("Offer accepted: offer_id=%s buyer=%s seller=%s trade_id=%s",
                        offer.id, buyer_user_id, seller_user_id, trade.id)
        
        result = offer_schema.dump(offer)
        result["trade_id"] = trade.id
        
        return jsonify(result), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error("Failed to accept offer: %s", str(e))
        abort(500, description="Failed to accept offer")


@app.route("/market/offers/<int:offer_id>/cancel", methods=["POST"])
def cancel_offer(offer_id):
    """Cancel an offer (only by creator, only if OPEN)"""
    user_id = get_user_id_from_token()
    
    # Find the offer
    offer = Offer.query.get(offer_id)
    if not offer:
        abort(404, description="Offer not found")
    
    # Only creator can cancel
    if offer.creator_user_id != user_id:
        abort(403, description="Only the offer creator can cancel it")
    
    # Can only cancel OPEN offers
    if offer.status != "OPEN":
        abort(400, description=f"Cannot cancel offer with status {offer.status}")
    
    # Update status
    offer.status = "CANCELED"
    offer.updated_at = datetime.datetime.now()
    db.session.commit()
    
    # Log offer canceled
    log_audit_event("offer_canceled", success=True, user_id=user_id,
                   metadata={"offer_id": offer.id})
    
    # Create notification for offer status change
    create_notification(
        user_id=user_id,
        type="offer_status_changed",
        message=f"Your offer #{offer.id} has been canceled",
        metadata={"offer_id": offer.id, "new_status": "CANCELED"}
    )
    
    app.logger.info("Offer canceled: offer_id=%s user_id=%s", offer.id, user_id)
    
    return jsonify(offer_schema.dump(offer)), 200


@app.route("/market/me/offers", methods=["GET"])
def my_offers():
    """Get all my offers (any status)"""
    user_id = get_user_id_from_token()
    
    offers = Offer.query.filter_by(creator_user_id=user_id).order_by(Offer.created_at.desc()).all()
    
    app.logger.info("Retrieved %s offers for user_id=%s", len(offers), user_id)
    
    return jsonify(offers_schema.dump(offers)), 200


@app.route("/market/me/trades", methods=["GET"])
def my_trades():
    """Get all my trades (as buyer or seller)"""
    user_id = get_user_id_from_token()
    
    # Find trades where user is buyer OR seller
    trades = Trade.query.filter(
        (Trade.buyer_user_id == user_id) | (Trade.seller_user_id == user_id)
    ).order_by(Trade.executed_at.desc()).all()
    
    app.logger.info("Retrieved %s trades for user_id=%s", len(trades), user_id)
    
    return jsonify(trades_schema.dump(trades)), 200


# =============================================================================
# Feature 4: Alerts CRUD
# =============================================================================

@app.route("/alerts", methods=["POST"])
def create_alert():
    """Create a new price alert"""
    user_id = get_user_id_from_token()
    
    data = request.get_json() or {}
    direction = data.get("direction")
    threshold = data.get("threshold")
    condition = data.get("condition")
    
    # Validation
    if not direction or direction not in ["USD_LBP", "LBP_USD"]:
        abort(400, description="Invalid direction. Must be USD_LBP or LBP_USD")
    
    if threshold is None:
        abort(400, description="threshold is required")
    
    try:
        threshold = float(threshold)
        if threshold <= 0:
            abort(400, description="threshold must be positive")
    except (TypeError, ValueError):
        abort(400, description="threshold must be a positive number")
    
    if not condition or condition not in ["ABOVE", "BELOW"]:
        abort(400, description="Invalid condition. Must be ABOVE or BELOW")
    
    # Create alert
    alert = Alert(
        user_id=user_id,
        direction=direction,
        threshold=threshold,
        condition=condition
    )
    db.session.add(alert)
    db.session.commit()
    
    # Log alert creation
    log_audit_event("alert_created", success=True, user_id=user_id,
                   metadata={"alert_id": alert.id, "direction": direction,
                            "threshold": threshold, "condition": condition})
    
    app.logger.info("Created alert id=%s for user_id=%s: %s %s %.2f",
                   alert.id, user_id, direction, condition, threshold)
    
    return jsonify(alert_schema.dump(alert)), 201


@app.route("/alerts", methods=["GET"])
def get_alerts():
    """Get all alerts for the authenticated user"""
    user_id = get_user_id_from_token()
    
    alerts = Alert.query.filter_by(user_id=user_id).order_by(Alert.created_at.desc()).all()
    
    app.logger.info("Retrieved %s alerts for user_id=%s", len(alerts), user_id)
    
    return jsonify(alerts_schema.dump(alerts)), 200


@app.route("/alerts/<int:alert_id>", methods=["DELETE"])
def delete_alert(alert_id):
    """Delete an alert (only owner can delete)"""
    user_id = get_user_id_from_token()
    
    alert = Alert.query.get(alert_id)
    if not alert:
        abort(404, description="Alert not found")
    
    # Permission check: only owner can delete
    if alert.user_id != user_id:
        abort(403, description="You can only delete your own alerts")
    
    db.session.delete(alert)
    db.session.commit()
    
    # Log alert deletion
    log_audit_event("alert_deleted", success=True, user_id=user_id,
                   metadata={"alert_id": alert_id})
    
    app.logger.info("Deleted alert id=%s by user_id=%s", alert_id, user_id)
    
    return jsonify({"message": "Alert deleted successfully"}), 200


# =============================================================================
# Feature 10: Notifications
# =============================================================================

@app.route("/notifications", methods=["GET"])
def get_notifications():
    """Get all notifications for the authenticated user"""
    user_id = get_user_id_from_token()
    
    # Optional filters
    unread_only = request.args.get("unread", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    
    # Limit maximum records
    limit = min(limit, 200)
    
    # Build query
    query = Notification.query.filter_by(user_id=user_id)
    
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    
    # Order by most recent first
    query = query.order_by(Notification.created_at.desc())
    
    # Apply pagination
    notifications = query.limit(limit).offset(offset).all()
    
    app.logger.info("Retrieved %d notifications for user_id=%s", len(notifications), user_id)
    
    return jsonify(notifications_schema.dump(notifications)), 200


@app.route("/notifications/<int:notification_id>/read", methods=["PATCH"])
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    user_id = get_user_id_from_token()
    
    notification = Notification.query.get(notification_id)
    if not notification:
        abort(404, description="Notification not found")
    
    # Permission check: only owner can mark as read
    if notification.user_id != user_id:
        abort(403, description="You can only mark your own notifications as read")
    
    # Mark as read
    notification.read_at = datetime.datetime.now()
    db.session.commit()
    
    app.logger.info("Marked notification id=%s as read by user_id=%s", notification_id, user_id)
    
    return jsonify(notification_schema.dump(notification)), 200


@app.route("/notifications/<int:notification_id>", methods=["DELETE"])
def delete_notification(notification_id):
    """Delete a notification"""
    user_id = get_user_id_from_token()
    
    notification = Notification.query.get(notification_id)
    if not notification:
        abort(404, description="Notification not found")
    
    # Permission check: only owner can delete
    if notification.user_id != user_id:
        abort(403, description="You can only delete your own notifications")
    
    db.session.delete(notification)
    db.session.commit()
    
    app.logger.info("Deleted notification id=%s by user_id=%s", notification_id, user_id)
    
    return jsonify({"message": "Notification deleted successfully"}), 200


# =============================================================================
# Feature 5: Watchlist CRUD
# =============================================================================

@app.route("/watchlist", methods=["POST"])
def add_watchlist_item():
    """Add item to watchlist with duplicate prevention"""
    user_id = get_user_id_from_token()
    
    data = request.get_json() or {}
    item_type = data.get("type")
    payload_json = data.get("payload_json")
    
    # Validation
    if not item_type or not isinstance(item_type, str) or not item_type.strip():
        abort(400, description="type is required and must be a non-empty string")
    
    if payload_json is None:
        abort(400, description="payload_json is required")
    
    # Convert payload_json to string if it's a dict/object
    import json
    if isinstance(payload_json, dict):
        payload_json_str = json.dumps(payload_json, sort_keys=True)
    elif isinstance(payload_json, str):
        # Validate it's valid JSON and normalize it
        try:
            parsed = json.loads(payload_json)
            payload_json_str = json.dumps(parsed, sort_keys=True)
        except json.JSONDecodeError:
            abort(400, description="payload_json must be valid JSON")
    else:
        abort(400, description="payload_json must be a JSON object or string")
    
    # Check for duplicates: same user_id + same payload_json
    existing = WatchlistItem.query.filter_by(
        user_id=user_id,
        payload_json=payload_json_str
    ).first()
    
    if existing:
        app.logger.warning("Duplicate watchlist item attempt by user_id=%s", user_id)
        abort(409, description="Duplicate watchlist item. This item already exists in your watchlist.")
    
    # Create watchlist item
    watchlist_item = WatchlistItem(
        user_id=user_id,
        type=item_type,
        payload_json=payload_json_str
    )
    db.session.add(watchlist_item)
    db.session.commit()
    
    app.logger.info("Created watchlist item id=%s for user_id=%s, type=%s",
                   watchlist_item.id, user_id, item_type)
    
    return jsonify(watchlist_item_schema.dump(watchlist_item)), 201


@app.route("/watchlist", methods=["GET"])
def get_watchlist():
    """Get all watchlist items for the authenticated user"""
    user_id = get_user_id_from_token()
    
    items = WatchlistItem.query.filter_by(user_id=user_id).order_by(WatchlistItem.created_at.desc()).all()
    
    app.logger.info("Retrieved %s watchlist items for user_id=%s", len(items), user_id)
    
    return jsonify(watchlist_items_schema.dump(items)), 200


@app.route("/watchlist/<int:item_id>", methods=["DELETE"])
def delete_watchlist_item(item_id):
    """Delete a watchlist item (only owner can delete)"""
    user_id = get_user_id_from_token()
    
    item = WatchlistItem.query.get(item_id)
    if not item:
        abort(404, description="Watchlist item not found")
    
    # Permission check: only owner can delete
    if item.user_id != user_id:
        abort(403, description="You can only delete your own watchlist items")
    
    db.session.delete(item)
    db.session.commit()
    
    app.logger.info("Deleted watchlist item id=%s by user_id=%s", item_id, user_id)
    
    return jsonify({"message": "Watchlist item deleted successfully"}), 200


# =============================================================================
# Feature 7: User Preferences
# =============================================================================

@app.route("/preferences", methods=["GET"])
def get_preferences():
    """Get user's preferences, creating defaults if they don't exist"""
    user_id = get_user_id_from_token()
    
    # Query for existing preferences
    prefs = UserPreference.query.get(user_id)
    
    # If preferences don't exist, create them with defaults
    if not prefs:
        prefs = UserPreference(user_id=user_id)
        db.session.add(prefs)
        db.session.commit()
        app.logger.info("Created default preferences for user_id=%s", user_id)
    
    app.logger.info("Retrieved preferences for user_id=%s", user_id)
    
    return jsonify(user_preference_schema.dump(prefs)), 200


@app.route("/preferences", methods=["PUT"])
def update_preferences():
    """Update user's preferences"""
    user_id = get_user_id_from_token()
    
    data = request.get_json() or {}
    
    # Query for existing preferences
    prefs = UserPreference.query.get(user_id)
    
    # If preferences don't exist, create them first
    if not prefs:
        prefs = UserPreference(user_id=user_id)
        db.session.add(prefs)
    
    # Update fields if provided
    if "default_from_range_hours" in data:
        try:
            hours = int(data["default_from_range_hours"])
            if hours <= 0:
                abort(400, description="default_from_range_hours must be positive")
            if hours > 8760:  # Max 1 year
                abort(400, description="default_from_range_hours cannot exceed 8760 (1 year)")
            prefs.default_from_range_hours = hours
        except (TypeError, ValueError):
            abort(400, description="default_from_range_hours must be a positive integer")
    
    if "default_interval" in data:
        interval = data["default_interval"]
        if interval not in ["hour", "day"]:
            abort(400, description="default_interval must be 'hour' or 'day'")
        prefs.default_interval = interval
    
    if "default_direction" in data:
        direction = data["default_direction"]
        if direction not in ["USD_LBP", "LBP_USD"]:
            abort(400, description="default_direction must be 'USD_LBP' or 'LBP_USD'")
        prefs.default_direction = direction
    
    # Update timestamp
    prefs.updated_at = datetime.datetime.now()
    
    db.session.commit()
    
    # Log preferences change
    log_audit_event("preferences_updated", success=True, user_id=user_id,
                   metadata={"from_range_hours": prefs.default_from_range_hours,
                            "interval": prefs.default_interval, "direction": prefs.default_direction})
    
    app.logger.info("Updated preferences for user_id=%s: from_range=%s interval=%s direction=%s",
                   user_id, prefs.default_from_range_hours, prefs.default_interval, prefs.default_direction)
    
    return jsonify(user_preference_schema.dump(prefs)), 200


# =============================================================================
# Audit Logs (Immutable append-only)
# =============================================================================

@app.route("/me/audit", methods=["GET"])
def get_my_audit_logs():
    """Get current user's audit logs"""
    user_id = get_user_id_from_token()
    
    # Get query parameters for pagination
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    event_type = request.args.get("event_type")
    
    # Limit maximum records
    limit = min(limit, 500)
    
    # Build query
    query = AuditLog.query.filter_by(user_id=user_id)
    
    # Optional filter by event type
    if event_type:
        query = query.filter_by(event_type=event_type)
    
    # Order by most recent first
    query = query.order_by(AuditLog.created_at.desc())
    
    # Apply pagination
    logs = query.limit(limit).offset(offset).all()
    
    app.logger.info("Retrieved %d audit logs for user_id=%s", len(logs), user_id)
    
    return jsonify(audit_logs_schema.dump(logs)), 200


# =============================================================================
# ADMIN ENDPOINTS (Feature 8 - RBAC)
# =============================================================================

@app.route("/admin/users", methods=["GET"])
@require_role("ADMIN")
def admin_list_users():
    """List all users with basic info (admin only)"""
    users = User.query.all()
    
    # Return basic info for each user
    users_data = []
    for user in users:
        users_data.append({
            "id": user.id,
            "user_name": user.user_name,
            "role": user.role,
            "status": user.status,
            "created_at": user.created_at.isoformat() if user.created_at else None
        })
    
    app.logger.info("Admin listed %d users", len(users_data))
    return jsonify(users_data), 200


@app.route("/admin/stats/transactions", methods=["GET"])
@require_role("ADMIN")
def admin_transaction_stats():
    """Get system-wide transaction statistics (admin only)"""
    
    # Count total transactions
    total_count = Transaction.query.count()
    
    # Count by direction
    usd_to_lbp = Transaction.query.filter_by(usd_to_lbp=True).count()
    lbp_to_usd = Transaction.query.filter_by(usd_to_lbp=False).count()
    
    # Get total volumes
    usd_lbp_volume = db.session.query(func.sum(Transaction.usd_amount)).filter_by(usd_to_lbp=True).scalar() or 0
    lbp_usd_volume = db.session.query(func.sum(Transaction.usd_amount)).filter_by(usd_to_lbp=False).scalar() or 0
    
    # Count unique users
    unique_users = db.session.query(func.count(func.distinct(Transaction.user_id))).scalar()
    
    # Get date range
    earliest = db.session.query(func.min(Transaction.added_date)).scalar()
    latest = db.session.query(func.max(Transaction.added_date)).scalar()
    
    stats = {
        "total_transactions": total_count,
        "usd_to_lbp_count": usd_to_lbp,
        "lbp_to_usd_count": lbp_to_usd,
        "usd_to_lbp_volume_usd": float(usd_lbp_volume),
        "lbp_to_usd_volume_usd": float(lbp_usd_volume),
        "unique_users": unique_users,
        "earliest_transaction": earliest.isoformat() if earliest else None,
        "latest_transaction": latest.isoformat() if latest else None
    }
    
    app.logger.info("Admin requested transaction stats: %d total", total_count)
    return jsonify(stats), 200


@app.route("/admin/audit", methods=["GET"])
@require_role("ADMIN")
def admin_get_audit_logs():
    """Get all audit logs with optional filters (admin only)"""
    # Get query parameters
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    event_type = request.args.get("event_type")
    user_id_filter = request.args.get("user_id", type=int)
    success_filter = request.args.get("success")
    
    # Limit maximum records
    limit = min(limit, 1000)
    
    # Build query
    query = AuditLog.query
    
    # Optional filters
    if event_type:
        query = query.filter_by(event_type=event_type)
    
    if user_id_filter is not None:
        query = query.filter_by(user_id=user_id_filter)
    
    if success_filter is not None:
        success_bool = success_filter.lower() in ['true', '1', 'yes']
        query = query.filter_by(success=success_bool)
    
    # Order by most recent first
    query = query.order_by(AuditLog.created_at.desc())
    
    # Apply pagination
    logs = query.limit(limit).offset(offset).all()
    
    app.logger.info("Admin retrieved %d audit logs (filters: event_type=%s, user_id=%s, success=%s)",
                   len(logs), event_type, user_id_filter, success_filter)
    
    return jsonify(audit_logs_schema.dump(logs)), 200


@app.route("/admin/rate/quality", methods=["GET"])
@require_role("ADMIN")
def admin_get_rate_quality():
    """Get rate quality metrics: sources summary and recent anomalies (admin only)"""
    
    # Get query parameters
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 100)  # Cap at 100
    
    # Get sources summary - count by source type
    sources_summary = db.session.query(
        RateSource.source,
        func.count(RateSource.id).label('count'),
        func.avg(RateSource.rate).label('avg_rate')
    ).group_by(RateSource.source).all()
    
    sources_data = [
        {
            "source": source,
            "count": count,
            "avg_rate": float(avg_rate) if avg_rate else 0
        }
        for source, count, avg_rate in sources_summary
    ]
    
    # Get recent anomalies
    recent_anomalies = RateAnomaly.query.order_by(
        RateAnomaly.flagged_at.desc()
    ).limit(limit).all()
    
    anomalies_data = rate_anomalies_schema.dump(recent_anomalies)
    
    # Get statistics
    total_anomalies = RateAnomaly.query.count()
    anomalies_last_24h = RateAnomaly.query.filter(
        RateAnomaly.flagged_at >= datetime.datetime.now() - datetime.timedelta(hours=24)
    ).count()
    
    response = {
        "sources_summary": sources_data,
        "anomalies": {
            "recent": anomalies_data,
            "total_count": total_anomalies,
            "last_24h_count": anomalies_last_24h
        },
        "thresholds": {
            "percent_change": OUTLIER_THRESHOLD_PERCENT,
            "time_window_minutes": OUTLIER_TIME_WINDOW_MINUTES
        }
    }
    
    app.logger.info("Admin requested rate quality: %d sources, %d recent anomalies", 
                   len(sources_data), len(recent_anomalies))
    
    return jsonify(response), 200


@app.route("/admin/users/<int:user_id>/status", methods=["PATCH"])
@require_role("ADMIN")
def admin_update_user_status(user_id):
    """Update user status (admin only)"""
    data = request.get_json(silent=True)
    if not data or "status" not in data:
        abort(400, description="Request body must include 'status' field")
    
    new_status = data["status"]
    
    # Validate status
    if new_status not in ["ACTIVE", "SUSPENDED", "BANNED"]:
        abort(400, description="status must be 'ACTIVE', 'SUSPENDED', or 'BANNED'")
    
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    old_status = user.status
    user.status = new_status
    db.session.commit()
    
    app.logger.info("Admin updated user_id=%d status from %s to %s", user_id, old_status, new_status)
    
    return jsonify({
        "id": user.id,
        "user_name": user.user_name,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }), 200


@app.route("/admin/users/<int:user_id>/preferences", methods=["GET"])
@require_role("ADMIN")
def admin_get_user_preferences(user_id):
    """Get any user's preferences (admin only)"""
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    prefs = UserPreference.query.get(user_id)
    if not prefs:
        # Create defaults
        prefs = UserPreference(
            user_id=user_id,
            default_from_range_hours=24,
            default_interval="hour",
            default_direction="USD_LBP"
        )
        db.session.add(prefs)
        db.session.commit()
        app.logger.info("Admin created default preferences for user_id=%s", user_id)
    
    return jsonify(user_preference_schema.dump(prefs)), 200


@app.route("/admin/users/<int:user_id>/preferences", methods=["PUT"])
@require_role("ADMIN")
def admin_update_user_preferences(user_id):
    """Update any user's preferences (admin only)"""
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    prefs = UserPreference.query.get(user_id)
    if not prefs:
        # Create if not exists
        prefs = UserPreference(
            user_id=user_id,
            default_from_range_hours=24,
            default_interval="hour",
            default_direction="USD_LBP"
        )
        db.session.add(prefs)
    
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="Request body must be JSON")
    
    # Validate and update fields
    if "default_from_range_hours" in data:
        hours = data["default_from_range_hours"]
        if not isinstance(hours, (int, float)) or hours <= 0:
            abort(400, description="default_from_range_hours must be a positive number")
        prefs.default_from_range_hours = hours
    
    if "default_interval" in data:
        interval = data["default_interval"]
        if interval not in ["hour", "day"]:
            abort(400, description="default_interval must be 'hour' or 'day'")
        prefs.default_interval = interval
    
    if "default_direction" in data:
        direction = data["default_direction"]
        if direction not in ["USD_LBP", "LBP_USD"]:
            abort(400, description="default_direction must be 'USD_LBP' or 'LBP_USD'")
        prefs.default_direction = direction
    
    prefs.updated_at = datetime.datetime.now()
    db.session.commit()
    
    app.logger.info("Admin updated preferences for user_id=%s", user_id)
    return jsonify(user_preference_schema.dump(prefs)), 200


@app.route("/admin/users/<int:user_id>/alerts", methods=["GET"])
@require_role("ADMIN")
def admin_get_user_alerts(user_id):
    """Get all alerts for a specific user (admin only)"""
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    alerts = Alert.query.filter_by(user_id=user_id).all()
    app.logger.info("Admin retrieved %d alerts for user_id=%s", len(alerts), user_id)
    return jsonify(alerts_schema.dump(alerts)), 200


@app.route("/admin/users/<int:user_id>/alerts", methods=["POST"])
@require_role("ADMIN")
def admin_create_alert_for_user(user_id):
    """Create an alert for a specific user (admin only)"""
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    data = request.get_json(silent=True)
    if not data:
        abort(400, description="Request body must be JSON")
    
    # Validate required fields
    required_fields = ["threshold", "direction", "condition"]
    for field in required_fields:
        if field not in data:
            abort(400, description=f"{field} is required")
    
    threshold = data["threshold"]
    direction = data["direction"]
    condition = data["condition"]
    
    if not isinstance(threshold, (int, float)) or threshold <= 0:
        abort(400, description="threshold must be a positive number")
    
    if direction not in ["USD_LBP", "LBP_USD"]:
        abort(400, description="direction must be 'USD_LBP' or 'LBP_USD'")
    
    if condition not in ["ABOVE", "BELOW"]:
        abort(400, description="condition must be 'ABOVE' or 'BELOW'")
    
    # Create alert
    alert = Alert(
        user_id=user_id,
        direction=direction,
        threshold=threshold,
        condition=condition
    )
    
    db.session.add(alert)
    db.session.commit()
    
    app.logger.info("Admin created alert_id=%d for user_id=%s: threshold=%s direction=%s condition=%s",
                   alert.id, user_id, threshold, direction, condition)
    
    return jsonify(alert_schema.dump(alert)), 201


@app.route("/admin/users/<int:user_id>/alerts/<int:alert_id>", methods=["DELETE"])
@require_role("ADMIN")
def admin_delete_user_alert(user_id, alert_id):
    """Delete an alert for a specific user (admin only)"""
    user = User.query.get(user_id)
    if not user:
        abort(404, description="User not found")
    
    alert = Alert.query.filter_by(id=alert_id, user_id=user_id).first()
    if not alert:
        abort(404, description="Alert not found or does not belong to this user")
    
    db.session.delete(alert)
    db.session.commit()
    
    app.logger.info("Admin deleted alert_id=%d for user_id=%s", alert_id, user_id)
    return jsonify({"message": "Alert deleted"}), 200


# ==================== Aggregated Reporting Endpoints (Feature 14) ====================

def _parse_report_dates(from_str, to_str):
    """Parse and validate optional from/to date query params.
    Returns (from_dt, to_dt) as datetime objects (or None).
    Raises 400 HTTPException on invalid input."""
    from_dt = None
    to_dt = None
    try:
        if from_str:
            from_dt = parser.parse(from_str)
        if to_str:
            to_dt = parser.parse(to_str)
    except (ValueError, OverflowError):
        abort(400, description="Invalid date format. Use ISO 8601 (e.g. 2026-01-01 or 2026-01-01T00:00:00)")
    if from_dt and to_dt and from_dt > to_dt:
        abort(400, description="'from' must be before 'to'")
    return from_dt, to_dt


@app.route("/admin/reports/volume", methods=["GET"])
@require_role("ADMIN")
def admin_report_volume():
    """Admin: total transaction volume (USD and LBP) within an optional date range."""
    from_dt, to_dt = _parse_report_dates(request.args.get("from"), request.args.get("to"))

    query = Transaction.query
    if from_dt:
        query = query.filter(Transaction.added_date >= from_dt)
    if to_dt:
        query = query.filter(Transaction.added_date <= to_dt)

    total_count = query.count()

    usd_to_lbp_q = query.filter(Transaction.usd_to_lbp == True)
    lbp_to_usd_q = query.filter(Transaction.usd_to_lbp == False)

    usd_sold   = db.session.query(func.sum(Transaction.usd_amount)).filter(
        Transaction.usd_to_lbp == True,
        *(([Transaction.added_date >= from_dt]) if from_dt else []),
        *(([Transaction.added_date <= to_dt])   if to_dt   else []),
    ).scalar() or 0.0

    lbp_sold   = db.session.query(func.sum(Transaction.lbp_amount)).filter(
        Transaction.usd_to_lbp == True,
        *(([Transaction.added_date >= from_dt]) if from_dt else []),
        *(([Transaction.added_date <= to_dt])   if to_dt   else []),
    ).scalar() or 0.0

    usd_bought = db.session.query(func.sum(Transaction.usd_amount)).filter(
        Transaction.usd_to_lbp == False,
        *(([Transaction.added_date >= from_dt]) if from_dt else []),
        *(([Transaction.added_date <= to_dt])   if to_dt   else []),
    ).scalar() or 0.0

    lbp_bought = db.session.query(func.sum(Transaction.lbp_amount)).filter(
        Transaction.usd_to_lbp == False,
        *(([Transaction.added_date >= from_dt]) if from_dt else []),
        *(([Transaction.added_date <= to_dt])   if to_dt   else []),
    ).scalar() or 0.0

    result = {
        "report": "volume",
        "filters": {
            "from": from_dt.isoformat() if from_dt else None,
            "to":   to_dt.isoformat()   if to_dt   else None,
        },
        "total_transactions": total_count,
        "usd_to_lbp": {
            "count":        usd_to_lbp_q.count(),
            "usd_volume":   round(float(usd_sold),   2),
            "lbp_volume":   round(float(lbp_sold),   2),
        },
        "lbp_to_usd": {
            "count":        lbp_to_usd_q.count(),
            "usd_volume":   round(float(usd_bought), 2),
            "lbp_volume":   round(float(lbp_bought), 2),
        },
        "totals": {
            "usd_volume": round(float(usd_sold) + float(usd_bought), 2),
            "lbp_volume": round(float(lbp_sold) + float(lbp_bought), 2),
        }
    }

    app.logger.info("Admin volume report: %d transactions (from=%s to=%s)",
                    total_count, from_dt, to_dt)
    return jsonify(result), 200


@app.route("/admin/reports/activity", methods=["GET"])
@require_role("ADMIN")
def admin_report_activity():
    """Admin: most active users ranked by transaction count + offer count within optional date range."""
    from_dt, to_dt = _parse_report_dates(request.args.get("from"), request.args.get("to"))
    limit = min(int(request.args.get("limit", 10)), 100)

    # Transaction counts per user
    tx_q = db.session.query(
        Transaction.user_id,
        func.count(Transaction.id).label("tx_count")
    )
    if from_dt:
        tx_q = tx_q.filter(Transaction.added_date >= from_dt)
    if to_dt:
        tx_q = tx_q.filter(Transaction.added_date <= to_dt)
    tx_q = tx_q.filter(Transaction.user_id.isnot(None)).group_by(Transaction.user_id)
    tx_counts = {row.user_id: row.tx_count for row in tx_q.all()}

    # Offer counts per user
    offer_q = db.session.query(
        Offer.creator_user_id,
        func.count(Offer.id).label("offer_count")
    )
    if from_dt:
        offer_q = offer_q.filter(Offer.created_at >= from_dt)
    if to_dt:
        offer_q = offer_q.filter(Offer.created_at <= to_dt)
    offer_q = offer_q.group_by(Offer.creator_user_id)
    offer_counts = {row.creator_user_id: row.offer_count for row in offer_q.all()}

    # Merge by user_id
    all_user_ids = set(tx_counts.keys()) | set(offer_counts.keys())
    users_by_id = {u.id: u.user_name for u in User.query.filter(User.id.in_(all_user_ids)).all()} if all_user_ids else {}

    rows = []
    for uid in all_user_ids:
        tx_c    = tx_counts.get(uid, 0)
        offer_c = offer_counts.get(uid, 0)
        rows.append({
            "user_id":           uid,
            "user_name":         users_by_id.get(uid, "unknown"),
            "transaction_count": tx_c,
            "offer_count":       offer_c,
            "total_activity":    tx_c + offer_c,
        })

    rows.sort(key=lambda r: r["total_activity"], reverse=True)
    rows = rows[:limit]

    result = {
        "report": "activity",
        "filters": {
            "from":  from_dt.isoformat() if from_dt else None,
            "to":    to_dt.isoformat()   if to_dt   else None,
            "limit": limit,
        },
        "total_active_users": len(rows),
        "users": rows,
    }

    app.logger.info("Admin activity report: %d active users (from=%s to=%s)", len(rows), from_dt, to_dt)
    return jsonify(result), 200


@app.route("/admin/reports/market", methods=["GET"])
@require_role("ADMIN")
def admin_report_market():
    """Admin: offer counts by status (OPEN/ACCEPTED/CANCELED) within optional date range."""
    from_dt, to_dt = _parse_report_dates(request.args.get("from"), request.args.get("to"))

    base_q = Offer.query
    if from_dt:
        base_q = base_q.filter(Offer.created_at >= from_dt)
    if to_dt:
        base_q = base_q.filter(Offer.created_at <= to_dt)

    status_counts = db.session.query(
        Offer.status,
        func.count(Offer.id).label("count")
    )
    if from_dt:
        status_counts = status_counts.filter(Offer.created_at >= from_dt)
    if to_dt:
        status_counts = status_counts.filter(Offer.created_at <= to_dt)
    status_counts = status_counts.group_by(Offer.status).all()

    counts_by_status = {row.status: row.count for row in status_counts}
    total = base_q.count()

    # USD vs LBP offer breakdown
    usd_offers = base_q.filter(Offer.from_currency == "USD").count()
    lbp_offers = base_q.filter(Offer.from_currency == "LBP").count()

    result = {
        "report": "market",
        "filters": {
            "from": from_dt.isoformat() if from_dt else None,
            "to":   to_dt.isoformat()   if to_dt   else None,
        },
        "total_offers": total,
        "by_status": {
            "OPEN":     counts_by_status.get("OPEN",     0),
            "ACCEPTED": counts_by_status.get("ACCEPTED", 0),
            "CANCELED": counts_by_status.get("CANCELED", 0),
        },
        "by_currency": {
            "USD_to_LBP": usd_offers,
            "LBP_to_USD": lbp_offers,
        },
        "acceptance_rate_pct": round(
            counts_by_status.get("ACCEPTED", 0) / total * 100, 1
        ) if total > 0 else 0.0,
    }

    app.logger.info("Admin market report: %d total offers (from=%s to=%s)", total, from_dt, to_dt)
    return jsonify(result), 200


# ==================== Wallet Endpoints (Feature 13) ====================

@app.route("/wallet", methods=["GET"])
def get_wallet():
    """Get current user's wallet balances"""
    user_id = get_user_id_from_token()
    
    wallet = Wallet.query.get(user_id)
    if not wallet:
        # Create wallet with 0 balances if it doesn't exist
        wallet = Wallet(user_id=user_id, usd_balance=0.0, lbp_balance=0.0)
        db.session.add(wallet)
        db.session.commit()
    
    return jsonify(wallet_schema.dump(wallet)), 200


@app.route("/wallet", methods=["PUT"])
def update_wallet():
    """Update wallet balances (for testing/admin purposes)"""
    user_id = get_user_id_from_token()
    
    data = request.get_json()
    if not data:
        abort(400, description="Request body is required")
    
    # Get or create wallet
    wallet = Wallet.query.get(user_id)
    if not wallet:
        wallet = Wallet(user_id=user_id)
        db.session.add(wallet)
    
    # Update balances if provided
    if "usd_balance" in data:
        try:
            usd_balance = float(data["usd_balance"])
            if usd_balance < 0:
                abort(400, description="usd_balance cannot be negative")
            wallet.usd_balance = usd_balance
        except (TypeError, ValueError):
            abort(400, description="usd_balance must be a number")
    
    if "lbp_balance" in data:
        try:
            lbp_balance = float(data["lbp_balance"])
            if lbp_balance < 0:
                abort(400, description="lbp_balance cannot be negative")
            wallet.lbp_balance = lbp_balance
        except (TypeError, ValueError):
            abort(400, description="lbp_balance must be a number")
    
    wallet.updated_at = datetime.datetime.now()
    db.session.commit()
    
    return jsonify(wallet_schema.dump(wallet)), 200


@app.route("/wallet/user/<int:user_id>", methods=["GET"])
def get_user_wallet(user_id):
    """Get any user's wallet balances (admin or for viewing)"""
    requester_id = get_user_id_from_token()
    
    wallet = Wallet.query.get(user_id)
    if not wallet:
        # Create wallet with 0 balances if it doesn't exist
        wallet = Wallet(user_id=user_id, usd_balance=0.0, lbp_balance=0.0)
        db.session.add(wallet)
        db.session.commit()
    
    return jsonify(wallet_schema.dump(wallet)), 200


# ==================== Backup / Restore Endpoints (Feature 15) ====================

# Default backup directory (relative to the package root, i.e. repo root/backups)
_DEFAULT_BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backups')

def _get_backup_dir():
    """Return backup directory; tests can override via app.config['BACKUP_DIR']."""
    return app.config.get('BACKUP_DIR', _DEFAULT_BACKUP_DIR)

def _ensure_backup_dir():
    os.makedirs(_get_backup_dir(), exist_ok=True)

def _serialize_model(instance):
    """Serialize any SQLAlchemy model row → plain dict (datetimes → ISO strings)."""
    result = {}
    for col in instance.__table__.columns:
        val = getattr(instance, col.name)
        if isinstance(val, datetime.datetime):
            val = val.isoformat()
        elif isinstance(val, bool):
            val = bool(val)
        result[col.name] = val
    return result

def _parse_dt(val):
    if val is None:
        return None
    try:
        return datetime.datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


@app.route("/admin/backup", methods=["POST"])
@require_role("ADMIN")
def admin_create_backup():
    """Trigger a full JSON backup of users, transactions, offers, alerts, preferences, and wallets."""
    _ensure_backup_dir()

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
    filename = f"backup_{timestamp}.json"
    filepath = os.path.join(_get_backup_dir(), filename)

    backup_data = {
        "backup_version": "1.0",
        "created_at": now.isoformat(),
        "tables": {
            "users":            [_serialize_model(r) for r in User.query.all()],
            "transactions":     [_serialize_model(r) for r in Transaction.query.all()],
            "offers":           [_serialize_model(r) for r in Offer.query.all()],
            "alerts":           [_serialize_model(r) for r in Alert.query.all()],
            "user_preferences": [_serialize_model(r) for r in UserPreference.query.all()],
            "wallets":          [_serialize_model(r) for r in Wallet.query.all()],
        }
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2)

    size_bytes = os.path.getsize(filepath)
    record_counts = {k: len(v) for k, v in backup_data["tables"].items()}

    log_audit_event("backup_created", success=True,
                    metadata={"filename": filename, "size_bytes": size_bytes, "counts": record_counts})

    app.logger.info("Backup created: %s (%d bytes)", filename, size_bytes)
    return jsonify({
        "message": "Backup created successfully",
        "filename": filename,
        "size_bytes": size_bytes,
        "created_at": backup_data["created_at"],
        "record_counts": record_counts,
    }), 200


@app.route("/admin/backup/status", methods=["GET"])
@require_role("ADMIN")
def admin_backup_status():
    """Return metadata about the latest backup and total backup count."""
    _ensure_backup_dir()
    backup_dir = _get_backup_dir()
    all_files = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".json")],
        reverse=True
    )

    if not all_files:
        return jsonify({
            "has_backup": False,
            "message": "No backups found. Run POST /admin/backup to create one.",
            "backup_dir": backup_dir,
        }), 200

    latest = all_files[0]
    latest_path = os.path.join(backup_dir, latest)
    size_bytes = os.path.getsize(latest_path)

    # Parse creation time from filename: backup_YYYYMMDD_HHMMSS_ffffff.json
    try:
        created_at = datetime.datetime.strptime(latest[7:-5], "%Y%m%d_%H%M%S_%f").isoformat()
    except ValueError:
        created_at = None

    # Count records in latest file
    try:
        with open(latest_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        record_counts = {k: len(v) for k, v in meta.get("tables", {}).items()}
        backup_version = meta.get("backup_version", "unknown")
    except Exception:
        record_counts = {}
        backup_version = "unknown"

    return jsonify({
        "has_backup": True,
        "latest_backup": {
            "filename": latest,
            "size_bytes": size_bytes,
            "created_at": created_at,
            "backup_version": backup_version,
            "record_counts": record_counts,
        },
        "total_backups": len(all_files),
        "all_backups": all_files,
        "backup_dir": backup_dir,
    }), 200


@app.route("/admin/restore", methods=["POST"])
@require_role("ADMIN")
def admin_restore_backup():
    """Restore data from a backup file. Uses latest backup if no filename is given."""
    _ensure_backup_dir()
    backup_dir = _get_backup_dir()

    data = request.get_json(silent=True) or {}
    filename = data.get("filename")

    if filename:
        # Sanitize: reject path traversal, enforce naming convention
        filename = os.path.basename(filename)
        if not (filename.startswith("backup_") and filename.endswith(".json")):
            abort(400, description="Invalid backup filename. Must be a .json file starting with 'backup_'")
        filepath = os.path.join(backup_dir, filename)
        if not os.path.exists(filepath):
            abort(404, description=f"Backup file '{filename}' not found")
    else:
        all_files = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".json")],
            reverse=True
        )
        if not all_files:
            abort(404, description="No backup files found. Run POST /admin/backup first.")
        filename = all_files[0]
        filepath = os.path.join(backup_dir, filename)

    # Load & validate structure
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        abort(400, description=f"Could not read backup file: {e}")

    if "tables" not in backup_data:
        abort(400, description="Invalid backup format: missing 'tables' key")

    tables = backup_data["tables"]
    required = {"users", "transactions", "offers", "alerts", "user_preferences", "wallets"}
    missing = required - set(tables.keys())
    if missing:
        abort(400, description=f"Invalid backup: missing table(s): {sorted(missing)}")

    try:
        # Delete in FK-safe order (children before parents)
        Wallet.query.delete()
        UserPreference.query.delete()
        Alert.query.delete()
        Trade.query.delete()
        Transaction.query.delete()
        Offer.query.delete()
        User.query.delete()
        db.session.flush()

        # Restore users (call real __init__ then override with saved hash + id)
        for row in tables["users"]:
            u = User(user_name=row["user_name"], password="__restore__",
                     role=row.get("role", "USER"))
            u.hashed_password = row["hashed_password"]  # overwrite placeholder hash
            u.id         = row["id"]
            u.status     = row.get("status", "ACTIVE")
            u.created_at = _parse_dt(row.get("created_at"))
            db.session.add(u)
        db.session.flush()

        # Restore transactions
        for row in tables["transactions"]:
            t = Transaction(usd_amount=row["usd_amount"], lbp_amount=row["lbp_amount"],
                            usd_to_lbp=row["usd_to_lbp"], user_id=row.get("user_id"))
            t.id         = row["id"]
            t.added_date = _parse_dt(row.get("added_date"))
            db.session.add(t)

        # Restore offers
        for row in tables["offers"]:
            o = Offer(creator_user_id=row["creator_user_id"], from_currency=row["from_currency"],
                      to_currency=row["to_currency"], amount_from=row["amount_from"],
                      rate=row["rate"])
            o.id         = row["id"]
            o.status     = row.get("status", "OPEN")
            o.created_at = _parse_dt(row.get("created_at"))
            o.updated_at = _parse_dt(row.get("updated_at"))
            db.session.add(o)
        db.session.flush()

        # Restore alerts
        for row in tables["alerts"]:
            a = Alert(user_id=row["user_id"], direction=row["direction"],
                      threshold=row["threshold"], condition=row["condition"])
            a.id           = row["id"]
            a.triggered    = row.get("triggered", False)
            a.triggered_at = _parse_dt(row.get("triggered_at"))
            a.created_at   = _parse_dt(row.get("created_at"))
            db.session.add(a)

        # Restore user preferences
        for row in tables["user_preferences"]:
            p = UserPreference(user_id=row["user_id"],
                               default_from_range_hours=row.get("default_from_range_hours", 24),
                               default_interval=row.get("default_interval", "hour"),
                               default_direction=row.get("default_direction", "USD_LBP"))
            p.updated_at = _parse_dt(row.get("updated_at"))
            db.session.add(p)

        # Restore wallets
        for row in tables["wallets"]:
            w = Wallet(user_id=row["user_id"],
                       usd_balance=row.get("usd_balance", 0.0),
                       lbp_balance=row.get("lbp_balance", 0.0))
            w.created_at = _parse_dt(row.get("created_at"))
            w.updated_at = _parse_dt(row.get("updated_at"))
            db.session.add(w)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        app.logger.exception("Restore failed from %s", filename)
        abort(500, description=f"Restore failed: {str(e)}")

    restored_counts = {k: len(tables[k]) for k in required}
    log_audit_event("backup_restored", success=True,
                    metadata={"filename": filename, "counts": restored_counts})

    app.logger.info("Restore completed from %s: %s", filename, restored_counts)
    return jsonify({
        "message": "Restore completed successfully",
        "filename": filename,
        "restored_counts": restored_counts,
    }), 200



def handle_rate_limit_exceeded(err):
    app.logger.warning("Rate limit exceeded on %s: %s", request.path, err.description)
    return jsonify({
        "error": "Too Many Requests",
        "message": "Rate limit exceeded. Please try again later.",
        "status": 429,
        "retry_after": err.description
    }), 429


@app.errorhandler(HTTPException)
def handle_http_exception(err):
    app.logger.warning("HTTP %s on %s: %s", err.code, request.path, err.description)
    return jsonify({
        "error": err.name,
        "message": err.description,
        "status": err.code
    }), err.code


@app.errorhandler(Exception)
def handle_exception(err):
    app.logger.exception("Unhandled exception on %s", request.path)
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "status": 500
    }), 500


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
