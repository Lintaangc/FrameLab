"""7. Negative - invert every intensity."""
INFO = {
    "id": "negative",
    "name": "Negative",
    "summary": "Inverts intensities: light becomes dark and the other way around.",
    "formula": "g(x,y) = 255 − f(x,y)",
    "params": [],
}


def apply(img, params):
    return 255 - img  # uint8 arithmetic: 255 - x never underflows
