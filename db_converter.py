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

        fields = '''
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT,
            designation TEXT,
            name TEXT UNIQUE NOT NULL,
            kc_id TEXT,
            blw_zone TEXT,
            group_name TEXT,
            chapter TEXT,
            images_json TEXT DEFAULT '[]',  -- Stores ["path1", "path2", ...]
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        '''

        cur.execute(f"CREATE TABLE IF NOT EXISTS gpd_records ({fields})")

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
        cur.execute("PRAGMA table_info(gpd_records)")
        columns = [row[1] for row in cur.fetchall()]
        if 'images_json' not in columns:
            cur.execute("ALTER TABLE gpd_records ADD COLUMN images_json TEXT DEFAULT '[]'")
        conn.commit()
        conn.close()

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.allowed_extensions

    def map_columns(self, df):
        df = df.copy()
        df.columns = [str(c).lower().strip() for c in df.columns]
        mapping = {
            'region': ['region', 'area'],
            'designation': ['designation', 'title'],
            'name': ['name', 'full name', 'person'],
            'kc_id': ['kc id', 'kingschat number', 'kcid'],
            'blw_zone': ['zone', 'blw zone'],
            'group_name': ['group', 'group name', 'groups'],
            'chapter': ['chapter']
        }
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

    def convert_excel_to_sql(self, filepath):
        try:
            df_dict = pd.read_excel(filepath, sheet_name=None)
            conn = sqlite3.connect(self.database_path)
            cur = conn.cursor()
            total = 0

            for sheet_name, df in df_dict.items():
                df = df.dropna(how='all').fillna('')
                df_mapped = self.map_columns(df)

                inserted = 0
                for _, row in df_mapped.iterrows():
                    name = row['name']
                    if not name: continue
                    try:
                        cur.execute('''
                            INSERT INTO gpd_records 
                            (region, designation, name, kc_id, blw_zone, group_name, chapter)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row['region'], row['designation'], name,
                            row['kc_id'], row['blw_zone'], row['group_name'], row['chapter']
                        ))
                        inserted += 1
                        total += 1
                    except sqlite3.IntegrityError:
                        pass  # duplicate skipped

                print(f"Sheet '{sheet_name}' → gpd_records: {inserted} records")

            conn.commit()
            conn.close()
            return {'success': True, 'records_inserted': total, 'message': f"{total} records added"}
        except Exception as e:
            return {'success': False, 'error': str(e)}