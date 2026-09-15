# TLY + THF Portföy

Başlangıç portföyü:
- TLY: 14 adet, ortalama maliyet 9.593,90 TL
- THF: 1.922 adet, ortalama maliyet 2,912217 TL

GitHub Pages için `index.html` ana sayfadır. `.github/workflows/update-tefas.yml`, hafta içi TEFAS verisini otomatik kontrol eder ve `tly-history.json` / `thf-history.json` dosyalarını günceller.

Önemli: GitHub Pages yalnızca statik siteyi gösterir; fiyat güncellemesini GitHub Actions yapar. Workflow'un çalışması için Actions'ın açık olması ve repository'nin `contents: write` iznine izin vermesi gerekir.
