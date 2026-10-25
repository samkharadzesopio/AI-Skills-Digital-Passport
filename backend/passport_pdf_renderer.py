import hashlib
from functools import lru_cache
from math import ceil
from pathlib import Path

import pymupdf as fitz


BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "templates" / "Passport_Blank.pdf"
RENDERER_VERSION = "pymupdf-template-v4-georgian-fonts"

FONT_FILES = {
    "regular": BASE_DIR / "templates" / "NotoSansGeorgian-Regular.ttf",
    "bold": BASE_DIR / "templates" / "NotoSansGeorgian-Bold.ttf",
}

STAMP_FILES = {
    "FOCUSED": BASE_DIR / "stamps" / "ai_skill.png",
    "APPLIED": BASE_DIR / "stamps" / "ai_applied.png",
    "ADVANCED": BASE_DIR / "stamps" / "ai_advanced.png",
}


def renderer_fingerprint():
    digest = hashlib.sha256(RENDERER_VERSION.encode("ascii"))
    for path in (
        TEMPLATE,
        *[STAMP_FILES[key] for key in sorted(STAMP_FILES)],
        *[FONT_FILES[key] for key in sorted(FONT_FILES)],
    ):
        digest.update(path.read_bytes())
    return digest.hexdigest()

CARD_POSITIONS = [
    (75, 255), (220, 255), (365, 255), (510, 255), (655, 255),
    (75, 425), (220, 425), (365, 425), (510, 425), (655, 425),
]


class PDFRenderLimitError(ValueError):
    """Snapshot text cannot be represented faithfully by the existing template."""


@lru_cache(maxsize=2)
def _font(style="regular"):
    return fitz.Font(fontfile=str(FONT_FILES[style]))


def _page_font(page, style):
    name = f"BTUNotoGeorgian{style.title()}"
    page.insert_font(fontname=name, fontfile=str(FONT_FILES[style]))
    return name


def _text(value, limit=500):
    value = "" if value is None else str(value)
    value = " ".join(value.split())
    if len(value) > limit:
        raise PDFRenderLimitError('Text exceeds the supported template limit.')
    if any(not _font().has_glyph(ord(character), fallback=False) for character in value):
        raise PDFRenderLimitError('Text contains a glyph unavailable in the bundled font.')
    return value


def _insert_box(page, rect, value, *, fontsize=8, align=fitz.TEXT_ALIGN_LEFT, color=(0, 0, 0)):
    remaining = page.insert_textbox(
        rect, _text(value), fontsize=fontsize,
        fontname=_page_font(page, "regular"), align=align, color=color
    )
    if remaining < 0:
        raise PDFRenderLimitError('Text does not fit the existing template box.')


def _insert_line(page, position, value, *, fontsize=8, fontname='regular', max_x=None, **kwargs):
    value = _text(value)
    boundary = max_x if max_x is not None else page.rect.width - 20
    if position[0] + _font(fontname).text_length(value, fontsize=fontsize) > boundary:
        raise PDFRenderLimitError('Text does not fit the existing template line.')
    page.insert_text(position, value, fontsize=fontsize, fontname=_page_font(page, fontname), **kwargs)


def _stamp_path(stamp_type):
    return STAMP_FILES.get(str(stamp_type).upper(), STAMP_FILES["FOCUSED"])


def _render_cover(document, data):
    page = document[0]
    student, version, passport = data["student"], data["version"], data["passport"]
    _insert_line(page, (255, 270), _text(student["first_name"], 100), fontsize=14, max_x=580)
    _insert_line(page, (255, 310), _text(student["last_name"], 100), fontsize=14, max_x=620)
    page.insert_text((150, 335), "STUDENT ID:", fontsize=8, fontname="hebo")
    _insert_line(page, (255, 335), _text(student.get("external_student_id"), 60), fontsize=8, max_x=620)
    page.insert_text((150, 352), "PROGRAM:", fontsize=8, fontname="hebo")
    _insert_line(page, (255, 352), _text(student.get("program"), 80), fontsize=8, max_x=620)
    page.insert_text((655, 263), _text(version["issued_date"], 20), fontsize=10)
    page.insert_text((655, 282), f"VERSION {version['number']}", fontsize=8)
    page.insert_text((650, 515), _text(passport["public_reference"], 40), fontsize=7)
    page.insert_text((510, 220), f"VERSION ID: {_text(version['public_reference'], 40)}", fontsize=6.5)
    page.insert_text((510, 234), f"VERIFY: {_text(data['verification_reference'], 80)}", fontsize=6.5)


def _render_skill_cards(document, skills):
    page = document[2]
    for index, skill in enumerate(skills[:10]):
        x, y = CARD_POSITIONS[index]
        _insert_box(
            page,
            fitz.Rect(x, y - 5, x + 125, y + 20),
            _text(skill["name"], 80).upper(),
            fontsize=8,
            align=fitz.TEXT_ALIGN_CENTER,
        )
        classification = " / ".join(filter(None, [skill["category"], skill.get("subcategory", "")]))
        label = f"{_text(classification, 303)} / {_text(skill['level'], 20)}"
        _insert_box(
            page,
            fitz.Rect(x, y + 22, x + 125, y + 44),
            label.upper(),
            fontsize=6.5,
            align=fitz.TEXT_ALIGN_CENTER,
            color=(0.35, 0.35, 0.35),
        )
        page.insert_image(
            fitz.Rect(x + 12, y - 65, x + 112, y - 15),
            filename=str(_stamp_path(skill["stamp_type"])),
            keep_proportion=True,
        )


def _render_supplement_page(page, skills):
    # Fill the existing template's five 53.89-point rows, within its column lines.
    row_positions = [194, 248, 302, 356, 410]
    columns = {
        "skill": (207, 89), "description": (304, 138),
        "earned_through": (449, 168), "date_earned": (624, 136),
    }
    for index, skill in enumerate(skills):
        y = row_positions[index]
        page.insert_image(
            fitz.Rect(105, y + 5, 175, y + 35),
            filename=str(_stamp_path(skill["stamp_type"])),
            keep_proportion=True,
        )
        fields = {
            "skill": ' / '.join(filter(None, [skill['name'], skill['category'], skill.get('subcategory', ''), skill['level']])),
            "description": skill["description"],
            "earned_through": skill["earned_through"], "date_earned": skill["date_earned"],
        }
        for field_name, value in fields.items():
            x, width = columns[field_name]
            _insert_box(
                page,
                fitz.Rect(x, y, x + width, y + 44),
                value,
                fontsize=6.5 if field_name == "skill" else 6,
                align=fitz.TEXT_ALIGN_CENTER,
            )


def _render_credential_page(document, credentials, page_number, page_count, data):
    page = document.new_page(width=842, height=595)
    page.draw_rect(page.rect, color=(0.16, 0.16, 0.16), fill=(0.16, 0.16, 0.16))
    page.draw_rect(fitz.Rect(40, 45, 802, 550), color=(0.85, 0.85, 0.87), fill=(1, 1, 1))
    page.insert_text((70, 88), "ISSUED CREDENTIALS", fontsize=24, fontname="hebo")
    page.insert_text(
        (70, 110),
        f"Passport version {data['version']['number']} - page {page_number} of {page_count}",
        fontsize=9,
        color=(0.35, 0.35, 0.35),
    )
    y = 145
    for credential in credentials:
        page.draw_rect(fitz.Rect(70, y - 18, 772, y + 39), color=(0.75, 0.75, 0.75))
        _insert_line(page, (82, y), _text(credential["issuer_name"], 90), fontsize=9, fontname="bold", max_x=760)
        page.insert_text((82, y + 15), f"Credential: {_text(credential['public_reference'], 40)}", fontsize=7)
        expiry = credential["expires_date"] or "No expiry"
        page.insert_text((520, y + 15), f"Issued {credential['issued_date']} | {expiry}", fontsize=7)
        y += 65
    page.insert_text((70, 525), f"PASSPORT ID: {data['passport']['public_reference']}", fontsize=7)
    page.insert_text((480, 525), _text(data["verification_reference"], 80), fontsize=7)


def render_passport_pdf(data):
    """Render one immutable passport-version context to deterministic PDF bytes."""

    skills, credentials = list(data.get("skills", ())), list(data.get("credentials", ()))
    document = fitz.open(TEMPLATE)
    try:
        supplement_pages = max(1, ceil(len(skills) / 5))
        for _ in range(supplement_pages - 1):
            document.fullcopy_page(3)
        _render_cover(document, data)
        _render_skill_cards(document, skills)
        document[1].insert_text((160, 491), _text(data["passport"]["public_reference"], 40), fontsize=7)
        document[2].insert_text((650, 510), _text(data["passport"]["public_reference"], 40), fontsize=7)
        for index in range(supplement_pages):
            page = document[3 + index]
            _render_supplement_page(page, skills[index * 5 : (index + 1) * 5])
            page.insert_text((160, 493), _text(data["passport"]["public_reference"], 40), fontsize=7)
        credential_page_count = ceil(len(credentials) / 6)
        for index in range(credential_page_count):
            _render_credential_page(
                document,
                credentials[index * 6 : (index + 1) * 6],
                index + 1,
                credential_page_count,
                data,
            )
        document.set_metadata(
            {
                "title": "BTU AI Skills Digital Passport",
                "author": "Business and Technology University",
                "subject": data["verification_reference"],
                "keywords": "BTU, AI Skills, Digital Passport",
                "creator": RENDERER_VERSION,
                "producer": RENDERER_VERSION,
                "creationDate": "",
                "modDate": "",
            }
        )
        return document.tobytes(garbage=4, clean=True, deflate=True, no_new_id=True)
    finally:
        document.close()
