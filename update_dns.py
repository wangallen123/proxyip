import os
import requests
import pandas as pd

# 从环境变量读取配置
API_TOKEN = os.getenv('CF_API_TOKEN')
ZONE_ID = os.getenv('CF_ZONE_ID')
RECORD_NAME = os.getenv('CF_RECORD_NAME')
SOURCE_URL = "https://raw.githubusercontent.com/xgonce/Cloudflare_IP/refs/heads/main/result.csv"

def get_best_ip():
    try:
        # 读取 CSV，注意原文件可能没有 Header，根据图片看是有 Header 的
        df = pd.read_csv(SOURCE_URL)
        
        # --- 核心筛选逻辑 ---
        # 1. 筛选 IP 列与 cf-meta-ip 列相同的行
        # 2. 这里的列名需与 CSV 文件实际表头一致，如果图片里是 'IP' 和 'cf-meta-ip'
        mask = df['IP'] == df['cf-meta-ip']
        filtered_df = df[mask].copy()
        
        if filtered_df.empty:
            print("没有找到 IP 与 cf-meta-ip 相同的匹配项")
            return None

        # 3. 在匹配项中，按速度(Mbps)降序排列，取第一个
        # 注意：如果表头有中文，请确保名称完全一致，如 '速度(Mbps)'
        best_ip = filtered_df.sort_values(by='速度(Mbps)', ascending=False).iloc[0]['IP']
        print(f"筛选出的最优 IP 为: {best_ip}")
        return best_ip
    except Exception as e:
        print(f"读取数据失败: {e}")
        return None

def update_cloudflare_dns(ip):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. 获取现有解析记录 ID
    dns_url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records"
    res = requests.get(dns_url, headers=headers, params={"name": RECORD_NAME})
    records = res.json().get('result', [])
    
    if not records:
        print(f"未找到域名 {RECORD_NAME} 的解析记录，请先手动创建一条 A 记录")
        return

    record_id = records[0]['id']
    current_ip = records[0]['content']

    # 2. 如果 IP 没变，不更新
    if current_ip == ip:
        print(f"IP 未变化 ({ip})，跳过更新")
        return

    # 3. 更新 A 记录
    update_data = {
        "type": "A",
        "name": RECORD_NAME,
        "content": ip,
        "ttl": 60,  # 选最快的 60s 生效
        "proxied": False # 必须关闭小云朵
    }
    put_res = requests.put(f"{dns_url}/{record_id}", headers=headers, json=update_data)
    if put_res.json().get('success'):
        print(f"成功更新 {RECORD_NAME} -> {ip}")
    else:
        print(f"更新失败: {put_res.text}")

if __name__ == "__main__":
    target_ip = get_best_ip()
    if target_ip:
        update_cloudflare_dns(target_ip)
