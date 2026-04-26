from django import template

register = template.Library()


def _format_indian(num_str: str) -> str:
    """Insert commas in Indian style: 1,23,45,678.90"""
    neg = num_str.startswith("-")
    if neg:
        num_str = num_str[1:]
    if "." in num_str:
        whole, frac = num_str.split(".", 1)
        frac = "." + frac
    else:
        whole, frac = num_str, ""
    if len(whole) <= 3:
        out = whole
    else:
        last3 = whole[-3:]
        rest = whole[:-3]
        # Group the rest in 2s from the right
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        out = ",".join(groups) + "," + last3
    return ("-" if neg else "") + out + frac


@register.filter(name="inr")
def inr(value, decimals=0):
    """Format a number with Indian-style commas. Usage: {{ v|inr }} or {{ v|inr:2 }}"""
    if value in (None, ""):
        return ""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return value
    try:
        d = int(decimals)
    except (TypeError, ValueError):
        d = 0
    s = f"{n:.{d}f}"
    return _format_indian(s)


@register.filter(name="rupees")
def rupees(value, decimals=0):
    """Same as inr but prefixed with ₹."""
    formatted = inr(value, decimals)
    return f"₹{formatted}" if formatted != "" else ""
