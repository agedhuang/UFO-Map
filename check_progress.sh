#!/bin/bash
# 进度检查脚本 - 每15分钟运行一次

cd "/Users/huangchenxu/Desktop/US School/Parsons CDMPS/Data Visualization/Final  Project UFO/Scrape"

python3 << 'EOF'
import pandas as pd
import os
from datetime import datetime

print('=' * 60)
print(f'📊 进度检查 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

try:
    if os.path.exists('ufo_data_tiered_partial.csv'):
        df = pd.read_csv('ufo_data_tiered_partial.csv')
        file_size = os.path.getsize('ufo_data_tiered_partial.csv') / (1024*1024)
        
        total_pages = 1586
        records_per_page = 100
        estimated_pages = len(df) / records_per_page
        progress = estimated_pages / total_pages * 100
        
        print(f'\n✅ 当前状态:')
        print(f'   总记录数: {len(df):,}')
        print(f'   文件大小: {file_size:.2f} MB')
        print(f'   有Report_Link: {df["Report_Link"].notna().sum():,} ({df["Report_Link"].notna().sum()/len(df)*100:.1f}%)')
        print(f'   Media=Y: {len(df[df["Media"] == "Y"])},')
        print(f'   Tier 1/2: {df["Is_High_Tier"].sum():,}')
        
        print(f'\n📈 进度:')
        print(f'   已完成: ~{estimated_pages:.0f} / {total_pages} 页')
        print(f'   完成度: {progress:.1f}%')
        print(f'   预计剩余: ~{total_pages - estimated_pages:.0f} 页')
        
        pages_remaining = total_pages - estimated_pages
        estimated_minutes = (pages_remaining * 3) / 60
        print(f'   预计剩余时间: ~{estimated_minutes:.0f} 分钟')
        
        if os.path.exists('ufo_data_tiered_full.csv'):
            df_final = pd.read_csv('ufo_data_tiered_full.csv')
            print(f'\n🎉 已完成！最终文件:')
            print(f'   总记录数: {len(df_final):,}')
            print(f'   有Report_Link: {df_final["Report_Link"].notna().sum():,}')
            print(f'   Media=Y: {len(df_final[df_final["Media"] == "Y"])},')
    else:
        print('\n⚠️ 未找到数据文件，脚本可能还在启动...')
        
except Exception as e:
    print(f'\n❌ 检查失败: {e}')

print('\n' + '=' * 60)
EOF
