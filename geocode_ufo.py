"""
UFO数据地理编码脚本
为UFO数据添加经纬度坐标
"""

import pandas as pd
import numpy as np

# US州缩写到全名的映射字典
US_STATE_MAPPING = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia'
}

# 国家名称标准化（UFO数据中的国家名 -> worldcities中的国家名）
COUNTRY_MAPPING = {
    'usa': 'United States',
    'us': 'United States',
    'united states': 'United States',
    'uk': 'United Kingdom',
    'united kingdom': 'United Kingdom',
}


def normalize_text(text):
    """标准化文本：转小写并去除首尾空格"""
    if pd.isna(text):
        return ''
    return str(text).lower().strip()


def preprocess_data(ufo_df, worldcities_df):
    """
    Step A: 数据预处理
    - 标准化文本字段
    - 按人口降序排列worldcities
    """
    print("=" * 60)
    print("Step A: 数据预处理")
    print("=" * 60)
    
    # 标准化UFO数据
    print("正在标准化UFO数据...")
    ufo_df = ufo_df.copy()
    ufo_df['City_norm'] = ufo_df['City'].apply(normalize_text)
    ufo_df['State_norm'] = ufo_df['State'].apply(normalize_text)
    ufo_df['Country_norm'] = ufo_df['Country'].apply(normalize_text)
    
    # 标准化worldcities数据
    print("正在标准化WorldCities数据...")
    worldcities_df = worldcities_df.copy()
    worldcities_df['city_ascii_norm'] = worldcities_df['city_ascii'].apply(normalize_text)
    worldcities_df['admin_name_norm'] = worldcities_df['admin_name'].apply(normalize_text)
    worldcities_df['country_norm'] = worldcities_df['country'].apply(normalize_text)
    
    # 按人口降序排列（处理population可能为字符串的情况）
    print("正在按人口降序排列WorldCities数据...")
    worldcities_df['population_num'] = pd.to_numeric(worldcities_df['population'], errors='coerce')
    worldcities_df = worldcities_df.sort_values('population_num', ascending=False, na_position='last')
    
    print(f"UFO数据: {len(ufo_df)} 条")
    print(f"WorldCities数据: {len(worldcities_df)} 条")
    
    return ufo_df, worldcities_df


def cascade_matching(ufo_df, worldcities_df):
    """
    Step B: 级联匹配策略
    依次尝试三种匹配方式
    """
    print("\n" + "=" * 60)
    print("Step B: 级联匹配")
    print("=" * 60)
    
    ufo_df = ufo_df.copy()
    ufo_df['lat'] = np.nan
    ufo_df['lng'] = np.nan
    ufo_df['match_method'] = ''
    
    matched_indices = set()
    
    # 第一轮：城市 + 州/省代码（最精准）
    print("\n第一轮匹配：城市 + 州/省...")
    round1_count = 0
    
    for idx, row in ufo_df.iterrows():
        if idx in matched_indices:
            continue
            
        city = row['City_norm']
        state = row['State_norm']
        country = row['Country_norm']
        
        if not city or pd.isna(city):
            continue
        
        # 对于美国，尝试将州缩写转换为全名
        if country in ['usa', 'us', 'united states'] and state in US_STATE_MAPPING:
            state_full = US_STATE_MAPPING[state].lower()
            
            # 匹配：city_ascii + admin_name
            match = worldcities_df[
                (worldcities_df['city_ascii_norm'] == city) &
                (worldcities_df['admin_name_norm'] == state_full) &
                (worldcities_df['iso2'] == 'US')
            ]
            
            if len(match) > 0:
                ufo_df.at[idx, 'lat'] = match.iloc[0]['lat']
                ufo_df.at[idx, 'lng'] = match.iloc[0]['lng']
                ufo_df.at[idx, 'match_method'] = 'City+State'
                matched_indices.add(idx)
                round1_count += 1
                continue
        
        # 对于其他国家，尝试匹配city + admin_name
        if state and not pd.isna(state):
            match = worldcities_df[
                (worldcities_df['city_ascii_norm'] == city) &
                (worldcities_df['admin_name_norm'] == state)
            ]
            
            if len(match) > 0:
                ufo_df.at[idx, 'lat'] = match.iloc[0]['lat']
                ufo_df.at[idx, 'lng'] = match.iloc[0]['lng']
                ufo_df.at[idx, 'match_method'] = 'City+State'
                matched_indices.add(idx)
                round1_count += 1
    
    print(f"  第一轮匹配成功: {round1_count} 条")
    
    # 第二轮：城市 + 国家
    print("\n第二轮匹配：城市 + 国家...")
    round2_count = 0
    
    for idx, row in ufo_df.iterrows():
        if idx in matched_indices:
            continue
            
        city = row['City_norm']
        country = row['Country_norm']
        
        if not city or pd.isna(city):
            continue
        
        # 标准化国家名称
        country_normalized = COUNTRY_MAPPING.get(country, country)
        country_normalized = normalize_text(country_normalized)
        
        match = worldcities_df[
            (worldcities_df['city_ascii_norm'] == city) &
            (worldcities_df['country_norm'] == country_normalized)
        ]
        
        if len(match) > 0:
            ufo_df.at[idx, 'lat'] = match.iloc[0]['lat']
            ufo_df.at[idx, 'lng'] = match.iloc[0]['lng']
            ufo_df.at[idx, 'match_method'] = 'City+Country'
            matched_indices.add(idx)
            round2_count += 1
    
    print(f"  第二轮匹配成功: {round2_count} 条")
    
    # 第三轮：仅匹配城市名（保底）
    print("\n第三轮匹配：仅城市名...")
    round3_count = 0
    
    for idx, row in ufo_df.iterrows():
        if idx in matched_indices:
            continue
            
        city = row['City_norm']
        
        if not city or pd.isna(city):
            continue
        
        # 由于已按人口降序排列，取第一个匹配的（人口最多的）
        match = worldcities_df[worldcities_df['city_ascii_norm'] == city]
        
        if len(match) > 0:
            ufo_df.at[idx, 'lat'] = match.iloc[0]['lat']
            ufo_df.at[idx, 'lng'] = match.iloc[0]['lng']
            ufo_df.at[idx, 'match_method'] = 'CityOnly'
            matched_indices.add(idx)
            round3_count += 1
    
    print(f"  第三轮匹配成功: {round3_count} 条")
    
    total_matched = len(matched_indices)
    print(f"\n总匹配成功: {total_matched} 条")
    
    return ufo_df, matched_indices


def main():
    """
    主函数
    """
    print("=" * 60)
    print("UFO数据地理编码脚本")
    print("=" * 60)
    
    # 读取数据
    print("\n正在读取数据文件...")
    ufo_df = pd.read_csv('ufo_list_full.csv')
    worldcities_df = pd.read_csv('worldcities.csv')
    
    original_count = len(ufo_df)
    print(f"原始UFO数据: {original_count} 条")
    
    # Step A: 预处理
    ufo_df, worldcities_df = preprocess_data(ufo_df, worldcities_df)
    
    # Step B: 级联匹配
    ufo_df, matched_indices = cascade_matching(ufo_df, worldcities_df)
    
    # Step C: 合并与输出
    print("\n" + "=" * 60)
    print("Step C: 合并与输出")
    print("=" * 60)
    
    # 只保留成功匹配的行
    ufo_geocoded = ufo_df[ufo_df['lat'].notna()].copy()
    
    # 删除临时列
    ufo_geocoded = ufo_geocoded.drop(columns=['City_norm', 'State_norm', 'Country_norm'])
    
    # 保存结果
    output_file = 'ufo_final_geocoded.csv'
    ufo_geocoded.to_csv(output_file, index=False, encoding='utf-8')
    
    # 输出统计
    print("\n" + "=" * 60)
    print("统计结果")
    print("=" * 60)
    print(f"原始数据: {original_count} 条")
    print(f"成功匹配: {len(ufo_geocoded)} 条")
    print(f"匹配成功率: {len(ufo_geocoded)/original_count*100:.2f}%")
    print(f"丢弃数据: {original_count - len(ufo_geocoded)} 条")
    
    # 匹配方法统计
    print(f"\n匹配方法统计:")
    if 'match_method' in ufo_geocoded.columns:
        method_counts = ufo_geocoded['match_method'].value_counts()
        for method, count in method_counts.items():
            print(f"  {method}: {count} 条")
    
    # 预览前5条数据
    print(f"\n前5条数据预览:")
    preview_cols = ['City', 'State', 'Country', 'lat', 'lng', 'match_method']
    available_cols = [col for col in preview_cols if col in ufo_geocoded.columns]
    print(ufo_geocoded[available_cols].head(5).to_string())
    
    print(f"\n✅ 数据已保存至: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()






