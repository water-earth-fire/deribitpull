import os
import requests
import datetime

# Configuration
DERIBIT_URL = "https://www.deribit.com/api/v2/"
CURRENCIES = ["BTC", "ETH", "USDC"]

def get_deribit_data():
    # 1. Authentication
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

    # 2. Get Account Data & Index Prices
    for coin in CURRENCIES:
        # Get Equity and Margin for this currency
        summary_resp = requests.get(f"{DERIBIT_URL}private/get_account_summary", 
                                     headers=headers, params={"currency": coin})
        summary_resp.raise_for_status()
        summary = summary_resp.json()['result']

        # Get the current Index Price (USD value) for this currency
        # Note: USDC index is usually $1, but we fetch it to be safe.
        index_name = f"{coin.lower()}_usd" if coin != "USDC" else "usdc_usd"
        price_resp = requests.get(f"{DERIBIT_URL}public/get_index_price", params={"index_name": index_name})
        price_resp.raise_for_status()
        index_price = price_resp.json()['result']['index_price']

        # Manual conversion to USD
        total_usd_equity += summary['equity'] * index_price
        total_usd_maint_margin += summary['maintenance_margin'] * index_price

    # 3. Calculate Global Margin Usage %
    margin_usage = (total_usd_maint_margin / total_usd_equity * 100) if total_usd_equity > 0 else 0

    # 4. Get XRP Net Notional Position
    # XRP options are USDC-settled, so they are queried under the XRP currency
    pos_resp = requests.get(f"{DERIBIT_URL}private/get_positions", 
                             headers=headers, params={"currency": "XRP", "kind": "option"})
    pos_resp.raise_for_status()
    positions = pos_resp.json()['result']
    
    # Deribit XRP Option contract multiplier is 1,000. 
    # 'size' is positive for Long, negative for Short.
    net_xrp_notional = sum(p['size'] * 1000 for p in positions)

    return {
        "total_usd": total_usd_equity,
        "maint_margin": total_usd_maint_margin,
        "usage": margin_usage,
        "xrp_notional": net_xrp_notional
    }

def send_to_telegram(stats):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    msg = (
        f"🏦 *Global Portfolio Summary*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Total NAV:* ${stats['total_usd']:,.2f}\n"
        f"⚠️ *Maint. Margin:* ${stats['maint_margin']:,.2f}\n"
        f"📉 *Margin Usage:* {stats['usage']:.2f}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌀 *Net XRP Option Notional:* {stats['xrp_notional']:,.0f} XRP\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🕒 *Updated:* {datetime.datetime.now().strftime('%H:%M:%S UTC')}"
    )
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    try:
        results = get_deribit_data()
        send_to_telegram(results)
    except Exception as e:
        print(f"Error occurred: {e}")