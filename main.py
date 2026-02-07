import os
import requests

# Configuration
DERIBIT_URL = "https://www.deribit.com/api/v2/"
CURRENCY = "XRP" # Pulling XRP data

def get_data():
    # 1. Authenticate
    auth_params = {
        "grant_type": "client_credentials",
        "client_id": os.getenv('DERIBIT_CLIENT_ID'),
        "client_secret": os.getenv('DERIBIT_CLIENT_SECRET')
    }
    auth_req = requests.get(f"{DERIBIT_URL}public/auth", params=auth_params).json()
    token = auth_req['result']['access_token']
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Account Summary (NAV & Margin)
    acc_res = requests.get(f"{DERIBIT_URL}private/get_account_summary", 
                           headers=headers, params={"currency": CURRENCY}).json()
    acc = acc_res['result']
    price = acc['index_price']

    # 3. Get All Positions (Filter for Short Calls)
    pos_res = requests.get(f"{DERIBIT_URL}private/get_positions", 
                           headers=headers, params={"currency": CURRENCY, "kind": "option"}).json()
    
    short_calls_qty = 0
    short_calls_usd_value = 0
    
    for pos in pos_res.get('result', []):
        # Logic: Size < 0 (Short) and Instrument ends with -C (Call)
        if pos['size'] < 0 and pos['instrument_name'].endswith('-C'):
            qty = abs(pos['size'])
            short_calls_qty += qty
            # Mark price is in XRP, so: qty * mark_price * index_price = USD value
            short_calls_usd_value += (qty * pos['mark_price'] * price)

    return {
        "price": price,
        "nav_usd": acc['equity'] * price,
        "maint_usd": acc['maintenance_margin'] * price,
        "margin_usage": (acc['maintenance_margin'] / acc['equity']) * 100 if acc['equity'] > 0 else 0,
        "short_qty": short_calls_qty,
        "short_usd": short_calls_usd_value
    }

def send_telegram(data):
    msg = (
        f"📉 *Deribit {CURRENCY} Portfolio*\n"
        f"💰 *{CURRENCY} Price:* ${data['price']:,.4f}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏦 *NAV:* `${data['nav_usd']:,.2f}`\n"
        f"⚠️ *Maint. Margin:* `${data['maint_usd']:,.2f}`\n"
        f"⚡ *Margin Usage:* {data['margin_usage']:.2f}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔴 *Short Call Summary:*\n"
        f"📦 *Total Size:* {data['short_qty']:,.0f} {CURRENCY}\n"
        f"💸 *Cost to Close:* `${data['short_usd']:,.2f}`"
    )
    
    requests.post(f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage", 
                  data={"chat_id": os.getenv('TELEGRAM_CHAT_ID'), "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    try:
        stats = get_data()
        send_telegram(stats)
    except Exception as e:
        print(f"Error: {e}")
