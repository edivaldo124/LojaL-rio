"""Ponto de entrada WSGI (gunicorn app:app) e do comando `flask`."""

from servidor import create_app, sincronizar_admin

app = create_app()
# Acerta a conta admin a cada subida, sem depender do Start Command do Render chamar `flask admin`.
sincronizar_admin(app)

__all__ = ["app"]
