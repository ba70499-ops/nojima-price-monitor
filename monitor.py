# ノジマ値下げ監視 - Render.com LINE版（15分ごと自動実行）

import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import sys

# ========== 環境変数設定 ==========
CHANNEL_TOKEN = os.getenv('CHANNEL_TOKEN')
NOJIMA_URL = "https://online.nojima.co.jp/category/114/"
PRICE_DB_FILE = "/tmp/nojima_prices.json"
LINE_API_URL = "https://api.line.me/v2/bot/message/broadcast"

# 必須チェック
if not CHANNEL_TOKEN:
    print("❌ CHANNEL_TOKEN が設定されていません")
    print("Render.com の Environment Variables で設定してください")
    sys.exit(1)

print("✅ ノジマ値下げ監視（LINE版）開始")
print(f"🔗 LINE API: {LINE_API_URL[:50]}...")

# ========== LINE送信関数 ==========
def send_line_message(message):
    """LINEにメッセージ送信"""
    try:
        headers = {
            "Authorization": f"Bearer {CHANNEL_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }
        response = requests.post(LINE_API_URL, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            print("✅ LINE送信成功")
            return True
        else:
            print(f"❌ LINE送信エラー: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ LINE送信失敗: {e}")
        return False

# ========== 価格DB管理 ==========
def load_price_db():
    """価格DB読み込み"""
    try:
        if os.path.exists(PRICE_DB_FILE):
            with open(PRICE_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except:
        return {}

def save_price_db(db):
    """価格DB保存"""
    try:
        with open(PRICE_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print("💾 DB保存完了")
    except Exception as e:
        print(f"❌ DB保存エラー: {e}")

# ========== スクレイピング ==========
def fetch_products():
    """ノジマから商品取得"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(NOJIMA_URL, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        products = {}
        
        # 商品コンテナを探す（複数パターン対応）
        containers = soup.find_all(['div', 'li', 'a'], class_=lambda x: x and any(keyword in x for keyword in ['item', 'product', 'goods', 'ec-']))
        
        for container in containers[:60]:
            try:
                # 商品名取得
                name_elem = container.find(['h1','h2','h3','a','span'], string=lambda x: x and len(x.strip()) > 3)
                if not name_elem:
                    continue
                name = name_elem.get_text(strip=True)[:80]
                
                # 価格取得
                price_elems = container.find_all(['span', 'div', 'p'], string=lambda x: x and '¥' in x)
                for price_elem in price_elems:
                    price_text = price_elem.get_text(strip=True)
                    price_nums = ''.join(c for c in price_text if c.isdigit())
                    if len(price_nums) > 3:
                        price = int(price_nums)
                        products[name] = price
                        break
                        
            except:
                continue
        
        print(f"📦 取得商品数: {len(products)}")
        return products
        
    except Exception as e:
        print(f"❌ スクレイピングエラー: {e}")
        return {}

# ========== メイン実行 ==========
def main():
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"⏰ 実行時刻: {timestamp}")
    
    # 開始通知（1日1回のみ）
    now = datetime.now()
    if now.hour == 0 and now.minute < 5:  # 0時台に1回
        send_line_message(
            f"✅ ノジマ値下げ監視 再起動\n"
            f"⏰ {timestamp}\n"
            f"🔗 {NOJIMA_URL}"
        )
    
    # 価格DB読み込み
    price_db = load_price_db()
    print(f"💾 前回DB: {len(price_db)}商品")
    
    # 商品取得
    current_products = fetch_products()
    if not current_products:
        send_line_message(f"⚠️ 商品取得失敗\n⏰ {timestamp}")
        return
    
    # 値下げ検知
    price_drops = []
    for name, price in current_products.items():
        if name in price_db and price_db[name] > price > 0:
            drop_amount = price_db[name] - price
            drop_percent = round((drop_amount / price_db[name]) * 100, 1)
            price_drops.append({
                'name': name[:35],
                'old': f"¥{price_db[name]:,}",
                'new': f"¥{price:,}",
                'drop': f"¥{drop_amount:,}",
                'pct': f"{drop_percent}%"
            })
    
    # 通知送信
    if price_drops:
        message = f"🔥 【値下げ検知】{len(price_drops)}件\n⏰ {timestamp}\n\n"
        for drop in sorted(price_drops, key=lambda x: int(x['drop'][1:].replace(',', '')), reverse=True)[:8]:
            message += f"📱 {drop['name']}\n"
            message += f"   {drop['old']} → {drop['new']}\n"
            message += f"   {drop['drop']} ({drop['pct']})\n\n"
        
        message += f"🔗 {NOJIMA_URL}"
        send_line_message(message)
        print(f"🔥 値下げ通知: {len(price_drops)}件")
    else:
        print("📊 値下げなし")
    
    # DB更新
    price_db.update(current_products)
    save_price_db(price_db)
    print("✅ 実行完了")

if __name__ == "__main__":
    main()
