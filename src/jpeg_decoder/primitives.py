from dataclasses import dataclass, field
from typing import List, Tuple, Dict

# [[f32; 8]; 8]
Block = List[List[float]]  # Represents an 8x8 block of floating numbers

# [Vec<Vec<Block>>; 3]
MCU = List[List[List[Block]]]  # Represents 3 components, each component is a 2D list of blocks

@dataclass
class HuffmanTable:
    # dc_tables: [HashMap<(u8, u16), u8>; 2]
    # ac_tables: [HashMap<(u8, u16), u8>; 2]
    dc_tables: List[Dict[Tuple[int, int], int]] = field(
        default_factory=lambda: [dict(), dict()]
    )
    ac_tables: List[Dict[Tuple[int, int], int]] = field(
        default_factory=lambda: [dict(), dict()]
    )

@dataclass
class ComponentInfo:
    horizontal_sampling: int = 0
    vertical_sampling: int = 0
    quantization_table_id: int = 0

@dataclass
class SofInfo:
    precision: int = 0
    height: int = 0
    width: int = 0
    components: List[ComponentInfo] = field(
        default_factory=lambda: [ComponentInfo(), ComponentInfo(), ComponentInfo()]
    )
    max_horizontal_sampling: int = 0
    max_vertical_sampling: int = 0

@dataclass
class AppInfo:
    identifier: bytes = b"\x00" * 5
    version_major_id: int = 0
    version_minor_id: int = 0
    units: int = 0
    x_density: int = 0
    y_density: int = 0
    x_thumbnail: int = 0
    y_thumbnail: int = 0

@dataclass
class JPEGMetadata:
    app_info: AppInfo = field(default_factory=AppInfo)
    sof_info: SofInfo = field(default_factory=SofInfo)
    huffman_tables: HuffmanTable = field(default_factory=HuffmanTable)
    # 4 quantization_tables each is a list of 64 floating numbers
    quantization_tables: List[List[float]] = field(
        default_factory=lambda: [[0.0] * 64 for _ in range(4)]
    )  # List of quantization tables
    table_mapping: List[Tuple[int, int]] = field(
        default_factory=lambda: [(0, 0) for _ in range(3)]
    )  # List of (dc_table_id, ac_table_id) for each component