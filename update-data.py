import json
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests


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

TEFAS_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"

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


def request_tefas(code, date_value):

    payload = {
        "fontip": "YAT",
        "fonkod": code,
        "bastarih": date_value,
        "bittarih": date_value
    }

    session = requests.Session()

    session.headers.update(HEADERS)

    for attempt in range(5):

        try:

            response = session.post(
                TEFAS_URL,
                json=payload,
                timeout=60
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

            if rows:
                return rows

        except Exception as e:

            print(
                f"{code}: deneme "
                f"{attempt + 1}/5 başarısız: {e}"
            )

            time.sleep(5)

    return []


def normalize_date(value):

    if value is None:
        return None

    value = str(value).strip()

    for fmt in (
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S"
    ):

        try:

            return datetime.strptime(
                value[:19],
                fmt
            ).strftime("%Y-%m-%d")

        except Exception:
            pass

    return None


def normalize_price(value):

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = str(value).strip()

    try:

        if "," in value:

            value = value.replace(".", "")
            value = value.replace(",", ".")

        return float(value)

    except Exception:

        return None


def get_existing(code):

    file = ROOT / f"{code.lower()}-history.json"

    if not file.exists():
        return []

    try:

        with open(
            file,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        return data if isinstance(data, list) else []

    except Exception:

        return []


def save_history(code, rows):

    file = ROOT / f"{code.lower()}-history.json"

    with open(
        file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            rows,
            f,
            ensure_ascii=False,
            indent=2
        )


def fetch_fund(code):

    print("")
    print("=" * 60)
    print(f"TEFAS -> {code}")
    print("=" * 60)

    existing = get_existing(code)

    merged = {}

    for item in existing:

        try:

            d = normalize_date(
                item.get("date")
            )

            p = normalize_price(
                item.get("price")
            )

            if d and p is not None:
                merged[d] = p

        except Exception:
            pass


    today = datetime.now().date()

    # Son 30 günü ayrı ayrı kontrol ediyoruz.
    # Böylece TEFAS'ın tek istekteki tarih sınırına takılmıyoruz.

    for i in range(30):

        day = today - timedelta(days=i)

        date_string = day.strftime(
            "%d.%m.%Y"
        )

        rows = request_tefas(
            code,
            date_string
        )

        if not rows:
            continue

        for row in rows:

            d = normalize_date(
                row.get("tarih")
                or row.get("date")
            )

            p = normalize_price(
                row.get("fiyat")
                or row.get("price")
            )

            if d and p is not None:

                merged[d] = p


        # TEFAS'ı gereksiz yere hızlı sorgulamayalım.
        time.sleep(1)


    if not merged:

        raise RuntimeError(
            f"{code}: TEFAS'tan veri alınamadı."
        )


    final = []

    for d in sorted(merged.keys()):

        final.append({
            "date": d,
            "price": merged[d]
        })


    # Son 5 yıl
    cutoff = today - timedelta(
        days=365 * 5
    )

    final = [
        x for x in final
        if datetime.strptime(
            x["date"],
            "%Y-%m-%d"
        ).date() >= cutoff
    ]


    save_history(
        code,
        final
    )


    latest = final[-1]

    print("")
    print(f"✓ {code} BAŞARILI")
    print(f"Tarih: {latest['date']}")
    print(f"Fiyat: {latest['price']}")
    print(f"Kayıt: {len(final)}")

    return latest


def update_portfolio(latest):

    file = ROOT / "portfolio.json"

    portfolio = {}

    if file.exists():

        try:

            with open(
                file,
                "r",
                encoding="utf-8"
            ) as f:

                portfolio = json.load(f)

        except Exception:
            portfolio = {}


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

    portfolio["latest"] = latest

    total_cost = 0
    total_value = 0

    for asset in portfolio["assets"]:

        code = asset["code"]
        quantity = float(
            asset["quantity"]
        )
        avg_cost = float(
            asset["avgCost"]
        )

        total_cost += (
            quantity * avg_cost
        )

        if code in latest:

            total_value += (
                quantity
                *
                float(latest[code]["price"])
            )


    portfolio["totalCost"] = round(
        total_cost,
        6
    )

    portfolio["totalValue"] = round(
        total_value,
        6
    )

    portfolio["totalProfit"] = round(
        total_value - total_cost,
        6
    )

    if total_cost:

        portfolio["totalProfitPercent"] = round(
            (
                (total_value - total_cost)
                /
                total_cost
            ) * 100,
            4
        )

    else:

        portfolio["totalProfitPercent"] = 0


    portfolio["updatedAt"] = datetime.now(
        timezone.utc
    ).isoformat()


    with open(
        file,
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


def main():

    print("")
    print("=" * 60)
    print("       TLY + THF TEFAS GÜNCELLEME")
    print("=" * 60)

    latest = {}
    errors = []

    for code in FUNDS:

        try:

            latest[code] = fetch_fund(code)

        except Exception as e:

            print("")
            print(f"❌ {code} HATASI:")
            print(e)

            errors.append(code)


    if not latest:

        print("")
        print("❌ Hiçbir fon verisi alınamadı.")

        sys.exit(1)


    update_portfolio(
        latest
    )


    if errors:

        print("")
        print(
            "❌ Hatalı fonlar: "
            + ", ".join(errors)
        )

        sys.exit(1)


    print("")
    print("=" * 60)
    print("✓ TLY + THF BAŞARIYLA GÜNCELLENDİ")
    print("=" * 60)


if __name__ == "__main__":
    main()
