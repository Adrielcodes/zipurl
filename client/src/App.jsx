import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { getLink, shortenUrl } from "./api.js";

const HISTORY_KEY = "zipurl:history";
const MAX_HISTORY = 10;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY)) ?? [];
  } catch {
    return [];
  }
}

function saveHistory(links) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(links));
  } catch {
    // Storage can be unavailable (private mode) — history just won't persist.
  }
}

// Let people paste "github.com/me" without typing the protocol.
function normalizeUrl(value) {
  const trimmed = value.trim();
  if (!trimmed || /^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button type="button" className="btn btn-ghost" onClick={copy}>
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

function Result({ link }) {
  const [showQr, setShowQr] = useState(false);

  return (
    <section className="card result" aria-live="polite">
      <p className="label">Your short link</p>
      <div className="result-row">
        <a href={link.shortUrl} target="_blank" rel="noreferrer" className="short-url">
          {link.shortUrl.replace(/^https?:\/\//, "")}
        </a>
        <CopyButton text={link.shortUrl} />
        <button type="button" className="btn btn-ghost" onClick={() => setShowQr((v) => !v)}>
          {showQr ? "Hide QR" : "QR code"}
        </button>
      </div>
      <p className="muted truncate">→ {link.url}</p>
      {showQr && (
        <div className="qr">
          <QRCodeSVG value={link.shortUrl} size={168} marginSize={2} />
        </div>
      )}
    </section>
  );
}

function History({ links, onRefresh, onClear }) {
  if (links.length === 0) return null;

  return (
    <section className="card">
      <div className="history-header">
        <h2>Recent links</h2>
        <div>
          <button type="button" className="btn btn-ghost" onClick={onRefresh}>
            Refresh clicks
          </button>
          <button type="button" className="btn btn-ghost" onClick={onClear}>
            Clear
          </button>
        </div>
      </div>
      <ul className="history">
        {links.map((link) => (
          <li key={link.code}>
            <div className="history-main">
              <a href={link.shortUrl} target="_blank" rel="noreferrer">
                /{link.code}
              </a>
              <span className="muted truncate">{link.url}</span>
            </div>
            <span className="clicks" title="Total clicks">
              {link.clicks} {link.clicks === 1 ? "click" : "clicks"}
            </span>
            <CopyButton text={link.shortUrl} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function App() {
  const [url, setUrl] = useState("");
  const [alias, setAlias] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [latest, setLatest] = useState(null);
  const [history, setHistory] = useState(loadHistory);

  useEffect(() => saveHistory(history), [history]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const link = await shortenUrl(normalizeUrl(url), alias.trim());
      setLatest(link);
      setHistory((prev) => [link, ...prev.filter((l) => l.code !== link.code)].slice(0, MAX_HISTORY));
      setUrl("");
      setAlias("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function refreshClicks() {
    const updated = await Promise.all(history.map((link) => getLink(link.code).catch(() => link)));
    setHistory(updated);
  }

  return (
    <main className="container">
      <header className="hero">
        <h1>
          <span aria-hidden="true">⚡</span> ZipURL
        </h1>
        <p className="muted">Shorten long links, track clicks, and share with a QR code.</p>
      </header>

      <form className="card" onSubmit={handleSubmit} noValidate>
        <label htmlFor="url">Long URL</label>
        <input
          id="url"
          type="text"
          inputMode="url"
          placeholder="https://example.com/a/really/long/link"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          autoComplete="off"
          required
        />

        <label htmlFor="alias">
          Custom alias <span className="muted">(optional)</span>
        </label>
        <div className="alias-input">
          <span className="prefix">{window.location.host}/</span>
          <input
            id="alias"
            type="text"
            placeholder="my-link"
            value={alias}
            onChange={(e) => setAlias(e.target.value)}
            autoComplete="off"
            maxLength={32}
          />
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn-primary" disabled={loading || !url.trim()}>
          {loading ? "Shortening…" : "Shorten"}
        </button>
      </form>

      {latest && <Result link={latest} />}

      <History links={history} onRefresh={refreshClicks} onClear={() => setHistory([])} />

      <footer className="muted">
        Built with React + Flask · <a href="https://github.com/Adrielcodes/zipurl">Source</a>
      </footer>
    </main>
  );
}
