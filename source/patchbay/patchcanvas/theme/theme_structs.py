

class Margin:
    top = 0
    bottom = 0
    ports_side = 0
    free_side = 0
    
    @property
    def height(self) -> int:
        return self.top + self.bottom
