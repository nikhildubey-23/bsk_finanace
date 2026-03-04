from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from urllib.parse import unquote
import os
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime
import uuid
import re
import platform
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import scanner module
try:
    from scanner import get_scanners, scan_document
    SCANNER_AVAILABLE = True
except ImportError:
    SCANNER_AVAILABLE = False
    print("Scanner module not available. Run: pip install comtypes")

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    try:
        conn = sqlite3.connect('documents.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        flash("Database connection error. Please try again.", "error")
        return None

# Helper function for safe database operations
def safe_db_execute(query, params=(), fetch=True):
    try:
        conn = get_db_connection()
        if conn is None:
            return None if fetch else False
        
        cursor = conn.execute(query, params)
        if fetch:
            result = cursor.fetchall()
            conn.close()
            return result
        else:
            conn.commit()
            conn.close()
            return True
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        flash(f"Database error: {str(e)}", "error")
        return None if fetch else False
    except Exception as e:
        logger.error(f"Error in database operation: {e}")
        flash("An error occurred", "error")
        return None if fetch else False

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {error}")
    return render_template('error.html', error_code=500, error_message="Something went wrong"), 500

def create_client_folder(client_name):
    # Clean client name to create valid folder name
    clean_name = re.sub(r'[^\w\s-]', '', client_name.strip())
    clean_name = re.sub(r'[-\s]+', '-', clean_name)
    
    # Base folder path
    base_path = os.path.join(app.config['UPLOAD_FOLDER'], clean_name)
    
    # If folder doesn't exist, create it
    if not os.path.exists(base_path):
        os.makedirs(base_path)
        return clean_name
    
    # If folder exists, add number suffix
    counter = 1
    while True:
        folder_name = f"{clean_name}_{counter}"
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            return folder_name
        counter += 1

def get_client_folder_path(client_id, client_name):
    # Get existing folder for this client or create new one
    conn = get_db_connection()
    result = conn.execute('SELECT folder_name FROM clients WHERE id = ?', (client_id,)).fetchone()
    
    if result and result['folder_name']:
        folder_name = result['folder_name']
    else:
        # Create new folder and update database
        folder_name = create_client_folder(client_name)
        conn.execute('UPDATE clients SET folder_name = ? WHERE id = ?', (folder_name, client_id))
        conn.commit()
    
    conn.close()
    return os.path.join(app.config['UPLOAD_FOLDER'], folder_name)

def init_db():
    conn = get_db_connection()
    
    # Create clients table with all required columns
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            folder_name TEXT,
            client_type TEXT,
            policy_number TEXT,
            pan_card TEXT,
            address TEXT,
            policy_expiry_date TEXT,
            premium_amount TEXT,
            policy_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if new columns exist, add them if they don't
    try:
        # Check existing columns
        cursor = conn.execute('PRAGMA table_info(clients)')
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add missing columns
        if 'folder_name' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN folder_name TEXT')
        if 'client_type' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN client_type TEXT')
        if 'policy_number' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN policy_number TEXT')
        if 'pan_card' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN pan_card TEXT')
        if 'address' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN address TEXT')
        if 'policy_expiry_date' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN policy_expiry_date TEXT')
        if 'premium_amount' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN premium_amount TEXT')
        if 'policy_type' not in columns:
            conn.execute('ALTER TABLE clients ADD COLUMN policy_type TEXT')
            
    except Exception as e:
        print(f"Error adding columns: {e}")
    
    # Create documents table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            daily_entry_id INTEGER,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT,
            document_name TEXT,
            document_date TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id),
            FOREIGN KEY (daily_entry_id) REFERENCES daily_entries (id)
        )
    ''')
    
    # Check if documents table has new columns
    try:
        cursor = conn.execute('PRAGMA table_info(documents)')
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'document_name' not in columns:
            conn.execute('ALTER TABLE documents ADD COLUMN document_name TEXT')
        if 'document_date' not in columns:
            conn.execute('ALTER TABLE documents ADD COLUMN document_date TEXT')
        if 'daily_entry_id' not in columns:
            conn.execute('ALTER TABLE documents ADD COLUMN daily_entry_id INTEGER REFERENCES daily_entries(id)')
            
    except Exception as e:
        print(f"Error adding document columns: {e}")
    
    # Create whatsapp_sent table to track sent messages
    conn.execute('''
        CREATE TABLE IF NOT EXISTS whatsapp_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            template_id TEXT,
            message TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')
    
    # Create daily_entries table to track daily activities
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date DATE,
            client_name TEXT,
            investment_type TEXT,
            lic_subtype TEXT,
            lic_policy_number TEXT,
            lic_plan_term TEXT,
            amount REAL,
            note TEXT,
            file_no TEXT,
            pan_card TEXT,
            address TEXT,
            hi_policy TEXT,
            hi_dob DATE,
            hi_plan_term TEXT,
            hi_doc DATE,
            hi_year TEXT,
            hi_sum_assured REAL,
            mf_folio TEXT,
            mf_company_id INTEGER,
            mf_fund_id INTEGER,
            mf_fund_id_to INTEGER,
            mf_subtype TEXT,
            mf_stp_date DATE,
            mf_stp_start_date DATE,
            mf_stp_end_date DATE,
            mf_sip_amount REAL,
            mf_sip_date INTEGER,
            mf_sip_start_date DATE,
            mf_sip_end_date DATE,
            mf_transmission_type TEXT,
            mf_claimant_name TEXT,
            mf_claimant_relation TEXT,
            mf_companies TEXT,
            mf_folios TEXT,
            mf_sip_frequency TEXT,
            mf_switch_fund_from INTEGER,
            mf_switch_fund_to INTEGER,
            mf_new_address TEXT,
            mf_old_bank_detail TEXT,
            mf_new_bank_detail TEXT,
            mf_fund_type TEXT,
            mf_fund_subtype TEXT,
            client_id INTEGER,
            hi_company_id INTEGER,
            hi_product_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add missing columns to daily_entries if they don't exist
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN it_address TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN id_type TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN stp_fund_type TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN stp_fund_subtype TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN switch_fund_type TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN switch_fund_subtype TEXT')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN mf_swp_amount REAL')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN mf_swp_start_date DATE')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN mf_swp_end_date DATE')
    except:
        pass
    try:
        conn.execute('ALTER TABLE daily_entries ADD COLUMN hi_expiry_date DATE')
    except:
        pass
    
    # Create MF companies table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mf_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add fund_type column to mf_funds if it doesn't exist
    try:
        conn.execute('ALTER TABLE mf_funds ADD COLUMN fund_type TEXT')
    except:
        pass
    
    # Create MF funds table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mf_funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            fund_name TEXT NOT NULL,
            fund_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES mf_companies(id)
        )
    ''')
    
    # Create Health Insurance companies table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS hi_companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Health Insurance products table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS hi_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES hi_companies(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_demo_data():
    conn = get_db_connection()
    
    # Check if demo data already exists
    existing_clients = conn.execute('SELECT COUNT(*) as count FROM clients').fetchone()
    if existing_clients['count'] > 0:
        conn.close()
        return
    
    # Add demo clients
    clients_data = [
        ('Rajesh Kumar', '9876543210', 'rajesh@email.com', 'LIC', 'LIC123456', 'ABCDE1234F', '123 Main Street, Delhi'),
        ('Priya Sharma', '9876543211', 'priya@email.com', 'Mutual Fund', 'MF789012', 'FGHIJ5678K', '456 Oak Avenue, Mumbai'),
        ('Amit Patel', '9876543212', 'amit@email.com', 'Both', 'LIC456789', 'KLMNO9012P', '789 Pine Road, Bangalore'),
        ('Sneha Reddy', '9876543213', 'sneha@email.com', 'Health Insurance', 'HI234567', 'PQRST3456U', '321 Cedar Lane, Chennai'),
        ('Vikram Singh', '9876543214', 'vikram@email.com', 'Income Tax', 'IT890123', 'UVWXY7890Z', '654 Birch Street, Kolkata'),
    ]
    
    client_ids = []
    for client in clients_data:
        conn.execute('INSERT INTO clients (name, phone, email, client_type, policy_number, pan_card, address) VALUES (?, ?, ?, ?, ?, ?, ?)', client)
        client_ids.append(conn.execute('SELECT last_insert_rowid()').fetchone()[0])
    
    # Add demo MF companies
    mf_companies = [
        ('HDFC Asset Management',),
        ('ICICI Prudential',),
        ('SBI Mutual Fund',),
        ('Axis Mutual Fund',),
        ('UTI Mutual Fund',),
    ]
    
    mf_company_ids = []
    for company in mf_companies:
        conn.execute('INSERT INTO mf_companies (name) VALUES (?)', company)
        mf_company_ids.append(conn.execute('SELECT last_insert_rowid()').fetchone()[0])
    
    # Add demo MF funds
    mf_funds_data = [
        (mf_company_ids[0], 'HDFC Top 100 Fund', 'Growth'),
        (mf_company_ids[0], 'HDFC Mid-Cap Opportunities', 'Dividend'),
        (mf_company_ids[1], 'ICICI Prudential Bluechip', 'Growth'),
        (mf_company_ids[1], 'ICICI Prudential Value Discovery', 'Dividend'),
        (mf_company_ids[2], 'SBI Small Cap Fund', 'Growth'),
        (mf_company_ids[2], 'SBI Bluechip Fund', 'Dividend'),
        (mf_company_ids[3], 'Axis Long Term Equity', 'Growth'),
        (mf_company_ids[3], 'Axis Midcap Fund', 'Dividend'),
        (mf_company_ids[4], 'UTI Nifty Index Fund', 'Growth'),
    ]
    
    for fund in mf_funds_data:
        conn.execute('INSERT INTO mf_funds (company_id, fund_name, fund_type) VALUES (?, ?, ?)', fund)
    
    # Add demo HI companies
    hi_companies = [
        ('Star Health Insurance',),
        ('HDFC Ergo General Insurance',),
        ('ICICI Lombard',),
        ('Bajaj Allianz',),
        ('Care Health Insurance',),
    ]
    
    hi_company_ids = []
    for company in hi_companies:
        conn.execute('INSERT INTO hi_companies (name) VALUES (?)', company)
        hi_company_ids.append(conn.execute('SELECT last_insert_rowid()').fetchone()[0])
    
    # Add demo HI products
    hi_products_data = [
        (hi_company_ids[0], 'Star Family Health Optima'),
        (hi_company_ids[0], 'Star Health Complete'),
        (hi_company_ids[1], 'HDFC Ergo Health Suraksha'),
        (hi_company_ids[1], 'HDFC Ergo My Health'),
        (hi_company_ids[2], 'ICICI Lombard Health Insurance'),
        (hi_company_ids[2], 'ICICI Lombard Complete Health'),
        (hi_company_ids[3], 'Bajaj Allianz Health Insurance'),
        (hi_company_ids[4], 'Care Health Insurance'),
    ]
    
    for product in hi_products_data:
        conn.execute('INSERT INTO hi_products (company_id, product_name) VALUES (?, ?)', product)
    
    # Add demo daily entries
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)
    last_month = today - timedelta(days=30)
    
    entries_data = [
        # LIC Entries
        (str(today), 'Rajesh Kumar', 'LIC', 'New Policy', 'LIC/2024/001', '25 Years', 50000, 'New endowment policy', 'LIC123456', 'ABCDE1234F', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[0], None, None),
        (str(yesterday), 'Amit Patel', 'LIC', 'Surrender', 'LIC/2024/002', '15 Years', 25000, 'Policy surrender request', 'LIC456789', 'KLMNO9012P', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[2], None, None),
        (str(last_week), 'Rajesh Kumar', 'LIC', 'Nominee Change', 'LIC/2024/003', '25 Years', 0, 'Nominee changed to wife', 'LIC123456', 'ABCDE1234F', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[0], None, None),
        
        # Mutual Fund Entries
        (str(today), 'Priya Sharma', 'Mutual Fund', 'Purchase', None, None, 100000, 'Invested in growth fund', None, None, '1', mf_company_ids[0], '1', 'Purchase', None, None, None, None, None, None, 'Monthly', None, None, None, None, 'Growth', None, client_ids[1], None, None),
        (str(yesterday), 'Amit Patel', 'Mutual Fund', 'SIP', None, None, 5000, 'Monthly SIP started', None, None, '10', mf_company_ids[1], '1', 'SIP', None, None, None, 5000, '10', None, None, 'Monthly', None, None, None, None, None, 'Dividend', 'IDCW', client_ids[2], None, None),
        (str(last_week), 'Priya Sharma', 'Mutual Fund', 'Redemption', None, None, 25000, 'Partial redemption', None, None, '1', mf_company_ids[0], '1', 'Redemption', None, None, None, None, None, None, None, None, None, None, None, None, None, 'Growth', None, client_ids[1], None, None),
        (str(last_month), 'Amit Patel', 'Mutual Fund', 'STP', None, None, 50000, 'STP from bluechip to small cap', None, None, '1', mf_company_ids[1], '5', 'STP', '15', str(last_week), str(today), None, None, None, None, 'Monthly', None, None, None, None, None, None, client_ids[2], None, None),
        (str(last_week), 'Priya Sharma', 'Mutual Fund', 'Switch', None, None, 0, 'Switch from old fund to new', None, None, '1', mf_company_ids[0], '3', 'Switch', None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[1], None, None),
        
        # Health Insurance Entries
        (str(today), 'Sneha Reddy', 'Health Insurance', 'New Policy', None, None, 15000, 'Family health policy', None, None, None, None, None, None, None, '1', str(today), '3', 5000000, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[3], hi_company_ids[0], '1'),
        (str(yesterday), 'Vikram Singh', 'Health Insurance', 'Renewal', None, None, 12000, 'Policy renewed', None, None, None, None, None, None, None, '1', str(last_year), '2', 3000000, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[4], hi_company_ids[1], '2'),
        
        # Income Tax Entries
        (str(today), 'Vikram Singh', 'Income Tax', 'ITR Filing', None, None, 5000, 'ITR filed for FY 2023-24', 'IT/2024/001', 'UVWXY7890Z', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[4], None, None),
        (str(last_week), 'Rajesh Kumar', 'Income Tax', 'Tax Planning', None, None, 3000, 'Tax saving investments planned', 'IT/2024/002', 'ABCDE1234F', None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, client_ids[0], None, None),
    ]
    
    last_year = today - timedelta(days=365)
    
    for entry in entries_data:
        conn.execute('''
            INSERT INTO daily_entries (
                entry_date, client_name, investment_type, lic_subtype, lic_policy_number, lic_plan_term, 
                amount, note, file_no, pan_card, address, hi_policy, hi_dob, hi_plan_term, hi_doc, 
                hi_year, hi_sum_assured, mf_folio, mf_company_id, mf_fund_id, mf_fund_id_to, 
                mf_subtype, mf_stp_date, mf_stp_start_date, mf_stp_end_date, mf_sip_amount, 
                mf_sip_date, mf_sip_start_date, mf_sip_end_date, mf_sip_frequency, 
                mf_switch_fund_from, mf_switch_fund_to, mf_fund_type, mf_fund_subtype, client_id,
                hi_company_id, hi_product_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', entry)
    
    conn.commit()
    conn.close()
    print("Demo data added successfully!")

# Add demo data on startup
# with app.app_context():
#     add_demo_data()

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error in index: {e}")
        flash("Error loading dashboard", "error")
        return render_template('error.html', error_code=500, error_message="Error loading dashboard")

@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    try:
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('add_client'))
        
        clients = conn.execute('SELECT id, name, phone, email FROM clients ORDER BY name').fetchall()
        conn.close()
        
        if request.method == 'POST':
            name = request.form['client_name']
            phone = request.form['phone']
            email = request.form['email']
            client_type = request.form.get('client_type', '')
            policy_number = request.form.get('policy_number', '')
            pan_card = request.form.get('pan_card', '')
            address = request.form.get('address', '')
            
            conn = get_db_connection()
            conn.execute('INSERT INTO clients (name, phone, email, client_type, policy_number, pan_card, address) VALUES (?, ?, ?, ?, ?, ?, ?)',
                        (name, phone, email, client_type, policy_number, pan_card, address))
            conn.commit()
            conn.close()
            
            flash('Client added successfully!')
            return redirect(url_for('index'))
        
        return render_template('add_client.html', clients=clients)
    except Exception as e:
        logger.error(f"Error in add_client: {e}")
        flash("Error adding client", "error")
        return redirect(url_for('add_client'))

@app.route('/search_client', methods=['GET', 'POST'])
def search_client():
    try:
        clients = []
        search_term = ""
        search_results = 0
        
        if request.method == 'POST':
            search_term = request.form.get('search_term', '').strip()
            if search_term:
                conn = get_db_connection()
                if conn is None:
                    return render_template('search_client.html', clients=[], search_term=search_term, search_results=0)
                clients = conn.execute('''
                    SELECT c.*, COUNT(d.id) as document_count 
                    FROM clients c 
                    LEFT JOIN documents d ON c.id = d.client_id 
                    WHERE c.name LIKE ? OR c.phone LIKE ? OR c.email LIKE ?
                    GROUP BY c.id
                    ORDER BY c.name
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')).fetchall()
                search_results = len(clients)
                conn.close()
        
        return render_template('search_client.html', clients=clients, search_term=search_term, search_results=search_results)
    except Exception as e:
        logger.error(f"Error in search_client: {e}")
        flash("Error searching clients", "error")
        return render_template('search_client.html', clients=[], search_term="", search_results=0)

@app.route('/client/<int:client_id>')
def client_details(client_id):
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database error", "error")
            return redirect(url_for('search_client'))
        client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
        documents = conn.execute(
            'SELECT * FROM documents WHERE client_id = ? ORDER BY upload_date DESC',
            (client_id,)
        ).fetchall()
        conn.close()
        
        if client is None:
            flash('Client not found!')
            return redirect(url_for('search_client'))
        
        return render_template('client_details.html', client=client, documents=documents)
    except Exception as e:
        logger.error(f"Error in client_details: {e}")
        flash("Error loading client details", "error")
        return redirect(url_for('search_client'))

@app.route('/upload_document/<int:client_id>', methods=['GET', 'POST'])
def upload_document(client_id):
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected!')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected!')
            return redirect(request.url)
        
        document_name = request.form.get('document_name', '')
        document_date = request.form.get('document_date', '')
        
        if file and allowed_file(file.filename):
            # Get client info
            conn = get_db_connection()
            client = conn.execute('SELECT name FROM clients WHERE id = ?', (client_id,)).fetchone()
            client_name = client['name']
            
            # Get client folder path
            client_folder_path = get_client_folder_path(client_id, client_name)
            
            # Generate unique filename
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename or '')
            file_path = os.path.join(client_folder_path, filename)
            file.save(file_path)
            
            # Save only relative path in database (use forward slashes for URLs)
            folder_name = os.path.basename(client_folder_path)
            relative_filename = f"{folder_name}/{filename}"
            
            conn.execute(
                'INSERT INTO documents (client_id, filename, original_filename, file_type, document_name, document_date) VALUES (?, ?, ?, ?, ?, ?)',
                (client_id, relative_filename, file.filename, filename.rsplit('.', 1)[1].lower(), document_name, document_date)
            )
            conn.commit()
            conn.close()
            
            flash('Document uploaded successfully!')
            return redirect(url_for('client_details', client_id=client_id))
        else:
            flash('Invalid file type!')
    
    return render_template('upload_document.html', client_id=client_id)

@app.route('/download/<path:filename>')
def download_file(filename):
    # Handle both forward and back slashes
    filename = unquote(filename)
    filename = filename.replace('\\', '/')
    filename = filename.lstrip('/')
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/view/<path:filename>')
def view_file(filename):
    # Handle both forward and back slashes
    filename = unquote(filename)
    filename = filename.replace('\\', '/')
    # Ensure we have the right relative path
    filename = filename.lstrip('/')
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/delete_document/<int:document_id>', methods=['POST'])
def delete_document(document_id):
    conn = get_db_connection()
    document = conn.execute('SELECT * FROM documents WHERE id = ?', (document_id,)).fetchone()
    
    if document:
        # Delete file from client folder
        try:
            file_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER'], document['filename']))
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        
        # Delete from database
        conn.execute('DELETE FROM documents WHERE id = ?', (document_id,))
        conn.commit()
        flash('Document deleted successfully!')
    
    conn.close()
    return redirect(url_for('client_details', client_id=document['client_id']))

@app.route('/delete_client/<int:client_id>', methods=['POST', 'DELETE'])
def delete_client(client_id):
    conn = get_db_connection()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    
    if client:
        # Get client folder name
        client_info = conn.execute('SELECT folder_name FROM clients WHERE id = ?', (client_id,)).fetchone()
        folder_name = client_info['folder_name'] if client_info else None
        
        # Delete all documents of this client
        documents = conn.execute('SELECT * FROM documents WHERE client_id = ?', (client_id,)).fetchall()
        for doc in documents:
            try:
                file_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER'], doc['filename']))
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        # Delete documents from database
        conn.execute('DELETE FROM documents WHERE client_id = ?', (client_id,))
        # Delete client from database
        conn.execute('DELETE FROM clients WHERE id = ?', (client_id,))
        conn.commit()
        
        # Delete client folder if exists
        if folder_name:
            try:
                import shutil
                folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
                shutil.rmtree(folder_path)
            except:
                pass
        
        flash('Client and all documents deleted successfully!')
    
    conn.close()
    return redirect(url_for('search_client'))

@app.route('/edit_client/<int:client_id>', methods=['GET', 'POST'])
def edit_client(client_id):
    conn = get_db_connection()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        client_type = request.form.get('client_type', '')
        policy_number = request.form.get('policy_number', '')
        pan_card = request.form.get('pan_card', '')
        address = request.form.get('address', '')
        
        conn.execute('UPDATE clients SET name = ?, phone = ?, email = ?, client_type = ?, policy_number = ?, pan_card = ?, address = ? WHERE id = ?',
                    (name, phone, email, client_type, policy_number, pan_card, address, client_id))
        conn.commit()
        conn.close()
        
        flash('Client updated successfully!')
        return redirect(url_for('client_details', client_id=client_id))
    
    conn.close()
    return render_template('edit_client.html', client=client)

@app.route('/storage_info')
def storage_info():
    return render_template('storage_info.html')

@app.route('/whatsapp')
def whatsapp_dashboard():
    conn = get_db_connection()
    
    # Get clients with upcoming renewals (next 30 days)
    upcoming_renewals = conn.execute('''
        SELECT * FROM clients 
        WHERE policy_expiry_date IS NOT NULL 
        AND date(policy_expiry_date) <= date('now', '+30 days')
        AND date(policy_expiry_date) >= date('now')
        ORDER BY policy_expiry_date
    ''').fetchall()
    
    # Get expired policies
    expired_policies = conn.execute('''
        SELECT * FROM clients 
        WHERE policy_expiry_date IS NOT NULL 
        AND date(policy_expiry_date) < date('now')
        ORDER BY policy_expiry_date DESC
    ''').fetchall()
    
    # Get all clients for bulk messaging
    all_clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    
    # Convert Row objects to dictionaries for JSON serialization
    all_clients = [dict(client) for client in all_clients]
    upcoming_renewals = [dict(client) for client in upcoming_renewals]
    expired_policies = [dict(client) for client in expired_policies]
    
    conn.close()
    return render_template('whatsapp_dashboard.html', 
                         upcoming_renewals=upcoming_renewals,
                         expired_policies=expired_policies,
                         all_clients=all_clients,
                         templates=WHATSAPP_TEMPLATES)

@app.route('/api/renewal_clients')
def api_renewal_clients():
    conn = get_db_connection()
    
    # Get clients with policy expiry information
    clients = conn.execute('''
        SELECT id, name, phone, email, policy_number, policy_expiry_date, 
               premium_amount, policy_type, client_type,
               CASE 
                   WHEN date(policy_expiry_date) < date('now') THEN 'expired'
                   WHEN date(policy_expiry_date) <= date('now', '+7 days') THEN '7_days'
                   WHEN date(policy_expiry_date) <= date('now', '+15 days') THEN '15_days'
                   WHEN date(policy_expiry_date) <= date('now', '+30 days') THEN '30_days'
                   ELSE 'not_soon'
               END as renewal_status
        FROM clients 
        WHERE policy_expiry_date IS NOT NULL
        ORDER BY policy_expiry_date
    ''').fetchall()
    
    conn.close()
    return jsonify([dict(client) for client in clients])

@app.route('/send_whatsapp', methods=['POST'])
def send_whatsapp():
    data = request.get_json()
    client_ids = data.get('client_ids', [])
    template_id = data.get('template_id', '')
    custom_message = data.get('custom_message', '')
    
    if not client_ids or not template_id:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    conn = get_db_connection()
    sent_count = 0
    
    for client_id in client_ids:
        client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
        
        if client and client['phone']:
            # Get template
            template = WHATSAPP_TEMPLATES.get(template_id, {})
            message = template.get('message', custom_message)
            
            # Replace placeholders
            if message:
                message = message.replace('{client_name}', client['name'] or '')
                message = message.replace('{policy_number}', client['policy_number'] or '')
                message = message.replace('{policy_type}', client['policy_type'] or 'Insurance')
                message = message.replace('{premium_amount}', client['premium_amount'] or 'Contact for details')
                message = message.replace('{due_date}', client['policy_expiry_date'] or 'Contact for details')
                message = message.replace('{expiry_date}', client['policy_expiry_date'] or 'Contact for details')
                message = message.replace('{advisor_name}', 'Insurance Advisor')
                message = message.replace('{advisor_phone}', '+919876543210')
                message = message.replace('{update_details}', 'Please contact us for details')
            
            # Create WhatsApp URL
            whatsapp_url = f"https://web.whatsapp.com/send?phone={client['phone']}&text={message}"
            
            # Save to sent messages
            conn.execute('''
                INSERT INTO whatsapp_sent (client_id, template_id, message)
                VALUES (?, ?, ?)
            ''', (client_id, template_id, message))
            
            sent_count += 1
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'sent_count': sent_count,
        'message': f'Messages prepared for {sent_count} clients. Click on each WhatsApp link to send.'
    })

@app.route('/whatsapp_sent_history')
def whatsapp_sent_history():
    conn = get_db_connection()
    
    sent_messages = conn.execute('''
        SELECT ws.*, c.name as client_name, c.phone as client_phone
        FROM whatsapp_sent ws
        JOIN clients c ON ws.client_id = c.id
        ORDER BY ws.sent_date DESC
        LIMIT 100
    ''').fetchall()
    
    # Convert Row objects to dictionaries for JSON serialization
    sent_messages = [dict(message) for message in sent_messages]
    
    conn.close()
    return render_template('whatsapp_sent_history.html', sent_messages=sent_messages)

@app.route('/client_list')
def client_list():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    conn.close()
    return render_template('client_list.html', clients=clients)

import json
import shutil

@app.route('/daily_entry', methods=['GET', 'POST'])
def daily_entry():
    if request.method == 'POST':
        try:
            # ... (existing form data retrieval) ...
            entry_date = request.form.get('entry_date_visible')
            client_name = request.form.get('client_name')
            client_id = request.form.get('client_id')
            investment_type = request.form.get('investment_type')
            # (Keep all other form gets)
            lic_subtype = request.form.get('lic_subtype')
            lic_policy_number = request.form.get('lic_policy_number')
            lic_plan_term = request.form.get('lic_plan_term')
            amount = request.form.get('amount')
            note = request.form.get('note')
            file_no = request.form.get('file_no')
            pan_card = request.form.get('pan_card')
            address = request.form.get('address')
            hi_policy = request.form.get('hi_policy')
            hi_dob = request.form.get('hi_dob')
            hi_plan_term = request.form.get('hi_plan_term')
            hi_doc = request.form.get('hi_doc')
            hi_year = request.form.get('hi_year')
            hi_sum_assured = request.form.get('hi_sum_assured')
            hi_company = request.form.get('hi_company')
            hi_product = request.form.get('hi_product')
            mf_folio = request.form.get('mf_folio')
            mf_company_id = request.form.get('mf_company')
            mf_fund_id = request.form.get('mf_fund_name')
            mf_fund_id_to = request.form.get('mf_fund_name_to')
            mf_subtype = request.form.get('mf_subtype')
            mf_stp_start_date = request.form.get('mf_stp_start_date')
            mf_stp_end_date = request.form.get('mf_stp_end_date')
            mf_sip_amount = request.form.get('mf_sip_amount')
            mf_sip_date = request.form.get('mf_sip_date')
            mf_sip_start_date = request.form.get('mf_sip_start_date')
            mf_sip_end_date = request.form.get('mf_sip_end_date')
            mf_transmission_type = request.form.get('mf_transmission_type')
            mf_claimant_name = request.form.get('mf_claimant_name')
            mf_claimant_relation = request.form.get('mf_claimant_relation')
            mf_sip_frequency = request.form.get('mf_sip_frequency')
            mf_switch_fund_from = request.form.get('mf_switch_fund_from')
            mf_switch_fund_to = request.form.get('mf_switch_fund_to')
            mf_new_address = request.form.get('mf_new_address')
            mf_old_bank_detail = request.form.get('mf_old_bank_detail')
            mf_new_bank_detail = request.form.get('mf_new_bank_detail')
            mf_fund_type = request.form.get('mf_fund_type')
            mf_fund_subtype = request.form.get('mf_fund_subtype')
            it_address = request.form.get('it_address')
            id_type = request.form.get('id_type')
            stp_fund_type = request.form.get('stp_fund_type')
            stp_fund_subtype = request.form.get('stp_fund_subtype')
            switch_fund_type = request.form.get('switch_fund_type')
            switch_fund_subtype = request.form.get('switch_fund_subtype')
            mf_swp_amount = request.form.get('mf_swp_amount')
            mf_swp_start_date = request.form.get('mf_swp_start_date')
            mf_swp_end_date = request.form.get('mf_swp_end_date')
            hi_expiry_date = request.form.get('hi_expiry_date')
            
            scanned_docs_json = request.form.get('scanned_documents')
            
            conn = get_db_connection()
            if conn is not None:
                try:
                    fields = {
                        'entry_date': entry_date,
                        'client_name': client_name,
                        'investment_type': investment_type,
                        'lic_subtype': lic_subtype,
                        'lic_policy_number': lic_policy_number,
                        'lic_plan_term': lic_plan_term,
                        'amount': amount,
                        'note': note,
                        'file_no': file_no,
                        'pan_card': pan_card,
                        'address': address,
                        'hi_policy': hi_policy,
                        'hi_dob': hi_dob,
                        'hi_plan_term': hi_plan_term,
                        'hi_doc': hi_doc,
                        'hi_year': hi_year,
                        'hi_sum_assured': hi_sum_assured,
                        'mf_folio': mf_folio,
                        'mf_company_id': mf_company_id,
                        'mf_fund_id': mf_fund_id,
                        'mf_fund_id_to': mf_fund_id_to,
                        'mf_subtype': mf_subtype,
                        'mf_stp_start_date': mf_stp_start_date,
                        'mf_stp_end_date': mf_stp_end_date,
                        'mf_sip_amount': mf_sip_amount,
                        'mf_sip_date': mf_sip_date,
                        'mf_sip_start_date': mf_sip_start_date,
                        'mf_sip_end_date': mf_sip_end_date,
                        'mf_transmission_type': mf_transmission_type,
                        'mf_claimant_name': mf_claimant_name,
                        'mf_claimant_relation': mf_claimant_relation,
                        'mf_sip_frequency': mf_sip_frequency,
                        'mf_switch_fund_from': mf_switch_fund_from,
                        'mf_switch_fund_to': mf_switch_fund_to,
                        'mf_new_address': mf_new_address,
                        'mf_old_bank_detail': mf_old_bank_detail,
                        'mf_new_bank_detail': mf_new_bank_detail,
                        'mf_fund_type': mf_fund_type,
                        'mf_fund_subtype': mf_fund_subtype,
                        'client_id': client_id,
                        'hi_company_id': hi_company,
                        'hi_product_id': hi_product,
                        'it_address': it_address,
                        'id_type': id_type,
                        'stp_fund_type': stp_fund_type,
                        'stp_fund_subtype': stp_fund_subtype,
                        'switch_fund_type': switch_fund_type,
                        'switch_fund_subtype': switch_fund_subtype,
                        'mf_swp_amount': mf_swp_amount,
                        'mf_swp_start_date': mf_swp_start_date,
                        'mf_swp_end_date': mf_swp_end_date,
                        'hi_expiry_date': hi_expiry_date,
                    }
                    
                    # Filter out None and empty values
                    valid_fields = {k: v for k, v in fields.items() if v not in (None, '', 'None')}
                    
                    columns = ', '.join(valid_fields.keys())
                    placeholders = ', '.join(['?'] * len(valid_fields))
                    values = list(valid_fields.values())
                    
                    cursor = conn.execute(f'INSERT INTO daily_entries ({columns}) VALUES ({placeholders})', values)

                    entry_id = cursor.lastrowid
                    logger.info(f"Daily entry saved with ID: {entry_id}, client: {client_name}, type: {investment_type}")

                    # Process attached scans
                    if scanned_docs_json and client_id:
                        scanned_docs = json.loads(scanned_docs_json)
                        client_folder_path = get_client_folder_path(int(client_id), client_name)
                        folder_name = os.path.basename(client_folder_path)

                        for doc in scanned_docs:
                            temp_path_full = os.path.join(app.config['UPLOAD_FOLDER'], doc['temp_path'])
                            if os.path.exists(temp_path_full):
                                original_filename = doc['original_filename']
                                final_filename = str(uuid.uuid4()) + '_' + secure_filename(original_filename)
                                dest_path_full = os.path.join(client_folder_path, final_filename)
                                
                                shutil.move(temp_path_full, dest_path_full)
                                
                                relative_filename = f"{folder_name}/{final_filename}".replace('\\','/')
                                
                                conn.execute(
                                    'INSERT INTO documents (client_id, daily_entry_id, filename, original_filename, file_type, document_name, document_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                    (int(client_id), entry_id, relative_filename, original_filename, doc['file_type'], doc['document_name'], doc['document_date'])
                                )
                    
                    conn.commit()
                    conn.close()
                    flash('Daily entry saved successfully!')
                    return redirect(url_for('daily_report'))  # Redirect to daily report
                except Exception as e:
                    conn.close()
                    logger.error(f"Error saving daily entry: {e}")
                    flash(f"Error saving daily entry: {str(e)}", "error")
            else:
                flash('Database error. Please try again.', 'error')
        except Exception as e:
            logger.error(f"Error in daily_entry: {e}")
            flash(f"Error saving daily entry: {str(e)}", "error")
        
    # GET request - load form
    try:
        conn = get_db_connection()
        if conn is None:
            return render_template('daily_entry.html', hi_companies=[], clients=[])
        hi_companies = conn.execute('SELECT * FROM hi_companies ORDER BY name').fetchall()
        clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
        conn.close()
        return render_template('daily_entry.html', hi_companies=hi_companies, clients=clients)
    except Exception as e:
        logger.error(f"Error loading daily_entry: {e}")
        return render_template('daily_entry.html', hi_companies=[], clients=[])

@app.route('/daily_report')
def daily_report():
    try:
        conn = get_db_connection()
        if conn is None:
            flash("Database error", "error")
            return render_template('daily_report.html', entries=[], companies=[], hi_companies=[], mf_funds=[], hi_products=[], clients=[])
        
        entries = conn.execute('''
            SELECT de.*, 
            COALESCE(c.client_images, '') as client_images,
            COALESCE(e.entry_images, '') as entry_images,
            cl.client_type as client_category
            FROM daily_entries de
            LEFT JOIN clients cl ON de.client_id = cl.id
            LEFT JOIN (
                SELECT client_id, GROUP_CONCAT(filename) as client_images
                FROM documents
                WHERE daily_entry_id IS NULL
                GROUP BY client_id
            ) c ON de.client_id = c.client_id
            LEFT JOIN (
                SELECT daily_entry_id, GROUP_CONCAT(filename) as entry_images
                FROM documents
                WHERE daily_entry_id IS NOT NULL
                GROUP BY daily_entry_id
            ) e ON de.id = e.daily_entry_id
            ORDER BY de.entry_date DESC, de.id DESC
        ''').fetchall()

        companies = conn.execute('SELECT * FROM mf_companies ORDER BY name').fetchall()
        hi_companies = conn.execute('SELECT * FROM hi_companies ORDER BY name').fetchall()
        mf_funds = conn.execute('SELECT * FROM mf_funds ORDER BY fund_name').fetchall()
        hi_products = conn.execute('SELECT * FROM hi_products ORDER BY product_name').fetchall()
        clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
        conn.close()
        
        entries = [dict(row) for row in entries]
        companies = [dict(row) for row in companies]
        hi_companies = [dict(row) for row in hi_companies]
        mf_funds = [dict(row) for row in mf_funds]
        hi_products = [dict(row) for row in hi_products]
        clients = [dict(row) for row in clients]
        
        def get_company_name(company_id):
            if not company_id:
                return 'N/A'
            company = next((c for c in companies if c['id'] == company_id), None)
            return company['name'] if company else 'N/A'
        
        def get_hi_company_name(company_id):
            if not company_id:
                return 'N/A'
            company = next((c for c in hi_companies if c['id'] == company_id), None)
            return company['name'] if company else 'N/A'
        
        def get_fund_name(fund_id):
            if not fund_id:
                return 'N/A'
            fund = next((f for f in mf_funds if f['id'] == fund_id), None)
            return fund['fund_name'] if fund else 'N/A'
        
        return render_template('daily_report.html', 
            entries=entries, 
            companies=companies, 
            hi_companies=hi_companies, 
            mf_funds=mf_funds, 
            hi_products=hi_products, 
            clients=clients,
            get_company_name=get_company_name,
            get_hi_company_name=get_hi_company_name,
            get_fund_name=get_fund_name)
    except Exception as e:
        logger.error(f"Error in daily_report: {e}")
        flash("Error loading daily report", "error")
        return render_template('daily_report.html', entries=[], companies=[], hi_companies=[], mf_funds=[], hi_products=[], clients=[],
            get_company_name=lambda x: 'N/A',
            get_hi_company_name=lambda x: 'N/A',
            get_fund_name=lambda x: 'N/A')

@app.route('/delete_daily_entry/<int:entry_id>', methods=['DELETE'])
def delete_daily_entry(entry_id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM daily_entries WHERE id = ?', (entry_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Entry deleted successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/quick_upload', methods=['GET', 'POST'])
def quick_upload():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        file = request.files.get('file')
        document_name = request.form.get('document_name', '')
        document_date = request.form.get('document_date', '')
        
        if not client_id or not file:
            flash('Please select client and file!')
            return redirect(url_for('quick_upload'))
        
        if file and allowed_file(file.filename):
            # Get client info
            client = conn.execute('SELECT name FROM clients WHERE id = ?', (client_id,)).fetchone()
            client_name = client['name']
            
            # Get client folder path
            client_folder_path = get_client_folder_path(int(client_id), client_name)
            
            # Generate unique filename
            filename = str(uuid.uuid4()) + '_' + secure_filename(file.filename or '')
            file_path = os.path.join(client_folder_path, filename)
            file.save(file_path)
            
            # Save only relative path in database (use forward slashes for URLs)
            folder_name = os.path.basename(client_folder_path)
            relative_filename = f"{folder_name}/{filename}"
            
            conn.execute(
                'INSERT INTO documents (client_id, filename, original_filename, file_type, document_name, document_date) VALUES (?, ?, ?, ?, ?, ?)',
                (int(client_id), relative_filename, file.filename, filename.rsplit('.', 1)[1].lower(), document_name, document_date)
            )
            conn.commit()
            
            client_name = client['name']
            conn.close()
            flash(f'Document uploaded successfully for {client_name}!')
            return redirect(url_for('quick_upload'))
        else:
            flash('Invalid file type!')
    
    conn.close()
    return render_template('quick_upload.html', clients=clients)

@app.route('/api/document_counts')
def api_document_counts():
    conn = get_db_connection()
    counts = conn.execute('''
        SELECT client_id, COUNT(*) as count 
        FROM documents 
        GROUP BY client_id
    ''').fetchall()
    conn.close()
    return jsonify([{'client_id': c['client_id'], 'count': c['count']} for c in counts])

@app.route('/api/total_clients')
def api_total_clients():
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) as count FROM clients').fetchone()
    conn.close()
    return jsonify({'count': count['count']})

@app.route('/api/mf_companies')
def api_mf_companies():
    conn = get_db_connection()
    companies = conn.execute('SELECT * FROM mf_companies ORDER BY name').fetchall()
    conn.close()
    return jsonify([{'id': c['id'], 'name': c['name']} for c in companies])

@app.route('/api/mf_funds/<int:company_id>')
def api_mf_funds(company_id):
    conn = get_db_connection()
    funds = conn.execute('SELECT * FROM mf_funds WHERE company_id = ? ORDER BY fund_name', (company_id,)).fetchall()
    conn.close()
    return jsonify([{'id': f['id'], 'fund_name': f['fund_name'], 'fund_type': f['fund_type']} for f in funds])

@app.route('/api/client_documents/<int:client_id>')
def api_client_documents(client_id):
    conn = get_db_connection()
    documents = conn.execute('SELECT * FROM documents WHERE client_id = ? ORDER BY upload_date DESC', (client_id,)).fetchall()
    conn.close()
    return jsonify([dict(doc) for doc in documents])

@app.route('/api/hi_products/<int:company_id>')
def api_hi_products(company_id):
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM hi_products WHERE company_id = ? ORDER BY product_name', (company_id,)).fetchall()
    conn.close()
    return jsonify([{'id': p['id'], 'product_name': p['product_name']} for p in products])

@app.route('/master', methods=['GET', 'POST'])
def master():
    conn = get_db_connection()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_company':
            company_name = request.form.get('company_name')
            if company_name:
                conn.execute('INSERT INTO mf_companies (name) VALUES (?)', (company_name,))
                conn.commit()
                flash('Company added successfully!')
        
        elif action == 'add_fund':
            fund_company = request.form.get('fund_company')
            fund_name = request.form.get('fund_name')
            fund_type = request.form.get('fund_type')
            if fund_company and fund_name:
                conn.execute('INSERT INTO mf_funds (company_id, fund_name, fund_type) VALUES (?, ?, ?)', (fund_company, fund_name, fund_type))
                conn.commit()
                flash('Fund added successfully!')
        
        elif action == 'delete_company':
            company_id = request.form.get('company_id')
            if company_id:
                conn.execute('DELETE FROM mf_funds WHERE company_id = ?', (company_id,))
                conn.execute('DELETE FROM mf_companies WHERE id = ?', (company_id,))
                conn.commit()
                flash('Company deleted successfully!')
        
        elif action == 'delete_fund':
            fund_id = request.form.get('fund_id')
            if fund_id:
                conn.execute('DELETE FROM mf_funds WHERE id = ?', (fund_id,))
                conn.commit()
                flash('Fund deleted successfully!')
        
        elif action == 'add_hi_company':
            hi_company_name = request.form.get('hi_company_name')
            if hi_company_name:
                conn.execute('INSERT INTO hi_companies (name) VALUES (?)', (hi_company_name,))
                conn.commit()
                flash('Health Insurance Company added successfully!')
        
        elif action == 'add_hi_product':
            hi_product_company = request.form.get('hi_product_company')
            hi_product_name = request.form.get('hi_product_name')
            if hi_product_company and hi_product_name:
                conn.execute('INSERT INTO hi_products (company_id, product_name) VALUES (?, ?)', (hi_product_company, hi_product_name))
                conn.commit()
                flash('Health Insurance Product added successfully!')
        
        elif action == 'delete_hi_company':
            hi_company_id = request.form.get('hi_company_id')
            if hi_company_id:
                conn.execute('DELETE FROM hi_products WHERE company_id = ?', (hi_company_id,))
                conn.execute('DELETE FROM hi_companies WHERE id = ?', (hi_company_id,))
                conn.commit()
                flash('Health Insurance Company deleted successfully!')
        
        elif action == 'delete_hi_product':
            hi_product_id = request.form.get('hi_product_id')
            if hi_product_id:
                conn.execute('DELETE FROM hi_products WHERE id = ?', (hi_product_id,))
                conn.commit()
                flash('Health Insurance Product deleted successfully!')
    
    companies = conn.execute('SELECT * FROM mf_companies ORDER BY name').fetchall()
    funds = conn.execute('''
        SELECT mf_funds.*, mf_companies.name as company_name 
        FROM mf_funds 
        JOIN mf_companies ON mf_funds.company_id = mf_companies.id 
        ORDER BY mf_companies.name, mf_funds.fund_name
    ''').fetchall()
    hi_companies = conn.execute('SELECT * FROM hi_companies ORDER BY name').fetchall()
    hi_products = conn.execute('''
        SELECT hi_products.*, hi_companies.name as company_name 
        FROM hi_products 
        JOIN hi_companies ON hi_products.company_id = hi_companies.id 
        ORDER BY hi_companies.name, hi_products.product_name
    ''').fetchall()
    conn.close()
    
    return render_template('master.html', companies=companies, funds=funds, hi_companies=hi_companies, hi_products=hi_products)

# WhatsApp Templates
WHATSAPP_TEMPLATES = {
    'renewal_reminder_30': {
        'name': '30 Days Renewal Reminder',
        'message': "📢 *Policy Renewal Reminder* - 30 Days Left\n\nDear {client_name},\n\nYour {policy_type} policy (Policy No: {policy_number}) is due for renewal in 30 days.\n\n📅 Due Date: {due_date}\n💰 Premium: {premium_amount}\n\n📞 Please contact us for renewal process.\n\nThank you,\n{advisor_name}\n{advisor_phone}"
    },
    'renewal_reminder_15': {
        'name': '15 Days Renewal Reminder',
        'message': "⚠️ *URGENT: Policy Renewal* - 15 Days Left\n\nDear {client_name},\n\nYour {policy_type} policy (Policy No: {policy_number}) expires in 15 days.\n\n📅 Due Date: {due_date}\n💰 Premium: {premium_amount}\n\n🚨 Please renew immediately to avoid lapse.\n\n📞 Call: {advisor_phone}\n\nRegards,\n{advisor_name}"
    },
    'renewal_reminder_7': {
        'name': '7 Days Final Reminder',
        'message': "🔥 *FINAL REMINDER* - 7 Days Left\n\nDear {client_name},\n\nYour {policy_type} policy (Policy No: {policy_number}) will expire in 7 DAYS!\n\n📅 Due Date: {due_date}\n💰 Premium: {premium_amount}\n\n🚨 RENEW NOW TO CONTINUE COVERAGE\n\n📞 Emergency: {advisor_phone}\n\n{advisor_name}"
    },
    'renewal_expired': {
        'name': 'Policy Expired Notice',
        'message': "❌ *Policy Expired* - Action Required\n\nDear {client_name},\n\nYour {policy_type} policy (Policy No: {policy_number}) has expired on {expiry_date}.\n\n⚠️ You are currently without coverage!\n\n📞 Contact us immediately for renewal:\n{advisor_phone}\n\n{advisor_name}"
    },
    'premium_due': {
        'name': 'Premium Payment Reminder',
        'message': "💰 *Premium Payment Reminder*\n\nDear {client_name},\n\nYour premium payment of ₹{premium_amount} is due for {policy_type} policy.\n\n📅 Due Date: {due_date}\n💳 Payment Methods: Online/Offline\n\n📞 For assistance: {advisor_phone}\n\nThank you,\n{advisor_name}"
    },
    'policy_update': {
        'name': 'Policy Update Notification',
        'message': "📄 *Policy Update Information*\n\nDear {client_name},\n\nThere's an update regarding your {policy_type} policy (Policy No: {policy_number}).\n\n📋 Update Details: {update_details}\n\n📞 For queries: {advisor_phone}\n\nRegards,\n{advisor_name}"
    },
    'happy_birthday': {
        'name': 'Birthday Wishes',
        'message': "🎂 *Happy Birthday {client_name}* 🎂\n\nWishing you a very happy birthday and a wonderful year ahead!\n\nMay your life be filled with happiness, success and good health.\n\nWarm regards,\n{advisor_name}\n{advisor_phone}"
    },
    'new_year_wishes': {
        'name': 'New Year Wishes',
        'message': "🎊 *Happy New Year {client_name}* 🎊\n\nWishing you and your family a very Happy New Year!\n\nMay 2025 bring you happiness, prosperity and good health.\n\nWith best wishes,\n{advisor_name}\n{advisor_phone}"
    }
}

# ==================== SCANNER API ROUTES ====================

@app.route('/api/scanner/status')
def api_scanner_status():
    """Check if scanner feature is available"""
    if platform.system() != 'Windows':
        return jsonify({
            'available': False,
            'message': 'Scanner feature is only available on Windows'
        })
    
    if not SCANNER_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Scanner module not available. Install comtypes: pip install comtypes'
        })
    
    return jsonify({
        'available': True,
        'message': 'Scanner feature is ready'
    })

@app.route('/api/scanners')
def api_scanners():
    """Get list of available scanners"""
    if platform.system() != 'Windows':
        return jsonify({'success': False, 'error': 'Scanner feature is only available on Windows', 'scanners': []})
    
    if not SCANNER_AVAILABLE:
        return jsonify({'success': False, 'error': 'Scanner module not available', 'scanners': []})
    
    result = get_scanners()
    return jsonify(result)

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Scan a document from the selected scanner"""
    if platform.system() != 'Windows':
        return jsonify({'success': False, 'error': 'Scanner feature is only available on Windows'})
    
    if not SCANNER_AVAILABLE:
        return jsonify({'success': False, 'error': 'Scanner module not available'})
    
    data = request.get_json()
    scanner_id = data.get('scanner_id')
    output_format = data.get('format', 'jpg')
    
    if not scanner_id:
        return jsonify({'success': False, 'error': 'No scanner selected'})
    
    result = scan_document(scanner_id, output_format, 'uploads/temp')
    return jsonify(result)

@app.route('/api/scan_and_save', methods=['POST'])
def api_scan_and_save():
    """Scan document and return temporary file info."""
    if platform.system() != 'Windows':
        return jsonify({'success': False, 'error': 'Scanner feature is only available on Windows'})
    
    if not SCANNER_AVAILABLE:
        return jsonify({'success': False, 'error': 'Scanner module not available'})
    
    data = request.get_json()
    scanner_id = data.get('scanner_id')
    document_name = data.get('document_name', 'Scanned Document')
    document_date = data.get('document_date', '')
    output_format = data.get('format', 'jpg')
    multiscan = data.get('multiscan', False)
    scan_mode = data.get('scan_mode', 'dialog')
    
    if not scanner_id:
        return jsonify({'success': False, 'error': 'No scanner selected'})

    temp_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    
    # Scan the document(s) to the temp folder
    result = scan_document(scanner_id, output_format, temp_folder, multiscan, scan_mode)
    
    if not result.get('success'):
        return jsonify(result)
    
    # Process all scanned files to prepare info for the frontend
    scanned_files_info = []
    for i, file_info in enumerate(result['files']):
        scanned_filename = file_info['filename'] # e.g., scan_....jpg
        
        # For multi-page scans, append a page number to the document name
        final_document_name = f"{document_name} (Page {i+1})" if multiscan and len(result['files']) > 1 else document_name
        
        # The path is relative to the temp folder
        temp_path = os.path.join('temp', scanned_filename).replace('\\', '/')

        scanned_files_info.append({
            'temp_path': temp_path,
            'original_filename': scanned_filename,
            'file_type': output_format.lower(),
            'document_name': final_document_name,
            'document_date': document_date
        })

    return jsonify({
        'success': True,
        'message': f'{len(scanned_files_info)} document(s) scanned successfully to a temporary location.',
        'scanned_files': scanned_files_info
    })

@app.route('/temp/<filename>')
def view_temp_file(filename):
    """View temporary scanned files"""
    filename = unquote(filename).replace('\\', '/')
    filename = os.path.normpath(filename)
    return send_from_directory('uploads/temp', filename)

@app.route('/delete_temp/<filename>', methods=['DELETE'])
def delete_temp_file(filename):
    """Delete temporary scanned files"""
    try:
        filename = unquote(filename).replace('\\', '/')
        filename = os.path.normpath(filename)
        file_path = os.path.join('uploads/temp', os.path.basename(filename))
        
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'success': True, 'message': 'File deleted'})
        else:
            return jsonify({'success': False, 'error': 'File not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/daily_entry_rows')
def api_daily_entry_rows():
    since_id = request.args.get('since_id', 0, type=int)
    try:
        conn = get_db_connection()
        if conn is None:
            return ""

        entries = conn.execute('''
            SELECT de.*, c.images
            FROM daily_entries de
            LEFT JOIN (
                SELECT client_id, GROUP_CONCAT(filename) as images
                FROM documents
                GROUP BY client_id
            ) c ON de.client_id = c.client_id
            WHERE de.id > ?
            ORDER BY de.id DESC
        ''', (since_id,)).fetchall()

        if not entries:
            conn.close()
            return ""

        # Data for rendering
        companies = conn.execute('SELECT * FROM mf_companies ORDER BY name').fetchall()
        hi_companies = conn.execute('SELECT * FROM hi_companies ORDER BY name').fetchall()
        mf_funds = conn.execute('SELECT * FROM mf_funds ORDER BY fund_name').fetchall()
        hi_products = conn.execute('SELECT * FROM hi_products ORDER BY product_name').fetchall()
        conn.close()

        return render_template(
            '_daily_report_rows.html', 
            entries=[dict(row) for row in entries], 
            companies=[dict(row) for row in companies], 
            hi_companies=[dict(row) for row in hi_companies], 
            mf_funds=[dict(row) for row in mf_funds], 
            hi_products=[dict(row) for row in hi_products]
        )
    except Exception as e:
        logger.error(f"Error in api_daily_entry_rows: {e}")
        return ""

@app.route('/api/daily_entry/<int:entry_id>')
def api_daily_entry(entry_id):
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify(None)
        
        entry = conn.execute('SELECT * FROM daily_entries WHERE id = ?', (entry_id,)).fetchone()
        conn.close()

        if entry:
            return jsonify(dict(entry))
        else:
            return jsonify(None), 404
    except Exception as e:
        logger.error(f"Error in api_daily_entry: {e}")
        return jsonify(None), 500

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    if not os.path.exists('uploads/temp'):
        os.makedirs('uploads/temp')
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)