# PRISM Cloud API — hardened beta build

FastAPI wrapper for the AeroxLabs PRISM XGBoost message threat-detection model.

## Project layout

```text
prism-cloud-api/
├── main.py
├── database.py
├── auth_and_limits.py
├── ml_pipeline.py
├── logging_config.py
├── requirements.txt
├── .env.example
├── .gitignore
└── models/  (copy your five trained model artifacts here)
```

Copy these files into `models/`:
- `prism_threat_model.json`
- `prism_category_model.json`
- `prism_word_vectorizer.joblib`
- `prism_char_vectorizer.joblib`
- `prism_metadata.joblib`

Do not upload your local SQLite database or real `.env` file to a public repository.

## Local setup (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Generate two different secrets:
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Use one value for `ADMIN_SECRET` and another for `API_KEY_PEPPER`.
Keep `.env` private.

Run:
```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```
Docs: http://127.0.0.1:8000/docs

## Health checks

- `GET /health/live`: process liveness.
- `GET /health`: checks model readiness and executes `SELECT 1` against SQLite.
  Returns HTTP 200 when both checks pass, otherwise HTTP 503.

## Create customer keys

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/admin/keys" `
  -Headers @{"X-Admin-Secret"="YOUR_ADMIN_SECRET"} `
  -ContentType "application/json" `
  -Body '{"user_id":"customer-001","email":"customer@example.com","tier":"free"}'
```

Set `"tier":"pro"` only after confirming payment. The raw key is returned
once; only its HMAC-SHA256 hash is stored.

## Plan enforcement

| Plan | Rate limit per API key | Included requests per rolling 30 days |
|---|---:|---:|
| Free | 1 request/second | 500 |
| Pro | 5 requests/second | 25,000 |

Free requests after 500 are rejected with HTTP 429. Pro requests beyond
25,000 continue and increment `overage_count`. This app does not collect
payments or automatically bill overages.

The rate limiter is process-local. It works in one process, but is not shared
between workers or replicas. Use one worker/instance for this beta; use a
shared Redis limiter before scaling.

## Logs and privacy

JSON application logs include request ID, method, path, status, and duration.
They do not log message bodies or API-key values. Validation errors omit
submitted input values. Exception stack traces are retained in server logs.
Ensure hosting proxy settings do not log request bodies.

## SQLite deployment warning

SQLite is retained as requested. It is suitable for a single instance and
light traffic, but the database file must live on persistent storage or
customer keys and usage counters may be lost when the host replaces the
instance. Verify the platform's storage behavior before accepting customers.

## Beta limitations

- Pro overages are counted but not billed automatically.
- `confidence_score` is a raw XGBoost score, not a calibrated probability.
- Reason codes are heuristic indicators and predicted category, not SHAP
  explanations or causal attributions.
- Validate on source-held-out data before making real-world accuracy claims.
- Use HTTPS, protect admin access, rotate exposed secrets, and back up SQLite.
