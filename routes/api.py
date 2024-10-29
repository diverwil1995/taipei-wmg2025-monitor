import logging
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import List, Optional
import pytz

from models.schemas import LoginStatus, EventStatus, EventQuery
from services.browser import setup_driver
from services.login import login
from services.event import get_page_content, parse_event
from utils.cookie_manager import CookieManager

router = APIRouter()
cookie_manager = CookieManager()

@router.get("/status")
async def get_status():
    """獲取目前監控狀態"""
    driver = None
    try:
        driver = setup_driver()
        html_content = get_page_content(driver)
        event = parse_event(html_content)
        return {
            "status": "running",
            "last_checked": datetime.now(pytz.timezone('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S'),
            "current_event": event,
            "cookies_valid": cookie_manager.is_cookie_valid()
        }
    finally:
        if driver:
            driver.quit()

@router.get("/events", response_model=List[EventStatus])
async def get_events():
    """獲取所有課程狀態"""
    driver = None
    try:
        driver = setup_driver()
        html_content = get_page_content(driver)
        events = parse_event(html_content)
        if not events:
            return []
        return events if isinstance(events, list) else [events]
    finally:
        if driver:
            driver.quit()

@router.get("/events/search", response_model=Optional[EventStatus])
async def search_event(event_name: Optional[str] = None, event_date: Optional[str] = None):
    """搜尋特定課程狀態
    
    Args:
        event_name: 課程名稱
        event_date: 活動日期 (YYYY/MM/DD格式)
    """
    if not event_name and not event_date:
        raise HTTPException(status_code=400, detail="必須提供課程名稱或活動日期")
        
    driver = None
    try:
        driver = setup_driver()
        html_content = get_page_content(driver)
        event = parse_event(html_content, event_name, event_date)
        if not event:
            raise HTTPException(status_code=404, detail="未找到符合條件的課程")
        return event
    finally:
        if driver:
            driver.quit()

@router.get("/login/test")
async def test_login():
    """測試登入功能"""
    driver = None
    try:
        driver = setup_driver()
        login_status = login(driver, cookie_manager)
        return login_status
    finally:
        if driver:
            driver.quit()

@router.get("/cookies/clear")
async def clear_cookies():
    """清除已保存的 cookies"""
    cookie_manager.clear_cookies()
    return {"message": "Cookies 已清除"}
