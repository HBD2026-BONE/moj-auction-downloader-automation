import os
import time
import requests
import ddddocr
import re  # 引入正則表達式模組
import shutil
import glob
import urllib.parse  # 用於結合相對路徑
from concurrent.futures import ThreadPoolExecutor
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

def process_and_download_data2(driver):
    """負責解析網頁表格、點入詳細分頁下載多張圖片、並精準下載 PDF 附件"""
    wait = WebDriverWait(driver, 1)
    rows = driver.find_elements(By.CSS_SELECTOR, "table.tb_rwd tbody tr")

    if not rows:
        print("[!] 查無資料。")
        return False

    print(f"➡️  成功讀取到 {len(rows)} 筆資料，開始處理...")
    
    # 紀錄原本的主搜尋結果視窗 ID 與當前網站根網址 (用於拼接 PDF 絕對路徑)
    main_window = driver.current_window_handle
    current_url = driver.current_url
    parsed_uri = urllib.parse.urlparse(current_url)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"  

    for index, row in enumerate(rows):
        try:
            # 1. 抓取案號與說明文字
            case_no = row.find_element(By.XPATH, "./td[1]").text.split('\n')[0].strip()
            desc_text = row.find_element(By.XPATH, "./td[last()]").text

            # 清理案號中不能作為資料夾名稱的特殊字元
            clean_case_no = re.sub(r'[\\/:*?"<>|]', '_', case_no).strip()
            
            # 建立該案件的專屬資料夾
            case_folder_path = os.path.join(FINAL_SAVE_PATH, clean_case_no)
            os.makedirs(case_folder_path, exist_ok=True)

            # 廠牌與年份抓取邏輯
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
            base_img_name = f"{clean_case_no}_{clean_brand}_{year}"

            # 2. 點擊進入新分頁下載「所有圖片」
            try:
                detail_link = row.find_element(By.XPATH, ".//td[contains(@data-th, '照片')]//a | .//a[contains(@href, 'Detail')]")
                driver.execute_script("arguments[0].click();", detail_link)

                # 切換控制權到新開的分頁
                all_windows = driver.window_handles
                for window in all_windows:
                    if window != main_window:
                        driver.switch_to.window(window)
                        break

                print(f"  -> [{index+1}] 已進入詳細頁，正在秒速抓取所有圖片原始網址...")
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.slides")))
                
                sub_imgs = driver.find_elements(By.CSS_SELECTOR, "ul.slides img")
                
                valid_urls = []
                for img_el in sub_imgs:
                    img_url = img_el.get_attribute("src")
                    if img_url and "Img?" in img_url:
                        valid_urls.append(img_url)

                img_count = len(valid_urls)
                print(f"    -> 偵測到該案件共有 {img_count} 張圖片，啟動平行同步下載...")
                
                download_tasks = []
                for img_idx, img_url in enumerate(valid_urls):
                    save_name = f"{base_img_name}_{img_idx + 1}.jpg"
                    img_path = os.path.join(case_folder_path, save_name)
                    download_tasks.append((img_url, img_path))

                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(download_image, url, path) for url, path in download_tasks]
                    success_count = sum(1 for f in futures if f.result() == True)

                print(f"    -> ⚡ 圖片下載完成！成功儲存 {success_count}/{img_count} 張圖片")

                driver.close()
                driver.switch_to.window(main_window)

            except Exception as page_err:
                print(f"    [!] 進入詳細頁下載圖片失敗: {page_err}")
                if len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)

            # 3. 🔥 修正後的優化下載附件邏輯：不透過瀏覽器點擊，改用 requests 直接高精度下載
            download_links = row.find_elements(By.XPATH, ".//a[contains(@href, 'Download')]")
            if download_links:
                print(f"    -> 偵測到有 {len(download_links)} 個附件，開始解析下載網址...")
                
                for link in download_links:
                    # 獲取 a 標籤上的相對網址或絕對網址 (例如: /File/Download?PATH=...)
                    relative_pdf_url = link.get_attribute("href")
                    
                    if relative_pdf_url:
                        # 確保將相對路徑轉為帶有域名的完整絕對路徑
                        pdf_absolute_url = urllib.parse.urljoin(base_domain, relative_pdf_url)
                        
                        # 從 href 網址參數中解析出真實的系統檔名 NAME (例如 1130100028708_1_1.pdf)
                        # 如果解析不出來，就用預設案號當名稱
                        pdf_name_match = re.search(r'NAME=([^&]+)', pdf_absolute_url)
                        if pdf_name_match:
                            pdf_filename = urllib.parse.unquote(pdf_name_match.group(1))
                        else:
                            pdf_filename = f"{clean_case_no}_公告文件.pdf"
                        
                        # 設定最終儲存路徑，直達專屬資料夾！
                        pdf_save_path = os.path.join(case_folder_path, pdf_filename)
                        
                        # 複用你原本寫好的精美 download_image 函式 (因為 requests 載圖片跟載 PDF 原理完全一樣)
                        print(f"    -> 📥 正在下載 PDF 附件: {pdf_filename} ...")
                        if download_image(pdf_absolute_url, pdf_save_path):
                            print(f"    -> 📄 附件 {pdf_filename} 已成功精準儲存至資料夾！")
                        else:
                            print(f"    [!] 附件 {pdf_filename} 下載失敗。")

        except Exception as row_err:
            print(f"    [!] 第 {index+1} 筆處理失敗: {row_err}")
            driver.switch_to.window(main_window)
            
    return True

def process_and_download_data3(driver):
    """負責解析網頁表格、進分頁秒抓網址、不等待下載直接跳轉下一個案件"""
    wait = WebDriverWait(driver, 5) # 縮短等待上限
    rows = driver.find_elements(By.CSS_SELECTOR, "table.tb_rwd tbody tr")

    if not rows:
        print("[!] 查無資料。")
        return False

    print(f"➡️ 成功讀取到 {len(rows)} 筆資料，啟動極速異步處理...")
    
    main_window = driver.current_window_handle
    current_url = driver.current_url
    parsed_uri = urllib.parse.urlparse(current_url)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"  

    # 建立一個全域或單次的線程池（10個線程同時並行下載，快上加快）
    with ThreadPoolExecutor(max_workers=10) as executor:
        
        for index, row in enumerate(rows):
            try:
                # 1. 抓取案號與說明文字並建立資料夾
                case_no = row.find_element(By.XPATH, "./td[1]").text.split('\n')[0].strip()
                desc_text = row.find_element(By.XPATH, "./td[last()]").text

                clean_case_no = re.sub(r'[\\/:*?"<>|]', '_', case_no).strip()
                case_folder_path = os.path.join(FINAL_SAVE_PATH, clean_case_no)
                os.makedirs(case_folder_path, exist_ok=True)

                # 廠牌與年份抓取邏輯
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
                base_img_name = f"{clean_case_no}_{clean_brand}_{year}"

                # 準備收集該案件「所有要下載的任務」(包含圖片與PDF)
                all_download_tasks = []

                # 2. 點擊進入新分頁 ─── 只抓網址，抓完秒關！
                try:
                    detail_link = row.find_element(By.XPATH, ".//td[contains(@data-th, '照片')]//a | .//a[contains(@href, 'Detail')]")
                    driver.execute_script("arguments[0].click();", detail_link)

                    # 切換控制權
                    all_windows = driver.window_handles
                    for window in all_windows:
                        if window != main_window:
                            driver.switch_to.window(window)
                            break

                    # 只要結構出來了，立刻抓完網址就走
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.slides")))
                    sub_imgs = driver.find_elements(By.CSS_SELECTOR, "ul.slides img")
                    
                    img_idx = 1
                    for img_el in sub_imgs:
                        img_url = img_el.get_attribute("src")
                        if img_url and "Img?" in img_url:
                            save_name = f"{base_img_name}_{img_idx}.jpg"
                            img_path = os.path.join(case_folder_path, save_name)
                            # 丟進任務清單，先不下載
                            all_download_tasks.append((img_url, img_path))
                            img_idx += 1

                    # 🎯 核心改動：抓完地址了，直接關閉分頁，不等下載！
                    driver.close()
                    driver.switch_to.window(main_window)
                    print(f"  -> [{index+1}] 圖片地址提取完成，已關閉分頁。")

                except Exception as page_err:
                    print(f"    [!] 提取分頁圖片網址失敗: {page_err}")
                    if len(driver.window_handles) > 1:
                        driver.close()
                    driver.switch_to.window(main_window)

                # 3. 解析主頁面的 PDF 附件地址
                download_links = row.find_elements(By.XPATH, ".//a[contains(@href, 'Download')]")
                for link in download_links:
                    relative_pdf_url = link.get_attribute("href")
                    if relative_pdf_url:
                        pdf_absolute_url = urllib.parse.urljoin(base_domain, relative_pdf_url)
                        
                        pdf_name_match = re.search(r'NAME=([^&]+)', pdf_absolute_url)
                        if pdf_name_match:
                            pdf_filename = urllib.parse.unquote(pdf_name_match.group(1))
                        else:
                            pdf_filename = f"{clean_case_no}_公告文件.pdf"
                        
                        pdf_save_path = os.path.join(case_folder_path, pdf_filename)
                        # 丟進任務清單
                        all_download_tasks.append((pdf_absolute_url, pdf_save_path))

                # 4. 🔥 真正的幕後推手：把任務塞進背景線程，不阻塞主程式！
                # submit 後立刻放行，Selenium 會直接執行下一個 for 迴圈（下一個案件）
                if all_download_tasks:
                    print(f"    -> 🚀 已將該案 {len(all_download_tasks)} 個檔案送往背景下載，瀏覽器繼續前進...")
                    for url, path in all_download_tasks:
                        executor.submit(download_image, url, path)

            except Exception as row_err:
                print(f"    [!] 第 {index+1} 筆處理失敗: {row_err}")
                driver.switch_to.window(main_window)
                
    print("[+] 所有案件網址皆已掃描完畢，背景下載正在陸續收尾。")
    return True

def process_and_download_data(driver):
    """負責解析圖片與 PDF 網址，並收集至總任務清單，最後進行全域非同步下載"""
    wait = WebDriverWait(driver, 2) # 縮短等待時間
    rows = driver.find_elements(By.CSS_SELECTOR, "table.tb_rwd tbody tr")

    if not rows:
        print("[!] 查無資料。")
        return False

    print(f"[-] 成功讀取到 {len(rows)} 筆資料，開始抓取網址...")
    
    main_window = driver.current_window_handle
    current_url = driver.current_url
    parsed_uri = urllib.parse.urlparse(current_url)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"  

    # 建立一個總任務清單，把所有案件的 (網址, 儲存路徑) 通通塞進來
    all_download_tasks = []

    for index, row in enumerate(rows):
        try:
            # 1. 🔥 關鍵修正：改用 data-label 定位，直接抓取「案號 分署/股別」這一欄
            try:
                case_td = row.find_element(By.XPATH, ".//td[contains(@data-label, '案號')]")
                full_td_text = case_td.text.strip()
            except Exception:
                # 備用方案：如果上面找不到，嘗試原本的 td[2] (因為 td[1] 通常是 1,2,3 序號)
                full_td_text = row.find_element(By.XPATH, "./td[2]").text.strip()

            # 清理文字，只拿換行前第一行的純案號 (1130100028708)
            case_no = full_td_text.split('\n')[0].strip()
            
            # 如果因為網頁結構異動導致案號變空值，給予一個安全的防錯備用名稱
            if not case_no:
                case_no = f"{index+1}_未知案號"
                
            desc_text = row.find_element(By.XPATH, "./td[last()]").text

            # 清理案號中不能作為資料夾與檔名的特殊字元
            clean_raw_case_no = re.sub(r'[\\/:*?"<>|]', '_', case_no).strip()
            clean_case_no = f"{index + 1}_{clean_raw_case_no}"

            # 建立該案件的專屬資料夾
            case_folder_path = os.path.join(FINAL_SAVE_PATH, clean_case_no)
            os.makedirs(case_folder_path, exist_ok=True)

            # 廠牌與年份抓取邏輯
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
            base_img_name = f"{clean_case_no}_{clean_brand}_{year}"

            # 2. 點擊進入新分頁（僅抓取網址，抓完秒關）
            try:
                detail_link = row.find_element(By.XPATH, ".//td[contains(@data-th, '照片')]//a | .//a[contains(@href, 'Detail')]")
                driver.execute_script("arguments[0].click();", detail_link)

                all_windows = driver.window_handles
                for window in all_windows:
                    if window != main_window:
                        driver.switch_to.window(window)
                        break

                # 只要結構一出現，立刻撈網址
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.slides")))
                sub_imgs = driver.find_elements(By.CSS_SELECTOR, "ul.slides img")
                
                # 🔥 改動：建立一個用來記錄「這一個案件」已經抓過什麼網址的集合 (Set)
                seen_urls = set()
                img_idx = 1
                
                for img_el in sub_imgs:
                    img_url = img_el.get_attribute("src")
                    if img_url and "Img?" in img_url:
                        
                        # 🔥 關鍵：如果這個網址之前已經收集過了，就直接跳過，不重複塞入任務
                        if img_url in seen_urls:
                            continue
                        
                        # 沒見過的新網址，加入紀錄簿，並塞入下載任務
                        seen_urls.add(img_url)
                        
                        save_name = f"{base_img_name}_{img_idx}.jpg"
                        img_path = os.path.join(case_folder_path, save_name)
                        
                        # 塞入任務：(網址, 儲存路徑)
                        all_download_tasks.append((img_url, img_path))
                        img_idx += 1

                driver.close()
                driver.switch_to.window(main_window)
                print(f"  -> [{index+1}] 案件 {clean_case_no} 圖片網址抓取完畢，已跳轉。")

            except Exception as page_err:
                print(f"    [!] 進入詳細頁抓取網址失敗: {page_err}")
                if len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)

            # 3. 抓取主頁面的 PDF 附件網址 
            download_links = row.find_elements(By.XPATH, ".//a[contains(@href, 'Download')]")
            for link in download_links:
                relative_pdf_url = link.get_attribute("href")
                if relative_pdf_url:
                    pdf_absolute_url = urllib.parse.urljoin(base_domain, relative_pdf_url)
                    
                    pdf_name_match = re.search(r'NAME=([^&]+)', pdf_absolute_url)
                    if pdf_name_match:
                        pdf_filename = urllib.parse.unquote(pdf_name_match.group(1))
                    else:
                        pdf_filename = f"{clean_case_no}_公告文件.pdf"
                    
                    pdf_save_path = os.path.join(case_folder_path, pdf_filename)
                    
                    # 塞入任務：(網址, 儲存路徑)
                    all_download_tasks.append((pdf_absolute_url, pdf_save_path))

        except Exception as row_err:
            print(f"    [!] 第 {index+1} 筆網址解析失敗: {row_err}")
            driver.switch_to.window(main_window)
            
    # ========================================================
    # 🔥 核心優化：網頁全部跳轉、解析完了！現在啟動後台全速平行下載
    # ========================================================
    total_tasks = len(all_download_tasks)
    if total_tasks > 0:
        print(f"\n⚡ [完成網頁解析] 總共收集到 {total_tasks} 個下載任務（含圖片與PDF）。")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 丟給 requests 背景瘋狂下載，完全不需要等網頁
            futures = [executor.submit(download_image, url, path) for url, path in all_download_tasks]
            success_count = sum(1 for f in futures if f.result() == True)
            
        print(f"🎉【全部下載完成】成功儲存 {success_count} / {total_tasks} 個檔案，均已完美分類至案號資料夾！")
    else:
        print("\n[!] 未發現任何可下載的檔案網址。")

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
            wait = WebDriverWait(driver, 10)    # 最長等待時間

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
    