"""Alerts: always to the events table (dashboard banner); optionally Telegram / email
(owner-supplied tokens, OFF by default). Alerts never include secrets."""
from __future__ import annotations

import logging
import smtplib
import sqlite3
from email.message import EmailMessage

import requests

from ..config.schema import Config
from ..db import log_event
from ..secrets import get_secret, scrub

log = logging.getLogger("thunder.alerts")
PUSH_LEVELS = {"HALT", "ERROR"}


def alert(con: sqlite3.Connection, cfg: Config, level: str, source: str, message: str) -> None:
    message = scrub(message)
    log_event(con, level, source, message)
    if level not in PUSH_LEVELS and "LIVE" not in message:
        return
    if cfg.alerts.telegram_enabled:
        tok, chat = get_secret("telegram_token"), get_secret("telegram_chat_id")
        if tok and chat:
            try:
                requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                              json={"chat_id": chat, "text": f"THUNDER {level}: {message}"}, timeout=10)
            except Exception as e:
                log.warning("telegram alert failed: %s", type(e).__name__)
    if cfg.alerts.email_enabled:
        host, user, pw, to = (get_secret(k) for k in ("smtp_host", "smtp_user", "smtp_password", "alert_email"))
        if host and to:
            try:
                m = EmailMessage()
                m["Subject"], m["From"], m["To"] = f"THUNDER {level}", user or to, to
                m.set_content(message)
                with smtplib.SMTP_SSL(host, 465, timeout=15) as s:
                    if user and pw:
                        s.login(user, pw)
                    s.send_message(m)
            except Exception as e:
                log.warning("email alert failed: %s", type(e).__name__)
