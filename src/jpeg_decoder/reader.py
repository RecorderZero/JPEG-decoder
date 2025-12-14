from __future__ import annotations
from typing import List, Tuple, Dict, BinaryIO
import struct

from .primitives import JPEGMetadata, MCU, Block, HuffmanTable
from .marker import (
    read_u8, read_u16, 
    parse_dqt, parse_dht, parse_sof0, parse_sos, parse_app0
)

# 定義 Marker 常數
MARKER_PREFIX = 0xFF
SOI_MARKER = 0xD8
EOI_MARKER = 0xD9
APP0_MARKER = 0xE0
DQT_MARKER = 0xDB
DHT_MARKER = 0xC4
SOF0_MARKER = 0xC0
SOS_MARKER = 0xDA

class BitStream:
    """處理位元流讀取與 Byte Stuffing (0xFF00)"""
    def __init__(self, f: BinaryIO):
        self.f = f
        self.current_byte = 0
        self.bit_count = 0  # 目前這個 byte 剩幾個 bit 還沒讀
        # 用來記錄每個 component 的上一個 DC 值 (Y, Cb, Cr)
        self.last_dc = [0.0, 0.0, 0.0] 

    def get_bit(self) -> int:
        if self.bit_count == 0:
            # 讀取一個新的 byte
            b_data = self.f.read(1)
            if not b_data:
                raise EOFError("Unexpected End of Stream")
            
            self.current_byte = b_data[0]
            
            # 處理 JPEG 的 Byte Stuffing：如果讀到 0xFF，後面必須是 0x00
            if self.current_byte == 0xFF:
                check_byte = self.f.read(1)
                if check_byte and check_byte[0] != 0x00:
                    # 在標準 JPEG 中，Entropy 數據裡的 0xFF 後面一定是 0x00
                    # 如果不是，通常代表數據流結束或遇到 RST 標記
                    # 這裡簡化處理，視為錯誤或略過
                    print(f"Warning: 0xFF followed by {hex(check_byte[0])} inside bitstream")
            
            self.bit_count = 8

        # 取出最高位 (Big Endian)
        bit = (self.current_byte >> (self.bit_count - 1)) & 1
        self.bit_count -= 1
        return bit

    def match_huffman(self, table: Dict[Tuple[int, int], int]) -> int:
        """根據霍夫曼表讀取下一個符號"""
        code = 0
        length = 0
        while length < 16:
            length += 1
            code = (code << 1) | self.get_bit()
            
            if (length, code) in table:
                return table[(length, code)]
        
        raise ValueError(f"Huffman decoding failed. Code: {bin(code)}")

    def read_value(self, length: int) -> float:
        """讀取指定長度的數值 (處理正負號)"""
        if length == 0:
            return 0.0
        
        first_bit = self.get_bit()
        val = 1  # 這裡只是一個 placeholder，實際邏輯如下
        
        # 已經讀了 1 bit
        current_val = first_bit
        for _ in range(length - 1):
            current_val = (current_val << 1) | self.get_bit()
            
        # 判斷正負：若首位是 1，則是正數；若首位是 0，則需要轉換
        # JPEG 的規則：如果是負數，其值為 (val - (2^length - 1))
        if first_bit == 1:
            return float(current_val)
        else:
            return float(current_val - ((1 << length) - 1))

    def read_dc(self, table: Dict[Tuple[int, int], int], component_id: int) -> float:
        length = self.match_huffman(table)
        if length == 0:
            diff = 0.0
        else:
            diff = self.read_value(length)
        
        # DC 值是累加的
        self.last_dc[component_id] += diff
        return self.last_dc[component_id]

    def read_ac(self, table: Dict[Tuple[int, int], int]) -> Tuple[int, float]:
        """回傳 (前面的 0 的個數, 數值)"""
        s = self.match_huffman(table)
        
        if s == 0x00:
            return (-1, 0.0) # EOB (End of Block)
        elif s == 0xF0:
            return (16, 0.0) # ZRL (16 zeros)
        else:
            num_zeros = s >> 4
            category = s & 0x0F
            val = self.read_value(category)
            return (num_zeros, val)

def read_mcu(bit_stream: BitStream, metadata: JPEGMetadata) -> MCU:
    # 建立一個空的 MCU 結構: [Component][Block_Row][Block_Col] -> Block(8x8)
    mcu = [] 
    
    # 依序處理 Y, Cb, Cr 三個分量
    for i in range(3):
        comp_info = metadata.sof_info.components[i]
        h_samp = comp_info.horizontal_sampling
        v_samp = comp_info.vertical_sampling
        
        # 取得對應的 Huffman Table ID
        dc_table_id = metadata.table_mapping[i][0]
        ac_table_id = metadata.table_mapping[i][1]
        
        dc_table = metadata.huffman_tables.dc_tables[dc_table_id]
        ac_table = metadata.huffman_tables.ac_tables[ac_table_id]

        comp_data = [] # 儲存這個 component 下的所有 blocks

        for v in range(v_samp):
            row_blocks = []
            for h in range(h_samp):
                # 初始化 8x8 block
                block = [[0.0] * 8 for _ in range(8)]
                
                # 1. 讀取 DC
                block[0][0] = bit_stream.read_dc(dc_table, i)
                
                # 2. 讀取 AC
                idx = 1
                while idx < 64:
                    zeros, val = bit_stream.read_ac(ac_table)
                    
                    if zeros == -1: # EOB
                        break
                    
                    idx += zeros
                    if idx >= 64:
                        break
                        
                    block[idx // 8][idx % 8] = val
                    idx += 1
                
                row_blocks.append(block)
            comp_data.append(row_blocks)
        mcu.append(comp_data)
    
    return mcu

def read_mcus(f: BinaryIO, metadata: JPEGMetadata) -> List[List[MCU]]:
    """讀取所有 MCU"""
    sof = metadata.sof_info
    max_h = sof.max_horizontal_sampling
    max_v = sof.max_vertical_sampling
    
    # 計算 MCU 的網格數量
    mcu_width = 8 * max_h
    mcu_height = 8 * max_v
    
    w_mcus = (sof.width + mcu_width - 1) // mcu_width
    h_mcus = (sof.height + mcu_height - 1) // mcu_height
    
    print(f"Image Size: {sof.width}x{sof.height}")
    print(f"MCU Grid: {w_mcus}x{h_mcus}")
    
    bit_stream = BitStream(f)
    
    mcus = []
    for r in range(h_mcus):
        row_mcus = []
        for c in range(w_mcus):
            try:
                mcu = read_mcu(bit_stream, metadata)
                row_mcus.append(mcu)
            except Exception as e:
                print(f"Error reading MCU at ({r}, {c}): {e}")
                raise e
        mcus.append(row_mcus)
        
    return mcus

def data_reader(f: BinaryIO) -> Tuple[JPEGMetadata, List[List[MCU]]]:
    """主要的讀取入口"""
    metadata = JPEGMetadata()
    mcus = []
    
    while True:
        # 1. 讀取 0xFF
        b = f.read(1)
        if not b: 
            break
        if b[0] != MARKER_PREFIX:
            continue
            
        # 2. 讀取 Marker 類型
        b = f.read(1)
        if not b: 
            break
        marker = b[0]
        
        if marker == SOI_MARKER:
            print("SOI found")
        elif marker == EOI_MARKER:
            print("EOI found")
            break
        elif marker == 0x00:
            continue # stuffed byte
        else:
            # 讀取區段長度
            length = read_u16(f)
            print(f"Marker {hex(marker)} length {length}")
            
            if marker == APP0_MARKER:
                parse_app0(f, length, metadata)
            elif marker == DQT_MARKER:
                parse_dqt(f, length, metadata)
            elif marker == DHT_MARKER:
                parse_dht(f, length, metadata)
            elif marker == SOF0_MARKER:
                parse_sof0(f, length, metadata)
            elif marker == SOS_MARKER:
                parse_sos(f, length, metadata)
                # SOS 之後緊接著就是壓縮數據，開始解碼 MCU
                print("Start decoding MCUs...")
                mcus = read_mcus(f, metadata)
                # 讀完數據後通常就結束了，或者後面緊接 EOI
                # 我們這裡可以直接 break 或者繼續 loop 找 EOI
            else:
                # 跳過不支援的標記
                f.read(length - 2)
                
    return metadata, mcus