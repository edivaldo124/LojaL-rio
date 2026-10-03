"""Ponto de entrada WSGI (gunicorn app:app) e do comando `flask`."""

from servidor import create_app

app = create_app()

__all__ = ["app"]
