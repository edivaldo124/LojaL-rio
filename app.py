"""Ponto de entrada WSGI (gunicorn app:app) e do comando `flask`."""

from servicos import keep_alive
from servidor import create_app, sincronizar_admin

app = create_app()
# Acerta a conta admin a cada subida, sem depender do Start Command do Render chamar `flask admin`.
sincronizar_admin(app)
# Com KEEP_ALIVE=true, pinga o próprio /health para o Render gratuito não hibernar.
keep_alive.iniciar(app.config["KEEP_ALIVE"], app.config["URL_BASE"], app.config["KEEP_ALIVE_INTERVALO"])

__all__ = ["app"]
