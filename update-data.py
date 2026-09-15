import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

TEFAS_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"

FUNDS = {
    "TLY": {
        "quantity": 14,
        "avg_cost": 9593.90
    },
    "THF": {
        "quantity": 1922,
        "avg_cost": 2.912217
    }
}

HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )
}


def get_value(item, names):
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return None


def get_price(code, date):
    date_str = date.strftime("%Y%m%d")

    payload = {
        "fonTipi": "YAT",
        "fonKodu": code,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "kurucuKod": None,
        "basTarih": date_str,
        "bitTarih": date_str,
        "basSira": 1,
        "bitSira": 100000,
        "dil": "TR",
        "sFonTurKod": "",
        "fonKod": "",
        "fonGrup": "",
        "fonUnvanTip": ""
    }

    try:
        r = requests.post(
            TEFAS_URL,
            json=payload,
            headers=HEADERS,
            timeout=30
        )

        print(f"{code} {date.strftime('%d.%m.%Y')}: HTTP {r.status_code}")

        if r.status_code != 200:
            return None

        data = r.json()

        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = []

            for key in [
                "data",
                "items",
                "resultList",
                "fonlar",
                "dataList"
            ]:
                if isinstance(data.get(key), list):
                    records = data[key]
                    break
        else:
            records = []

        for item in records:

            if not isinstance(item, dict):
                continue

            fund_code = get_value(
                item,
                [
                    "fonKodu",
                    "FonKodu",
                    "fonkod",
                    "code",
                    "kod"
                ]
            )

            if str(fund_code).upper() != code.upper():
                continue

            price = get_value(
                item,
                [
                    "fiyat",
                    "FonFiyat",
                    "fonFiyat",
                    "birimPayDegeri",
                    "payDegeri",
                    "price"
                ]
            )

            if price is None:
                continue

            try:
                price = float(
                    str(price).replace(",", ".")
                )
            except:
                continue

            if price <= 0:
                continue

            return price

    except Exception as e:
        print(f"{code}: {e}")

    return None


def find_prices(code):

    today = datetime.now()

    # Bugün + son 4 gün.
    # Hafta sonu / tatil durumunda son geçerli fiyatı bulur.
    for i in range(5):

        date = today - timedelta(days=i)

        price = get_price(code, date)

        if price is not None:
            return {
                "price": price,
                "date": date.strftime("%Y-%m-%d")
            }

    return None


def main():

    print()
    print("=" * 55)
    print("          TEFAS PORTFÖY GÜNCELLEME")
    print("=" * 55)
    print()

    assets = {}

    for code, info in FUNDS.items():

        print(f"{code}: güncel fiyat aranıyor...")

        result = find_prices(code)

        if result is None:
            print(f"❌ {code}: fiyat bulunamadı.")
            raise SystemExit(1)

        quantity = info["quantity"]
        avg_cost = info["avg_cost"]
        current_price = result["price"]

        cost = quantity * avg_cost
        value = quantity * current_price

        profit = value - cost

        profit_percent = (
            profit / cost * 100
            if cost else 0
        )

        assets[code] = {
            "code": code,
            "quantity": quantity,
            "avgCost": avg_cost,

            "currentPrice": current_price,

            "cost": round(cost, 2),
            "value": round(value, 2),

            "profit": round(profit, 2),
            "profitPercent": round(profit_percent, 4),

            "dailyProfit": None,
            "dailyProfitPercent": None,

            "priceDate": result["date"]
        }

        print(
            f"✅ {code}: "
            f"{current_price:.6f} TL"
        )

    total_cost = sum(
        x["cost"] for x in assets.values()
    )

    total_value = sum(
        x["value"] for x in assets.values()
    )

    total_profit = total_value - total_cost

    total_profit_percent = (
        total_profit / total_cost * 100
        if total_cost else 0
    )

    portfolio = {
        "currency": "TRY",

        "updatedAt": datetime.now().isoformat(),

        "assets": assets,

        "summary": {
            "totalCost": round(total_cost, 2),
            "totalValue": round(total_value, 2),
            "totalProfit": round(total_profit, 2),
            "totalProfitPercent": round(
                total_profit_percent,
                4
            )
        }
    }

    Path("portfolio.json").write_text(
        json.dumps(
            portfolio,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("=" * 55)
    print("✅ PORTFÖY GÜNCELLENDİ")
    print("=" * 55)

    print(
        f"Toplam maliyet : "
        f"{total_cost:,.2f} TL"
    )

    print(
        f"Toplam değer   : "
        f"{total_value:,.2f} TL"
    )

    print(
        f"Genel K/Z      : "
        f"{total_profit:,.2f} TL"
    )

    print(
        f"Genel getiri   : "
        f"%{total_profit_percent:.2f}"
    )

    print("=" * 55)


if __name__ == "__main__":
    main()
