# GitBook Model Context Provider (MCP) Server

This Python-based MCP server creates a bridge between your codebase and GitBook documentation, providing real-time context and code insights to enhance your technical documentation.

## Features

- **Code Indexing**: Automatically indexes your Python codebase, extracting functions, classes, modules, docstrings, and relationships
- **Documentation Parsing**: Analyzes your markdown documentation files to find code references
- **API Endpoints**: Provides RESTful endpoints for searching and retrieving code context
- **GitBook Integration**: Syncs code information to GitBook via API
- **Real-time Updates**: Periodically re-indexes your codebase to keep information current
- **Relationship Tracking**: Maps dependencies between code entities
- **Webhook Support**: Processes GitBook webhooks for interactive documentation

## Installation

1. Clone this repository or save the MCP server code to your project
2. Install required dependencies:

```bash
pip install flask flask-cors requests markdown beautifulsoup4
```

## Usage

### Basic Usage

Start the MCP server by pointing it to your codebase:

```bash
python gitbook_mcp.py --code-path /path/to/your/codebase
```

### Including Documentation

To also index documentation files:

```bash
python gitbook_mcp.py --code-path /path/to/your/codebase --docs-path /path/to/your/docs
```

### Full Configuration

```bash
python gitbook_mcp.py \
  --code-path /path/to/your/codebase \
  --docs-path /path/to/your/docs \
  --port 5000 \
  --gitbook-space your-gitbook-space-id \
  --gitbook-token your-gitbook-api-token
```

## API Endpoints

### Health Check
```
GET /health
```
Returns server status and version information.

### Search Code and Documentation
```
GET /search?q=query&type=entity_type
```
Search for code entities and documentation matching the query.

Parameters:
- `q`: Search query (required)
- `type`: Filter by entity type (optional) - "function", "class", or "module"

### Get Entity Details
```
GET /entity/{entity_name}
```
Get detailed information about a specific code entity and its relationships.

### Sync to GitBook
```
POST /sync
```
Manually trigger a sync of code information to GitBook.

### GitBook Webhook
```
POST /webhook
```
Endpoint for GitBook webhooks to receive events.

## Integration with GitBook

### Setup in GitBook

1. Go to your GitBook space settings
2. Navigate to Integrations > Custom Integration
3. Add a new integration with the following settings:
   - Name: Code Context Provider
   - Webhook URL: `http://your-server:5000/webhook`
   - Events: Select page updates and comments
4. Generate an API token in GitBook settings
5. Start your MCP server with the GitBook space ID and token

### Using in Documentation

Once set up, you can:

1. Reference code entities in your GitBook documentation
2. Insert live code snippets with automatic updates
3. Add "View in Code" links that open the source file
4. Enable contextual comments with code suggestions

## Advanced Configuration

Create a configuration file `mcp_config.json`:

```json
{
  "code_path": "/path/to/your/codebase",
  "docs_path": "/path/to/your/docs",
  "port": 5000,
  "index_interval": 300,
  "exclude_patterns": ["__pycache__", "*.pyc", ".*", "venv", "env"],
  "gitbook": {
    "space_id": "your-gitbook-space-id",
    "api_token": "your-gitbook-api-token",
    "sync_modules": true,
    "sync_classes": true,
    "sync_functions": true
  }
}
```

Then start the server using:

```bash
python gitbook_mcp.py --config mcp_config.json
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.