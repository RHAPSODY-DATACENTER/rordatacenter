# db_converter.py
import pandas as pd
import json
from datetime import datetime
import os

class DatabaseConverter:
    def __init__(self, db_path, upload_folder):
        self.db_path = db_path
        self.upload_folder = upload_folder

    def get_db_connection(self):
        """Helper to get database connection (same as in app.py)"""
        import psycopg2
        from psycopg2.extras import RealDictCursor

        db_url = os.environ.get('DATABASE_URL')
        if db_url and ('postgres://' in db_url or 'postgresql://' in db_url):
            return psycopg2.connect(
                db_url,
                sslmode='require',
                cursor_factory=RealDictCursor
            )
        # Fallback to local SQLite (for local testing)
        import sqlite3
        return sqlite3.connect(self.db_path)

    def convert_excel_to_sql(self, filepath, ministry):
        """
        Reads Excel/CSV file and inserts records into the database.
        Supports both .xlsx and .csv files.
        """
        try:
            # Read file (supports both Excel and CSV)
            if filepath.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(filepath)
            elif filepath.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                return {'success': False, 'error': 'Unsupported file format. Use .xlsx, .xls or .csv'}

            # Clean column names
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

            # Required columns (core ones)
            required_core = ['name']
            missing_core = [col for col in required_core if col not in df.columns]
            if missing_core:
                return {'success': False, 'error': f'Missing required column(s): {", ".join(missing_core)}'}

            # Optional columns (will be '' if missing)
            optional_cols = [
                'region', 'designation', 'kc_id', 'group_name',
                'blw_zone', 'chapter', 'zone', 'church'
            ]

            records = []
            for _, row in df.iterrows():
                record = {
                    'name': str(row['name']).strip(),
                    'region': str(row.get('region', '')),
                    'designation': str(row.get('designation', '')),
                    'kc_id': str(row.get('kc_id', '')),
                    'group_name': str(row.get('group_name', '')),
                    'images_json': json.dumps([]),  # No photos initially
                    'created_at': datetime.now().isoformat()
                }

                # Ministry-specific fields
                if ministry == 'campus':
                    record['blw_zone'] = str(row.get('blw_zone', ''))
                    record['chapter'] = str(row.get('chapter', ''))
                else:  # church
                    record['zone'] = str(row.get('zone', ''))
                    record['church'] = str(row.get('church', ''))

                records.append(record)

            if not records:
                return {'success': False, 'error': 'No valid records found in file'}

            # Insert into database
            conn = self.get_db_connection()
            cur = conn.cursor()
            table = 'campus_records' if ministry == 'campus' else 'church_records'

            placeholder = '%s' if 'psycopg2' in str(type(conn)) else '?'
            columns = ', '.join(records[0].keys())
            values_placeholder = ', '.join([placeholder] * len(records[0]))

            inserted = 0
            for rec in records:
                try:
                    cur.execute(f"""
                        INSERT INTO {table} ({columns})
                        VALUES ({values_placeholder})
                        ON CONFLICT (name) DO NOTHING
                    """, tuple(rec.values()))
                    inserted += 1
                except Exception as e:
                    print(f"Insert error for record {rec['name']}: {e}")

            conn.commit()
            conn.close()

            # Optional: clean up uploaded file after processing
            try:
                os.remove(filepath)
            except:
                pass

            return {
                'success': True,
                'message': f'Successfully processed {len(records)} records. {inserted} new records added (duplicates skipped).'
            }

        except Exception as e:
            return {'success': False, 'error': f'Processing failed: {str(e)}'}