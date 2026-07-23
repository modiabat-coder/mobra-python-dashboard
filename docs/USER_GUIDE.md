# MOBRA User Guide

MOBRA — Mobile Operational Biosecurity Readiness Assessment — is an experimental computational verification and decision-support prototype for structured operational biosecurity readiness assessment in mobile biological laboratories.

## Workflow

1. Select demonstration data or upload a hazard register and ORL requirements file.
2. Enter optional assessment metadata in the sidebar.
3. Review Data Validation findings and correct blocking errors.
4. Review BRI, domain readiness, hazards, risk acceptance, mappings, and critical-control governance.
5. Read the contextual interpretation boxes before relying on any result.
6. Download the HTML report, JSON, CSV, Excel workbook, and optional backup package.

Use **Refresh View** to rerun the current page while preserving session inputs where Streamlit permits. Use **Reset Assessment** only after confirming; it clears uploaded data, filters, calculated outputs, metadata, recipient fields, and selected attachments.

## Printable forms

Resources and Contact generates the full 60-row ORL form, hazard register, blank digital import templates, and the combined field-assessment workbook. Complete paper forms with qualified assessors. Likelihood and Consequence are not inferred automatically. Handwritten PDF forms require manual data entry later; there is no automatic OCR promise.

## Contact and manuscript

Contact the author at [modiabat@gmail.com](mailto:modiabat@gmail.com) for scientific feedback, software issues, collaboration requests, data-integration questions, or general inquiries. The address is public metadata and is not an automatic assessment destination.

The approved manuscript is optional at runtime and must be supplied separately at `docs/MOBRA_Manuscript.pdf`. If absent, MOBRA displays a reminder and does not fabricate a PDF.

## Email backup and privacy

Email backup is disabled until SMTP settings are supplied through Streamlit Secrets or environment variables. Sending is explicit and requires recipient validation, a mission name, consent, institutional authorization, and data-classification confirmation. The warning explains that transmission may leave the controlled environment. Original uploaded files are excluded from attachments by default. Download `MOBRA_Assessment_Backup.zip` for a local derived-output fallback.

## Normative evidence

Resources and Contact loads the centralized normative manifest and separates normative guidance, international standards, implementation guidance, advisory best practice, and supporting scientific literature. The catalogue provides official links and metadata only. ISO documents are link-only and not redistributed. See [NORMATIVE_EVIDENCE_BASE.md](NORMATIVE_EVIDENCE_BASE.md).

## Limitations

MOBRA does not replace qualified biosafety/biosecurity professionals, institutional authorization, regulatory review, clinical judgment, site-specific risk assessment, expert risk acceptance, or field validation. Passing software tests confirms software-rule consistency only.
