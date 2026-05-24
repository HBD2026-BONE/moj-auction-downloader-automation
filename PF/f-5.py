import os
import time
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
DEPT_INDEX = 5                # 分署編號
DATE_START = "2026/03/01"      # 拍賣日期-起
DATE_END = "2026/04/30"        # 拍賣日期-迄

# 分署對照表 (用於資料夾命名)
DEPT_MAP = {
    1: "台北分署", 2: "新北分署", 3: "桃園分署", 4: "新竹分署",
    5: "台中分署", 6: "彰化分署", 7: "南投分署", 8: "嘉義分署",
    9: "台南分署", 10: "高雄分署", 11: "屏東分署", 12: "花蓮分署",
    13: "士林分署", 14: "宜蘭分署"
}

# --- 自動建立分類資料夾 ---
# 格式：downloads/日期範圍_分署名稱 (例如: 20260301-20260430_新竹分署)
folder_name = f"{DATE_START.replace('/','')}~{DATE_END.replace('/','')}_{DEPT_MAP.get(DEPT_INDEX, '未知分署')}"
BASE_DOWNLOAD_PATH = os.path.join(os.getcwd(), "downloads")
FINAL_SAVE_PATH = os.path.join(BASE_DOWNLOAD_PATH, folder_name)

if not os.path.exists(FINAL_SAVE_PATH):
    os.makedirs(FINAL_SAVE_PATH)
    print(f"[*] 已建立分類資料夾: {FINAL_SAVE_PATH}")

# ==========================================

# 初始化 OCR
print("[*] 正在初始化 OCR 模型...")
ocr = ddddocr.DdddOcr(show_ad=False)

def get_driver():
    """配置並啟動瀏覽器實例"""
    chrome_options = Options()
    chrome_options.binary_location = BRAVE_PATH
    
    # --- 進階下載設定 (動態指向 FINAL_SAVE_PATH) ---
    prefs = {
        "download.default_directory": FINAL_SAVE_PATH,  # <-- 這裡改為子資料夾
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

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

            # 2. 選擇分署
            dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
            Select(dept_el).select_by_index(DEPT_INDEX)
            
            # 3. 填寫日期
            driver.find_element(By.ID, "OPEN_BID_TIME_S").send_keys(DATE_START)
            driver.find_element(By.ID, "OPEN_BID_TIME_E").send_keys(DATE_END)

            # 4. 驗證碼
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

            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                time.sleep(2)

                download_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'Download')]")

                if not download_links:
                    if "查無資料" in driver.page_source:
                        print("[!] 查無資料。")
                    else:
                        print("[!] 找不到下載按鈕。")
                else:
                    print(f"[*] 找到 {len(download_links)} 個檔案，將存入: {folder_name}")
                    for i, link in enumerate(download_links):
                        try:
                            file_info = link.get_attribute("title") or link.text or f"File_{i+1}"
                            print(f"   -> 下載中 ({i+1}/{len(download_links)}): {file_info}")
                            driver.execute_script("arguments[0].click();", link)
                            time.sleep(2) # 稍微加長一點，避免下載太快資料夾鎖定
                        except:
                            continue
                    
                    print(f"[*] 下載完成！請至 {FINAL_SAVE_PATH} 查看。")
            
            except Exception as e:
                print(f"[!] 發生錯誤: {e}")
            
            break

        except Exception as e:
            print(f"[!] 第 {attempt + 1} 次出錯: {e}")
            if driver: driver.quit()
            if attempt < max_retries - 1: time.sleep(3)

    if driver:
        input("\n按 Enter 鍵關閉瀏覽器...")
        driver.quit()

if __name__ == "__main__":
    run_task()