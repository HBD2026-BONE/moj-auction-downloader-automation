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
# ⚙️ 全域參數設定區 
# ==========================================
THE_USE_TEXT = "汽機車" 
DEPT_INDEX = [1, 2, 4, 13, 5, 6,7,8,9,10]               
DATE_START = "2026/06/01"      
DATE_END = "2026/06/30"        

DEPT_MAP = {
    1: "台北分署", 2: "新北分署", 3: "桃園分署", 4: "新竹分署",
    5: "台中分署", 6: "彰化分署", 7: "南投分署", 8: "嘉義分署",
    9: "台南分署", 10: "高雄分署", 11: "屏東分署", 12: "花蓮分署",
    13: "士林分署", 14: "宜蘭分署"
}

BASE_DOWNLOAD_PATH = os.path.join(os.getcwd(), f"法拍_{THE_USE_TEXT}")

# ==========================================

print("正在初始化 OCR 模型...")
ocr = ddddocr.DdddOcr(show_ad=False)

def get_driver(save_path):
    """ 假裝自己是真人，並準備自動下載檔案 (加入 save_path 參數) """
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")   # 使用穩定的新版無頭模式 

    prefs = {
        "download.default_directory": save_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    stealth(driver, languages=["zh-TW", "en"], vendor="Google Inc.", platform="Win32",
            webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True)
    return driver

def download_image(url, save_path):
    """" 圖片與檔案下載 """
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"    [!] 檔案下載失敗: {e}")
    return False

def submit_form(driver, wait, dept_index):
    """負責填寫表單、辨識驗證碼並按下查詢 (加入 dept_index 參數) """
    print(f"[*] 開始填寫查詢表單 ({DEPT_MAP.get(dept_index, '未知分署')})...")
    
    # 1. 填寫表單欄位
    kind_el = wait.until(EC.element_to_be_clickable((By.ID, "THE_USE"))) 
    Select(kind_el).select_by_visible_text(THE_USE_TEXT)
    
    dept_el = wait.until(EC.element_to_be_clickable((By.ID, "EXEC_DEPT_ID")))
    Select(dept_el).select_by_index(dept_index)
    
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

def process_and_download_data(driver, final_save_path):
    """負責解析圖片與 PDF 網址，並收集至總任務清單，最後進行全域非同步下載"""
    wait = WebDriverWait(driver, 5) 
    rows = driver.find_elements(By.CSS_SELECTOR, "table.tb_rwd tbody tr")

    if not rows:
        print("[!] 查無資料。")
        return False

    print(f"[-] 成功讀取到 {len(rows)} 筆資料，開始抓取網址...")
    
    main_window = driver.current_window_handle
    current_url = driver.current_url
    parsed_uri = urllib.parse.urlparse(current_url)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"  

    all_download_tasks = []

    for index, row in enumerate(rows):
        try:
            full_td_text = ""
            try:
                case_td = row.find_element(By.XPATH, ".//td[contains(@data-label, '案號')]")
                full_td_text = case_td.text.strip()
            except Exception:
                try:
                    all_tds = row.find_elements(By.XPATH, "./td")
                    if len(all_tds) >= 2:
                        for td in all_tds[1:4]: 
                            if td.text.strip():
                                full_td_text = td.text.strip()
                                break
                except Exception:
                    full_td_text = ""

            if full_td_text:
                case_no = full_td_text.split('\n')[0].strip()
            else:
                case_no = ""
            
            if not case_no:
                case_no = f"Case_{index+1}"
                print(f"  [!] 第 {index+1} 筆抓不到案號文字，啟用備用名稱: {case_no}")
                
            try:
                desc_text = row.find_element(By.XPATH, "./td[last()]").text
            except Exception:
                desc_text = ""

            clean_raw_case_no = re.sub(r'[\\/:*?"<>|]', '_', case_no).strip()
            clean_case_no = f"{index + 1}_{clean_raw_case_no}"

            case_folder_path = os.path.join(final_save_path, clean_case_no)
            os.makedirs(case_folder_path, exist_ok=True)

            brand = "未知廠牌"
            if desc_text:
                brand_keywords = [r"廠牌[：|:|\/型式：]+([\w\u4e00-\u9fa5]+)", r"([\w\u4e00-\u9fa5]+)牌"]
                for pattern in brand_keywords:
                    match = re.search(pattern, desc_text)
                    if match:
                        brand = match.group(1).strip()
                        break

            year = "未知年份"
            if desc_text:
                year_keywords = [r"出廠年份[：|:]+(\d+)", r"(\d+)年", r"(\d+)出廠"]
                for pattern in year_keywords:
                    match = re.search(pattern, desc_text)
                    if match:
                        year = match.group(1).strip()
                        break

            clean_brand = re.sub(r'[\\/:*?"<>|]', '', brand).strip()
            base_img_name = f"{clean_case_no}_{clean_brand}_{year}"

            # 點擊進入詳細頁抓圖
            try:
                detail_link = row.find_element(By.XPATH, ".//a[contains(@href, 'Detail') or contains(@class, 'btn')]")
                driver.execute_script("arguments[0].click();", detail_link)

                all_windows = driver.window_handles
                for window in all_windows:
                    if window != main_window:
                        driver.switch_to.window(window)
                        break

                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.slides")))
                sub_imgs = driver.find_elements(By.CSS_SELECTOR, "ul.slides img")
                
                seen_urls = set()
                img_idx = 1
                
                for img_el in sub_imgs:
                    img_url = img_el.get_attribute("src")
                    if img_url and "Img?" in img_url:
                        if img_url in seen_urls:
                            continue
                        
                        seen_urls.add(img_url)
                        save_name = f"{base_img_name}_{img_idx}.jpg"
                        img_path = os.path.join(case_folder_path, save_name)
                        
                        all_download_tasks.append((img_url, img_path))
                        img_idx += 1

                driver.close()
                driver.switch_to.window(main_window)
                print(f"  -> [{index+1}] 案件 {clean_case_no} 圖片網址抓取完畢。")

            except Exception as page_err:
                print(f"    [!] 進入詳細頁抓取網址失敗: {page_err}")
                if len(driver.window_handles) > 1:
                    driver.close()
                driver.switch_to.window(main_window)

            # 抓取主頁面的 PDF 附件
            try:
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
                        all_download_tasks.append((pdf_absolute_url, pdf_save_path))
            except Exception:
                pass 

        except Exception as row_err:
            print(f"    [!] 第 {index+1} 筆整體解析失敗: {row_err}")
            driver.switch_to.window(main_window)
            
    # 後台平行下載
    total_tasks = len(all_download_tasks)
    if total_tasks > 0:
        print(f"\n⚡ [完成網頁解析] 總共收集到 {total_tasks} 個下載任務。")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(download_image, url, path) for url, path in all_download_tasks]
            success_count = sum(1 for f in futures if f.result() == True)
        print(f"🎉【該分署下載完成】成功儲存 {success_count} / {total_tasks} 個檔案！")
    else:
        print("\n[!] 未發現任何可下載的檔案網址。")

    return True

# ==========================================
# 🚀 主任務流程區
# ==========================================
def run_task_for_dept(dept_index):
    """ 執行單一分署的下載任務 """
    dept_name = DEPT_MAP.get(dept_index, '未知分署')
    folder_name = f"{DATE_START.replace('/','')}-{DATE_END.replace('/','')}_{dept_name}"
    final_save_path = os.path.join(BASE_DOWNLOAD_PATH, folder_name)

    if not os.path.exists(final_save_path):
        os.makedirs(final_save_path)
        print(f"\n[*] 已建立分類資料夾: {final_save_path}")

    driver = None
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"[*] 【{dept_name}】嘗試啟動第 {attempt + 1} 次...")
            
            driver = get_driver(final_save_path) # 傳入動態路徑
            wait = WebDriverWait(driver, 10)  

            driver.get("https://www.tpkonsale.moj.gov.tw/Chattel") 
            
            # 填寫表單 (傳入當前迴圈的分署代號)
            submit_form(driver, wait, dept_index)

            # 等待網頁結果表格載入
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.tb_rwd")))
            time.sleep(2)

            # 解析並下載資料
            process_and_download_data(driver, final_save_path)

            print(f"[*] 【{dept_name}】任務完成！")
            break

        except Exception as e:
            print(f"[!] 出錯或驗證碼錯誤: {e}")
            if attempt < max_retries - 1:
                print("[*] 3 秒後嘗試重新辨識...")
            if driver: 
                driver.quit()
            time.sleep(3)
    else:
        print(f"[❌] 【{dept_name}】嘗試 {max_retries} 次均失敗，跳過此分署。")

if __name__ == "__main__":
    # 💡 在這裡指定你想一次下載的所有分署代號
    # 1:台北, 2:新北, 3:桃園, 4:新竹, 13:士林 ...以此類推
    target_depts = DEPT_INDEX 
    
    print(f"🚀 開始批次下載任務，目標分署: {[DEPT_MAP.get(i) for i in target_depts]}")
    
    for dept_id in target_depts:
        run_task_for_dept(dept_id)
        time.sleep(2) # 分署與分署之間稍微休息一下，避免被網站阻擋
        
    print("\n🏁 【所有指定分署任務已全部結束】")