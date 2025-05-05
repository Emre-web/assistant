import requests
import json
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# 🔧 Ortam değişkenlerini yükle
load_dotenv()
print("🔧 Ortam değişkenleri yüklendi")

# 📦 PostgreSQL bağlantı bilgileri
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "job_insights_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433")
}
print("📦 Veritabanı yapılandırması yüklendi")

# 🔐 OpenRouter API Ayarları
API_KEY = os.getenv("API_KEY")
MODEL = "mistralai/mistral-small-3.1-24b-instruct:free"

def get_db_connection():
    """PostgreSQL veritabanı bağlantısı kurar"""
    print("🔗 Veritabanına bağlanılıyor...")
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        print("✅ Veritabanına başarıyla bağlanıldı")
        return conn
    except psycopg2.Error as e:
        print(f"🔴 Veritabanı bağlantı hatası: {str(e)}")
        return None

def fetch_unanalyzed_jobs(limit: int = 100) -> List[Dict]:
    """Analiz edilmemiş iş ilanlarını çeker"""
    print("📥 Analiz edilmemiş iş ilanları çekiliyor...")
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as cur:
            cur.execute(""" 
                SELECT id, title, company_name, location, description, 
                       sector, remote_type, scraped_at
                FROM job_listings
                WHERE NOT EXISTS (
                    SELECT 1 FROM job_analysis WHERE job_id = job_listings.id
                )
                ORDER BY scraped_at DESC
                LIMIT %s
            """, (limit,))
            jobs = cur.fetchall()
            print(f"📊 {len(jobs)} analiz edilmemiş ilan bulundu")
            return jobs
    except psycopg2.Error as e:
        print(f"🔴 Veritabanı sorgu hatası: {str(e)}")
        return []
    finally:
        conn.close()
        print("🔌 Veritabanı bağlantısı kapatıldı")

def chat_with_ai(prompt: str) -> Optional[str]:
    """OpenRouter API ile sohbet tamamlama"""
    print("🤖 AI'den analiz isteniyor...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-Title": "Job Parser",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()

        if "error" in result:
            print(f"🔴 API Hatası: {result['error'].get('message', 'Bilinmeyen API hatası')}")
            return None

        if not result.get("choices"):
            print("🔴 Geçersiz yanıt formatı (choices boş)")
            return None

        content = result["choices"][0]["message"].get("content")
        print("✅ AI'den yanıt alındı")
        return content

    except requests.exceptions.RequestException as e:
        print(f"🔴 İstek hatası: {str(e)}")
        return None
    except json.JSONDecodeError:
        print("🔴 Geçersiz JSON yanıtı")
        return None

def save_analysis_results(job_id: int, ai_results: Dict, scraped_at: str) -> bool:
    """Analiz sonuçlarını veritabanına kaydeder"""
    print(f"💾 Analiz sonuçları kaydediliyor... (Job ID: {job_id})")
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO job_analysis (
                    job_id, hard_skills, soft_skills, location, 
                    sector, responsibilities, work_type, scraped_at, title_skills
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                job_id,
                json.dumps(ai_results.get("hard_skills", [])),
                json.dumps(ai_results.get("soft_skills", [])),
                ai_results.get("location", "Belirtilmemiş"),
                ai_results.get("sector", "Belirtilmemiş"),
                json.dumps(ai_results.get("responsibilities", [])),
                ai_results.get("work_type", "Belirtilmemiş"),
                scraped_at,
                json.dumps(ai_results.get("title_skills", []))  # 👈 Yeni eklenen alan
            ))
            conn.commit()
            print("✅ Analiz sonuçları başarıyla kaydedildi")
            return True
    except psycopg2.Error as e:
        print(f"🔴 Analiz kayıt hatası: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()
        print("🔌 Veritabanı bağlantısı kapatıldı")

def analyze_job(job: Dict) -> Optional[Dict]:
    """Bir iş ilanını analiz eder"""
    print(f"🧠 İş ilanı analiz ediliyor: {job.get('company_name')} - {job.get('title')}")
    prompt = f"""
Aşağıdaki iş ilanını analiz ederek STRICT JSON FORMATINDA cevapla. SADECE JSON formatında cevap ver, başka hiçbir açıklama veya işaret içerme:
{{
    "hard_skills": ["Teknik beceriler listesi"],
    "soft_skills": ["Kişisel beceriler listesi"],
    "location": "Şehir, Ülke",
    "sector": "Sektör adı",
    "responsibilities": ["Sorumluluklar listesi"],
    "work_type": "remote / hybrid / on-site şeklinde açık şekilde belirt. Açıklama içinde doğrudan geçmiyorsa tahmin et ama kesinlikle 'bilinmiyor', 'belirtilmemiş' gibi ifadeler kullanma.",
    "title_skills": ["Pozisyon başlığına bakarak ilan başlığı yazdır. en uygun pozisyon başlığını yazdır."]
}}

    İlan Detayları:
    Şirket: {job.get('company_name', '')}
    Pozisyon Başlığı: {job.get('title', '')}
    Konum: {job.get('location', '')}
    Sektör: {job.get('sector', '')}
    Çalışma Tipi: {job.get('remote_type', '')}
    Açıklama: {job.get('description', '')[:3000]}...
    """
    
    response = chat_with_ai(prompt)
    if not response:
        print("⚠️ AI'den geçerli bir yanıt alınamadı")
        return None
    
    try:
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        print("🔍 Temizlenmiş yanıt:", cleaned[:200] + "...")
        analysis = json.loads(cleaned)
        print("✅ JSON başarıyla ayrıştırıldı")
        return analysis
    except json.JSONDecodeError as e:
        print(f"🔴 JSON parse hatası: {str(e)}")
        print("🔴 Ham AI yanıtı:", response)
        return None

def process_jobs():
    """Analiz edilmemiş tüm iş ilanlarını işler"""
    print("🚀 Analiz işlemi başlatılıyor...")
    jobs = fetch_unanalyzed_jobs()
    if not jobs:
        print("✅ Analiz edilecek yeni iş ilanı bulunamadı")
        return
    
    success_count = 0
    for job in jobs:
        analysis = analyze_job(job)
        if analysis:
            saved = save_analysis_results(job['id'], analysis, job.get('scraped_at'))
            if saved:
                success_count += 1
                print(f"✅ Başarıyla işlendi: ID {job['id']}")
            else:
                print(f"⚠️ Kayıt hatası: ID {job['id']}")
        else:
            print(f"⚠️ Analiz hatası: ID {job['id']}")
    
    print(f"\n🎉 Toplam {success_count}/{len(jobs)} ilan başarıyla analiz edildi ve kaydedildi")

if __name__ == "__main__":
    process_jobs()
