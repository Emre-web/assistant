from datetime import datetime
import os
import re
import warnings
import json
import logging
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import psycopg2

warnings.filterwarnings("ignore")
load_dotenv()

# .env dosyasından veritabanı bilgilerini al
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Log dosyasını başlat
logging.basicConfig(filename='job_scraping.log', level=logging.INFO)

# Veritabanı bağlantısı fonksiyonu
def connect_db():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("Veritabanına başarıyla bağlanıldı!")
        return connection
    except Exception as e:
        print(f"Veritabanına bağlanırken hata oluştu: {e}")
        logging.error(f"Veritabanına bağlanırken hata oluştu: {e}")
        return None

# Veritabanına iş ilanı ekleme fonksiyonu
# Veritabanına iş ilanı ekleme fonksiyonu (GÜNCELLENMİŞ)
def insert_job_to_db(job_data, cursor, connection):
    try:
        # Veri uzunluk kontrolü
        processed_data = {
            'title': job_data.get('title', '')[:255],
            'description': job_data.get('description', '')[:2000],
            'company_name': job_data.get('company_name', '')[:255],
            'location': job_data.get('location', '')[:255],
            'sector': job_data.get('sector', '')[:255],
            'remote_type': job_data.get('remote_type', '')[:100]
        }

        cursor.execute("""
            INSERT INTO job_listings 
            (title, description, company_name, location, sector, remote_type, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            processed_data['title'],
            processed_data['description'],
            processed_data['company_name'],
            processed_data['location'],
            processed_data['sector'],
            processed_data['remote_type']
        ))
        
        job_id = cursor.fetchone()[0]
        connection.commit()
        logging.info(f"Kayıt başarılı! ID: {job_id} - Scraped at: {datetime.now()}")
        return True
        
    except psycopg2.Error as e:
        connection.rollback()
        logging.error(f"PostgreSQL Hatası: {e.pgerror}")
        return False
    except Exception as e:
        connection.rollback()
        logging.error(f"Beklenmeyen Hata: {str(e)}")
        return False
    
# WebDriver başlatma fonksiyonu
def start_driver():
    """ Kullanıcı profiliyle Chrome WebDriver başlatır """
    profile_path = r"user-data-dir=C:\Users\Emrey\AppData\Local\Google\Chrome\User Data\Default"

    options = Options()
    options.add_argument(profile_path)
    options.add_argument("--start-maximized")
    options.add_experimental_option("detach", True)
    options.add_argument("--disable-webrtc")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-infobars")

    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=options)
    return driver

# LinkedIn'e giriş yapma fonksiyonu
def login_to_linkedin(driver):
    """ LinkedIn'e giriş yapar (eğer oturum açık değilse) """
    driver.get("https://www.linkedin.com")
    
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='session_key']")))

        email = driver.find_element(By.CSS_SELECTOR, "input[name='session_key']")
        email.send_keys(os.environ.get("EMAIL"))

        password = driver.find_element(By.CSS_SELECTOR, "input[name='session_password']")
        password.send_keys(os.environ.get("PASSWORD"))
        password.send_keys(Keys.RETURN)
        sleep(3)
    except:
        print("Zaten giriş yapılmış.")
    
sleep(3)

# İş ilanlarını arama fonksiyonu
def search_jobs(driver, keyword="Python Developer", location="London"):
    """ İş ilanlarını aratır ve sonuçları döndürür """
    search_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Arama yap']"))
    )
    search_box.click()
    search_box.send_keys(keyword)
    search_box.send_keys(Keys.RETURN)

    button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//button[text()='İş İlanları']"))
    )
    button.click()
    sleep(2)

    location_box = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[aria-label='Şehir, eyalet veya posta kodu']"))
    )
    location_box.click()
    location_box.send_keys(Keys.CONTROL + "a")
    location_box.send_keys(Keys.BACKSPACE)
    location_box.send_keys(location)
    sleep(2)
    location_box.send_keys(Keys.RETURN)
    sleep(2)

def scrape_jobs():
    """ LinkedIn'den tüm sayfalardaki iş ilanlarını çeker ve veritabanına kaydeder """
    driver = start_driver()
    login_to_linkedin(driver)
    search_jobs(driver)

    sleep(3)
    jobs = []
    page_number = 1
    job_global_index = 1

    connection = connect_db()
    if not connection:
        print("Veritabanı bağlantısı kurulamadı.")
        return

    cursor = connection.cursor()

    while True:
        print(f"\n📄 Sayfa {page_number} işleniyor...")
        sleep(2)

        job_listings = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.scaffold-layout__list-item"))
        )

        print(f"🔍 Bu sayfada {len(job_listings)} ilan bulundu.")
        logging.info(f"Sayfa {page_number}: {len(job_listings)} ilan bulundu.")

        for index, job in enumerate(job_listings):
            try:
                # İlanı tıklanabilir hale getir
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job)
                ActionChains(driver).move_to_element(job).perform()
                sleep(1)
                job.click()
                sleep(2)

                # Başlık ve açıklama bilgileri
                title = job.text.strip().split('\n')[0]
                description_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "jobs-description__container"))
                )
                description = description_element.text.strip()

                # Şirket bilgisi - GÜNCEL VE GÜVENİLİR YÖNTEM
                try:
                    company_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-unified-top-card__company-name"))
                    )
                    company_name = company_element.text.strip()
                except:
                    try:
                        company_element = driver.find_element(By.CSS_SELECTOR, ".artdeco-entity-lockup__subtitle")
                        company_name = company_element.text.strip()
                    except:
                        company_name = "Şirket bilgisi bulunamadı"

                try:
                    location_element = driver.find_element(By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__tertiary-description-container span")
                    location_raw = location_element.text.strip()
                    location = location_raw.split(' · ')[0]
                except Exception:
                    location = "Konum bilgisi bulunamadı"

                try:
                    insights_elements = driver.find_elements(By.CSS_SELECTOR, "li.job-details-jobs-unified-top-card__job-insight")
                    remote_type = next(
                        (el.text.strip() for el in insights_elements if any(word in el.text.lower() for word in ["remote", "uzaktan", "hibrit", "hybrid", "ofis", "on-site"])),
                        "Bilinmiyor"
                    )
                except Exception:
                    remote_type = "Bilinmiyor"

                try:
                    sector_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.t-14.mt5"))
                    )
                    sector_raw = sector_element.text.strip()
                    sector = re.sub(r'\d+[\+]*.*$', '', sector_raw).strip() or "Sektör bilgisi bulunamadı"
                except Exception:
                    sector = "Sektör bilgisi bulunamadı"

                job_data = {
                    "title": title,
                    "description": description,
                    "company_name": company_name,
                    "location": location,
                    "sector": sector,
                    "remote_type": remote_type
                }

                print(f"✅ {job_global_index}. ilan (Sayfa {page_number}, İlan {index + 1}) alındı.")
                insert_job_to_db(job_data, cursor, connection)
                job_global_index += 1

            except Exception as e:
                print(f"❌ Hata (İlan {index + 1}): {e}")
                logging.error(f"Hata: {e}")
                continue

        # Sonraki sayfaya geçmeyi dene
       # Sonraki sayfaya geçmeyi dene
        try:
            next_button = driver.find_element(
                By.CSS_SELECTOR,
                "button.artdeco-button.jobs-search-pagination__button--next[aria-label='Sonraki sayfayı görüntüle']"
            )
            if next_button.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                next_button.click()
                page_number += 1
                sleep(3)
            else:
                print("Son sayfaya ulaşıldı.")
                break
        except Exception:
            print("Sonraki sayfa butonu bulunamadı veya devre dışı. İşlem tamamlandı.")
            break


    connection.commit()
    cursor.close()
    connection.close()
    print("🎉 Tüm ilanlar başarıyla çekildi ve veritabanına kaydedildi.")

if __name__ == "__main__":
    scrape_jobs()
