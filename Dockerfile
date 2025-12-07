# Playwright Proxy MCP Server Dockerfile
# Multi-stage build with manual file filtering for production

# Build arguments with defaults
ARG PYTHON_VERSION=3.12

# Stage 1: Copy all source files (no .dockerignore filtering)
FROM python:${PYTHON_VERSION}-slim AS source

WORKDIR /source
COPY . .

# Stage 2: Filter files for production (remove dev-only files)
FROM python:${PYTHON_VERSION}-slim AS filtered-source

WORKDIR /filtered

# Copy from source and manually filter out development files
COPY --from=source /source /filtered

# Remove development-only files and directories
RUN rm -rf \
    # Git
    .git \
    .gitignore \
    # Python artifacts
    __pycache__ \
    *.py[cod] \
    *.egg-info \
    .eggs \
    dist \
    build \
    *.egg \
    # Virtual environments
    .venv \
    venv \
    # Testing
    .pytest_cache \
    .coverage \
    htmlcov \
    tests \
    # IDEs
    .idea \
    .vscode \
    # Documentation (keep README.md)
    docs \
    CLAUDE.md \
    # Environment files
    .env \
    .env.local \
    .env.*.local \
    # Docker files
    Dockerfile* \
    docker-compose*.yml \
    .docker \
    dockerignore.reference \
    # Dev container
    .devcontainer \
    # Claude
    .claude \
    # Logs
    *.log \
    logs \
    # Temporary files
    tmp \
    temp \
    *.tmp \
    *.bak

# Stage 3: Base production image
FROM python:${PYTHON_VERSION}-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    # For mcp-mapped-resource-lib MIME detection
    libmagic1 \
    # For Node.js (playwright-mcp)
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /workspace

# Copy filtered production files
COPY --from=filtered-source /filtered /workspace

# Install production dependencies
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Install Playwright browsers (chromium by default)
RUN npx playwright@latest install chromium --with-deps

# Create directories for blob storage and playwright output
RUN mkdir -p /mnt/blob-storage /workspace/playwright-output

# Stage 4: Production stage
FROM base AS production
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Mount points for persistence
VOLUME ["/mnt/blob-storage", "/workspace/playwright-output"]

CMD ["uv", "run", "playwright-proxy-mcp"]

# Stage 5: Development stage with all files and additional tools
FROM python:${PYTHON_VERSION}-slim AS development

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    sudo \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI for Docker-outside-of-Docker (DooD) support
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc && \
    chmod a+r /etc/apt/keyrings/docker.asc && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

# Create vscode user with sudo privileges
ARG CREATE_VSCODE_USER=true
RUN if [ "$CREATE_VSCODE_USER" = "true" ]; then \
    groupadd --gid 1000 vscode && \
    useradd --uid 1000 --gid 1000 -m -s /bin/bash vscode && \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/vscode && \
    chmod 0440 /etc/sudoers.d/vscode && \
    groupadd docker || true && \
    usermod -aG docker vscode; \
    fi

# Set working directory
WORKDIR /workspace

# Install Node.js for Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install uv package manager for root
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install uv for vscode user if created
RUN if [ "$CREATE_VSCODE_USER" = "true" ]; then \
    su - vscode -c "curl -LsSf https://astral.sh/uv/install.sh | sh"; \
    fi

# Copy ALL files from source (including tests, CLAUDE.md, etc.)
COPY --from=source /source /workspace

# Install system dependencies for Playwright and libmagic
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (chromium by default) for the subprocess
# This needs to be done at system level so npx playwright can find them
RUN npx playwright@latest install chromium --with-deps

# Create directories for blob storage and playwright output
RUN mkdir -p /mnt/blob-storage /workspace/playwright-output

# Set ownership of workspace to vscode user
RUN chown -R vscode:vscode /workspace

# Don't run uv sync here - let postCreateCommand handle it as vscode user
# This avoids permission issues with the .venv directory

ENV PYTHONUNBUFFERED=1
CMD ["/usr/bin/sleep", "infinity"]
