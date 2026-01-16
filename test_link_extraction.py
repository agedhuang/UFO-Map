"""
测试脚本：验证Report_Link提取逻辑
"""
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False

def is_yellow_background(element):
    """检测元素是否有黄色背景"""
    if not element:
        return False
    
    style = element.get('style', '')
    bgcolor = element.get('bgcolor', '')
    all_color_info = (style + ' ' + bgcolor).lower()
    
    yellow_keywords = ['yellow', '#ffff00', '#ffffc0', '#ffffcc', '#ffff99']
    for keyword in yellow_keywords:
        if keyword in all_color_info:
            return True
    return False

def test_link_extraction():
    """测试链接提取逻辑"""
    print('=' * 60)
    print('测试Report_Link提取逻辑')
    print('=' * 60)
    
    # 初始化浏览器
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    
    try:
        if WEBDRIVER_MANAGER_AVAILABLE:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)
        
        print('\n1. 正在访问页面...')
        driver.get('https://nuforc.org/subndx/?id=all')
        time.sleep(10)
        
        print('\n2. 解析第一页数据...')
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        
        if not table:
            print('❌ 未找到表格')
            return
        
        rows = table.find_all('tr')
        if len(rows) < 2:
            print('❌ 表格数据不足')
            return
        
        # 解析前5行数据
        print('\n3. 测试链接提取（前5行数据）:')
        success_count = 0
        total_count = min(5, len(rows) - 1)
        
        for i in range(1, total_count + 1):
            row = rows[i]
            cells = row.find_all('td')
            
            # 使用修复后的逻辑：遍历所有单元格查找链接
            report_link = ''
            for cell in cells:
                link_tag = cell.find('a', href=True)
                if link_tag:
                    href = link_tag.get('href', '')
                    if '/sighting/?id=' in href:
                        report_link = urljoin('https://nuforc.org', href)
                        break
            
            if report_link:
                success_count += 1
                print(f'   行{i}: ✅ 成功提取链接: {report_link[:60]}...')
            else:
                print(f'   行{i}: ❌ 未找到链接')
                # 调试：显示所有单元格的内容
                for idx, cell in enumerate(cells):
                    text = cell.get_text(strip=True)[:30]
                    links = cell.find_all('a', href=True)
                    print(f'      列{idx}: "{text}" (链接数: {len(links)})')
        
        print(f'\n✅ 测试完成: {success_count}/{total_count} 行成功提取链接')
        
        if success_count == total_count:
            print('🎉 链接提取逻辑正常！可以运行完整爬取')
        else:
            print('⚠️ 部分行未能提取链接，需要进一步调试')
        
        driver.quit()
        
    except Exception as e:
        print(f'\n❌ 测试失败: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_link_extraction()
