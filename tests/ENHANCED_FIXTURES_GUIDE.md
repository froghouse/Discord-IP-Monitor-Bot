# Enhanced Test Fixtures Guide

This guide explains the comprehensive test fixtures added to the Discord IP Monitor Bot testing infrastructure. These fixtures provide robust, isolated, and repeatable test environments for all components of the system.

## Table of Contents

1. [Database Test Fixtures](#database-test-fixtures)
2. [HTTP Mock Server Fixtures](#http-mock-server-fixtures)
3. [Discord Bot Mock Fixtures](#discord-bot-mock-fixtures)
4. [Usage Examples](#usage-examples)
5. [Best Practices](#best-practices)

## Database Test Fixtures

### Overview

The database fixtures provide isolated SQLite database environments for testing storage operations without affecting production data.

### Available Fixtures

#### `temp_db_path`
- **Type**: Path string
- **Description**: Creates a temporary SQLite database file path that is automatically cleaned up after tests
- **Usage**: For creating custom SQLiteIPStorage instances

```python
def test_custom_database(temp_db_path):
    storage = SQLiteIPStorage(temp_db_path, history_size=5)
    # Your test code here
```

#### `temp_db_connection`
- **Type**: sqlite3.Connection
- **Description**: Pre-configured SQLite connection with the full database schema
- **Usage**: For direct database operations and schema testing

```python
def test_database_schema(temp_db_connection):
    cursor = temp_db_connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert 'current_ip' in tables
    assert 'ip_history' in tables
```

#### `sqlite_storage`
- **Type**: SQLiteIPStorage instance
- **Description**: Clean SQLiteIPStorage instance with temporary database
- **Usage**: For testing storage operations from scratch

```python
def test_ip_storage_operations(sqlite_storage):
    assert sqlite_storage.save_current_ip("192.168.1.1") is True
    assert sqlite_storage.load_last_ip() == "192.168.1.1"
```

#### `sqlite_storage_with_data`
- **Type**: SQLiteIPStorage instance with test data
- **Description**: Pre-populated SQLiteIPStorage with sample IP history
- **Usage**: For testing operations on existing data

```python
def test_ip_history_operations(sqlite_storage_with_data):
    history = sqlite_storage_with_data.load_ip_history()
    assert len(history) == 3
    assert history[0]["ip"] == "192.168.1.1"
```

### Test Data Structure

The `sqlite_storage_with_data` fixture includes:
- **Current IP**: `192.168.1.3`
- **History**: 3 entries with IPs `192.168.1.1`, `192.168.1.2`, `192.168.1.3`
- **Timestamps**: `2023-01-01T12:00:00Z`, `2023-01-01T13:00:00Z`, `2023-01-01T14:00:00Z`

## HTTP Mock Server Fixtures

### Overview

These fixtures provide real HTTP servers for testing API interactions without depending on external services.

### Available Fixtures

#### `mock_ip_api_server`
- **Type**: Dictionary with server information
- **Description**: Async HTTP server with multiple endpoints simulating different IP APIs
- **Usage**: For testing HTTP client behavior and API integration

```python
@pytest.mark.asyncio
async def test_api_client(mock_ip_api_server):
    import httpx
    
    json_url = mock_ip_api_server["endpoints"]["json"]
    async with httpx.AsyncClient() as client:
        response = await client.get(json_url)
        assert response.status_code == 200
        assert response.json()["ip"] == "203.0.113.1"
```

#### Server Endpoints

| Endpoint | Response Type | Response | Description |
|----------|---------------|----------|-------------|
| `/json` | JSON | `{"ip": "203.0.113.1"}` | Standard JSON API response |
| `/text` | Text | `203.0.113.1` | Plain text IP response |
| `/custom` | JSON | `{"origin": "203.0.113.1"}` | Custom field name |
| `/slow` | JSON | `{"ip": "203.0.113.1"}` | 2-second delay for timeout testing |
| `/error` | Error | HTTP 500 | Server error simulation |

#### `mock_httpx_client`
- **Type**: Mock httpx.AsyncClient
- **Description**: Pre-configured mock HTTP client with default responses
- **Usage**: For unit testing without actual HTTP calls

```python
def test_with_mock_client(mock_httpx_client):
    # Client is already configured with default responses
    response = mock_httpx_client.get.return_value
    assert response.status_code == 200
    assert response.text == "203.0.113.1"
```

#### `mock_httpx_responses`
- **Type**: MockResponse factory class
- **Description**: Configurable mock HTTP responses
- **Usage**: For creating custom response scenarios

```python
def test_custom_responses(mock_httpx_responses):
    # Create custom responses
    success_response = mock_httpx_responses(200, "192.168.1.1", {"ip": "192.168.1.1"})
    error_response = mock_httpx_responses(404, "Not Found")
    
    assert success_response.status_code == 200
    assert error_response.status_code == 404
```

## Discord Bot Mock Fixtures

### Overview

Comprehensive Discord.py mocking infrastructure for testing bot interactions without connecting to Discord.

### Available Fixtures

#### `mock_discord_client`
- **Type**: Enhanced AsyncMock Discord client
- **Description**: Full Discord client mock with user, guild, and channel support
- **Usage**: For testing bot-level operations

```python
def test_discord_bot(mock_discord_client):
    # Bot user information
    assert mock_discord_client.user.name == "TestBot"
    assert mock_discord_client.user.id == 123456789
    
    # Connection status
    assert mock_discord_client.is_ready() is True
    assert mock_discord_client.latency == 0.1
    
    # Guild and channel access
    guild = mock_discord_client.get_guild(987654321)
    channel = mock_discord_client.get_channel(12345)
```

#### `mock_discord_interaction`
- **Type**: AsyncMock Discord interaction
- **Description**: Slash command interaction mock with response methods
- **Usage**: For testing slash command handlers

```python
@pytest.mark.asyncio
async def test_slash_command(mock_discord_interaction):
    # User has admin permissions
    assert mock_discord_interaction.user.guild_permissions.administrator is True
    
    # Send response
    await mock_discord_interaction.response.send_message("Test response")
    mock_discord_interaction.response.send_message.assert_called_once()
```

#### `mock_discord_cog`
- **Type**: Mock Discord cog
- **Description**: Command cog mock for testing command organization
- **Usage**: For testing cog-based command structure

```python
def test_cog_functionality(mock_discord_cog):
    assert mock_discord_cog.qualified_name == "TestCog"
    assert mock_discord_cog.description == "Test cog for testing"
```

#### Message Fixtures

- **`mock_message`**: Basic message mock
- **`mock_admin_message`**: Message with administrator permissions
- **`mock_non_admin_message`**: Message without administrator permissions

```python
def test_permission_checking(mock_admin_message, mock_non_admin_message):
    # Admin user
    assert mock_admin_message.author.guild_permissions.administrator is True
    
    # Regular user
    assert mock_non_admin_message.author.guild_permissions.administrator is False
```

### Discord Mock Properties

#### User Properties
- `id`: 123456789
- `name`: "TestBot"
- `discriminator`: "0001"
- `mention`: "<@123456789>"

#### Guild Properties
- `id`: 987654321
- `name`: "Test Guild"
- `member_count`: 100

#### Channel Properties
- `id`: 12345
- `name`: "test-channel"
- `guild`: Associated guild object

## Usage Examples

### Basic Database Testing

```python
def test_ip_storage_basic(sqlite_storage):
    # Test saving IP
    test_ip = "203.0.113.1"
    assert sqlite_storage.save_current_ip(test_ip) is True
    
    # Test loading IP
    loaded_ip = sqlite_storage.load_last_ip()
    assert loaded_ip == test_ip
    
    # Test IP validation
    assert sqlite_storage.is_valid_ip("192.168.1.1") is True
    assert sqlite_storage.is_valid_ip("invalid") is False
```

### HTTP API Testing

```python
@pytest.mark.asyncio
async def test_api_integration(mock_ip_api_server):
    import httpx
    
    base_url = mock_ip_api_server["base_url"]
    
    async with httpx.AsyncClient() as client:
        # Test JSON endpoint
        response = await client.get(f"{base_url}/json")
        assert response.status_code == 200
        assert response.json()["ip"] == "203.0.113.1"
        
        # Test error handling
        response = await client.get(f"{base_url}/error")
        assert response.status_code == 500
```

### Discord Bot Testing

```python
@pytest.mark.asyncio
async def test_command_handling(mock_admin_message):
    # Simulate command processing
    command_content = mock_admin_message.content
    
    # Process command (your logic here)
    response = f"Processed: {command_content}"
    
    # Send response
    await mock_admin_message.channel.send(response)
    
    # Verify response was sent
    mock_admin_message.channel.send.assert_called_once_with(response)
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_full_integration(
    mock_ip_api_server,
    sqlite_storage,
    mock_discord_client
):
    # Get IP from mock server
    import httpx
    json_url = mock_ip_api_server["endpoints"]["json"]
    
    async with httpx.AsyncClient() as client:
        response = await client.get(json_url)
        ip = response.json()["ip"]
    
    # Save to database
    assert sqlite_storage.save_current_ip(ip) is True
    
    # Send Discord notification
    channel = mock_discord_client.get_channel(12345)
    await channel.send(f"IP updated to: {ip}")
    
    # Verify everything worked
    assert sqlite_storage.load_last_ip() == ip
    channel.send.assert_called_once_with(f"IP updated to: {ip}")
```

## Best Practices

### 1. Use Appropriate Fixtures

- **Database operations**: Use `sqlite_storage` or `sqlite_storage_with_data`
- **HTTP testing**: Use `mock_ip_api_server` for integration, `mock_httpx_client` for unit tests
- **Discord testing**: Use `mock_discord_client` for bot-level, `mock_discord_interaction` for slash commands

### 2. Test Isolation

Each fixture creates isolated test environments:
- Database fixtures use temporary files
- HTTP server fixtures use random ports
- Discord mocks are independent instances

### 3. Async Testing

Use `@pytest.mark.asyncio` for async fixtures:

```python
@pytest.mark.asyncio
async def test_async_operation(mock_ip_api_server):
    # Your async test code here
```

### 4. Error Testing

Test error conditions using the provided error endpoints:

```python
@pytest.mark.asyncio
async def test_error_handling(mock_ip_api_server):
    import httpx
    
    error_url = mock_ip_api_server["endpoints"]["error"]
    
    async with httpx.AsyncClient() as client:
        response = await client.get(error_url)
        assert response.status_code == 500
```

### 5. Performance Testing

Use the slow endpoint for timeout testing:

```python
@pytest.mark.asyncio
async def test_timeout_handling(mock_ip_api_server):
    import httpx
    
    slow_url = mock_ip_api_server["endpoints"]["slow"]
    
    async with httpx.AsyncClient(timeout=1.0) as client:
        with pytest.raises(httpx.TimeoutException):
            await client.get(slow_url)
```

### 6. Cleanup

Fixtures handle cleanup automatically:
- Database files are removed after tests
- HTTP servers are shut down
- Mock objects are reset between tests

### 7. Configuration

Use the `mock_config` fixture for consistent test configuration:

```python
def test_with_config(mock_config, sqlite_storage):
    assert mock_config.check_interval == 300
    assert sqlite_storage.history_size == 10
```

## Troubleshooting

### Common Issues

1. **Database locked errors**: Ensure proper cleanup of database connections
2. **HTTP server port conflicts**: Fixtures use random ports to avoid conflicts
3. **Async/await errors**: Use `@pytest.mark.asyncio` for async tests
4. **Mock not called**: Verify the mock is properly configured and called

### Debug Tips

1. Use `pytest -v` for verbose output
2. Check fixture scope if sharing data between tests
3. Use `pytest --tb=short` for concise tracebacks
4. Enable logging to see fixture initialization

## Contributing

When adding new fixtures:

1. Follow the existing naming convention
2. Include comprehensive docstrings
3. Add cleanup logic for resources
4. Create usage examples
5. Update this documentation

## Related Files

- `tests/conftest.py`: Main fixture definitions
- `tests/example_enhanced_fixtures_usage.py`: Comprehensive usage examples
- `tests/unit/`: Unit test implementations using these fixtures
- `tests/integration/`: Integration test implementations