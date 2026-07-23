"""Generate original MOBRA brand and educational-media assets.

This script uses only the bundled document/PDF runtime when run by the
maintainer.  The source-of-truth brand geometry remains SVG; PNG and PDF files
are deterministic derivatives for web, print, and download compatibility.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.graphics.barcode import qr
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "assets" / "branding"
POSTERS = ROOT / "assets" / "posters"
OFFICIAL = "MOBRA — Mobile Operational Biosecurity Readiness Assessment"
AUTHOR = "Mohammad Ahmad Yousef E'Diabat"
EMAIL = "modiabat@gmail.com"
REPOSITORY = "https://github.com/modiabat-coder/mobra-python-dashboard"
LIVE_APP = "https://mobra-biosecurity-lab.streamlit.app/"
PALETTE = {
    "navy": "#0B1F3A",
    "teal": "#0F766E",
    "cyan": "#0EA5E9",
    "amber": "#D97706",
    "red": "#B42318",
    "green": "#168A4C",
    "ink": "#17202A",
    "slate": "#475569",
    "mist": "#F1F5F9",
    "white": "#FFFFFF",
}

POSTER_TOPICS = [
    (
        "biosafety_overview",
        "Biosafety",
        "Preventing unintended exposure and protecting people, animals, and the environment.",
    ),
    (
        "biosecurity_overview",
        "Biosecurity",
        "Protecting biological materials, information, and capabilities from misuse or loss.",
    ),
    (
        "biorisk_management",
        "Biorisk Management",
        "A structured cycle for identifying, evaluating, controlling, and reviewing biorisk.",
    ),
    (
        "mobile_biological_laboratory",
        "Mobile Biological Laboratories",
        "A deployable laboratory context where readiness, logistics, and traceability meet.",
    ),
    (
        "risk_assessment",
        "Risk Assessment",
        "A transparent review of likelihood, consequence, uncertainty, and controls.",
    ),
    (
        "incident_notification",
        "Incident Notification and Reporting",
        "Timely, traceable escalation supports learning and accountable response.",
    ),
    (
        "critical_controls",
        "Critical Controls",
        "Controls that can block an automatic deployment-ready decision when failed.",
    ),
    (
        "infectious_substance_transport",
        "Transport of Infectious Substances",
        "Plan packaging, documentation, custody, route, and emergency communication.",
    ),
    (
        "objective_evidence_traceability",
        "Objective Evidence and Traceability",
        "Connect requirements to records, observations, owners, and review decisions.",
    ),
    (
        "biosecurity_readiness_index",
        "Biosecurity Readiness Index",
        "A score of requirement readiness that does not override blocking controls.",
    ),
]


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def safe_font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def icon_svg(fill: str = PALETTE["teal"], accent: str = PALETTE["cyan"]) -> str:
    """Original shield + mobile-lab + traceability geometry."""
    return (
        f'<g fill="none" stroke="{fill}" stroke-width="18" stroke-linejoin="round">'
        '<path d="M256 24 L454 92 V242 C454 380 373 468 256 500 C139 468 58 380 58 242 V92 Z"/>'
        f'<path d="M142 274 h228 v112 h-228 z" fill="{accent}" stroke="{fill}"/>'
        '<path d="M172 274 v-42 h168 v42 M198 232 v-54 h116 v54"/>'
        f'<circle cx="170" cy="342" r="16" fill="{PALETTE["white"]}"/><circle cx="342" cy="342" r="16" fill="{PALETTE["white"]}"/>'
        '<path d="M196 342 h120 M256 178 v-58 M256 120 l-20 22 M256 120 l20 22"/>'
        "</g>"
    )


def write_svg(path: Path, body: str, width: int, height: int, background: str = PALETTE["white"]) -> None:
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" fill="{background}"/>{body}</svg>',
        encoding="utf-8",
    )


def create_logo_svgs() -> None:
    icon = icon_svg()
    write_svg(BRANDING / "mobra_icon.svg", f'<g transform="scale(1)">{icon}</g>', 512, 512)
    write_svg(
        BRANDING / "mobra_monochrome.svg", f'<g transform="scale(1)">{icon_svg("#111827", "#FFFFFF")}</g>', 512, 512
    )
    main_body = (
        '<g transform="translate(22 8) scale(.36)">' + icon + "</g>"
        f'<text x="235" y="185" font-family="Arial,sans-serif" font-size="92" font-weight="700" fill="{PALETTE["navy"]}">MOBRA</text>'
        f'<text x="240" y="270" font-family="Arial,sans-serif" font-size="31" fill="{PALETTE["slate"]}">{html.escape(OFFICIAL)}</text>'
        f'<text x="240" y="330" font-family="Arial,sans-serif" font-size="24" fill="{PALETTE["teal"]}">Structured readiness for mobile biological laboratories</text>'
    )
    write_svg(BRANDING / "mobra_logo_main.svg", main_body, 1500, 400)
    horizontal_body = (
        '<g transform="translate(10 8) scale(.22)">' + icon + "</g>"
        f'<text x="135" y="118" font-family="Arial,sans-serif" font-size="64" font-weight="700" fill="{PALETTE["navy"]}">MOBRA</text>'
        f'<text x="138" y="174" font-family="Arial,sans-serif" font-size="22" fill="{PALETTE["slate"]}">{html.escape(OFFICIAL)}</text>'
    )
    write_svg(BRANDING / "mobra_logo_horizontal.svg", horizontal_body, 1200, 240)


def draw_icon(draw: ImageDraw.ImageDraw, origin: tuple[int, int], scale: float, *, dark: bool = False) -> None:
    x, y = origin
    navy = hex_rgb(PALETTE["white"] if dark else PALETTE["navy"])
    teal = hex_rgb(PALETTE["cyan"] if dark else PALETTE["teal"])
    outline = [
        (x + 256 * scale, y + 24 * scale),
        (x + 454 * scale, y + 92 * scale),
        (x + 454 * scale, y + 242 * scale),
        (x + 373 * scale, y + 468 * scale),
        (x + 256 * scale, y + 500 * scale),
        (x + 139 * scale, y + 468 * scale),
        (x + 58 * scale, y + 242 * scale),
        (x + 58 * scale, y + 92 * scale),
    ]
    draw.polygon(outline, outline=navy, fill=None, width=max(2, int(18 * scale)))
    draw.rounded_rectangle(
        (x + 142 * scale, y + 274 * scale, x + 370 * scale, y + 386 * scale),
        radius=int(12 * scale),
        outline=navy,
        fill=teal,
        width=max(2, int(12 * scale)),
    )
    draw.rectangle(
        (x + 172 * scale, y + 232 * scale, x + 340 * scale, y + 274 * scale),
        outline=navy,
        width=max(2, int(10 * scale)),
    )
    draw.rectangle(
        (x + 198 * scale, y + 178 * scale, x + 314 * scale, y + 232 * scale),
        outline=navy,
        width=max(2, int(10 * scale)),
    )
    for cx in (170, 342):
        draw.ellipse(
            (x + (cx - 16) * scale, y + 326 * scale, x + (cx + 16) * scale, y + 358 * scale),
            fill=hex_rgb(PALETTE["white"]),
        )
    draw.line(
        (x + 196 * scale, y + 342 * scale, x + 316 * scale, y + 342 * scale), fill=navy, width=max(2, int(10 * scale))
    )


def create_logo_pngs() -> None:
    img = Image.new("RGB", (1500, 400), hex_rgb(PALETTE["white"]))
    draw = ImageDraw.Draw(img)
    draw_icon(draw, (25, 12), 0.74)
    draw.text((300, 95), "MOBRA", fill=hex_rgb(PALETTE["navy"]), font=safe_font(88, True))
    draw.text((305, 205), OFFICIAL, fill=hex_rgb(PALETTE["slate"]), font=safe_font(29))
    draw.text(
        (305, 265),
        "Structured readiness for mobile biological laboratories",
        fill=hex_rgb(PALETTE["teal"]),
        font=safe_font(23),
    )
    img.save(BRANDING / "mobra_logo_main.png")
    horizontal = img.resize((1200, 320))
    horizontal.save(BRANDING / "mobra_logo_horizontal.png")
    icon_img = Image.new("RGB", (512, 512), hex_rgb(PALETTE["white"]))
    draw_icon(ImageDraw.Draw(icon_img), (0, 0), 1.0)
    icon_img.save(BRANDING / "mobra_icon.png")
    icon_img.resize((256, 256), Image.Resampling.LANCZOS).save(BRANDING / "mobra_favicon.png")


def qr_assets() -> dict[str, Path]:
    """Render QR matrices locally with ReportLab's encoder and Pillow."""
    paths: dict[str, Path] = {}
    for name, url in (("streamlit", LIVE_APP), ("github", REPOSITORY)):
        code = qr.QrCodeWidget(url)
        code.qr.make()
        module_count = code.qr.getModuleCount()
        margin = 8
        scale = 8
        image_size = (module_count + 2 * margin) * scale
        image = Image.new("RGB", (image_size, image_size), "white")
        draw = ImageDraw.Draw(image)
        for row in range(module_count):
            for column in range(module_count):
                if code.qr.isDark(row, column):
                    x0 = (column + margin) * scale
                    y0 = (row + margin) * scale
                    draw.rectangle((x0, y0, x0 + scale - 1, y0 + scale - 1), fill="black")
        target = BRANDING / f"qr_{name}.png"
        image.save(target)
        paths[name] = target
    return paths


def brand_guidelines_pdf() -> None:
    target = BRANDING / "mobra_brand_guidelines.pdf"
    page_w, page_h = landscape(letter)
    pdf = canvas.Canvas(str(target), pagesize=(page_w, page_h))
    pdf.setFillColor(colors.HexColor(PALETTE["navy"]))
    pdf.rect(0, page_h - 120, page_w, 120, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(48, page_h - 62, "MOBRA Brand Guidelines")
    pdf.setFont("Helvetica", 13)
    pdf.drawString(48, page_h - 86, OFFICIAL.replace("—", "-"))
    pdf.setFillColor(colors.HexColor(PALETTE["ink"]))
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(48, page_h - 170, "Concept")
    pdf.setFont("Helvetica", 11)
    text = pdf.beginText(48, page_h - 195)
    text.setLeading(16)
    for line in [
        "The shield represents governance and containment; the mobile laboratory silhouette represents deployable context;",
        "the connected geometry represents traceability. The identity is original MOBRA artwork and does not imply endorsement",
        "by WHO, ISO, CDC, NIH, military, government, or any other third party.",
    ]:
        text.textLine(line)
    pdf.drawText(text)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(48, page_h - 270, "Accessible palette")
    x, y = 48, page_h - 320
    for index, (name, value) in enumerate(PALETTE.items()):
        col = index % 4
        row = index // 4
        bx, by = x + col * 170, y - row * 70
        pdf.setFillColor(colors.HexColor(value))
        pdf.roundRect(bx, by, 36, 36, 6, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor(PALETTE["ink"]))
        pdf.setFont("Helvetica", 10)
        pdf.drawString(bx + 48, by + 20, name)
        pdf.drawString(bx + 48, by + 6, value)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(48, 110, "Usage")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(
        48,
        90,
        "Use the full logo on light backgrounds, the icon at small sizes, and monochrome artwork when colour is unavailable.",
    )
    pdf.drawString(
        48,
        72,
        "Do not stretch, recolour arbitrarily, add third-party marks, or present MOBRA as endorsed or certified.",
    )
    pdf.showPage()
    pdf.setFillColor(colors.HexColor(PALETTE["teal"]))
    pdf.rect(0, page_h - 90, page_w, 90, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(48, page_h - 56, "Typography and layout")
    pdf.setFillColor(colors.HexColor(PALETTE["ink"]))
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(48, page_h - 140, "Minimum guidance")
    pdf.setFont("Helvetica", 11)
    for i, line in enumerate(
        [
            "Prefer a clear sans-serif hierarchy, generous whitespace, and labels alongside icons.",
            "Use amber for conditional attention and red only for critical warnings; do not rely on colour alone.",
            "Keep the application definition, prototype status, author, and disclaimer visible in public materials.",
        ]
    ):
        pdf.drawString(65, page_h - 170 - i * 24, "- " + line)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, 48, "MOBRA visual identity version 1.0.0 | Educational and prototype use only")
    pdf.save()


def poster_svg(
    slug: str, title: str, definition: str, *, main: bool = False, qr_paths: dict[str, Path] | None = None
) -> str:
    escaped_title = html.escape(title)
    key_points = [
        "Use documented context, responsibilities, and review points.",
        "Connect controls to objective evidence and traceable decisions.",
        "Keep uncertainty, limitations, and escalation visible.",
        "Treat outputs as demonstration support, not authorization.",
    ]
    body = [
        f'<rect x="0" y="0" width="1600" height="900" fill="{PALETTE["mist"]}"/>',
        f'<rect x="0" y="0" width="1600" height="170" fill="{PALETTE["navy"]}"/>',
        f'<g transform="translate(42 14) scale(.27)">{icon_svg(fill=PALETTE["white"], accent=PALETTE["cyan"])}</g>',
        f'<text x="195" y="78" font-family="Arial,sans-serif" font-size="66" font-weight="700" fill="{PALETTE["white"]}">MOBRA</text>',
        f'<text x="195" y="122" font-family="Arial,sans-serif" font-size="24" fill="{PALETTE["white"]}">{html.escape(OFFICIAL)}</text>',
        f'<text x="72" y="270" font-family="Arial,sans-serif" font-size="56" font-weight="700" fill="{PALETTE["navy"]}">{escaped_title}</text>',
        f'<text x="72" y="325" font-family="Arial,sans-serif" font-size="26" fill="{PALETTE["slate"]}">{html.escape(definition)}</text>',
        f'<rect x="72" y="380" width="930" height="300" rx="24" fill="{PALETTE["white"]}" stroke="{PALETTE["teal"]}" stroke-width="4"/>',
        f'<text x="112" y="430" font-family="Arial,sans-serif" font-size="28" font-weight="700" fill="{PALETTE["teal"]}">MOBRA practice points</text>',
    ]
    for idx, point in enumerate(key_points):
        yy = 490 + idx * 48
        body.append(f'<circle cx="125" cy="{yy - 8}" r="10" fill="{PALETTE["cyan"]}"/>')
        body.append(
            f'<text x="155" y="{yy}" font-family="Arial,sans-serif" font-size="24" fill="{PALETTE["ink"]}">{html.escape(point)}</text>'
        )
    if main:
        body.extend(
            [
                f'<rect x="1070" y="250" width="440" height="430" rx="24" fill="{PALETTE["white"]}" stroke="{PALETTE["cyan"]}" stroke-width="4"/>',
                f'<text x="1110" y="300" font-family="Arial,sans-serif" font-size="26" font-weight="700" fill="{PALETTE["navy"]}">Framework at a glance</text>',
                f'<text x="1110" y="352" font-family="Arial,sans-serif" font-size="22" fill="{PALETTE["ink"]}">60 requirements | 24 hazards</text>',
                f'<text x="1110" y="392" font-family="Arial,sans-serif" font-size="22" fill="{PALETTE["ink"]}">Likelihood x Consequence risk matrix</text>',
                f'<text x="1110" y="432" font-family="Arial,sans-serif" font-size="22" fill="{PALETTE["ink"]}">BRI + critical-control override</text>',
                f'<text x="1110" y="472" font-family="Arial,sans-serif" font-size="22" fill="{PALETTE["ink"]}">Evidence traceability and validation</text>',
            ]
        )
    body.extend(
        [
            f'<text x="72" y="755" font-family="Arial,sans-serif" font-size="21" fill="{PALETTE["slate"]}">Educational summary. Source basis: WHO guidance, ISO standards, BMBL, and MOBRA methodology notes.</text>',
            f'<text x="72" y="792" font-family="Arial,sans-serif" font-size="21" fill="{PALETTE["slate"]}">No endorsement is claimed. Demonstration outputs are examples and require qualified institutional review.</text>',
            f'<text x="72" y="842" font-family="Arial,sans-serif" font-size="20" fill="{PALETTE["navy"]}">{html.escape(AUTHOR)} | {EMAIL} | {html.escape(REPOSITORY)}</text>',
        ]
    )
    if main and qr_paths:
        for idx, name in enumerate(("streamlit", "github")):
            data = base64.b64encode(qr_paths[name].read_bytes()).decode("ascii")
            x = 1080 + idx * 190
            body.append(f'<image x="{x}" y="520" width="150" height="150" href="data:image/png;base64,{data}"/>')
            body.append(
                f'<text x="{x + 26}" y="690" font-family="Arial,sans-serif" font-size="18" fill="{PALETTE["navy"]}">{name.title()}</text>'
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">'
        + "".join(body)
        + "</svg>"
    )


def poster_png(
    title: str, definition: str, *, main: bool = False, qr_paths: dict[str, Path] | None = None
) -> Image.Image:
    img = Image.new("RGB", (1600, 900), hex_rgb(PALETTE["mist"]))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1600, 170), fill=hex_rgb(PALETTE["navy"]))
    draw_icon(draw, (35, 12), 0.28, dark=True)
    draw.text((195, 42), "MOBRA", fill=hex_rgb(PALETTE["white"]), font=safe_font(66, True))
    draw.text((195, 105), OFFICIAL, fill=hex_rgb(PALETTE["white"]), font=safe_font(22))
    draw.text((72, 230), title, fill=hex_rgb(PALETTE["navy"]), font=safe_font(54, True))
    draw.multiline_text((72, 300), definition, fill=hex_rgb(PALETTE["slate"]), font=safe_font(25), spacing=8)
    draw.rounded_rectangle(
        (72, 380, 1002, 680), radius=24, fill=hex_rgb(PALETTE["white"]), outline=hex_rgb(PALETTE["teal"]), width=4
    )
    draw.text((112, 420), "MOBRA practice points", fill=hex_rgb(PALETTE["teal"]), font=safe_font(28, True))
    points = [
        "Use documented context, responsibilities, and review points.",
        "Connect controls to objective evidence and traceable decisions.",
        "Keep uncertainty, limitations, and escalation visible.",
        "Treat outputs as demonstration support, not authorization.",
    ]
    for idx, point in enumerate(points):
        yy = 490 + idx * 48
        draw.ellipse((115, yy - 20, 135, yy), fill=hex_rgb(PALETTE["cyan"]))
        draw.text((155, yy - 24), point, fill=hex_rgb(PALETTE["ink"]), font=safe_font(22))
    if main:
        draw.rounded_rectangle(
            (1070, 250, 1510, 680), radius=24, fill=hex_rgb(PALETTE["white"]), outline=hex_rgb(PALETTE["cyan"]), width=4
        )
        draw.text((1110, 290), "Framework at a glance", fill=hex_rgb(PALETTE["navy"]), font=safe_font(25, True))
        for idx, line in enumerate(
            [
                "60 requirements | 24 hazards",
                "Likelihood x Consequence risk matrix",
                "BRI + critical-control override",
                "Evidence traceability and validation",
            ]
        ):
            draw.text((1110, 345 + idx * 40), line, fill=hex_rgb(PALETTE["ink"]), font=safe_font(21))
        if qr_paths:
            for idx, name in enumerate(("streamlit", "github")):
                qr_img = Image.open(qr_paths[name]).convert("RGB").resize((140, 140))
                img.paste(qr_img, (1085 + idx * 190, 515))
                draw.text((1110 + idx * 190, 665), name.title(), fill=hex_rgb(PALETTE["navy"]), font=safe_font(18))
    draw.text(
        (72, 755),
        "Educational summary. Source basis: WHO guidance, ISO standards, BMBL, and MOBRA methodology notes.",
        fill=hex_rgb(PALETTE["slate"]),
        font=safe_font(19),
    )
    draw.text(
        (72, 792),
        "No endorsement is claimed. Demonstration outputs are examples and require qualified institutional review.",
        fill=hex_rgb(PALETTE["slate"]),
        font=safe_font(19),
    )
    draw.text((72, 842), f"{AUTHOR} | {EMAIL} | {REPOSITORY}", fill=hex_rgb(PALETTE["navy"]), font=safe_font(18))
    return img


def poster_pdf(path: Path, title: str, definition: str, *, main: bool = False) -> None:
    page_w, page_h = landscape(letter)
    pdf = canvas.Canvas(str(path), pagesize=(page_w, page_h))
    pdf.setFillColor(colors.HexColor(PALETTE["mist"]))
    pdf.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor(PALETTE["navy"]))
    pdf.rect(0, page_h - 95, page_w, 95, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawString(44, page_h - 52, "MOBRA")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(150, page_h - 48, OFFICIAL.replace("—", "-"))
    icon_path = BRANDING / "mobra_icon.png"
    if icon_path.is_file():
        pdf.drawImage(
            str(icon_path), page_w - 52, page_h - 88, width=40, height=40, preserveAspectRatio=True, mask="auto"
        )
    pdf.setFillColor(colors.HexColor(PALETTE["navy"]))
    pdf.setFont("Helvetica-Bold", 25)
    pdf.drawString(44, page_h - 150, title)
    pdf.setFillColor(colors.HexColor(PALETTE["slate"]))
    pdf.setFont("Helvetica", 13)
    pdf.drawString(44, page_h - 178, definition[:130])
    pdf.setFillColor(colors.white)
    pdf.roundRect(44, 150, 430, 230, 12, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor(PALETTE["teal"]))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(64, 350, "MOBRA practice points")
    pdf.setFillColor(colors.HexColor(PALETTE["ink"]))
    pdf.setFont("Helvetica", 11)
    for idx, line in enumerate(
        [
            "Use documented context, responsibilities, and review points.",
            "Connect controls to objective evidence and traceable decisions.",
            "Keep uncertainty, limitations, and escalation visible.",
            "Treat outputs as demonstration support, not authorization.",
        ]
    ):
        pdf.drawString(70, 315 - idx * 32, "- " + line)
    if main:
        pdf.setFillColor(colors.white)
        pdf.roundRect(500, 150, 270, 230, 12, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor(PALETTE["navy"]))
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(520, 350, "Framework at a glance")
        pdf.setFont("Helvetica", 11)
        for idx, line in enumerate(
            [
                "60 requirements | 24 hazards",
                "Likelihood x Consequence matrix",
                "BRI + critical-control override",
            ]
        ):
            pdf.drawString(520, 315 - idx * 26, line)
        for idx, name in enumerate(("streamlit", "github")):
            qr_path = BRANDING / f"qr_{name}.png"
            if qr_path.is_file():
                pdf.drawImage(
                    str(qr_path),
                    520 + idx * 115,
                    165,
                    width=90,
                    height=90,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                pdf.setFont("Helvetica", 9)
                pdf.drawString(540 + idx * 115, 150, name.title())
    pdf.setFillColor(colors.HexColor(PALETTE["slate"]))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        44, 100, "Educational summary. Source basis: WHO guidance, ISO standards, BMBL, and MOBRA methodology notes."
    )
    pdf.drawString(
        44,
        82,
        "No endorsement is claimed. Demonstration outputs are examples and require qualified institutional review.",
    )
    pdf.drawString(44, 50, f"{AUTHOR} | {EMAIL} | {REPOSITORY}")
    pdf.save()


def main() -> None:
    BRANDING.mkdir(parents=True, exist_ok=True)
    POSTERS.mkdir(parents=True, exist_ok=True)
    (BRANDING / "brand_palette.json").write_text(
        json.dumps(
            {
                "version": "1.0.0",
                "colors": PALETTE,
                "contrast_notes": {
                    "navy_on_white": "Passes WCAG AA for normal text",
                    "white_on_navy": "Passes WCAG AA for normal text",
                    "ink_on_mist": "Passes WCAG AA for normal text",
                    "teal_on_white": "Use for large text or controls; pair with text labels",
                    "amber_on_white": "Use for status chips with dark text labels",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    create_logo_svgs()
    create_logo_pngs()
    qr_paths = qr_assets()
    brand_guidelines_pdf()
    main_definition = "A computational verification prototype for mobile-laboratory biosecurity readiness."
    main_svg = poster_svg(
        "MOBRA_Information_Poster", "MOBRA Information Poster", main_definition, main=True, qr_paths=qr_paths
    )
    (POSTERS / "MOBRA_Information_Poster.svg").write_text(main_svg, encoding="utf-8")
    poster_png("MOBRA Information Poster", main_definition, main=True, qr_paths=qr_paths).save(
        POSTERS / "MOBRA_Information_Poster.png"
    )
    poster_pdf(POSTERS / "MOBRA_Information_Poster.pdf", "MOBRA Information Poster", main_definition, main=True)
    media = []
    for slug, title, definition in POSTER_TOPICS:
        svg_name, png_name, pdf_name = f"{slug}.svg", f"{slug}.png", f"{slug}.pdf"
        (POSTERS / svg_name).write_text(poster_svg(slug, title, definition), encoding="utf-8")
        poster_png(title, definition).save(POSTERS / png_name)
        poster_pdf(POSTERS / pdf_name, title, definition)
        media.append(
            {
                "media_id": f"POSTER-{slug.upper()}",
                "title": title,
                "topic": title,
                "description": definition,
                "svg_path": f"assets/posters/{svg_name}",
                "png_path": f"assets/posters/{png_name}",
                "pdf_path": f"assets/posters/{pdf_name}",
                "source_resource_ids": ["WHO-01", "WHO-02", "ISO-01", "BMBL-01"],
                "educational_status": "Original educational summary",
                "copyright_note": "MOBRA-created artwork and paraphrased educational content. No endorsement is claimed.",
                "last_updated": "2026-07-23",
            }
        )
    (ROOT / "config" / "educational_media.json").write_text(
        json.dumps({"media": media}, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
