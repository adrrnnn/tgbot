# Cloudflare Worker Setup

This is optional. By default the bot reads API keys directly from `config/config.json`. If you'd rather store them in Cloudflare (so they're never written to disk on the machine running the bot), follow these steps.

## 1. Create a Worker

1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Go to **Workers & Pages** → **Create application** → **Create Worker**
3. Give it a name (e.g. `telegram-bot-keys`) and deploy the default placeholder

## 2. Deploy the worker code

1. Open the worker editor
2. Replace the default code with the contents of `cloudflare_worker.js` from this repo
3. Save and deploy

## 3. Set environment variables

In the worker's **Settings → Environment variables**, add:

| Name | Value |
|---|---|
| `BOT_AUTH_TOKEN` | Any secret string you generate — this is what the bot sends to authenticate |
| `GEMINI_API_KEY` | Your Gemini API key |
| `OPENAI_API_KEY` | Your OpenAI key (optional) |

Mark all of them as encrypted.

## 4. Update config.json

```json
{
  "cloudflare": {
    "enabled": true,
    "worker_url": "https://your-worker.your-subdomain.workers.dev",
    "auth_token": "the BOT_AUTH_TOKEN value you set above",
    "fallback_to_local": true,
    "timeout": 10
  }
}
```

Set `fallback_to_local` to `false` if you want the bot to refuse to start when Cloudflare is unreachable (stricter, better for production). Leave it `true` during development so a temporary network issue doesn't block you.

## 5. Verify it's working

```bash
python -c "from src.config import ConfigManager; c = ConfigManager(); print('gemini:', 'set' if c.api.gemini_api_key else 'missing')"
```

If it prints `gemini: set`, the worker is returning keys correctly.

## Rotating keys

Update the environment variable in the Cloudflare dashboard. No bot restart needed — the new key is picked up on the next startup.

## Troubleshooting

**403 Forbidden** — the `auth_token` in your config doesn't match `BOT_AUTH_TOKEN` in the worker. They need to be identical.

**404 Not Found** — double-check the `worker_url` in config. Copy it directly from the Cloudflare dashboard.

**Invalid JSON** — check the worker's log tab in the Cloudflare dashboard for errors in the worker code.

**Falling back to local unexpectedly** — if `fallback_to_local` is `true` and the worker is unreachable, the bot silently uses local keys. Check `logs/bot.log` for a "Cloudflare unreachable" line.
