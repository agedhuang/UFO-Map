"""
NUFORC UFO 完整数据爬虫（使用Selenium处理分页）
从 subndx/?id=all 页面获取所有1586页，约158574条记录
"""
import time
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urljoin
import re
from tqdm import tqdm

# 添加webdriver-manager支持
try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False
    print("⚠️ webdriver-manager未安装，请运行: pip3 install webdriver-manager")


class UFOPaginatedScraper:
    def __init__(self, headless=True):
        self.base_url = "https://nuforc.org"
        self.all_page_url = "https://nuforc.org/subndx/?id=all"
        self.headless = headless
        self.driver = None
        self.all_data = []
        
    def setup_driver(self):
        """设置Selenium WebDriver（使用webdriver-manager自动管理）"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            if WEBDRIVER_MANAGER_AVAILABLE:
                # 使用webdriver-manager自动下载和管理ChromeDriver
                print("正在使用webdriver-manager自动下载ChromeDriver...")
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                print("✅ WebDriver初始化成功")
            else:
                # 回退到系统PATH中的chromedriver
                self.driver = webdriver.Chrome(options=chrome_options)
            return True
        except Exception as e:
            print(f"❌ Chrome driver初始化失败: {e}")
            if not WEBDRIVER_MANAGER_AVAILABLE:
                print("\n💡 提示：请运行: pip3 install webdriver-manager")
            return False
    
    def is_yellow_background(self, element):
        """检测元素是否有黄色或淡黄色背景"""
        if not element:
            return False
        
        style = element.get('style', '')
        bgcolor = element.get('bgcolor', '')
        all_color_info = (style + ' ' + bgcolor).lower()
        
        yellow_keywords = [
            'yellow', '#ffff00', '#ffffc0', '#ffffcc', '#ffff99',
            '#ffffe0', '#ffffd0', '#ffffb0', '#fffacd', '#fff8dc',
            '#ffeb3b', '#ffc107', 'rgb(255, 255, 0)', 'rgb(255, 255, 192)',
            'rgb(255, 255, 204)', 'rgb(255, 255, 176)', 'rgb(255, 255, 224)',
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
    
    def parse_table_page(self):
        """解析当前页面的表格数据"""
        try:
            # 等待表格加载
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            
            # 获取页面HTML
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return []
            
            rows = table.find_all('tr')
            if len(rows) < 2:
                return []
            
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
            for row in rows[1:]:
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
                # 方法：遍历整行的所有单元格查找链接（不依赖特定列）
                report_link = ''
                is_high_tier = False
                link_cell = None
                
                # 遍历所有单元格查找包含链接的单元格
                for cell in cells:
                    link_tag = cell.find('a', href=True)
                    if link_tag:
                        href = link_tag.get('href', '')
                        if '/sighting/?id=' in href:
                            report_link = urljoin(self.base_url, href)
                            link_cell = cell
                            break
                
                # 如果找到了链接单元格，检测Tier
                if link_cell:
                    # 检查单元格背景色
                    if self.is_yellow_background(link_cell):
                        is_high_tier = True
                    
                    # 检查链接元素
                    link_tag = link_cell.find('a', href=True)
                    if link_tag:
                        link_text = link_tag.get_text(strip=True)
                        # 检查链接文本中的符号（Tier标记）
                        if '!' in link_text:
                            is_high_tier = True
                        elif link_text.endswith('.') or link_text == 'Open .' or 'Open .' in link_text:
                            is_high_tier = True
                        # 检查链接元素本身的背景色
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
            print(f"解析页面失败: {e}")
            return []
    
    def get_total_pages(self):
        """获取总页数"""
        try:
            # 等待分页信息加载
            wait = WebDriverWait(self.driver, 30)
            # 查找分页信息，通常在"Showing X to Y of Z entries"这样的文本中
            # 或者查找最后一页的页码
            time.sleep(5)  # 等待DataTables完全加载
            
            # 尝试通过JavaScript获取总页数
            try:
                # DataTables通常会在window上暴露表格对象
                total_pages = self.driver.execute_script("""
                    if (typeof jQuery !== 'undefined' && jQuery.fn.dataTable) {
                        var table = jQuery('#table_1').DataTable();
                        if (table) {
                            return table.page.info().pages;
                        }
                    }
                    return null;
                """)
                if total_pages:
                    return int(total_pages)
            except:
                pass
            
            # 备用方法：查找分页控件中的最后一页
            try:
                pagination_elements = self.driver.find_elements(By.CSS_SELECTOR, ".dataTables_paginate a")
                page_numbers = []
                for elem in pagination_elements:
                    text = elem.text.strip()
                    if text.isdigit():
                        page_numbers.append(int(text))
                if page_numbers:
                    return max(page_numbers)
            except:
                pass
            
            # 如果都失败，使用默认值1586
            print("⚠️ 无法自动检测总页数，使用默认值1586")
            return 1586
            
        except Exception as e:
            print(f"获取总页数失败: {e}，使用默认值1586")
            return 1586
    
    def go_to_page(self, page_num):
        """跳转到指定页面"""
        try:
            wait = WebDriverWait(self.driver, 30)
            
            # 方法1: 使用DataTables API跳转
            try:
                self.driver.execute_script(f"""
                    if (typeof jQuery !== 'undefined' && jQuery.fn.dataTable) {{
                        var table = jQuery('#table_1').DataTable();
                        if (table) {{
                            table.page({page_num - 1}).draw('page');
                            return true;
                        }}
                    }}
                    return false;
                """)
                time.sleep(2)  # 等待页面加载
                return True
            except:
                pass
            
            # 方法2: 点击分页按钮
            try:
                # 查找包含目标页码的链接
                page_link = self.driver.find_element(By.XPATH, f"//a[contains(@class, 'paginate_button') and text()='{page_num}']")
                self.driver.execute_script("arguments[0].click();", page_link)
                time.sleep(2)
                return True
            except:
                pass
            
            # 方法3: 使用"下一页"按钮逐步翻页
            # 这里需要知道当前页码，然后点击多次"下一页"
            return False
            
        except Exception as e:
            print(f"跳转到第{page_num}页失败: {e}")
            return False
    
    def scrape_all(self):
        """主爬取函数"""
        print("=" * 60)
        print("NUFORC UFO 完整数据爬虫启动（使用Selenium）")
        print("目标：获取所有1586页，约158574条记录")
        print("=" * 60)
        
        # 1. 初始化浏览器
        if not self.setup_driver():
            return
        
        try:
            # 2. 访问目标页面
            print(f"\n正在访问: {self.all_page_url}")
            self.driver.get(self.all_page_url)
            
            # 等待页面加载
            print("等待页面加载...")
            time.sleep(10)  # 给DataTables足够时间加载
            
            # 3. 获取总页数
            total_pages = self.get_total_pages()
            print(f"\n✅ 检测到总页数: {total_pages}")
            
            # 4. 遍历所有页面
            print(f"\n开始抓取数据...")
            for page_num in tqdm(range(1, total_pages + 1), desc="抓取页面", unit="页"):
                # 跳转到目标页面
                if page_num > 1:
                    if not self.go_to_page(page_num):
                        print(f"⚠️ 无法跳转到第{page_num}页，跳过")
                        continue
                
                # 解析当前页面
                page_data = self.parse_table_page()
                self.all_data.extend(page_data)
                
                # 每10页保存一次（防止数据丢失）
                if page_num % 10 == 0:
                    self.save_partial_data()
                    print(f"\n[进度] 已处理 {page_num}/{total_pages} 页，已获取 {len(self.all_data)} 条记录")
            
            # 5. 保存最终数据
            self.save_final_data()
            
            print("\n" + "=" * 60)
            print("✅ 抓取完成！")
            print(f"📊 总共获取了 {len(self.all_data)} 条记录")
            print(f"💾 文件已保存至 ufo_data_tiered_full.csv")
            print("=" * 60)
            
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断，正在保存已抓取的数据...")
            self.save_final_data()
        except Exception as e:
            print(f"\n❌ 抓取过程出错: {e}")
            self.save_final_data()
        finally:
            if self.driver:
                self.driver.quit()
    
    def save_partial_data(self):
        """保存部分数据（中间保存）"""
        if not self.all_data:
            return
        df = pd.DataFrame(self.all_data)
        df.to_csv('ufo_data_tiered_partial.csv', index=False, encoding='utf-8')
    
    def save_final_data(self):
        """保存最终数据"""
        if not self.all_data:
            print("未获取到任何数据")
            return
        
        df = pd.DataFrame(self.all_data)
        
        # 去重：如果Report_Link有空值，使用Date+City+State组合去重
        if df['Report_Link'].isna().all():
            # 所有Report_Link都是空的，使用其他字段组合去重
            df = df.drop_duplicates(subset=['Date', 'City', 'State', 'Shape'], keep='first')
        else:
            # 使用Report_Link去重
            df = df.drop_duplicates(subset=['Report_Link'], keep='first')
        
        # 保存
        output_file = 'ufo_data_tiered_full.csv'
        df.to_csv(output_file, index=False, encoding='utf-8')
        
        print(f"\n✅ 数据已保存至 {output_file}")
        print(f"📊 总记录数: {len(df)}")
        print(f"⭐ Tier 1/2: {df['Is_High_Tier'].sum()} 条")


def main():
    scraper = UFOPaginatedScraper(headless=False)  # 设置为False可以看到浏览器操作过程
    scraper.scrape_all()


if __name__ == "__main__":
    main()
