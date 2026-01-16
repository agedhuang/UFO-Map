"""
NUFORC UFO 图片爬虫
从详情页抓取所有带图片的报告，包括图片URL、报告信息和Tier等级
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin
from tqdm import tqdm


class UFOImageScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.all_images = []
        
    def read_tiered_data(self):
        """
        读取已有的Tier数据文件
        """
        try:
            df = pd.read_csv('ufo_data_tiered.csv')
            print(f"读取到 {len(df)} 条Tier数据")
            return df
        except Exception as e:
            print(f"读取Tier数据失败: {e}")
            return pd.DataFrame()
    
    def extract_image_from_detail_page(self, report_url):
        """
        从详情页提取图片URL和相关信息
        """
        try:
            response = self.session.get(report_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取基本信息
            date = ''
            city = ''
            state = ''
            shape = ''
            summary = ''
            description = ''
            
            # 查找所有文本内容，尝试提取字段
            text_content = soup.get_text()
            
            # 提取图片
            images = []
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                src = img.get('src', '')
                if src:
                    # 跳过logo和图标
                    if 'logo' in src.lower() or 'icon' in src.lower() or 'button' in src.lower():
                        continue
                    
                    # 构建完整URL
                    if not src.startswith('http'):
                        full_url = urljoin(self.base_url, src)
                    else:
                        full_url = src
                    
                    images.append(full_url)
            
            # 如果没有找到图片，返回None
            if not images:
                return None
            
            # 尝试从页面提取报告信息
            # 查找包含日期的文本
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text_content)
            if date_match:
                date = date_match.group(1)
            
            # 查找城市和州
            city_match = re.search(r'City[:\s]+([^,\n]+)', text_content, re.IGNORECASE)
            if city_match:
                city = city_match.group(1).strip()
            
            state_match = re.search(r'State[:\s]+([A-Z]{2})', text_content, re.IGNORECASE)
            if state_match:
                state = state_match.group(1)
            
            # 查找Shape
            shape_match = re.search(r'Shape[:\s]+([^\n]+)', text_content, re.IGNORECASE)
            if shape_match:
                shape = shape_match.group(1).strip()[:50]
            
            # 提取描述（前500字符）
            paragraphs = soup.find_all('p')
            description_texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
            description = ' '.join(description_texts)[:500]
            
            return {
                'images': images,
                'date': date,
                'city': city,
                'state': state,
                'shape': shape,
                'description': description,
                'report_url': report_url
            }
            
        except Exception as e:
            print(f"\n提取图片失败 ({report_url}): {e}")
            return None
    
    def scrape_all_images(self):
        """
        主爬取函数：从Tier数据中提取所有报告链接，然后访问详情页抓取图片
        """
        print("=" * 60)
        print("NUFORC UFO 图片爬虫启动")
        print("=" * 60)
        
        # 1. 读取Tier数据
        tier_df = self.read_tiered_data()
        if tier_df.empty:
            print("未找到Tier数据文件，程序退出")
            return
        
        # 2. 筛选有Report_Link的记录
        reports_with_links = tier_df[tier_df['Report_Link'].notna() & (tier_df['Report_Link'] != '')]
        print(f"\n找到 {len(reports_with_links)} 条有链接的报告")
        
        # 3. 遍历所有报告，提取图片（8分钟内尽可能多地获取）
        print("\n开始抓取图片...")
        print("⚠️ 快速模式：8分钟内尽可能多地获取图片")
        import time as time_module
        start_time = time_module.time()
        time_limit = 8 * 60  # 8分钟
        
        # 优先处理Tier 1/2的报告
        tier_reports = reports_with_links[reports_with_links['Is_High_Tier'] == True]
        normal_reports = reports_with_links[reports_with_links['Is_High_Tier'] != True]
        
        # 先处理Tier报告
        all_reports = pd.concat([tier_reports, normal_reports])
        
        for idx, row in tqdm(all_reports.iterrows(), total=len(all_reports), desc="抓取报告", unit="个"):
            # 检查时间限制
            elapsed = time_module.time() - start_time
            if elapsed > time_limit:
                print(f"\n⏰ 时间限制到达（8分钟），已获取 {len(self.all_images)} 张图片")
                break
            
            report_url = row['Report_Link']
            is_high_tier = row.get('Is_High_Tier', False)
            
            # 访问详情页提取图片
            image_data = self.extract_image_from_detail_page(report_url)
            
            if image_data and image_data['images']:
                # 为每张图片创建一条记录
                for img_url in image_data['images']:
                    self.all_images.append({
                        'Image_URL': img_url,
                        'Report_URL': report_url,
                        'Date': image_data.get('date', row.get('Date', '')),
                        'City': image_data.get('city', row.get('City', '')),
                        'State': image_data.get('state', row.get('State', '')),
                        'Shape': image_data.get('shape', row.get('Shape', '')),
                        'Summary': row.get('Summary', ''),
                        'Description': image_data.get('description', ''),
                        'Is_High_Tier': is_high_tier,
                        'Tier': 'Tier 1/2' if is_high_tier else 'Normal'
                    })
                    
                    # 如果已经获取了足够的图片，提前退出
                    if len(self.all_images) >= 50:
                        break
            
            # 每次请求后休息0.3秒（加快速度，8分钟内获取更多）
            time.sleep(0.3)
        
        # 4. 保存数据
        if not self.all_images:
            print("\n未获取到任何图片数据")
            return
        
        print("\n正在保存数据...")
        df = pd.DataFrame(self.all_images)
        
        # 确保列的顺序
        columns_order = ['Image_URL', 'Report_URL', 'Date', 'City', 'State', 'Shape', 'Summary', 'Description', 'Is_High_Tier', 'Tier']
        df = df[columns_order]
        
        # 保存数据
        output_file = 'ufo_images.csv'
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        # 输出统计
        print("\n" + "=" * 60)
        print("✅ 抓取完成！")
        print(f"📊 总共获取了 {len(df)} 张图片")
        print(f"⭐ Tier 1/2 图片: {df['Is_High_Tier'].sum()} 张 ({df['Is_High_Tier'].sum()/len(df)*100:.2f}%)")
        print(f"💾 文件已保存至 {output_file}")
        print("=" * 60)


def main():
    scraper = UFOImageScraper()
    scraper.scrape_all_images()


if __name__ == "__main__":
    main()

