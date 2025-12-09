#!/usr/bin/env python3
# ノジマ中古4カテゴリ値下げ監視 - スマホ/タブレット/PC/カメラ（15分ごと）

import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys

CHANNEL_TOKEN = os.getenv('CHANNEL_TOKEN')
NOJIMA_CATEGORIES = {
    "中古スマホ": "https://online.nojima.co.jp/category/10006902/",
    "中古タブレット": "https://online.nojima.co.jp/category/10006501/",
    "中古PC": "https://online.nojima.co.jp/category/10006301/",
    "中古カメラ": "https://online.nojima.co.jp/category/10006201/"
}
PRICE_DB_FILE = "/tmp/nojima_prices.json"
LINE_API_URL = "https://api.line.me/v2/bot/message/broadcast"

if not CHANNEL_TOKEN:
    print("❌ CHANNEL_TOKEN 未設定")
    sys.exit(1)

def send_line(text):
    headers = {"Authorization": f"Bearer {CHANNEL_TOKEN}", "Content-Type": "application/json"}
    data = {"messages": [{"type": "text", "text": text}]}
    try:
        r = requests.post(LINE_API_URL, headers=headers, json=data, timeout=10)
        print(f"✅ LINE: {r.status_code}")
        return True
    except:
        return False

def load_db():
    try:
        if os.path.exists(PRICE_DB_FILE):
            with open(PRICE_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except:
        return {}

def save_db(db):
    try:
        with open(PRICE_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print("💾 DB保存完了")
    except:
        pass

def scrape_category(url, category_name):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        products = {}
        
        print(f"🔍 {category_name} 取得中...")
        
        # 商品アイテム取得（複数セレクタ対応）
        items = soup.find_all(['div', 'li', 'a'], class_=lambda x: x and any(kw in str(x).lower() for kw in ['product', 'item', 'goods', 'card']))
        
        for item in items[:40]:
            try:
                # 商品名
                name_elem = item.find(['h1','h2','h3','h4','.product-name','.item-title','a','span'])
                if name_elem:
                    name = name_elem.get_text(strip=True)[:60]
                else:
                    continue
                
                # 価格（¥抽出）
                price_text = ''
                price_elems = item.find_all(string=lambda x: x and '¥' in str(x))
                for pe in price_elems:
                    price_text = pe.strip()
                    break
                
                if not price_text:
                    price_span = item.find(['span', 'div', 'p', '.price'], class_=lambda x: x and ('price' in str(x).lower() or '¥' in str(x)))
                    if price_span:
                        price_text = price_span.get_text(strip=True)
                
                price_nums = ''.join(c for c in price_text if c.isdigit())
                if len(price_nums) >= 4:
                    price = int(price_nums)
                    key = f"{category_name}:{name}"
                    products[key] = price
                    print(f"  📦 {name[:30]}: ¥{price:,}")
                    
            except:
                continue
        
        print(f"  ✅ {category_name}: {len(products)}件取得")
        return products
        
    except Exception as e:
        print(f"❌ {category_name} エラー: {e}")
        return {}

def main():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')
    print(f"⏰ ノジマ4カテゴリ監視開始: {timestamp}")
    
    # DB読み込み
    price_db = load_db()
    print(f"💾 前回DB: {len(price_db)}件")
    
    all_drops = []
    
    # 4カテゴリ同時チェック
    for category_name, url in NOJIMA_CATEGORIES.items():
        current_products = scrape_category(url, category_name)
        
        # 値下げ検知
        for key, price in current_products.items():
            if key in price_db and price_db[key] > price:
                drop_amount = price_db[key] - price
                drop_percent = round((drop_amount / price_db[key]) * 100, 1)
                cat_name = key.split(':')[0][:2]
                prod_name = key.split(':', 1)[1]
                all_drops.append({
                    'category': cat_name,
                    'name': prod_name[:35],
                    'old': f"¥{price_db[key]:,}",
                    'new': f"¥{price:,}",
                    'drop': f"¥{drop_amount:,}",
                    'pct': f"{drop_percent}%"
                })
        
        # DB更新
        price_db.update(current_products)
    
    print(f"📊 値下げ検知: {len(all_drops)}件")
    
    # LINE通知（値下げ時のみ）
    if all_drops:
        message = f"🔥 【ノジマ値下げ】{len(all_drops)}件\n⏰ {timestamp}\n\n"
        for drop in sorted(all_drops, key=lambda x: int(x['drop'][1:].replace(',', '')), reverse=True)[:8]:
            message += f"{drop['category']} {drop['name']}\n"
            message += f"   {drop['old']} → {drop['new']}\n"
            message += f"   {drop['drop']} ({drop['pct']})\n\n"
        
        message += "🔗 https://online.nojima.co.jp/category/114/"
        if send_line(message):
            print(f"✅ 値下げ通知送信: {len(all_drops)}件")
    else:
        print("📊 値下げなし（正常）")
    
    # DB保存
    save_db(price_db)
    print("✅ ノジマ4カテゴリ監視完了")

if __name__ == "__main__":
    main()
