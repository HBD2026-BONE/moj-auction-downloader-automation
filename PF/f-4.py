import os
import time
import random
import ddddocr
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# ==========================================
# ⚙️ 參數設定區 
# ==========================================
BRAVE_PATH = r"C:\Users\姍姍來遲\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"

THE_USE_TEXT = "汽機車"         # 種類
DEPT_INDEX = 4                # 分署編號 (1: 台北  2: 新北  3: 桃園  4: 新竹 5: 台中 13: 士林)
DATE_START = "2026/03/01"      # 拍賣日期-起
DATE_END = "2026/4/30"        # 拍賣日期-迄

# 設定下載儲存路徑
DOWNLOAD_PATH = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# 初始化 OCR
print("[*] 正在初始化 OCR 模型...")
ocr = ddddocr.DdddOcr(show_ad=False)
# ==========================================

def get_driver():
    """配置並啟動瀏覽器實例"""
    chrome_options = Options()
    chrome_options.binary_location = BRAVE_PATH
    
    # --- 進階下載設定 ---
    prefs = {
        "download.default_directory": DOWNLOAD_PATH,    # 指定下載路徑 (需絕對路徑)
        "download.prompt_for_download": False,          # 不彈出下載視窗
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True      # 強制下載 PDF，不要在瀏覽器內打開
    }
    chrome_options.add_experimental_option("prefs", prefs)
    # ------------------

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    
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
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"[*] 嘗試啟動第 {attempt + 1} 次...")
            driver = get_driver()
            wait = WebDriverWait(driver, 20)

            driver.get("https://www.tpkonsale.moj.gov.tw/Chattel")
            
            # 1. 選擇種類
            kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE")))
            Select(kind_el).select_by_visible_text(THE_USE_TEXT)

            # 2. 選擇分署 (使用 Index 編號)
            dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
            Select(dept_el).select_by_index(DEPT_INDEX)
            
            # 3. 填寫日期
            driver.find_element(By.ID, "OPEN_BID_TIME_S").send_keys(DATE_START)
            driver.find_element(By.ID, "OPEN_BID_TIME_E").send_keys(DATE_END)

            # 4. 驗證碼處理 
            captcha_img = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
            captcha_bytes = captcha_img.screenshot_as_png
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
            print("[*] 查詢提交成功，等待搜尋結果...")

            try:
                print("[*] 正在尋找搜尋結果表格...")
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                time.sleep(2)  # 額外等待 2 秒確保資料加載完成

                # 重新抓取下載連結：直接找所有 href 包含 Download 的 a 標籤
                # 這樣最保險，不用管它在哪個 td 裡面
                download_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'Download')]")

                if not download_links:
                    # 檢查是否有「查無資料」的字樣
                    if "查無資料" in driver.page_source:
                        print("[!] 查詢成功，但該條件下查無任何拍賣資料。")
                    else:
                        print("[!] 找不到下載按鈕，可能是頁面結構改變。")
                else:
                    print(f"[*] 成功！找到 {len(download_links)} 個檔案，開始下載...")
                    for i, link in enumerate(download_links):
                        try:
                            # 獲取檔名（優先取 title，沒有就取文字）
                            file_info = link.get_attribute("title") or link.text or f"File_{i+1}"
                            print(f"   -> 下載中 ({i+1}/{len(download_links)}): {file_info}")
                            
                            # 強制點擊
                            driver.execute_script("arguments[0].click();", link)
                            time.sleep(1.5) # 下載間隔
                        except:
                            continue
                    
                    print("[*] 所有下載指令已發送！請檢查 downloads 資料夾。")
            
            except Exception as e:
                print(f"[!] 等待結果超時或發生錯誤: {e}")
            
            # --- 下載功能結束 ---
            break

        except Exception as e:
            print(f"[!] 第 {attempt + 1} 次執行出錯: {e}")
            if driver: driver.quit()
            if attempt < max_retries - 1:
                time.sleep(3)
            else:
                print("[X] 已達到最大重試次數。")
                return

    if driver:
        input("\n任務結束，檔案應在 downloads 資料夾中。按 Enter 鍵關閉瀏覽器...")
        driver.quit()

if __name__ == "__main__":
    run_task()