import os
import uuid
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# Secret key for session management
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-fallback-key-123')

# --- DATABASE SETUP (SUPABASE / LOCAL FALLBACK) ---
db_url = os.environ.get('DATABASE_URL')

if db_url:
    # Fix the SQLAlchemy compatibility bug (changes postgres:// to postgresql://)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    # Local fallback for your machine so it doesn't crash during offline testing
    db_url = 'sqlite:///local_budget.db'

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- DATABASE MODELS ---
class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(80), primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.String(50), primary_key=True)
    date = db.Column(db.String(10), nullable=False)       # Format: YYYY-MM-DD
    description = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)        # income or expense
    category = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

# Force the database tables to be created automatically on startup
with app.app_context():
    db.create_all()


# --- REWRITTEN HELPER FUNCTIONS (DATABASE DRIVEN) ---
def get_user(username):
    return User.query.filter_by(username=username).first()

def create_user(username, password_hash):
    if get_user(username):
        return False
    try:
        new_user = User(username=username, password_hash=password_hash)
        db.session.add(new_user)
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
        return False

def read_transactions():
    """Read all transactions from the database sorted by date descending."""
    try:
        db_txs = Transaction.query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        transactions = []
        for tx in db_txs:
            transactions.append({
                'id': tx.id,
                'date': tx.date,
                'description': tx.description,
                'type': tx.type,
                'category': tx.category,
                'amount': tx.amount
            })
        return transactions
    except Exception as e:
        print(f"Database read error: {e}")
        return []


# --- ANALYTICS ENGINE ---
def calculate_summary(transactions):
    """Compute financial summary statistics and category breakdowns."""
    total_income = sum(tx['amount'] for tx in transactions if tx['type'] == 'income')
    total_expense = sum(tx['amount'] for tx in transactions if tx['type'] == 'expense')
    balance = total_income - total_expense

    categories = {}
    for tx in transactions:
        if tx['type'] == 'expense':
            cat = tx['category']
            categories[cat] = categories.get(cat, 0.0) + tx['amount']
            
    for cat in categories:
        categories[cat] = round(categories[cat], 2)

    return {
        'total_income': round(total_income, 2),
        'total_expense': round(total_expense, 2),
        'balance': round(balance, 2),
        'categories': categories
    }


# --- ROUTES & AUTH ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    
    password_hash = generate_password_hash(password)
    if not create_user(username, password_hash):
        return jsonify({'success': False, 'error': 'User already exists'}), 409
    
    session['user_id'] = username
    session['username'] = username
    return jsonify({'success': True, 'message': 'Registered and logged in'}), 201

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    
    user = get_user(username)
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
    session['user_id'] = username
    session['username'] = username
    return jsonify({'success': True, 'message': 'Logged in'}), 200


# --- TRANSACTION API ENDPOINTS ---
@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    try:
        transactions = read_transactions()
        search_query = request.args.get('search', '').strip().lower()
        filter_type = request.args.get('type', '').strip().lower()
        filter_category = request.args.get('category', '').strip().lower()
        
        filtered = transactions
        if search_query:
            filtered = [tx for tx in filtered if search_query in tx['description'].lower() or search_query in tx['category'].lower()]
        if filter_type in ['income', 'expense']:
            filtered = [tx for tx in filtered if tx['type'] == filter_type]
        if filter_category:
            filtered = [tx for tx in filtered if tx['category'].lower() == filter_category]

        summary = calculate_summary(transactions)
        return jsonify({'success': True, 'transactions': filtered, 'summary': summary})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    try:
        data = request.get_json() or {}
        description = data.get('description', '').strip()
        tx_type = data.get('type', '').strip().lower()
        category = data.get('category', '').strip()
        amount_val = data.get('amount')
        date = data.get('date', '').strip()
        
        if not description or not category or not date or amount_val is None:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        if tx_type not in ['income', 'expense']:
            return jsonify({'success': False, 'error': 'Invalid transaction type'}), 400
            
        try:
            amount_float = float(amount_val)
        except ValueError:
            return jsonify({'success': False, 'error': 'Amount must be a number'}), 400

        # Save straight to Supabase
        new_tx = Transaction(
            id=str(uuid.uuid4())[:8],  # Generates a clean 8-character ID
            date=date,
            description=description,
            type=tx_type,
            category=category,
            amount=amount_float
        )
        db.session.add(new_tx)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Transaction added successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
