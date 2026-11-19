# Capstone workbench development notes

This directory is the **only active development scope** for the capstone in `CSA4315-Internet-Programming`. The original application's Flask routes, three modules, and database are retained.

## Development branch

`improvement/capstone-workbench-foundation` (review changes before merging into `main`).

## UI foundation delivered

- Dark-first responsive left navigation linking to the existing Bootstrap module tabs.
- Complete original project title and three exact module titles in application labels.
- Live overview of recent recorded passed/failed tests and average measured SOAP latency, sourced from `GET /api/v1/reports`. The API returns at most 100 records, so the overview does **not** claim lifetime totals.
- Accessible mobile menu, theme switch with local browser preference, keyboard focus indicators, and reduced-motion fallback.
- Current frontend entry point remains `templates/index.html`; the new stylesheet is `static/css/workbench.css`. Legacy HTML views remain untouched for safety.

## Runtime and security foundation

- Portable Windows starter script `Start_Project.bat` using its own directory.
- Local-only development server binding without Flask debug mode.
- XML parsing disables external entity resolution and network loading.
- SOAP XML envelope generation now uses lxml serialization, escaping user values.
- SOAP endpoint validation blocks private/reserved IPs except the local calculator demonstration endpoint; redirects are disabled; request timeout is bounded.
- Cross-origin API access defaults to `http://127.0.0.1:5000`; change `CAPSTONE_ALLOWED_ORIGIN` if an explicitly trusted frontend needs a different origin.

**Important security limitation:** DNS lookup and subsequent HTTP connection are separate operations. In a production multi-user deployment, DNS rebinding and request routing should be handled with an outbound network proxy/firewall or pinned IP transport, and authentication/authorization should be added. Do not deploy this educational Flask server to the public Internet.

## Run and verify

```bash
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

In another terminal (same directory), run:

```bash
python -m unittest discover -s tests -v
```

Verification completed on November 19, 2026: **19 of 19 tests passed** in an isolated Vercel QA sandbox. All three application modules were also exercised against the protected online deployment. See `VERCEL_PREVIEW.md` for live test results, durable private Blob audit storage, saved WSDL catalog, and known limitations.

## Work remaining

- Browser visual QA across responsive sizes and the full three-module workflow.
- Repair and unify legacy frontend implementation and obsolete tests without breaking the active page.
- Improve WSDL/XSD complex-type compatibility logic and verify SOAP 1.2 integration.
- Add persistent dashboard aggregate metrics and filters if lifetime data is required.
- Review authorization and additional network hardening before any production exposure.

## Protected online deployment

The complete Flask app is live at https://capstone-contract-studio-preview.vercel.app (Vercel sign-in required). Runtime audit history and saved WSDL configurations use private Vercel Blob, and PDF exports are generated from durable records in memory. The earlier sidebar overlap was fixed by subtracting the fixed rail width from Bootstrap's full-width layout. Automated/browser screenshot comparison has not yet been completed on all viewport sizes.
