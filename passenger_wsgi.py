"""Entry point for GoDaddy cPanel (and other shared hosting) via "Setup Python App" / Passenger.

Shared hosting can't run Docker or an AI model, so Santo uses its built-in engine here:
it answers from your documents, looks up general facts (Wikipedia/DuckDuckGo), does math,
and captures bookings and leads. No API key needed.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
os.environ.setdefault("LLM_PROVIDER", "local")
os.environ.setdefault("DATA_DIR", os.path.join(BASE, "data"))

from a2wsgi import ASGIMiddleware  # noqa: E402  (FastAPI is ASGI; Passenger speaks WSGI)
from app.main import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
