import csv
import os
import requests
import math
import json
from PIL import Image
from io import BytesIO
import concurrent.futures
import threading

# 配置
CSV_FILE = 'ufo_images.csv'
OUTPUT_DIR = 'sprites'
SPRITE_SIZE = 128  # 每个小图的大小
ATLAS_SIZE = 2048  # 大图（纹理）的大小
MAX_IMAGES = None   # 演示用：限制处理图片数量，以免下载太久。想处理全部请设为 None
MAX_WORKERS = 20    # 线程数

def generate_spritesheets():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # 读取CSV
    images = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Image_URL']:
                images.append(row)

    if MAX_IMAGES:
        images = images[:MAX_IMAGES]

    print(f"Found {len(images)} images. Starting processing with {MAX_WORKERS} threads...")

    # 计算容量
    cols = ATLAS_SIZE // SPRITE_SIZE
    rows = ATLAS_SIZE // SPRITE_SIZE
    images_per_atlas = cols * rows
    
    current_atlas_index = 0
    current_image_index = 0
    atlas_image = Image.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))
    
    manifest = [] # 存储映射关系
    
    # 线程锁
    lock = threading.Lock()

    def process_image(index, item):
        url = item['Image_URL']
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                img = resize_and_crop(img, SPRITE_SIZE)
                return index, item, img
        except Exception as e:
            # print(f"Error processing {url}: {e}")
            pass
        return index, item, None

    # 使用线程池下载
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_index = {executor.submit(process_image, i, item): i for i, item in enumerate(images)}
        
        completed_count = 0
        total_count = len(images)

        for future in concurrent.futures.as_completed(future_to_index):
            original_idx, item, img = future.result()
            completed_count += 1
            
            if completed_count % 100 == 0:
                print(f"Processed {completed_count}/{total_count} images...")

            if img:
                with lock:
                    # 计算在大图中的位置
                    atlas_local_idx = current_image_index % images_per_atlas
                    row_idx = atlas_local_idx // cols
                    col_idx = atlas_local_idx % cols
                    
                    x = col_idx * SPRITE_SIZE
                    y = row_idx * SPRITE_SIZE
                    
                    # 粘贴到大图
                    atlas_image.paste(img, (x, y))
                    
                    # 记录元数据
                    manifest.append({
                        'original_index': original_idx,
                        'atlas_index': current_atlas_index,
                        'u': x / ATLAS_SIZE,
                        'v': y / ATLAS_SIZE,
                        'w': SPRITE_SIZE / ATLAS_SIZE,
                        'h': SPRITE_SIZE / ATLAS_SIZE
                    })
                    
                    current_image_index += 1
                    
                    # 如果大图满了，保存并开始下一张
                    if (current_image_index % images_per_atlas) == 0:
                        save_atlas(atlas_image, current_atlas_index)
                        current_atlas_index += 1
                        atlas_image = Image.new('RGBA', (ATLAS_SIZE, ATLAS_SIZE), (0, 0, 0, 0))

    # 保存最后一张未满的大图
    if (current_image_index % images_per_atlas) != 0:
        save_atlas(atlas_image, current_atlas_index)

    # 保存清单文件
    with open(os.path.join(OUTPUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False)
    
    print("Done! Spritesheets generated in 'sprites' folder.")

def resize_and_crop(img, size):
    # 保持比例缩放，填满正方形
    ratio = max(size / img.width, size / img.height)
    new_size = (int(img.width * ratio), int(img.height * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    
    # 居中裁剪
    left = (img.width - size) / 2
    top = (img.height - size) / 2
    right = (img.width + size) / 2
    bottom = (img.height + size) / 2
    
    return img.crop((left, top, right, bottom))

def save_atlas(img, index):
    filename = f"atlas_{index}.jpg"
    path = os.path.join(OUTPUT_DIR, filename)
    if img.mode == 'RGBA':
        background = Image.new("RGB", img.size, (0, 0, 0))
        background.paste(img, mask=img.split()[3]) 
        img = background
    img.save(path, quality=85)
    print(f"Saved atlas: {filename}")

if __name__ == "__main__":
    generate_spritesheets()
