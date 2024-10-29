import logging
import os
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx
import pytesseract
from typing import Set

from routes.api import router
from services.browser import setup_driver
from services.event import get_page_content, parse_event
from utils.cookie_manager import CookieManager
from config import Settings, TARGET_URL

# 設定日誌
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 設定 tesseract 路徑
TESSERACT_CMD = '/opt/homebrew/bin/tesseract'
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    logger.info(f"Successfully set tesseract path to: {TESSERACT_CMD}")
else:
    logger.error(f"Tesseract not found at {TESSERACT_CMD}")
    raise RuntimeError(f"Tesseract not found at {TESSERACT_CMD}. Please verify the installation.")

app = FastAPI(title="世壯運訓練營課程監控系統")
scheduler = AsyncIOScheduler()
notified_events: Set[str] = set()
cookie_manager = CookieManager()

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
    driver = None
    try:
        driver = setup_driver()
        html_content = get_page_content(driver)
        
        if not html_content:
            error_message = "無法獲取頁面內容，可能需要重新登入"
            logger.error(error_message)
            await send_telegram_message(f"⚠️ 監控系統警告\n\n{error_message}")
            cookie_manager.clear_cookies()
            return
            
        events = parse_event(html_content)
        
        if not events:
            logger.warning("未找到任何課程")
            return

        # 遍歷所有事件
        for event in events:
            if event.status == "開放報名" and event.name not in notified_events:
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
            else:
                logger.info(f"課程狀態: {event.name} - {event.status}")
                
    finally:
        if driver:
            driver.quit()

@app.on_event("startup")
async def startup_event():
    """啟動排程器"""
    scheduler.add_job(check_event, 'interval', seconds=60, id='check_event')
    scheduler.start()
    logger.info("排程器已啟動")

# 註冊路由
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
