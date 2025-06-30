# İş İlanı Analiz Platformu

Bu proje, iş ilanı verilerinin otomatik olarak toplanması (scraping), analiz edilmesi ve modern bir arayüzde görselleştirilmesi için geliştirilmiş bir veri analitiği platformudur. Projede yapay zeka destekli analizler, anahtar kelime çıkarımı ve kapsamlı veri görselleştirme özellikleri bulunmaktadır.

## Proje Kapsamı ve Özellikler

- **Veri Kazıma (Scraping):** Farklı kaynaklardan iş ilanı verileri otomatik olarak toplanır ve PostgreSQL veritabanında saklanır.
- **Yapay Zeka Destekli Analiz:** İş ilanı metinlerinden anahtar kelime çıkarımı, pozisyon ve meslek tahmini gibi işlemler için temel AI teknikleri ve doğal dil işleme yöntemleri kullanılır.
- **Veri Görselleştirme:** Streamlit ve Plotly ile modern, interaktif dashboard arayüzü. Sektör, şehir, beceri ve maaş trendleri gibi birçok metrik görselleştirilir.
- **Zaman Serisi Analizi:** İş ilanı ve maaş verilerinin aylık değişimi, beceri ve sektör trendleri zaman içinde izlenebilir.
- **Kullanıcı Dostu Arayüz:** Filtreleme, detaylı tablo ve grafikler, kolay veri keşfi için modern bir UI ile sunulur.
- **Meslek Verisi Toplama:** Kullanıcıdan alınan iş tanımlarını analiz ederek anahtar kelime ve meslek önerileri sunar.

## Klasör ve Dosya Yapısı

- `analysis/StreamlitDashboard.py`: Tüm analiz ve görselleştirme arayüzünün ana kodu. Veritabanı bağlantısı, veri çekme, işleme, AI tabanlı analiz ve tüm görselleştirme burada yapılır.
- `.env`: Veritabanı bağlantı bilgileri (kullanıcı tarafından oluşturulmalı).
- `requirements.txt`: Gerekli Python paketleri.
- (Varsa) `scraper/`: İş ilanı verilerini otomatik olarak toplayan (scraping) Python scriptleri.
- (Varsa) `data/`: Toplanan veya örnek veri dosyaları.

## Kurulum

1. **Gereksinimler**
   - Python 3.8+
   - PostgreSQL veritabanı
   - Gerekli Python paketleri: `streamlit`, `pandas`, `plotly`, `psycopg2`, `python-dotenv`, (ve scraping için `requests`, `beautifulsoup4` vb.)

2. **Bağımlılıkları yükleyin**
   ```
   pip install -r requirements.txt
   ```

3. **.env dosyasını oluşturun**
   Proje kök dizinine bir `.env` dosyası ekleyin ve aşağıdaki gibi doldurun:
   ```
   DB_NAME=veritabani_adi
   DB_USER=kullanici_adi
   DB_PASSWORD=sifre
   DB_HOST=localhost
   DB_PORT=5432
   ```

4. **Veritabanı şemasını oluşturun**
   `job_analysis` tablosunun ve gerekli alanların mevcut olduğundan emin olun.

## Kullanım

Uygulamayı başlatmak için terminalde proje dizininde şu komutu çalıştırın:
```
streamlit run analysis/StreamlitDashboard.py
```

Arayüzde:
- **Analiz Paneli:** Sektör, şehir, beceri ve sorumluluk dağılımları, pozisyon başlıkları ve filtreleme.
- **Zaman Serisi Analizi:** Aylık ilan ve maaş değişimleri, beceri ve sektör trendleri.
- **Meslek Verisi Toplama:** Girilen iş tanımından anahtar kelime ve meslek önerisi (AI tabanlı).

## Yapay Zeka ve Veri Kazıma

- **AI Kullanımı:** Anahtar kelime çıkarımı, pozisyon başlığı tahmini ve öneri sistemlerinde temel doğal dil işleme ve istatistiksel analizler kullanılmıştır.
- **Scraper:** Projede iş ilanı verileri otomatik olarak web sitelerinden çekilmekte, temizlenmekte ve analiz için veritabanına kaydedilmektedir.

## Katkı

Katkıda bulunmak için lütfen bir fork oluşturun ve pull request gönderin.

## Lisans

© 2025 İş Analiz Platformu • Tüm hakları saklıdır.
