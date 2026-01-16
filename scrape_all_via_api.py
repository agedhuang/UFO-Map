"""
NUFORC UFO 完整数据爬虫（通过DataTables API获取所有1586页）
直接调用DataTables的服务器端API，获取所有约158574条记录
"""
import requests
import pandas as pd
import time
import json
import urllib3
from tqdm import tqdm
from urllib.parse import urljoin
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UFOAPIScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.all_page_url = "https://nuforc.org/subndx/?id=all"
        self.api_url = "https://nuforc.org/wp-admin/admin-ajax.php"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://nuforc.org',
            'Referer': 'https://nuforc.org/subndx/?id=all'
        })
        self.all_data = []
        
    def get_session_cookies(self):
        """先访问主页获取必要的cookies和session信息"""
        try:
            print("正在获取session信息...")
            response = self.session.get(self.all_page_url, timeout=30, verify=False)
            response.raise_for_status()
            
            # 从HTML中提取可能的token或nonce
            if 'wpDataTables' in response.text:
                print("✅ Session初始化成功")
                return True
            return False
        except Exception as e:
            print(f"⚠️ Session初始化失败: {e}")
            return False
    
    def is_yellow_background(self, element_style):
        """检测样式字符串是否包含黄色背景"""
        if not element_style:
            return False
        
        style = element_style.lower()
        yellow_keywords = [
            'yellow', '#ffff00', '#ffffc0', '#ffffcc', '#ffff99',
            '#ffffe0', '#ffffd0', '#ffffb0', '#fffacd', '#fff8dc',
            '#ffeb3b', '#ffc107', 'rgb(255, 255, 0)', 'rgb(255, 255, 192)',
            'rgb(255, 255, 204)', 'rgb(255, 255, 176)', 'rgb(255, 255, 224)',
        ]
        
        for keyword in yellow_keywords:
            if keyword in style:
                return True
        
        rgb_match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', style)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            if r > 200 and g > 200 and b < 200:
                return True
        
        return False
    
    def fetch_page(self, start=0, length=100):
        """从API获取一页数据"""
        try:
            params = {
                'action': 'get_wdtable',
                'table_id': '1',
                'wdt_var1': 'Post',
                'wdt_var2': '-1'
            }
            
            data = {
                'draw': '1',
                'start': str(start),
                'length': str(length),
                'order[0][column]': '1',
                'order[0][dir]': 'desc',
                'search[value]': '',
                'search[regex]': 'false'
            }
            
            response = self.session.post(
                self.api_url,
                params=params,
                data=data,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    return result
                except json.JSONDecodeError:
                    # 如果返回的是HTML错误页面
                    if len(response.text) < 500:
                        print(f"⚠️ API返回非JSON响应: {response.text[:200]}")
                    return None
            else:
                print(f"⚠️ API返回状态码: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"⚠️ 获取页面数据失败 (start={start}): {e}")
            return None
    
    def parse_api_data(self, api_result):
        """解析API返回的数据"""
        if not api_result or 'data' not in api_result:
            return []
        
        rows_data = api_result['data']
        parsed_data = []
        
        for row in rows_data:
            # DataTables API返回的数据通常是数组，需要根据列索引解析
            # 列顺序通常是: Date, City, State, Shape, Summary, Media, Link, ...
            if len(row) < 8:
                continue
            
            date = str(row[0]).strip() if row[0] else ''
            city = str(row[1]).strip() if row[1] else ''
            state = str(row[2]).strip() if row[2] else ''
            shape = str(row[5]).strip() if row[5] else ''
            summary = str(row[6]).strip() if row[6] else ''
            media = str(row[7]).strip() if row[7] else ''
            
            # 提取链接（通常在某个列中，可能是HTML格式）
            report_link = ''
            is_high_tier = False
            
            # 查找链接列（通常包含<a href="/sighting/?id=...">）
            for cell in row:
                if isinstance(cell, str) and '/sighting/?id=' in cell:
                    # 提取URL
                    link_match = re.search(r'href=["\']([^"\']*\/sighting\/\?id=\d+)["\']', cell)
                    if link_match:
                        report_link = urljoin(self.base_url, link_match.group(1))
                    
                    # 检查Tier标记
                    if '!' in cell:
                        is_high_tier = True
                    elif 'Open .' in cell or (cell.endswith('.') and 'Open' in cell):
                        is_high_tier = True
                    
                    # 检查黄色背景
                    if self.is_yellow_background(cell):
                        is_high_tier = True
                    break
            
            parsed_data.append({
                'Date': date,
                'City': city,
                'State': state,
                'Shape': shape,
                'Summary': summary,
                'Media': media,
                'Report_Link': report_link,
                'Is_High_Tier': is_high_tier
            })
        
        return parsed_data
    
    def scrape_all(self):
        """主爬取函数"""
        print("=" * 60)
        print("NUFORC UFO 完整数据爬虫启动（通过DataTables API）")
        print("目标：获取所有1586页，约158574条记录")
        print("=" * 60)
        
        # 1. 初始化session
        if not self.get_session_cookies():
            print("❌ Session初始化失败，程序退出")
            return
        
        # 2. 先获取第一页以确定总记录数
        print("\n正在获取第一页数据以确定总记录数...")
        first_page = self.fetch_page(0, 100)
        
        if not first_page:
            print("❌ 无法获取数据，API调用失败")
            print("💡 提示：可能需要使用Selenium方式（运行 scrape_all_paginated.py）")
            return
        
        total_records = first_page.get('recordsTotal', 158574)
        records_per_page = first_page.get('length', 100) if 'length' in first_page else 100
        total_pages = (total_records + records_per_page - 1) // records_per_page
        
        print(f"✅ 总记录数: {total_records}")
        print(f"✅ 每页记录数: {records_per_page}")
        print(f"✅ 总页数: {total_pages}")
        
        # 解析第一页数据
        first_page_data = self.parse_api_data(first_page)
        self.all_data.extend(first_page_data)
        print(f"✅ 第一页解析完成，获得 {len(first_page_data)} 条记录\n")
        
        # 3. 遍历剩余页面
        print("开始抓取剩余页面...")
        for page_num in tqdm(range(1, total_pages), desc="抓取页面", unit="页"):
            start = page_num * records_per_page
            page_result = self.fetch_page(start, records_per_page)
            
            if page_result:
                page_data = self.parse_api_data(page_result)
                self.all_data.extend(page_data)
            else:
                print(f"\n⚠️ 第{page_num + 1}页获取失败，跳过")
            
            # 每10页休息一下
            if (page_num + 1) % 10 == 0:
                time.sleep(0.5)
                # 每100页保存一次中间结果
                if (page_num + 1) % 100 == 0:
                    self.save_partial_data()
                    print(f"\n[进度] 已处理 {page_num + 1}/{total_pages} 页，已获取 {len(self.all_data)} 条记录")
        
        # 4. 保存最终数据
        self.save_final_data()
        
        print("\n" + "=" * 60)
        print("✅ 抓取完成！")
        print(f"📊 总共获取了 {len(self.all_data)} 条记录")
        print(f"💾 文件已保存至 ufo_data_tiered_full.csv")
        print("=" * 60)
    
    def save_partial_data(self):
        """保存部分数据（中间保存）"""
        if not self.all_data:
            return
        df = pd.DataFrame(self.all_data)
        df = df.drop_duplicates(subset=['Report_Link'], keep='first')
        df.to_csv('ufo_data_tiered_partial.csv', index=False, encoding='utf-8')
    
    def save_final_data(self):
        """保存最终数据"""
        if not self.all_data:
            print("未获取到任何数据")
            return
        
        df = pd.DataFrame(self.all_data)
        
        # 去重
        df = df.drop_duplicates(subset=['Report_Link'], keep='first')
        
        # 保存
        output_file = 'ufo_data_tiered_full.csv'
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"\n✅ 数据已保存至 {output_file}")
        print(f"📊 总记录数: {len(df)}")
        print(f"⭐ Tier 1/2: {df['Is_High_Tier'].sum()} 条")
        print(f"📸 Media=Y: {len(df[df['Media'] == 'Y'])} 条")


def main():
    scraper = UFOAPIScraper()
    scraper.scrape_all()


if __name__ == "__main__":
    main()
