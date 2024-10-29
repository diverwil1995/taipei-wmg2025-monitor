import requests
import os
import json
from tqdm import tqdm

def download_image(url, save_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    return False

def main():
    # 創建保存圖片的目錄
    if not os.path.exists('downloaded_captchas'):
        os.makedirs('downloaded_captchas')

    base_url = "https://www.wmg2025warmup.org.tw/images/check/{}.jpg"
    results = {}

    # 使用tqdm顯示進度條
    for i in tqdm(range(1, 106)):
        url = base_url.format(i)
        save_path = f'downloaded_captchas/{i}.jpg'
        
        # 下載圖片
        if download_image(url, save_path):
            results[str(i)] = ""  # 留空供手動填寫
        else:
            results[str(i)] = "download_failed"

    # 保存空的結果字典到JSON文件，供後續填寫
    with open('data/captcha_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
