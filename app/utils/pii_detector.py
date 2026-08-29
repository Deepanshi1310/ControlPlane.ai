import re


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"
)


def detect_pii(text: str):

    detected = []

    if EMAIL_PATTERN.search(text):
        detected.append("EMAIL")

    if PHONE_PATTERN.search(text):
        detected.append("PHONE")

    return {
        "detected": len(detected) > 0,
        "types": detected
    }