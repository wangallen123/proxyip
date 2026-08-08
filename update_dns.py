import os
import requests
import pandas as pd

# 基础配置
API_TOKEN = os.getenv('CF_API_TOKEN')
ZONE_ID = os.getenv('CF_ZONE_ID')
SOURCE_URL = os.getenv('SOURCE_URL', 'https://raw.githubusercontent.com/xgonce/Cloudflare_IP/main/result.csv')

# 读取多任务配置
countries_raw = os.getenv('TARGET_COUNTRIES', 'HK,US,SG').split(',')
record_names_raw = os.getenv('CF_RECORD_NAMES', '').split(',')

# 清洗空格
countries = [c.strip().upper() for c in countries_raw]
record_names = [r.strip() for r in record_names_raw]

# 地区映射表
COUNTRY_MAP = {
    'HK': '香港',
    'US': '美国',
    'SG': '新加坡',
    'CA': '加拿大',
    'JP': '日本',
    'KR': '韩国'
}

def get_top_5_ips(country):
    try:
        df = pd.read_csv(SOURCE_URL)
        # 筛选：IP一致性 + 归属国
        mask = (df['IP'] == df['cf-meta-ip']) & (df['CF归属国'] == country)
        filtered_df = df[mask].copy()

        if filtered_df.empty:
            return []

        # 质量排序：延迟 < 100ms 优先，按速度排
        quality_mask = filtered_df['TCP延迟(ms)'] < 100
        if filtered_df[quality_mask].empty:
            final_df = filtered_df.sort_values(by='速度(Mbps)', ascending=False)
        else:
            final_df = filtered_df[quality_mask].sort_values(by='速度(Mbps)', ascending=False)

        return final_df.head(5)['IP'].tolist()
    except Exception as e:
        print(f"❌ {country} 数据处理失败: {e}")
        return []

def update_cf(record_name, ip_list):
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    base_url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    
    # 获取并清理旧记录
    res = requests.get(base_url, headers=headers, params={"name": record_name, "type": "A"})
    for record in res.json().get('result', []):
        requests.delete(f"{base_url}/{record['id']}", headers=headers)
    
    # 添加新记录
    for ip in ip_list:
        data = {"type": "A", "name": record_name, "content": ip, "ttl": 60, "proxied": False}
        requests.post(base_url, headers=headers, json=data)
    print(f"✅ 已更新 DNS: {record_name}")

if __name__ == "__main__":
    all_lines = [] # 用于存放汇总数据

    for i in range(len(countries)):
        c, r = countries[i], record_names[i]
        print(f"正在处理: {c} -> {r}")
        
        ips = get_top_5_ips(c)
        if ips:
            # 更新 DNS
            update_cf(r, ips)
            
            # 准备当前地区的数据
            remark = COUNTRY_MAP.get(c, c)
            current_ips_with_remark = [f"{ip}#{remark}" for ip in ips]
            
            # 保存分地区文件
            with open(f"{c.lower()}_ips.txt", 'w', encoding='utf-8') as f:
                f.write("\n".join(current_ips_with_remark) + "\n")
            
            # 加入汇总列表
            all_lines.extend(current_ips_with_remark)
        
    # --- 汇总保存 ---
    if all_lines:
        with open("all_ips.txt", 'w', encoding='utf-8') as f:
            f.write("\n".join(all_lines) + "\n")
        print(f"📂 所有地区 IP 已汇总至 all_ips.txt (共 {len(all_lines)} 条)")
