# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python Discord bot that monitors public IP address changes and sends notifications when the IP changes. The bot uses the discord.py library and runs continuously to check for IP changes at configurable intervals.

## Architecture

- **Entry Point**: `main.py` - loads configuration and starts the bot
- **Core Bot**: `ip_monitor/bot.py` - main Discord bot class with event handlers and scheduled tasks
- **Configuration**: `ip_monitor/config.py` - environment-based configuration management using dataclasses
- **IP Service**: `ip_monitor/ip_service.py` - handles IP retrieval from multiple APIs with fallback and retry logic
- **Storage**: `ip_monitor/storage.py` - SQLite database storage for IP history and current IP with data integrity
- **Commands**: Split into `ip_monitor/commands/ip_commands.py` (user commands) and `admin_commands.py` (admin-only)
- **Utilities**: Rate limiting, logging, and resilience components in `ip_monitor/utils/`

### Resilience & Fault Tolerance System

The bot includes a comprehensive resilience system designed to handle various failure scenarios:

- **Discord Rate Limiter** (`ip_monitor/utils/discord_rate_limiter.py`) - Handles Discord API rate limits with exponential backoff and jitter
- **Circuit Breaker** (`ip_monitor/utils/circuit_breaker.py`) - Prevents cascading failures for IP API calls with 3-state pattern (CLOSED/OPEN/HALF_OPEN)
- **Service Health Monitor** (`ip_monitor/utils/service_health.py`) - Tracks system health with 5-level degradation (NORMAL → CRITICAL) and automatic fallback activation
- **Message Queue** (`ip_monitor/utils/message_queue.py`) - Async message queuing with persistence, priority handling, and automatic retry for Discord API downtime

The bot uses Discord's tasks extension for scheduled IP checking and maintains both current IP and historical IP data in a SQLite database for improved data integrity and performance. During service outages, the system gracefully degrades functionality while maintaining core operations.

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
- `DB_FILE` - SQLite database file path (default: `ip_monitor.db`)

### New Resilience Configuration Options

- `CIRCUIT_BREAKER_ENABLED` - Enable/disable circuit breaker (default: true)
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` - Failures before opening circuit (default: 3)
- `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` - Seconds before testing recovery (default: 120)
- `MESSAGE_QUEUE_ENABLED` - Enable async message queuing (default: true)
- `MESSAGE_QUEUE_MAX_SIZE` - Maximum queued messages (default: 1000)
- `MESSAGE_QUEUE_MAX_AGE_HOURS` - Message expiry time (default: 24)
- `MESSAGE_QUEUE_BATCH_SIZE` - Messages processed per batch (default: 5)
- `MESSAGE_QUEUE_PROCESS_INTERVAL` - Seconds between batches (default: 1.0)

### Storage Configuration

- `DB_FILE` - SQLite database file path (default: `ip_monitor.db`)
- `IP_FILE` - Legacy JSON file for current IP (used for migration only)
- `IP_HISTORY_FILE` - Legacy JSON file for IP history (used for migration only)
- `IP_HISTORY_SIZE` - Maximum number of IP records to store (default: 10)

## Bot Commands

### User Commands
- `!ip` - Manually check current public IP
- `!history` - View IP change history
- `!status` - View bot status, configuration, and system health
- `!help` - Display available commands

### Admin Commands
- `!stop` - Gracefully shut down bot (admin only)
- `!config` - Manage bot configuration at runtime
- `!config show` - Display current configuration
- `!config show <field>` - Show specific configuration field
- `!config set <field> <value>` - Update configuration field
- `!config list` - List all configurable fields with descriptions
- `!config save` - Save current configuration to file
- `!config reload` - Reload configuration from file (requires restart)
- `!api` - Manage custom IP detection APIs
- `!api list` - List all configured IP APIs
- `!api add <name> <url> [format] [field]` - Add new IP API
- `!api remove <id>` - Remove IP API
- `!api enable/disable <id>` - Enable/disable IP API
- `!api test <id>` - Test IP API
- `!api priority <id> <priority>` - Set API priority
- `!api stats` - Show API performance statistics
- `!queue` - Show message queue status and statistics
- `!queue clear` - Clear all queued messages
- `!queue retry` - Retry all failed messages
- `!queue start` - Start message queue processing
- `!queue stop` - Stop message queue processing

## Runtime Configuration Management

The bot supports dynamic configuration changes through Discord commands without requiring a restart for most settings.

### Configurable Fields

**IP Monitoring:**
- `check_interval` (1-1440 minutes) - IP check interval ⚠️ *Restart required*
- `max_retries` (1-10) - Maximum retry attempts for IP checks
- `retry_delay` (1-300 seconds) - Delay between retries
- `concurrent_api_checks` (true/false) - Enable concurrent API checks

**Circuit Breaker:**
- `circuit_breaker_enabled` (true/false) - Enable circuit breaker pattern
- `circuit_breaker_failure_threshold` (1-20) - Failures before opening circuit
- `circuit_breaker_recovery_timeout` (10-3600 seconds) - Recovery timeout

**Rate Limiting:**
- `rate_limit_period` (60-3600 seconds) - Rate limit period
- `max_checks_per_period` (1-100) - Maximum checks per period

**Storage:**
- `ip_history_size` (1-100) - Maximum IP history entries

**Messages:**
- `startup_message_enabled` (true/false) - Enable startup notifications

**Custom APIs:**
- `custom_apis_enabled` (true/false) - Enable custom IP detection APIs

**Message Queue:**
- `message_queue_enabled` (true/false) - Enable async message queue
- `message_queue_max_size` (10-10000) - Maximum messages in queue
- `message_queue_max_age_hours` (1-168 hours) - Maximum message age
- `message_queue_batch_size` (1-50) - Messages processed per batch
- `message_queue_process_interval` (0.1-60.0 seconds) - Processing interval

### Configuration Persistence

Configuration changes are automatically saved to `bot_config.json` and persist across bot restarts. The bot loads environment variables first, then applies any saved configuration overrides from the JSON file.

### Usage Examples

```
!config show                           # Show all configuration
!config show check_interval            # Show specific field
!config set max_retries 5              # Update retry count
!config set circuit_breaker_enabled false  # Disable circuit breaker
!config list                           # List all configurable fields
!config save                           # Save current config to file
```

## Custom IP Detection APIs

The bot supports configuring custom IP detection services with automatic performance tracking and failover.

### API Response Formats

**Supported Formats:**
- `json` - JSON response with IP in specified field
- `text` - Plain text IP response
- `auto` - Auto-detect format (default)

**JSON Field Examples:**
- `ip` - Most common field name
- `origin` - Used by some services
- `address` - Alternative field name

### API Management Commands

**Adding APIs:**
```
!api add "My JSON API" "https://api.example.com/ip" json ip
!api add "Simple Text API" "https://text.example.com/" text
!api add "Auto-detect API" "https://auto.example.com/"
```

**Managing APIs:**
```
!api list                              # Show all APIs with performance data
!api enable my_json_api                # Enable specific API
!api disable my_json_api               # Disable specific API
!api priority my_json_api 1            # Set highest priority
!api test my_json_api                  # Test API response
!api remove my_json_api                # Remove API permanently
!api stats                             # Show performance rankings
```

### Performance Tracking

The system automatically tracks:
- **Success Rate**: Percentage of successful requests
- **Response Time**: Average response time with moving average
- **Performance Score**: Composite score considering success rate, speed, and recent failures
- **Recent Activity**: Last success/failure timestamps

APIs are automatically ranked by performance score and used in optimal order.

### API Configuration

**Custom API Settings:**
- `custom_apis_enabled` (true/false) - Enable custom IP detection APIs
- `api_config_file` - Configuration file path (default: `ip_apis.json`)

**Default APIs:**
The system includes 5 default APIs (IPify JSON/Text, ifconfig.me, icanhazip.com, AWS CheckIP) which are automatically configured on first run.

### Failover Behavior

- APIs are tried in priority order, then by performance score
- Failed APIs are automatically deprioritized
- System falls back to built-in APIs if all custom APIs fail
- Performance data persists across bot restarts

## Resilience Features

### System Health & Degradation
The bot automatically adjusts its behavior based on service health:
- **NORMAL**: Full functionality with standard check intervals
- **MINOR**: Slight increase in check intervals, all features active
- **MODERATE**: Reduced notification frequency, longer intervals
- **SEVERE**: Silent monitoring mode, minimal Discord API usage
- **CRITICAL**: Emergency operation with basic IP tracking only

### Message Priority System
Messages are queued with different priorities during Discord API issues:
- **CRITICAL**: System errors and urgent alerts (processed first)
- **HIGH**: IP address changes (high priority)
- **NORMAL**: User-requested commands and status updates
- **LOW**: History requests and help messages (processed last)

### Circuit Breaker Behavior
IP API calls are protected by a circuit breaker that:
- **CLOSED**: Normal operation, all APIs available
- **OPEN**: API failures detected, using cached IP fallback
- **HALF_OPEN**: Testing recovery, limited API calls allowed

### Message Queue Persistence
The message queue survives bot restarts and includes:
- Automatic message deduplication to prevent spam
- Exponential backoff retry for failed messages
- Message expiration to prevent stale notifications
- Priority-based processing during recovery

## SQLite Storage System

The bot uses SQLite database for reliable data storage with the following benefits:

### Database Schema
- **current_ip table**: Stores the single current IP address with timestamp
- **ip_history table**: Maintains chronological history of IP changes with automatic size limiting
- **Indexes**: Optimized queries with timestamp indexing for better performance

### Data Integrity Features
- **ACID Transactions**: Ensures data consistency during crashes or power failures
- **Automatic Migration**: Seamlessly converts existing JSON files to SQLite on first run
- **Input Validation**: IP address format validation before storage
- **Constraint Enforcement**: Database-level data validation and foreign key constraints

### Performance Optimizations
- **Connection Pooling**: Efficient database connection management
- **Indexed Queries**: Fast lookups with timestamp-based indexing
- **Batch Operations**: Efficient bulk data operations for history management
- **Memory Management**: Automatic cleanup of old history records

### Backward Compatibility
- **Automatic Migration**: Existing `last_ip.json` and `ip_history.json` files are automatically imported
- **Graceful Fallback**: System continues operating even if migration partially fails
- **Legacy Support**: Old configuration options remain valid during transition

## Testing Mode

Set `TESTING_MODE=true` in environment to run a single IP check and exit (useful for testing API connectivity).