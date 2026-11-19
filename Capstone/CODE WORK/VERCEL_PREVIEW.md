# Verified online deployment — Capstone Contract Studio

> Scope: `Capstone/CODE WORK/` in `sanjaykumar3L/CSA4315-Internet-Programming`.
> No changes to NetShield or repository `main`.

## Current deployment

- **Stable URL**: https://capstone-contract-studio-preview.vercel.app
- **Vercel team**: `lsk10`
- **Vercel project**: `capstone-contract-studio-preview`
- **Framework**: Flask (Python 3.12 runtime on Vercel)
- **Vercel root directory**: `Capstone/CODE WORK`
- **Git branch**: `deployment/capstone-vercel-preview`
- **Access**: Vercel Authentication enabled on all deployment URLs. Remain protected until authorization, rate limiting and network egress policy have been independently reviewed.
- **Storage**: private Vercel Blob (`BLOB_READ_WRITE_TOKEN` injected through Vercel project integration). Audit documents survive redeployments; local development still uses SQLite.

## Tested on November 19, 2026

In an isolated sandbox, `python -m unittest discover -s tests -v` completed with **19 tests passing**.

Online application checks against a protected deployment:

| Operation | Result |
| --- | --- |
| Root HTML and UI CSS | HTTP 200 |
| Module 1: save service configuration | HTTP 200; durable service catalog persisted |
| Module 1: reload service catalog | HTTP 200; contains CalculatorService |
| Runtime API | HTTP 200; `history_persistence: "vercel-blob"` |
| Calculator WSDL | HTTP 200; dynamically advertises deployment URL |
| Module 1: parse WSDL | HTTP 200, two operations found |
| Module 1: generate SOAP envelope | HTTP 200; unsafe input escaped |
| Module 2: valid XML vs XSD | HTTP 200; PASSED |
| Module 2: incorrect datatype | HTTP 422; FAILED |
| Module 2: mandatory field omitted | HTTP 422; FAILED |
| Module 2: compatible schema update | HTTP 200; compatible |
| Module 2: breaking schema update | HTTP 200; incompatible with two changes |
| Module 3: SOAP Add (7 + 8) | HTTP 200; PASSED, result 15 |
| Module 3: division by zero | SOAP Fault detected; FAILED, upstream HTTP 500 |
| Persistent history | Contains records from separate prior requests |
| On-demand PDF download | HTTP 200, valid PDF binary |
| Stable alias | Reassigned to the tested preview build and checked for `vercel-blob` and fixed UI CSS |

The UI width correction subtracts the fixed sidebar width from both main content and header, including Bootstrap's `container-fluid` default width. **Actual browser screenshot comparisons after this change are still pending**, so do not claim visual QA has been completed on all screen sizes.

## Data model and limitations

WSDL configurations are also stored separately under `capstone-services/v1/` in the same private Blob store; the UI retrieves a metadata-only service catalog.

Durable test logs are stored as separate JSON files under `capstone-records/v1/` in **private** Vercel Blob. Report PDFs are generated in memory from saved records. Data remains available between serverless invocations and deployments, unlike `/tmp` SQLite.

Caveats:
- The audit log is **append-only object storage**, not a relational reporting database. Browsing history enumerates blob objects; large history volumes will require a proper indexed database, pagination and retention policy.
- Do not store production credentials or private customer payloads. Educational XML test payloads may be recorded in the private audit store.
- The application requires Vercel Authentication to stay protected. The external SOAP executor is for controlled classroom testing and still requires hardened DNS/IP egress, rate limiting, quotas and explicit user authorization before public release.
- No custom domain, paid subscription upgrade, or NetShield configuration was changed.
- Tests verify prepared requests and core backend behavior; real third-party SOAP endpoints can fail owing to TLS, CORS, rate limits or upstream service behavior.

## Development

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python run.py
```

Open `http://127.0.0.1:5000` locally. No Vercel Blob token is required for normal local SQLite mode.

The pull requests remain **draft** and unmerged; this online deployment tests the branch directly. Review and merge only when satisfied with the result.
