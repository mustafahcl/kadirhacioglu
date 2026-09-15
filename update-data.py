import json
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
PORTFOLIO_FILE = ROOT / "portfolio.json"

FUNDS = {
    "TLY": {
        "quantity": 14,
        "avgCost": 9593.90
    },
    "THF": {
        "quantity": 1922,
        "avgCost": 2.912217
    }
}

TEFAS_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"

HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


def get_latest_price(code):

    session = requests.Session()
    session.headers.update(HEADERS)

    # Güncel tarihi almak için TEFAS'a istek.
    # TEFAS tarafında güncel fiyat endpoint'i.
    payload = {
        "fontip": "YAT",
        "fonkod": code,
        "bastarih": "",
        "bittarih": ""
    }

    for attempt in range(3):

        try:

            print(f"{code}: TEFAS bağlantısı ({attempt + 1}/3)")

            response = session.post(
                TEFAS_URL,
                json=payload,
                timeout=20
            )

            print(
                f"{code}: HTTP {response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            if isinstance(data, dict):

                rows = (
                    data.get("data")
                    or data.get("resultList")
                    or data.get("result")
                    or []
                )

            elif isinstance(data, list):

                rows = data

            else:

                rows = []

            if not rows:
                raise RuntimeError(
                    f"{code}: TEFAS boş cevap döndürdü."
                )

            # Kod eşleşmesi
            matching = []

            for row in rows:

                row_code = (
                    row.get("fonkod")
                    or row.get("fonKodu")
                    or row.get("code")
                    or row.get("kod")
                )

                if row_code:

                    if str(row_code).upper() == code.upper():
                        matching.append(row)

            if matching:
                rows = matching

            # En son kullanılabilir fiyatı bul
            for row in reversed(rows):

                raw_price = (
                    row.get("fiyat")
                    or row.get("price")
                    or row.get("fonFiyat")
                    or row.get("birimPayDegeri")
                )

                if raw_price is None:
                    continue

                price_text = str(raw_price).strip()

                # Türkçe sayı formatı
                if "," in price_text:
                    price_text = price_text.replace(".", "")
                    price_text = price_text.replace(",", ".")

                price = float(price_text)

                if price > 0:

                    date_value = (
                        row.get("tarih")
                        or row.get("date")
                        or row.get("fonTarih")
                    )

                    return {
                        "price": price,
                        "date": str(date_value)
                        if date_value else None
                    }

            raise RuntimeError(
                f"{code}: Fiyat alanı bulunamadı."
            )

        except Exception as e:

            print(
                f"{code}: {e}"
            )

            if attempt < 2:
                time.sleep(3)

    raise RuntimeError(
        f"{code}: TEFAS'tan güncel fiyat alınamadı."
    )


def calculate_asset(code, price):

    quantity = FUNDS[code]["quantity"]
    avg_cost = FUNDS[code]["avgCost"]

    cost = quantity * avg_cost
    value = quantity * price

    profit = value - cost

    if cost > 0:
        profit_percent = (
            profit / cost
        ) * 100
    else:
        profit_percent = 0

    return {
        "code": code,
        "quantity": quantity,
        "avgCost": avg_cost,
        "price": price,
        "cost": round(cost, 6),
        "value": round(value, 6),
        "profit": round(profit, 6),
        "profitPercent": round(
            profit_percent,
            4
        )
    }


def main():

    print("")
    print("=" * 55)
    print("       TEFAS PORTFÖY GÜNCELLEME")
    print("=" * 55)

    prices = {}

    for code in FUNDS:

        try:

            prices[code] = get_latest_price(code)

        except Exception as e:

            print("")
            print(f"❌ {code}: {e}")
            sys.exit(1)


    # -----------------------------------------------------
    # VARLIKLARI HESAPLA
    # -----------------------------------------------------

    assets = {}

    total_cost = 0
    total_value = 0

    for code in FUNDS:

        price = prices[code]["price"]

        asset = calculate_asset(
            code,
            price
        )

        assets[code] = asset

        total_cost += asset["cost"]
        total_value += asset["value"]


    total_profit = (
        total_value - total_cost
    )

    if total_cost > 0:

        total_profit_percent = (
            total_profit / total_cost
        ) * 100

    else:

        total_profit_percent = 0


    # -----------------------------------------------------
    # PORTFOLIO.JSON
    # -----------------------------------------------------

    portfolio = {

        "owner": "Mustafa Hacıoğlu",

        "currency": "TRY",

        "updatedAt": (
            __import__("datetime")
            .datetime.now()
            .isoformat()
        ),

        "totalCost": round(
            total_cost,
            6
        ),

        "totalValue": round(
            total_value,
            6
        ),

        "totalProfit": round(
            total_profit,
            6
        ),

        "totalProfitPercent": round(
            total_profit_percent,
            4
        ),

        "assets": assets
    }


    with open(
        PORTFOLIO_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            portfolio,
            f,
            ensure_ascii=False,
            indent=2
        )


    print("")
    print("✓ PORTFOLIO.JSON GÜNCELLENDİ")
    print("")
    print(
        f"TLY: {assets['TLY']['price']}"
    )
    print(
        f"THF: {assets['THF']['price']}"
    )
    print("")
    print(
        f"Toplam maliyet: "
        f"{total_cost:,.2f} TL"
    )
    print(
        f"Portföy değeri: "
        f"{total_value:,.2f} TL"
    )
    print(
        f"Toplam kâr/zarar: "
        f"{total_profit:,.2f} TL"
    )
    print(
        f"Getiri: "
        f"{total_profit_percent:.2f}%"
    )
    print("")
    print("=" * 55)


if __name__ == "__main__":
    main()
