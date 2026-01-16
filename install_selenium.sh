#!/bin/bash
echo "正在安装Selenium..."
pip3 install selenium --user

echo ""
echo "检查ChromeDriver..."
if command -v chromedriver &> /dev/null; then
    echo "✅ ChromeDriver已安装"
    chromedriver --version
else
    echo "⚠️ ChromeDriver未安装"
    echo ""
    echo "请选择安装方式："
    echo "1. 使用Homebrew安装（推荐）: brew install chromedriver"
    echo "2. 手动下载: https://chromedriver.chromium.org/downloads"
    echo "3. 或运行脚本时会自动尝试下载"
fi
