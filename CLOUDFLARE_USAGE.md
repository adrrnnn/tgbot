# Cloudflare Integration

Once set up, the bot fetches API keys from your Cloudflare Worker on every startup instead of reading them from `config.json`. Keys are held in memory only and never written to disk.

## Config options

```json
{
  "cloudflare": {
    "enabled": true,
    "worker_url": "https://your-worker.workers.dev",
    "auth_token": "your-secret-token",
    "fallback_to_local": false,
    "timeout": 10
  }
}
```

**`enabled`** — set to `false` to skip Cloudflare entirely and use local keys.

**`worker_url`** — the full URL to your deployed worker.

**`auth_token`** — must match `BOT_AUTH_TOKEN` in your worker's environment variables.

**`fallback_to_local`** — if `true`, the bot falls back to keys in `config.json` when the worker is unreachable. If `false`, the bot exits on startup if Cloudflare fails. Use `false` in production if you don't want local keys as a fallback.

**`timeout`** — seconds to wait for the worker to respond before treating it as unreachable.

## Disabling Cloudflare

Set `enabled` to `false`. The bot will use `api.gemini_key` and `api.openai_key` from `config.json` directly.

## Rotating API keys

Update the environment variable in the Cloudflare dashboard. The change takes effect on the next bot startup — no code changes needed.

## Troubleshooting

**401** — `auth_token` in config doesn't match `BOT_AUTH_TOKEN` in the worker.

**403** — worker is rejecting requests, possibly a deployment issue. Check the worker logs in the Cloudflare dashboard.

**404** — worker URL is wrong or the worker was deleted.

**Keys load but bot still fails** — the key itself may be exhausted or invalid. Check `logs/bot.log` for quota error messages and replace the key in the Cloudflare dashboard.
