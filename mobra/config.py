"""Central application metadata, approved wording, and disclaimer text."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

APP_TITLE = "MOBRA — Mobile Operational Biosecurity Readiness Assessment"
APP_VERSION = "0.9.0"
BRANDING_VERSION = "1.0.0"
AUTHOR_NAME = "Mohammad Ahmad Yousef E'Diabat"
# The author explicitly approved this public application contact address.
AUTHOR_EMAIL = "modiabat@gmail.com"
REPOSITORY_URL = "https://github.com/modiabat-coder/mobra-python-dashboard"
LIVE_APP_URL = "https://mobra-biosecurity-lab.streamlit.app/"
MANUSCRIPT_FILENAME = "MOBRA_Manuscript.pdf"
MANUSCRIPT_SHA256 = "8dbcf4e3c1017144fbd0f4fb415398f87f5665d8fce4f106b2a18354aaac22f5"
MANUSCRIPT_VERSION_NOTE = (
    "The manuscript documents the research framework and an earlier synthetic demonstration. The deployed "
    "application has subsequently undergone additional software development, governance refinement, "
    "validation-rule expansion, and interface updates. Numerical demonstration outputs in the manuscript "
    "may therefore differ from the current application."
)
DISCLAIMER_VERSION = "1.0"
PROTOTYPE_STATUS = "Experimental research and decision-support prototype"
LAST_UPDATE_DATE = "2026-07-23"
VALIDATION_REFERENCE_DATE = "2026-07-23"

APPLICATION_DEFINITION = (
    "MOBRA is a prototype decision-support application for structured operational biosecurity readiness "
    "assessment in mobile biological laboratories."
)

INTRODUCTION_COMPONENTS = [
    "Operational Requirements Library",
    "Biosecurity Readiness Index",
    "Hazard and risk analysis",
    "Requirement-to-Hazard Mapping",
    "Risk Acceptance",
    "Critical-Control Governance",
    "Data Validation",
    "Reporting and exports",
]

HOW_TO_USE_STEPS = [
    "Select demonstration data or upload assessment files.",
    "Review and correct validation findings.",
    "Examine BRI and domain readiness.",
    "Review hazards and risk acceptance.",
    "Review critical-control failures and conditional gaps.",
    "Export the assessment and supporting reports.",
]

WHAT_MOBRA_DOES_NOT_DO = [
    "Qualified biosafety or biosecurity professionals.",
    "Institutional authorization.",
    "Regulatory review.",
    "Clinical judgment.",
    "Site-specific risk assessment.",
    "Expert risk acceptance.",
    "Field validation.",
]

NORMATIVE_EVIDENCE_WORDING = (
    "The normative evidence base comprised World Health Organization guidance on laboratory biosafety, "
    "laboratory biosecurity, rapid-response mobile laboratories, and the transport of infectious substances; "
    "ISO 35001 for biorisk management; ISO 31000 for risk management; and the sixth edition of Biosafety in "
    "Microbiological and Biomedical Laboratories. Supporting evidence included recent scientific literature on "
    "mobile biological laboratories and laboratory biosafety and biosecurity."
)

NON_ENDORSEMENT_STATEMENT = (
    "Access to a referenced standard or guidance document does not imply endorsement, certification, "
    "accreditation, or validation of MOBRA by the issuing organization."
)

FULL_DISCLAIMER = (
    "MOBRA is an experimental research and decision-support prototype intended for computational verification, "
    "methodology illustration, education, and structured assessment support. It does not constitute legal, "
    "regulatory, clinical, medical, safety, security, accreditation, certification, or operational advice. "
    "It does not replace applicable laws, institutional policies, authorized biosafety and biosecurity "
    "professionals, risk-management committees, competent authorities, or accountable decision-makers.\n\n"
    "All scores, classifications, mappings, thresholds, critical-control profiles, acceptance dispositions, "
    "and deployment recommendations must be reviewed, validated, approved, and adapted by qualified "
    "institutional personnel before operational use.\n\n"
    "The author, developer, contributors, affiliated institutions, and hosting providers make no warranty "
    "regarding completeness, accuracy, suitability, reliability, or fitness for a particular purpose. To the "
    "maximum extent permitted by applicable law, they shall not be responsible for decisions, actions, omissions, "
    "losses, incidents, injuries, damages, regulatory consequences, data loss, confidentiality breaches, or "
    "other outcomes arising from use of, inability to use, or reliance on the application or its outputs.\n\n"
    "Users are responsible for protecting confidential, personal, security-sensitive, and laboratory information "
    "and for ensuring that uploading, downloading, storing, emailing, or sharing assessment data is authorized "
    "and lawful. Final legal wording should be reviewed by qualified legal counsel before institutional deployment."
)


def build_identifier() -> str:
    """Return a deployment identifier without requiring a network or repository write."""
    for key in ("GITHUB_SHA", "COMMIT_SHA", "MOBRA_BUILD_ID"):
        value = os.getenv(key)
        if value:
            return value[:12]
    try:
        root = Path(__file__).resolve().parent.parent
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def configured_author_email() -> str:
    """Return the approved public contact, allowing deployment configuration to override it."""
    value = os.getenv("MOBRA_AUTHOR_EMAIL")
    return AUTHOR_EMAIL if value is None else value.strip()


def application_metadata(*, assessment_metadata: dict[str, object] | None = None) -> dict[str, object]:
    """Return stable metadata fields used by reports and Summary JSON."""
    return {
        "application_name": APP_TITLE,
        "application_version": APP_VERSION,
        "branding_version": BRANDING_VERSION,
        "author_name": AUTHOR_NAME,
        "author_email": configured_author_email(),
        "author_email_configured": bool(configured_author_email()),
        "contact_enabled": bool(configured_author_email()),
        "repository_url": REPOSITORY_URL,
        "live_app_url": LIVE_APP_URL,
        "disclaimer_version": DISCLAIMER_VERSION,
        "manuscript_available": (Path(__file__).resolve().parent.parent / "docs" / MANUSCRIPT_FILENAME).exists(),
        "manuscript_filename": MANUSCRIPT_FILENAME,
        "manuscript_sha256": MANUSCRIPT_SHA256,
        "manuscript_version_note": MANUSCRIPT_VERSION_NOTE,
        "manuscript_download_enabled": (Path(__file__).resolve().parent.parent / "docs" / MANUSCRIPT_FILENAME).exists(),
        "email_backup_enabled": bool(os.getenv("MOBRA_EMAIL_ENABLED", "").lower() in {"1", "true", "yes", "on"}),
        "notification_system_enabled": True,
        "prototype_status": PROTOTYPE_STATUS,
        "build_identifier": build_identifier(),
        "last_update_date": LAST_UPDATE_DATE,
        "validation_reference_date": VALIDATION_REFERENCE_DATE,
        "assessment_metadata": dict(assessment_metadata or {}),
    }
