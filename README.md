# PRISM Cloud

**AI-powered message threat detection, built for developers.**

PRISM Cloud is a developer API by [AeroxLabs](https://github.com/AeroxLabs) that analyzes text messages and identifies potential scams and security threats.

Using machine learning, PRISM evaluates messages, predicts threat categories, assigns risk levels, and returns explainable detection indicators through a simple REST API.

## Features

- **Scam Detection:** Identify potentially fraudulent and malicious messages.
- **Threat Classification:** Categorize detected threats, including phishing and financial fraud.
- **Risk Assessment:** Receive a risk-level assessment for analyzed messages.
- **Detection Indicators:** Understand which indicators contributed to a detection.
- **REST API:** Integrate message threat detection into your own applications.
- **API Authentication:** Secure requests using individual API keys.
- **Usage Tracking:** Monitor API consumption and plan limits.

## Getting Started

### API Base URL

```text
https://prism-cloud.fastapicloud.dev
```

### Authentication

Every detection request requires an API key in the `X-API-Key` header.

```http
X-API-Key: YOUR_API_KEY
```

API keys are issued by AeroxLabs. Never expose your API key in public repositories, frontend applications, or client-side code.

### First Request

Send a `POST` request to `/v1/detect`.

**Python**

```python
import requests

API_KEY = "YOUR_API_KEY"
API_URL = "https://prism-cloud.fastapicloud.dev/v1/detect"

response = requests.post(
    API_URL,
    headers={
        "X-API-Key": API_KEY
    },
    json={
        "text": "Your bank account has been suspended. Verify immediately."
    },
    timeout=30
)

response.raise_for_status()
print(response.json())
```

**PowerShell**

```powershell
$headers = @{"X-API-Key"="YOUR_API_KEY"}
$body = @{text="Your bank account has been suspended. Verify immediately."} | ConvertTo-Json

Invoke-RestMethod -Method Post `
    -Uri "https://prism-cloud.fastapicloud.dev/v1/detect" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

## API Reference

### `POST /v1/detect`

Analyzes a text message for potential threats.

**Request body**

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | Yes | Message to analyze |

**Example response**

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

The response above is illustrative, not a guaranteed result. Model confidence scores are not calibrated probabilities, and risk levels are assigned using deterministic rules.

### Response fields

| Field | Description |
|---|---|
| `is_scam` | Whether the model classified the message as a potential scam |
| `confidence_score` | Model confidence score |
| `risk_level` | Assigned risk level |
| `reason_codes` | Detection indicators and predicted category |
| `usage` | API plan and usage information |

### `GET /health`

Returns application health information.

## Plans and Usage Limits

| Plan | Monthly requests | Rate limit |
|---|---:|---:|
| Free | 500 | 1 request/second |
| Pro | 25,000 included | 5 requests/second |

Pro requests beyond the included allowance are tracked as overage requests. Automatic overage billing is not currently supported.

Contact AeroxLabs for API access and plan information.

## Error Handling

PRISM Cloud uses standard HTTP status codes to communicate request outcomes.

| Status | Meaning |
|---|---|
| `200` | Request successfully processed |
| `401` | Missing or invalid API key |
| `429` | Rate or usage limit exceeded |
| `500` | Internal server error |

Error responses may include a `request_id` for troubleshooting.

## Architecture and Intellectual Property

PRISM Cloud is provided as a hosted API.

The underlying machine learning models, model artifacts, training datasets, feature extraction pipeline, and internal inference implementation are proprietary to AeroxLabs and are not included in this repository.

This repository contains public-facing API documentation and integration examples only.

## Responsible Use

PRISM is designed to assist with identifying potentially fraudulent messages. Its predictions should not be treated as definitive proof that a message is malicious or legitimate.

Always apply appropriate human review and additional security controls when making consequential decisions.

## About AeroxLabs

PRISM Cloud is developed by **AeroxLabs**, an independent AI development initiative focused on building practical machine learning systems and developer tools.

## Contact

For API access, questions, or collaboration inquiries, contact AeroxLabs through GitHub.

---

© 2026 AeroxLabs. All rights reserved.
