# ⚡ ZipURL

A full-stack URL shortener. Paste a long link and get a short one, pick your own custom alias, track how many times it's clicked, and share it with a QR code.

> This started as one of my first full-stack projects in college (React + Flask + Firebase on Heroku). I rebuilt it in 2026 with a cleaner architecture, a real database layer, click analytics, and tests.

## Features

- **Shorten any link:** generates a random 6-character code, or use your own alias like `/my-portfolio`
- **Click tracking:** every redirect is counted, and you can see the total and the time of the last click
- **QR codes:** generated instantly for any short link
- **Recent links:** your last 10 links are saved in the browser, with one-click copy and live click counts
- **Validation that protects users:** only `http(s)` URLs are accepted (no `javascript:` links), aliases are checked for format and uniqueness, and reserved paths like `/api` can't be taken
- **Light and dark mode:** follows your system setting

## Tech Stack

| Layer | Tech |
|---|---|
| Frontend | React 19, Vite, `qrcode.react` |
| Backend | Python, Flask 3 |
| Database | SQLite |
| Testing | pytest (19 tests) |
| Production server | Gunicorn |

## How It Works

```
Browser ──POST /api/links──► Flask ──► SQLite (code, url, clicks, created_at)
Browser ──GET /<code>──────► Flask ──► increment clicks ──► 302 redirect to original URL
```

In development, Vite proxies `/api` calls to Flask. In production, Flask serves the built React app and the API from one server.

### API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/links` | Body `{ "url": "...", "alias": "optional" }`. Returns the new link (`201`), `400` if invalid, `409` if the alias is taken |
| `GET` | `/api/links/<code>` | Stats for a link (URL, clicks, created, last click) |
| `GET` | `/<code>` | Redirects to the original URL and counts the click |
| `GET` | `/api/health` | Health check |

## Running Locally

**1. Start the API** (Python 3.10+)

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
flask --app app run
```

**2. Start the client** (Node 20+), in a second terminal

```bash
cd client
npm install
npm run dev
```

Open http://localhost:5173.

### Tests

```bash
cd server
pytest
```

## Deploying

Build the client, then run Flask with Gunicorn. It serves both the React app and the API:

```bash
cd client && npm run build
cd ../server && gunicorn app:app
```

Set `ZIPURL_DB` to choose where the SQLite database is stored (default: `zipurl.db`).

## Project Structure

```
client/          React + Vite frontend
  src/App.jsx    Shortener form, result card, QR code, link history
  src/api.js     API helpers
server/          Flask backend
  app.py         Routes, validation, SQLite storage
  tests/         pytest suite
```
