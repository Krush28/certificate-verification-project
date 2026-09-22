# Certificate Verification Project

A certificate verification pipeline that extracts certificate information from uploaded documents, verifies the information against the issuer's verification website, compares the extracted and verified fields deterministically, and checks the certificate against a trusted registry.

The project is designed as a modular pipeline so that OCR providers, LLM providers, web-verification tools, and browser automation can be changed without redesigning the core verification logic.

---

## Overview

The certificate verification pipeline follows this flow:

```text
Certificate Image / PDF
        ↓
OCR API
        ↓
OCR Text + Structured Data
        ↓
Local LLM
        ↓
Canonical Certificate Fields
        ↓
MCP Client
        ↓
MCP Tool Gateway
        ↓
Sandbox / Web Verification
        ↓
Issuer Website Data
        ↓
Deterministic Field Comparison
        ↓
MISMATCH → STOP
        ↓
MATCH
        ↓
Trusted Certificate Registry
        ↓
VERIFIED / DOMAIN_NOT_VERIFIED
```

The main goal is to keep AI-based extraction separate from the final verification decision.

The LLM is used for information extraction and normalization. It is **not responsible for deciding whether a certificate is genuine**.

The final certificate comparison and trusted-registry decision are deterministic.

---

## Key Features

- Upload certificate images or PDF documents.
- Extract certificate information using an external OCR service.
- Use a local LLM for structured certificate-field extraction.
- Normalize certificate information into a canonical format.
- Route web-verification requests through an MCP-based architecture.
- Isolate web access inside a separate Sandbox process.
- Scrape issuer verification pages using the current BeautifulSoup-based implementation.
- Compare certificate fields deterministically.
- Stop verification immediately when a field mismatch is detected.
- Check matching certificates against a trusted certificate registry.
- Detect CAPTCHA or bot-verification pages.
- Capture screenshots of CAPTCHA/bot-verification pages.
- Send CAPTCHA screenshots to the Frontier LLM for analysis/handling.
- Keep LLM and external-service configuration in environment variables.
- Support future migration from the current local LLM to a Gemini paid service.
- Provide a path for future Firecrawl and Browser Use integration.

---

## Verification Fields

The pipeline currently works with the following canonical certificate fields:

| Field | Description |
|---|---|
| `certificate_id` | Unique certificate or credential identifier |
| `recipient_name` | Name of the person receiving the certificate |
| `issuer` | Organization that issued the certificate |
| `issued_date` | Certificate issue date |
| `verification_url` | URL used to verify the certificate |

The LLM is responsible for extracting and normalizing these values from OCR output.

The final verification decision is performed using deterministic comparison logic.

---

## Verification Workflow

### 1. Certificate Upload

The user uploads a certificate image or PDF.

The backend accepts the uploaded document through:

```text
POST /api/certificate/verify-document
```

---

### 2. OCR Processing

The backend sends the uploaded document to the configured OCR service.

Current OCR configuration:

```env
OCR_API_URL=http:
OCR_ENDPOINT_PATH=/api/extract
```

The current OCR service exposes:

```text
POST /api/extract
```

with the uploaded document sent as a multipart form-data file.

The OCR service returns extracted text and/or structured information.

---

### 3. Local LLM Extraction

The OCR result is passed to the configured local LLM.

The local LLM extracts and normalizes the canonical certificate fields:

```text
certificate_id
recipient_name
issuer
issued_date
verification_url
```

The LLM may identify a verification URL when the URL is explicitly present in the certificate/OCR content.

The LLM must not invent a verification URL.

---

### 4. MCP Client

After certificate information has been extracted, the backend uses the MCP client to request web verification.

The MCP layer provides a controlled interface between the application and external web-verification tools.

The current configuration uses:

```env
MCP_CLIENT_MODE=inprocess
MCP_CLIENT_BASE_URL=http://localhost:8000
```

---

### 5. MCP Tool Gateway

The MCP layer routes the verification request to the appropriate web-verification tool.

The goal is to keep the application logic independent from the specific web-access implementation.

The current development architecture uses the Sandbox for web access.

---

### 6. Sandbox Web Verification

Web access is isolated into the Sandbox process.

Current architecture:

```text
Backend
   ↓
Sandbox Runner
   ↓
Certificate Scraper
   ↓
HTTP Request
   ↓
Issuer Verification Website
```

The Sandbox uses a separate Python environment and executes web-access tools independently from the main backend process.

This provides isolation between the application and web-scraping logic.

---

## Verification Website Extraction

The current implementation uses:

```text
httpx
BeautifulSoup
```

inside the Sandbox.

The scraper retrieves the issuer verification page and extracts the relevant certificate fields.

The current implementation is intentionally simple so that the web-verification layer can later be replaced or extended with more advanced tools.

---

## Deterministic Field Comparison

Once the issuer website has been processed, the extracted certificate fields are compared with the values obtained from the uploaded certificate.

For example:

```text
Certificate:
certificate_id = ABC123
recipient_name = John Doe
issuer = Example University
issued_date = 2026-01-15

Issuer Website:
certificate_id = ABC123
recipient_name = John Doe
issuer = Example University
issued_date = 2026-01-15
```

The fields match, so the verification process continues.

If a mismatch occurs:

```text
Certificate:
certificate_id = ABC123

Issuer Website:
certificate_id = XYZ999
```

the verification process stops with:

```text
MISMATCH
```

The LLM does not override this deterministic comparison.

---

## Trusted Certificate Registry

After all certificate fields match the issuer's verification data, the certificate can be checked against the trusted certificate registry.

The current development implementation uses a local SQLite database.

The registry stores:

```text
certificate_id
recipient_name
issuer
issued_date
```

The registry API currently provides:

```text
POST /api/certificate/trusted
GET  /api/certificate/trusted
```

Example request:

```json
{
  "certificate_id": "ABC123",
  "recipient_name": "John Doe",
  "issuer": "Example University",
  "issued_date": "2026-01-15"
}
```

The current SQLite registry is intended for development.

A production deployment should replace it with the appropriate trusted certificate source while preserving the same application contract.

---

## CAPTCHA / Bot Verification Handling

Some issuer websites may display CAPTCHA or bot-verification pages instead of the certificate information.

The intended workflow is:

```text
Issuer Verification Page
        ↓
CAPTCHA / Bot Verification Detected
        ↓
Take Screenshot
        ↓
Send Screenshot to Frontier LLM
        ↓
Frontier Model CAPTCHA Analysis / Handling
        ↓
Continue Verification
        ↓
Extract Certificate Data
        ↓
Deterministic Comparison
```

The Frontier model is intended to assist with CAPTCHA/bot-verification handling when the verification website requires visual or interactive analysis.

This workflow still requires testing against real issuer websites because CAPTCHA implementations and anti-bot systems vary between websites.

---

## LLM Architecture

The project separates LLM responsibilities into two areas.

### Local LLM

The local LLM is currently used for:

- OCR-result interpretation.
- Certificate-field extraction.
- Field normalization.
- Verification URL identification when explicitly present.

Current configuration:

```env
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_API_KEY=
LOCAL_LLM_MODEL=
LOCAL_LLM_TIMEOUT_SECONDS=120
```

The local LLM is not responsible for the final certificate-verification decision.

---

### Frontier LLM

The Frontier LLM is currently configured separately.

Current configuration:

```env
FRONTIER_PROVIDER=gemini
FRONTIER_API_KEY=
FRONTIER_MODEL=
FRONTIER_ENABLE_WEB_SEARCH=true
FRONTIER_TIMEOUT_SECONDS=120
```

The Frontier model is intended for tasks requiring stronger reasoning or visual analysis, including the planned CAPTCHA/bot-verification workflow.

---

## Planned Gemini Migration

The current development environment uses a local LLM for certificate extraction.

During development, limitations were observed with structured certificate extraction and normalization.

A future version is planned to use a paid Gemini service exposed through the mentor's Flask service.

The intended architecture is:

```text
Certificate
    ↓
OCR
    ↓
Gemini Paid Service / Flask API
    ↓
Structured Certificate Fields
```

The provider configuration is kept separate from the core verification logic so that this migration does not require redesigning the entire pipeline.

API keys and credentials must remain outside the repository.

---

## Planned Web Automation

The current implementation uses the Sandbox with HTTP requests and BeautifulSoup.

Future versions are planned to evaluate:

### Firecrawl

Firecrawl can be used for structured website crawling and content extraction.

Potential future flow:

```text
MCP
 ↓
Firecrawl
 ↓
Issuer Website
 ↓
Structured Content
```

### Browser Use

Browser Use can be evaluated for websites that require:

- JavaScript execution.
- Form interaction.
- Button clicks.
- Dynamic page navigation.
- Browser-based workflows.

Potential future flow:

```text
MCP
 ↓
Browser Use
 ↓
Interactive Issuer Website
 ↓
Certificate Information
```

These are planned enhancements and are not currently required for the existing development implementation.

---

## Current Architecture

The current development architecture is:

```text
                    Certificate
                         │
                         ▼
                    OCR Service
                         │
                         ▼
                 Local LLM Extraction
                         │
                         ▼
                    MCP Client
                         │
                         ▼
                  MCP Tool Gateway
                         │
                         ▼
                      Sandbox
                         │
                         ▼
              BeautifulSoup / HTTPX
                         │
                         ▼
             Issuer Verification Site
                         │
                         ▼
             Extracted Website Fields
                         │
                         ▼
            Deterministic Field Comparison
                         │
                  ┌──────┴──────┐
                  │             │
               MISMATCH        MATCH
                  │             │
                 STOP           ▼
                       Trusted Registry
                              │
                    ┌─────────┴─────────┐
                    │                   │
                 VERIFIED      DOMAIN_NOT_VERIFIED
```

---

## Project Structure

```text
CertificateVerification2/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── ...
│   │   ├── ocr/
│   │   │   └── client.py
│   │   └── tools/
│   │       └── beautifulsoup_tool.py
│   │
│   └── .venv/
│
├── frontend/
│
├── sandbox/
│   ├── .venv/
│   ├── tools/
│   │   └── certificate_scraper.py
│   ├── requirements.txt
│   └── runner.py
│
├── tests/
│
├── .env.example
├── .gitignore
├── README.md
├── setup_sandbox.ps1
└── setup_sandbox.sh
```

---

## Setup

### Backend

Open PowerShell and run:

```powershell
cd "C:\Users\Rushabh K\Desktop\CertificateVerification2\backend"
```

Activate the backend virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the backend:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend should start on:

```text
http://127.0.0.1:8000
```

---

### Sandbox

From the project root:

```powershell
cd "C:\Users\Rushabh K\Desktop\CertificateVerification2"
```

Run the Sandbox setup script:

```powershell
.\setup_sandbox.ps1
```

The Sandbox creates its own Python virtual environment and installs its dependencies.

---

## Environment Configuration

Create a local `.env` file using `.env.example` as the template.

Example:

```env
APP_HOST=
APP_PORT=
CORS_ORIGINS=*
DATA_DIR=./backend/data
TOOL_GATEWAY_KEY=

# OCR
OCR_API_URL=http:
OCR_ENDPOINT_PATH=/api/extract
OCR_API_KEY=
OCR_AUTH_MODE=bearer
OCR_AUTH_HEADER_NAME=
OCR_FILE_FIELD_NAME=file
OCR_TIMEOUT_SECONDS=60

# Local LLM
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=
LOCAL_LLM_API_KEY=
LOCAL_LLM_MODEL=
LOCAL_LLM_TIMEOUT_SECONDS=120

# Frontier
FRONTIER_PROVIDER=gemini
FRONTIER_API_KEY=
FRONTIER_MODEL=
FRONTIER_ENABLE_WEB_SEARCH=true
FRONTIER_TIMEOUT_SECONDS=120

# MCP
MCP_CLIENT_MODE=inprocess
MCP_CLIENT_BASE_URL=

# Sandbox
SANDBOX_PYTHON=
SANDBOX_TIMEOUT_SECONDS=45

# Trusted Registry
CERTIFICATE_TRUSTED_REGISTRY_REQUIRED=true
```

Do not commit real API keys or credentials.

---

## Health Check

After starting the backend, check:

```text
GET /api/health
```

Example PowerShell command:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

The endpoint reports the current service configuration, including:

```text
status
local_llm_enabled
frontier_provider
ocr_configured
```

---

## API

### Verify Certificate Document

```text
POST /api/certificate/verify-document
```

Upload a certificate image or PDF using multipart form-data.

Optional:

```text
verification_url
```

If a verification URL is not supplied, the local LLM may identify one from the OCR content when a URL is explicitly present.

---

### Add Trusted Certificate

```text
POST /api/certificate/trusted
```

Example:

```json
{
  "certificate_id": "ABC123",
  "recipient_name": "John Doe",
  "issuer": "Example University",
  "issued_date": "2026-01-15"
}
```

---

### List Trusted Certificates

```text
GET /api/certificate/trusted
```

---

## Verification Statuses

The API may return statuses including:

| Status | Meaning |
|---|---|
| `VERIFIED` | Certificate data matched the issuer verification data and trusted registry requirements |
| `DOMAIN_NOT_VERIFIED` | Certificate information matched, but the trusted-domain/registry requirement was not satisfied |
| `MISMATCH` | Certificate information did not match issuer verification data |
| `NEEDS_HUMAN_REVIEW` | The workflow requires manual intervention |
| `MISSING_VERIFICATION_URL` | No usable verification URL was available |
| `MISSING_CERTIFICATE_ID` | Certificate ID could not be extracted |
| `LOCAL_LLM_ERROR` | Local LLM extraction failed |
| `OCR_ERROR` | OCR processing failed |

---

## Deterministic Verification Principle

The system intentionally separates AI extraction from verification decisions.

The LLM can:

```text
Read
Extract
Normalize
Interpret
```

The deterministic verification layer performs:

```text
Compare
Validate
Match
Reject
```

For example:

```text
LLM:
"Certificate No: ABC123"

        ↓

Normalized:
certificate_id = ABC123

        ↓

Issuer Website:
certificate_id = ABC123

        ↓

Deterministic Comparison:
MATCH
```

This prevents the LLM from independently declaring a certificate genuine based only on its own reasoning.

---

## Security and Secrets

Sensitive configuration must not be committed to Git.

The following should remain outside the repository:

- API keys.
- Authentication tokens.
- Private service URLs when appropriate.
- Local credentials.
- Production database credentials.
- Gemini credentials.
- OCR authentication credentials.

The `.env` file should remain ignored by Git.

The repository should contain:

```text
.env.example
```

with empty or placeholder values instead of real secrets.

---

## Development Issues and Lessons Learned

### Local LLM Limitations

The local LLM is useful for extraction and normalization, but structured certificate extraction may not always be reliable enough for every certificate format.

This is one reason a future migration to a paid Gemini service through the mentor's Flask service is planned.

The core verification logic should remain provider-independent.

---

### OCR Service Dependency

The current OCR service is hosted separately from the certificate-verification application.

Current configuration:

```text
http://192.168.1.34:8007
```

This introduces an external network dependency.

If the OCR host or port is unavailable, certificate verification cannot proceed because the backend cannot obtain the required OCR output.

The OCR configuration is therefore kept configurable through environment variables rather than hard-coded into the application.

---

### Web Verification

Issuer verification websites may differ significantly.

Some pages may be:

- Static HTML.
- JavaScript-based.
- Dynamic.
- Protected by CAPTCHA.
- Protected by anti-bot systems.
- Dependent on browser interaction.

The current BeautifulSoup implementation is therefore treated as the development web-verification implementation rather than the final web automation solution.

Future versions can introduce Firecrawl and Browser Use where appropriate.

---

### CAPTCHA Handling

CAPTCHA and bot-verification pages require special handling because the normal HTML extraction process may not expose the certificate information.

The intended architecture uses screenshot capture and Frontier-model analysis/handling before continuing verification.

This workflow requires additional testing with real issuer websites.

---

## Testing

### Backend Health Test

Start the backend:

```powershell
cd "C:\Users\Rushabh K\Desktop\CertificateVerification2\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected result should indicate that the backend is running.

---

### Sandbox Test

From the project root:

```powershell
'{"tool":"scrape_url","arguments":{"url":"https://example.com"}}' | .\sandbox\.venv\Scripts\python.exe .\sandbox\runner.py
```

A successful response should contain information such as:

```text
ok: true
title: Example Domain
HTTP status: 200
captcha_detected: false
```

This confirms that the Sandbox runner can execute the scraper independently.

---

### OCR Connectivity Test

The OCR service can be tested independently from the backend.

Check whether the OCR host is reachable:

```powershell
Test-NetConnection 192.168.1.34 -Port 8007
```

A failed connection indicates a network/service availability problem rather than necessarily a backend configuration problem.

---

## Current Development Status

The current implementation has the core development infrastructure in place:

- Backend application.
- Backend virtual environment.
- OCR client configuration.
- Local LLM configuration.
- Frontier provider configuration.
- MCP client configuration.
- Sandbox runner.
- Sandbox virtual environment.
- Sandbox web scraper.
- Trusted certificate registry.
- Certificate verification API.
- Health endpoint.
- Development README and project documentation.

The Sandbox has been tested successfully against a basic web page.

The complete end-to-end workflow still requires validation with a real certificate and a reachable OCR service.

The OCR service is currently an external network dependency, so end-to-end certificate verification cannot be considered fully validated until that service is reachable and a real certificate has been tested.

---

## Future Roadmap

### Phase 1 — Current Development

- Complete end-to-end certificate testing.
- Validate OCR responses with real certificate documents.
- Validate local LLM extraction against different certificate formats.
- Test issuer verification websites.
- Test deterministic field comparison.
- Test trusted registry behavior.

### Phase 2 — LLM Improvements

- Integrate the paid Gemini service through the mentor's Flask API.
- Compare extraction quality with the current local LLM.
- Improve structured output validation.
- Improve normalization for different certificate formats.

### Phase 3 — Web Verification Improvements

- Evaluate Firecrawl for structured website extraction.
- Evaluate Browser Use for interactive websites.
- Improve dynamic-page handling.
- Improve CAPTCHA/bot-verification handling.
- Add more robust website-specific extraction strategies.

### Phase 4 — Production Hardening

- Replace development SQLite registry with the production trusted registry.
- Add stronger authentication and authorization.
- Add production secret management.
- Improve logging and monitoring.
- Add comprehensive automated tests.
- Add rate limiting and request validation.
- Harden Sandbox isolation.
- Add production deployment configuration.

---

## Design Principles

### 1. Separate Extraction from Verification

AI models are used to extract and normalize information.

Verification decisions are performed deterministically.

---

### 2. Provider Independence

OCR, local LLM, Frontier LLM, and web-verification providers should be configurable.

Changing a provider should not require redesigning the verification pipeline.

---

### 3. Isolate Web Access

External web access is isolated from the main backend through the Sandbox/MCP architecture.

---

### 4. Fail Safely

If certificate fields do not match, verification stops.

The system should not use an LLM to override deterministic mismatches.

---

### 5. Keep Secrets Outside the Repository

Credentials and API keys must be provided through environment variables or an appropriate secret-management system.

---

### 6. Design for Replaceable Components

The current BeautifulSoup implementation is a development implementation.

Future web-verification components such as Firecrawl and Browser Use can be introduced without changing the core certificate-verification logic.

---

## Summary

The Certificate Verification Project provides a modular pipeline for:

```text
Document
   ↓
OCR
   ↓
LLM Extraction
   ↓
Canonical Certificate Data
   ↓
MCP
   ↓
Web Verification
   ↓
Deterministic Comparison
   ↓
Trusted Registry
   ↓
Verification Result
```

The current implementation focuses on establishing the complete development architecture while keeping future provider changes possible.

The immediate development priorities are:

1. Validate the OCR service connection.
2. Test the pipeline with a real certificate.
3. Validate local LLM extraction.
4. Validate issuer website verification.
5. Validate deterministic field comparison.
6. Validate trusted registry behavior.
7. Test CAPTCHA/bot-verification handling.
8. Later migrate certificate extraction to the paid Gemini service.
9. Later evaluate Firecrawl and Browser Use for more advanced web verification.

The architecture is intentionally designed so that these future changes can be introduced without replacing the core certificate-verification logic.
