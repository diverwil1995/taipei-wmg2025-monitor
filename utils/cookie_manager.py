import pickle
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class CookieManager:
    def __init__(self, cookie_max_age: int = 24 * 60 * 60):
        self.cookie_dir = Path('data')
        self.cookie_dir.mkdir(exist_ok=True)
        self.cookie_file = self.cookie_dir / 'wmg_cookies.pkl'
        self.cookie_timestamp_file = self.cookie_dir / 'cookie_timestamp.txt'
        self.cookie_max_age = cookie_max_age

    def save_cookies(self, driver) -> bool:
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

    def load_cookies(self, driver) -> bool:
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

    def clear_cookies(self) -> bool:
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

    def is_cookie_valid(self) -> bool:
        """檢查 cookies 是否有效"""
        try:
            if not self.cookie_timestamp_file.exists():
                return False
                
            with open(self.cookie_timestamp_file, 'r') as f:
                timestamp = float(f.read().strip())
            saved_time = datetime.fromtimestamp(timestamp)
            return (datetime.now() - saved_time).total_seconds() < self.cookie_max_age
        except Exception as e:
            logger.error(f"檢查 Cookies 有效性失敗: {str(e)}")
            return False
