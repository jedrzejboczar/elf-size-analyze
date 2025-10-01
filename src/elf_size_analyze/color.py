"""
The color class
"""

import sys


class Color:
    """
    Class for easy color codes manipulations.
    """

    _base_string = '\033[%sm'
    _colors = {
        'BLACK':   0,
        'RED':     1,
        'GREEN':   2,
        'YELLOW':  3,
        'BLUE':    4,
        'MAGENTA': 5,
        'CYAN':    6,
        'GRAY':    7,
    }

    def __init__(self, color_codes=[]):
        try:
            self.color_codes = set(color_codes)
        except TypeError:
            self.color_codes = set([color_codes])

    def __add__(self, other):
        if isinstance(other, Color):
            return Color(self.color_codes.union(other.color_codes))
        elif isinstance(other, str):
            return str(self) + other
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, str):
            return other + str(self)
        return NotImplemented

    def __str__(self):
        return self._base_string % ';'.join(str(c) for c in self.color_codes)

    def __repr__(self):
        return 'Color(%s)' % self.color_codes


# should probably be done in a metaclass or something
for name, value in Color._colors.items():
    # regular color
    setattr(Color, name, Color(value + 30))
    # lighter version
    setattr(Color, 'L_%s' % name, Color(value + 90))
    # background
    setattr(Color, 'BG_%s' % name, Color(value + 40))
    # lighter background
    setattr(Color, 'BG_L_%s' % name, Color(value + 100))

setattr(Color, 'RESET', Color(0))
setattr(Color, 'BOLD', Color(1))
setattr(Color, 'DIM', Color(2))
setattr(Color, 'UNDERLINE', Color(4))
setattr(Color, 'BLINK', Color(5))
setattr(Color, 'REVERSE', Color(7))  # swaps background and forground
setattr(Color, 'HIDDEN', Color(8))


def test__colors():
    for attr in dir(Color):
        if attr.isupper() and not attr.startswith('_'):
            print(getattr(Color, attr) + 'attribute %s' % attr + Color.RESET)
    sys.exit(0)


#  test__colors()
