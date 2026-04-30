# Quick Start

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Get Telegram API credentials

Go to [my.telegram.org/apps](https://my.telegram.org/apps), log in with your Telegram account, and create an application. You'll get an `api_id` (number) and `api_hash` (string) — keep these private.

## 3. Configure

```bash
python main.py --setup
```

This creates `config/config.json`. Open it and fill in your credentials:

```json
{
  "telegram": {
    "api_id": 123456,
    "api_hash": "your_api_hash",
    "phone_number": "+1234567890"
  },
  "api": {
    "gemini_key": "your_gemini_key"
  }
}
```

A free Gemini key is enough to get started — get one at [ai.google.dev](https://ai.google.dev/).

## 4. Run

```bash
python main.py
```

On first launch the app will ask for your Telegram verification code via a dialog. After that a session file is saved and you won't need to log in again.

Once authenticated, go to the **Start Bot** tab and hit Start. The bot will begin replying to incoming private messages using the active profile.

---

## CLI tools

```bash
# View database stats
python cli/db_status.py

# Create a database backup
python cli/db_status.py --backup

# Delete expired conversations
python cli/db_status.py --cleanup
```

---

## Common issues

**No reply being sent** — open the Start Bot tab and check the log output. Most likely the API key is missing or the bot isn't started.

**Lost session / auth error** — delete the file inside `pyrogram_sessions/` and relaunch. The app will prompt for the verification code again.

**Config not found** — run `python main.py --setup` to regenerate the template.
