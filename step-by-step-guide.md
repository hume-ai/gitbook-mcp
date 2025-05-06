# GitBook MCP Server: Step-by-Step Usage Guide

This guide walks you through the process of setting up and using the GitBook Model Context Provider (MCP) server with your projects.

## Step 1: Set Up Your Environment

First, create a dedicated environment for your MCP server:

```bash
# Create and activate a virtual environment
python -m venv mcp-env
source mcp-env/bin/activate  # On Windows: mcp-env\Scripts\activate

# Install required dependencies
pip install flask flask-cors requests markdown beautifulsoup4
```

## Step 2: Save the MCP Server Code

1. Save the MCP server code to a file named `gitbook_mcp.py` in your project directory
2. Make the file executable:
   ```bash
   chmod +x gitbook_mcp.py
   ```

## Step 3: Basic Server Setup

Start with a basic setup to index your codebase:

```bash
python gitbook_mcp.py --code-path /path/to/your/codebase --port 5000
```

This will:
- Index all Python files in your codebase
- Start a server on port 5000
- Provide API endpoints for accessing code information

## Step 4: Verify the Server is Running

Open your browser and navigate to:
```
http://localhost:5000/health
```

You should see a JSON response:
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

## Step 5: Test the Search API

Let's search for a code entity in your codebase:

```
http://localhost:5000/search?q=example
```

This will return JSON results with matching code entities:
```json
{
  "code_results": [
    {
      "name": "example_function",
      "filepath": "path/to/file.py",
      "line_start": 10,
      "line_end": 20,
      "docstring": "Example function documentation",
      "code_snippet": "def example_function():\n    ...",
      "entity_type": "function"
    }
  ],
  "doc_results": []
}
```

## Step 6: Include Documentation

Restart the server with your documentation path:

```bash
python gitbook_mcp.py --code-path /path/to/your/codebase --docs-path /path/to/your/docs --port 5000
```

Now the server will:
- Index both code and documentation
- Find relationships between docs and code
- Return documentation matches in search results

## Step 7: Test the Combined Search

Search again with documentation included:

```
http://localhost:5000/search?q=example
```

Now your results will include both code and documentation matches:
```json
{
  "code_results": [...],
  "doc_results": [
    {
      "path": "getting-started.md",
      "title": "Getting Started",
      "matches": [
        {
          "line": 15,
          "context": "Here is an example of using our API..."
        }
      ]
    }
  ]
}
```

## Step 8: Explore Entity Details

Get detailed information about a specific code entity:

```
http://localhost:5000/entity/example_module
```

This returns comprehensive information including:
```json
{
  "entity": {
    "name": "example_module",
    "filepath": "example_module.py",
    "docstring": "This module provides example functionality",
    "functions": ["function1", "function2"],
    "classes": ["ExampleClass"],
    "entity_type": "module"
  },
  "relationships": {
    "imports": ["other_module"],
    "imported_by": ["main_module"],
    "uses": ["utility_function"],
    "used_by": ["application"]
  }
}
```

## Step 9: GitBook Integration Setup

### 9.1. Get GitBook API Credentials

1. Log in to your GitBook account
2. Go to Settings > Integrations
3. Create a new API token with appropriate permissions
4. Note your GitBook Space ID (found in the URL of your space)

### 9.2. Start Server with GitBook Integration

```bash
python gitbook_mcp.py \
  --code-path /path/to/your/codebase \
  --docs-path /path/to/your/docs \
  --port 5000 \
  --gitbook-space your-space-id \
  --gitbook-token your-api-token
```

### 9.3. Configure GitBook Webhooks

1. In GitBook, go to Space Settings > Integrations
2. Add a Custom Integration
3. Set the Webhook URL to `http://your-server:5000/webhook`
4. Select events: Page Updates, Comments, etc.
5. Save the integration

## Step 10: Manually Sync Code to GitBook

Trigger a manual sync of code information to GitBook:

```bash
curl -X POST http://localhost:5000/sync
```

This will:
- Format code entity information for GitBook
- Send data to the GitBook API
- Update your documentation with code context

## Step 11: Run as a Background Service

For production use, set up the server as a background service:

### 11.1. Create a systemd service (Linux)

Create a file at `/etc/systemd/system/gitbook-mcp.service`:

```ini
[Unit]
Description=GitBook Model Context Provider
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/mcp
ExecStart=/path/to/mcp-env/bin/python gitbook_mcp.py --config config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 11.2. Create a configuration file

Create `config.json` in your MCP directory:

```json
{
  "code_path": "/path/to/your/codebase",
  "docs_path": "/path/to/your/docs",
  "port": 5000,
  "gitbook_space_id": "your-space-id",
  "gitbook_token": "your-api-token"
}
```

### 11.3. Start the service

```bash
sudo systemctl enable gitbook-mcp
sudo systemctl start gitbook-mcp
```

## Step 12: Using in GitBook Documents

Now that everything is set up, you can use the MCP server to enhance your GitBook documentation:

### 12.1. Add Code References

In your GitBook pages, reference code entities using the standard markdown code format:
```markdown
The `example_function()` handles data processing.
```

### 12.2. Add Live Code Snippets

Create a special code block that will be enhanced with live code:
```markdown
{% code title="example_module.py" %}
```python
# This will be replaced with the actual code
def example_function():
    pass
```
{% endcode %}
```

### 12.3. Use the GitBook UI Integration

If you've set up the integration correctly, you'll see:
- "View in Code" buttons next to code references
- Tooltips showing documentation when hovering over function names
- Auto-completion suggestions when writing code examples

## Step 13: Advanced Usage

### 13.1. Custom Plugins

Extend the MCP server with custom plugins by creating a Python module in a `plugins` directory:

```python
# plugins/my_plugin.py
def register(server):
    @server.app.route('/custom-endpoint')
    def custom_endpoint():
        return {"status": "ok", "custom": True}
```

### 13.2. Language Support Extensions

The default implementation focuses on Python, but you can extend it for other languages:

1. Create a new indexer class (e.g., `JavaScriptIndexer`)
2. Implement the language-specific parsing logic
3. Register it with the main server

### 13.3. CI/CD Integration

Automate the documentation synchronization process by adding to your CI/CD pipeline:

```yaml
# Example GitHub Action
name: Sync Code Context
on:
  push:
    branches: [main]
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install requests
      - name: Trigger sync
        run: curl -X POST http://your-mcp-server/sync
```

## Troubleshooting

### Server Won't Start

Check:
- Python version (requires 3.8+)
- All dependencies are installed
- Correct file paths
- Port availability (try a different port)

### Indexing Issues

If code isn't indexing properly:
- Ensure files have correct Python syntax
- Check excluded patterns
- Verify file permissions
- Monitor server logs for errors

### GitBook Integration Problems

If GitBook integration isn't working:
- Verify API token permissions
- Check network connectivity
- Ensure correct Space ID
- Review server logs for API response errors

## Next Steps

- Add user authentication for secure API access
- Implement more advanced code analysis features
- Create a dashboard UI for monitoring
- Add support for additional programming languages
- Develop GitBook-specific plugins for enhanced integration