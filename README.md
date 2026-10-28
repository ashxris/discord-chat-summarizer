# Discord Chat Summarizer Bot

A Discord bot that keeps busy channels readable. Every minute it checks each
watched channel and, if **more than 10 messages** have been sent since the
last summary, condenses the conversation with the **Groq API** and posts the
digest back into the channel. With 10 or fewer messages it stays idle and
keeps counting — nothing is lost.

> 🔑 **Bring Your Own Key (BYOK):** Uses a BYOK architecture where each server provides its own free Groq API key via `/setkey` — ensuring complete privacy, zero API costs for the bot host, and dedicated rate limits for every server.

## How it works

- Admins run `/enable` in the channels they want summarized, and `/setkey`
  once per server to provide a Groq API key.
- The bot buffers the text of human messages (bot messages and
  attachments-only messages are ignored) in memory for every enabled channel.
- A background loop runs every 60 seconds. For each watched channel it
  compares the buffered count against the threshold of **10**: strictly more
  than 10 triggers a summary, 10 or fewer stays idle.
- Because the counter measures messages *since the previous summarization*,
  quiet channels keep accumulating across checks until they cross the
  threshold — messages are never discarded for being too few.
- If the Groq call or the channel post fails, the buffered messages are put
  back and the summary is retried on the next check.
- With no key stored, enabled channels simply pause until someone runs
  `/setkey`.

## Setup

**1. Discord application** — at the [Developer Portal](https://discord.com/developers/applications):

1. Create an application, then a bot under the **Bot** tab.
2. Enable **Message Content Intent** under *Privileged Gateway Intents*
   (required to read message text).
3. Invite it with this URL (replace `YOUR_APP_ID`, found under
   *OAuth2 → General*):

   ```
   https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot+applications.commands&permissions=84992
   ```

   That grants View Channels, Send Messages, Embed Links, and Read Message
   History.

**2. Free Groq API Key** — Groq offers a fast, generous **free tier with no credit card required**. Getting a key takes under a minute:
   1. Head over to [console.groq.com](https://console.groq.com/keys) and sign in with Google or GitHub.
   2. Click **Create API Key** and copy your key (it starts with `gsk_`).
   3. That's it! You won't even need to edit configuration files — simply configure it directly in Discord by running `/setkey key:gsk_...` as an admin.

**3. Run the bot** (Python 3.10+):

```bash
cd Discord_Chat_Summarizer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then paste your bot token into DISCORD_TOKEN
python bot.py
```

**4. In Discord** (as a server admin):

- `/setkey key:gsk_...` — validates and stores the key for this server
- `/enable` — in each channel you want summarized
- `/status` — verify everything

Slash commands can take a few minutes to appear on first launch. For instant
commands while testing, put your server ID in `DEV_GUILD_ID` in `.env`.

## Commands

| Command | Who | What it does |
| --- | --- | --- |
| `/setkey key` | Administrator | Validates the key with Groq and stores it for this server |
| `/clearkey` | Administrator | Removes the stored key (summaries pause) |
| `/setmodel model` | Administrator | Override the Groq model, e.g. `llama-3.1-8b-instant` |
| `/enable` | Administrator | Watch the current channel |
| `/disable` | Administrator | Stop watching the current channel and discard its buffer |
| `/status` | anyone (ephemeral) | Show key state, model, threshold, buffered count |

Command results are ephemeral and keys are only ever displayed masked (last
4 characters).

## Configuration (`.env`)

| Variable | Default | Meaning |
| --- | --- | --- |
| `DISCORD_TOKEN` | — | Required. Bot token from the Developer Portal |
| `GROQ_MODEL` | `qwen/qwen3.8-27b` | Default model; per-server via `/setmodel` |
| `MESSAGE_THRESHOLD` | `10` | Summarize when strictly more than this many messages since the last summary |
| `INTERVAL_SECONDS` | `60` | How often channels are checked |
| `DEV_GUILD_ID` | — | Instant slash-command sync to one server for testing |
| `DB_PATH` | `data/chatsummarizer.db` | SQLite database location |
| `DONATION_URL` | `https://buymeacoffee.com/ashwiinn` | Donation link shown in `/status` |

## Data & privacy notes

- Groq keys are stored in **plaintext SQLite** at `DB_PATH`. Anyone with
  Administrator can replace the key, and the bot host can read it — only
  share the server with people you trust with that.
- Message text lives in memory only; it is never written to disk.
- Groq processes message content server-side per their API terms — make sure
  channel members are comfortable with that (a good idea for any AI bot).

## Project layout

```
bot.py          entrypoint: client, slash commands, the 60-second summary loop
summarizer.py   Groq client wrapper, prompt, transcript formatting
store.py        SQLite persistence (per-guild key/model, enabled channels)
```

## Troubleshooting

- **Bot posts nothing** — check `/status`: is the channel enabled, is the key
  set, and is the buffered count above 10?
- **Embeds / summaries not posting** — summaries are delivered as Discord
  embeds. Ensure the bot has **Embed Links** permission enabled in that channel
  (under Channel Settings → Permissions → allow *Embed Links* and *Send Messages*).
  If Embed Links is blocked, the summary cannot be posted.
- **Slash commands don't appear or appear duplicated** — make sure the bot was
  invited with the `applications.commands` scope, and try `DEV_GUILD_ID` for instant
  sync. If duplicate commands appear in the menu, press `Cmd + R` (Mac) or `Ctrl + R`
  (Windows) in Discord to refresh your client's cache.
- **`PrivilegedIntentsRequired` on startup** — the Message Content Intent
  wasn't enabled in the Developer Portal.
- **Model errors** — Groq model names change; browse available models at
  [console.groq.com/docs/models](https://console.groq.com/docs/models) and
  `/setmodel` accordingly.
