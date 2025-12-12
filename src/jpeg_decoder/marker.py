# --------------------------------------------------------
# |segment name|marker value|has data|description        |
# --------------------------------------------------------
# |SOI         |0xFFD8      |No      | start of image    |
# |EOI         |0xFFD9      |No      | end of image      |
# |DQT         |0xFFDB      |Yes     | quantization table|
# |DHT         |0xFFC4      |Yes     | huffman table     |
# |SOF0        |0xFFC0      |Yes     | baseline DCT      |
# |SOS         |0xFFDA      |Yes     | start of scan     |
# |APP0        |0xFFE0      |Yes     | JFIF extra info   |
# --------------------------------------------------------
# 無data的segment只有2bytes
# 有data的segment在marker後緊接著2bytes為此segment的長度(因此要扣除2bytes才是後面的資料量)
from __future__ import annotations
from pathlib import Path
from typing import BinaryIO, Union

from .primitives import JPEGMetadata, AppInfo, SofInfo, ComponentInfo

def marker_info(marker: int) -> str:
    
    marker_dict = {
        # 0xD8: "Start of Image (SOI)",
        # 0xD9: "End of Image (EOI)",
        0xDB: "Define Quantization Table (DQT)",
        0xC4: "Define Huffman Table (DHT)",
        0xC0: "Start of Frame 0 (SOF0) - Baseline DCT",
        0xDA: "Start of Scan (SOS)",
        0xE0: "Application Segment 0 (APP0) - JFIF Info",
    }
    
    return marker_dict.get(marker, "Unknown Marker")

def read_u8(f) -> int:
    byte = f.read(1)
    if len(byte) != 1:
        raise IOError("Unexpected length while reading 1 byte")
    return byte[0]

def read_u16(f) -> int:
    bytes_read = f.read(2)
    if len(bytes_read) != 2:
        raise IOError("Unexpected length while reading 2 bytes")
    return (bytes_read[0] << 8) | bytes_read[1]


def parse_app0(f: BinaryIO, length: int, metadata: JPEGMetadata) -> None:
    """Parse APP0 (JFIF) segment and store in metadata.app_info."""
    # length includes the 2 bytes for length field itself, so data is length - 2
    # Identifier: 5 bytes (e.g., "JFIF\0")
    metadata.app_info.identifier = f.read(5)
    # Version: 2 bytes (major, minor)
    metadata.app_info.version_major_id = read_u8(f)
    metadata.app_info.version_minor_id = read_u8(f)
    # Units: 1 byte (0=no units, 1=dots per inch, 2=dots per cm)
    metadata.app_info.units = read_u8(f)
    # X density: 2 bytes
    metadata.app_info.x_density = read_u16(f)
    # Y density: 2 bytes
    metadata.app_info.y_density = read_u16(f)
    # X thumbnail: 1 byte
    metadata.app_info.x_thumbnail = read_u8(f)
    # Y thumbnail: 1 byte
    metadata.app_info.y_thumbnail = read_u8(f)
    # Skip thumbnail data if any (length - 2 - 14 = remaining bytes)
    thumbnail_size = metadata.app_info.x_thumbnail * metadata.app_info.y_thumbnail * 3
    if thumbnail_size > 0:
        f.read(thumbnail_size)


def parse_dqt(f: BinaryIO, length: int, metadata: JPEGMetadata) -> None:
    """Parse DQT (Define Quantization Table) segment."""
    # length includes the 2 bytes for length field, so data is length - 2
    bytes_remaining = length - 2
    
    while bytes_remaining > 0:
        # Table info: 1 byte (upper 4 bits = precision, lower 4 bits = table ID)
        table_info = read_u8(f)
        bytes_remaining -= 1
        
        precision = (table_info >> 4) & 0x0F  # 0 = 8-bit, 1 = 16-bit
        table_id = table_info & 0x0F
        
        # Read 64 quantization values
        if precision == 0:
            # 8-bit precision: 64 bytes
            for i in range(64):
                metadata.quantization_tables[table_id][i] = float(read_u8(f))
            bytes_remaining -= 64
        else:
            # 16-bit precision: 128 bytes
            for i in range(64):
                metadata.quantization_tables[table_id][i] = float(read_u16(f))
            bytes_remaining -= 128


def parse_dht(f: BinaryIO, length: int, metadata: JPEGMetadata) -> None:
    """Parse DHT (Define Huffman Table) segment."""
    # length includes the 2 bytes for length field, so data is length - 2
    bytes_remaining = length - 2
    
    while bytes_remaining > 0:
        # Table info: 1 byte (bit 4 = AC/DC, bits 0-3 = table ID)
        table_info = read_u8(f)
        bytes_remaining -= 1
        
        table_class = (table_info >> 4) & 0x0F  # 0 = DC, 1 = AC
        table_id = table_info & 0x0F
        
        # Read 16 bytes: number of codes for each bit length (1-16)
        code_counts = []
        for _ in range(16):
            code_counts.append(read_u8(f))
        bytes_remaining -= 16
        
        # Build Huffman table: (bit_length, code) -> symbol
        # Read symbols and assign codes
        code = 0
        huffman_dict = {}
        
        for bit_length in range(16):
            num_codes = code_counts[bit_length]
            for _ in range(num_codes):
                symbol = read_u8(f)
                bytes_remaining -= 1
                # Store mapping: (bit_length + 1, code) -> symbol
                huffman_dict[(bit_length + 1, code)] = symbol
                code += 1
            # Shift code left for next bit length
            code <<= 1
        
        # Store in appropriate table
        if table_class == 0:
            metadata.huffman_tables.dc_tables[table_id] = huffman_dict
        else:
            metadata.huffman_tables.ac_tables[table_id] = huffman_dict


def parse_sof0(f: BinaryIO, length: int, metadata: JPEGMetadata) -> None:
    """Parse SOF0 (Start of Frame - Baseline DCT) segment."""
    # Precision: 1 byte (bits per sample, usually 8)
    metadata.sof_info.precision = read_u8(f)
    # Height: 2 bytes
    metadata.sof_info.height = read_u16(f)
    # Width: 2 bytes
    metadata.sof_info.width = read_u16(f)
    # Number of components: 1 byte (usually 3 for YCbCr)
    num_components = read_u8(f)
    
    max_h_sampling = 0
    max_v_sampling = 0
    
    # For each component: 3 bytes
    for i in range(num_components):
        # Component ID: 1 byte (usually 1=Y, 2=Cb, 3=Cr)
        component_id = read_u8(f)
        # Sampling factors: 1 byte (upper 4 bits = horizontal, lower 4 bits = vertical)
        sampling = read_u8(f)
        h_sampling = (sampling >> 4) & 0x0F
        v_sampling = sampling & 0x0F
        # Quantization table ID: 1 byte
        quant_table_id = read_u8(f)
        
        # Store component info (component_id is 1-indexed, array is 0-indexed)
        idx = component_id - 1
        if 0 <= idx < 3:
            metadata.sof_info.components[idx].horizontal_sampling = h_sampling
            metadata.sof_info.components[idx].vertical_sampling = v_sampling
            metadata.sof_info.components[idx].quantization_table_id = quant_table_id
        
        # Track max sampling factors
        max_h_sampling = max(max_h_sampling, h_sampling)
        max_v_sampling = max(max_v_sampling, v_sampling)
    
    metadata.sof_info.max_horizontal_sampling = max_h_sampling
    metadata.sof_info.max_vertical_sampling = max_v_sampling


def parse_sos(f: BinaryIO, length: int, metadata: JPEGMetadata) -> None:
    """Parse SOS (Start of Scan) segment."""
    # Number of components in scan: 1 byte
    num_components = read_u8(f)
    
    # For each component: 2 bytes
    for i in range(num_components):
        # Component selector: 1 byte (component ID)
        component_id = read_u8(f)
        # Table mapping: 1 byte (upper 4 bits = DC table, lower 4 bits = AC table)
        table_mapping = read_u8(f)
        dc_table_id = (table_mapping >> 4) & 0x0F
        ac_table_id = table_mapping & 0x0F
        
        # Store mapping (component_id is 1-indexed, array is 0-indexed)
        idx = component_id - 1
        if 0 <= idx < 3:
            metadata.table_mapping[idx] = (dc_table_id, ac_table_id)
    
    # Skip spectral selection and approximation (3 bytes)
    # Start of spectral selection: 1 byte
    # End of spectral selection: 1 byte
    # Successive approximation: 1 byte
    f.read(3)


def marker_detector(path: str | Path, metadata: JPEGMetadata = None) -> JPEGMetadata:
    """
    Detect JPEG markers and parse segment data into metadata.
    
    Args:
        path: Path to the JPEG file
        metadata: Optional JPEGMetadata instance to populate (creates new if None)
    
    Returns:
        Populated JPEGMetadata instance
    """
    if metadata is None:
        metadata = JPEGMetadata()
    
    with open(path, "rb") as f:
        while True:
            byte = f.read(1)
            if not byte:
                break  # End of file

            if byte[0] != 0xFF:
                continue  # Not a marker start

            marker_byte = f.read(1)
            if not marker_byte:
                break  # End of file
            marker = marker_byte[0]

            if marker == 0x00:
                continue  # Stuffed byte, not a marker
            elif marker == 0xD8:  # SOI
                print("Found SOI (Start of Image)")
            elif marker == 0xD9:  # EOI
                print("Found EOI (End of Image)")
                break
            else:
                length = read_u16(f)
                print(f"Found {marker_info(marker)} with length {length} bytes")
                
                # Parse segment data based on marker type
                if marker == 0xE0:  # APP0
                    parse_app0(f, length, metadata)
                elif marker == 0xDB:  # DQT
                    parse_dqt(f, length, metadata)
                elif marker == 0xC4:  # DHT
                    parse_dht(f, length, metadata)
                elif marker == 0xC0:  # SOF0
                    parse_sof0(f, length, metadata)
                elif marker == 0xDA:  # SOS
                    parse_sos(f, length, metadata)
                else:
                    # Skip unknown segments
                    f.read(length - 2)

    return metadata
            