# MOBRA Deployment Configuration

## Streamlit

Deploy the repository `modiabat-coder/mobra-python-dashboard` from branch `main` with `app.py` as the entry point. Keep `requirements.txt` at the repository root. Do not commit `.venv`, real laboratory data, `.env` files, or `.streamlit/secrets.toml`.

## Author email

The approved public application contact is `modiabat@gmail.com`. It is application metadata, not an SMTP credential. The example file documents the value for local configuration; the application remains functional if it is omitted.

## Optional SMTP backup

Configure only through Streamlit Secrets or environment variables:

- `MOBRA_EMAIL_ENABLED`
- `MOBRA_SMTP_HOST`
- `MOBRA_SMTP_PORT`
- `MOBRA_SMTP_USERNAME`
- `MOBRA_SMTP_PASSWORD`
- `MOBRA_SMTP_FROM`
- `MOBRA_SMTP_USE_TLS`

Keep email disabled unless institutional policy authorizes transmission. TLS is enabled by default. Passwords are never rendered or logged. The application enforces a 20 MB total attachment limit and does not attach original uploaded files by default. Hosted environments may block outbound SMTP; the ZIP and download controls remain available.

## Manuscript

The author-approved PDF is checked in at `docs/MOBRA_Manuscript.pdf` and is served as a direct download from Resources and Contact. The application verifies the PDF signature and approved SHA-256 before presenting the current manuscript card. It keeps the manuscript's historical 81.0% illustrative BRI separate from the current demonstration BRI of 86.7%.

## Secrets and privacy

Use `.streamlit/secrets.toml.example` as a placeholder only. Copy it to `.streamlit/secrets.toml` locally or configure equivalent hosted secrets; the real file is ignored by Git. Users remain responsible for data classification, authorization, retention, and lawful sharing.

## Branding, posters, and live review

Brand files live under `assets/branding/` and poster files under `assets/posters/`. The central palette and usage rules are documented in `docs/VISUAL_IDENTITY.md`. `docs/LIVE_APPLICATION_QA.md` records the deployed-app review, local verification checklist, known limitations, and the non-endorsement boundary. No third-party or ISO PDF is bundled.
