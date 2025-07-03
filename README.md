# Discord IP Monitor Bot

A robust Discord bot that monitors your public IP address and notifies you when it changes. Perfect for home servers, dynamic IP setups, or anyone who wants to keep track of their public IP address.

## Features

### Core Functionality
- 🔄 **Real-time IP monitoring**: Periodically checks your public IP address and notifies when it changes
- 📊 **IP history tracking**: Maintains a history of previous IP addresses with timestamps
- 🛡️ **Multiple API fallbacks**: Uses multiple services to retrieve IP information with retry logic
- ⚡ **Concurrent checks**: Option to check multiple IP services simultaneously for faster results
- 💬 **Rich command interface**: Comprehensive Discord commands for monitoring, configuration, and administration

### Resilience & Fault Tolerance
- 🔧 **Circuit breaker pattern**: Prevents cascading failures with automatic recovery
- 📬 **Async message queue**: Handles Discord API downtime with priority-based message queuing
- 🏥 **Service health monitoring**: 5-level health system with automatic degradation and recovery
- 🔄 **HTTP connection pooling**: Efficient connection reuse with configurable timeouts
- 🔐 **Async rate limiting**: Built-in async-native rate limiting with exponential backoff and jitter

### Storage & Data Management
- 🗃️ **SQLite database**: Reliable data storage with ACID transactions and automatic migration
- 📈 **Performance tracking**: Automatic API performance monitoring and optimization
- 🔄 **Automatic migration**: Seamless upgrade from JSON file storage to SQLite
- 💾 **Data integrity**: Database-level validation and constraint enforcement

### Configuration & Management
- ⚙️ **Runtime configuration**: Change bot settings without restart via Discord commands
- 🌐 **Custom IP APIs**: Add and manage custom IP detection services with performance tracking
- 🔧 **Admin commands**: Comprehensive administration interface for bot management
- 📊 **Health diagnostics**: Real-time monitoring of system health and performance

### Advanced Features
- 🎯 **Message prioritization**: Critical messages processed first during outages
- 🔄 **Automatic recovery**: Self-healing capabilities with exponential backoff
- 📝 **Detailed logging**: Configurable logging levels for troubleshooting
- 🧠 **Smart error handling**: Comprehensive error handling and recovery mechanisms
- 🚀 **Testing mode**: Single-check mode for testing API connectivity
- 🗄️ **Intelligent caching**: Reduces API calls with configurable TTL, smart invalidation, and performance monitoring

## Commands

The bot supports both **modern slash commands** (recommended) and legacy text commands for backwards compatibility.

### User Commands (Slash Commands)
- `/ip` - Manually check the current public IP address
- `/history` - View the history of IP address changes
- `/status` - View bot status, configuration, and system health
- `/help` - Display available commands and their usage

### Admin Commands (Slash Commands)

*All admin commands require administrator permissions in the Discord server.*

#### Bot Management
- `/stop` - Gracefully shut down the bot

#### Configuration Management
- `/config show [field]` - Display current configuration (optionally for a specific field)
- `/config set <field> <value>` - Update a configuration field
- `/config list` - List all configurable fields with descriptions
- `/config save` - Save current configuration to file
- `/config reload` - Reload configuration from file (requires restart)

#### Custom IP API Management
- `/api list` - List all configured IP APIs with performance data
- `/api add <name> <url> [format] [field]` - Add new IP API
- `/api remove <api_id>` - Remove IP API by ID or name
- `/api toggle <api_id> <enable|disable>` - Enable or disable IP API
- `/api test <api_id>` - Test IP API response
- `/api stats` - Show API performance statistics

#### Cache Management
- `/cache show` - Show cache status and statistics
- `/cache clear [namespace]` - Clear cache entries (all or by namespace)

#### Message Queue Management
- `/queue status` - Show message queue status and statistics
- `/queue clear` - Clear all queued messages

### Legacy Text Commands (Backwards Compatibility)

For backwards compatibility, the bot still supports the original text-based commands:

#### User Commands
- `!ip` - Manually check the current public IP address
- `!history` - View the history of IP address changes
- `!status` - View bot status, configuration, and system health
- `!help` - Display available commands

#### Admin Commands
- `!stop` - Gracefully shut down the bot (admin only)
- `!config show` - Display current configuration
- `!config show <field>` - Show specific configuration field
- `!config set <field> <value>` - Update configuration field
- `!config list` - List all configurable fields with descriptions
- `!config save` - Save current configuration to file
- `!config reload` - Reload configuration from file (requires restart)
- `!api list` - List all configured IP APIs with performance data
- `!api add <name> <url> [format] [field]` - Add new IP API
- `!api remove <id>` - Remove IP API
- `!api enable/disable <id>` - Enable/disable IP API
- `!api test <id>` - Test IP API response
- `!api priority <id> <priority>` - Set API priority
- `!api stats` - Show API performance statistics
- `!cache show` - Show cache status and statistics
- `!cache clear [namespace]` - Clear cache entries (all or by namespace)
- `!cache stats` - Show detailed cache statistics
- `!cache cleanup` - Force cleanup of expired entries
- `!cache refresh` - Refresh stale cache entries
- `!queue` - Show message queue status and statistics
- `!queue clear` - Clear all queued messages
- `!queue retry` - Retry all failed messages
- `!queue start` - Start message queue processing
- `!queue stop` - Stop message queue processing

### Command Features

#### Slash Command Benefits
- **Auto-completion**: Discord provides parameter suggestions
- **Parameter validation**: Built-in type checking and validation
- **Better UX**: Modern, intuitive interface
- **Ephemeral responses**: Admin commands respond privately by default
- **Permission integration**: Automatic permission checking

#### Permission System
- **User commands**: Available to all users in the designated channel
- **Admin commands**: Require administrator permissions in the Discord server
- **Ephemeral responses**: Admin slash commands respond privately to prevent clutter

## Installation

### Prerequisites

- Python 3.13 or higher
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

# Core IP monitoring settings
CHECK_INTERVAL=30  # Minutes between automatic IP checks
MAX_RETRIES=3  # Number of retry attempts when IP APIs fail
RETRY_DELAY=5  # Seconds to wait between retries
CONCURRENT_API_CHECKS=true  # Whether to check all APIs simultaneously

# Database and storage settings
DB_FILE=ip_monitor.db  # SQLite database file path
IP_HISTORY_SIZE=10  # Number of historical IPs to keep

# Legacy file settings (for migration only)
IP_FILE=last_ip.json  # Legacy file (migrated to SQLite)
IP_HISTORY_FILE=ip_history.json  # Legacy file (migrated to SQLite)

# Resilience and fault tolerance settings
CIRCUIT_BREAKER_ENABLED=true  # Enable circuit breaker pattern
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3  # Failures before opening circuit
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=120  # Seconds before testing recovery
MESSAGE_QUEUE_ENABLED=true  # Enable async message queuing
MESSAGE_QUEUE_MAX_SIZE=1000  # Maximum queued messages
MESSAGE_QUEUE_MAX_AGE_HOURS=24  # Message expiry time
MESSAGE_QUEUE_BATCH_SIZE=5  # Messages processed per batch
MESSAGE_QUEUE_PROCESS_INTERVAL=1.0  # Seconds between batches

# HTTP connection pooling
CONNECTION_POOL_SIZE=10  # Maximum HTTP connections in pool
CONNECTION_POOL_MAX_KEEPALIVE=5  # Maximum keep-alive connections
CONNECTION_TIMEOUT=10.0  # HTTP connection timeout in seconds
READ_TIMEOUT=30.0  # HTTP read timeout in seconds

# Intelligent caching settings
CACHE_ENABLED=true  # Enable intelligent caching system
CACHE_TTL=300  # Default cache TTL in seconds (5 minutes)
CACHE_MAX_MEMORY_SIZE=1000  # Maximum cache entries in memory
CACHE_STALE_THRESHOLD=0.8  # Threshold for considering entries stale (0.0-1.0)
CACHE_FILE=cache.json  # Cache persistence file
CACHE_CLEANUP_INTERVAL=300  # Seconds between cache cleanup runs

# Rate limiting settings
RATE_LIMIT_PERIOD=300  # Rate limit window in seconds
MAX_CHECKS_PER_PERIOD=10  # Maximum checks allowed in the rate limit window

# Custom IP API settings
CUSTOM_APIS_ENABLED=true  # Enable custom IP detection APIs
API_CONFIG_FILE=ip_apis.json  # Configuration file for custom APIs

# General settings
LOG_LEVEL=INFO  # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
STARTUP_MESSAGE_ENABLED=true  # Whether to send a message when the bot starts
TESTING_MODE=false  # Test mode will check IP once and exit
```

4. Run the bot:
```bash
python main.py
```

## Architecture

The bot is built with a modular architecture designed for resilience, scalability, and maintainability:

### Core Components

- **Entry Point** (`main.py`): Loads configuration and starts the bot
- **Core Bot** (`ip_monitor/bot.py`): Main Discord bot class with event handlers and scheduled tasks
- **Configuration** (`ip_monitor/config.py`): Environment-based configuration management using dataclasses
- **IP Service** (`ip_monitor/ip_service.py`): Handles IP retrieval from multiple APIs with fallback and retry logic
- **Storage** (`ip_monitor/storage.py`): SQLite database storage for IP history and current IP with data integrity

### Command System

- **User Commands** (`ip_monitor/commands/ip_commands.py`): User-accessible commands for IP monitoring
- **Admin Commands** (`ip_monitor/commands/admin_commands.py`): Administrator-only commands for bot management

### Resilience & Fault Tolerance

- **Discord Rate Limiter** (`ip_monitor/utils/discord_rate_limiter.py`): Handles Discord API rate limits with exponential backoff
- **Async Rate Limiter** (`ip_monitor/utils/async_rate_limiter.py`): Async-native rate limiting for IP API calls with configurable windows and token bucket algorithm
- **Circuit Breaker** (`ip_monitor/utils/circuit_breaker.py`): Prevents cascading failures with 3-state pattern (CLOSED/OPEN/HALF_OPEN)
- **Service Health Monitor** (`ip_monitor/utils/service_health.py`): Tracks system health with 5-level degradation and automatic fallback
- **Message Queue** (`ip_monitor/utils/message_queue.py`): Async message queuing with persistence and priority handling
- **HTTP Connection Pooling**: Efficient connection reuse with configurable pool sizes and timeout management

### Data Flow

1. **IP Monitoring**: Scheduled tasks check IP addresses using multiple APIs with circuit breaker protection
2. **Storage**: Changes are stored in SQLite database with automatic migration from legacy JSON files
3. **Notifications**: Discord notifications are queued with priority handling and retry logic
4. **Health Monitoring**: System health is continuously monitored with automatic degradation responses
5. **Configuration**: Runtime configuration changes are applied immediately and persisted to disk

## Runtime Configuration Management

The bot supports dynamic configuration changes through Discord commands without requiring a restart for most settings. Configuration changes are automatically saved to `bot_config.json` and persist across bot restarts.

### Configurable Settings

#### IP Monitoring
- `check_interval` (1-1440 minutes): IP check interval ⚠️ *Restart required*
- `max_retries` (1-10): Maximum retry attempts for IP checks
- `retry_delay` (1-300 seconds): Delay between retries
- `concurrent_api_checks` (true/false): Enable concurrent API checks

#### Circuit Breaker
- `circuit_breaker_enabled` (true/false): Enable circuit breaker pattern
- `circuit_breaker_failure_threshold` (1-20): Failures before opening circuit
- `circuit_breaker_recovery_timeout` (10-3600 seconds): Recovery timeout

#### Rate Limiting
- `rate_limit_period` (60-3600 seconds): Rate limit period
- `max_checks_per_period` (1-100): Maximum checks per period

#### Storage
- `ip_history_size` (1-100): Maximum IP history entries

#### Message Queue
- `message_queue_enabled` (true/false): Enable async message queue
- `message_queue_max_size` (10-10000): Maximum messages in queue
- `message_queue_max_age_hours` (1-168 hours): Maximum message age
- `message_queue_batch_size` (1-50): Messages processed per batch
- `message_queue_process_interval` (0.1-60.0 seconds): Processing interval

#### HTTP Connection Pooling
- `connection_pool_size` (1-100): Maximum HTTP connections in pool
- `connection_pool_max_keepalive` (1-50): Maximum keep-alive connections
- `connection_timeout` (1.0-60.0 seconds): HTTP connection timeout
- `read_timeout` (1.0-300.0 seconds): HTTP read timeout

#### Other Settings
- `startup_message_enabled` (true/false): Enable startup notifications
- `custom_apis_enabled` (true/false): Enable custom IP detection APIs

### Usage Examples

```
!config show                           # Show all configuration
!config show check_interval            # Show specific field
!config set max_retries 5              # Update retry count
!config set circuit_breaker_enabled false  # Disable circuit breaker
!config list                           # List all configurable fields
!config save                           # Save current config to file
!config reload                         # Reload from file (requires restart)
```

## Custom IP Detection APIs

The bot supports adding custom IP detection services with automatic performance tracking, failover, and optimization. This allows you to use your preferred IP detection services or add redundancy.

### Supported API Response Formats

#### JSON Format
APIs that return IP addresses in JSON format:
```json
{"ip": "192.168.1.1"}
{"origin": "192.168.1.1"}
{"address": "192.168.1.1"}
```

#### Text Format
APIs that return plain text IP addresses:
```
192.168.1.1
```

#### Auto-Detection
The bot can automatically detect the response format and extract the IP address.

### API Management

#### Adding APIs
```
!api add "My JSON API" "https://api.example.com/ip" json ip
!api add "Simple Text API" "https://text.example.com/" text
!api add "Auto-detect API" "https://auto.example.com/"
```

#### Managing APIs
```
!api list                              # Show all APIs with performance data
!api enable my_json_api                # Enable specific API
!api disable my_json_api               # Disable specific API
!api priority my_json_api 1            # Set highest priority (1-10)
!api test my_json_api                  # Test API response
!api remove my_json_api                # Remove API permanently
!api stats                             # Show performance rankings
```

### Performance Tracking

The system automatically tracks and optimizes API usage based on:

- **Success Rate**: Percentage of successful requests over time
- **Response Time**: Average response time with weighted moving average
- **Performance Score**: Composite score considering success rate, speed, and recent failures
- **Recent Activity**: Last success/failure timestamps and error tracking

APIs are automatically ranked by performance and used in optimal order, with failed APIs being temporarily deprioritized.

### Default APIs

The bot includes these default APIs, automatically configured on first run:
- IPify JSON API (https://api.ipify.org?format=json)
- IPify Text API (https://api.ipify.org)
- ifconfig.me (https://ifconfig.me/ip)
- icanhazip.com (https://icanhazip.com)
- AWS CheckIP (https://checkip.amazonaws.com)

### Failover Behavior

1. APIs are tried in priority order (1-10), then by performance score
2. Failed APIs are automatically deprioritized for a cooldown period
3. System falls back to built-in APIs if all custom APIs fail
4. Performance data persists across bot restarts
5. Automatic retry with exponential backoff for temporary failures

## Intelligent Cache Management

The bot includes a sophisticated caching system that significantly reduces API calls while maintaining accuracy and performance. The cache operates with configurable TTL (Time To Live) values and intelligent invalidation strategies.

### Cache Features

- **Multi-Type Caching**: Different cache types for IP results, API responses, DNS lookups, and performance data
- **Configurable TTL**: Default 5-minute TTL for IP results, customizable per cache type
- **Smart Invalidation**: Automatic expiration and manual cache clearing by namespace
- **Stale Detection**: Proactive refresh of entries approaching expiration
- **Performance Monitoring**: Hit rate tracking, memory usage metrics, and access statistics
- **Persistent Storage**: Cache survives bot restarts with JSON file persistence
- **Thread-Safe Operations**: Safe concurrent access with proper locking

### Cache Configuration

```bash
# Cache settings in .env file
CACHE_ENABLED=true                    # Enable intelligent caching
CACHE_TTL=300                        # Default TTL (5 minutes)
CACHE_MAX_MEMORY_SIZE=1000           # Maximum cache entries
CACHE_STALE_THRESHOLD=0.8            # When entries are considered stale
CACHE_FILE=cache.json                # Persistence file
CACHE_CLEANUP_INTERVAL=300           # Background cleanup interval
```

### Cache Management Commands

```bash
!cache show                          # Show cache status and basic statistics
!cache clear                         # Clear all cache entries
!cache clear ip_check                # Clear specific namespace
!cache stats                         # Detailed performance metrics
!cache cleanup                       # Force cleanup of expired entries
!cache refresh                       # Refresh stale cache entries
```

### Cache Types and TTL

- **IP Results**: 5 minutes (configurable) - Cached IP addresses from API calls
- **API Responses**: 2.5 minutes - Individual API endpoint responses
- **DNS Lookups**: 1 hour - Hostname resolution results
- **Performance Data**: 10 minutes - API performance metrics

### Performance Benefits

The caching system provides several performance improvements:

1. **Reduced API Calls**: Up to 80% reduction in external API requests during normal operation
2. **Faster Responses**: Instant responses for cached IP checks (sub-millisecond vs. network latency)
3. **Lower Bandwidth Usage**: Fewer HTTP requests reduce network overhead
4. **Improved Reliability**: Cached results available during API outages
5. **Better Rate Limit Handling**: Reduced risk of hitting API rate limits

### Cache Statistics

The system tracks comprehensive metrics accessible via `!cache stats`:

- **Hit Rate**: Percentage of requests served from cache
- **Memory Usage**: Current cache size and memory consumption
- **Entry Types**: Breakdown of cached data by type
- **Operations**: Counts of hits, misses, evictions, and refreshes
- **Efficiency Rating**: Automatic performance assessment

## Async Rate Limiting System

The bot includes an async-native rate limiting system that provides efficient, non-blocking rate limiting for IP API calls and user commands. This system replaces traditional thread-based rate limiting with async/await patterns for better performance.

### Features

#### AsyncRateLimiter
- **Async-Native Design**: Uses `asyncio.Lock()` instead of threading locks
- **Better Performance**: Eliminates thread switching overhead in async contexts
- **Memory Management**: Automatic cleanup of expired call timestamps
- **Detailed Monitoring**: Comprehensive status reporting and utilization metrics

#### Core Methods
```python
# Check if rate limited
is_limited, wait_time = await rate_limiter.is_limited()

# Acquire a slot, waiting if necessary
await rate_limiter.acquire()

# Try to acquire without waiting
if await rate_limiter.try_acquire():
    # Proceed with operation
    pass

# Get detailed status
status = await rate_limiter.get_status()
```

### Token Bucket Algorithm

The system also includes `TokenBucketRateLimiter` for advanced use cases:
- **Burst Traffic Support**: Allows burst traffic up to bucket capacity
- **Smooth Rate Limiting**: Maintains overall rate while allowing bursts
- **Configurable Rates**: Supports fractional tokens per second

```python
# Initialize with 2 tokens/second, capacity 10
bucket = TokenBucketRateLimiter(rate=2.0, capacity=10)

# Acquire multiple tokens for larger operations
await bucket.acquire(tokens=3)
```

### Configuration

Rate limiting is configured via environment variables:

```bash
# Rate limiting settings
RATE_LIMIT_PERIOD=300              # Rate limit window in seconds (5 minutes)
MAX_CHECKS_PER_PERIOD=10           # Maximum IP checks allowed in window
```

### Integration

The async rate limiter is integrated throughout the bot:

- **IP Commands**: Manual IP checks via `!ip` command respect rate limits
- **Status Display**: Rate limit status shown in `!status` command
- **Automatic Checks**: Scheduled IP monitoring respects configured limits
- **Admin Monitoring**: Rate limit information available in diagnostics

### Benefits Over Threading

1. **No Thread Blocking**: All operations are async and non-blocking
2. **Better Performance**: Eliminates context switching between threads
3. **Cleaner Integration**: Works naturally with the async bot architecture
4. **Enhanced Monitoring**: More detailed metrics and status reporting
5. **Memory Efficiency**: Automatic cleanup prevents memory leaks

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

### Data Storage
- The bot stores IP addresses in an SQLite database with proper file permissions
- Database files should be readable only by the bot user account
- Legacy JSON files are automatically migrated and can be safely removed after migration
- Configuration files (`bot_config.json`, `ip_apis.json`) contain sensitive settings and should be protected

### Authentication & Authorization
- The bot token in the `.env` file should be kept secure and never committed to version control
- Admin commands are restricted to users with administrator permissions in the Discord server
- Runtime configuration changes are logged for audit purposes

### Network Security
- All HTTP requests use connection pooling with configurable timeouts
- Custom IP APIs should use HTTPS endpoints when possible
- Circuit breaker prevents excessive requests to failing services
- Async rate limiting protects against API abuse without blocking threads

### System Security
- Consider running the bot with minimal system permissions
- Use a dedicated user account for the bot process
- Implement proper log rotation to prevent disk space issues
- Regular security updates for Python dependencies are recommended

### Discord Bot Security
- Use the principle of least privilege for Discord bot permissions
- Monitor bot activity through Discord's audit logs
- Message queue persistence files should be protected from unauthorized access

## Troubleshooting

### Common Issues

#### Bot Not Starting
- Check the `bot.log` file for detailed error messages
- Verify the `DISCORD_BOT_TOKEN` in your `.env` file is correct
- Ensure the bot has the correct permissions in the Discord channel
- Check that the bot has write access to its directory for database and config files

#### IP Check Failures
- Use `!status` command to check system health and API performance
- Check `!api stats` to see which APIs are failing
- Test individual APIs with `!api test <api_name>`
- If all IP checks fail, verify your internet connection
- Try disabling `CONCURRENT_API_CHECKS` if experiencing timeout issues

#### Database Issues
- Check file permissions on the SQLite database file
- Look for migration errors in the log file during first startup
- Ensure sufficient disk space for database operations
- Use `!status` to check database connectivity

#### Performance Problems
- Monitor system health with `!status` command
- Check message queue status with `!queue` command
- Review circuit breaker status in the health report
- Check rate limiting status in `!status` output (utilization percentage)
- Adjust connection pool settings if experiencing timeouts
- Review cache performance with `!cache stats` for optimization opportunities

### Diagnostic Commands

#### System Health
```
!status                                # Overall system health and performance
!queue                                 # Message queue status and statistics
!api stats                             # API performance rankings
!cache stats                           # Detailed cache performance metrics
```

#### Configuration Issues
```
!config show                          # Current configuration
!config list                          # Available configuration options
!api list                             # All IP detection APIs and their status
```

#### Recovery Commands
```
!queue clear                          # Clear stuck messages
!queue retry                          # Retry failed messages
!api test <api_name>                  # Test specific API
!cache clear                          # Clear cache if causing issues
!cache cleanup                        # Clean up expired cache entries
```

### Log Files

The bot generates detailed logs in `bot.log` with different levels:
- **ERROR**: Critical issues requiring immediate attention
- **WARNING**: Issues that may affect functionality
- **INFO**: General operational information
- **DEBUG**: Detailed debugging information (enable with `LOG_LEVEL=DEBUG`)

### Health System States

The bot automatically adjusts behavior based on system health:
- **NORMAL**: All systems operational
- **MINOR**: Slight degradation, increased monitoring
- **MODERATE**: Reduced functionality, longer intervals
- **SEVERE**: Limited operations, minimal Discord usage
- **CRITICAL**: Emergency mode, basic functionality only

### Getting Help

If you encounter persistent issues:
1. Check the bot logs for error messages
2. Use diagnostic commands to identify the problem
3. Review the configuration settings
4. Ensure all dependencies are properly installed
5. Consider enabling debug logging for detailed troubleshooting

## Acknowledgments

- [discord.py](https://github.com/Rapptz/discord.py) for the Discord API wrapper
- Public IP APIs used in this project:
  - ipify.org
  - ifconfig.me
  - icanhazip.com
  - checkip.amazonaws.com
