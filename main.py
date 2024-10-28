# 標準庫
import asyncio
import base64
import io
import logging
import os
import pickle
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 第三方庫
import httpx
import pytesseract
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# 導入設定
from config import Settings, BASE_URL, LOGIN_URL, TARGET_URL, SCAN_INTERVAL, TARGET_EVENT, TARGET_LOCATION

# 直接設定 tesseract 路徑
TESSERACT_CMD = '/opt/homebrew/bin/tesseract'
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    logger.info(f"Successfully set tesseract path to: {TESSERACT_CMD}")
else:
    logger.error(f"Tesseract not found at {TESSERACT_CMD}")
    raise RuntimeError(f"Tesseract not found at {TESSERACT_CMD}. Please verify the installation.")
# 常數設定
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒
COOKIE_MAX_AGE = 24 * 60 * 60  # 24小時，以秒為單位

class LoginStatus(BaseModel):
    success: bool
    message: str

class EventStatus(BaseModel):
    name: str
    location: str
    event_date: str
    registration_start: str
    registration_end: str
    status: str
    last_checked: str

class CookieManager:
    def __init__(self):
        self.cookie_dir = Path('data')
        self.cookie_dir.mkdir(exist_ok=True)
        self.cookie_file = self.cookie_dir / 'wmg_cookies.pkl'
        self.cookie_timestamp_file = self.cookie_dir / 'cookie_timestamp.txt'

    def save_cookies(self, driver):
        """保存 cookies 到文件"""
        try:
            cookies = driver.get_cookies()
            with open(self.cookie_file, 'wb') as f:
                pickle.dump(cookies, f)
            # 記錄保存時間
            with open(self.cookie_timestamp_file, 'w') as f:
                f.write(str(datetime.now().timestamp()))
            logger.info("Cookies 已保存")
            return True
        except Exception as e:
            logger.error(f"保存 Cookies 失敗: {str(e)}")
            return False

    def load_cookies(self, driver):
        """從文件加載 cookies"""
        try:
            if not self.cookie_file.exists() or not self.is_cookie_valid():
                return False

            with open(self.cookie_file, 'rb') as f:
                cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
            logger.info("Cookies 已加載")
            return True
        except Exception as e:
            logger.error(f"加載 Cookies 失敗: {str(e)}")
            return False

    def clear_cookies(self):
        """清除保存的 cookies"""
        try:
            if self.cookie_file.exists():
                self.cookie_file.unlink()
            if self.cookie_timestamp_file.exists():
                self.cookie_timestamp_file.unlink()
            logger.info("Cookies 已清除")
            return True
        except Exception as e:
            logger.error(f"清除 Cookies 失敗: {str(e)}")
            return False

    def is_cookie_valid(self):
        """檢查 cookies 是否有效"""
        try:
            if not self.cookie_timestamp_file.exists():
                return False
                
            with open(self.cookie_timestamp_file, 'r') as f:
                timestamp = float(f.read().strip())
            saved_time = datetime.fromtimestamp(timestamp)
            return (datetime.now() - saved_time).total_seconds() < COOKIE_MAX_AGE
        except Exception as e:
            logger.error(f"檢查 Cookies 有效性失敗: {str(e)}")
            return False

app = FastAPI(title="運動賽事監控系統")
scheduler = AsyncIOScheduler()
notified_events: Set[str] = set()
cookie_manager = CookieManager()

def setup_driver():
    """設置 Chrome WebDriver"""
    chrome_options = Options()
    # 先註釋掉 headless 模式以便觀察
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 模擬真實瀏覽器
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(10)
    return driver


from urllib.parse import urljoin

def get_captcha_image(driver, image_element) -> str:
    """獲取驗證碼圖片內容並轉換為文字"""
    try:
        # 獲取圖片的 src 屬性
        img_src = image_element.get_attribute('src')
        logger.info(f"驗證碼圖片路徑: {img_src}")
        
        # 使用 driver 的當前 session 下載圖片
        # 這樣可以保持登入狀態和 cookies
        img_data = driver.execute_script("""
            var img = document.querySelector('img[src^="images/check/"]');
            var canvas = document.createElement('canvas');
            var ctx = canvas.getContext('2d');
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
            return canvas.toDataURL('image/png').substring(22);
        """)
        
        # 將 base64 轉換為圖片
        img_bytes = base64.b64decode(img_data)
        img = Image.open(io.BytesIO(img_bytes))
        
        # 前處理圖片
        # 轉為灰度圖
        img = img.convert('L')
        # 二值化
        threshold = 128
        img = img.point(lambda x: 0 if x < threshold else 255, '1')
        
        # OCR 識別
        captcha_text = pytesseract.image_to_string(
            img, 
            config='--psm 7 -c tessedit_char_whitelist=0123456789'
        ).strip()
        
        logger.info(f"識別出的驗證碼: {captcha_text}")
        return captcha_text
            
    except Exception as e:
        logger.error(f"驗證碼識別失敗: {str(e)}", exc_info=True)
        return None

def recognize_captcha(image: Image) -> str:
    """識別驗證碼"""
    try:
        # 預處理圖片
        # 轉換為灰度圖
        image = image.convert('L')
        # 二值化
        threshold = 127
        table = []
        for i in range(256):
            if i < threshold:
                table.append(0)
            else:
                table.append(1)
        image = image.point(table, '1')
        
        # 使用 pytesseract 識別驗證碼
        captcha_text = pytesseract.image_to_string(image, config='--psm 7 -c tessedit_char_whitelist=0123456789')
        # 清理結果
        captcha_text = ''.join(filter(str.isdigit, captcha_text))
        
        return captcha_text
    except Exception as e:
        logger.error(f"識別驗證碼失敗: {str(e)}")
        return None


def check_login_status(driver) -> bool:
    """檢查是否已登入"""
    try:
        # 先處理可能出現的 Alert
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            logger.info(f"檢測到 Alert: {alert_text}")
            if "已登入" in alert_text:
                alert.accept()  # 關閉 Alert
                return True
        except Exception:
            pass

        # 檢查 URL
        current_url = driver.current_url
        return "member_login.php" not in current_url
            
    except Exception as e:
        logger.error(f"檢查登入狀態失敗: {str(e)}")
        return False


def login(driver, retry_count=0) -> LoginStatus:
    """登入網站"""
    try:
        # 先嘗試使用保存的 cookies
        if cookie_manager.load_cookies(driver):
            driver.get(BASE_URL)
            time.sleep(2)
            if check_login_status(driver):
                return LoginStatus(success=True, message="使用已保存的登入狀態")

        # 如果 cookies 無效或登入失敗，進行新的登入
        logger.info("開始新的登入程序")
        driver.get(LOGIN_URL)
        time.sleep(3)  # 確保頁面完全載入
        
        logger.info("當前頁面 URL: " + driver.current_url)
        logger.info("正在尋找登入表單元素...")
        
        # 尋找表單元素
        try:
            username_input = driver.find_element(By.NAME, "member_userid")
            logger.info("找到帳號輸入框")
        except NoSuchElementException:
            logger.error("無法找到帳號輸入框")
            return LoginStatus(success=False, message="無法找到帳號輸入框")

        try:
            password_input = driver.find_element(By.NAME, "member_password")
            logger.info("找到密碼輸入框")
        except NoSuchElementException:
            logger.error("無法找到密碼輸入框")
            return LoginStatus(success=False, message="無法找到密碼輸入框")

        try:
            captcha_input = driver.find_element(By.NAME, "check_num")
            logger.info("找到驗證碼輸入框")
        except NoSuchElementException:
            logger.error("無法找到驗證碼輸入框")
            return LoginStatus(success=False, message="無法找到驗證碼輸入框")

        try:
            submit_button = driver.find_element(By.NAME, "b1")
            logger.info("找到提交按鈕")
        except NoSuchElementException:
            logger.error("無法找到提交按鈕")
            return LoginStatus(success=False, message="無法找到提交按鈕")

        # 輸入帳號密碼
        username_input.clear()
        username_input.send_keys(Settings.WMG_USERNAME)
        logger.info(f"輸入帳號: {Settings.WMG_USERNAME}")
        time.sleep(1)
        
        password_input.clear()
        password_input.send_keys(Settings.WMG_PASSWORD)
        logger.info("輸入密碼")
        time.sleep(1)

        # 處理驗證碼
        try:
            # 找到驗證碼圖片
            captcha_image = driver.find_element(By.CSS_SELECTOR, "img[src^='images/check/']")
            
            # 獲取並識別驗證碼
            captcha_text = get_captcha_image(driver, captcha_image)
            if captcha_text and len(captcha_text) > 0:
                logger.info(f"識別出驗證碼: {captcha_text}")
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                time.sleep(1)
            else:
                logger.error("無法識別驗證碼")
                if retry_count < MAX_RETRIES:
                    return login(driver, retry_count + 1)
                return LoginStatus(success=False, message="無法識別驗證碼")
                
        except Exception as e:
            logger.error(f"處理驗證碼時發生錯誤: {str(e)}")
            if retry_count < MAX_RETRIES:
                return login(driver, retry_count + 1)
            return LoginStatus(success=False, message=f"處理驗證碼錯誤: {str(e)}")

        # 提交表單
        logger.info("準備提交表單...")
        submit_button.click()
        time.sleep(3)

        # 處理可能的彈窗
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            logger.info(f"檢測到彈窗: {alert_text}")
            if "已登入" in alert_text:
                alert.accept()
                logger.info("關閉'已登入'彈窗")
                return LoginStatus(success=True, message="已是登入狀態")
            else:
                alert.accept()
                logger.warning(f"未預期的彈窗訊息: {alert_text}")
        except Exception:
            pass

        # 檢查登入結果
        if check_login_status(driver):
            logger.info("登入成功")
            cookie_manager.save_cookies(driver)
            return LoginStatus(success=True, message="登入成功")
        else:
            if retry_count < MAX_RETRIES:
                logger.warning(f"登入可能失敗，第 {retry_count + 1} 次重試...")
                time.sleep(RETRY_DELAY)
                return login(driver, retry_count + 1)
            else:
                return LoginStatus(success=False, message="登入重試次數超過上限")

    except Exception as e:
        logger.error(f"登入過程發生錯誤: {str(e)}", exc_info=True)
        if retry_count < MAX_RETRIES:
            return login(driver, retry_count + 1)
        return LoginStatus(success=False, message=f"登入錯誤: {str(e)}")

def get_page_content():
    """獲取活動頁面內容"""
    driver = None
    try:
        driver = setup_driver()
        
        # 進行登入
        login_status = login(driver)
        if not login_status.success:
            return None
            
        # 訪問目標頁面
        logger.info("訪問活動頁面")
        driver.get(TARGET_URL)
        wait = WebDriverWait(driver, 20)
        
        try:
            # 等待頁面載入（調整選擇器以符合實際網頁結構）
            wait.until(EC.presence_of_element_located((
                By.CLASS_NAME, "card"
            )))
        except TimeoutException:
            logger.warning("等待活動列表超時，嘗試直接獲取頁面內容")
        
        # 滾動頁面以確保所有內容載入
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        return driver.page_source
        
    except Exception as e:
        logger.error(f"獲取頁面失敗: {str(e)}", exc_info=True)
        return None
    finally:
        if driver:
            driver.quit()

def parse_event(html_content: str) -> Optional[EventStatus]:
    """解析目標課程資訊"""
    if not html_content:
        return None
        
    soup = BeautifulSoup(html_content, 'html.parser')
    cards = soup.find_all('div', class_='card')
    
    for card in cards:
        try:
            name = card.find('h2').text.strip()
            if name == TARGET_EVENT:
                location = card.find('div', string=lambda text: '活動地點' in str(text)).text.split('：')[1].strip()
                
                if location == TARGET_LOCATION:
                    event_date = card.find('div', string=lambda text: '活動日期' in str(text)).text.split('：')[1].strip()
                    reg_start = card.find('div', string=lambda text: '報名開始日' in str(text)).text.split('：')[1].strip()
                    reg_end = card.find('div', string=lambda text: '報名截止日' in str(text)).text.split('：')[1].strip()
                    
                    button = card.find('button', class_='btn-primary')
                    status = "開放報名" if button and "活動報名" in button.text else "已額滿"
                    
                    return EventStatus(
                        name=name,
                        location=location,
                        event_date=event_date,
                        registration_start=reg_start,
                        registration_end=reg_end,
                        status=status,
                        last_checked=datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S')
                    )
        except Exception as e:
            logger.error(f"解析活動卡片失敗: {str(e)}")
            continue
    
    return None

async def send_telegram_message(message: str):
    """發送 Telegram 通知"""
    url = f"https://api.telegram.org/bot{Settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json={
                "chat_id": Settings.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            })
            response.raise_for_status()
            logger.info("Telegram 通知發送成功")
        except Exception as e:
            logger.error(f"Telegram 通知發送失敗: {str(e)}")

async def check_event():
    """檢查課程狀態並發送通知"""
    logger.info("開始檢查課程狀態")
    html_content = get_page_content()
    
    if not html_content:
        error_message = "無法獲取頁面內容，可能需要重新登入"
        logger.error(error_message)
        await send_telegram_message(f"⚠️ 監控系統警告\n\n{error_message}")
        cookie_manager.clear_cookies()  # 清除可能失效的 cookies
        return
        
    event = parse_event(html_content)
    
    if event and event.status == "開放報名" and event.name not in notified_events:
        message = f"""
🎯 <b>課程報名開放通知！</b>

課程名稱: {event.name}
活動地點: {event.location}
活動日期: {event.event_date}
報名期間: {event.registration_start} 至 {event.registration_end}
目前狀態: ⭐ 開放報名中 ⭐

快去報名吧！
🔗 報名連結: {TARGET_URL}
"""
        await send_telegram_message(message)
        notified_events.add(event.name)
        logger.info(f"發送通知: {event.name} 開放報名")
    
    elif event:
        logger.info(f"課程狀態: {event.name} - {event.status}")
    else:
        logger.warning("未找到目標課程")

@app.on_event("startup")
async def startup_event():
    """啟動排程器"""
    scheduler.add_job(check_event, 'interval', seconds=SCAN_INTERVAL, id='check_event')
    scheduler.start()
    logger.info("排程器已啟動")

@app.get("/status")
async def get_status():
    """獲取目前監控狀態"""
    html_content = get_page_content()
    event = parse_event(html_content)
    return {
        "status": "running",
        "last_checked": datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S'),
        "current_event": event,
        "cookies_valid": cookie_manager.is_cookie_valid()
    }

@app.get("/login/test")
async def test_login():
    """測試登入功能"""
    driver = None
    try:
        driver = setup_driver()
        login_status = login(driver)
        return login_status
    finally:
        if driver:
            driver.quit()

@app.get("/cookies/clear")
async def clear_cookies():
    """清除已保存的 cookies"""
    cookie_manager.clear_cookies()
    return {"message": "Cookies 已清除"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)