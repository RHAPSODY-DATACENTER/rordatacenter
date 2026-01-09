# db_converter.py
import os
import sqlite3
import pandas as pd
import json
from werkzeug.security import generate_password_hash


class DatabaseConverter:
    def __init__(self, database_path, upload_folder):
        self.database_path = database_path
        self.upload_folder = upload_folder
        self.allowed_extensions = {"xlsx", "xls", "csv"}
        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(os.path.dirname(database_path), exist_ok=True)

    def init_db(self):
        conn = sqlite3.connect(self.database_path)
        cur = conn.cursor()

        # Campus Ministry table (your original structure)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS campus_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # Church Ministry table (matches your Excel and sketch)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS church_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # Users table (shared)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        cur.execute("SELECT id FROM users WHERE username = 'super'")
        if not cur.fetchone():
            cur.execute("INSERT INTO users (username, password) VALUES ('super', ?)",
                        (generate_password_hash('superuser'),))
            print("SUPER USER: super / superuser")

        conn.commit()
        conn.close()

    def add_images_json_column(self):
        conn = sqlite3.connect(self.database_path)
        cur = conn.cursor()
        for table in ['campus_records', 'church_records']:
            cur.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cur.fetchall()]
            if 'images_json' not in columns:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN images_json TEXT DEFAULT '[]'")
        conn.commit()
        conn.close()

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def map_columns(self, df, ministry):
        df = df.copy()
        df.columns = [str(c).lower().strip() for c in df.columns]

        # Common fields
        mapping = {
            'region': ['region'],
            'designation': ['designation', 'title'],
            'name': ['name', 'full name'],
            'kc_id': ['kc id', 'kingschat', 'kcid']
        }

        # Ministry-specific fields
        if ministry == 'campus':
            mapping.update({
                'blw_zone': ['zone', 'blw zone'],
                'group_name': ['group', 'group name'],
                'chapter': ['chapter']
            })
        else:  # church
            mapping.update({
                'group_name': ['group'],
                'zone': ['zone'],
                'church': ['church']
            })

        result = pd.DataFrame()
        for target, sources in mapping.items():
            for src in sources:
                if src in df.columns:
                    result[target] = df[src]
                    break
            else:
                result[target] = ''

        result['name'] = result['name'].str.strip()
        return result

    def convert_excel_to_sql(self, filepath, ministry='campus'):
        try:
            df_dict = pd.read_excel(filepath, sheet_name=None)
            conn = sqlite3.connect(self.database_path)
            cur = conn.cursor()
            table = 'campus_records' if ministry == 'campus' else 'church_records'
            total = 0

            for sheet_name, df in df_dict.items():
                df = df.dropna(how='all').fillna('')
                df_mapped = self.map_columns(df, ministry)

                inserted = 0
                for _, row in df_mapped.iterrows():
                    name = row['name']
                    if not name: continue
                    try:
                        if ministry == 'campus':
                            cur.execute(f'''
                                INSERT INTO {table} 
                                (region, designation, name, kc_id, blw_zone, group_name, chapter)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                row['region'], row['designation'], name,
                                row['kc_id'], row.get('blw_zone', ''), row.get('group_name', ''), row.get('chapter', '')
                            ))
                        else:
                            cur.execute(f'''
                                INSERT INTO {table} 
                                (region, designation, name, kc_id, group_name, zone, church)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                row['region'], row['designation'], name,
                                row['kc_id'], row.get('group_name', ''), row.get('zone', ''), row.get('church', '')
                            ))
                        inserted += 1
                        total += 1
                    except sqlite3.IntegrityError:
                        pass  # duplicate name skipped

            conn.commit()
            conn.close()
            return {'success': True, 'records_inserted': total, 'message': f"{total} records added to {ministry} ministry"}
        except Exception as e:
            return {'success': False, 'error': str(e)}