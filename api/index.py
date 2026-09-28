"""Vercel entrypoint: exposes the Flask app as a Python function.

vercel.json rewrites /api/* and short-link paths here; everything else
(the React app) is served as static files from /public.
"""

from server.app import app  # noqa: F401
