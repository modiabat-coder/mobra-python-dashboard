# MOBRA Normative Evidence Base

The normative evidence base comprised World Health Organization guidance on laboratory biosafety, laboratory biosecurity, rapid-response mobile laboratories, and the transport of infectious substances; ISO 35001 for biorisk management; ISO 31000 for risk management; and the sixth edition of Biosafety in Microbiological and Biomedical Laboratories. Supporting evidence included recent scientific literature on mobile biological laboratories and laboratory biosafety and biosecurity.

## Selection and access

`config/normative_resources.json` is the single manifest used by the application and catalogue exports. It records official source pages, authorized official downloads when available, edition/year, topic, relevance, access type, current status, copyright/licence, citation, and verification date. WHO resources expose official links and are not bundled by default. ISO resources are licensed standards, link-only, and labelled **Do not redistribute**. ISO/TS 7446:2026 is clearly labelled implementation guidance and does not replace ISO 35001.

WHO-05 is the current WHO transport edition: *Guidance on Regulations for the Transport of Infectious Substances 2025–2026*, applicable from 1 October 2025. ISO 35001:2019 remains published and is under revision for a future second edition; Amendment 1:2024 is recorded. ISO 31000:2018 was reviewed and confirmed in 2023 and remains current. BMBL sixth edition is an advisory best-practice document and is not itself a regulatory standard.

## Supporting literature

`config/supporting_literature.json` keeps DOI/publisher metadata separate from normative resources. Supporting literature is not automatically normative and publisher PDFs are not uploaded without clear redistribution permission. The current catalogue contains five records covering mobile laboratory operations, laboratory biosafety/biosecurity, risk assessment, emergency preparedness, and validation methodology.

## Copyright and attribution

MOBRA exports metadata and official links, not unauthorized document contents. `MOBRA_Open_Access_Reference_Package.zip` can include only explicitly supplied files marked as redistribution-permitted; ISO PDFs are never bundled. Before lawful bundling, verify licence, attribution, non-commercial restrictions, file integrity, official source, and current edition. The safer default is an official-link download.

## Review and non-endorsement

Review the manifest at least before each release and update `last_verified_date`, edition, official URLs, status, and citations. Missing external links must not crash the app. Access to a referenced standard or guidance document does not imply endorsement, certification, accreditation, or validation of MOBRA by the issuing organization. MOBRA does not claim WHO, ISO, CDC, or NIH endorsement.
