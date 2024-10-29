import logging
from typing import Optional
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from models.schemas import EventStatus
from config import TARGET_URL, TARGET_EVENT, TARGET_LOCATION

logger = logging.getLogger(__name__)

def get_page_content(driver):
    """獲取活動頁面內容"""
    try:
        # 訪問目標頁面
        logger.info("訪問活動頁面")
        driver.get(TARGET_URL)
        wait = WebDriverWait(driver, 20)
        
        try:
            # 等待頁面載入
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
