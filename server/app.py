"""ZipURL API server.

Endpoints
    POST /api/links          shorten a URL (optional custom alias)
    GET  /api/links/<code>   stats for a short link
    GET  /api/health         health check
    GET  /<code>             redirect to the original URL (counts the click)

Storage is Postgres when DATABASE_URL is set (production on Vercel + Neon),
otherwise a local SQLite file — so development needs no database setup.

The built React client lives in /public and is served from "/".
"""

from __future__ import annotations

import os
import re
import secrets
import sqlite3
import string
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, g, jsonify, redirect, request, send_from_directory

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 6
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED = {"api", "assets", "static", "index.html", "favicon.ico"}
MAX_URL_LENGTH = 2048
PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"

# Plain SQL that runs unchanged on both SQLite and Postgres
SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code        TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    clicks      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    last_click  TEXT
)
"""


def is_valid_url(url: str) -> bool:
    """Only allow absolute http(s) URLs so a short link can't point at javascript: etc."""
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    """Tiny wrapper so the routes can use one API for SQLite and Postgres.

    Queries are written with SQLite-style `?` placeholders and translated for Postgres.
    Rows support `row["column"]` access on both backends.
    """

    def __init__(self, target: str):
        self.is_postgres = target.startswith(("postgres://", "postgresql://"))
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            self.conn = psycopg.connect(target, row_factory=dict_row)
        else:
            self.conn = sqlite3.connect(target)
            self.conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()):
        if self.is_postgres:
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self.execute(sql, params).fetchone()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def create_app(database: str | None = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["DATABASE"] = database or os.environ.get("DATABASE_URL") or os.environ.get("ZIPURL_DB", "zipurl.db")

    def get_db() -> Database:
        if "db" not in g:
            g.db = Database(app.config["DATABASE"])
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        db = get_db()
        db.execute(SCHEMA)
        db.commit()

    def serialize(row) -> dict:
        return {
            "code": row["code"],
            "url": row["url"],
            "shortUrl": request.host_url + row["code"],
            "clicks": row["clicks"],
            "createdAt": row["created_at"],
            "lastClick": row["last_click"],
        }

    def code_taken(code: str) -> bool:
        return get_db().fetchone("SELECT 1 FROM links WHERE code = ?", (code,)) is not None

    @app.post("/api/links")
    def create_link():
        body = request.get_json(silent=True) or {}
        url = str(body.get("url", "")).strip()
        alias = str(body.get("alias", "") or "").strip()

        if not is_valid_url(url):
            return jsonify(error="Enter a full URL starting with http:// or https://"), 400

        if alias:
            if not ALIAS_PATTERN.match(alias):
                return jsonify(error="Aliases are 3-32 characters: letters, numbers, - and _"), 400
            if alias.lower() in RESERVED or code_taken(alias):
                return jsonify(error=f"The alias '{alias}' is already taken"), 409
            code = alias
        else:
            code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
            while code_taken(code):
                code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))

        db = get_db()
        db.execute("INSERT INTO links (code, url, created_at) VALUES (?, ?, ?)", (code, url, now()))
        db.commit()
        row = db.fetchone("SELECT * FROM links WHERE code = ?", (code,))
        return jsonify(serialize(row)), 201

    @app.get("/api/links/<code>")
    def link_stats(code: str):
        row = get_db().fetchone("SELECT * FROM links WHERE code = ?", (code,))
        if row is None:
            return jsonify(error="Link not found"), 404
        return jsonify(serialize(row))

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    # On Vercel the CDN serves /public directly; these routes cover local `flask run`.
    @app.get("/")
    def index():
        if not (PUBLIC_DIR / "index.html").exists():
            return jsonify(message="ZipURL API is running. Start the client with `npm run dev` in /client.")
        return send_from_directory(PUBLIC_DIR, "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(PUBLIC_DIR / "assets", filename)

    @app.get("/<code>")
    def follow(code: str):
        db = get_db()
        row = db.fetchone("SELECT url FROM links WHERE code = ?", (code,))
        if row is None:
            abort(404)
        db.execute("UPDATE links SET clicks = clicks + 1, last_click = ? WHERE code = ?", (now(), code))
        db.commit()
        return redirect(row["url"], code=302)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
