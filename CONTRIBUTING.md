# Contributing to Chat Summarizer

Thank you for considering contributing to **Chat Summarizer**! Whether you're fixing a bug, adding a new feature, improving documentation, or optimizing prompts, your help is welcome.

Please take a moment to review this guide to make the contribution process smooth and effective.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Features](#suggesting-features)
  - [Submitting Pull Requests](#submitting-pull-requests)
- [Local Development Setup](#local-development-setup)
- [Development Guidelines](#development-guidelines)
- [Pull Request Checklist](#pull-request-checklist)

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful and constructive in all discussions, issues, and pull requests.

---

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report, please check existing [Issues](https://github.com/ashxris/discord-chat-summarizer/issues) to see if it has already been reported.

When filing an issue, include:
- A clear, descriptive title.
- Steps to reproduce the problem.
- Expected vs. actual behavior.
- Relevant error traceback or logs (make sure to **redact bot tokens or API keys**).
- Your Python version and OS.

### Suggesting Features

Feature ideas are always welcome! Open an issue describing:
- What problem the feature solves.
- How you envision the user experience in Discord (e.g., slash command, embed layout).
- Any potential alternatives or trade-offs.

---

## Local Development Setup

To test changes locally, you'll need:
- **Python 3.10+**
- A **Discord Bot Token** from the [Discord Developer Portal](https://discord.com/developers/applications) with **Message Content Intent** enabled
- A free **Groq API key** from [console.groq.com](https://console.groq.com/keys)

### Step 1: Fork and Clone

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/<your-username>/discord-chat-summarizer.git
   cd discord-chat-summarizer
   ```

### Step 2: Set Up Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

Copy the example file to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DISCORD_TOKEN`: Your test bot's token.
- `DEV_GUILD_ID`: Your test Discord server ID (enables instant slash-command sync during testing).

### Step 4: Run the Bot

```bash
python bot.py
```

In your test Discord server:
1. Run `/setkey key:gsk_...` with your Groq API key.
2. Run `/enable` in a channel.
3. Post 11+ test messages to trigger a summary digest.

---

## Development Guidelines

### Code Style
- Write clean, readable, idiomatic Python (3.10+).
- Use type hints (`from __future__ import annotations`).
- Keep async operations non-blocking.
- Maintain existing architecture:
  - `bot.py` handles the Discord client, commands, and scheduled loop.
  - `summarizer.py` handles Groq API communication and transcript formatting.
  - `store.py` handles SQLite persistence.

### Security & Privacy
- **Never commit credentials** (`.env`, database files with keys, or bot tokens).
- Maintain user privacy: messages are buffered in memory only and never persisted to disk.

---

## Pull Request Checklist

Before submitting your PR, please verify:

1. [ ] Your code runs without errors (`python -m py_compile bot.py summarizer.py store.py`).
2. [ ] You tested the bot on a test Discord server.
3. [ ] No sensitive credentials, tokens, or `.env` files are tracked in git (`git status`).
4. [ ] Documentation in `README.md` is updated if your change modifies commands, configuration, or behavior.
5. [ ] Your commit messages are concise and descriptive.

Once submitted, we'll review your PR as quickly as possible. Thank you for making Chat Summarizer better! 🚀
