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
# ⚙️ 參數設定區 
# ==========================================
BRAVE_PATH = r"C:\Users\姍姍來遲\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"

THE_USE_TEXT = "汽機車"         # 種類
DEPT_TEXT = "新竹分署"          # 分署
DATE_START = "2024/01/01"      # 拍賣日期-起
DATE_END = "2026/12/31"        # 拍賣日期-迄
# ==========================================

def run_fix_filler():
    chrome_options = Options()
    chrome_options.binary_location = BRAVE_PATH
    
    # 加入穩定連線的參數，防止第一次執行連線中斷
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222") # 穩定 Debug 連線
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        print("[*] 正在嘗試啟動 Brave 瀏覽器...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # 隱藏特徵
        stealth(driver, languages=["zh-TW", "en"], vendor="Google Inc.", platform="Win32",
                webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)

        ocr = ddddocr.DdddOcr(show_ad=False)
        wait = WebDriverWait(driver, 30) 

        # 🚀 解決第一次噴錯：給瀏覽器更多時間初始化
        print("[*] 瀏覽器已啟動，等待 5 秒後連線網址...")
        time.sleep(5)
        
        driver.get("https://www.tpkonsale.moj.gov.tw/Chattel")
        print(f"[*] 成功進入網頁，正在查詢: {DEPT_TEXT}...")
        
        # 等待選單選項加載
        time.sleep(3)

        # 1. 選擇種類
        kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE")))
        Select(kind_el).select_by_visible_text(THE_USE_TEXT)

        # 2. 選擇分署
        dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
        Select(dept_el).select_by_visible_text(DEPT_TEXT)
        
        # 3. 填寫日期
        driver.find_element(By.ID, "OPEN_BID_TIME_S").send_keys(DATE_START)
        driver.find_element(By.ID, "OPEN_BID_TIME_E").send_keys(DATE_END)

        # 4. 驗證碼處理 
        captcha_img = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
        captcha_bytes = captcha_img.screenshot_as_png
        
        # 辨識結果
        raw_text = ocr.classification(captcha_bytes)
        
        # 【關鍵修改】：強制把辨識結果轉為「全大寫」
        captcha_text = raw_text.upper() 
        print(f"-> AI 原本抓到: {raw_text}")
        print(f"-> 最終輸入大寫: {captcha_text}")

        # 5. 輸入驗證碼
        captcha_input = driver.find_element(By.ID, "CAPTCHA")
        captcha_input.clear()
        captcha_input.send_keys(captcha_text) # 這裡送出的單字絕對是大寫
        
        # 6. 點擊查詢
        time.sleep(1)
        # 根據截圖，該按鈕的 name 屬性為 "doQueryData"
        query_btn = driver.find_element(By.NAME, "doQueryData") 
        driver.execute_script("arguments[0].click();", query_btn)
        print("[*] 查詢提交成功！")

        # 查詢結果停留時間
        time.sleep(15)

    except Exception as e:
        print(f"\n[X] 發生錯誤: {e}")
    
    finally:
        if driver:
            input("\n任務結束, 按 Enter 鍵關閉瀏覽器...")
            driver.quit()

if __name__ == "__main__":
    run_fix_filler()