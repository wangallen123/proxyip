import os
import requests
import pandas as pd

# 配置
API_TOKEN = os.getenv('CF_API_TOKEN')
ZONE_ID = os.getenv('CF_ZONE_ID')
RECORD_NAME = os.getenv('CF_RECORD_NAME')
TARGET_COUNTRY = os.getenv('TARGET_COUNTRY', 'CA') 
SOURCE_URL = os.getenv('SOURCE_URL', 'https://raw.githubusercontent.com/xgonce/Cloudflare_IP/refs/heads/main/result.csv')

def get_top_5_ips():
    try:
        df = pd.read_csv(SOURCE_URL)
        # 1. 筛选：IP一致性 + 归属国
        mask = (df['IP'] == df['cf-meta-ip']) & (df['CF归属国'] == TARGET_COUNTRY)
        filtered_df = df[mask].copy()

        if filtered_df.empty:
            print(f"区域 {TARGET_COUNTRY} 无匹配 IP")
            return []

        # 2. 综合质量排序
        # 优先选择 TCP 延迟低于 100ms 的，然后按速度从大到小排
        # 如果都没有低于 100ms 的，则整体按速度排
        quality_mask = filtered_df['TCP延迟(ms)'] < 100
        if filtered_df[quality_mask].empty:
            final_df = filtered_df.sort_values(by='速度(Mbps)', ascending=False)
        else:
            final_df = filtered_df[quality_mask].sort_values(by='速度(Mbps)', ascending=False)

        top_5 = final_df.head(5)
        print("筛选出的前 5 名 IP：")
        print(top_5[['IP', '速度(Mbps)', 'TCP延迟(ms)']])
        return top_5['IP'].tolist()
    except Exception as e:
        print(f"数据处理错误: {e}")
        return []

def update_cloudflare_dns(ip_list):
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    base_url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"

    # 1. 获取当前域名下的所有 A 记录
    res = requests.get(base_url, headers=headers, params={"name": RECORD_NAME, "type": "A"})
    existing_records = res.json().get('result', [])

    # 2. 删除旧的 A 记录 (清理干净，防止 IP 堆积)
    for record in existing_records:
        requests.delete(f"{base_url}/{record['id']}", headers=headers)
        print(f"已删除旧记录: {record['content']}")

    # 3. 添加新的前 5 名 IP
    for ip in ip_list:
        data = {
            "type": "A",
            "name": RECORD_NAME,
            "content": ip,
            "ttl": 60,
            "proxied": False
        }
        post_res = requests.post(base_url, headers=headers, json=data)
        if post_res.json().get('success'):
            print(f"成功添加新记录: {ip}")

if __name__ == "__main__":
    ips = get_top_5_ips()
    if ips:
        update_cloudflare_dns(ips)
    else:
        print("未筛选到有效 IP，不执行更新")
