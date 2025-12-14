import numpy as np
import math
from .reader import data_reader
from .image import Image, Color

class IDCT_1D():
    """
    1-D DCT
    """
    def __init__(self, x):
        """
        input time-domain signal x
        """
        self.F = x
        # self.M = np.shape(x)[0]
        self.N = np.shape(x)[0]

    def solve(self):
        """
        METHOD: Compute inverse DCT of x
        """
        f = np.zeros(self.N, dtype=np.float64)
        for x in range(self.N):
                sumuv =0
                for u in range(self.N):
                    if u==0:
                       sumuv += (1/(math.sqrt(2)))* self.F[u]*math.cos((2*x+1)*u*math.pi/(2*self.N))
                    else:
                       sumuv +=  self.F[u]*math.cos((2*x+1)*u*math.pi/(2*self.N))
                # 最終結果
                f[x]= math.sqrt(2/self.N) *sumuv   
        return f
class IDCT_2D_RowColumn():
    """
    使用行-列法 (Row-Column Method) 實作 2-D IDCT。
    """
    def __init__(self, x):
        self.F = x # 輸入是 DCT 係數矩陣
        self.N = np.shape(x)[0]

    def solve(self):
        N = self.N
        
        # 步驟一: 對每一行進行 1D IDCT
        # G 是儲存中間結果的矩陣
        G = np.zeros([N, N], dtype=np.float64)
        
        for row_idx in range(N):
            input_row = self.F[row_idx, :]
            idct_solver_1d = IDCT_1D(input_row)
            row_reconstruction = idct_solver_1d.solve()
            G[row_idx, :] = row_reconstruction
            
        
        # 步驟二: 對中間矩陣 G 的每一列進行 1D IDCT
        f = np.zeros([N, N], dtype=np.float64)
        
        for col_idx in range(N):
            input_column = G[:, col_idx]
            idct_solver_1d = IDCT_1D(input_column)
            column_reconstruction = idct_solver_1d.solve()
            f[:, col_idx] = column_reconstruction
            
        return f
ZZ = [
    [ 0,  1,  5,  6, 14, 15, 27, 28],
    [ 2,  4,  7, 13, 16, 26, 29, 42],
    [ 3,  8, 12, 17, 25, 30, 41, 43],
    [ 9, 11, 18, 24, 31, 40, 44, 53],
    [10, 19, 23, 32, 39, 45, 52, 54],
    [20, 22, 33, 38, 46, 51, 55, 60],
    [21, 34, 37, 47, 50, 56, 59, 61],
    [35, 36, 48, 49, 57, 58, 62, 63]
]

class MCUWrap():
    def __init__(self, MCU,jpeg_meta_data):
        self.mcu = MCU
        self.jpeg_meta_data = jpeg_meta_data
    def display(self): 
        sof_info = self.jpeg_meta_data.sof_info
        component_infos = sof_info.components
        m = ["Y", "Cb", "Cr"]
        for id in range(3): 
            c_info = component_infos[id]
            for h in range(c_info.vertical_sampling) :
                for w in range(c_info.horizontal_sampling) :
                    print("------ {} 顏色分量 {} {} ------", m[id], h, w)
                    block = self.mcu[id][h][w]
                    for i in range(8):
                        for j in range(8) :
                            print("{} ", block[i][j])
                        
                        print("")
                   
    
    def inverse_zigzag_scan(self):
        """
        對整個 MCU 進行反向 Zig-Zag 掃描 (De-Zigzag)。
        將 read_mcu 讀出的線性順序(填充在8x8中)轉換為正確的空間順序。
        """
        
        # 遍歷 3 個 component (Y, Cb, Cr)
        for i in range(len(self.mcu)):
            # 遍歷垂直方向 blocks
            for v in range(len(self.mcu[i])):
                # 遍歷水平方向 blocks
                for h in range(len(self.mcu[i][v])):
                    
                    # 取得目前尚未排列正確的 block (Raw Block)
                    # 在 read_mcu 中，資料是依照 zigzag 順序直接填入 array 的
                    raw_block = self.mcu[i][v][h]
                    
                    # 建立一個新的暫存 block 用來存放正確空間順序的係數
                    tmp = [[0.0] * 8 for _ in range(8)]
                    
                    # 使用查表法重新排列
                    for r in range(8):
                        for c in range(8):
                            # 邏輯：查表得知 (r,c) 這個位置在 ZigZag 序列是第幾個 (z_index)
                            # 然後去 raw_block 中把那個順序的值抓出來
                            z_index = ZZ[r][c]
                            tmp[r][c] = raw_block[z_index // 8][z_index % 8]
                    
                    # 將排列好的 block 放回 MCU
                    self.mcu[i][v][h] = tmp
                    
    def dequantize(self):
        """
        對應 Rust: MCUWrap::dequantize
        對 MCU 內的每個 Block 進行反量化。
        """
        sof = self.jpeg_meta_data.sof_info
        
        # 遍歷 Component
        for i in range(len(self.mcu)):
            # 取得該 Component 的 Quantization Table
            # comp_id = sof.components[i]
            q_table_id = sof.components[i].quantization_table_id
            quant_table = self.jpeg_meta_data.quantization_tables[q_table_id]
                    
            for v in range(len(self.mcu[i])):
                for h in range(len(self.mcu[i][v])):
                    # In-place 修改
                    for r in range(8):
                        for c in range(8):
                            self.mcu[i][v][h][r][c] *= quant_table[r * 8 + c]
        # return mcu
    def idct(self):
        """
        對應 Rust: MCUWrap::idct
        對 MCU 內的每個 Block 進行 IDCT。
        """
        for i in range(len(self.mcu)):
            for v in range(len(self.mcu[i])):
                for h in range(len(self.mcu[i][v])):
                    # 取出 Block (這是 List[List]) 轉成 Numpy 以利運算
                    block_data = np.array(self.mcu[i][v][h])
                    
                    # 呼叫你原本寫好的 2D IDCT Solver
                    solver = IDCT_2D_RowColumn(block_data)
                    pixels = solver.solve()
                    
                    # 存回 MCU (轉回 List 或是保持 Numpy 都可以，看 mcu_to_rgb 怎麼接)
                    self.mcu[i][v][h] = pixels
        
    def decode(self):
        self.dequantize()
        self.inverse_zigzag_scan()
        self.idct()
    def show_all_stage(self): 
        print("---------------- 未經處理 ----------------")
        self.display()
        self.dequantize()
        print("---------------- 反量化之後 ----------------")
        self.display()
        self.inverse_zigzag_scan()
        print("---------------- zigzag 之後 ----------------")
        self.display()
        self.idct()
        print("---------------- 反向餘弦變換之後 ----------------")
        self.display()
    

    def toRGB(self):
        self.decode()

        sof_info = self.jpeg_meta_data.sof_info
        component_infos = sof_info.components
        max_vertical_sampling = sof_info.max_vertical_sampling 
        max_horizontal_sampling = sof_info.max_horizontal_sampling 
        mcu_height = 8 * max_vertical_sampling 
        mcu_width = 8 * max_horizontal_sampling 

        ret = [[Color.RGB(0, 0, 0) for _ in range(int(mcu_width))] for _ in range(int(mcu_height))]
        for i in range(mcu_height): 
            for j in range(mcu_width): 
                # // 獲取 Y, Cb, Cr 三個顏色分量所對應的採樣
                YCbCr = [0.0, 0.0, 0.0]
                for id in range(3) :
                    vh = int(i * component_infos[id].vertical_sampling / max_vertical_sampling)
                    vw = int(j * component_infos[id].horizontal_sampling / max_horizontal_sampling)
                    YCbCr[id] = self.mcu[id][vh //8][vw // 8][vh % 8][vw % 8] 
                
                Y, Cb, Cr = YCbCr[0], YCbCr[1], YCbCr[2]
                # // let (Y, Cb, Cr) = (YCbCr[0], 0.0, 0.0) 
                R = chomp(Y + 1.402*Cr + 128.0) 
                G = chomp(Y - 0.34414*Cb - 0.71414*Cr + 128.0) 
                B = chomp(Y + 1.772*Cb + 128.0) 
                ret[i ][j] = Color.RGB(R, G, B) 
            
        
        return ret 


def chomp(val):
    """ 將數值限制在 [0, 255] 並轉為整數 """
    return int(max(0, min(255, round(val))))



def decoder(filepath):
    with open(filepath, 'rb') as f:
        jpeg_meta_data, MCUs = data_reader(f)
        f.close()

        sof_info = jpeg_meta_data.sof_info
        mcu_width = 8 * sof_info.max_horizontal_sampling 
        mcu_height = 8 * sof_info.max_vertical_sampling 

        # // 寬度上有幾個 MCU
        mcu_width_number = int((sof_info.width- 1) / mcu_width + 1) 
        # // 高度上有幾個 MCU
        mcu_height_number = int((sof_info.height - 1) / mcu_height + 1) 

        image_width = int(mcu_width_number * mcu_width)
        image_height = int(mcu_height_number * mcu_height) 
        img = Image.new(image_width, image_height)

        for h in range(mcu_height_number) :
            for w in range(mcu_width_number) :
                mcu = MCUs[h][w].copy()
                mcu_rgb = MCUWrap(mcu, jpeg_meta_data).toRGB()
                for y in range(mcu_height) :
                    for x in range(mcu_width) :
                        img.pixels[h*mcu_height + y][w*mcu_width + x] = mcu_rgb[y][x]
                   
        return img


def show_mcu_stage(reader, h, w):
    with open(reader, 'rb') as f:
        
        jpeg_meta_data, MCUs= data_reader(f)
        f.close()
        mcu = MCUs[h][w].copy()
        mcu_wrap = MCUWrap(mcu, jpeg_meta_data)
        mcu_wrap.show_all_stage()

