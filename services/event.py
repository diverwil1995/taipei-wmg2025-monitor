import logging
from typing import Optional, List
from datetime import datetime
import pytz
import time
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from models.schemas import EventStatus
from config import TARGET_URL

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
                By.CLASS_NAME, "activity-card"
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

def parse_event(html_content: str, target_event: Optional[str] = None, target_date: Optional[str] = None) -> Optional[EventStatus]:
    """解析課程資訊
    
    Args:
        html_content: HTML內容
        target_event: 目標課程名稱，如果為None則返回所有課程
        target_date: 目標活動日期，格式為YYYY/MM/DD，如果為None則不過濾日期
    """
    if not html_content:
        return None
        
    soup = BeautifulSoup(html_content, 'html.parser')
    cards = soup.find_all('div', class_='activity-card')
    
    events = []
    for card in cards:
        try:
            name = card.find('h2').text.strip()
            
            # 如果指定了課程名稱且不匹配，則跳過
            if target_event and name != target_event:
                continue
                
            location = card.find('h3').find('span').text.strip()
            event_date = card.find('h4').text.strip()
            
            # 如果指定了日期且不匹配，則跳過
            if target_date:
                event_date_str = event_date.split(' ')[0]  # 提取日期部分
                if event_date_str != target_date:
                    continue
            
            reg_start = card.find_all('h4')[1].text.strip()
            reg_end = card.find_all('h4')[2].text.strip()
            
            # 檢查狀態
            state_full = card.find('b', class_='stateFull')
            status = "已額滿" if state_full else "開放報名"
            
            event = EventStatus(
                name=name,
                location=location,
                event_date=event_date,
                registration_start=reg_start,
                registration_end=reg_end,
                status=status,
                last_checked=datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S')
            )
            # 如果指定了特定課程，直接返回匹配的結果
            if target_event and target_date:
                return event
            events.append(event)
            
        except Exception as e:
            logger.error(f"解析活動卡片失敗: {str(e)}")
            continue
    
    # 如果指定了特定課程但沒找到，返回None
    if target_event or target_date:
        return None
        
    # 返回所有找到的課程
    return events
