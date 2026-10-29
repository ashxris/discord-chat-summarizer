<div align="center">
  <img src="assets/icon.jpg" alt="Chat Summarizer Icon" width="128" />
  <h1>Chat Summarizer</h1>
  <p><strong>A Discord bot that condenses active channel conversations into concise AI digests using Groq.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/Discord-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord" />
    <img src="https://img.shields.io/badge/Powered%20by-Groq-F55036?style=flat" alt="Groq" />
    <a href="https://buymeacoffee.com/ashwiinn"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me a Coffee" /></a>
  </p>
</div>

---

A Discord bot that keeps busy channels readable. It monitors conversation activity across multiple channels and automatically summarizes them into clean, bulleted digests with the **Groq API** whenever activity crosses your message threshold. With fewer messages, it stays idle and keeps counting — nothing is lost.

## ✨ Features

- 🔑 **Bring Your Own Key (BYOK)**: Operates on a BYOK architecture where each server supplies its own free Groq API key via `/setkey` — ensuring complete privacy, dedicated rate limits, and zero API costs for the bot host.
- 📡 **Multi-Channel & Multi-Server Support**: Initiate and run the bot across multiple channels simultaneously. Each channel operates independently with its own message buffer, counter, and summary timer.
- ⏱️ **Customizable Intervals (`/setinterval`)**: Server admins can tweak how frequently channels are checked directly via slash commands (anywhere between **1 minute and 6 hours**).
- 📊 **Customizable Message Thresholds (`/setthreshold`)**: Fine-tune message triggers between **10 and 400 messages** so you only get digests when there's meaningful discussion.
- ⚡ **Blazing-Fast AI Inference**: Powered by Groq (default: `qwen/qwen3.8-27b`) to generate objective, high-quality channel summaries in seconds.
- 🛡️ **Administrator Security**: All configuration commands are restricted to members with Discord **Administrator** permissions.

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

<details>
<summary><strong>☁️ Deploy on Railway (recommended for running 24/7)</strong></summary>

The bot has to stay online to catch messages, so a small always-on host is an
easier home for it than a laptop that sleeps. Railway runs the repo as-is, with
no Dockerfile needed.

1. Push this repo to GitHub, then in [Railway](https://railway.com) choose
   **New Project → Deploy from GitHub repo** and select it.
2. Open **Variables** and add `DISCORD_TOKEN` with your bot token. Add any
   other `.env` values you want to override (see the configuration table below).
3. Add a **Volume** mounted at `/data`, then set
   `DB_PATH=/data/chatsummarizer.db`. The SQLite file holds each server's Groq
   key and enabled channels — without the volume it is wiped on every redeploy.
4. Under **Settings → Deploy**, set the custom start command to `python bot.py`.
   The bot is a worker, so leave domains and ports untouched.
5. Deploy and watch the logs for `Logged in as …`, then run `/setkey` and
   `/enable` in Discord as usual.

After that, pushes to the connected branch redeploy automatically.

</details>

## Commands

| Command | Who | What it does |
| --- | --- | --- |
| `/setkey key` | Administrator | Validates the key with Groq and stores it for this server |
| `/clearkey` | Administrator | Removes the stored key (summaries pause) |
| `/setmodel model` | Administrator | Override the Groq model, e.g. `llama-3.3-70b-versatile` |
| `/setinterval seconds` | Administrator | Set check interval between 1 minute and 6 hours (60 to 21600s) |
| `/setthreshold messages` | Administrator | Set message trigger threshold between 10 and 400 messages |
| `/enable` | Administrator | Watch the current channel (tracks independently) |
| `/disable` | Administrator | Stop watching the current channel and discard its buffer |
| `/status` | anyone (ephemeral) | Show key state, model, interval, threshold, and buffered count |

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

## 🔧 Troubleshooting

| Issue | Likely Cause | Solution |
| --- | --- | --- |
| **Bot posts no summaries** | Channel disabled, key missing, or under threshold | Run `/status` in the channel. Verify the channel is **enabled**, Groq key is **set**, and buffered messages exceed your threshold. |
| **Embeds / digests not posting** | Missing channel permissions | Summaries are formatted as Discord embeds. Ensure the bot has **Embed Links** and **Send Messages** granted in the channel permissions. |
| **Commands missing or duplicated** | Discord client cache | If commands appear twice or don't refresh after updates, press `Cmd + R` (Mac) or `Ctrl + R` (Windows) in Discord to reload client cache. |
| **`PrivilegedIntentsRequired` on startup** | Message Content Intent disabled | In the [Discord Developer Portal](https://discord.com/developers/applications), open the **Bot** tab, scroll to *Privileged Gateway Intents*, and enable **Message Content Intent**. |
| **Model not found / Groq errors** | Deprecated model name or account quota | Check available models at [console.groq.com/docs/models](https://console.groq.com/docs/models) and switch using `/setmodel model:<name>`. |

## Contributing

Contributions are welcome! Please check out our [Contributing Guide](CONTRIBUTING.md) for local development setup, guidelines, and PR checklist.
