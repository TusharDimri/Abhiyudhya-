"""Hiding most of a sensitive number (Aadhaar, bank account, PAN)."""


def mask(value):
    """Everything but the last four characters hidden: 'XXXXXXXX7764'."""
    if not value:
        return None
    v = str(value)
    return "X" * max(len(v) - 4, 0) + v[-4:]
