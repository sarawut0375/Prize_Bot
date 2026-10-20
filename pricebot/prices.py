import re

_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def parse_price(text: str | None) -> float | None:
    """'฿1,234.50', '1.234 บาท', 'THB 990 - 1,290' -> first number found.
    Returns None if there is no number."""
    if not text:
        return None
    match = _NUMBER.search(str(text).replace(" ", " "))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def fmt_price(value: float | None) -> str:
    if value is None:
        return "-"
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.2f}"
