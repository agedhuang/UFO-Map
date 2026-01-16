"""
NUFORC UFO 报告列表爬虫（极速版）
使用 pd.read_html() 快速获取所有历史数据概览
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from urllib.parse import urljoin
from tqdm import tqdm
from io import StringIO


class UFOListScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.index_url = "https://nuforc.org/webreports/ndxevent.html"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.all_dataframes = []
        
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
    
    def scrape_month_table(self, month_url):
        """
        使用 pd.read_html() 快速读取月份页面的表格
        """
        try:
            response = self.session.get(month_url, timeout=10)
            response.raise_for_status()
            
            # 提取表格HTML并清理
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return None
            
            # 移除style属性中的display:none，让pd.read_html能识别
            if 'style' in table.attrs:
                style = table.attrs['style']
                style = style.replace('display: none;', '').replace('display:none;', '')
                if style.strip():
                    table.attrs['style'] = style
                else:
                    del table.attrs['style']
            
            # 提取链接信息（如果需要Report_Link列）
            links_list = []
            rows = table.find_all('tr')
            for row in rows[1:]:  # 跳过表头
                link_tag = row.find('a', href=True)
                if link_tag:
                    href = link_tag.get('href', '')
                    if '/sighting/?id=' in href:
                        full_link = urljoin(self.base_url, href)
                        links_list.append(full_link)
                    else:
                        links_list.append('')
                else:
                    links_list.append('')
            
            # 使用StringIO包装HTML，让pd.read_html读取
            table_html = str(table)
            tables = pd.read_html(StringIO(table_html))
            
            if not tables:
                return None
            
            df = tables[0]
            
            # 添加Report_Link列
            if links_list and len(links_list) == len(df):
                df['Report_Link'] = links_list
            else:
                df['Report_Link'] = ''
            
            return df
            
        except Exception as e:
            print(f"\n抓取失败 ({month_url}): {e}")
            return None
    
    def scrape_all(self):
        """
        主爬取函数
        """
        print("=" * 60)
        print("NUFORC UFO 报告列表爬虫（极速版）启动")
        print("=" * 60)
        
        # 1. 获取所有月份链接
        month_links = self.get_month_links()
        if not month_links:
            print("未找到月份链接，程序退出")
            return
        
        # 2. 遍历所有月份，使用pd.read_html快速读取表格
        print("\n开始抓取数据...")
        for month_url in tqdm(month_links, desc="抓取月份", unit="个月"):
            df = self.scrape_month_table(month_url)
            if df is not None and not df.empty:
                self.all_dataframes.append(df)
            
            # 每次请求后休息0.5秒
            time.sleep(0.5)
        
        # 3. 合并所有数据
        if not self.all_dataframes:
            print("\n未获取到任何数据")
            return
        
        print("\n正在合并数据...")
        combined_df = pd.concat(self.all_dataframes, ignore_index=True)
        
        # 4. 数据清洗：统一列名
        combined_df = self.clean_columns(combined_df)
        
        # 5. 保存数据
        output_file = 'ufo_list_full.csv'
        combined_df.to_csv(output_file, index=False, encoding='utf-8')
        
        # 6. 打印结果
        print("\n" + "=" * 60)
        print("✅ 抓取完成！")
        print(f"📊 总共获取了 {len(combined_df)} 条数据")
        print(f"💾 文件已保存至 {output_file}")
        print("=" * 60)
    
    def clean_columns(self, df):
        """
        数据清洗：统一列名为指定格式
        目标列名：Date, City, State, Shape, Duration, Summary, Posted
        """
        # 创建列名映射字典（不区分大小写）
        column_mapping = {}
        
        for col in df.columns:
            col_lower = str(col).strip().lower()
            
            # 映射到目标列名
            if 'occurred' in col_lower or ('date' in col_lower and 'reported' not in col_lower):
                column_mapping[col] = 'Date'
            elif 'city' in col_lower:
                column_mapping[col] = 'City'
            elif 'state' in col_lower:
                column_mapping[col] = 'State'
            elif 'shape' in col_lower:
                column_mapping[col] = 'Shape'
            elif 'duration' in col_lower:
                column_mapping[col] = 'Duration'
            elif 'summary' in col_lower:
                column_mapping[col] = 'Summary'
            elif 'posted' in col_lower:
                column_mapping[col] = 'Posted'
            elif 'reported' in col_lower and 'posted' not in col_lower:
                # 如果没有Posted列，使用Reported列
                column_mapping[col] = 'Posted'
        
        # 重命名列
        df = df.rename(columns=column_mapping)
        
        # 确保目标列存在（如果不存在则创建空列）
        target_columns = ['Date', 'City', 'State', 'Shape', 'Duration', 'Summary', 'Posted']
        for col in target_columns:
            if col not in df.columns:
                df[col] = ''
        
        # 重新排列列的顺序：目标列在前，然后是Report_Link，最后是其他列
        other_columns = [col for col in df.columns if col not in target_columns and col != 'Report_Link']
        final_columns = target_columns + ['Report_Link'] + other_columns
        final_columns = [col for col in final_columns if col in df.columns]
        df = df[final_columns]
        
        return df


def main():
    scraper = UFOListScraper()
    scraper.scrape_all()


if __name__ == "__main__":
    main()

