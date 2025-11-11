FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock* ./

# Install uv
RUN pip install uv

# Install dependencies
RUN uv sync

# Copy application code
COPY . .

# Make bin scripts executable
RUN chmod +x bin/*

# Expose port
EXPOSE 8080

# Default command (can be overridden in docker-compose)
CMD ["./bin/run"]
