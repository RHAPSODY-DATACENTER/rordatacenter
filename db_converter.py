# db_converter.py
import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import json
from werkzeug.security import generate_password_hash


# === SAFE DB CONNECTION HELPER (same as app.py) ===
def get_db_connection(db_path=None):
    db_url = os.environ.get('DATABASE_URL')
    print(f"[DB CONVERTER] Raw DATABASE_URL: {db_url[:60] if db_url else 'MISSING'}...")

    if db_url and ('postgres://' in db_url or 'postgresql://' in db_url):
        print("[DB CONVERTER] Detected Postgres - connecting...")
        try:
            conn = psycopg2.connect(
                db_url,
                sslmode='require',
                cursor_factory=RealDictCursor
            )
            conn.autocommit = True
            print("[DB CONVERTER] Postgres connection SUCCESS")
            return conn
        except Exception as e:
            print(f"[DB CONVERTER ERROR] Postgres failed: {str(e)}")

    print("[DB CONVERTER] Falling back to local SQLite")
    return sqlite3.connect(db_path or 'gpd_portal.db')


class DatabaseConverter:
    def __init__(self, database_path, upload_folder):
        self.database_path = database_path
        self.upload_folder = upload_folder
        self.allowed_extensions = {"xlsx", "xls", "csv"}
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(os.path.dirname(database_path), exist_ok=True)

    def init_db(self):
        conn = get_db_connection(self.database_path)
        cur = conn.cursor()

        # Campus Ministry table
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

        # Church Ministry table
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

        # Users table (if needed here, but usually handled in app.py)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()
        print("[DB CONVERTER] Tables verified/created")

    def add_images_json_column(self):
        conn = get_db_connection(self.database_path)
        cur = conn.cursor()
        for table in ['campus_records', 'church_records']:
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'images_json'
                    ) THEN
                        ALTER TABLE {table} ADD COLUMN images_json TEXT DEFAULT '[]';
                    END IF;
                END $$;
            """)
        conn.commit()
        conn.close()
        print("[DB CONVERTER] images_json columns checked")

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def map_columns(self, df, ministry):
        df = df.copy()
        # Normalize column names: lowercase, strip spaces, replace spaces with underscores
        df.columns = [str(c).lower().strip().replace(' ', '_').replace('-', '_') for c in df.columns]

        # Flexible mapping - more variations accepted
        mapping = {
            'region': ['region', 'region_name', 'area', 'state', 'location'],
            'designation': ['designation', 'title', 'position', 'role', 'rank'],
            'name': ['name', 'full_name', 'pastor_name', 'full name', 'fullname'],
            'kc_id': ['kc_id', 'kingschat_id', 'kc id', 'kcid', 'kc', 'id']
        }

        if ministry == 'campus':
            mapping.update({
                'blw_zone': ['blw_zone', 'zone', 'blw zone', 'blwzone', 'zone_name'],
                'group_name': ['group_name', 'group', 'group name', 'grp'],
                'chapter': ['chapter', 'chapter_name', 'chaptername']
            })
        else:
            mapping.update({
                'group_name': ['group_name', 'group', 'group name', 'grp'],
                'zone': ['zone', 'zone_name', 'zonename'],
                'church': ['church', 'church_name', 'churchname']
            })

        result = pd.DataFrame()
        for target, sources in mapping.items():
            found = False
            for src in sources:
                if src in df.columns:
                    result[target] = df[src]
                    found = True
                    break
            if not found:
                result[target] = ''

        result['name'] = result['name'].str.strip()
        print(f"[DB CONVERTER] Mapped columns for {ministry}: {list(result.columns)}")
        return result

    def convert_excel_to_sql(self, filepath, ministry='campus'):
        try:
            df_dict = pd.read_excel(filepath, sheet_name=None)
            conn = get_db_connection(self.database_path)
            cur = conn.cursor()
            table = 'campus_records' if ministry == 'campus' else 'church_records'
            total = 0

            for sheet_name, df in df_dict.items():
                print(f"[DB CONVERTER] Processing sheet: {sheet_name}")
                df = df.dropna(how='all').fillna('')
                df_mapped = self.map_columns(df, ministry)

                inserted = 0
                for _, row in df_mapped.iterrows():
                    name = row['name']
                    if not name:
                        continue
                    try:
                        if ministry == 'campus':
                            cur.execute(f'''
                                INSERT INTO {table} 
                                (region, designation, name, kc_id, blw_zone, group_name, chapter)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (name) DO NOTHING
                            ''', (
                                row['region'], row['designation'], name,
                                row['kc_id'], row.get('blw_zone', ''), row.get('group_name', ''), row.get('chapter', '')
                            ))
                        else:
                            cur.execute(f'''
                                INSERT INTO {table} 
                                (region, designation, name, kc_id, group_name, zone, church)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (name) DO NOTHING
                            ''', (
                                row['region'], row['designation'], name,
                                row['kc_id'], row.get('group_name', ''), row.get('zone', ''), row.get('church', '')
                            ))
                        inserted += 1
                        total += 1
                    except Exception as e:
                        print(f"[DB CONVERTER] Insert error for {name}: {str(e)}")

            conn.commit()
            conn.close()
            print(f"[DB CONVERTER] Import complete: {total} records added to {ministry}")
            return {'success': True, 'records_inserted': total, 'message': f"{total} records added to {ministry} ministry"}
        except Exception as e:
            print(f"[DB CONVERTER] Import failed: {str(e)}")
            return {'success': False, 'error': str(e)}