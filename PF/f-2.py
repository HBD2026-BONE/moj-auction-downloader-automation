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
# ⚙️ 參數設定區 (一格一格修改這裡)
# ==========================================
BRAVE_PATH = r"C:\Users\姍姍來遲\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"

THE_USE_VALUE = "1"           # 種類：1=汽機車, 2=股票, 3=其他
DEPT_VALUE = "SCY001"         # 分署：SCY001=新竹, TPY001=台北 (請見下方說明)
DATE_START = "2024/01/01"     # 拍賣日期-起
DATE_END = "2026/12/31"       # 拍賣日期-迄
# ==========================================

def run_fix_filler():
    chrome_options = Options()
    chrome_options.binary_location = BRAVE_PATH
    
    # 加入穩定啟動參數
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        print("[*] 正在啟動 Brave 瀏覽器...")
        driver = webdriver.Chrome(options=chrome_options)
        
        stealth(driver, languages=["zh-TW", "en"], vendor="Google Inc.", platform="Win32",
                webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)

        ocr = ddddocr.DdddOcr(show_ad=False)
        wait = WebDriverWait(driver, 30) 

        # 🚀 延遲啟動以穩定連線
        time.sleep(5)
        driver.get("https://www.tpkonsale.moj.gov.tw/Chattel")
        print("[*] 頁面載入中...")
        time.sleep(3)

        # 1. 選擇種類 (根據截圖 ID="THE_USE")
        kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE")))
        # 改用 value 選取更精準 (1=汽機車)
        Select(kind_el).select_by_value(THE_USE_VALUE)
        print(f"-> 種類已選: {THE_USE_VALUE}")

        # 2. 選擇分署 (根據截圖 ID="EXEC_DEPT_ID")
        dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
        Select(dept_el).select_by_value(DEPT_VALUE)
        print(f"-> 分署已選: {DEPT_VALUE}")
        
        # 3. 填寫日期 (根據截圖 ID="OPEN_BID_TIME_S" / "OPEN_BID_TIME_E")
        driver.find_element(By.ID, "OPEN_BID_TIME_S").send_keys(DATE_START)
        driver.find_element(By.ID, "OPEN_BID_TIME_E").send_keys(DATE_END)
        print("-> 日期填寫完成")

        # 4. 驗證碼處理
        captcha_img = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
        captcha_bytes = captcha_img.screenshot_as_png
        
        # 辨識並強制轉大寫
        raw_text = ocr.classification(captcha_bytes)
        captcha_text = raw_text.upper() 
        print(f"-> AI 辨識: {raw_text} -> 輸入大寫: {captcha_text}")

        # 5. 輸入驗證碼 (ID="CAPTCHA")
        captcha_input = driver.find_element(By.ID, "CAPTCHA")
        captcha_input.clear()
        captcha_input.send_keys(captcha_text)
        
        # 6. 點擊查詢按鈕 (根據截圖 <a> 標籤且 name="doQueryData")
        time.sleep(1)
        # 因為是 <a> 標籤，我們改用 name 屬性來定位
        query_btn = driver.find_element(By.NAME, "doQueryData")
        driver.execute_script("arguments[0].click();", query_btn)
        print("[*] 查詢提交成功！")

        time.sleep(15)

    except Exception as e:
        print(f"\n[X] 發生錯誤: {e}")
    
    finally:
        if driver:
            input("\n任務結束，按 Enter 關閉瀏覽器...")
            driver.quit()

if __name__ == "__main__":
    run_fix_filler()