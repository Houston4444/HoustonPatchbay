from qtpy.QtGui import QColor

class Color:
    def __init__(self, name: str):
        self.name = name
        self.exists_in = set[str]()
        self.equivalents = set[tuple[str, float]]()


def compare_colors(colors: dict[str, Color]):
    cols = [QColor(color_name) for color_name in colors.keys()]
    cols = sorted(cols, key=QColor.lightness)
    
    for i, col in enumerate(cols):
        if col.lightness() == 0:
            continue

        for col_ in cols[i+1:]:
            if col_.lightnessF() == 1.0:
                continue
            
            ratio = col_.lightnessF() / col.lightnessF()
            rounded_ratio = round(100 * ratio)
            reds, greens, blues = set[int](), set[int](), set[int]()
            for epsilon in (-1, 0, 1):
                light_col = col.lighter(rounded_ratio + epsilon)
                reds.add(light_col.red())
                greens.add(light_col.green())
                blues.add(light_col.blue())
                
            if (col_.red() in reds
                    and col_.green() in greens
                    and col_.blue() in blues):
                colors[col_.name()].equivalents.add((col.name(), ratio))
                colors[col.name()].equivalents.add((col_.name(), 1 / ratio))
        