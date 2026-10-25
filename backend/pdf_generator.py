"""Legacy Excel adapter for the shared passport PDF renderer."""

from pathlib import Path

from excel_reader import get_student
from passport_pdf_renderer import render_passport_pdf


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

LEGACY_STAMP_TYPES = {
    "AI Skill": "FOCUSED",
    "AI Applied Skill": "APPLIED",
    "AI Advanced Skill": "ADVANCED",
}


def _legacy_context(student):
    skills = [
        {
            "name": skill["name"],
            "category": skill["category"],
            "level": skill["category"],
            "stamp_type": LEGACY_STAMP_TYPES.get(skill["category"], "FOCUSED"),
            "description": skill["description"],
            "earned_through": skill.get("earned_through", ""),
            "date_earned": skill.get("date_earned", ""),
        }
        for skill in student["skills"]
    ]
    return {
        "student": {
            "first_name": student["first_name"],
            "last_name": student["last_name"],
            "external_student_id": student["student_id"],
        },
        "passport": {"public_reference": student["passport_id"]},
        "version": {
            "public_reference": student["passport_id"],
            "number": 1,
            "issued_date": student["first_issued"],
        },
        "verification_reference": f"passport:{student['passport_id']}",
        "skills": skills,
        "credentials": [],
    }


def generate_passport(student_id):
    student = get_student(student_id)
    if student is None:
        raise ValueError(f"Student {student_id} not found in Excel!")
    pdf_bytes = render_passport_pdf(_legacy_context(student))
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / f"{student['student_id']}_passport.pdf"
    output_path.write_bytes(pdf_bytes)
    return output_path


if __name__ == "__main__":
    generate_passport(input("Enter Student ID: ").strip())
