import pymupdf as fitz
from pathlib import Path
from excel_reader import get_student

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "templates" / "Passport_Blank.pdf"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)


# STUDENT DATA
student_id = input("Enter Student ID: ").strip()

student = get_student(student_id)

if student is None:
    raise ValueError(f"Student {student_id} not found in Excel!")



# STAMP FILES
stamp_files = {
    "AI Skill": BASE_DIR / "stamps" / "ai_skill.png",
    "AI Applied Skill": BASE_DIR / "stamps" / "ai_applied.png",
    "AI Advanced Skill": BASE_DIR / "stamps" / "ai_advanced.png"
}


# OPEN PDF TEMPLATE
doc = fitz.open(TEMPLATE)


# PAGE 1 - STUDENT INFORMATION
page = doc[0]

page.insert_text(
    (255, 270),
    student["first_name"],
    fontsize=14,
    color=(0, 0, 0)
)

page.insert_text(
    (255, 310),
    student["last_name"],
    fontsize=14,
    color=(0, 0, 0)
)

page.insert_text(
    (655, 263),
    student["first_issued"],
    fontsize=12,
    color=(0, 0, 0)
)

page.insert_text(
    (685, 515),
    student["passport_id"],
    fontsize=12,
    color=(0, 0, 0)
)


# PASSPORT ID ON OTHER PAGES
passport_positions = {
    1: (160, 491),
    2: (690, 510),
    3: (160, 491)
}

for page_number, position in passport_positions.items():
    page = doc[page_number]

    page.insert_text(
        position,
        student["passport_id"],
        fontsize=10,
        color=(0, 0, 0)
    )


# PAGE 3 - VERIFIED AI SKILLSET
skills_page = doc[2]

card_positions = [
    (75, 255),
    (220, 255),
    (365, 255),
    (510, 255),
    (655, 255),

    (75, 425),
    (220, 425),
    (365, 425),
    (510, 425),
    (655, 425)
]

for index, skill in enumerate(student["skills"][:10]):
    x, y = card_positions[index]

    # Skill name
    text_rect = fitz.Rect(
        x, y - 5,
        x + 125, y + 20
    )

    result = skills_page.insert_textbox(
        text_rect,
        skill["name"].upper(),
        fontsize=8,
        fontname="hebo",
        align=fitz.TEXT_ALIGN_CENTER,
        color=(0, 0, 0)
    )

    if result < 0:
        print("Page 3 - Text did not fit:", skill["name"])

    # Skill category
    category_rect = fitz.Rect(
        x, y + 22,
        x + 125, y + 40
    )

    result = skills_page.insert_textbox(
        category_rect,
        skill["category"].upper(),
        fontsize=7,
        fontname="helv",
        align=fitz.TEXT_ALIGN_CENTER,
        color=(0.4, 0.4, 0.4)
    )

    if result < 0:
        print("Page 3 - Category did not fit:", skill["category"])

    # Stamp image
    stamp_path = stamp_files[skill["category"]]

    stamp_rect = fitz.Rect(
        x + 12,
        y - 65,
        x + 112,
        y - 15
    )

    skills_page.insert_image(
        stamp_rect,
        filename=str(stamp_path),
        keep_proportion=True
    )


# PAGE 4 - AI SKILL SUPPLEMENT
supplement_page = doc[3]

# Row positions
row_positions = [200, 260, 320, 380, 440]

# Column positions and widths
columns = {
    "skill": (195, 95),
    "description": (295, 145),
    "earned_through": (455, 175),
    "date_earned": (650, 115)
}

for index, skill in enumerate(student["skills"][:5]):
    y = row_positions[index]

    # Stamp image
    stamp_path = stamp_files[skill["category"]]

    supplement_page.insert_image(
        fitz.Rect(105, y - 5, 175, y + 25),
        filename=str(stamp_path),
        keep_proportion=True
    )

    # Information for each column
    fields = {
        "skill": skill["name"],
        "description": skill["description"],
        "earned_through": skill["earned_through"],
        "date_earned": skill["date_earned"]
    }

    # Insert text into each column
    for field_name, value in fields.items():
        x, width = columns[field_name]

        # Separate text area for each cell
        text_rect = fitz.Rect(
            x,
            y - 5,
            x + width,
            y + 45
        )

        # Use a smaller font for long skill names
        font_size = 7

        if field_name == "skill" and len(str(value)) > 20:
            font_size = 6

        result = supplement_page.insert_textbox(
            text_rect,
            str(value),
            fontsize=font_size,
            fontname="helv",
            align=fitz.TEXT_ALIGN_CENTER,
            color=(0, 0, 0)
        )

        if result < 0:
            print(
                "Page 4 - Text did not fit:",
                field_name,
                value
            )


# SAVE PDF

student_id = student["student_id"]

output_filename = f"{student_id}_passport.pdf"

output_path = OUTPUT_DIR / output_filename

doc.save(output_path)
doc.close()

print("PDF created:", output_path)
print("Student:", student["first_name"], student["last_name"])
print("Passport ID:", student["passport_id"])
print("Number of skills:", len(student["skills"]))

