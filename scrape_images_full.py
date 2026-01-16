"""
NUFORC UFO 图片完整爬虫
从 subndx/?id=all 页面分页获取所有报告数据（1586页，约158574条）
筛选Media=Y的记录，然后访问详情页抓取图片和描述
支持断点续传
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
from urllib.parse import urljoin
from tqdm import tqdm


class UFOImageScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.all_page_url = "https://nuforc.org/subndx/?id=all"
        self.records_per_page = 100  # 每页100条记录
        self.total_pages = 1586  # 总共1586页
        self.total_records = 158574  # 总共约158574条记录
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.all_images = []
    
    def is_yellow_background(self, element):
        """
        检测元素是否有黄色或淡黄色背景
        检查style属性和bgcolor属性
        """
        if not element:
            return False
        
        # 获取style属性和bgcolor属性
        style = element.get('style', '')
        bgcolor = element.get('bgcolor', '')
        
        # 合并所有颜色信息
        all_color_info = (style + ' ' + bgcolor).lower()
        
        # 检查黄色关键词（包括各种可能的黄色变体）
        yellow_keywords = [
            'yellow',
            '#ffff00',  # 纯黄色
            '#ffffc0',  # 淡黄色
            '#ffffcc',  # 淡黄色变体
            '#ffff99',  # 淡黄色变体
            '#ffffe0',  # 淡黄色变体
            '#ffffd0',  # 淡黄色变体
            '#ffffb0',  # 淡黄色变体
            '#fffacd',  # 柠檬雪纺色
            '#fff8dc',  # 玉米色
            '#ffeb3b',  # 亮黄色
            '#ffc107',  # 琥珀色（偏黄）
            'rgb(255, 255, 0)',  # RGB黄色
            'rgb(255, 255, 192)',  # RGB淡黄色
            'rgb(255, 255, 204)',  # RGB淡黄色变体
            'rgb(255, 255, 176)',  # RGB淡黄色变体
            'rgb(255, 255, 224)',  # RGB淡黄色变体
        ]
        
        for keyword in yellow_keywords:
            if keyword in all_color_info:
                return True
        
        # 检查RGB格式 (rgb(255, 255, x) 其中x < 200表示黄色)
        rgb_match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', all_color_info)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            # 黄色特征：R和G都很高(>200)，B较低(<200)
            if r > 200 and g > 200 and b < 200:
                return True
        
        return False
    
    def scrape_paginated_table(self, start=0):
        """
        使用BeautifulSoup解析分页表格，检测Tier
        start: 起始记录位置（0表示第一页，100表示第二页，依此类推）
        """
        try:
            # 构建分页URL
            page_url = f"{self.all_page_url}&start={start}"
            
            # 尝试先使用SSL验证
            try:
                response = self.session.get(page_url, timeout=30, verify=True)
            except Exception as e:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = self.session.get(page_url, timeout=30, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return []
            
            rows = table.find_all('tr')
            if len(rows) < 2:  # 至少需要表头+1行数据
                return []
            
            # 解析表头，找到各列的索引
            header_row = rows[0]
            header_cells = header_row.find_all(['th', 'td'])
            column_indices = {}
            
            for idx, cell in enumerate(header_cells):
                text = cell.get_text(strip=True).lower()
                if 'occurred' in text or 'date' in text:
                    column_indices['date'] = idx
                elif 'city' in text:
                    column_indices['city'] = idx
                elif 'state' in text:
                    column_indices['state'] = idx
                elif 'shape' in text:
                    column_indices['shape'] = idx
                elif 'summary' in text:
                    column_indices['summary'] = idx
                elif 'media' in text:
                    column_indices['media'] = idx
                elif 'link' in text or 'report' in text:
                    column_indices['link'] = idx
            
            # 解析数据行
            page_data = []
            for row in rows[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) < len(header_cells):
                    continue
                
                # 提取各字段
                date = cells[column_indices.get('date', 0)].get_text(strip=True) if 'date' in column_indices else ''
                city = cells[column_indices.get('city', 1)].get_text(strip=True) if 'city' in column_indices else ''
                state = cells[column_indices.get('state', 2)].get_text(strip=True) if 'state' in column_indices else ''
                shape = cells[column_indices.get('shape', 5)].get_text(strip=True) if 'shape' in column_indices else ''
                summary = cells[column_indices.get('summary', 6)].get_text(strip=True) if 'summary' in column_indices else ''
                media = cells[column_indices.get('media', 8)].get_text(strip=True) if 'media' in column_indices else ''
                
                # 提取Report链接并检测Tier
                report_link = ''
                is_high_tier = False
                link_cell_idx = column_indices.get('link', 0)
                if link_cell_idx < len(cells):
                    link_cell = cells[link_cell_idx]
                    
                    # 检测Tier：检查LINK单元格的背景色
                    if self.is_yellow_background(link_cell):
                        is_high_tier = True
                    
                    # 提取链接
                    link_tag = link_cell.find('a', href=True)
                    if link_tag:
                        href = link_tag.get('href', '')
                        if '/sighting/?id=' in href:
                            report_link = urljoin(self.base_url, href)
                        
                        # 检查链接文本中的符号（Tier标记）
                        link_text = link_tag.get_text(strip=True)
                        # 检查链接文本中是否有感叹号（"Open !" 表示 Tier 1）
                        if '!' in link_text:
                            is_high_tier = True
                        # 检查链接文本中是否有点号（"Open ." 表示 Tier 2）
                        elif link_text.endswith('.') or link_text == 'Open .' or 'Open .' in link_text:
                            is_high_tier = True
                        # 检查链接元素是否有黄色背景（备用检测方法）
                        if self.is_yellow_background(link_tag):
                            is_high_tier = True
                
                page_data.append({
                    'Date': date,
                    'City': city,
                    'State': state,
                    'Shape': shape,
                    'Summary': summary,
                    'Media': media,
                    'Report_Link': report_link,
                    'Is_High_Tier': is_high_tier
                })
            
            return page_data
            
        except Exception as e:
            print(f"抓取分页表格失败 (start={start}): {e}")
            return []
    
    def extract_image_from_detail_page(self, report_url):
        """从详情页提取图片URL和相关信息"""
        try:
            # 尝试先使用SSL验证
            try:
                response = self.session.get(report_url, timeout=10, verify=True)
            except Exception as e:
                # 如果SSL验证失败，尝试禁用SSL验证
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = self.session.get(report_url, timeout=10, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取图片
            images = []
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                src = img.get('src', '')
                if src:
                    # 跳过logo和图标（只过滤明确的logo/icon/button）
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
            
            # 提取基本信息
            text_content = soup.get_text()
            date = ''
            city = ''
            state = ''
            shape = ''
            description = ''
            
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
            return None
    
    def load_existing_images(self):
        """加载已有的图片数据，用于断点续传"""
        try:
            df = pd.read_csv('ufo_images.csv')
            processed_reports = set(df['Report_URL'].unique())
            existing_images = df.to_dict('records')
            print(f"📂 发现已有数据：{len(existing_images)} 张图片，{len(processed_reports)} 个报告已处理")
            return existing_images, processed_reports
        except FileNotFoundError:
            print("📂 未找到已有数据文件，将从头开始")
            return [], set()
        except Exception as e:
            print(f"⚠️ 读取已有数据时出错: {e}，将从头开始")
            return [], set()
    
    def scrape_all_images(self):
        """主爬取函数：从数据文件读取数据，筛选Media=Y的记录，然后访问详情页抓取图片"""
        print("=" * 60)
        print("NUFORC UFO 图片完整爬虫启动（支持断点续传）")
        print("=" * 60)
        
        # 0. 加载已有数据（断点续传）
        existing_images, processed_reports = self.load_existing_images()
        self.all_images = existing_images.copy() if existing_images else []
        
        # 1. 从CSV文件读取报告数据（优先使用完整数据文件）
        data_file = None
        if os.path.exists('ufo_data_tiered_full.csv'):
            data_file = 'ufo_data_tiered_full.csv'
            print("\n正在读取 ufo_data_tiered_full.csv（完整数据文件）...")
        elif os.path.exists('ufo_data_tiered.csv'):
            data_file = 'ufo_data_tiered.csv'
            print("\n正在读取 ufo_data_tiered.csv...")
        else:
            print("❌ 未找到数据文件（ufo_data_tiered_full.csv 或 ufo_data_tiered.csv）")
            return
        
        try:
            all_reports_df = pd.read_csv(data_file)
            print(f"✅ 成功读取 {len(all_reports_df)} 条报告数据")
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
            return
        
        # 2. 筛选有Report_Link的记录，且Media = "Y"（只处理有媒体文件的报告）
        reports_with_links = all_reports_df[
            all_reports_df['Report_Link'].notna() & 
            (all_reports_df['Report_Link'] != '') & 
            (all_reports_df['Media'] == 'Y')
        ].copy()
        print(f"\n找到 {len(reports_with_links)} 条有链接且有媒体的报告（Media=Y）")
        print(f"其中 Tier 1/2: {reports_with_links['Is_High_Tier'].sum()} 条")
        print(f"普通报告: {(reports_with_links['Is_High_Tier'] == False).sum()} 条")
        
        # 过滤掉已处理的报告
        reports_to_process = reports_with_links[~reports_with_links['Report_Link'].isin(processed_reports)]
        skipped_count = len(reports_with_links) - len(reports_to_process)
        print(f"✅ 已处理报告: {skipped_count} 个（将跳过）")
        print(f"📋 待处理报告: {len(reports_to_process)} 个\n")
        
        if len(reports_to_process) == 0:
            print("所有报告已处理完成！")
            return
        
        # 3. 遍历待处理的报告，提取图片（无时间限制，完整抓取）
        print("开始抓取图片...")
        print("⚠️ 完整模式：将遍历所有待处理报告（可能需要数小时）")
        print("建议：如果需要中断，按 Ctrl+C 保存已抓取的数据\n")
        
        processed_count = 0
        error_count = 0
        
        for idx, row in tqdm(reports_to_process.iterrows(), total=len(reports_to_process), desc="抓取报告", unit="个"):
            report_url = row['Report_Link']
            is_high_tier = bool(row.get('Is_High_Tier', False))
            
            try:
                # 访问详情页提取图片
                image_data = self.extract_image_from_detail_page(report_url)
                
                if image_data and image_data['images']:
                    # 为每张图片创建一条记录
                    for img_url in image_data['images']:
                        # 检查是否已存在（避免重复）
                        if not any(existing['Image_URL'] == img_url for existing in self.all_images):
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
                    processed_count += 1
                else:
                    error_count += 1
                    
            except KeyboardInterrupt:
                print("\n\n⚠️ 用户中断，正在保存已抓取的数据...")
                break
            except Exception as e:
                error_count += 1
                continue
            
            # 每次请求后休息0.5秒（防止被封IP）
            time.sleep(0.5)
        
        # 4. 保存数据（合并新旧数据）
        if not self.all_images:
            print("\n未获取到任何图片数据")
            return
        
        print("\n正在保存数据...")
        df = pd.DataFrame(self.all_images)
        
        # 去重（如果有重复的图片URL）
        df = df.drop_duplicates(subset=['Image_URL'], keep='first')
        
        # 确保列的顺序
        columns_order = ['Image_URL', 'Report_URL', 'Date', 'City', 'State', 'Shape', 'Summary', 'Description', 'Is_High_Tier', 'Tier']
        df = df[columns_order]
        
        # 保存数据
        output_file = 'ufo_images.csv'
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        # 输出统计
        new_images_count = len(self.all_images) - len(existing_images) if existing_images else len(self.all_images)
        print("\n" + "=" * 60)
        print("✅ 抓取完成！")
        print(f"📊 本次新增图片: {new_images_count} 张")
        print(f"📊 累计总图片数: {len(df)} 张")
        print(f"⭐ Tier 1/2 图片: {df['Is_High_Tier'].sum()} 张 ({df['Is_High_Tier'].sum()/len(df)*100:.2f}%)")
        print(f"📸 普通图片: {(df['Is_High_Tier'] == False).sum()} 张 ({(df['Is_High_Tier'] == False).sum()/len(df)*100:.2f}%)")
        print(f"✅ 本次成功处理报告: {processed_count} 个")
        print(f"❌ 本次失败/无图片报告: {error_count} 个")
        print(f"📋 剩余待处理报告: {len(reports_with_links) - len(processed_reports) - processed_count} 个")
        print(f"💾 文件已保存至 {output_file}")
        print("=" * 60)


def main():
    scraper = UFOImageScraper()
    scraper.scrape_all_images()


if __name__ == "__main__":
    main()
