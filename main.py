import os
import requests
import datetime

# Configuration
DERIBIT_URL = "https://www.deribit.com/api/v2/"
# Currencies to check for equity and margin
CURRENCIES = ["BTC", "ETH", "USDC"]

def get_deribit_data():
    # 1. Get Access Token
    auth_params = {
        "grant_type": "client_credentials",
        "client_id": os.getenv('DERIBIT_CLIENT_ID'),
        "client_secret": os.getenv('DERIBIT_CLIENT_SECRET')
    }
    
    auth_req = requests.get(f"{DERIBIT_URL}public/auth", params=auth_params)
    auth_req.raise_for_status()
    token = auth_req.json()['result']['access_token']
    headers = {"Authorization": f"Bearer {token}"}

    total_usd_equity = 0.0
    total_usd_maint_margin = 0.0
    
    # 2. Aggregate USD values across all sub-accounts
    for coin in CURRENCIES:
        resp = requests.get(f"{DERIBIT_URL}private/get_account_summary", 
                            headers=headers, 
                            params={"currency": coin})
        resp.raise_for_status()
        data = resp.json()['result']
        
        # Pulling the USD equivalents directly from Deribit
        total_usd_equity += data.get('equity_usd', 0.0)
        total_usd_maint_margin += data.get('maintenance_margin_usd', 0.0)

    # Calculate Global Margin Usage %
    margin_usage = (total_usd_maint_margin / total_usd_equity * 100) if total_usd_equity > 0 else 0

    # 3. Get Net Notional XRP Options Position
    xrp_params = {"currency": "XRP", "kind": "option"}
    pos_resp = requests.get(f"{DERIBIT_URL}private/get_positions", headers=headers, params=xrp_params)
    pos_resp.raise_for_status()
    positions = pos_resp.json()['result']
    
    # Net sum: positive for longs, negative for shorts
    net_xrp_notional = sum(p['size'] for p in positions)

    return {
        "total_usd": total_usd_equity,
        "maint_margin": total_usd_maint_margin,
        "usage": margin_usage,
        "xrp_notional": net_xrp_notional
    }

def send_to_telegram(stats):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # Format the message for clarity and risk monitoring
    msg = (
        f"🏦 *Global Portfolio Summary*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Total NAV:* ${stats['total_usd']:,.2f}\n"
        f"⚠️ *Maint. Margin:* ${stats['maint_margin']:,.2f}\n"
        f"📉 *Margin Usage:* {stats['usage']:.2f}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌀 *Net XRP Option:* {stats['xrp_notional']:,.0f} XRP\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕒 *Updated:* {datetime.datetime.now().strftime('%H:%M:%S UTC')}"
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

if __name__ == "__main__":
    try:
        results = get_deribit_data()
        send_to_telegram(results)
    except Exception as e:
        print(f"Error occurred: {e}")