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


def get_tefas_price(code):
    """
    Sadece son kullanılabilir TEFAS fiyatını arar.
    Geçmiş veri kaydetmez.
    """

    today = datetime.now()

    # Bugün + son 4 gün.
    # Hafta sonu / resmi tatilde son iş gününü yakalayabilmek için.
    for days_back in range(5):

        date = today - timedelta(days=days_back)
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
            print(f"{code}: {date.strftime('%d.%m.%Y')} sorgulanıyor...")

            response = requests.post(
                TEFAS_URL,
                json=payload,
                headers=HEADERS,
                timeout=30
            )

            print(f"{code}: HTTP {response.status_code}")

            response.raise_for_status()

            data = response.json()

            # TEFAS cevabını kontrol et
            records = []

            if isinstance(data, list):
                records = data

            elif isinstance(data, dict):
                for key in [
                    "data",
                    "items",
                    "resultList",
                    "fonlar",
                    "dataList"
                ]:
                    value = data.get(key)

                    if isinstance(value, list):
                        records = value
                        break

            if not records:
                print(f"{code}: Bu tarihte veri yok.")
                continue

            # Fon kodunu bul
            for item in records:

                if not isinstance(item, dict):
                    continue

                fund_code = (
                    item.get("fonKodu")
                    or item.get("fund_code")
                    or item.get("FonKodu")
                    or item.get("code")
                )

                if str(fund_code).upper() != code.upper():
                    continue

                price = (
                    item.get("fiyat")
                    or item.get("price")
                    or item.get("FonFiyat")
                    or item.get("fonFiyat")
                    or item.get("birimPayDegeri")
                )

                if price is None:
                    continue

                price = float(price)

                if price <= 0:
                    continue

                print(
                    f"✅ {code}: {price:.6f} TL "
                    f"({date.strftime('%d.%m.%Y')})"
                )

                return {
                    "price": price,
                    "date": date.strftime("%Y-%m-%d")
                }

        except Exception as e:
            print(f"{code}: hata -> {e}")

    return None


def main():

    print("=" * 55)
    print("       TEFAS PORTFÖY GÜNCELLEME")
    print("=" * 55)

    assets = {}

    for code, info in FUNDS.items():

        result = get_tefas_price(code)

        if result is None:
            print(f"\n❌ {code}: TEFAS'tan fiyat alınamadı.")
            raise SystemExit(1)

        quantity = info["quantity"]
        avg_cost = info["avg_cost"]

        price = result["price"]

        cost = quantity * avg_cost
        value = quantity * price

        profit = value - cost

        profit_percent = (
            (profit / cost) * 100
            if cost > 0 else 0
        )

        assets[code] = {
            "code": code,
            "quantity": quantity,
            "avgCost": avg_cost,
            "currentPrice": price,
            "cost": round(cost, 2),
            "value": round(value, 2),
            "profit": round(profit, 2),
            "profitPercent": round(profit_percent, 4),
            "priceDate": result["date"]
        }

    total_cost = sum(
        item["cost"]
        for item in assets.values()
    )

    total_value = sum(
        item["value"]
        for item in assets.values()
    )

    total_profit = total_value - total_cost

    total_profit_percent = (
        total_profit / total_cost * 100
        if total_cost > 0 else 0
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
                total_profit_percent, 4
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

    print("\n" + "=" * 55)
    print("✅ PORTFÖY GÜNCELLENDİ")
    print("=" * 55)

    print(f"Toplam maliyet : {total_cost:,.2f} TL")
    print(f"Güncel değer   : {total_value:,.2f} TL")
    print(f"Toplam kâr/zarar: {total_profit:,.2f} TL")
    print(f"Getiri         : %{total_profit_percent:.2f}")
    print("=" * 55)


if __name__ == "__main__":
    main()
