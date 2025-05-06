# Dockerfile for GitBook MCP Server
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gitbook_mcp.py .

# Expose the port
EXPOSE 5000

# Command to run
ENTRYPOINT ["python", "gitbook_mcp.py"]
CMD ["--help"]