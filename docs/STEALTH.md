# Stealth Mode Documentation

This document explains the stealth/anti-detection capabilities of the Playwright MCP Proxy server.

## Overview

The Playwright MCP Proxy includes built-in stealth capabilities to make browser automation less detectable by bot detection systems. This is particularly useful when scraping websites with anti-bot protections or when you need the browser to appear more like a real user.

## How It Works

The stealth implementation uses a JavaScript initialization script that runs **before** any page scripts execute. This script modifies browser properties and APIs that are commonly used to detect automation tools.

## Configuration

### Quick Start

To enable stealth mode, simply set the `PLAYWRIGHT_STEALTH_MODE` environment variable:

```bash
PLAYWRIGHT_STEALTH_MODE=true
```

This will automatically inject the bundled `stealth.js` script into every page.

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PLAYWRIGHT_STEALTH_MODE` | boolean | `false` | Enable built-in stealth mode |
| `PLAYWRIGHT_USER_AGENT` | string | (browser default) | Custom user agent string |
| `PLAYWRIGHT_INIT_SCRIPT` | string | - | Path to custom initialization script |
| `PLAYWRIGHT_IGNORE_HTTPS_ERRORS` | boolean | `false` | Ignore HTTPS certificate errors |

### Example Configuration

```bash
# Enable stealth mode
PLAYWRIGHT_STEALTH_MODE=true

# Use a realistic user agent
PLAYWRIGHT_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36

# Optional: Use headed mode to appear more real
PLAYWRIGHT_HEADLESS=false

# Optional: Use a persistent user data directory for cookies/cache
PLAYWRIGHT_USER_DATA_DIR=/app/browser-profile
```

## Anti-Detection Techniques

The bundled `stealth.js` script implements the following anti-detection techniques:

### 1. WebDriver Property Removal
- Removes `navigator.webdriver` property that identifies automation
- Sets it to `undefined` to match real browsers

### 2. Chrome Runtime Spoofing
- Adds `window.chrome.runtime` object
- Makes the browser appear to have Chrome extensions installed

### 3. Permissions API Override
- Properly handles permissions queries
- Returns realistic values for notification permissions

### 4. Plugin Array Spoofing
- Adds realistic plugin entries
- Mimics Chrome's PDF viewer, Native Client, etc.

### 5. Language Configuration
- Sets `navigator.languages` to realistic values
- Defaults to `['en-US', 'en']`

### 6. WebGL Vendor Masking
- Overrides WebGL vendor/renderer info
- Hides headless browser indicators
- Returns "Intel Inc." / "Intel Iris OpenGL Engine"

### 7. User Agent Data (Client Hints)
- Spoofs `navigator.userAgentData` for Chromium 90+
- Provides realistic brand and platform information

### 8. Battery API Masking
- Removes battery API not available in headless mode
- Returns realistic charging state

### 9. Connection Info
- Adds `navigator.connection` with realistic values
- Reports 4G connection with appropriate speeds

### 10. Media Devices
- Ensures `navigator.mediaDevices` exists
- Returns realistic device enumerations

### 11. Hardware Concurrency
- Sets CPU core count to realistic value (8 cores)

### 12. Device Memory
- Reports realistic RAM amount (8GB)

### 13. Screen Properties
- Matches screen dimensions to viewport
- Prevents dimension-based detection

### 14. Touch Events
- Adds touch support properties
- Makes browser appear touch-capable

### 15. Notification Permissions
- Sets realistic notification permission state

### 16. Canvas Fingerprinting Protection
- Basic protection against canvas fingerprinting
- Note: Advanced protection is commented out to avoid breaking legitimate canvas usage

### 17. Console Debug Protection
- Filters automation-related console messages

### 18. Error Stack Trace Cleaning
- Cleans error stack traces that might reveal automation

## Limitations

### What Stealth Mode Can Help With:
✅ Simple bot detection checks (webdriver property, plugins, etc.)
✅ Basic fingerprinting techniques
✅ User-agent based filtering
✅ Headless browser detection

### What Stealth Mode Cannot Fully Prevent:
❌ Advanced bot detection services (Cloudflare Turnstile, DataDome, PerimeterX)
❌ Behavioral analysis (mouse movements, timing patterns)
❌ IP-based rate limiting
❌ CAPTCHAs and human verification challenges
❌ TLS fingerprinting

## Advanced Usage

### Custom Initialization Scripts

If you need custom anti-detection logic, create your own initialization script:

1. Create a JavaScript file (e.g., `custom-stealth.js`)
2. Set the environment variable:
   ```bash
   PLAYWRIGHT_INIT_SCRIPT=/path/to/custom-stealth.js
   ```

Your custom script will run instead of the bundled `stealth.js`.

### Combining with Other Techniques

For maximum stealth, combine the stealth mode with:

1. **Realistic User Agents**: Use recent, common user agent strings
2. **Headed Mode**: Run with `PLAYWRIGHT_HEADLESS=false`
3. **Persistent Profiles**: Use `PLAYWRIGHT_USER_DATA_DIR` to maintain cookies/cache
4. **Proxy Rotation**: Use `PLAYWRIGHT_PROXY_SERVER` with rotating proxies
5. **Realistic Viewport**: Use common resolutions like `1920x1080` or `1366x768`
6. **Device Emulation**: Use `PLAYWRIGHT_DEVICE` to emulate real devices

### Example: Maximum Stealth Configuration

```bash
# Enable stealth mode
PLAYWRIGHT_STEALTH_MODE=true

# Use headed mode
PLAYWRIGHT_HEADLESS=false

# Realistic viewport
PLAYWRIGHT_VIEWPORT_SIZE=1920x1080

# Current Chrome user agent
PLAYWRIGHT_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36

# Persistent profile
PLAYWRIGHT_USER_DATA_DIR=/app/browser-profile
PLAYWRIGHT_ISOLATED=false

# Save session data
PLAYWRIGHT_SAVE_SESSION=true

# Use proxy (if needed)
# PLAYWRIGHT_PROXY_SERVER=http://proxy.example.com:8080
```

## Testing Stealth Mode

You can test your stealth configuration using various bot detection test sites:

1. **Arh.antoinevastel.com/bots**: Tests for headless browser detection
2. **bot.sannysoft.com**: Comprehensive bot detection test
3. **pixelscan.net**: Browser fingerprinting analysis
4. **browserleaks.com**: Various browser fingerprint tests

Example test script:

```python
# Test stealth mode
result = await browser_navigate(url="https://bot.sannysoft.com")
screenshot = await browser_take_screenshot(fullPage=True)
# Check the screenshot for "WebDriver: false" and other passing tests
```

## Troubleshooting

### Stealth Script Not Loading

Check if the script file exists:
```bash
ls -la /opt/src/mcp/playwright-proxy-mcp/src/playwright_proxy_mcp/playwright/stealth.js
```

### Still Being Detected

Try these additional measures:
1. Enable headed mode (`PLAYWRIGHT_HEADLESS=false`)
2. Add realistic delays between actions
3. Use a residential proxy
4. Update user agent to latest Chrome version
5. Consider using a persistent browser profile

### Custom Script Not Working

Ensure:
1. The script path is absolute
2. The file is readable
3. The JavaScript syntax is valid
4. The script doesn't have runtime errors

Check logs for errors:
```bash
tail -f /workspace/logs/mcp-server-playwright-proxy-mcp-docker.log
```

## Best Practices

1. **Don't Over-Stealth**: Only use stealth mode when needed. It adds overhead and may cause issues with some websites.

2. **Test Regularly**: Bot detection evolves constantly. Test your stealth configuration regularly.

3. **Combine Techniques**: Use stealth mode with realistic behavior (delays, mouse movements, etc.)

4. **Respect Rate Limits**: Even with stealth mode, excessive requests will get you blocked.

5. **Use Real User Agents**: Keep user agents up-to-date with current browser versions.

6. **Consider Legal/Ethical Implications**: Ensure your use case complies with website terms of service and applicable laws.

## Performance Impact

Stealth mode has minimal performance impact:
- Script injection: < 10ms per page load
- Memory overhead: < 1MB
- No impact on network requests

## Security Considerations

The stealth script:
- Runs in the page context (has access to page JavaScript)
- Does NOT send data externally
- Does NOT modify user data or cookies
- Only modifies browser API responses

## References

This implementation is inspired by:
- [playwright-stealth](https://github.com/AtuboDad/playwright_stealth) (Python)
- [puppeteer-extra-plugin-stealth](https://github.com/berstend/puppeteer-extra/tree/master/packages/puppeteer-extra-plugin-stealth) (Node.js)
- Various anti-detection research and techniques

## Contributing

If you discover new detection techniques or improvements to the stealth script, please:
1. Create an issue describing the detection method
2. Submit a PR with the fix/improvement
3. Include test cases demonstrating the improvement
