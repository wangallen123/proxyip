import os
import requests
import pandas as pd

# 基础配置
API_TOKEN = os.getenv('CF_API_TOKEN')
ZONE_ID = os.getenv('CF_ZONE_ID')
SOURCE_URL = os.getenv('SOURCE_URL', 'https://raw.githubusercontent.com/xgonce/Cloudflare_IP/refs/heads/main/result.csv')

# 读取多任务配置 (转为列表)
countries = os.getenv('TARGET_COUNTRIES', 'HK,JP,SG,US,CA').split(',')
record_names = os.getenv('CF_RECORD_NAMES', '').split(',')

def get_top_5_ips(country):
    try:
        df = pd.read_csv(SOURCE_URL)
        # 1. 筛选：IP一致性 + 对应归属国
        mask = (df['IP'] == df['cf-meta-ip']) & (df['CF归属国'] == country.strip())
        filtered_df = df[mask].copy()

        if filtered_df.empty:
            print(f"⚠️ 区域 {country} 未筛选到匹配 IP")
            return []

        # 2. 综合质量排序 (延迟 < 100ms 优先，再按速度排)
        quality_mask = filtered_df['TCP延迟(ms)'] < 100
        if filtered_df[quality_mask].empty:
            final_df = filtered_df.sort_values(by='速度(Mbps)', ascending=False)
        else:
            final_df = filtered_df[quality_mask].sort_values(by='速度(Mbps)', ascending=False)

        return final_df.head(5)['IP'].tolist()
    except Exception as e:
        print(f"❌ 数据处理错误 ({country}): {e}")
        return []

def update_cf(record_name, ip_list):
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    base_url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"

    # 获取该域名当前的所有 A 记录
    res = requests.get(base_url, headers=headers, params={"name": record_name.strip(), "type": "A"})
    existing_records = res.json().get('result', [])

    # 删除旧记录
    for record in existing_records:
        requests.delete(f"{base_url}/{record['id']}", headers=headers)

    # 添加新记录
    for ip in ip_list:
        data = {"type": "A", "name": record_name.strip(), "content": ip, "ttl": 60, "proxied": False}
        requests.post(base_url, headers=headers, json=data)
    
    print(f"✅ 已完成 {record_name} ({len(ip_list)} 个 IP) 的更新")

if __name__ == "__main__":
    if len(countries) != len(record_names):
        print("❌ 错误：地区列表与域名列表数量不匹配！")
    else:
        for i in range(len(countries)):
            current_country = countries[i].strip()
            current_record = record_names[i].strip()
            
            print(f"正在处理任务: {current_country} -> {current_record}")
            ips = get_top_5_ips(current_country)
            if ips:
                update_cf(current_record, ips)
