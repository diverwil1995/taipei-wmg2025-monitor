import logging
from fastapi import APIRouter, HTTPException
from datetime import datetime
import pytz

from models.schemas import LoginStatus, EventStatus
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
