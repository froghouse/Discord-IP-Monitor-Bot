# Discord IP Monitor Bot

A robust Discord bot that monitors your public IP address and notifies you when it changes. Perfect for home servers, dynamic IP setups, or anyone who wants to keep track of their public IP address.

## Features

- 🔄 **Real-time IP monitoring**: Periodically checks your public IP address and notifies when it changes
- 📊 **IP history tracking**: Maintains a history of previous IP addresses with timestamps
- 🛡️ **Multiple API fallbacks**: Uses multiple services to retrieve IP information with retry logic
- ⚡ **Concurrent checks**: Option to check multiple IP services simultaneously for faster results
- 🔐 **Rate limiting**: Built-in rate limiting to prevent API abuse
- 🧠 **Smart error handling**: Comprehensive error handling and recovery mechanisms
- 📝 **Detailed logging**: Configurable logging levels for troubleshooting
- 💬 **Simple commands**: Easy-to-use Discord commands for manual checks and configuration

## Commands

- `!ip` - Manually check the current public IP address
- `!history` - View the history of IP address changes
- `!status` - View the current bot status and configuration
- `!help` - Display available commands
- `!stop` - Gracefully shut down the bot (admin only)

## Installation

### Prerequisites

- Python 3.11 or higher
- Discord Bot Token (create one at [Discord Developer Portal](https://discord.com/developers/applications))
- Permissions to write files in the bot directory

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/discord-ip-monitor-bot.git
cd discord-ip-monitor-bot
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Create a `.env` file with your configuration:
```
# Required settings
DISCORD_BOT_TOKEN=your_discord_bot_token_here
CHANNEL_ID=123456789012345678  # The channel ID where notifications will be sent

# Optional settings (defaults shown)
CHECK_INTERVAL=30  # Minutes between automatic IP checks
MAX_RETRIES=3  # Number of retry attempts when IP APIs fail
RETRY_DELAY=5  # Seconds to wait between retries
IP_FILE=last_ip.json  # File to store the current IP
IP_HISTORY_FILE=ip_history.json  # File to store IP history
IP_HISTORY_SIZE=10  # Number of historical IPs to keep
LOG_LEVEL=INFO  # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
STARTUP_MESSAGE_ENABLED=true  # Whether to send a message when the bot starts
TESTING_MODE=false  # Test mode will check IP once and exit
CONCURRENT_API_CHECKS=true  # Whether to check all APIs simultaneously
RATE_LIMIT_PERIOD=300  # Rate limit window in seconds
MAX_CHECKS_PER_PERIOD=10  # Maximum checks allowed in the rate limit window
```

4. Run the bot:
```bash
python main.py
```

## Deployment

For production deployment, you may want to use a process manager like `systemd`, `supervisor`, or Docker. Here's a simple systemd service file example:

```ini
[Unit]
Description=Discord IP Monitor Bot
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/bot
ExecStart=/path/to/bot/venv/bin/python /path/to/bot/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

## Security Considerations

- The bot stores IP addresses in plain text files. Ensure the server has appropriate file permissions.
- The bot token in the `.env` file should be kept secure.
- Consider running the bot with minimal permissions on your system.

## Troubleshooting

- Check the `bot.log` file for detailed error messages
- Ensure the bot has the correct permissions in the Discord channel
- Verify that the bot has write access to its directory
- If IP checks consistently fail, check your internet connection or try disabling `CONCURRENT_API_CHECKS`

## Acknowledgments

- [discord.py](https://github.com/Rapptz/discord.py) for the Discord API wrapper
- Public IP APIs used in this project:
  - ipify.org
  - ifconfig.me
  - icanhazip.com
  - checkip.amazonaws.com
