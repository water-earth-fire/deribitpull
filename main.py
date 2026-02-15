import os
import requests
import datetime

# Configuration
DERIBIT_URL = "https://www.deribit.com/api/v2/"

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

    # 2. Get Index Prices for conversion
    def get_price(coin):
        index = f"{coin.lower()}_usd" if coin != "USDC" else "usdc_usd"
        res = requests.get(f"{DERIBIT_URL}public/get_index_price", params={"index_name": index}).json()
        return res['result']['index_price']

    btc_price = get_price("BTC")
    eth_price = get_price("ETH")
    usdc_price = get_price("USDC") # Usually ~$1.00

    # 3. Get Account Summaries
    # We fetch all to calculate the "Total USD Balance" (NAV) manually
    btc_data = requests.get(f"{DERIBIT_URL}private/get_account_summary", headers=headers, params={"currency": "BTC"}).json()['result']
    eth_data = requests.get(f"{DERIBIT_URL}private/get_account_summary", headers=headers, params={"currency": "ETH"}).json()['result']
    usdc_data = requests.get(f"{DERIBIT_URL}private/get_account_summary", headers=headers, params={"currency": "USDC"}).json()['result']

    # Calculate Total NAV (BTC + ETH + USDC balances converted to USD)
    total_nav_usd = (btc_data['equity'] * btc_price) + \
                    (eth_data['equity'] * eth_price) + \
                    (usdc_data['equity'] * usdc_price)

    # 4. Correct Portfolio Margin Calculation
    # In X:PM, the 'maintenance_margin' in the BTC summary is the GLOBAL MM requirement 
    # for the whole account, denominated in BTC.
    global_maint_margin_usd = btc_data['maintenance_margin'] * btc_price
    
    # Calculate Usage
    margin_usage = (global_maint_margin_usd / total_nav_usd * 100) if total_nav_usd > 0 else 0

    # 5. Get XRP Notional (USDC-settled)
    # XRP options are linear and settled in USDC, so they appear in the USDC positions list.
    pos_resp = requests.get(f"{DERIBIT_URL}private/get_positions", 
                            headers=headers, params={"currency": "USDC", "kind": "option"})
    pos_resp.raise_for_status()
    positions = pos_resp.json()['result']
    
    # In the API, 'size' for linear options is already (contracts * multiplier)
    # so 'size' represents the actual number of XRP tokens.
    net_xrp_notional = sum(p['size'] for p in positions if "XRP" in p['instrument_name'])

    return {
        "total_usd": total_nav_usd,
        "maint_margin": global_maint_margin_usd,
        "usage": margin_usage,
        "xrp_notional": net_xrp_notional
    }

def send_to_telegram(stats):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    msg = (
        f"🏦 *Global X:PM Portfolio*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Total NAV:* ${stats['total_usd']:,.2f}\n"
        f"⚠️ *Global MM:* ${stats['maint_margin']:,.2f}\n"
        f"📉 *Margin Usage:* {stats['usage']:.2f}%\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌀 *Net XRP Option:* {stats['xrp_notional']:,.0f} XRP\n"
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