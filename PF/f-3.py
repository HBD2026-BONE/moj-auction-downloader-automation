import time
import random
import ddddocr
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# ==========================================
# ⚙️ 參數設定區 
# ==========================================
BRAVE_PATH = r"C:\Users\姍姍來遲\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"

THE_USE_TEXT = "汽機車"        # 種類
DEPT_INDEX = 2                 # 分署
DATE_START = "2024/01/01"      # 拍賣日期-起
DATE_END = "2026/12/31"        # 拍賣日期-迄

# 🚀 提前初始化 OCR，避免與瀏覽器啟動競爭資源
print("[*] 正在初始化 OCR 模型...")
ocr = ddddocr.DdddOcr(show_ad=False)
# ==========================================

def get_driver():
    """配置並啟動瀏覽器實例"""
    chrome_options = Options()
    chrome_options.binary_location = BRAVE_PATH
    
    # 基本穩定性參數
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # 啟動 Driver (若有特定 chromedriver 路徑可在此加入 Service)
    driver = webdriver.Chrome(options=chrome_options)
    
    # 隱藏自動化特徵
    stealth(driver, 
            languages=["zh-TW", "en"], 
            vendor="Google Inc.", 
            platform="Win32",
            webgl_vendor="Intel Inc.", 
            renderer="Intel Iris OpenGL Engine", 
            fix_hairline=True)
    return driver

def run_task():
    driver = None
    max_retries = 3  # 最大重試次數
    
    for attempt in range(max_retries):
        try:
            print(f"[*] 嘗試啟動第 {attempt + 1} 次...")
            driver = get_driver()
            wait = WebDriverWait(driver, 20)

            # 進入網頁
            driver.get("https://www.tpkonsale.moj.gov.tw/Chattel")
            
            # 檢查關鍵元素是否存在，確認頁面加載成功
            wait.until(EC.presence_of_element_located((By.ID, "THE_USE")))
            print(f"[*] 成功進入網頁，正在查詢: {DEPT_INDEX}...")

            # 1. 選擇種類
            kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE")))
            Select(kind_el).select_by_visible_text(THE_USE_TEXT)

            # 2. 選擇分署
            dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
            Select(dept_el).select_by_index(DEPT_INDEX)
            
            # 3. 填寫日期
            driver.find_element(By.ID, "OPEN_BID_TIME_S").send_keys(DATE_START)
            driver.find_element(By.ID, "OPEN_BID_TIME_E").send_keys(DATE_END)

            # 4. 驗證碼處理 
            captcha_img = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
            captcha_bytes = captcha_img.screenshot_as_png
            
            # 辨識並強制轉大寫
            captcha_text = ocr.classification(captcha_bytes).upper()
            print(f"-> 驗證碼識別結果: {captcha_text}")

            # 5. 輸入驗證碼
            captcha_input = driver.find_element(By.ID, "CAPTCHA")
            captcha_input.clear()
            captcha_input.send_keys(captcha_text)
            
            # 6. 點擊查詢
            time.sleep(0.5)
            query_btn = driver.find_element(By.NAME, "doQueryData") 
            driver.execute_script("arguments[0].click();", query_btn)
            print("[*] 查詢提交成功！")

            # 如果成功走到這裡，跳出重試迴圈
            break

        except Exception as e:
            print(f"[!] 第 {attempt + 1} 次執行出錯: {e}")
            if driver:
                driver.quit()
            if attempt < max_retries - 1:
                print("[*] 正在嘗試重新啟動...")
                time.sleep(3) # 等待幾秒後再重試
            else:
                print("[X] 已達到最大重試次數，任務失敗。")
                return

    # 查詢結果停留
    if driver:
        input("\n任務結束，按 Enter 鍵關閉瀏覽器並結束程式...")
        driver.quit()

if __name__ == "__main__":
    run_task()