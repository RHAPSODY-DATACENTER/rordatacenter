# app.py
import os
import sqlite3
import json
from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps
from db_converter import DatabaseConverter

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
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(CAMPUS_IMAGES_FOLDER, exist_ok=True)
os.makedirs(CHURCH_IMAGES_FOLDER, exist_ok=True)

db = DatabaseConverter(DATABASE_PATH, UPLOAD_FOLDER)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login', next=request.url))
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


# =============== SEARCH API - BOTH MINISTRIES (FULL FIELDS) ===============
@app.route('/api/search')
def search():
    query = request.args.get('q', '').strip().lower()
    ministry = request.args.get('ministry', 'campus')

    if not query:
        return jsonify([])

    table = 'campus_records' if ministry == 'campus' else 'church_records'

    results = []
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()

    if ministry == 'campus':
        cur.execute(f"""
            SELECT name, designation, images_json, kc_id, region, blw_zone, group_name, chapter
            FROM {table}
            WHERE LOWER(name) LIKE ? OR LOWER(kc_id) LIKE ?
            ORDER BY name
        """, (f'%{query}%', f'%{query}%'))
    else:
        cur.execute(f"""
            SELECT name, designation, images_json, kc_id, region, zone, group_name, church
            FROM {table}
            WHERE LOWER(name) LIKE ? OR LOWER(kc_id) LIKE ?
            ORDER BY name
        """, (f'%{query}%', f'%{query}%'))

    for row in cur.fetchall():
        all_photos = json.loads(row[2]) if row[2] else []
        main_photo = all_photos[0] if all_photos else '/public/default-photo.jpg'

        result = {
            'name': row[0],
            'designation': row[1] or '',
            'photo': main_photo,
            'all_photos': all_photos,
            'kc_id': row[3] or '',
            'region': row[4] or '',
            'zone': row[5] or '',  # blw_zone or zone
            'group': row[6] or '',
            'chapter': row[7] or ''  # chapter or church
        }

        results.append(result)

    conn.close()
    return jsonify(results)


# =============== ADMIN ROUTES ===============
@app.route('/admin')
@login_required
def admin_dashboard():
    return send_from_directory(BASE_DIR, 'dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE username = ?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['logged_in'] = True
            return redirect(request.args.get('next') or '/admin')
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


# =============== DASHBOARD DATA - BOTH MINISTRIES ===============
@app.route('/api/dashboard-data')
@login_required
def dashboard_data():
    def get_ministry_stats(table, zone_col='blw_zone', group_col='group_name', chapter_col='chapter'):
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total_records = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(DISTINCT region) FROM {table} WHERE region IS NOT NULL AND region != ''")
        unique_regions = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(DISTINCT {zone_col}) FROM {table} WHERE {zone_col} IS NOT NULL AND {zone_col} != ''")
        unique_zones = cur.fetchone()[0]

        cur.execute(f"""
            SELECT region, COUNT(*) as count
            FROM {table}
            WHERE region IS NOT NULL AND region != ''
            GROUP BY region
            ORDER BY count DESC
            LIMIT 10
        """)
        regions = [{"region": r[0] or "Unknown", "count": r[1]} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT {zone_col}, COUNT(*) as count
            FROM {table}
            WHERE {zone_col} IS NOT NULL AND {zone_col} != ''
            GROUP BY {zone_col}
            ORDER BY count DESC
            LIMIT 10
        """)
        zones = [{"zone": z[0] or "Unknown", "count": z[1]} for z in cur.fetchall()]

        cur.execute(f"""
            SELECT designation, COUNT(*) as count
            FROM {table}
            WHERE designation IS NOT NULL AND designation != ''
            GROUP BY designation
            ORDER BY count DESC
            LIMIT 10
        """)
        designations = [{"designation": d[0] or "Unknown", "count": d[1]} for d in cur.fetchall()]

        conn.close()

        return {
            "total_records": total_records,
            "unique_regions": unique_regions,
            "unique_zones": unique_zones,
            "regions": regions,
            "zones": zones,
            "designations": designations
        }

    campus_stats = get_ministry_stats('campus_records', 'blw_zone', 'group_name', 'chapter')
    church_stats = get_ministry_stats('church_records', 'zone', 'group_name', 'church')

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
    if not db.allowed_file(file.filename):
        return jsonify({'error': 'Only Excel/CSV'}), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
    saved_name = timestamp + "_" + filename
    filepath = os.path.join(UPLOAD_FOLDER, saved_name)
    file.save(filepath)

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

    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute(f"SELECT images_json FROM {table} WHERE TRIM(LOWER(name)) = TRIM(LOWER(?))", (name,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'Name not found'}), 404

    current = json.loads(row[0]) if row[0] else []

    saved_paths = []
    for file in valid_files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
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

    cur.execute(f"UPDATE {table} SET images_json = ? WHERE TRIM(LOWER(name)) = LOWER(?)",
                (json.dumps(final_images), name))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'message': f'Uploaded {len(saved_paths)} image(s)'})


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

        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.cursor()
        table = 'campus_records' if ministry == 'campus' else 'church_records'

        if ministry == 'campus':
            cur.execute(f'''
                INSERT INTO {table} 
                (region, designation, name, kc_id, blw_zone, group_name, chapter)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Name already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    db.init_db()
    db.add_images_json_column()
    print("GPD PORTAL RUNNING - Dual Ministry Support")
    app.run(debug=True, port=5000)