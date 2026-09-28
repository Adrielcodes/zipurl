"""ZipURL API server.

Endpoints
    POST /api/links          shorten a URL (optional custom alias)
    GET  /api/links/<code>   stats for a short link
    GET  /api/health         health check
    GET  /<code>             redirect to the original URL (counts the click)

In production the built React client (client/dist) is served from "/".
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code        TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    clicks      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    last_click  TEXT
);
"""


def is_valid_url(url: str) -> bool:
    """Only allow absolute http(s) URLs so a short link can't point at javascript: etc."""
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_app(database: str | None = None) -> Flask:
    client_dist = Path(__file__).resolve().parent.parent / "client" / "dist"
    app = Flask(__name__, static_folder=None)
    app.config["DATABASE"] = database or os.environ.get("ZIPURL_DB", "zipurl.db")

    def get_db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        get_db().executescript(SCHEMA)

    def serialize(row: sqlite3.Row) -> dict:
        return {
            "code": row["code"],
            "url": row["url"],
            "shortUrl": request.host_url + row["code"],
            "clicks": row["clicks"],
            "createdAt": row["created_at"],
            "lastClick": row["last_click"],
        }

    def code_taken(code: str) -> bool:
        return get_db().execute("SELECT 1 FROM links WHERE code = ?", (code,)).fetchone() is not None

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
        row = db.execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        return jsonify(serialize(row)), 201

    @app.get("/api/links/<code>")
    def link_stats(code: str):
        row = get_db().execute("SELECT * FROM links WHERE code = ?", (code,)).fetchone()
        if row is None:
            return jsonify(error="Link not found"), 404
        return jsonify(serialize(row))

    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.get("/")
    def index():
        if not (client_dist / "index.html").exists():
            return jsonify(message="ZipURL API is running. Start the client with `npm run dev` in /client.")
        return send_from_directory(client_dist, "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(client_dist / "assets", filename)

    @app.get("/<code>")
    def follow(code: str):
        db = get_db()
        row = db.execute("SELECT url FROM links WHERE code = ?", (code,)).fetchone()
        if row is None:
            abort(404)
        db.execute(
            "UPDATE links SET clicks = clicks + 1, last_click = ? WHERE code = ?", (now(), code)
        )
        db.commit()
        return redirect(row["url"], code=302)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
