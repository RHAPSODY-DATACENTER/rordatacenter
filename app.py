# app.py
import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

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
    print(f"[DB DEBUG] Raw DATABASE_URL: {db_url[:60] if db_url else 'MISSING'}...")

    if db_url and ('postgres://' in db_url or 'postgresql://' in db_url):
        print("[DB DEBUG] Detected Postgres URL - attempting connection...")
        try:
            conn = psycopg2.connect(
                db_url,
                sslmode='require',
                cursor_factory=RealDictCursor
            )
            conn.autocommit = True
            print("[DB DEBUG] Postgres connection SUCCESS")
            return conn
        except Exception as e:
            print(f"[DB ERROR] Postgres connection failed: {str(e)}")

    print("[DB DEBUG] Falling back to local SQLite")
    return sqlite3.connect(DATABASE_PATH)


# === AUTO INITIALIZE DB ON STARTUP ===
print("[STARTUP] Initializing database...")
try:
    conn = get_db_connection()
    print("[STARTUP] Connection obtained")
    cur = conn.cursor()

    print("[STARTUP] Creating/verifying tables...")
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

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')

    print("[STARTUP] Checking super user...")
    cur.execute("SELECT 1 FROM users WHERE username = 'super'")
    if cur.fetchone() is None:
        hashed = generate_password_hash('superuser')
        cur.execute("INSERT INTO users (username, password, role) VALUES ('super', %s, 'super')", (hashed,))
        print("[STARTUP] Super user created")
    else:
        print("[STARTUP] Super user already exists")

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
        all_photos = json.loads(row['images_json']) if row['images_json'] else []
        main_photo = all_photos[0] if all_photos else '/public/default-photo.jpg'

        results.append({
            'name': row['name'],
            'designation': row['designation'] or '',
            'photo': main_photo,
            'all_photos': all_photos,
            'kc_id': row['kc_id'] or '',
            'region': row['region'] or '',
            'zone': row['blw_zone'] if ministry == 'campus' else row['zone'] or '',
            'group': row['group_name'] or '',
            'chapter': row['chapter'] if ministry == 'campus' else row['church'] or ''
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
            html = open(os.path.join(BASE_DIR, 'login.html'), 'r', encoding='utf-8').read()
            return html.replace('</body>', error + '</body>')

    return send_from_directory(BASE_DIR, 'login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/<path:filename>')
@login_required
def admin_files(filename):
    return send_from_directory(BASE_DIR, filename)


# =============== DASHBOARD DATA ===============
@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    def get_ministry_stats(table, zone_col='blw_zone'):
        conn = get_db_connection()
        cur = conn.cursor()

        def fetch_one(query):
            cur.execute(query)
            row = cur.fetchone()
            if row is None:
                return 0
            if isinstance(row, dict):
                return list(row.values())[0]
            return row[0]

        total_records = fetch_one(f"SELECT COUNT(*) FROM {table}")

        unique_regions = fetch_one(
            f"SELECT COUNT(DISTINCT region) FROM {table} WHERE region IS NOT NULL AND region != ''"
        )

        unique_zones = fetch_one(
            f"SELECT COUNT(DISTINCT {zone_col}) FROM {table} WHERE {zone_col} IS NOT NULL AND {zone_col} != ''"
        )

        cur.execute(f"""
            SELECT region, COUNT(*) as count
            FROM {table}
            WHERE region IS NOT NULL AND region != ''
            GROUP BY region
            ORDER BY count DESC
            LIMIT 10
        """)
        regions = [{"region": r['region'] or "Unknown", "count": r['count']} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT {zone_col} as zone, COUNT(*) as count
            FROM {table}
            WHERE {zone_col} IS NOT NULL AND {zone_col} != ''
            GROUP BY {zone_col}
            ORDER BY count DESC
            LIMIT 10
        """)
        zones = [{"zone": z['zone'] or "Unknown", "count": z['count']} for z in cur.fetchall()]

        cur.execute(f"""
            SELECT designation, COUNT(*) as count
            FROM {table}
            WHERE designation IS NOT NULL AND designation != ''
            GROUP BY designation
            ORDER BY count DESC
            LIMIT 10
        """)
        designations = [{"designation": d['designation'] or "Unknown", "count": d['count']} for d in cur.fetchall()]

        conn.close()

        return {
            "total_records": total_records,
            "unique_regions": unique_regions,
            "unique_zones": unique_zones,
            "regions": regions,
            "zones": zones,
            "designations": designations
        }

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
        return jsonify({'error': 'Invalid ministry'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    saved_name = timestamp + "_" + filename
    filepath = os.path.join(UPLOAD_FOLDER, saved_name)
    file.save(filepath)

    from db_converter import DatabaseConverter
    db = DatabaseConverter(DATABASE_PATH, UPLOAD_FOLDER)
    result = db.convert_excel_to_sql(filepath, ministry)
    return jsonify(result)


# =============== UPLOAD IMAGE ===============
@app.route('/api/upload-image', methods=['POST'])
@login_required
def upload_image():
    ministry = request.form.get('ministry')
    if ministry not in ['campus', 'church']:
        return jsonify({'success': False, 'error': 'Invalid ministry'}), 400

    images_folder = CAMPUS_IMAGES_FOLDER if ministry == 'campus' else CHURCH_IMAGES_FOLDER
    table = 'campus_records' if ministry == 'campus' else 'church_records'

    if 'images' not in request.files:
        return jsonify({'success': False, 'error': 'No images'}), 400
    files = request.files.getlist('images')
    valid_files = [f for f in files if f.filename != '']
    if len(valid_files) > 4:
        return jsonify({'success': False, 'error': 'Max 4 images'}), 400

    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT images_json FROM {table} WHERE LOWER(name) = LOWER(%s)", (name,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'Name not found'}), 404

    current = json.loads(row['images_json']) if row['images_json'] else []

    saved_paths = []
    for file in valid_files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
            continue
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        safe_name = secure_filename(name.replace(' ', '_'))
        filename = f"{safe_name}_{timestamp}{ext}"
        filepath = os.path.join(images_folder, filename)
        file.save(filepath)
        prefix = 'campus' if ministry == 'campus' else 'church'
        saved_paths.append(f"/images/{prefix}/{filename}")

    all_images = current + saved_paths
    final_images = all_images[-4:]

    cur.execute(f"UPDATE {table} SET images_json = %s WHERE LOWER(name) = LOWER(%s)",
                (json.dumps(final_images), name))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'Uploaded {len(saved_paths)} image(s) to {ministry} ministry'})


# =============== ADD RECORD ===============
@app.route('/api/add-record', methods=['POST'])
@login_required
def add_record():
    try:
        data = request.get_json()
        ministry = data.get('ministry')
        if ministry not in ['campus', 'church']:
            return jsonify({'success': False, 'error': 'Invalid ministry'}), 400

        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Name required'}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        table = 'campus_records' if ministry == 'campus' else 'church_records'

        placeholder = '%s' if isinstance(conn, psycopg2.extensions.connection) else '?'
        if ministry == 'campus':
            cur.execute(f'''
                INSERT INTO {table} 
                (region, designation, name, kc_id, blw_zone, group_name, chapter)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ON CONFLICT (name) DO NOTHING
            ''', (
                data.get('region', ''),
                data.get('designation', ''),
                name,
                data.get('kc_id', ''),
                data.get('blw_zone', ''),
                data.get('group_name', ''),
                data.get('chapter', '')
            ))
        else:
            cur.execute(f'''
                INSERT INTO {table} 
                (region, designation, name, kc_id, group_name, zone, church)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ON CONFLICT (name) DO NOTHING
            ''', (
                data.get('region', ''),
                data.get('designation', ''),
                name,
                data.get('kc_id', ''),
                data.get('group_name', ''),
                data.get('zone', ''),
                data.get('church', '')
            ))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Record added'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
    return jsonify([{'id': u['id'], 'username': u['username'], 'role': u['role']} for u in users])


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

    # Check how many super users remain
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'super'")
    super_count = cur.fetchone()[0]

    # Get role of user to delete
    cur.execute(f"SELECT role FROM users WHERE id = {placeholder}", (user_id,))
    user = cur.fetchone()

    if user and user[0] == 'super' and super_count <= 1:
        conn.close()
        return jsonify({'success': False, 'error': 'Cannot delete the last super user'}), 403

    try:
        cur.execute(f"DELETE FROM users WHERE id = {placeholder}", (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'User deleted'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        conn.close()


if __name__ == '__main__':
    print("ROR PARTNERSHIP DATAHUB RUNNING (local mode)")
    app.run(debug=True, port=5000)