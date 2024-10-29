import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import base64

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from models.schemas import LoginStatus
from utils.cookie_manager import CookieManager
from config import Settings, BASE_URL, LOGIN_URL

logger = logging.getLogger(__name__)

# 定義重試相關常數
MAX_RETRIES = 3  # 最大重試次數
RETRY_DELAY = 2  # 重試間隔（秒）

# 定義認證碼圖片數字對應表
CAPTCHA_DICT = {
    "https://www.wmg2025warmup.org.tw/images/check/1.jpg": "14687",
    "https://www.wmg2025warmup.org.tw/images/check/2.jpg": "14689",
    "https://www.wmg2025warmup.org.tw/images/check/3.jpg": "15698",
    "https://www.wmg2025warmup.org.tw/images/check/4.jpg": "15937",
    "https://www.wmg2025warmup.org.tw/images/check/5.jpg": "18139",
    "https://www.wmg2025warmup.org.tw/images/check/6.jpg": "19534",
    "https://www.wmg2025warmup.org.tw/images/check/7.jpg": "19734",
    "https://www.wmg2025warmup.org.tw/images/check/8.jpg": "23498",
    "https://www.wmg2025warmup.org.tw/images/check/9.jpg": "24395",
    "https://www.wmg2025warmup.org.tw/images/check/10.jpg": "25463",
    "https://www.wmg2025warmup.org.tw/images/check/11.jpg": "25489",
    "https://www.wmg2025warmup.org.tw/images/check/12.jpg": "25843",
    "https://www.wmg2025warmup.org.tw/images/check/13.jpg": "26459",
    "https://www.wmg2025warmup.org.tw/images/check/14.jpg": "27951",
    "https://www.wmg2025warmup.org.tw/images/check/15.jpg": "28549",
    "https://www.wmg2025warmup.org.tw/images/check/16.jpg": "29514",
    "https://www.wmg2025warmup.org.tw/images/check/17.jpg": "31244",
    "https://www.wmg2025warmup.org.tw/images/check/18.jpg": "32236",
    "https://www.wmg2025warmup.org.tw/images/check/19.jpg": "33468",
    "https://www.wmg2025warmup.org.tw/images/check/20.jpg": "34974",
    "https://www.wmg2025warmup.org.tw/images/check/21.jpg": "37192",
    "https://www.wmg2025warmup.org.tw/images/check/22.jpg": "39631",
    "https://www.wmg2025warmup.org.tw/images/check/23.jpg": "39716",
    "https://www.wmg2025warmup.org.tw/images/check/24.jpg": "42217",
    "https://www.wmg2025warmup.org.tw/images/check/25.jpg": "42368",
    "https://www.wmg2025warmup.org.tw/images/check/26.jpg": "42467",
    "https://www.wmg2025warmup.org.tw/images/check/27.jpg": "43971",
    "https://www.wmg2025warmup.org.tw/images/check/28.jpg": "44431",
    "https://www.wmg2025warmup.org.tw/images/check/29.jpg": "45621",
    "https://www.wmg2025warmup.org.tw/images/check/30.jpg": "45628",
    "https://www.wmg2025warmup.org.tw/images/check/31.jpg": "47641",
    "https://www.wmg2025warmup.org.tw/images/check/32.jpg": "48379",
    "https://www.wmg2025warmup.org.tw/images/check/33.jpg": "48461",
    "https://www.wmg2025warmup.org.tw/images/check/34.jpg": "49389",
    "https://www.wmg2025warmup.org.tw/images/check/35.jpg": "49431",
    "https://www.wmg2025warmup.org.tw/images/check/36.jpg": "49731",
    "https://www.wmg2025warmup.org.tw/images/check/37.jpg": "49768",
    "https://www.wmg2025warmup.org.tw/images/check/38.jpg": "49837",
    "https://www.wmg2025warmup.org.tw/images/check/39.jpg": "18139",
    "https://www.wmg2025warmup.org.tw/images/check/40.jpg": "51456",
    "https://www.wmg2025warmup.org.tw/images/check/41.jpg": "52168",
    "https://www.wmg2025warmup.org.tw/images/check/42.jpg": "52497",
    "https://www.wmg2025warmup.org.tw/images/check/43.jpg": "54682",
    "https://www.wmg2025warmup.org.tw/images/check/44.jpg": "54936",
    "https://www.wmg2025warmup.org.tw/images/check/45.jpg": "55518",
    "https://www.wmg2025warmup.org.tw/images/check/46.jpg": "56197",
    "https://www.wmg2025warmup.org.tw/images/check/47.jpg": "59318",
    "https://www.wmg2025warmup.org.tw/images/check/48.jpg": "19534",
    "https://www.wmg2025warmup.org.tw/images/check/49.jpg": "62551",
    "https://www.wmg2025warmup.org.tw/images/check/50.jpg": "62893",
    "https://www.wmg2025warmup.org.tw/images/check/51.jpg": "63594",
    "https://www.wmg2025warmup.org.tw/images/check/52.jpg": "64379",
    "https://www.wmg2025warmup.org.tw/images/check/53.jpg": "64568",
    "https://www.wmg2025warmup.org.tw/images/check/54.jpg": "64587",
    "https://www.wmg2025warmup.org.tw/images/check/55.jpg": "64829",
    "https://www.wmg2025warmup.org.tw/images/check/56.jpg": "64939",
    "https://www.wmg2025warmup.org.tw/images/check/57.jpg": "65628",
    "https://www.wmg2025warmup.org.tw/images/check/58.jpg": "69697",
    "https://www.wmg2025warmup.org.tw/images/check/59.jpg": "19734",
    "https://www.wmg2025warmup.org.tw/images/check/60.jpg": "71234",
    "https://www.wmg2025warmup.org.tw/images/check/61.jpg": "71395",
    "https://www.wmg2025warmup.org.tw/images/check/62.jpg": "71598",
    "https://www.wmg2025warmup.org.tw/images/check/63.jpg": "72956",
    "https://www.wmg2025warmup.org.tw/images/check/64.jpg": "73198",
    "https://www.wmg2025warmup.org.tw/images/check/65.jpg": "73597",
    "https://www.wmg2025warmup.org.tw/images/check/66.jpg": "74927",
    "https://www.wmg2025warmup.org.tw/images/check/67.jpg": "75188",
    "https://www.wmg2025warmup.org.tw/images/check/68.jpg": "75318",
    "https://www.wmg2025warmup.org.tw/images/check/69.jpg": "76138",
    "https://www.wmg2025warmup.org.tw/images/check/70.jpg": "76249",
    "https://www.wmg2025warmup.org.tw/images/check/71.jpg": "77539",
    "https://www.wmg2025warmup.org.tw/images/check/72.jpg": "79513",
    "https://www.wmg2025warmup.org.tw/images/check/73.jpg": "79841",
    "https://www.wmg2025warmup.org.tw/images/check/74.jpg": "23498",
    "https://www.wmg2025warmup.org.tw/images/check/75.jpg": "81394",
    "https://www.wmg2025warmup.org.tw/images/check/76.jpg": "82643",
    "https://www.wmg2025warmup.org.tw/images/check/77.jpg": "82964",
    "https://www.wmg2025warmup.org.tw/images/check/78.jpg": "83461",
    "https://www.wmg2025warmup.org.tw/images/check/79.jpg": "84379",
    "https://www.wmg2025warmup.org.tw/images/check/80.jpg": "84399",
    "https://www.wmg2025warmup.org.tw/images/check/81.jpg": "84638",
    "https://www.wmg2025warmup.org.tw/images/check/82.jpg": "84679",
    "https://www.wmg2025warmup.org.tw/images/check/83.jpg": "84918",
    "https://www.wmg2025warmup.org.tw/images/check/84.jpg": "84974",
    "https://www.wmg2025warmup.org.tw/images/check/85.jpg": "85246",
    "https://www.wmg2025warmup.org.tw/images/check/86.jpg": "86324",
    "https://www.wmg2025warmup.org.tw/images/check/87.jpg": "86648",
    "https://www.wmg2025warmup.org.tw/images/check/88.jpg": "87344",
    "https://www.wmg2025warmup.org.tw/images/check/89.jpg": "88248",
    "https://www.wmg2025warmup.org.tw/images/check/90.jpg": "89134",
    "https://www.wmg2025warmup.org.tw/images/check/91.jpg": "89374",
    "https://www.wmg2025warmup.org.tw/images/check/92.jpg": "24395",
    "https://www.wmg2025warmup.org.tw/images/check/93.jpg": "91974",
    "https://www.wmg2025warmup.org.tw/images/check/94.jpg": "92468",
    "https://www.wmg2025warmup.org.tw/images/check/95.jpg": "92954",
    "https://www.wmg2025warmup.org.tw/images/check/96.jpg": "93468",
    "https://www.wmg2025warmup.org.tw/images/check/97.jpg": "93492",
    "https://www.wmg2025warmup.org.tw/images/check/98.jpg": "95713",
    "https://www.wmg2025warmup.org.tw/images/check/99.jpg": "96352",
    "https://www.wmg2025warmup.org.tw/images/check/100.jpg": "96548",
    "https://www.wmg2025warmup.org.tw/images/check/101.jpg": "96567",
    "https://www.wmg2025warmup.org.tw/images/check/102.jpg": "96846",
    "https://www.wmg2025warmup.org.tw/images/check/103.jpg": "96934",
    "https://www.wmg2025warmup.org.tw/images/check/104.jpg": "98165",
    "https://www.wmg2025warmup.org.tw/images/check/105.jpg": "99624"
  }

# 獲取專案根目錄
BASE_DIR = Path(__file__).resolve().parent.parent

def check_login_status(driver) -> bool:
    """檢查是否已登入"""
    try:
        # 先處理可能出現的 Alert
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text
            logger.info(f"檢測到 Alert: {alert_text}")
            if "已登入" in alert_text:
                alert.accept()
                return True
        except Exception:
            pass

        # 檢查 URL
        current_url = driver.current_url
        return "member_login.php" not in current_url
            
    except Exception as e:
        logger.error(f"檢查登入狀態失敗: {str(e)}")
        return False

def login(driver, cookie_manager: CookieManager, retry_count=0) -> LoginStatus:
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
        time.sleep(3)
        
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
            
            # 獲取圖片的src屬性
            image_src = captcha_image.get_attribute('src')
            
            # 從字典中獲取驗證碼
            captcha_text = CAPTCHA_DICT[image_src]
            
            if captcha_text:
                logger.info(f"從字典中找到驗證碼: {captcha_text}")
                captcha_input.clear()
                captcha_input.send_keys(captcha_text)
                time.sleep(1)
            else:
                logger.error(f"在字典中找不到對應的驗證碼: {image_src}")
                if retry_count < MAX_RETRIES:
                    return login(driver, cookie_manager, retry_count + 1)
                return LoginStatus(success=False, message="在字典中找不到對應的驗證碼")
                
        except Exception as e:
            logger.error(f"處理驗證碼時發生錯誤: {str(e)}")
            if retry_count < MAX_RETRIES:
                return login(driver, cookie_manager, retry_count + 1)
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
            elif "驗證碼錯誤" in alert_text:
                alert.accept()
                logger.warning("驗證碼錯誤，重試中...")
                if retry_count < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    return login(driver, cookie_manager, retry_count + 1)
                return LoginStatus(success=False, message="驗證碼錯誤次數過多")
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
                return login(driver, cookie_manager, retry_count + 1)
            else:
                return LoginStatus(success=False, message="登入重試次數超過上限")

    except Exception as e:
        logger.error(f"登入過程發生錯誤: {str(e)}", exc_info=True)
        if retry_count < MAX_RETRIES:
            return login(driver, cookie_manager, retry_count + 1)
        return LoginStatus(success=False, message=f"登入錯誤: {str(e)}")