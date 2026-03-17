from patshared import PortMode


class Margin:
    top = 0
    'The top margin in a box with title on top'
    
    bottom = 0
    'The bottom margin in a box with title on top'
    
    sides = 0
    'The sides margin in a box with title on top'

    ports_side = 0
    'The margin on the ports side in a box with title on side'
    
    free_side = 0
    'The margin on the opposite side of the ports in a box with title on side'
    
    top_side = 0
    'The top (or the bottom) margin in a box with title on side'
    
    def __add__(self, other: 'Margin') -> 'Margin':
        new = Margin()
        new.top = self.top + other.top
        new.bottom = self.bottom + other.bottom
        new.sides = self.sides + other.sides
        new.ports_side = self.ports_side + other.ports_side
        new.free_side = self.free_side + other.free_side
        new.top_side = self.top_side + other.top_side
        return new

    @property
    def height(self) -> int:
        return self.top + self.bottom
    
    @property
    def width(self):
        return self.sides * 2

    def width_with(self, port_mode=PortMode.BOTH):
        match port_mode:
            case PortMode.BOTH:
                return 2 * self.ports_side
            case PortMode.NULL:
                return 2 * self.free_side
            case _:
                return self.ports_side + self.free_side
    
    @property
    def sided_width(self):
        return self.ports_side + self.free_side
    
    @property
    def sided_height(self):
        return self.top_side * 2  