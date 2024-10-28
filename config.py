from dotenv import load_dotenv
import os
from pathlib import Path

# 獲取項目根目錄
BASE_DIR = Path(__file__).resolve().parent

# 加載 .env 檔案
load_dotenv(BASE_DIR / '.env')

# 網站設定
BASE_URL = "https://www.wmg2025warmup.org.tw"
LOGIN_URL = f"{BASE_URL}/member_login.php"
TARGET_URL = f"{BASE_URL}/index.php?folder=&level=&activity_date=課程報名中#event"

# 從環境變數獲取敏感資訊
class Settings:
    WMG_USERNAME = os.getenv("WMG_USERNAME")
    WMG_PASSWORD = os.getenv("WMG_PASSWORD")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # 驗證必要的設定是否存在
    @classmethod
    def validate(cls):
        missing_vars = []
        for var in ["WMG_USERNAME", "WMG_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"缺少必要的環境變數: {', '.join(missing_vars)}")

# 目標設定
SCAN_INTERVAL = 300  # 5分鐘
TARGET_EVENT = "射箭-反曲弓進階"
TARGET_LOCATION = "新北市輔大射箭場"