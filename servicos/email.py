"""Envio de e-mail por SMTP. Sem SMTP_HOST configurado, a mensagem vai para o log."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from flask import current_app


def enviar(destinatario: str, assunto: str, texto: str) -> None:
    config = current_app.config
    if not config["SMTP_HOST"]:
        current_app.logger.warning(
            "SMTP não configurado. E-mail para %s | %s\n%s", destinatario, assunto, texto
        )
        return

    mensagem = EmailMessage()
    mensagem["From"] = config["EMAIL_REMETENTE"]
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)

    with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORTA"], timeout=15) as smtp:
        smtp.starttls()
        if config["SMTP_USUARIO"]:
            smtp.login(config["SMTP_USUARIO"], config["SMTP_SENHA"])
        smtp.send_message(mensagem)
