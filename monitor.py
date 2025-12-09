# ノジマ4カテゴリ値下げ監視 - エラー時通知なし版

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
        print(f"✅ LINE送信成功: {r.status_code}")
        return True
    except Exception as e:
        print(f"❌ LINE送信失敗: {e}")
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
        
        # 商品アイテム（複数セレクタ）
        items = soup.find_all(['div', 'li', 'a'], class_=lambda x: x and any(kw in str(x).lower() for kw in ['product', 'item', 'goods', 'card']))
        
        for item in items[:40]:
            try:
                name_elem = item.find(['h1','h2','h3','h4','.product-name','.item-title','a','span'])
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)[:60]
                
                price_text = ''
                price_elems = item.find_all(string=lambda x: x and '¥' in str(x))
                for pe in price_elems:
                    price_text = pe.strip()
                    break
                
                price_nums = ''.join(c for c in price_text if c.isdigit())
                if len(price_nums) >= 4:
                    price = int(price_nums)
                    key = f"{category_name}:{name}"
                    products[key] = price
            except:
                continue
        
        return products
        
    except Exception as e:
        print(f"❌ {category_name} スクレイピングエラー（通知なし）: {e}")
        return None  # Noneを返すと通知なし

def main():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')
    print(f"⏰ {timestamp}")
    
    db = load_db()
    all_drops = []
    total_products = 0
    
    # 4カテゴリチェック
    for category_name, url in NOJIMA_CATEGORIES.items():
        print(f"🔍 {category_name}")
        products = scrape_category(url, category_name)
        
        if products is None:  # エラー時はスキップ
            continue
            
        total_products += len(products)
        
        # 値下げ検知
        for key, price in products.items():
            if key in db and db[key] > price:
                drop_amount = db[key] - price
                drop_percent = round((drop_amount / db[key]) * 100, 1)
                cat_short = category_name[:2]
                prod_name = key.split(':', 1)[1]
                all_drops.append({
                    'cat': cat_short,
                    'name': prod_name[:35],
                    'old': f"¥{db[key]:,}",
                    'new': f"¥{price:,}",
                    'drop': f"¥{drop_amount:,}",
                    'pct': f"{drop_percent}%"
                })
        
        # DB更新
        db.update(products)
    
    print(f"📦 総商品数: {total_products}件 | 値下げ: {len(all_drops)}件")
    
    # **値下げ時のみ通知（エラー・商品なし時は通知なし）**
    if all_drops:
        message = f"🔥 【ノジマ値下げ】{len(all_drops)}件\n⏰ {timestamp}\n\n"
        for drop in sorted(all_drops, key=lambda x: int(x['drop'][1:].replace(',', '')), reverse=True)[:6]:
            message += f"{drop['cat']} {drop['name']}\n"
            message += f"  {drop['old']} → {drop['new']}\n"
            message += f"  ↓{drop['drop']} ({drop['pct']})\n\n"
        message += "🔗 https://online.nojima.co.jp/category/114/"
        
        if send_line(message):
            print(f"✅ 値下げ通知送信完了")
    else:
        print("📊 値下げなし → 通知なし（正常）")
    
    save_db(db)
    print("✅ 監視完了")

if __name__ == "__main__":
    main()
