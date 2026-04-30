# Telegram Bot

A desktop application that runs an AI-powered auto-reply bot on a personal Telegram account using Pyrogram. Replies are generated via Google Gemini (primary) or OpenAI (fallback) based on a configurable persona profile.

## Warning

This uses Pyrogram in user-account mode, not the Bot API. That means the bot operates as a real Telegram user — people messaging the account will not know they're talking to automation. This technically violates Telegram's ToS. Use responsibly and at your own risk. Session files stored in `pyrogram_sessions/` give full access to the account; keep them private.

## Requirements

- Python 3.10+
- A Telegram account with API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- A Gemini API key (free) from [ai.google.dev](https://ai.google.dev/) or an OpenAI key

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the setup wizard to generate the config template:

```bash
python main.py --setup
```

Edit `config/config.json` with your credentials:

```json
{
  "telegram": {
    "api_id": 123456,
    "api_hash": "your_api_hash",
    "phone_number": "+1234567890"
  },
  "api": {
    "gemini_key": "your_gemini_key",
    "openai_key": "sk-..."
  }
}
```

Then launch:

```bash
python main.py
```

On first run the app will prompt for your Telegram verification code through a dialog box and create a session file so you won't need to log in again.

## Configuration

All settings live in `config/config.json`. Environment variables can override any value at runtime:

| Variable | Overrides |
|---|---|
| `TELEGRAM_API_ID` | `telegram.api_id` |
| `TELEGRAM_API_HASH` | `telegram.api_hash` |
| `TELEGRAM_PHONE` | `telegram.phone_number` |
| `GEMINI_API_KEY` | `api.gemini_key` |
| `OPENAI_API_KEY` | `api.openai_key` |
| `TELEGRAM_BOT_DB` | `database.path` |

Optionally, API keys can be fetched from a Cloudflare Worker at startup instead of storing them locally — see `CLOUDFLARE_SETUP.md`.

## Project Structure

```
├── main.py                  # Entry point
├── launch.pyw               # Windows no-console launcher
├── requirements.txt
├── config/
│   └── config.json          # Your credentials (gitignored)
├── src/
│   ├── bot_server.py        # Pyrogram client + handler registration
│   ├── config.py            # Config loading (JSON + env + Cloudflare)
│   ├── database.py          # SQLite schema and queries
│   ├── llm.py               # Gemini/OpenAI wrapper
│   ├── startup.py           # Pre-flight checks
│   └── handlers/
│       └── ai_reply_handler.py
│   └── ui/
│       ├── main_gui.py      # Main PyQt5 window
│       └── tabs/            # Accounts, Profiles, Start Bot, etc.
├── cli/
│   └── db_status.py         # DB inspection and backup tool
├── pyrogram_sessions/       # Session files (gitignored)
├── logs/                    # bot.log (gitignored)
└── telegrambot.db           # SQLite database (gitignored)
```

## Running

```bash
# Normal launch (opens GUI)
python main.py

# Re-run setup wizard
python main.py --setup

# Reinitialise database schema
python main.py --db-init

# Check database stats / create a backup
python cli/db_status.py
python cli/db_status.py --backup
python cli/db_status.py --cleanup
```

## Troubleshooting

**`ModuleNotFoundError`** — run `pip install -r requirements.txt`

**`AuthKeyUnregistered` or `Unauthorized`** — delete the file in `pyrogram_sessions/` and re-authenticate

**Bot isn't replying** — check `logs/bot.log`. Most likely the API key is missing or exhausted. The Start Bot tab shows live log output while running.

**Cloudflare 403** — your `auth_token` in config doesn't match `BOT_AUTH_TOKEN` set in the worker. Either fix the token or set `cloudflare.enabled` to `false` to use local keys.

## Security

Don't commit `config/config.json`, `pyrogram_sessions/`, or `telegrambot.db` — all three are gitignored by default. The config file contains your API credentials and the session files are equivalent to a logged-in Telegram session.
