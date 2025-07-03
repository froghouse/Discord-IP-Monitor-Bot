# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python Discord bot that monitors public IP address changes and sends notifications when the IP changes. The bot uses the discord.py library and runs continuously to check for IP changes at configurable intervals.

## Architecture

- **Entry Point**: `main.py` - loads configuration and starts the bot
- **Core Bot**: `ip_monitor/bot.py` - main Discord bot class with event handlers and scheduled tasks
- **Configuration**: `ip_monitor/config.py` - environment-based configuration management using dataclasses
- **IP Service**: `ip_monitor/ip_service.py` - handles IP retrieval from multiple APIs with fallback and retry logic
- **Storage**: `ip_monitor/storage.py` - atomic file operations for IP history and current IP storage
- **Commands**: Split into `ip_monitor/commands/ip_commands.py` (user commands) and `admin_commands.py` (admin-only)
- **Utilities**: Rate limiting and logging setup in `ip_monitor/utils/`

The bot uses Discord's tasks extension for scheduled IP checking and maintains both current IP and historical IP data in JSON files.

## Development Commands

### Setup and Installation
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Bot
```bash
python3 main.py
```

### Code Quality and Linting
```bash
# Format imports
isort .

# Format code
ruff format .

# Lint and auto-fix issues
ruff check --fix --exclude .venv .
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
pre-commit install

# Run pre-commit on all files
pre-commit run --all-files
```

## Configuration

The bot uses environment variables loaded from a `.env` file. See `.env.example` for all available options. Key required settings:
- `DISCORD_BOT_TOKEN` - Discord bot token
- `CHANNEL_ID` - Discord channel ID for notifications

## Bot Commands

- `!ip` - Manually check current public IP
- `!history` - View IP change history
- `!status` - View bot status and configuration
- `!help` - Display available commands
- `!stop` - Gracefully shut down bot (admin only)

## Testing Mode

Set `TESTING_MODE=true` in environment to run a single IP check and exit (useful for testing API connectivity).