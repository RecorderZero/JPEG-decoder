from typing import List
from image import Image

def to_ppm(image: Image, filename: str = "out.ppm") -> None:
    """將 Image 物件寫入 PPM 檔案 (P6 格式)"""
    print(f"Writing to {filename}...")
    
    with open(filename, "wb") as f:
        # 1. 寫入 Header
        # P6 <換行> 寬 高 <換行> 最大值 <換行>
        header = f"P6\n{image.width} {image.height}\n255\n"
        f.write(header.encode('ascii'))
        
        # 2. 寫入像素數據
        # Image.pixels 是 [row][col] 的 Color 物件
        for row in image.pixels:
            for pixel in row:
                # 確保數值在 0-255 之間 (雖然 Color 應該要是 int，但保險起見)
                r = max(0, min(255, int(pixel.r)))
                g = max(0, min(255, int(pixel.g)))
                b = max(0, min(255, int(pixel.b)))
                f.write(bytes([r, g, b]))
                
    print("Done.")