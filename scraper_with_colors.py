"""
NUFORC UFO 报告爬虫（带Tier检测版本）
检测表格中黄色背景的单元格来判断Tier 1/2案件
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin
from tqdm import tqdm


class UFOTierScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.index_url = "https://nuforc.org/webreports/ndxevent.html"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.all_data = []
        
    def get_month_links(self):
        """
        获取所有月份链接，按时间倒序排列
        """
        try:
            print("正在获取月份索引...")
            response = self.session.get(self.index_url, timeout=10)
            response.raise_for_status()
            
            # 使用正则表达式提取月份链接
            pattern = r'href=["\']?([^"\'>\s]*/subndx/\?id=e\d+)["\']?'
            matches = re.findall(pattern, response.text, re.IGNORECASE)
            
            month_links = []
            for href in matches:
                if not href.startswith('http'):
                    full_url = urljoin(self.base_url, href)
                else:
                    full_url = href
                month_links.append(full_url)
            
            # 去重并排序（倒序，最新的在前）
            month_links = list(set(month_links))
            month_links.sort(reverse=True)
            
            print(f"找到 {len(month_links)} 个月份链接")
            return month_links
            
        except Exception as e:
            print(f"获取月份链接失败: {e}")
            return []
    
    def is_yellow_background(self, element):
        """
        检测元素是否有黄色或淡黄色背景
        检查style属性和bgcolor属性
        """
        if not element:
            return False
        
        # 获取style属性
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
    
    def scrape_month_table(self, month_url):
        """
        使用BeautifulSoup解析表格，检测黄色背景
        """
        try:
            response = self.session.get(month_url, timeout=10)
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
                elif 'link' in text:
                    column_indices['link'] = idx
            
            # 解析数据行
            month_data = []
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
                
                # 提取Report链接（通常在第一个单元格）
                report_link = ''
                link_cell_idx = column_indices.get('link', 0)
                if link_cell_idx < len(cells):
                    link_cell = cells[link_cell_idx]
                    link_tag = link_cell.find('a', href=True)
                    if link_tag:
                        href = link_tag.get('href', '')
                        if '/sighting/?id=' in href:
                            report_link = urljoin(self.base_url, href)
                
                # 检测Tier：检查链接文本中的符号
                # Tier 1: "Open !" (有感叹号)
                # Tier 2: "Open ." (有点号)
                is_high_tier = False
                if link_cell_idx < len(cells):
                    link_cell = cells[link_cell_idx]
                    # 检查单元格本身是否有黄色背景
                    if self.is_yellow_background(link_cell):
                        is_high_tier = True
                    # 检查单元格内的链接
                    link_tag = link_cell.find('a')
                    if link_tag:
                        link_text = link_tag.get_text(strip=True)
                        # 检查链接文本中是否有感叹号（"Open !" 表示 Tier 1）
                        if '!' in link_text:
                            is_high_tier = True
                        # 检查链接文本中是否有点号（"Open ." 表示 Tier 2）
                        # 注意：点号可能在文本末尾，格式为 "Open ."
                        elif link_text.endswith('.') or link_text == 'Open .' or 'Open .' in link_text:
                            is_high_tier = True
                        # 检查链接元素是否有黄色背景（备用检测方法）
                        if self.is_yellow_background(link_tag):
                            is_high_tier = True
                
                month_data.append({
                    'Date': date,
                    'City': city,
                    'State': state,
                    'Shape': shape,
                    'Summary': summary,
                    'Media': media,
                    'Report_Link': report_link,
                    'Is_High_Tier': is_high_tier
                })
            
            return month_data
            
        except Exception as e:
            print(f"\n抓取失败 ({month_url}): {e}")
            return []
    
    def scrape_all(self):
        """
        主爬取函数
        """
        print("=" * 60)
        print("NUFORC UFO 报告爬虫（带Tier检测）启动")
        print("=" * 60)
        
        # 1. 获取所有月份链接
        month_links = self.get_month_links()
        if not month_links:
            print("未找到月份链接，程序退出")
            return
        
        # 2. 遍历所有月份，解析表格并检测Tier
        print("\n开始抓取数据...")
        for month_url in tqdm(month_links, desc="抓取月份", unit="个月"):
            month_data = self.scrape_month_table(month_url)
            self.all_data.extend(month_data)
            
            # 每次请求后休息0.5秒
            time.sleep(0.5)
        
        # 3. 转换为DataFrame并保存
        if not self.all_data:
            print("\n未获取到任何数据")
            return
        
        print("\n正在保存数据...")
        df = pd.DataFrame(self.all_data)
        
        # 确保列的顺序
        columns_order = ['Date', 'City', 'State', 'Shape', 'Summary', 'Media', 'Report_Link', 'Is_High_Tier']
        df = df[columns_order]
        
        # 保存数据
        output_file = 'ufo_data_tiered.csv'
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        # 输出统计
        print("\n" + "=" * 60)
        print("✅ 抓取完成！")
        print(f"📊 总共获取了 {len(df)} 条数据")
        print(f"⭐ Tier 1/2 案件: {df['Is_High_Tier'].sum()} 条 ({df['Is_High_Tier'].sum()/len(df)*100:.2f}%)")
        print(f"💾 文件已保存至 {output_file}")
        print("=" * 60)


def main():
    scraper = UFOTierScraper()
    scraper.scrape_all()


if __name__ == "__main__":
    main()

