"""
测试脚本：验证图片抓取和Tier检测功能
"""

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


class TestScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.all_url = "https://nuforc.org/subndx/?id=all"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def is_yellow_background(self, element):
        """检测元素是否有黄色或淡黄色背景"""
        if not element:
            return False
        
        style = element.get('style', '')
        bgcolor = element.get('bgcolor', '')
        all_color_info = (style + ' ' + bgcolor).lower()
        
        yellow_keywords = [
            'yellow', '#ffff00', '#ffffc0', '#ffffcc', '#ffff99', '#ffffe0',
            '#ffffd0', '#ffffb0', '#fffacd', '#fff8dc', '#ffeb3b', '#ffc107',
            'rgb(255, 255, 0)', 'rgb(255, 255, 192)', 'rgb(255, 255, 204)',
        ]
        
        for keyword in yellow_keywords:
            if keyword in all_color_info:
                return True
        
        rgb_match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', all_color_info)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            if r > 200 and g > 200 and b < 200:
                return True
        
        return False
    
    def test_table_scraping(self):
        """测试从all页面抓取表格并检测Tier"""
        print("=" * 60)
        print("测试1: 从all页面抓取表格并检测Tier")
        print("=" * 60)
        
        try:
            # 尝试先使用SSL验证
            try:
                response = self.session.get(self.all_url, timeout=30, verify=True)
            except Exception as e:
                # 如果SSL验证失败（可能是sandbox环境），尝试禁用SSL验证
                print("⚠️ SSL验证失败，使用不验证SSL模式...")
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = self.session.get(self.all_url, timeout=30, verify=False)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')
            
            if not table:
                print("❌ 未找到表格")
                return False
            
            rows = table.find_all('tr')
            if len(rows) < 2:
                print("❌ 表格数据为空")
                return False
            
            # 解析表头
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
                elif 'media' in text:
                    column_indices['media'] = idx
                elif 'link' in text:
                    column_indices['link'] = idx
            
            print(f"✅ 成功解析表头，找到列: {list(column_indices.keys())}")
            
            # 测试更多行数据（查找Media=Y和Tier记录）
            print("\n测试数据（查找Media=Y和Tier记录，最多检查200行）:")
            print("-" * 60)
            
            test_count = 0
            media_y_count = 0
            tier_detected_count = 0
            media_y_with_tier = 0
            
            for row_idx, row in enumerate(rows[1:201], 1):  # 检查前200行
                cells = row.find_all('td')
                if len(cells) < len(header_cells):
                    continue
                
                media = cells[column_indices.get('media', 8)].get_text(strip=True) if 'media' in column_indices else ''
                
                # 只关注Media=Y的记录
                if media == 'Y':
                    media_y_count += 1
                    date = cells[column_indices.get('date', 0)].get_text(strip=True) if 'date' in column_indices else ''
                    city = cells[column_indices.get('city', 1)].get_text(strip=True) if 'city' in column_indices else ''
                    state = cells[column_indices.get('state', 2)].get_text(strip=True) if 'state' in column_indices else ''
                    
                    # 检测Tier
                    link_cell_idx = column_indices.get('link', 0)
                    is_tier = False
                    report_link = ''
                    
                    if link_cell_idx < len(cells):
                        link_cell = cells[link_cell_idx]
                        # 检查单元格本身是否有黄色背景
                        is_tier = self.is_yellow_background(link_cell)
                        
                        link_tag = link_cell.find('a', href=True)
                        if link_tag:
                            href = link_tag.get('href', '')
                            if '/sighting/?id=' in href:
                                report_link = urljoin(self.base_url, href)
                            
                            # 检查链接文本中是否有感叹号（"Open !" 表示 Tier 1）
                            link_text = link_tag.get_text(strip=True)
                            if '!' in link_text:
                                is_tier = True
                            # 检查链接文本中是否有点号（"Open ." 表示 Tier 2）
                            elif link_text.endswith('.') or link_text == 'Open .' or 'Open .' in link_text:
                                is_tier = True
                            # 检查链接元素是否有黄色背景（备用检测方法）
                            if self.is_yellow_background(link_tag):
                                is_tier = True
                        
                        if is_tier:
                            tier_detected_count += 1
                    
                    tier_status = "✅ Tier 1/2" if is_tier else "普通"
                    print(f"  [{row_idx}] {date} | {city}, {state} | Media=Y | {tier_status}")
                    if report_link:
                        print(f"      链接: {report_link}")
                    if is_tier:
                        media_y_with_tier += 1
                    
                    test_count += 1
                    if test_count >= 10:  # 显示前10个Media=Y的记录
                        break
            
            print("-" * 60)
            print(f"✅ 在前200行中找到 {media_y_count} 条Media=Y的记录")
            print(f"✅ 其中 {media_y_with_tier} 条是Tier 1/2")
            print(f"✅ 总共检测到 {tier_detected_count} 条Tier 1/2记录（包括非Media=Y的）")
            
            return True
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return False
    
    def test_image_extraction(self, report_url):
        """测试从详情页提取图片"""
        print("\n" + "=" * 60)
        print(f"测试2: 从详情页提取图片 - {report_url}")
        print("=" * 60)
        
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
            
            print(f"找到 {len(img_tags)} 个img标签")
            
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
            
            print(f"\n✅ 提取到 {len(images)} 张图片:")
            for i, img_url in enumerate(images[:5], 1):  # 只显示前5张
                print(f"  [{i}] {img_url}")
            if len(images) > 5:
                print(f"  ... 还有 {len(images) - 5} 张图片")
            
            return len(images) > 0
            
        except Exception as e:
            print(f"❌ 提取图片失败: {e}")
            return False
    
    def run_tests(self):
        """运行所有测试"""
        print("\n开始测试...\n")
        
        # 测试1: 表格抓取和Tier检测
        table_ok = self.test_table_scraping()
        
        if not table_ok:
            print("\n❌ 表格抓取测试失败，无法继续")
            return
        
        # 测试2: 提取一个已知的报告图片（使用之前成功的报告）
        test_urls = [
            "https://nuforc.org/sighting/?id=194513",  # 之前成功过的
            "https://nuforc.org/sighting/?id=226",  # 从网页搜索看到的Media=Y的记录
        ]
        
        print("\n" + "=" * 60)
        print("测试多个报告的图片提取")
        print("=" * 60)
        
        for url in test_urls:
            self.test_image_extraction(url)
            print()
        
        print("=" * 60)
        print("测试完成！")
        print("=" * 60)


if __name__ == "__main__":
    tester = TestScraper()
    tester.run_tests()

