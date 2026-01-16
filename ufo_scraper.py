"""
NUFORC UFO 报告爬虫
爬取最近6个月的UFO目击报告数据
"""

import requests
from bs4 import BeautifulSoup
import time
import csv
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
from datetime import datetime, timedelta
import re


class UFOScraper:
    def __init__(self):
        self.base_url = "https://nuforc.org"
        self.index_url = "https://nuforc.org/ndx/?id=event"  # 实际重定向后的URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive'
        })
        self.data = []
        
    def get_month_links(self, months=6):
        """
        获取最近N个月的月份链接
        """
        try:
            print(f"正在获取最近 {months} 个月的索引...")
            # 先访问主页，建立会话
            time.sleep(0.5)
            response = self.session.get(self.index_url, timeout=15, allow_redirects=True)
            
            if response.status_code == 403:
                print("遇到403错误，尝试使用不同的请求方式...")
                # 尝试直接访问，不使用session
                response = requests.get(self.index_url, headers=self.session.headers, timeout=15)
            
            response.raise_for_status()
            
            # 尝试不同的编码
            try:
                response.encoding = 'utf-8'
                html_content = response.text
            except:
                html_content = response.content.decode('utf-8', errors='ignore')
            
            print(f"HTML内容长度: {len(html_content)}")
            
            # 使用正则表达式直接提取链接（因为BeautifulSoup可能无法正确解析某些HTML）
            month_links = []
            # 匹配格式：HREF=/subndx/?id=e202512 或 href="/subndx/?id=e202512"
            pattern = r'href=["\']?([^"\'>\s]*/subndx/\?id=e\d+)["\']?'
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            
            print(f"使用正则表达式找到 {len(matches)} 个月份链接")
            
            for href in matches:
                # 确保href是完整路径
                if not href.startswith('http'):
                    full_url = urljoin(self.base_url, href)
                else:
                    full_url = href
                month_links.append(full_url)
            
            # 排序并取最近N个月（链接已经按时间倒序排列）
            month_links = list(set(month_links))  # 去重
            month_links.sort(reverse=True)
            month_links = month_links[:months]
            
            print(f"找到 {len(month_links)} 个月份链接")
            if month_links:
                print("示例链接:", month_links[0] if month_links else "无")
            return month_links
            
        except Exception as e:
            print(f"获取月份链接失败: {e}")
            print(f"响应状态码: {response.status_code if 'response' in locals() else 'N/A'}")
            if 'response' in locals():
                print(f"响应内容前500字符: {response.text[:500] if hasattr(response, 'text') else response.content[:500]}")
            return []
    
    def get_report_links_from_month(self, month_url):
        """
        从月份页面获取所有报告链接
        """
        try:
            time.sleep(0.3)  # 请求前稍作休息
            response = self.session.get(month_url, timeout=10)
            response.raise_for_status()
            
            try:
                response.encoding = 'utf-8'
                html_content = response.text
            except:
                html_content = response.content.decode('utf-8', errors='ignore')
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            report_links = []
            # 查找所有报告详情链接：/sighting/?id=194496
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                if '/sighting/?id=' in href:
                    full_url = urljoin(self.base_url, href)
                    report_links.append(full_url)
            
            return report_links
            
        except Exception as e:
            print(f"获取报告链接失败 ({month_url}): {e}")
            return []
    
    def extract_image_url(self, soup, base_url):
        """
        提取页面中的图片URL，如果是相对路径则补全为绝对路径
        """
        img_tag = soup.find('img', src=True)
        if img_tag:
            img_src = img_tag.get('src', '')
            if img_src:
                # 如果是相对路径，补全为绝对路径
                if not img_src.startswith('http'):
                    img_src = urljoin(base_url, img_src)
                return img_src
        return ""
    
    def extract_field_value(self, text_content, field_name):
        """
        从文本内容中提取特定字段的值
        格式: "Field Name: value"
        """
        # 使用正则表达式匹配 "Field Name: value" 格式
        pattern = rf'{field_name}:\s*([^\n]+)'
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def extract_description(self, text_content):
        """
        提取完整的描述文本
        描述通常在 "Witnessed" 或长文本段落中
        """
        # 移除script和style标签后的文本
        description = ""
        
        # 查找 "Witnessed" 字段后的文本
        witnessed_match = re.search(r'Witnessed[:\s]+(.+?)(?=Posted|$)', text_content, re.IGNORECASE | re.DOTALL)
        if witnessed_match:
            description = witnessed_match.group(1).strip()
        else:
            # 如果没有找到Witnessed，尝试提取最长的文本段落
            # 找到所有长句子（超过50字符）
            sentences = re.findall(r'[^.!?]{50,}', text_content)
            if sentences:
                # 过滤掉导航和版权信息
                filtered = [s.strip() for s in sentences 
                           if 'copyright' not in s.lower() 
                           and 'terms of service' not in s.lower()
                           and 'privacy policy' not in s.lower()
                           and len(s.strip()) > 50]
                if filtered:
                    description = '. '.join(filtered[:3])  # 取前3个长段落
        
        return description.strip()
    
    def scrape_report_detail(self, report_url):
        """
        爬取单个报告的详情页
        """
        try:
            response = self.session.get(report_url, timeout=10)
            response.raise_for_status()
            
            try:
                response.encoding = 'utf-8'
                html_content = response.text
            except:
                html_content = response.content.decode('utf-8', errors='ignore')
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 获取页面文本内容
            body = soup.find('body')
            if body:
                # 移除script和style标签
                for script in body(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                text_content = body.get_text(separator=' ', strip=True)
            else:
                text_content = soup.get_text(separator=' ', strip=True)
            
            # 提取各个字段
            date = self.extract_field_value(text_content, "Occurred")
            if not date:
                date = self.extract_field_value(text_content, "Date")
            
            # 提取Location字段，然后分离City和State
            location = self.extract_field_value(text_content, "Location")
            city = ""
            state = ""
            if location:
                # 格式通常是 "City, State, USA" 或 "City, State"
                parts = [p.strip() for p in location.split(',')]
                if len(parts) >= 2:
                    city = parts[0]
                    state = parts[1].replace('USA', '').strip()
                elif len(parts) == 1:
                    city = parts[0]
            
            shape = self.extract_field_value(text_content, "Shape")
            summary = self.extract_field_value(text_content, "Summary")
            if not summary:
                # 尝试从Witnessed字段提取摘要
                witnessed = self.extract_field_value(text_content, "Witnessed")
                if witnessed:
                    summary = witnessed[:200]  # 取前200字符作为摘要
            
            tier = self.extract_field_value(text_content, "Tier")
            
            # 提取图片URL
            image_url = self.extract_image_url(soup, report_url)
            
            # 提取完整描述
            description = self.extract_description(text_content)
            
            # 如果description为空，尝试用summary填充
            if not description and summary:
                description = summary
            
            return {
                'Date': date,
                'City': city,
                'State': state,
                'Shape': shape,
                'Summary': summary,
                'Tier': tier,
                'Image_URL': image_url,
                'Description': description,
                'Report_URL': report_url
            }
            
        except Exception as e:
            print(f"\n爬取报告失败 ({report_url}): {e}")
            return None
    
    def scrape_all(self, months=6):
        """
        主爬取函数
        """
        print("=" * 60)
        print("NUFORC UFO 报告爬虫启动")
        print("=" * 60)
        
        # 1. 获取月份链接
        month_links = self.get_month_links(months)
        if not month_links:
            print("未找到月份链接，程序退出")
            return
        
        # 2. 收集所有报告链接
        print("\n正在收集所有报告链接...")
        all_report_links = []
        for month_url in tqdm(month_links, desc="收集月份链接", unit="个月"):
            report_links = self.get_report_links_from_month(month_url)
            all_report_links.extend(report_links)
            time.sleep(0.3)  # 月份页面之间也稍作休息
        
        print(f"\n总共找到 {len(all_report_links)} 个报告链接")
        
        if not all_report_links:
            print("未找到报告链接，程序退出")
            return
        
        # 3. 爬取所有报告详情
        print("\n开始爬取报告详情...")
        pbar = tqdm(all_report_links, desc="爬取报告", unit="条")
        for report_url in pbar:
            report_data = self.scrape_report_detail(report_url)
            if report_data:
                self.data.append(report_data)
                
                # 每抓取10条数据，打印一条日志
                if len(self.data) % 10 == 0:
                    city = report_data.get('City', 'N/A')
                    date = report_data.get('Date', 'N/A')
                    # 使用 tqdm.write() 避免干扰进度条显示
                    tqdm.write(f"[进度日志] 已抓取 {len(self.data)} 条数据 | 当前: {city}, {date}")
            
            # 每次请求后休息0.5秒
            time.sleep(0.5)
        
        # 4. 保存数据
        self.save_to_csv()
        
        print("\n" + "=" * 60)
        print(f"爬取完成！共获取 {len(self.data)} 条数据")
        print("=" * 60)
    
    def save_to_csv(self, filename='ufo_raw_data.csv'):
        """
        保存数据到CSV文件
        """
        if not self.data:
            print("没有数据可保存")
            return
        
        fieldnames = ['Date', 'City', 'State', 'Shape', 'Summary', 'Tier', 
                     'Image_URL', 'Description', 'Report_URL']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.data)
        
        print(f"\n数据已保存到: {filename}")


def main():
    scraper = UFOScraper()
    scraper.scrape_all(months=6)


if __name__ == "__main__":
    main()

