# PRISM Cloud — Developer Getting Started

Welcome to PRISM Cloud, an AI-powered message threat detection API by AeroxLabs.

This guide explains how to authenticate, submit messages for analysis, interpret responses, and manage API usage.

## 1. API Base URL

```text
https://prism-cloud.fastapicloud.dev
```

All API requests should use HTTPS.

## 2. Get an API Key

PRISM Cloud requires an API key to access protected endpoints.

To request access:

1. Contact AeroxLabs through its official communication channels.
2. Specify whether you want the Free or Pro plan.
3. Receive your API key.
4. Store the key securely.

**Never publish your API key in a public repository, frontend application, or client-side JavaScript.**

## 3. Authentication

Include your API key in the `X-API-Key` request header.

```http
X-API-Key: YOUR_API_KEY
```

Requests without a valid API key will be rejected.

## 4. Your First API Request

The primary detection endpoint is:

```http
POST /v1/detect
```

### Request body

```json
{
  "text": "URGENT: Your bank account has been suspended. Verify your identity immediately."
}
```

### Python example

Install the required dependency:

```bash
pip install requests
```

Create `detect.py`:

```python
import os
import requests

API_URL = "https://prism-cloud.fastapicloud.dev/v1/detect"
API_KEY = os.environ["PRISM_API_KEY"]

response = requests.post(
    API_URL,
    headers={
        "X-API-Key": API_KEY
    },
    json={
        "text": "Your bank account has been suspended. Verify your identity immediately."
    },
    timeout=30
)

response.raise_for_status()
result = response.json()

print(result)
```

Set your API key as an environment variable before running the script.

PowerShell:

```powershell
$env:PRISM_API_KEY = "YOUR_API_KEY"
python detect.py
```

Linux/macOS:

```bash
export PRISM_API_KEY="YOUR_API_KEY"
python detect.py
```

### PowerShell example

```powershell
$headers = @{
    "X-API-Key" = $env:PRISM_API_KEY
}

$body = @{
    text = "Your bank account has been suspended. Verify your identity immediately."
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "https://prism-cloud.fastapicloud.dev/v1/detect" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

## 5. Understanding the Response

A successful detection request returns a JSON response similar to:

```json
{
  "is_scam": true,
  "confidence_score": 0.8078,
  "risk_level": "medium",
  "reason_codes": [
    "URGENCY_OR_ACCOUNT_PRESSURE",
    "FINANCIAL_ACCOUNT_LANGUAGE",
    "PREDICTED_CATEGORY:FINANCIAL_FRAUD"
  ],
  "usage": {
    "tier": "pro",
    "requests_used": 1,
    "monthly_limit": 25000,
    "overage_requests": 0,
    "is_overage": false
  }
}
```

### Response fields

| Field | Description |
|---|---|
| `is_scam` | Whether the message was classified as a threat |
| `confidence_score` | Model's threat probability, between 0 and 1 |
| `risk_level` | Assigned risk severity |
| `reason_codes` | Detection indicators and predicted threat category |
| `usage` | API plan and usage information |

### Risk levels

PRISM assigns a severity level based on its risk assessment rules.

- `low` — Lower assessed risk.
- `medium` — Moderate assessed risk.
- `high` — Higher assessed risk.

Risk severity is an assessment, not proof that a message is malicious.

### Reason codes

Reason codes provide additional context about a detection.

Examples:

- `URGENCY_OR_ACCOUNT_PRESSURE`
- `FINANCIAL_ACCOUNT_LANGUAGE`
- `PREDICTED_CATEGORY:FINANCIAL_FRAUD`

The predicted category is currently included in `reason_codes` rather than returned as a separate response field.

**Important:** A confidence score is not a guarantee of correctness. Do not treat PRISM's output as definitive proof that a message is fraudulent or legitimate.

## 6. API Plans and Limits

| Feature | Free | Pro |
|---|---:|---:|
| Monthly requests | 500 | 25,000 included |
| Rate limit | 1 request/sec | 5 requests/sec |
| API access | Yes | Yes |

Pro requests beyond the included monthly allowance are currently tracked as overage requests. They are not automatically billed by the API.

Usage information is included in successful detection responses.

## 7. Error Handling

Your application should handle unsuccessful requests gracefully.

Common HTTP errors include:

| Status | Meaning |
|---|---|
| `401` | Missing or invalid API key |
| `429` | Rate limit or request allowance exceeded |
| `500` | Internal server error |

Example:

```python
try:
    response = requests.post(
        API_URL,
        headers={"X-API-Key": API_KEY},
        json={"text": "Example message"},
        timeout=30
    )

    response.raise_for_status()
    print(response.json())

except requests.exceptions.HTTPError as error:
    print("API returned an error:", error)

except requests.exceptions.RequestException as error:
    print("Connection error:", error)
```

## 8. Health Check

You can check whether the API is responding using:

```http
GET /health
```

Example:

```bash
curl https://prism-cloud.fastapicloud.dev/health
```

## 9. API Documentation

Interactive API documentation is available at:

[PRISM Cloud API Reference](https://prism-cloud.fastapicloud.dev/docs)

Use it to inspect available endpoints and request schemas.

## 10. Security Best Practices

- Keep API keys on your backend, never in browser code.
- Store keys in environment variables or a secure secrets manager.
- Never commit `.env` files or credentials to GitHub.
- Avoid logging API keys or sensitive message contents.
- Use HTTPS for all API requests.
- Do not send passwords, authentication codes, or unnecessary personal information.
- Handle model predictions as risk indicators, not definitive judgments.

## 11. Support

For API access, technical questions, or feedback, contact AeroxLabs through its official communication channels.

**PRISM Cloud — Message Threat Intelligence API**

Built by AeroxLabs.
