from dataclasses import dataclass, field
from typing import List

@dataclass
class Color:
    r: int = 0
    g: int = 0
    b: int = 0

    @staticmethod
    def RGB(r: int, g: int, b: int) -> "Color":
        return Color(r, g, b)
    
@dataclass
class Image:
    width: int
    height: int
    pixels: List[List[Color]] = field(default_factory=list)

    @staticmethod
    def new(width: int, height: int) -> "Image":
        pixels = [[Color.RGB(0, 0, 0) for _ in range(width)] for _ in range(height)]
        return Image(width, height, pixels)