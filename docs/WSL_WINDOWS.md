# WSL → Windows Host Connection

This document describes how to configure the proxy server to use Windows Node.js and browsers from within WSL.

## Overview

The proxy server can run in WSL while using Windows-installed Node.js and Playwright browsers. This enables access to Windows browsers (with better GPU support and native performance) from a Linux development environment.

## Configuration

### PLAYWRIGHT_WSL_WINDOWS

Enable WSL→Windows mode by setting this environment variable (any non-empty value). This automatically configures the proxy to use Windows Node.js from WSL.

**When PLAYWRIGHT_WSL_WINDOWS is set**:
1. **NPX Command**: Uses `cmd.exe /c npx.cmd` to execute Windows Node.js
2. **Process Communication**: Via stdio pipes (stdin/stdout)
3. **Node.js Instance**: Windows Node.js with access to Windows-installed browsers

**When PLAYWRIGHT_WSL_WINDOWS is NOT set** (standard mode):
1. **NPX Command**: Uses `npx` from PATH (native Linux/WSL Node.js)
2. **Process Communication**: Via stdio pipes (stdin/stdout)
3. **Node.js Instance**: Linux/WSL Node.js with access to Linux-installed browsers

### Example Configuration

```bash
# WSL→Windows mode
export PLAYWRIGHT_WSL_WINDOWS=1

# Or any non-empty value
export PLAYWRIGHT_WSL_WINDOWS=true
```

## Error Handling

If `PLAYWRIGHT_WSL_WINDOWS` is set but `cmd.exe` is not found:

```
RuntimeError: cmd.exe not found in PATH. When PLAYWRIGHT_WSL_WINDOWS is set,
cmd.exe must be available to execute Windows npx.cmd.
```

## Why This Design

This single environment variable enables Windows Node.js execution from WSL:
- No need to manually specify host IPs or port numbers
- Stdio transport works seamlessly across WSL/Windows boundary
- Simpler configuration than the previous HTTP-based approach
- No network binding or firewall concerns

## Stdio Transport Benefits

The proxy uses **stdio transport** instead of HTTP for communication with the upstream playwright-mcp server. This provides several advantages:

### 1. No Ping Timeout Issues

Stdio transport uses independent read/write streams that can handle concurrent messages (pings + tool responses). Unlike HTTP transport, there is no 5-second ping timeout limitation that required operation chunking.

### 2. Simpler Architecture

- No port detection
- No HTTP polling
- No URL construction
- Just direct pipe communication

### 3. Better Error Handling

Process exit signals instead of HTTP connection errors.

### 4. Lower Latency

Direct pipe communication has less overhead than HTTP.

### 5. No Port Conflicts

Eliminates ephemeral port management.

## Operation Duration

With stdio transport, tool operations can run for unlimited duration without worrying about ping timeouts. The previous HTTP-based workaround that split long `browser_wait_for` calls into chunks is no longer needed.

## Architecture Note

With stdio transport, the subprocess communicates via pipes rather than HTTP, eliminating the need for host IP configuration and network binding.
