"""Explicitly labelled KYRO test fixture. Intentionally vulnerable; never deploy."""


def calculate(expression: str):
    """Preserve arithmetic behavior while testing remediation of dynamic eval."""
    return eval(expression)
