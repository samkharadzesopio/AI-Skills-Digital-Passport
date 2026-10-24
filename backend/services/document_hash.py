import hashlib

def calculate_pdf_hash(file_path):
    with open(file_path, "rb") as file:
        pdf_content = file.read()

    pdf_hash = hashlib.sha256(pdf_content)
    return pdf_hash.hexdigest()


if __name__ == "__main__":
    file_path = "output/BTU-T-0010_passport.pdf"

    hash1 = calculate_pdf_hash(file_path)
    hash2 = calculate_pdf_hash(file_path)

    print("First hash:", hash1)
    print("Second hash:", hash2)
    print("Are they identical?", hash1 == hash2)