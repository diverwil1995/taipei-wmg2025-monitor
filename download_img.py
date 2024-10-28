import asyncio
from pathlib import Path
import random
from fastapi import FastAPI, HTTPException, BackgroundTasks, logger
import httpx
from pydantic import BaseModel
from typing import List, Optional
import json
from datetime import datetime

app = FastAPI(title="驗證碼圖片下載 API")

# 用於存儲下載任務狀態
class DownloadStatus:
    def __init__(self):
        self.is_running = False
        self.last_run = None
        self.results = None
        self.error = None

download_status = DownloadStatus()

class DownloadRange(BaseModel):
    start: int = 1
    end: int = 100
    output_dir: str = "captcha_images"

class DownloadResult(BaseModel):
    task_id: str
    status: str
    start_time: str
    total_images: Optional[int] = None
    found_images: Optional[List[int]] = None
    error: Optional[str] = None

@app.post("/download-captchas", response_model=DownloadResult)
async def start_download(params: DownloadRange, background_tasks: BackgroundTasks):
    """
    開始下載驗證碼圖片的任務
    """
    if download_status.is_running:
        raise HTTPException(status_code=400, detail="已有下載任務正在執行中")
    
    download_status.is_running = True
    download_status.last_run = datetime.now()
    download_status.results = None
    download_status.error = None
    
    task_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    background_tasks.add_task(
        download_captcha_images_task,
        params.start,
        params.end,
        params.output_dir
    )
    
    return DownloadResult(
        task_id=task_id,
        status="running",
        start_time=download_status.last_run.isoformat()
    )

@app.get("/download-status", response_model=DownloadResult)
async def get_download_status():
    """
    獲取當前下載任務的狀態
    """
    if not download_status.last_run:
        raise HTTPException(status_code=404, detail="尚未執行任何下載任務")
    
    return DownloadResult(
        task_id=download_status.last_run.strftime("%Y%m%d%H%M%S"),
        status="running" if download_status.is_running else "completed",
        start_time=download_status.last_run.isoformat(),
        total_images=len(download_status.results) if download_status.results else None,
        found_images=download_status.results,
        error=download_status.error
    )

async def download_captcha_images_task(start: int, end: int, output_dir: str):
    """
    背景執行下載任務
    """
    try:
        # 創建輸出目錄
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        base_url = "https://www.wmg2025warmup.org.tw/images/check/{}.jpg"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        found_images = []
        
        logger.info(f"開始下載驗證碼圖片 (範圍: {start}-{end})...")
        
        async with httpx.AsyncClient() as client:
            for i in range(start, end + 1):
                url = base_url.format(i)
                file_path = output_path / f"{i}.jpg"
                
                try:
                    # 隨機延遲，避免請求過快
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 200:
                        # 檢查是否真的是圖片
                        content_type = response.headers.get('content-type', '')
                        if 'image' in content_type:
                            # 保存圖片
                            with open(file_path, 'wb') as f:
                                f.write(response.content)
                            found_images.append(i)
                            logger.info(f"成功下載圖片 {i}.jpg")
                        else:
                            logger.warning(f"編號 {i} 不是圖片檔案")
                    elif response.status_code == 404:
                        logger.debug(f"圖片 {i}.jpg 不存在")
                    else:
                        logger.warning(f"下載圖片 {i}.jpg 失敗，狀態碼: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"處理圖片 {i}.jpg 時發生錯誤: {str(e)}")
        
        download_status.results = found_images
        logger.info(f"下載完成！總共找到 {len(found_images)} 張圖片")
        
    except Exception as e:
        download_status.error = str(e)
        logger.error(f"下載任務執行失敗: {str(e)}")
    finally:
        download_status.is_running = False

@app.get("/download-results")
async def get_download_results():
    """
    獲取所有已下載的圖片資訊
    """
    if not download_status.results:
        raise HTTPException(status_code=404, detail="尚無下載結果")
    
    return {
        "total_images": len(download_status.results),
        "found_images": download_status.results,
        "last_run": download_status.last_run.isoformat() if download_status.last_run else None
    }

@app.post("/clear-status")
async def clear_status():
    """
    清除下載狀態
    """
    download_status.is_running = False
    download_status.last_run = None
    download_status.results = None
    download_status.error = None
    return {"message": "狀態已清除"}