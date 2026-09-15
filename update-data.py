import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests


# =========================================================
# PORTFÖY
# =========================================================

ROOT = Path(__file__).resolve().parent

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


# =========================================================
# TEFAS AYARLARI
# =========================================================

TEFAS_URL = "https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/"
}


# =========================================================
# TEFAS'TAN FON VERİSİ ÇEK
# =========================================================

def get_tefas_data(code, period=12):

    session = requests.Session()

    session.headers.update(HEADERS)

    # Önce TEFAS ana sayfasına girip session/cookie oluştur
    home = session.get(
        "https://www.tefas.gov.tr/",
        timeout=30
    )

    home.raise_for_status()

    payload = {
        "fonKodu": code,
        "dil": "TR",
        "periyod": period
    }

    response = session.post(
        TEFAS_URL,
        json=payload,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if data.get("errorCode"):
        raise RuntimeError(
            f"TEFAS API hatası: {data.get('errorMessage')}"
        )

    result = data.get("resultList", [])

    if not result:
        raise RuntimeError(
            f"{code}: TEFAS veri döndürmedi."
        )

    return result


# =========================================================
# TARİH NORMALİZASYONU
# =========================================================

def normalize_date(value):

    if value is None:
        return None

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    value = str(value).strip()

    # Örnek:
    # 15.09.2026
    if "." in value:
        try:
            return datetime.strptime(
                value[:10],
                "%d.%m.%Y"
            ).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Örnek:
    # 2026-09-15
    if "-" in value:
        return value[:10]

    return None


# =========================================================
# FİYAT NORMALİZASYONU
# =========================================================

def normalize_price(value):

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    # Türkçe format ihtimali:
    # 9.593,900000
    if "," in value:

        value = value.replace(".", "")
        value = value.replace(",", ".")

    try:
        return float(value)

    except Exception:
        return None


# =========================================================
# FON GEÇMİŞİNİ GÜNCELLE
# =========================================================

def fetch_fund_history(code):

    history_file = ROOT / f"{code.lower()}-history.json"

    existing = []

    # -----------------------------------------------------
    # Mevcut geçmiş
    # -----------------------------------------------------

    if history_file.exists():

        try:

            with open(
                history_file,
                "r",
                encoding="utf-8"
            ) as f:

                existing = json.load(f)

            if not isinstance(existing, list):
                existing = []

        except Exception:

            existing = []


    print("")
    print("=" * 60)
    print(f"TEFAS -> {code}")
    print("=" * 60)


    # -----------------------------------------------------
    # TEFAS
    # -----------------------------------------------------

    # 12 aylık veri çekiyoruz.
    # Böylece yeni fiyat geldikçe geçmiş de güvenli şekilde
    # yenilenmiş oluyor.

    records = get_tefas_data(
        code,
        period=12
    )


    print(
        f"TEFAS {code}: "
        f"{len(records)} kayıt bulundu."
    )


    # -----------------------------------------------------
    # TEFAS kayıtlarını hazırla
    # -----------------------------------------------------

    merged = {}


    # Eski kayıtlar
    for item in existing:

        try:

            date_value = normalize_date(
                item.get("date")
            )

            price_value = normalize_price(
                item.get("price")
            )

            if date_value and price_value is not None:

                merged[date_value] = price_value

        except Exception:
            continue


    # Yeni TEFAS kayıtları
    for item in records:

        # Güncel TEFAS API:
        # tarih
        # fiyat

        date_value = normalize_date(
            item.get("tarih")
        )

        price_value = normalize_price(
            item.get("fiyat")
        )

        if date_value is None:
            continue

        if price_value is None:
            continue

        merged[date_value] = price_value


    # -----------------------------------------------------
    # Sırala
    # -----------------------------------------------------

    final_rows = []

    for date_value in sorted(merged.keys()):

        final_rows.append({
            "date": date_value,
            "price": merged[date_value]
        })


    if not final_rows:

        raise RuntimeError(
            f"{code}: Kullanılabilir fiyat verisi bulunamadı."
        )


    # -----------------------------------------------------
    # Son 5 yıl
    # -----------------------------------------------------

    cutoff = datetime.now().date() - timedelta(
        days=365 * 5
    )

    filtered = []

    for item in final_rows:

        try:

            item_date = datetime.strptime(
                item["date"],
                "%Y-%m-%d"
            ).date()

            if item_date >= cutoff:

                filtered.append(item)

        except Exception:

            continue


    # -----------------------------------------------------
    # JSON KAYDET
    # -----------------------------------------------------

    with open(
        history_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            filtered,
            f,
            ensure_ascii=False,
            indent=2
        )


    latest = filtered[-1]


    print("")
    print(f"✓ {code} BAŞARILI")
    print(f"  Tarih : {latest['date']}")
    print(f"  Fiyat : {latest['price']}")
    print(f"  Kayıt : {len(filtered)}")

    return latest


# =========================================================
# PORTFÖY.JSON
# =========================================================

def update_portfolio(latest_prices):

    portfolio_file = ROOT / "portfolio.json"


    # Mevcut dosyayı oku
    if portfolio_file.exists():

        try:

            with open(
                portfolio_file,
                "r",
                encoding="utf-8"
            ) as f:

                portfolio = json.load(f)

        except Exception:

            portfolio = {}

    else:

        portfolio = {}


    # -----------------------------------------------------
    # PORTFÖY
    # -----------------------------------------------------

    portfolio["owner"] = portfolio.get(
        "owner",
        "Mustafa Hacıoğlu"
    )

    portfolio["currency"] = "TRY"


    portfolio["assets"] = [
        {
            "code": "TLY",
            "name": "TLY",
            "quantity": 14,
            "avgCost": 9593.90
        },
        {
            "code": "THF",
            "name": "THF",
            "quantity": 1922,
            "avgCost": 2.912217
        }
    ]


    portfolio["latest"] = latest_prices


    portfolio["updatedAt"] = datetime.now(
        timezone.utc
    ).isoformat()


    # -----------------------------------------------------
    # TOPLAM MALİYET
    # -----------------------------------------------------

    total_cost = 0

    for asset in portfolio["assets"]:

        total_cost += (
            float(asset["quantity"])
            *
            float(asset["avgCost"])
        )


    portfolio["totalCost"] = round(
        total_cost,
        6
    )


    # -----------------------------------------------------
    # TOPLAM GÜNCEL DEĞER
    # -----------------------------------------------------

    total_value = 0

    for code, latest in latest_prices.items():

        asset = next(
            (
                x for x in portfolio["assets"]
                if x["code"] == code
            ),
            None
        )

        if asset is None:
            continue

        total_value += (
            float(asset["quantity"])
            *
            float(latest["price"])
        )


    portfolio["totalValue"] = round(
        total_value,
        6
    )


    portfolio["totalProfit"] = round(
        total_value - total_cost,
        6
    )


    if total_cost > 0:

        portfolio["totalProfitPercent"] = round(
            ((total_value - total_cost) / total_cost)
            * 100,
            4
        )

    else:

        portfolio["totalProfitPercent"] = 0


    # -----------------------------------------------------
    # KAYDET
    # -----------------------------------------------------

    with open(
        portfolio_file,
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
    print("✓ portfolio.json güncellendi")
    print(f"  Toplam maliyet : {total_cost:,.2f} TL")
    print(f"  Güncel değer   : {total_value:,.2f} TL")
    print(
        f"  Kâr/Zarar      : "
        f"{total_value - total_cost:,.2f} TL"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print("")
    print("=" * 60)
    print("       TLY + THF TEFAS GÜNCELLEME")
    print("=" * 60)


    latest_prices = {}

    errors = []


    # -----------------------------------------------------
    # TLY + THF
    # -----------------------------------------------------

    for code in FUNDS:

        try:

            latest = fetch_fund_history(
                code
            )

            latest_prices[code] = latest

        except Exception as e:

            print("")
            print(f"❌ {code} HATASI:")
            print(str(e))

            errors.append(code)


    # -----------------------------------------------------
    # Hiç veri yok
    # -----------------------------------------------------

    if not latest_prices:

        print("")
        print(
            "❌ TLY veya THF için "
            "TEFAS verisi alınamadı."
        )

        sys.exit(1)


    # -----------------------------------------------------
    # PORTFÖYÜ GÜNCELLE
    # -----------------------------------------------------

    update_portfolio(
        latest_prices
    )


    # -----------------------------------------------------
    # Hata varsa workflow kırmızı
    # -----------------------------------------------------

    if errors:

        print("")
        print(
            "❌ Hatalı fonlar: "
            + ", ".join(errors)
        )

        sys.exit(1)


    print("")
    print("=" * 60)
    print("✓ TÜM FONLAR BAŞARIYLA GÜNCELLENDİ")
    print("=" * 60)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":
    main()
