import os
import requests

# Configuration
DERIBIT_URL = "https://www.deribit.com/api/v2/"
CURRENCY = "BTC"  # Options: BTC, ETH, SOL, USDC

def get_stats():
    # 1. Get Access Token
    auth_params = {
        "grant_type": "client_credentials",
        "client_id": os.getenv('DERIBIT_CLIENT_ID'),
        "client_secret": os.getenv('DERIBIT_CLIENT_SECRET')
    }
    
    auth_req = requests.get(f"{DERIBIT_URL}public/auth", params=auth_params)
    auth_req.raise_for_status() # Stop if login fails
    token = auth_req.json()['result']['access_token']

    # 2. Get Account Summary
    headers = {"Authorization": f"Bearer {token}"}
    params = {"currency": CURRENCY}
    
    resp = requests.get(f"{DERIBIT_URL}private/get_account_summary", headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()['result']
    
    return {
        "nav": data['equity'],
        "maint": data['maintenance_margin'],
        "usage": (data['maintenance_margin'] / data['equity']) * 100 if data['equity'] > 0 else 0
    }

def send_to_telegram(stats):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # Simple formatting
    msg = (
        f"📊 *Deribit {CURRENCY} Status*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *NAV:* {stats['nav']:.4f}\n"
        f"⚠️ *Maint. Margin:* {stats['maint']:.4f}\n"
        f"📉 *Margin Usage:* {stats['usage']:.2f}%"
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    try:
        results = get_stats()
        send_to_telegram(results)
    except Exception as e:
        print(f"Error occurred: {e}")
