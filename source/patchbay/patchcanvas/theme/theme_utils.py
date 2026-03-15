from qtpy.QtGui import QColor


def to_qcolor(color: str) -> QColor | None:
    ''' convert a color given with a string to a QColor.
    returns None if color has a incorrect value.'''
    if not isinstance(color, str):
        return None

    intensity_ratio = 1.0
    opacity_ratio = 1.0

    if color.startswith('-'):
        color = color.partition('-')[2].strip()
        intensity_ratio = - 1.0

    if '*' in color:
        words = color.split('*')
        next_for_opac = False

        for i, word in enumerate(words):
            if i == 0:
                color = word.strip()
                continue

            if not word:
                next_for_opac = True
                continue

            if next_for_opac:
                try:
                    opacity_ratio *= float(word.strip())
                except:
                    pass

                next_for_opac = False
                continue

            try:
                intensity_ratio *= float(word.strip())
            except:
                pass

    if color.startswith('rgb(') and color.endswith(')'):
        try:
            channels = [int(c.strip()) for c in
                        color.partition('(')[2].rpartition(')')[0].split(',')]
            assert len(channels) == 3
            qcolor = QColor(*channels)
        except:
            return None

    elif color.startswith('rgba(') and color.endswith(')'):
        try:
            values = [c.strip() for c in
                      color.partition('(')[2].rpartition(')')[0].split(',')]
            assert len(values) == 4
            qcolor = QColor(*[int(v) for v in values[:3]],
                            int(float(values[3]) * 255)) # type:ignore
        except:
            return None

    else:
        qcolor = QColor(color)

    if not qcolor.isValid():
        return None

    if intensity_ratio == 1.0 and opacity_ratio == 1.0:
        return qcolor

    if intensity_ratio < 0.0:
        qcolor = QColor(
            255 - qcolor.red(), 255 - qcolor.green(),
            255 - qcolor.blue(), qcolor.alpha())

    if opacity_ratio != 1.0:
        qcolor.setAlphaF(opacity_ratio * qcolor.alphaF())

    return qcolor.lighter(int(100 * abs(intensity_ratio)))

def rail_float(value, mini: float, maxi: float) -> float:
    return max(min(float(value), float(maxi)), float(mini))

def rail_int(value, mini: int, maxi: int) -> int:
    return max(min(int(value), int(maxi)), int(mini))
