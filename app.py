# app.py - Full updated version
import os
import json
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3

app = Flask(__name__)
CORS(app)
app.secret_key = 'gpd_super_secure_key_2025_change_this_later'

# === PATHS ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DATABASE_FOLDER = os.path.join(BASE_DIR, 'database')
IMAGES_FOLDER = os.path.join(BASE_DIR, 'images')
CAMPUS_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, 'campus')
CHURCH_IMAGES_FOLDER = os.path.join(IMAGES_FOLDER, 'church')
DATABASE_PATH = os.path.join(DATABASE_FOLDER, 'gpd_portal.db')
PUBLIC_FOLDER = os.path.join(BASE_DIR, 'public')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATABASE_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(CAMPUS_IMAGES_FOLDER, exist_ok=True)
os.makedirs(CHURCH_IMAGES_FOLDER, exist_ok=True)

# === SAFE DB CONNECTION HELPER ===
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url and ('postgres://' in db_url or 'postgresql://' in db_url):
        try:
            conn = psycopg2.connect(
                db_url,
                sslmode='require',
                cursor_factory=RealDictCursor
            )
            conn.autocommit = True
            return conn
        except Exception as e:
            print(f"[DB ERROR] Postgres connection failed: {str(e)}")

    # Fallback to SQLite for local testing
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Allow accessing columns by name in SQLite
    return conn

# === AUTO INITIALIZE DB ON STARTUP ===
print("[STARTUP] Initializing database...")
try:
    conn = get_db_connection()
    cur = conn.cursor()

    # Campus Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS campus_records (
            id SERIAL PRIMARY KEY,
            region TEXT,
            designation TEXT,
            name TEXT UNIQUE NOT NULL,
            kc_id TEXT,
            blw_zone TEXT,
            group_name TEXT,
            chapter TEXT,
            images_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Church Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS church_records (
            id SERIAL PRIMARY KEY,
            region TEXT,
            designation TEXT,
            name TEXT UNIQUE NOT NULL,
            kc_id TEXT,
            group_name TEXT,
            zone TEXT,
            church TEXT,
            images_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Users Table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')

    # Create Super User if not exists
    print("[STARTUP] Checking super user...")
    # Handle different param styles for SQLite vs Postgres
    placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'
    
    cur.execute(f"SELECT 1 FROM users WHERE username = 'super'")
    if cur.fetchone() is None:
        hashed = generate_password_hash('superuser')
        cur.execute(f"INSERT INTO users (username, password, role) VALUES ('super', {placeholder}, 'super')", (hashed,))
        print("[STARTUP] Super user created")
    
    if hasattr(conn, 'commit'):
        conn.commit()
    print("[STARTUP] Database initialization SUCCESS")
except Exception as e:
    print(f"[STARTUP] Database initialization FAILED: {str(e)}")
finally:
    if 'conn' in locals() and conn:
        conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def super_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'super':
            return redirect(url_for('admin_user'))
        return f(*args, **kwargs)
    return decorated

# =============== PUBLIC ROUTES ===============
@app.route('/')
def index():
    return send_from_directory(PUBLIC_FOLDER, 'index.html')

@app.route('/public/<path:filename>')
def public_files(filename):
    return send_from_directory(PUBLIC_FOLDER, filename)

@app.route('/images/campus/<filename>')
def campus_image(filename):
    return send_from_directory(CAMPUS_IMAGES_FOLDER, filename)

@app.route('/images/church/<filename>')
def church_image(filename):
    return send_from_directory(CHURCH_IMAGES_FOLDER, filename)

# =============== SEARCH API ===============
@app.route('/api/search')
def search():
    query = request.args.get('q', '').strip().lower()
    ministry = request.args.get('ministry', 'campus')

    if not query:
        return jsonify([])

    table = 'campus_records' if ministry == 'campus' else 'church_records'

    results = []
    conn = get_db_connection()
    cur = conn.cursor()

    placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'
    like_pattern = f'%{query}%'

    # Select fields including images_json
    if ministry == 'campus':
        cur.execute(f"""
            SELECT name, designation, images_json, kc_id, region, blw_zone, group_name, chapter
            FROM {table}
            WHERE LOWER(name) LIKE {placeholder} OR LOWER(kc_id) LIKE {placeholder}
            ORDER BY name
        """, (like_pattern, like_pattern))
    else:
        cur.execute(f"""
            SELECT name, designation, images_json, kc_id, region, zone, group_name, church
            FROM {table}
            WHERE LOWER(name) LIKE {placeholder} OR LOWER(kc_id) LIKE {placeholder}
            ORDER BY name
        """, (like_pattern, like_pattern))

    rows = cur.fetchall()
    for row in rows:
        # SAFELY PARSE JSON
        try:
            images_raw = row['images_json']
            if images_raw:
                all_photos = json.loads(images_raw)
            else:
                all_photos = []
        except:
            all_photos = []

        main_photo = all_photos[0] if all_photos else '/public/default-photo.jpg'
        
        # Handle dictionary access for Postgres vs SQLite Row objects
        def get_col(r, key):
            return r[key] if key in r.keys() else ''

        results.append({
            'name': row['name'],
            'designation': get_col(row, 'designation'),
            'photo': main_photo,
            'all_photos': all_photos,
            'kc_id': get_col(row, 'kc_id'),
            'region': get_col(row, 'region'),
            'zone': get_col(row, 'blw_zone') if ministry == 'campus' else get_col(row, 'zone'),
            'group': get_col(row, 'group_name'),
            'chapter': get_col(row, 'chapter') if ministry == 'campus' else get_col(row, 'church')
        })

    conn.close()
    return jsonify(results)

# =============== ADMIN ROUTES ===============
@app.route('/admin')
@login_required
@super_required
def admin_dashboard():
    return send_from_directory(BASE_DIR, 'dashboard.html')

@app.route('/admin-user')
@login_required
def admin_user():
    if session.get('role') == 'super':
        return redirect(url_for('admin_dashboard'))
    return send_from_directory(BASE_DIR, 'admin_user.html')

@app.route('/assign_user.html')
@login_required
@super_required
def assign_user_page():
    return send_from_directory(BASE_DIR, 'assign_user.html')

@app.route('/users.html')
@login_required
@super_required
def users_page():
    return send_from_directory(BASE_DIR, 'users.html')

@app.route('/upload_dataset.html')
@login_required
def upload_dataset_page():
    return send_from_directory(BASE_DIR, 'upload_dataset.html')

@app.route('/upload_individual.html')
@login_required
def upload_individual_page():
    return send_from_directory(BASE_DIR, 'upload_individual.html')

@app.route('/upload_image.html')
@login_required
def upload_image_page():
    return send_from_directory(BASE_DIR, 'upload_image.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor()
        placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'
        
        cur.execute(f"SELECT id, password, role FROM users WHERE username = {placeholder}", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['role'] = user['role']
            if user['role'] == 'super':
                return redirect(request.args.get('next') or '/admin')
            else:
                return redirect(request.args.get('next') or '/admin-user')
        else:
            error = '<div style="color:red;text-align:center;margin:20px;font-weight:bold;">Invalid username or password</div>'
            try:
                html = open(os.path.join(BASE_DIR, 'login.html'), 'r', encoding='utf-8').read()
                return html.replace('</body>', error + '</body>')
            except:
                return "Login Failed. (login.html missing)"

    return send_from_directory(BASE_DIR, 'login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# =============== DASHBOARD DATA (UPDATED FOR VISUALIZATION) ===============
@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    def get_ministry_stats(table, zone_col='blw_zone'):
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. Basic Counts
        def fetch_val(query):
            cur.execute(query)
            row = cur.fetchone()
            if row is None: return 0
            if isinstance(row, tuple): return row[0]
            return row['count'] if 'count' in row.keys() else 0

        total_records = fetch_val(f"SELECT COUNT(*) as count FROM {table}")
        
        unique_regions = fetch_val(
            f"SELECT COUNT(DISTINCT region) as count FROM {table} WHERE region IS NOT NULL AND region != ''"
        )

        unique_zones = fetch_val(
            f"SELECT COUNT(DISTINCT {zone_col}) as count FROM {table} WHERE {zone_col} IS NOT NULL AND {zone_col} != ''"
        )

        # 2. Detailed Lists for Charts
        def get_list(query, label_key):
            cur.execute(query)
            rows = cur.fetchall()
            result = []
            for r in rows:
                # Handle Tuple (SQLite) vs RealDictRow (Postgres)
                # Query structure is always SELECT name, count
                val = r[0] if isinstance(r, tuple) else (r[label_key] if label_key in r.keys() else list(r.values())[0])
                count = r[1] if isinstance(r, tuple) else (r['count'] if 'count' in r.keys() else list(r.values())[1])
                
                clean_val = val if val and str(val).strip() != '' else "Unknown"
                result.append({label_key: clean_val, "count": count})
            return result

        # Regions List
        regions_list = get_list(
            f"SELECT region, COUNT(*) as count FROM {table} GROUP BY region ORDER BY count DESC", 
            "region"
        )

        # Zones List
        zones_list = get_list(
            f"SELECT {zone_col} as zone, COUNT(*) as count FROM {table} GROUP BY {zone_col} ORDER BY count DESC",
            "zone"
        )

        # Designations List
        designations_list = get_list(
            f"SELECT designation, COUNT(*) as count FROM {table} GROUP BY designation ORDER BY count DESC",
            "designation"
        )

        conn.close()

        return {
            "total_records": total_records,
            "unique_regions": unique_regions,
            "unique_zones": unique_zones,
            "regions": regions_list,
            "zones": zones_list,
            "designations": designations_list
        }

    # Fetch for both ministries
    campus_stats = get_ministry_stats('campus_records', 'blw_zone')
    church_stats = get_ministry_stats('church_records', 'zone')

    return jsonify({
        "campus": campus_stats,
        "church": church_stats
    })

# =============== UPLOAD DATASET ===============
@app.route('/api/upload-dataset', methods=['POST'])
@login_required
def upload_dataset():
    ministry = request.form.get('ministry')
    if ministry not in ['campus', 'church']:
        return jsonify({'success': False, 'error': 'Invalid ministry'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    saved_name = timestamp + filename
    filepath = os.path.join(UPLOAD_FOLDER, saved_name)
    file.save(filepath)

    try:
        from db_converter import DatabaseConverter
        db = DatabaseConverter(DATABASE_PATH, UPLOAD_FOLDER)
        # Assuming db_converter handles the dual DB logic internally or falls back to SQLite
        result = db.convert_excel_to_sql(filepath, ministry)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    try:
        os.remove(filepath)
    except:
        pass

    return jsonify(result)

# =============== UPLOAD IMAGE (FIXED & UPDATED) ===============
@app.route('/api/upload-image', methods=['POST'])
@login_required
def upload_image():
    ministry = request.form.get('ministry')
    if ministry not in ['campus', 'church']:
        return jsonify({'success': False, 'error': 'Invalid ministry'}), 400

    images_folder = CAMPUS_IMAGES_FOLDER if ministry == 'campus' else CHURCH_IMAGES_FOLDER
    table = 'campus_records' if ministry == 'campus' else 'church_records'

    if 'images' not in request.files:
        return jsonify({'success': False, 'error': 'No images uploaded'}), 400

    files = request.files.getlist('images')
    valid_files = [f for f in files if f.filename != '']
    
    if len(valid_files) == 0:
        return jsonify({'success': False, 'error': 'No valid images'}), 400
    if len(valid_files) > 4:
        return jsonify({'success': False, 'error': 'Maximum 4 images allowed'}), 400

    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Record name is required'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'

    # 1. CHECK IF RECORD EXISTS
    cur.execute(f"SELECT images_json FROM {table} WHERE LOWER(name) = LOWER({placeholder})", (name,))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': f'Record "{name}" not found in {ministry} ministry'}), 404

    # 2. GET CURRENT IMAGES SAFELY
    current_images = []
    if row and 'images_json' in row.keys() and row['images_json']:
        try:
            current_images = json.loads(row['images_json'])
        except:
            current_images = [] # If JSON is corrupt, start fresh
    
    # 3. SAVE NEW FILES
    saved_paths = []
    for file in valid_files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
            continue

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        safe_name = secure_filename(name.replace(' ', '_'))
        filename = f"{safe_name}_{timestamp}{ext}"
        filepath = os.path.join(images_folder, filename)
        file.save(filepath)

        prefix = 'campus' if ministry == 'campus' else 'church'
        public_url = f"/images/{prefix}/{filename}"
        saved_paths.append(public_url)

    if not saved_paths:
        conn.close()
        return jsonify({'success': False, 'error': 'No valid images saved (check file types)'}), 400

    # 4. COMBINE & LIMIT TO 4
    all_images = current_images + saved_paths
    final_images = all_images[-4:] # Keep only the last 4

    # 5. DUMP TO JSON & UPDATE DATABASE
    final_json = json.dumps(final_images)

    try:
        cur.execute(f"UPDATE {table} SET images_json = {placeholder} WHERE LOWER(name) = LOWER({placeholder})",
                    (final_json, name))
        
        if hasattr(conn, 'commit'):
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': f'Successfully uploaded. Total photos: {len(final_images)}',
            'photos': final_images
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f"Database Update Error: {str(e)}"}), 500
    finally:
        conn.close()

# =============== USER MANAGEMENT ENDPOINTS ===============
@app.route('/api/list-users', methods=['GET'])
@login_required
@super_required
def list_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role FROM users ORDER BY username")
    users = cur.fetchall()
    conn.close()
    
    # Handle dict/tuple difference
    result = []
    for u in users:
        uid = u['id'] if 'id' in u.keys() else u[0]
        uname = u['username'] if 'username' in u.keys() else u[1]
        urole = u['role'] if 'role' in u.keys() else u[2]
        result.append({'id': uid, 'username': uname, 'role': urole})
        
    return jsonify(result)

@app.route('/api/create-user', methods=['POST'])
@login_required
@super_required
def create_user():
    data = request.form
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400

    hashed = generate_password_hash(password)

    conn = get_db_connection()
    cur = conn.cursor()
    placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'
    
    try:
        cur.execute(f"INSERT INTO users (username, password, role) VALUES ({placeholder}, {placeholder}, {placeholder})",
                    (username, hashed, role))
        if hasattr(conn, 'commit'):
            conn.commit()
        return jsonify({'success': True, 'message': f'User "{username}" created as {role}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/delete-user', methods=['POST'])
@login_required
@super_required
def delete_user():
    data = request.json
    user_id = data.get('id')

    if not user_id:
        return jsonify({'success': False, 'error': 'ID required'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'

    # Check super user count
    cur.execute("SELECT COUNT(*) as count FROM users WHERE role = 'super'")
    row = cur.fetchone()
    super_count = row['count'] if 'count' in row.keys() else row[0]

    # Check target user role
    cur.execute(f"SELECT role FROM users WHERE id = {placeholder}", (user_id,))
    user_row = cur.fetchone()
    
    if not user_row:
        conn.close()
        return jsonify({'success': False, 'error': 'User not found'}), 404
        
    target_role = user_row['role'] if 'role' in user_row.keys() else user_row[0]

    if target_role == 'super' and super_count <= 1:
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot delete the last super user'}), 403

    try:
        cur.execute(f"DELETE FROM users WHERE id = {placeholder}", (user_id,))
        if hasattr(conn, 'commit'):
            conn.commit()
        return jsonify({'success': True, 'message': 'User deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()

if __name__ == '__main__':
    print("ROR PARTNERSHIP DATAHUB RUNNING")
    app.run(debug=True, port=5000)