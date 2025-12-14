import cv2
import numpy as np
import math
import os

def calculate_psnr(img1, img2):
    """
    計算兩張圖片的 PSNR (Peak Signal-to-Noise Ratio)
    """
    # 1. 轉換為 float64 以防止平方運算溢位
    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)

    # 2. 計算 MSE (Mean Squared Error)
    mse = np.mean((img1 - img2) ** 2)

    # 3. 若 MSE 為 0，代表兩張圖完全一樣 (PSNR 為無限大)
    if mse == 0:
        return float('inf')

    # 4. 計算 PSNR (像素最大值為 255)
    psnr = 20 * math.log10(255.0 / math.sqrt(mse))
    return psnr

def cal(path):
    # ================= 設定路徑 =================
    # 原始的 JPG 檔案 (你的輸入檔)
    original_jpg_path = str(path)
    
    # 你手寫 Decoder 產出的檔案 (可能是 ppm 或轉成的 png)
    my_decoder_output_path = "out.png" 
    
    # OpenCV 解碼結果的儲存路徑 (作為對照組 Ground Truth)
    opencv_output_save_path = "opencv_ground_truth.png"
    # ===========================================

    # 1. 讀取圖片
    if not os.path.exists(original_jpg_path) or not os.path.exists(my_decoder_output_path):
        print("錯誤：找不到輸入檔案，請檢查路徑。")
        return

    # OpenCV 預設讀入格式為 BGR
    img_gt = cv2.imread(original_jpg_path)       # Ground Truth (OpenCV)
    img_my = cv2.imread(my_decoder_output_path)  # 你的實作結果

    print(f"原始圖 (OpenCV) 尺寸: {img_gt.shape}")
    print(f"你的圖 (Custom) 尺寸: {img_my.shape}")

    # 2. 儲存 OpenCV 解碼的結果 (作為報告用的對照圖)
    cv2.imwrite(opencv_output_save_path, img_gt)
    print(f"已儲存 OpenCV 解碼結果至: {opencv_output_save_path}")

    # 3. 處理尺寸不合的問題 (MCU Padding)
    # 你的解碼器可能會因為 MCU 對齊而讓圖片稍微大一點點 (例如多了幾行/列的黑邊)
    # 這裡我們取兩者中較小的長寬進行裁切，只比較有效區域
    h_gt, w_gt, _ = img_gt.shape
    h_my, w_my, _ = img_my.shape

    min_h = min(h_gt, h_my)
    min_w = min(w_gt, w_my)

    if h_gt != h_my or w_gt != w_my:
        print(f"\n注意：尺寸不一致，將裁切至重疊區域 ({min_w}x{min_h}) 進行比較...")
        img_gt = img_gt[:min_h, :min_w]
        img_my = img_my[:min_h, :min_w]

    # 4. 計算 PSNR
    psnr_score = calculate_psnr(img_gt, img_my)

    # 5. 輸出結果與評語
    print("-" * 30)
    print(f"計算結果 PSNR: {psnr_score:.4f} dB")
    print("-" * 30)

    if psnr_score == float('inf'):
        print("評級：完美 (Perfect)")
        print("說明：兩張圖片像素完全一致。")
    elif psnr_score > 40:
        print("評級：極優 (Excellent)")
        print("說明：肉眼幾乎無法分辨差異，演算法實作非常精確。")
    elif psnr_score > 30:
        print("評級：良好 (Good)")
        print("說明：有一些細微差異 (可能是浮點數運算或 IDCT 精度誤差)，但在可接受範圍。")
    elif psnr_score > 20:
        print("評級：普通 (Acceptable)")
        print("說明：圖片內容可辨識，但有明顯雜訊或色偏。請檢查 RGB 轉換公式或 Zigzag 順序。")
    else:
        print("評級：失敗 (Fail)")
        print("說明：差異過大。請檢查：")
        print("  1. RGB/BGR 是否搞反了？ (OpenCV 是 BGR，你的輸出是 RGB 嗎？)")
        print("  2. 是否發生位元位移 (Bit shift)？")
        print("  3. IDCT 係數是否正確反量化？")

    # (Optional) 產生差異圖，方便 Debug
    # 計算絕對差異值
    diff = cv2.absdiff(img_gt, img_my)
    # 將差異放大 10 倍以便肉眼觀察 (黑色代表沒差異，越亮代表差異越大)
    diff_amplified = diff * 10 
    cv2.imwrite("diff_map.png", diff_amplified)
    print("已產生差異圖: diff_map.png (亮度已放大 10 倍以利觀察)")
