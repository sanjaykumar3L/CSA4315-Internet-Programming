# Vercel online preview deployment

This setup affects **only** `Capstone/CODE WORK/`, not NetShield or any other repository directory.

## Status and safeguards

- Deployment branch: `deployment/capstone-vercel-preview`.
- Flask entry point: `app.py`, with `requirements.txt` in the same directory.
- Frontend entry point: `templates/index.html`.
- Vercel project **Root Directory** must be `Capstone/CODE WORK` (relative to the repository root).
- Framework preset: **Flask**, with automatic Python dependency installation.
- Deploy this **preview branch**, not `main`, while testing. Keep production private/protected until functionality and security have been reviewed.

## Online-only changes

1. The Calculator demonstration WSDL dynamically advertises the deployed origin rather than 127.0.0.1.
2. SOAP requests to this application's `/soap/calculator` are handled through the actual built-in Flask SOAP endpoint without a self-referential network call. External service calls continue through the SOAP dispatcher.
3. SQLite audit history and PDF output are redirected to a temporary filesystem directory on Vercel. **This is nonpersistent** and can disappear on any cold start, concurrent invocation, scaling event, or redeploy. The UI visibly warns about this limitation.
4. The runtime endpoint `GET /api/v1/runtime` identifies local and preview modes and whether storage is ephemeral.
5. Local Windows BAT workflow is retained unchanged by this deployment branch.

## Important next milestone: persistent storage

Before calling this a reliable hosted application, migrate the audit trail to durable managed Postgres (or equivalent) and save reports in persistent object storage or generate them on request without assuming local files persist. Do not expose production services or real user data while using ephemeral preview storage.

## Security requirements

The remote SOAP executor should require authentication and authorization before public production access. The current endpoint restrictions reject private/reserved networks and disable redirects but do **not** eliminate DNS rebinding, proxy or alternate destination issues. Use egress controls or DNS/IP pinning, plus rate limiting and request quotas, before supporting arbitrary internet users.

## Online verification

Once Vercel preview deployment exists:

- Open `/` and confirm the application renders.
- Open `/api/v1/runtime` and confirm `mode=vercel-preview` and `history_persistence=ephemeral`.
- Open `/soap/calculator?wsdl`; confirm it advertises the deployment hostname.
- Parse that WSDL in Module 1.
- Validate valid, missing-field and data-type-error XML in Module 2.
- Execute Calculator Add and division-by-zero SOAP Fault cases in Module 3.
- Download a test PDF immediately after generating it, if the same temporary record is still available.
- Verify error logs and function execution limits; do not claim history persistence.
- Confirm responsive navigation and theme switching.
- Run `python -m unittest discover -s tests -v` in a configured local environment and report actual test results.

## Maintenance

All changes remain in GitHub; Vercel will use Git commits. Production publication and merging to main are separate actions, to be performed only after review.
