import os, sqlite3
from contextlib import closing
from dotenv import load_dotenv
load_dotenv()

USE_SQLITE = os.getenv("USE_SQLITE_FALLBACK", "1") == "1"
SQLITE_PATH = os.getenv("SQLITE_PATH", "placement_demo.db")

class SQLiteCompat:
    """Tiny placeholder converter so the same parameterized SQL works with SQLite."""
    def __init__(self, conn): self.conn = conn
    def execute(self, query, params=()):
        query = query.replace("%s", "?")
        cur = self.conn.execute(query, params)
        return CursorCompat(cur)
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()

class CursorCompat:
    def __init__(self, cur): self.cur = cur
    @property
    def lastrowid(self): return self.cur.lastrowid
    def fetchone(self):
        row = self.cur.fetchone()
        return dict(row) if row is not None else None
    def fetchall(self): return [dict(r) for r in self.cur.fetchall()]

def get_db():
    if USE_SQLITE:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return SQLiteCompat(conn)
    import mysql.connector
    return MySQLCompat(mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "placement_career"),
        autocommit=False
    ))

class MySQLCompat:
    def __init__(self, conn): self.conn = conn
    def execute(self, query, params=()):
        cur = self.conn.cursor(dictionary=True)
        cur.execute(query, params)
        return MySQLCursorCompat(cur)
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self): self.conn.close()

class MySQLCursorCompat:
    def __init__(self, cur): self.cur = cur
    @property
    def lastrowid(self): return self.cur.lastrowid
    def fetchone(self): return self.cur.fetchone()
    def fetchall(self): return self.cur.fetchall()

def init_db():
    if USE_SQLITE:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS student_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE, degree TEXT NOT NULL,
          cgpa REAL NOT NULL DEFAULT 0, backlogs INTEGER NOT NULL DEFAULT 0, projects INTEGER NOT NULL DEFAULT 0,
          internships INTEGER NOT NULL DEFAULT 0, coding INTEGER NOT NULL DEFAULT 0, communication INTEGER NOT NULL DEFAULT 0,
          sql INTEGER NOT NULL DEFAULT 0, web INTEGER NOT NULL DEFAULT 0, problem_solving INTEGER NOT NULL DEFAULT 0,
          university TEXT NOT NULL DEFAULT 'University of Mumbai', stream TEXT NOT NULL DEFAULT 'Science', preferred_role TEXT NOT NULL DEFAULT 'Data Analyst',
          tenth_percentage REAL NOT NULL DEFAULT 0, twelfth_percentage REAL NOT NULL DEFAULT 0,
          resume_filename TEXT NOT NULL DEFAULT '', resume_text TEXT NOT NULL DEFAULT '', resume_skills TEXT NOT NULL DEFAULT '[]',
          coding_languages TEXT NOT NULL DEFAULT '[]', resume_strengths TEXT NOT NULL DEFAULT '[]', ats_score INTEGER NOT NULL DEFAULT 0,
          FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS assessments (
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, aptitude_score INTEGER NOT NULL,
          section_scores TEXT NOT NULL, features_json TEXT NOT NULL, predicted_probability REAL NOT NULL,
          predicted_label TEXT NOT NULL, proctor_events TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id));
        """)
        # Lightweight migrations keep existing demo databases usable.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(student_profiles)").fetchall()}
        for name, definition in [("problem_solving", "INTEGER NOT NULL DEFAULT 0"), ("tenth_percentage", "REAL NOT NULL DEFAULT 0"), ("twelfth_percentage", "REAL NOT NULL DEFAULT 0"), ("resume_filename", "TEXT NOT NULL DEFAULT ''"), ("resume_text", "TEXT NOT NULL DEFAULT ''"), ("resume_skills", "TEXT NOT NULL DEFAULT '[]'"), ("coding_languages", "TEXT NOT NULL DEFAULT '[]'"), ("resume_strengths", "TEXT NOT NULL DEFAULT '[]'"), ("ats_score", "INTEGER NOT NULL DEFAULT 0"), ("university", "TEXT NOT NULL DEFAULT 'University of Mumbai'"), ("stream", "TEXT NOT NULL DEFAULT 'Science'")]:
            if name not in cols: conn.execute(f"ALTER TABLE student_profiles ADD COLUMN {name} {definition}")
        conn.commit(); conn.close()
    else:
        import mysql.connector
        conn = mysql.connector.connect(host=os.getenv("MYSQL_HOST", "localhost"),
          port=int(os.getenv("MYSQL_PORT", "3306")), user=os.getenv("MYSQL_USER", "root"),
          password=os.getenv("MYSQL_PASSWORD", ""), database=os.getenv("MYSQL_DATABASE", "placement_career"))
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
          id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(190) NOT NULL UNIQUE,
          password_hash VARCHAR(255) NOT NULL, created_at VARCHAR(40) NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS student_profiles (
          id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL UNIQUE, degree VARCHAR(100) NOT NULL,
          cgpa DECIMAL(4,2) NOT NULL DEFAULT 0, backlogs INT NOT NULL DEFAULT 0, projects INT NOT NULL DEFAULT 0,
          internships INT NOT NULL DEFAULT 0, coding INT NOT NULL DEFAULT 0, communication INT NOT NULL DEFAULT 0,
          sql_score INT NOT NULL DEFAULT 0, web INT NOT NULL DEFAULT 0, problem_solving INT NOT NULL DEFAULT 0,
          university VARCHAR(190) NOT NULL DEFAULT 'University of Mumbai', stream VARCHAR(100) NOT NULL DEFAULT 'Science', preferred_role VARCHAR(100) NOT NULL DEFAULT 'Data Analyst',
          tenth_percentage DECIMAL(5,2) NOT NULL DEFAULT 0, twelfth_percentage DECIMAL(5,2) NOT NULL DEFAULT 0,
          resume_filename VARCHAR(255) NOT NULL DEFAULT '', resume_text LONGTEXT, resume_skills JSON, coding_languages JSON, resume_strengths JSON, ats_score INT NOT NULL DEFAULT 0,
          FOREIGN KEY(user_id) REFERENCES users(id))""")
        for statement in [
          "ALTER TABLE student_profiles ADD COLUMN problem_solving INT NOT NULL DEFAULT 0",
          "ALTER TABLE student_profiles ADD COLUMN tenth_percentage DECIMAL(5,2) NOT NULL DEFAULT 0",
          "ALTER TABLE student_profiles ADD COLUMN twelfth_percentage DECIMAL(5,2) NOT NULL DEFAULT 0",
          "ALTER TABLE student_profiles ADD COLUMN resume_filename VARCHAR(255) NOT NULL DEFAULT ''",
          "ALTER TABLE student_profiles ADD COLUMN resume_text LONGTEXT",
          "ALTER TABLE student_profiles ADD COLUMN resume_skills JSON",
          "ALTER TABLE student_profiles ADD COLUMN coding_languages JSON",
          "ALTER TABLE student_profiles ADD COLUMN resume_strengths JSON",
          "ALTER TABLE student_profiles ADD COLUMN ats_score INT NOT NULL DEFAULT 0",
          "ALTER TABLE student_profiles ADD COLUMN university VARCHAR(190) NOT NULL DEFAULT 'University of Mumbai'",
          "ALTER TABLE student_profiles ADD COLUMN stream VARCHAR(100) NOT NULL DEFAULT 'Science'",
        ]:
          try: cur.execute(statement)
          except Exception: pass
        # MySQL uses sql_score; query compatibility aliases it to sql in the profile route.
        cur.execute("""CREATE TABLE IF NOT EXISTS assessments (
          id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, aptitude_score INT NOT NULL,
          section_scores JSON NOT NULL, features_json JSON NOT NULL, predicted_probability DECIMAL(6,5) NOT NULL,
          predicted_label VARCHAR(40) NOT NULL, proctor_events JSON NOT NULL, created_at VARCHAR(40) NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id))""")
        conn.commit(); cur.close(); conn.close()
