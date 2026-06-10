import sqlite3
import os
from pathlib import Path
from datetime import datetime


DB_DIR = Path.home() / ".ebookcleaner"
DB_PATH = DB_DIR / "library.db"


class Database:
    def __init__(self):
        DB_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def initialize(self):
        c = self.conn
        c.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT DEFAULT '',
                description TEXT DEFAULT '',
                source_url TEXT DEFAULT '',
                cover_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                chapter_number INTEGER NOT NULL,
                title TEXT DEFAULT '',
                original_content TEXT DEFAULT '',
                cleaned_content TEXT DEFAULT '',
                rewritten_content TEXT DEFAULT '',
                word_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'original',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                UNIQUE(book_id, chapter_number)
            );

            CREATE TABLE IF NOT EXISTS book_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                version_number INTEGER NOT NULL,
                import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT DEFAULT '',
                chapter_count INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS book_custom_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                rule_name TEXT DEFAULT '',
                pattern TEXT NOT NULL DEFAULT '',
                replacement TEXT DEFAULT '',
                is_regex INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS site_cookies (
                domain TEXT PRIMARY KEY,
                cookies_json TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        c.commit()
        # Migrate existing databases to add new columns (idempotent)
        self._migrate()

    def _migrate(self):
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(books)").fetchall()}
        for col, defn in [("source_url", "TEXT DEFAULT ''"), ("cover_url", "TEXT DEFAULT ''")]:
            if col not in existing:
                self.conn.execute(f"ALTER TABLE books ADD COLUMN {col} {defn}")

        ch_existing = {row[1] for row in self.conn.execute("PRAGMA table_info(chapters)").fetchall()}
        if "source_url" not in ch_existing:
            self.conn.execute("ALTER TABLE chapters ADD COLUMN source_url TEXT DEFAULT ''")
        # Ensure book_custom_rules table exists (for databases created before this feature)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS book_custom_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                rule_name TEXT DEFAULT '',
                pattern TEXT NOT NULL DEFAULT '',
                replacement TEXT DEFAULT '',
                is_regex INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS site_cookies (
                domain TEXT PRIMARY KEY,
                cookies_json TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    # --- Books ---

    def get_all_books(self):
        cur = self.conn.execute(
            "SELECT id, title, author, description, source_url, cover_url, created_at, updated_at"
            " FROM books ORDER BY updated_at DESC"
        )
        return [dict(row) for row in cur.fetchall()]

    def get_book(self, book_id):
        cur = self.conn.execute(
            "SELECT id, title, author, description, source_url, cover_url, created_at, updated_at"
            " FROM books WHERE id = ?",
            (book_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def add_book(self, title, author="", description="", source_url="", cover_url=""):
        cur = self.conn.execute(
            "INSERT INTO books (title, author, description, source_url, cover_url) VALUES (?, ?, ?, ?, ?)",
            (title, author, description, source_url, cover_url)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_book(self, book_id, **kwargs):
        allowed = {"title", "author", "description", "source_url", "cover_url"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [book_id]
        self.conn.execute(f"UPDATE books SET {set_clause} WHERE id = ?", values)
        self.conn.commit()

    def delete_book(self, book_id):
        self.conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        self.conn.commit()

    # --- Chapters ---

    def get_chapters(self, book_id):
        cur = self.conn.execute(
            """SELECT id, book_id, chapter_number, title, original_content,
                      cleaned_content, rewritten_content, word_count, status, source_url
               FROM chapters WHERE book_id = ? ORDER BY chapter_number""",
            (book_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_chapter(self, chapter_id):
        cur = self.conn.execute(
            """SELECT id, book_id, chapter_number, title, original_content,
                      cleaned_content, rewritten_content, word_count, status, source_url
               FROM chapters WHERE id = ?""",
            (chapter_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def get_chapter_source_urls(self, book_id) -> set:
        """Return the set of source_urls already stored for this book's chapters."""
        cur = self.conn.execute(
            "SELECT source_url FROM chapters WHERE book_id = ? AND source_url != ''",
            (book_id,)
        )
        return {row[0] for row in cur.fetchall()}

    def add_chapter(self, book_id, number, title, content, source_url=""):
        word_count = len(content.split())
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO chapters
               (book_id, chapter_number, title, original_content, word_count, source_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (book_id, number, title, content, word_count, source_url)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_chapter(self, chapter_id, **kwargs):
        allowed = {"title", "original_content", "cleaned_content", "rewritten_content", "word_count", "status"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [chapter_id]
        self.conn.execute(f"UPDATE chapters SET {set_clause} WHERE id = ?", values)
        self.conn.commit()

    def delete_chapters(self, chapter_ids: list) -> None:
        if not chapter_ids:
            return
        placeholders = ",".join("?" * len(chapter_ids))
        self.conn.execute(f"DELETE FROM chapters WHERE id IN ({placeholders})", chapter_ids)
        self.conn.commit()

    def replace_chapter_content(self, chapter_id: int, content: str) -> None:
        """Replace original content and clear derived versions (cleaned, rewritten)."""
        self.conn.execute(
            """UPDATE chapters
               SET original_content = ?, cleaned_content = '', rewritten_content = '',
                   word_count = ?, status = 'original', updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (content, len(content.split()), chapter_id),
        )
        self.conn.commit()

    def get_max_chapter_number(self, book_id):
        cur = self.conn.execute(
            "SELECT MAX(chapter_number) FROM chapters WHERE book_id = ?", (book_id,)
        )
        row = cur.fetchone()
        return row[0] or 0

    # --- Versions ---

    def add_version(self, book_id, version_number, file_path, chapter_count, notes=""):
        cur = self.conn.execute(
            """INSERT INTO book_versions (book_id, version_number, file_path, chapter_count, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (book_id, version_number, file_path, chapter_count, notes)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_versions(self, book_id):
        cur = self.conn.execute(
            """SELECT id, book_id, version_number, import_date, file_path, chapter_count, notes
               FROM book_versions WHERE book_id = ? ORDER BY version_number""",
            (book_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def get_next_version_number(self, book_id):
        cur = self.conn.execute(
            "SELECT MAX(version_number) FROM book_versions WHERE book_id = ?", (book_id,)
        )
        row = cur.fetchone()
        return (row[0] or 0) + 1

    # --- Custom Rules ---

    def get_custom_rules(self, book_id: int) -> list:
        cur = self.conn.execute(
            "SELECT * FROM book_custom_rules WHERE book_id = ? ORDER BY sort_order, id",
            (book_id,)
        )
        return [dict(row) for row in cur.fetchall()]

    def add_custom_rule(self, book_id: int, rule_name: str, pattern: str,
                        replacement: str = "", is_regex: bool = False) -> int:
        cur = self.conn.execute(
            """INSERT INTO book_custom_rules (book_id, rule_name, pattern, replacement, is_regex)
               VALUES (?, ?, ?, ?, ?)""",
            (book_id, rule_name, pattern, replacement, int(is_regex))
        )
        self.conn.commit()
        return cur.lastrowid

    def update_custom_rule(self, rule_id: int, **kwargs) -> None:
        allowed = {"rule_name", "pattern", "replacement", "is_regex", "enabled", "sort_order"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        self.conn.execute(
            f"UPDATE book_custom_rules SET {set_clause} WHERE id = ?",
            list(fields.values()) + [rule_id]
        )
        self.conn.commit()

    def delete_custom_rule(self, rule_id: int) -> None:
        self.conn.execute("DELETE FROM book_custom_rules WHERE id = ?", (rule_id,))
        self.conn.commit()

    # --- Site Cookies ---

    def get_all_site_cookies(self) -> list:
        cur = self.conn.execute(
            "SELECT domain, cookies_json, updated_at FROM site_cookies ORDER BY domain"
        )
        return [dict(row) for row in cur.fetchall()]

    def get_site_cookies(self, domain: str) -> list:
        cur = self.conn.execute(
            "SELECT cookies_json FROM site_cookies WHERE domain = ?", (domain,)
        )
        row = cur.fetchone()
        if not row:
            return []
        import json
        return json.loads(row[0]) or []

    def set_site_cookies(self, domain: str, cookies: list) -> None:
        import json
        self.conn.execute(
            "INSERT OR REPLACE INTO site_cookies (domain, cookies_json, updated_at)"
            " VALUES (?, ?, CURRENT_TIMESTAMP)",
            (domain, json.dumps(cookies))
        )
        self.conn.commit()

    def delete_site_cookies(self, domain: str) -> None:
        self.conn.execute("DELETE FROM site_cookies WHERE domain = ?", (domain,))
        self.conn.commit()

    def get_all_cookies_flat(self) -> list:
        """Return all stored site cookies as a flat list for requests.Session."""
        import json
        all_cookies = []
        for row in self.get_all_site_cookies():
            try:
                all_cookies.extend(json.loads(row["cookies_json"]) or [])
            except Exception:
                pass
        return all_cookies

    # --- Settings ---

    def get_setting(self, key, default=None):
        cur = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def reopen(self):
        """Close and reopen the connection (used after an in-place DB restore)."""
        self.conn.close()
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.initialize()
