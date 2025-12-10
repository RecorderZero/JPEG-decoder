import numpy as np
import math

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
        \\\\\ METHOD: Compute inverse DCT of x
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

def inverse_zigzag_scan(flat_array, block_size=8):
    block = np.zeros((block_size, block_size), dtype=np.float64)
    index = 0
    for i in range(15): # 0 to 14 (對角線數量)
        if i < 8:
            for j in range(i + 1):
                if i % 2 == 0:
                    block[i - j][j] = flat_array[index]
                else:
                    block[j][i - j] = flat_array[index]
                index += 1
        else:
            for j in range(15 - i):
                if i % 2 == 0:
                    block[7 - j][j + (i - 7)] = flat_array[index]
                else:
                    block[j + (i - 7)][7 - j] = flat_array[index]
                index += 1
    return block
