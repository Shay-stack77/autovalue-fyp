"""WSGI entry-point for production deployment.

Run locally:
    python -m flask --app wsgi:app run

Run with gunicorn (Linux/macOS production servers, e.g. Arden SoC):
    gunicorn --bind 0.0.0.0:8000 --workers 2 wsgi:app

Run with waitress (Windows production servers):
    waitress-serve --port=8000 wsgi:app
"""
from src.api.app import create_app

app = create_app()

if __name__ == "__main__":
    # Local dev fallback: `python wsgi.py`
    app.run(host="0.0.0.0", port=8000, debug=False)
