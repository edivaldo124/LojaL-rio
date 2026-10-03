"""Checagem de papel ADMIN no servidor (RNF04)."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import abort, redirect, request, url_for
from flask_login import current_user
from werkzeug.wrappers import Response


def bloquear_nao_admin() -> Response | None:
    """Devolve a resposta de bloqueio, ou None se a pessoa é admin."""
    if not current_user.is_authenticated:
        destino = request.full_path if request.query_string else request.path
        return redirect(url_for("conta.entrar", next=destino))
    if not current_user.is_admin:
        abort(403)
    return None


def admin_obrigatorio(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def protegida(*args: Any, **kwargs: Any) -> Any:
        bloqueio = bloquear_nao_admin()
        if bloqueio is not None:
            return bloqueio
        return view(*args, **kwargs)

    return protegida
