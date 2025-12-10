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
from pathlib import Path

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

def read_u16(f) -> int:
    
    bytes_read = f.read(2)
    if len(bytes_read) != 2:
        raise IOError("Unexpected length while reading 2 bytes")
    
    return (bytes_read[0] << 8) | bytes_read[1]

def marker_detector(path: str | Path):
    
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

    return
            