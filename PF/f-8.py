import os
import time
import requests
import ddddocr
import re  # 引入正則表達式模組
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium_stealth import stealth

# ==========================================
# ⚙️ 參數設定區 
# ==========================================
THE_USE_TEXT = "汽機車"         
DEPT_INDEX = 5               
DATE_START = "2026/06/01"      
DATE_END = "2026/06/30"        

DEPT_MAP = {
    1: "台北分署", 2: "新北分署", 3: "桃園分署", 4: "新竹分署",
    5: "台中分署", 6: "彰化分署", 7: "南投分署", 8: "嘉義分署",
    9: "台南分署", 10: "高雄分署", 11: "屏東分署", 12: "花蓮分署",
    13: "士林分署", 14: "宜蘭分署"
}

folder_name = f"{DATE_START.replace('/','')}-{DATE_END.replace('/','')}_{DEPT_MAP.get(DEPT_INDEX, '未知分署')}"
BASE_DOWNLOAD_PATH = os.path.join(os.getcwd(), f"法拍_{THE_USE_TEXT}")
FINAL_SAVE_PATH = os.path.join(BASE_DOWNLOAD_PATH, folder_name)

if not os.path.exists(FINAL_SAVE_PATH):
    os.makedirs(FINAL_SAVE_PATH)
    print(f"[*] 已建立分類資料夾: {FINAL_SAVE_PATH}")

# ==========================================

print("正在初始化 OCR 模型...")
ocr = ddddocr.DdddOcr(show_ad=False)

def get_driver():
    """ 假裝自己是真人，並準備自動下載檔案 """
    chrome_options = Options()
    prefs = {
        "download.default_directory": FINAL_SAVE_PATH,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--no-sandbox")             
    chrome_options.add_argument("--disable-dev-shm-usage")  # 關閉硬體加速
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")    # 清除機器人標籤
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    stealth(driver, languages=["zh-TW", "en"], vendor="Google Inc.", platform="Win32",
            webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    return driver

def download_image(url, save_path):
    """" 圖片下載 """
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"    [!] 圖片下載失敗: {e}")
    return False

def submit_form(driver, wait):
    """負責填寫表單、辨識驗證碼並按下查詢"""
    print("[*] 開始填寫查詢表單...")
    
    # 1. 填寫表單欄位
    kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE"))) 
    Select(kind_el).select_by_visible_text(THE_USE_TEXT)
    
    dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
    Select(dept_el).select_by_index(DEPT_INDEX)
    
    # 清除欄位原本可能殘留的文字再填入
    start_date_el = driver.find_element(By.ID, "OPEN_BID_TIME_S")
    start_date_el.clear()
    start_date_el.send_keys(DATE_START)
    
    end_date_el = driver.find_element(By.ID, "OPEN_BID_TIME_E")
    end_date_el.clear()
    end_date_el.send_keys(DATE_END)

    # 2. 處理驗證碼
    print("[*] 正在辨識驗證碼...")
    captcha_img = wait.until(EC.presence_of_element_located((By.ID, "CaptchaImage")))
    captcha_bytes = captcha_img.screenshot_as_png
    captcha_text = ocr.classification(captcha_bytes).upper()
    
    captcha_input = driver.find_element(By.ID, "CAPTCHA")
    captcha_input.clear()
    captcha_input.send_keys(captcha_text)
    print(f"[+] 填入驗證碼: {captcha_text}")
    
    # 3. 按下查詢
    time.sleep(0.5)
    query_btn = driver.find_element(By.NAME, "doQueryData") 
    driver.execute_script("arguments[0].click();", query_btn)

def process_and_download_data1(driver):
    """負責解析網頁表格並下載圖片與附件"""
    rows = driver.find_elements(By.CSS_SELECTOR, "table.tb_rwd tbody tr")

    if not rows:
        print("[!] 查無資料。")
        return False

    print(f"[+] 成功讀取到 {len(rows)} 筆資料，開始下載...")
    
    for index, row in enumerate(rows):
        try:
            # 1. 抓取案號
            case_no = row.find_element(By.XPATH, "./td[1]").text.split('\n')[0].strip()
            
            # 2. 抓取說明文字並提取 廠牌 與 年份
            desc_text = row.find_element(By.XPATH, "./td[last()]").text

            # a. 廠牌抓取
            brand_keywords = [r"廠牌[：|:|\/型式：]+([\w\u4e00-\u9fa5]+)", r"([\w\u4e00-\u9fa5]+)牌"]
            brand = "未知廠牌"
            for pattern in brand_keywords:
                match = re.search(pattern, desc_text)
                if match:
                    brand = match.group(1).strip()
                    break

            # b. 年份抓取
            year_keywords = [r"出廠年份[：|:]+(\d+)", r"(\d+)年", r"(\d+)出廠"]
            year = "未知年份"
            for pattern in year_keywords:
                match = re.search(pattern, desc_text)
                if match:
                    year = match.group(1).strip()
                    break

            # c. 修正後的字元過濾邏輯
            clean_brand = re.sub(r'[\\/:*?"<>|]', '', brand).strip()
            
            # 組合新檔名：案號_廠牌_年份.jpg
            img_name = f"{case_no}_{clean_brand}_{year}.jpg"
            img_path = os.path.join(FINAL_SAVE_PATH, img_name)
            
            # 3. 下載圖片
            try:
                img_el = row.find_element(By.TAG_NAME, "img")
                img_url = img_el.get_attribute("src")
                if img_url and download_image(img_url, img_path):
                    print(f"    -> [{index+1}] 成功存檔: {img_name}")
            except:
                print(f"    -> [{index+1}] 無圖片")

            # 4. 下載附件
            download_links = row.find_elements(By.XPATH, ".//a[contains(@href, 'Download')]")
            for link in download_links:
                driver.execute_script("arguments[0].click();", link)
                time.sleep(0.5)

        except Exception as row_err:
            print(f"    [!] 第 {index+1} 筆處理失敗: {row_err}")
            
    return True

def process_and_download_data(driver):
    """負責解析網頁表格、點入詳細分頁下載多張圖片、並下載附件"""
    wait = WebDriverWait(driver, 15)
    rows = driver.find_elements(By.CSS_SELECTOR, "table.tb_rwd tbody tr")

    if not rows:
        print("[!] 查無資料。")
        return False

    print(f"➡️ 成功讀取到 {len(rows)} 筆資料，開始處理...")
    
    # 紀錄原本的主搜尋結果視窗 ID
    main_window = driver.current_window_handle

    for index, row in enumerate(rows):
        try:
            # 1. 抓取案號與說明文字
            case_no = row.find_element(By.XPATH, "./td[1]").text.split('\n')[0].strip()
            desc_text = row.find_element(By.XPATH, "./td[last()]").text

            # a. 廠牌與年份抓取邏輯
            brand_keywords = [r"廠牌[：|:|\/型式：]+([\w\u4e00-\u9fa5]+)", r"([\w\u4e00-\u9fa5]+)牌"]
            brand = "未知廠牌"
            for pattern in brand_keywords:
                match = re.search(pattern, desc_text)
                if match:
                    brand = match.group(1).strip()
                    break

            year_keywords = [r"出廠年份[：|:]+(\d+)", r"(\d+)年", r"(\d+)出廠"]
            year = "未知年份"
            for pattern in year_keywords:
                match = re.search(pattern, desc_text)
                if match:
                    year = match.group(1).strip()
                    break

            clean_brand = re.sub(r'[\\/:*?"<>|]', '', brand).strip()
            base_img_name = f"{case_no}_{clean_brand}_{year}"

            # 2. 點擊進入新分頁下載「所有圖片」
            try:
                # 找到連往詳細頁的 a 標籤
                detail_link = row.find_element(By.XPATH, ".//td[contains(@data-th, '照片')]//a | .//a[contains(@href, 'Detail')]")
                
                # 點擊打開新分頁
                driver.execute_script("arguments[0].click();", detail_link)

                # 切換控制權到新開的分頁
                all_windows = driver.window_handles
                for window in all_windows:
                    if window != main_window:
                        driver.switch_to.window(window)
                        break

                print(f"  -> [{index+1}] 已進入詳細頁，正在秒速抓取所有圖片原始網址...")
                
                # 關鍵優化 1：只要確保 ul.slides 框架載入完成即可，完全不等輪播動畫
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.slides")))
                
                # 關鍵優化 2：直接撈出 ul.slides 裡面「當下所有」的 img 標籤（自動適應各種圖片張數）
                sub_imgs = driver.find_elements(By.CSS_SELECTOR, "ul.slides img")
                
                # 收集該頁面所有合法的絕對網址
                valid_urls = []
                for img_el in sub_imgs:
                    img_url = img_el.get_attribute("src")
                    if img_url and "Img?" in img_url:
                        valid_urls.append(img_url)

                img_count = len(valid_urls)
                print(f"    -> 偵測到該案件共有 {img_count} 張圖片，啟動平行同步下載...")

                # 關鍵優化 3：利用 ThreadPoolExecutor 同步下載這家分頁的所有圖片
                # max_workers=5 代表同時開 5 條線下載，不用一張一張排隊
                from concurrent.futures import ThreadPoolExecutor
                
                download_tasks = []
                for img_idx, img_url in enumerate(valid_urls):
                    save_name = f"{base_img_name}_{img_idx + 1}.jpg"
                    img_path = os.path.join(FINAL_SAVE_PATH, save_name)
                    download_tasks.append((img_url, img_path))

                with ThreadPoolExecutor(max_workers=5) as executor:
                    # 分發下載任務
                    futures = [executor.submit(download_image, url, path) for url, path in download_tasks]
                    # 計算真正下載成功的張數
                    success_count = sum(1 for f in futures if f.result() == True)

                print(f"    -> ⚡ 下載完成！成功儲存 {success_count}/{img_count} 張圖片")

                # 下載完後直接關閉分頁，切換回主視窗
                driver.close()
                driver.switch_to.window(main_window)

            except Exception as page_err:
                print(f"    [!] 進入詳細頁下載圖片失敗: {page_err}")
                if len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)
            # 3. 下載附件 (原本主頁面的 pdf 檔案)
            download_links = row.find_elements(By.XPATH, ".//a[contains(@href, 'Download')]")
            for link in download_links:
                driver.execute_script("arguments[0].click();", link)
                time.sleep(0.5)

        except Exception as row_err:
            print(f"    [!] 第 {index+1} 筆處理失敗: {row_err}")
            driver.switch_to.window(main_window)  # 確保回到主頁面
            
    return True

# ==========================================
# 🚀 主任務流程區
# ==========================================
def run_task():
    driver = None
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"\n[*] 嘗試啟動第 {attempt + 1} 次...")
            
            driver = get_driver()               # 發動引擎並坐上駕駛座
            wait = WebDriverWait(driver, 20)    # 最長等待時間

            driver.get("https://www.tpkonsale.moj.gov.tw/Chattel")      # 打開網址
            
            # 1. 填寫表單並送出查詢（呼叫獨立函式）
            submit_form(driver, wait)

            # 2. 等待網頁結果表格載入
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb_rwd")))
            time.sleep(2)

            # 3. 解析並下載資料（呼叫獨立函式）
            process_and_download_data(driver)

            print(f"\n[*] 任務完成！")
            break

        except Exception as e:
            print(f"[!] 出錯或驗證碼錯誤: {e}")
            if driver: 
                driver.quit()
            time.sleep(3)

    if driver:
        input("\n按 Enter 鍵關閉...")
        driver.quit()

if __name__ == "__main__":
    run_task()
    