#!/usr/bin/env python3
# ノジマ値下げ監視 - Render.com 版（1回実行）

import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json
import sys

# 環境変数から設定読み込み
GMAIL_USER = os.getenv('GMAIL_USER')
APP_PASSWORD = os.getenv('APP_PASSWORD')
NOTIFY_EMAIL = os.getenv('NOTIFY_EMAIL')
NOJIMA_URL = "https://online.nojima.co.jp/category/114/"
PRICE_DB_FILE = "/tmp/nojima_prices.json"

# 必須環境変数の確認
if not all([GMAIL_USER, APP_PASSWORD, NOTIFY_EMAIL]):
    print("❌ 環境変数が不足しています")
    print("Render.com で GMAIL_USER, APP_PASSWORD, NOTIFY_EMAIL を設定してください")
    sys.exit(1)

print("✅ ノジマ値下げ監視（Render.com版）開始")
print(f"📧 送信元: {GMAIL_USER}")
print(f"📮 通知先: {NOTIFY_EMAIL}")

# ========== メール送信関数 ==========
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = NOTIFY_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_USER, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✅ メール送信成功: {subject}")
        return True
    except Exception as e:
        print(f"❌ メール送信エラー: {e}")
        return False

# ========== 価格DB管理 ==========
def load_price_db():
    try:
        if os.path.exists(PRICE_DB_FILE):
            with open(PRICE_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except:
        return {}

def save_price_db(db):
    try:
        with open(PRICE_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
        print("💾 DB保存完了")
    except Exception as e:
        print(f"❌ DB保存エラー: {e}")

# ========== スクレイピング ==========
def fetch_products():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(NOJIMA_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        products = {}
        
        # 商品要素を取得
        product_items = soup.find_all('div', class_=['item', 'product', 'ec-product'])
        if not product_items:
            product_items = soup.find_all('a', href=True)
        
        for item in product_items[:50]:
            try:
                name_elem = item.find(['h2', 'h3', 'a']) or item
                name = name_elem.get_text(strip=True)[:100]
                
                price_elem = item.find(['span', 'p'], string=lambda x: x and '¥' in x)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = ''.join(c for c in price_text if c.isdigit())
                    if price and len(price) > 3 and name:
                        products[name] = int(price)
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
    
    # 価格DB読み込み
    price_db = load_price_db()
    
    # 商品取得
    current_products = fetch_products()
    if not current_products:
        send_email("⚠️ ノジマ監視エラー", f"商品取得に失敗しました\n⏰ {timestamp}")
        return
    
    # 値下げ検知
    price_drop_items = []
    for name, price in current_products.items():
        if name in price_db and price_db[name] > price > 0:
            drop_amount = price_db[name] - price
            drop_percent = (drop_amount / price_db[name]) * 100
            price_drop_items.append({
                'name': name,
                'old_price': price_db[name],
                'new_price': price,
                'drop': drop_amount,
                'drop_percent': drop_percent
            })
    
    # 通知送信
    if price_drop_items:
        subject = f"🔥 【値下げ検知】{len(price_drop_items)}件"
        body = f"値下げ情報 ({timestamp})\n\n"
        
        for item in sorted(price_drop_items, key=lambda x: x['drop'], reverse=True)[:5]:
            body += f"📱 {item['name'][:40]}\n"
            body += f"   ¥{item['old_price']:,} → ¥{item['new_price']:,}\n"
            body += f"   ↓ ¥{item['drop']:,} ({item['drop_percent']:.0f}%)\n\n"
        
        body += f"🔗 詳細: {NOJIMA_URL}"
        send_email(subject, body)
        print(f"🔥 値下げ通知送信: {len(price_drop_items)}件")
    else:
        print("📊 値下げなし")
    
    # DB更新
    price_db.update(current_products)
    save_price_db(price_db)
    
    print("✅ 実行完了")

if __name__ == "__main__":
    main()
