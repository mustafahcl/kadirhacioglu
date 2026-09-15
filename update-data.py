import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

from pytefas import Crawler


# =========================================================
# PORTFÖY AYARLARI
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


# İlk çalıştırmada 12 aylık geçmiş oluştur.
# Sonraki çalıştırmalarda sadece son 7 gün kontrol edilir.
INITIAL_MONTHS = 12
UPDATE_DAYS = 7


# =========================================================
# TEFAS
# =========================================================

def fetch_fund_history(code):
    """
    TEFAS'ın güncel API'sinden fon geçmişini çeker.
    İlk çalıştırmada 12 ay,
    sonraki çalıştırmalarda son 7 gün.
    """

    history_file = ROOT / f"{code.lower()}-history.json"

    existing = []

    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                existing = json.load(f)

            if not isinstance(existing, list):
                existing = []

        except Exception:
            existing = []


    # -----------------------------------------------------
    # Tarih aralığını belirle
    # -----------------------------------------------------

    today = datetime.now().date()

    if existing:
        start_date = today - timedelta(days=UPDATE_DAYS)
    else:
        start_date = today - timedelta(days=365)


    start = start_date.strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")


    print("")
    print("=" * 60)
    print(f"TEFAS -> {code}")
    print(f"Tarih aralığı: {start} -> {end}")
    print("=" * 60)


    # -----------------------------------------------------
    # TEFAS crawler
    # -----------------------------------------------------

    crawler = Crawler(
        timeout=60,
        max_retry=5
    )

    df = crawler.fetch(
        start=start,
        end=end,
        kind="YAT",
        columns="info",
        fund_code=code
    )


    if df is None or df.empty:
        raise RuntimeError(
            f"{code}: TEFAS veri döndürmedi."
        )


    # -----------------------------------------------------
    # DataFrame -> JSON
    # -----------------------------------------------------

    new_rows = []

    for _, row in df.iterrows():

        date_value = row.get("date")
        price_value = row.get("price")

        if date_value is None or price_value is None:
            continue

        try:
            price = float(price_value)
        except Exception:
            continue


        # Tarihi YYYY-MM-DD formatına çevir
        if hasattr(date_value, "strftime"):
            date_string = date_value.strftime("%Y-%m-%d")
        else:
            date_string = str(date_value)[:10]


        new_rows.append({
            "date": date_string,
            "price": price
        })


    if not new_rows:
        raise RuntimeError(
            f"{code}: TEFAS verisi bulundu fakat fiyat satırı oluşturulamadı."
        )


    # -----------------------------------------------------
    # Eski + yeni verileri birleştir
    # -----------------------------------------------------

    merged = {}

    for item in existing:
        try:
            d = item["date"]
            p = float(item["price"])

            merged[d] = p

        except Exception:
            pass


    for item in new_rows:
        merged[item["date"]] = item["price"]


    # Tarihe göre sırala
    final_rows = [
        {
            "date": date,
            "price": merged[date]
        }
        for date in sorted(merged.keys())
    ]


    # -----------------------------------------------------
    # Son 5 yıllık veriyi tut
    # -----------------------------------------------------

    cutoff = today - timedelta(days=365 * 5)

    filtered_rows = []

    for item in final_rows:

        try:
            d = datetime.strptime(
                item["date"],
                "%Y-%m-%d"
            ).date()

            if d >= cutoff:
                filtered_rows.append(item)

        except Exception:
            continue


    # -----------------------------------------------------
    # Kaydet
    # -----------------------------------------------------

    with open(
        history_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            filtered_rows,
            f,
            ensure_ascii=False,
            indent=2
        )


    latest = filtered_rows[-1]

    print("")
    print(f"✓ {code} güncellendi")
    print(f"  Tarih : {latest['date']}")
    print(f"  Fiyat : {latest['price']}")
    print(f"  Kayıt : {len(filtered_rows)}")


    return latest


# =========================================================
# PORTFÖY JSON
# =========================================================

def update_portfolio(latest_prices):

    portfolio_file = ROOT / "portfolio.json"

    if portfolio_file.exists():

        try:
            with open(
                portfolio_file,
                "r",
                encoding="utf-8"
            ) as f:

                portfolio = json.load(f)

        except Exception:

            portfolio = {
                "owner": "",
                "currency": "TRY",
                "assets": []
            }

    else:

        portfolio = {
            "owner": "",
            "currency": "TRY",
            "assets": []
        }


    # Sabit portföy bilgileri
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


# =========================================================
# MAIN
# =========================================================

def main():

    print("")
    print("==============================================")
    print("       TLY + THF TEFAS GÜNCELLEME")
    print("==============================================")

    latest_prices = {}

    errors = []


    for code in FUNDS:

        try:

            latest = fetch_fund_history(code)

            latest_prices[code] = latest

        except Exception as e:

            print("")
            print(f"❌ {code} HATASI:")
            print(str(e))

            errors.append(code)


    # Hiçbir fon alınamadıysa workflow başarısız olsun
    if len(latest_prices) == 0:

        print("")
        print("❌ Hiçbir TEFAS verisi alınamadı.")
        sys.exit(1)


    # Başarılı fonların fiyatlarını portfolio.json'a yaz
    update_portfolio(latest_prices)


    # Bir fon hata verdiyse de workflow kırmızı olsun
    if errors:

        print("")
        print(
            "❌ Hatalı fonlar: "
            + ", ".join(errors)
        )

        sys.exit(1)


    print("")
    print("==============================================")
    print("✓ TÜM FONLAR BAŞARIYLA GÜNCELLENDİ")
    print("==============================================")


if __name__ == "__main__":
    main()
