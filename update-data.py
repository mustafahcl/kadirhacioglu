import json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.tefas.gov.tr/",
    "Origin": "https://www.tefas.gov.tr",
}

FUNDS = ["TLY", "THF"]
session = requests.Session()
session.headers.update(HEADERS)

def norm_num(x):
    if x is None: return None
    if isinstance(x,(int,float)): return float(x)
    s = str(x).strip().replace("₺","").replace("TL","").replace(" ","")
    # TEFAS can return Turkish decimal strings or numeric strings.
    if "," in s and "." in s:
        # if last separator is comma, Turkish format
        if s.rfind(",") > s.rfind("."):
            s=s.replace(".","").replace(",",".")
        else:
            s=s.replace(",","")
    elif "," in s:
        s=s.replace(".","").replace(",",".")
    try: return float(s)
    except: return None

def parse_date(x):
    if not x: return None
    s=str(x).strip()
    for fmt in ("%d.%m.%Y","%Y-%m-%d","%Y-%m-%dT%H:%M:%S","%d/%m/%Y"):
        try: return datetime.strptime(s[:19],fmt).strftime("%Y-%m-%d")
        except: pass
    return s[:10]

def endpoint_simple(code):
    url="https://www.tefas.gov.tr/api/funds/fonFiyatBilgiGetir"
    r=session.post(url,json={"fonKodu":code,"dil":"TR","periyod":12},timeout=25)
    r.raise_for_status()
    data=r.json()
    rows=data.get("resultList") or data.get("data") or []
    out=[]
    for row in rows:
        if isinstance(row, dict):
            price=norm_num(row.get("fiyat") or row.get("price") or row.get("FONFIYAT"))
            date=parse_date(row.get("tarih") or row.get("date") or row.get("TARIH"))
        elif isinstance(row, (list, tuple)):
            # Bazı TEFAS wrapper'ları (fiyat, getiri, tarih) tuple döndürebiliyor.
            price = next((norm_num(v) for v in row if norm_num(v) is not None), None)
            date = next((parse_date(v) for v in row if isinstance(v,str) and re.search(r'\\d{4}[-/.]\\d{1,2}[-/.]\\d{1,2}',v)), None)
        else:
            price, date = None, None
        if price and date: out.append({"date":date,"price":price})
    return out

def endpoint_db(code):
    url="https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
    today=datetime.now().strftime("%d.%m.%Y")
    payload={
        "fontip":"YAT","fonkod":code,"bastarih":"01.01.2024","bittarih":today,
        "sfontur":"","fongrup":"","fonturkod":"","fonunvantip":"","kurucukod":""
    }
    r=session.post(url,data=payload,timeout=30)
    r.raise_for_status()
    data=r.json()
    rows=data.get("data") or data.get("resultList") or []
    out=[]
    for row in rows:
        if not isinstance(row,dict): continue
        price=None
        for k in ("FONFIYAT","fonFiyat","fiyat","FIYAT","price"):
            if k in row:
                price=norm_num(row[k]); break
        date=None
        for k in ("TARIH","tarih","date","Tarih"):
            if k in row:
                date=parse_date(row[k]); break
        if price and date: out.append({"date":date,"price":price})
    return out

def get_history(code):
    errors=[]
    for fn in (endpoint_simple, endpoint_db):
        try:
            rows=fn(code)
            if rows:
                # Deduplicate dates and sort.
                d={}
                for x in rows: d[x["date"]]=x["price"]
                return [{"date":k,"price":d[k]} for k in sorted(d)]
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")
    raise RuntimeError("TEFAS verisi alınamadı | " + " | ".join(errors))

def save(code, rows):
    path=ROOT/f"{code.lower()}-history.json"
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")

def main():
    ok=0
    latest={}
    for code in FUNDS:
        rows=get_history(code)
        save(code, rows)
        latest[code]=rows[-1]
        print(f"{code}: {rows[-1]['date']} {rows[-1]['price']}")
        ok+=1

    p=ROOT/"portfolio.json"
    data=json.loads(p.read_text(encoding="utf-8"))
    data["updatedAt"]=datetime.now(timezone.utc).isoformat()
    data["latest"]=latest
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    if ok != len(FUNDS):
        sys.exit(1)

if __name__=="__main__":
    main()
