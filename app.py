import os
import csv
import uuid
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
import json

app = Flask(__name__)

# Secret key for session management (use env var in production)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'development-fallback-key-123')

# Simple JSON based user store
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2)

def get_user(username):
    users = load_users()
    return users.get(username)

def create_user(username, password_hash):
    users = load_users()
    if username in users:
        return False
    users[username] = {'password_hash': password_hash}
    save_users(users)
    return True



CSV_FILE = os.path.join(os.path.dirname(__file__), 'transactions.csv')

def ensure_csv_exists():
    """Ensure the transactions.csv file exists in the root directory."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'date', 'description', 'type', 'category', 'amount'])

def read_transactions():
    """Read and parse all transactions from the CSV database."""
    ensure_csv_exists()
    transactions = []
    with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row['amount'] = float(row['amount'])
                transactions.append(row)
            except (ValueError, KeyError):
                continue
    # Sort transactions by date descending, then id descending
    transactions.sort(key=lambda x: (x['date'], x['id']), reverse=True)
    return transactions

def write_transactions(transactions):
    """Write the full list of transactions back to the CSV database."""
    ensure_csv_exists()
    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
        fieldnames = ['id', 'date', 'description', 'type', 'category', 'amount']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        # Sort transactions by date descending before saving to preserve order
        transactions.sort(key=lambda x: (x['date'], x['id']), reverse=True)
        for tx in transactions:
            writer.writerow({
                'id': tx['id'],
                'date': tx['date'],
                'description': tx['description'].strip(),
                'type': tx['type'],
                'category': tx['category'].strip(),
                'amount': f"{float(tx['amount']):.2f}"
            })

def calculate_summary(transactions):
    """Compute financial summary statistics and category breakdowns."""
    total_income = sum(tx['amount'] for tx in transactions if tx['type'] == 'income')
    total_expense = sum(tx['amount'] for tx in transactions if tx['type'] == 'expense')
    balance = total_income - total_expense

    # Category breakdowns for expense
    categories = {}
    for tx in transactions:
        if tx['type'] == 'expense':
            cat = tx['category']
            categories[cat] = categories.get(cat, 0.0) + tx['amount']
            
    # Format category sums to 2 decimal places
    for cat in categories:
        categories[cat] = round(categories[cat], 2)

    return {
        'total_income': round(total_income, 2),
        'total_expense': round(total_expense, 2),
        'balance': round(balance, 2),
        'categories': categories
    }

def login_required(f):
    """Decorator to protect routes requiring authentication."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    """Render the dashboard application shell (requires login)."""
    return render_template('index.html')

@app.route('/auth')
def auth():
    """Render login/register page."""
    return render_template('auth.html')

# Register endpoint
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    from werkzeug.security import generate_password_hash
    password_hash = generate_password_hash(password)
    if not create_user(username, password_hash):
        return jsonify({'success': False, 'error': 'User already exists'}), 409
    # Auto‑login after registration
    session['user_id'] = username
    session['username'] = username
    return jsonify({'success': True, 'message': 'Registered and logged in'}), 201

# Login endpoint
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    user = get_user(username)
    if not user:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    from werkzeug.security import check_password_hash
    if not check_password_hash(user['password_hash'], password):
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    session['user_id'] = username
    session['username'] = username
    return jsonify({'success': True, 'message': 'Logged in'}), 200


@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    """Retrieve transaction list and summaries. Supports filtering and search."""
    try:
        transactions = read_transactions()
        
        # Extract query parameters
        search_query = request.args.get('search', '').strip().lower()
        filter_type = request.args.get('type', '').strip().lower()
        filter_category = request.args.get('category', '').strip().lower()
        
        filtered = transactions
        
        # Apply search filter
        if search_query:
            filtered = [tx for tx in filtered if search_query in tx['description'].lower() or search_query in tx['category'].lower()]
            
        # Apply type filter
        if filter_type in ['income', 'expense']:
            filtered = [tx for tx in filtered if tx['type'] == filter_type]
            
        # Apply category filter
        if filter_category:
            filtered = [tx for tx in filtered if tx['category'].lower() == filter_category]

        summary = calculate_summary(transactions)
        
        return jsonify({
            'success': True,
            'transactions': filtered,
            'summary': summary
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    """Add a new transaction to the CSV database."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        # Extract and validate fields
        description = data.get('description', '').strip()
        tx_type = data.get('type', '').strip().lower()
        category = data.get('category', '').strip()
        amount_val = data.get('amount')
        date = data.get('date', '').strip()
        
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
        if tx_type not in ['income', 'expense']:
            return jsonify({'success': False, 'error': 'Invalid transaction type'}), 400
        if not category:
            return jsonify({'success': False, 'error': 'Category is required'}), 400
        if not date:
            return jsonify({'success': False, 'error': 'Date is required'}), 400
            
        try:
            amount = float(amount_val)
            if amount <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Amount must be a positive number'}), 400
        
        # Load existing, add new transaction, and write back
        transactions = read_transactions()
        
        new_tx = {
            'id': f"tx_{uuid.uuid4().hex[:8]}",
            'date': date,
            'description': description,
            'type': tx_type,
            'category': category,
            'amount': amount
        }
        
        transactions.append(new_tx)
        write_transactions(transactions)
        
        return jsonify({
            'success': True,
            'transaction': new_tx,
            'summary': calculate_summary(transactions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/<tx_id>', methods=['PUT'])
@login_required
def update_transaction(tx_id):
    """Update an existing transaction in the CSV database."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        description = data.get('description', '').strip()
        tx_type = data.get('type', '').strip().lower()
        category = data.get('category', '').strip()
        amount_val = data.get('amount')
        date = data.get('date', '').strip()

        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
        if tx_type not in ['income', 'expense']:
            return jsonify({'success': False, 'error': 'Invalid transaction type'}), 400
        if not category:
            return jsonify({'success': False, 'error': 'Category is required'}), 400
        if not date:
            return jsonify({'success': False, 'error': 'Date is required'}), 400

        try:
            amount = float(amount_val)
            if amount <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Amount must be a positive number'}), 400

        transactions = read_transactions()
        updated_tx = None

        for tx in transactions:
            if tx['id'] == tx_id:
                tx['date'] = date
                tx['description'] = description
                tx['type'] = tx_type
                tx['category'] = category
                tx['amount'] = amount
                updated_tx = tx
                break

        if not updated_tx:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404

        write_transactions(transactions)

        return jsonify({
            'success': True,
            'transaction': updated_tx,
            'summary': calculate_summary(transactions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/<tx_id>', methods=['DELETE'])
@login_required
def delete_transaction(tx_id):
    """Delete a transaction from the CSV database."""
    try:
        transactions = read_transactions()
        original_length = len(transactions)
        
        # Filter out the transaction with the given id
        transactions = [tx for tx in transactions if tx['id'] != tx_id]
        
        if len(transactions) == original_length:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404
            
        write_transactions(transactions)
        
        return jsonify({
            'success': True,
            'message': 'Transaction deleted successfully',
            'summary': calculate_summary(transactions)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/transactions/download', methods=['GET'])
def download_transactions():
    """Allows downloading the CSV database file directly."""
    try:
        ensure_csv_exists()
        return send_file(
            CSV_FILE,
            mimetype='text/csv',
            as_attachment=True,
            download_name='transactions.csv'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Log the user out and clear the session."""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'}), 200

    app.run(debug=True, port=5000)
