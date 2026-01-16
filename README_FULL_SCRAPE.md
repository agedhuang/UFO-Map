# 获取全部15万条NUFORC数据的说明

## 方案选择

由于NUFORC网站使用DataTables服务器端分页，需要模拟浏览器才能获取完整数据。

## 方案1: 使用Selenium（推荐）

### 安装步骤

1. **安装Selenium**
   ```bash
   pip3 install selenium
   ```

2. **安装ChromeDriver**
   - 确保已安装Chrome浏览器
   - 下载ChromeDriver：https://chromedriver.chromium.org/downloads
   - 确保ChromeDriver在系统PATH中，或将其放在项目目录

   **macOS快速安装（使用Homebrew）：**
   ```bash
   brew install chromedriver
   ```

3. **运行脚本**
   ```bash
   python3 scrape_all_paginated.py
   ```

### 脚本说明

- 脚本会打开Chrome浏览器（如果headless=False）
- 自动访问 `https://nuforc.org/subndx/?id=all`
- 自动检测总页数（1586页）
- 逐页获取数据并解析
- 每10页保存一次中间结果（防止数据丢失）
- 最终输出：`ufo_data_tiered_full.csv`

### 注意事项

- 完整爬取需要数小时（1586页 × 每页加载时间）
- 建议使用稳定的网络连接
- 可以随时按Ctrl+C中断，已获取的数据会保存
- 如果中断，可以修改脚本从上次中断的页码继续

## 方案2: API方式（已测试失败，不推荐）

```bash
python3 scrape_all_via_api.py
```

此方法已测试失败，API需要特殊认证。

## 输出文件

- `ufo_data_tiered_full.csv` - 完整的15万条记录（包含Tier信息）
- `ufo_data_tiered_partial.csv` - 中间保存的临时文件

## 获取数据后的下一步

获取完整数据后，可以运行 `scrape_images_full.py` 来抓取图片：

```bash
python3 scrape_images_full.py
```

脚本会自动读取 `ufo_data_tiered_full.csv`，筛选Media=Y的记录，然后访问每个报告的详情页抓取图片。
