"""Inloggning: losenordshashning, session-konfiguration och atkomstkontroll.

Sessionen bars av en signerad, HttpOnly-cookie (Starlette SessionMiddleware).
Den enda hemligheten i cookien ar anvandarens id - allt annat slas upp i DB:n
vid varje anrop, sa en avstangd/borttagen anvandare tappar atkomst direkt.
"""
from __future__ import annotations

import os
import secrets
import sys

import bcrypt
from fastapi import Depends, HTTPException, Request

from server import store

# Sessionssignering. MASTE sattas i drift (Railway) sa cookies overlever
# omstarter; annars loggas alla ut vid varje deploy. Lokalt faller vi tillbaka
# pa en flyktig nyckel med en varning.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    print(
        "[auth] VARNING: SECRET_KEY saknas - anvander en flyktig nyckel. "
        "Satt SECRET_KEY i miljon (Railway) sa inloggningar overlever omstart.",
        file=sys.stderr,
    )

# Secure-cookie kraver HTTPS. Pa i drift (Railway kor HTTPS), av lokalt sa
# inloggning fungerar over http://localhost.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes", "on")
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 dagar


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
#  Dependencies
# --------------------------------------------------------------------------- #
def current_user(request: Request) -> dict:
    """Den inloggade anvandaren, eller 401. Slar alltid upp i DB:n sa en
    borttagen anvandare inte fortsatter komma in pa en gammal cookie."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "Inte inloggad.")
    user = store.get_user(user_id)
    if not user:
        request.session.clear()
        raise HTTPException(401, "Inte inloggad.")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    """Som current_user men kraver adminbehorighet (403 annars)."""
    if not user["is_admin"]:
        raise HTTPException(403, "Kraver admin.")
    return user


# --------------------------------------------------------------------------- #
#  Bootstrap
# --------------------------------------------------------------------------- #
def ensure_bootstrap_admin() -> None:
    """Skapa ett forsta admin-konto om databasen saknar anvandare, och knyt
    befintliga (agarlosa) samtal till det.

    E-post och losenord las fran ADMIN_EMAIL / ADMIN_PASSWORD. Saknas losenordet
    genereras ett slumpat som skrivs till loggen en gang (Railway: satt
    ADMIN_PASSWORD i miljon for ett kant losenord). Idempotent - kor inget om
    det redan finns anvandare.
    """
    if store.count_users() > 0:
        return

    email = os.getenv("ADMIN_EMAIL", "david@swesharp.se").strip()
    password = os.getenv("ADMIN_PASSWORD")
    generated = False
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True

    user_id = store.create_user(email, hash_password(password), is_admin=True)
    moved = store.assign_orphan_conversations(user_id)

    print(f"[auth] Skapade admin-konto: {email} ({moved} befintliga samtal knutna).", file=sys.stderr)
    if generated:
        print(
            f"[auth] Genererat losenord for {email}: {password}\n"
            "[auth] Logga in och byt det via Anvandare-vyn, eller satt ADMIN_PASSWORD i miljon.",
            file=sys.stderr,
        )
