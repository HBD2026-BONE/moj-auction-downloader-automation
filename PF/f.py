import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth
import ddddocr

# ==========================================
# ⚙️ 參數設定區 (請在這裡直接修改內容)
# ==========================================
THE_USE_TEXT = "汽機車"          # 種類：例如 "汽車"、"機車"、"股票"
DEPT_TEXT = "新竹分署"         # 分署：例如 "台北分署"、"新北分署"、"台中分署"
DATE_START = "2024/01/01"     # 拍賣日期-起
DATE_END = "2026/12/31"       # 拍賣日期-迄
# ==========================================

def run_fix_filler():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 啟動瀏覽器
    driver = webdriver.Chrome(options=chrome_options)
    
    # 隱藏自動化偵測特徵
    stealth(driver, languages=["zh-TW", "en"], vendor="Google Inc.", platform="Win32",
            webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)

    ocr = ddddocr.DdddOcr(show_ad=False)
    wait = WebDriverWait(driver, 20) 

    try:
        # 1. 進入法務部動產拍賣頁面
        driver.get("https://www.tpkonsale.moj.gov.tw/Chattel")
        print(f"[*] 正在查詢: {DEPT_TEXT} 的 {THE_USE_TEXT} 資料...")
        
        # 重要：強制等待網頁選單選取項載入
        time.sleep(3)

        # 2. 選擇「種類」 (THE_USE)
        kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE")))
        kind_select = Select(kind_el)
        try:
            kind_select.select_by_visible_text(THE_USE_TEXT)
        except:
            print(f"[!] 無法選取 '{THE_USE_TEXT}'，改嘗試選取第 2 個選項")
            kind_select.select_by_index(1) 

        # 3. 選擇「分署」 (EXEC_DEPT_ID)
        dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
        dept_select = Select(dept_el)
        try:
            dept_select.select_by_visible_text(DEPT_TEXT)
        except:
            print(f"[!] 無法選取 '{DEPT_TEXT}'，改用代碼選取")
            dept_select.select_by_value("SCY001") # 預設新竹代碼
        
        # 4. 填寫日期範圍
        driver.find_element(By.ID, "OPEN_BID_TIME_S").send_keys(DATE_START)
        driver.find_element(By.ID, "OPEN_BID_TIME_E").send_keys(DATE_END)
        print(f"-> 已填寫日期: {DATE_START} 至 {DATE_END}")

        # 5. 處理驗證碼 (CaptchaImage)
        captcha_img = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
        captcha_bytes = captcha_img.screenshot_as_png
        captcha_text = ocr.classification(captcha_bytes)
        print(f"-> 驗證碼辨識結果: {captcha_text}")

        # 6. 輸入驗證碼 (CAPTCHA)
        driver.find_element(By.ID, "CAPTCHA").send_keys(captcha_text)

        # 7. 點擊查詢按鈕 (btnQuery)
        time.sleep(1)
        query_btn = driver.find_element(By.ID, "btnQuery")
        # 使用 JS 點擊最保險，避免被頁面元素遮擋
        driver.execute_script("arguments[0].click();", query_btn)
        print("[*] 查詢已送出！")

        # 停留一段時間讓你確認網頁結果
        time.sleep(15)

    except Exception as e:
        print(f"\n[X] 執行過程中發生錯誤: {e}")
    
    finally:
        input("\n任務結束，按 Enter 鍵將關閉瀏覽器...")
        driver.quit()

if __name__ == "__main__":
    run_fix_filler()