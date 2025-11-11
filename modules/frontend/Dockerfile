FROM oven/bun:1

WORKDIR /app

# Copy dependency files
COPY package.json bun.lock* ./

# Install dependencies
RUN bun install

# Copy application code
COPY . .

# Make bin scripts executable
RUN chmod +x bin/*

# Expose port
EXPOSE 51732

# Default command (can be overridden in docker-compose)
CMD ["bun", "run", "dev", "--host", "0.0.0.0", "--port", "51732"]
