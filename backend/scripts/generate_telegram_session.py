"""Generate a Telethon StringSession for hunt-scraping.

Usage:
    python scripts/generate_telegram_session.py

Required env vars:
    SCRAPING_TELEGRAM_API_ID
    SCRAPING_TELEGRAM_API_HASH
"""
from __future__ import annotations

import os
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession


def main() -> int:
    api_id_raw = os.getenv("SCRAPING_TELEGRAM_API_ID", "").strip()
    api_hash = os.getenv("SCRAPING_TELEGRAM_API_HASH", "").strip()

    if not api_id_raw or not api_hash:
        print("Defina SCRAPING_TELEGRAM_API_ID e SCRAPING_TELEGRAM_API_HASH antes de rodar o script.", file=sys.stderr)
        return 1

    try:
        api_id = int(api_id_raw)
    except ValueError:
        print("SCRAPING_TELEGRAM_API_ID deve ser numérico.", file=sys.stderr)
        return 1

    print("Abrindo autenticação Telegram interativa...")
    print("Você vai informar telefone e, se necessário, o código recebido no Telegram.")

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()

    print("\nSESSION_STRING gerada com sucesso:\n")
    print(session_string)
    print("\nGuarde esse valor em SCRAPING_TELEGRAM_SESSION_STRING.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
