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
    def width(self) -> int:
        return self.sides * 2
    
    @property
    def sided_width(self) -> int:
        return self.ports_side + self.free_side
    
    @property
    def sided_height(self) -> int:
        return self.top_side * 2

    def super(self, other: 'Margin') -> 'SuperMargin':
        return SuperMargin(self, other)


class SuperMargin(Margin):
    '''Combinaison of margins with the max values margins.
    Useful to calculate the needed sizes of a box, depending
    on the selected state, for example.'''
    def __init__(self, *margins: Margin):
        self.top = max([m.top for m in margins])
        self.bottom = max([m.bottom for m in margins])
        self.sides = max([m.sides for m in margins])
        self.ports_side = max([m.ports_side for m in margins])
        self.free_side = max([m.free_side for m in margins])
        self.top_side = max([m.top_side for m in margins])
        self._height = max([m.height for m in margins])
        self._sided_width = max([m.sided_width for m in margins])
        
    @property
    def height(self) -> int:
        return self._height
    
    @property
    def sided_width(self) -> int:
        return self._sided_width
