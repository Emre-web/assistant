import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import json
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Renk paleti (dark theme)
COLORS = {
    "primary": "#4C84FF",
    "secondary": "#1F2D3D",
    "accent": "#8E44AD",
    "grey": "#B0B0B0",
    "black": "#1A1A1A",
    "background": "#121212"
}

# Config
load_dotenv()
st.set_page_config(
    page_title="İş İlanı Analiz Paneli",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="📊"
)

# Updated CSS for modern UI
st.markdown(f"""
<style>
    body {{
        background-color: {COLORS['background']};
        color: {COLORS['grey']};
        font-family: 'Arial', sans-serif;
    }}
    .css-10trblm {{
        font-size: 3.5rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 2rem;
        color: white;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.6);
    }}
    .stMetric {{
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['accent']});
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        border-left: 6px solid {COLORS['primary']};
        color: white;
    }}
    .stMetric div {{
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }}
    .stMetric label {{
        font-size: 1.2rem !important;
        color: white !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
        padding: 8px;
        background: linear-gradient(135deg, {COLORS['black']}, {COLORS['secondary']});
        border-radius: 14px;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 50px;
        padding: 0 24px;
        border-radius: 10px;
        background: {COLORS['secondary']};
        box-shadow: 0 3px 6px rgba(0,0,0,0.3);
        font-weight: 600;
        color: {COLORS['grey']};
        transition: all 0.3s ease;
    }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['accent']});
        color: white;
        box-shadow: 0 6px 12px rgba(76,132,255,0.5);
    }}
    .plotly-graph-div {{
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
        border: 1px solid {COLORS['secondary']};
        padding: 10px;
    }}
    [data-testid="stSidebar"] {{
        background: linear-gradient(135deg, {COLORS['black']}, {COLORS['secondary']});
        padding: 24px;
        box-shadow: 3px 0 20px rgba(0,0,0,0.3);
    }}
    .stButton button {{
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['accent']});
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 1rem;
        font-weight: bold;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }}
    .stButton button:hover {{
        background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['primary']});
        box-shadow: 0 6px 12px rgba(0,0,0,0.4);
    }}
</style>
""", unsafe_allow_html=True)

# Veritabanı bağlantısı
def get_db_connection():
    # Bağlantı parametrelerini kontrol et
    db_params = {
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT"),
        "cursor_factory": RealDictCursor
    }
    missing = [k for k, v in db_params.items() if not v and k != "cursor_factory"]
    if missing:
        st.error(f"🔴 Veritabanı bağlantı parametreleri eksik: {', '.join(missing)}. Lütfen .env dosyanızı kontrol edin.")
        return None
    try:
        conn = psycopg2.connect(**db_params)
        return conn
    except Exception as e:
        st.error(f"🔴 Veritabanı bağlantısı kurulamadı: {str(e)}")
        return None

def get_available_months():
    conn = get_db_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT DATE_TRUNC('month', analyzed_at) as month FROM job_analysis ORDER BY month DESC""")
            return [row['month'] for row in cur.fetchall()]
    except Exception as e:
        st.error(f"🔴 Ay bilgileri alınırken hata: {str(e)}")
        return []
    finally:
        conn.close()

def get_monthly_analysis(selected_month):
    conn = get_db_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    sector, 
                    work_type, 
                    location, 
                    COALESCE(hard_skills::text, '[]') as hard_skills,
                    COALESCE(soft_skills::text, '[]') as soft_skills,
                    COALESCE(responsibilities::text, '[]') as responsibilities,
                    analyzed_at 
                FROM job_analysis 
                WHERE DATE_TRUNC('month', analyzed_at) = %s
            """, (selected_month,))
            return cur.fetchall()
    except Exception as e:
        st.error(f"🔴 Aylık analiz verileri alınırken hata: {str(e)}")
        return []
    finally:
        conn.close()

def get_skill_distribution(month, skill_type):
    conn = get_db_connection()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT skill, COUNT(*) as count
                FROM (
                    SELECT jsonb_array_elements_text(
                        CASE 
                            WHEN jsonb_typeof({skill_type}) = 'array' THEN {skill_type}
                            ELSE jsonb_build_array({skill_type})
                        END
                    ) as skill
                    FROM job_analysis
                    WHERE DATE_TRUNC('month', analyzed_at) = %s
                    AND {skill_type} IS NOT NULL
                ) subq
                GROUP BY skill
                ORDER BY count DESC
                LIMIT 15
            """, (month,))
            return cur.fetchall()
    except Exception as e:
        st.error(f"🔴 {skill_type} becerileri alınırken hata: {str(e)}")
        return []
    finally:
        conn.close()

def get_top_sectors(month):
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sector, COUNT(*) as job_count
                FROM job_analysis
                WHERE DATE_TRUNC('month', analyzed_at) = %s
                GROUP BY sector
                ORDER BY job_count DESC
                LIMIT 5
            """, (month,))
            return cur.fetchall()
    except Exception as e:
        st.error(f"🔴 Sektör bilgileri alınırken hata: {str(e)}")
        return []
    finally:
        conn.close()

def get_title_distribution(month):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            # TODO: Implement query for title distribution
            return []
    except Exception as e:
        st.error(f"🔴 Başlık dağılımı alınırken hata: {str(e)}")
        return None
    finally:
        conn.close()

# JSON verilerini güvenli şekilde parse etme fonksiyonu
def safe_json_parse(x):
    import json
    if x is None or x == "" or x == "[]" or x == "{}":
        return []
    try:
        return json.loads(x)
    except json.JSONDecodeError:
        return []

# Clean and preprocess the DataFrame to avoid pyarrow conversion issues
def preprocess_dataframe(df):
    for column in df.columns:
        if df[column].dtype == 'object':
            # Replace None or NaN with empty strings for object columns
            df[column] = df[column].fillna('')
        elif pd.api.types.is_numeric_dtype(df[column]):
            # Replace NaN with 0 for numeric columns
            df[column] = df[column].fillna(0)
        elif pd.api.types.is_datetime64_any_dtype(df[column]):
            # Ensure datetime columns are properly formatted
            df[column] = pd.to_datetime(df[column], errors='coerce')
    
    # Ensure list-like columns contain only lists
    list_like_columns = ['hard_skills', 'soft_skills', 'responsibilities']
    for column in list_like_columns:
        if column in df.columns:
            df[column] = df[column].apply(lambda x: x if isinstance(x, list) else [])
    
    return df

# Sidebar navigation
page = st.sidebar.radio(
    "Sayfa Seçimi",
    options=["Analiz Paneli", "Zaman Serisi Analizi", "Meslek Verisi Toplama"]
)

# Enhanced pie chart with unified design and larger size
def create_pie_chart(data, names, values, title):
    fig = px.pie(
        data,
        names=names,
        values=values,
        hole=0.3,  # Reduced hole size for a unified look
        color_discrete_sequence=px.colors.sequential.Blues_r,
        template='plotly_dark'
    )
    fig.update_traces(
        textposition='inside',
        textinfo='percent+label',
        textfont=dict(size=18, color='white'),  # Increased text size
        marker=dict(line=dict(color=COLORS['black'], width=1.5)),
        rotation=90  # Adjust rotation for better label placement
    )
    fig.update_layout(
        title={
            'text': title,
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': {'size': 24, 'color': 'white'}  # Larger title font
        },
        height=700,  # Increased height for larger display
        margin=dict(t=80, b=30, l=30, r=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(size=16)  # Larger legend font
        ),
        paper_bgcolor="#1B1B2F",  # Subtle dark blue background
        plot_bgcolor="#1B1B2F"  # Matches paper background
    )
    return fig

# Enhanced bar chart with consistent size and modern styling
def create_bar_chart(data, x, y, title, color_scale):
    fig = px.bar(
        data,
        x=x,
        y=y,
        orientation='h',
        color=x,
        color_continuous_scale=color_scale,
        template='plotly_dark',
        text=x
    )
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>Frekans: %{x}",
        marker_line_color=COLORS['black'],
        marker_line_width=1.5,
        texttemplate='%{text}',
        textposition='outside',
        textfont=dict(size=14, color='white')  # Larger text for bar labels
    )
    fig.update_layout(
        title={
            'text': title,
            'y': 0.95,
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top',
            'font': {'size': 22, 'color': 'white'}
        },
        height=600,  # Consistent height for all bar charts
        margin=dict(t=80, b=30, l=30, r=30),
        xaxis=dict(
            title="Frekans",
            title_font=dict(size=16, color='white'),
            tickfont=dict(size=14, color='white')
        ),
        yaxis=dict(
            title="",
            tickfont=dict(size=14, color='white'),
            categoryorder='total ascending'
        ),
        hoverlabel=dict(
            bgcolor=COLORS['black'],
            font_size=14,
            font_family="Arial"
        ),
        coloraxis_showscale=False,
        paper_bgcolor=COLORS['secondary'],
        plot_bgcolor=COLORS['secondary']
    )
    return fig

if page == "Analiz Paneli":
    # Main analysis panel
    st.title("📊 İş İlanı Analiz Paneli")

    with st.sidebar:
        st.header("🔍 Filtreler")
        available_months = get_available_months()
        if not available_months:
            st.warning("Analiz edilmiş veri bulunamadı.")
            st.stop()
        selected_month = st.selectbox(
            "📅 Ay Seçin",
            options=available_months,
            format_func=lambda x: x.strftime("%B %Y")
        )

    analysis_data = get_monthly_analysis(selected_month)
    if not analysis_data:
        st.warning("Seçilen ay için veri bulunamadı.")
        st.stop()

    df = pd.DataFrame(analysis_data)
    df['sector'] = df['sector'].fillna('BİLİNMİYOR')
    df['work_type'] = df['work_type'].fillna('BİLİNMİYOR')
    df['location'] = df['location'].fillna('BİLİNMİYOR')

    # Verileri güvenli şekilde normalize et
    if 'hard_skills' in df.columns:
        df['hard_skills'] = df['hard_skills'].apply(safe_json_parse)

    if 'soft_skills' in df.columns:
        df['soft_skills'] = df['soft_skills'].apply(safe_json_parse)

    if 'responsibilities' in df.columns:
        df['responsibilities'] = df['responsibilities'].apply(safe_json_parse)

    # Apply preprocessing to the DataFrame
    df = preprocess_dataframe(df)

    # Hata ayıklama için problemli satırları kontrol et
    problematic_rows = []
    for idx, row in df.iterrows():
        try:
            pass  # TODO: Implement logic
        except Exception:
            problematic_rows.append(idx)

    if problematic_rows:
        st.warning(f"⚠️ {len(problematic_rows)} satırda geçersiz JSON verisi tespit edildi ve boş listeye çevrildi")

    with st.sidebar:
        selected_sector = st.multiselect("Sektör Filtresi", options=df['sector'].unique(), default=[])
        work_type_filter = st.multiselect("Çalışma Tipi", options=df['work_type'].unique(), default=[])
        location_filter = st.multiselect("Şehir Filtresi", options=df['location'].unique(), default=[])

    if selected_sector: df = df[df['sector'].isin(selected_sector)]
    if work_type_filter: df = df[df['work_type'].isin(work_type_filter)]
    if location_filter: df = df[df['location'].isin(location_filter)]

    top_sectors = get_top_sectors(selected_month)

    st.header(f"📈 {selected_month.strftime('%B %Y')} Ayı Analiz Sonuçları")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Toplam İlan", len(df))
    col2.metric("🏭 Sektör Sayısı", df['sector'].nunique())
    col3.metric("🔄 Çalışma Tipi (Moda)", df['work_type'].mode()[0] if not df.empty else "-")
    col4.metric("📍 En Çok İlan Şehri", df['location'].mode()[0] if not df.empty else "-")

    st.subheader("🏆 En Çok İlan Veren Sektörler")
    cols = st.columns(len(top_sectors))
    for idx, (col, sector) in enumerate(zip(cols, top_sectors)):
        col.metric(
            label=f"{idx+1}. {sector['sector']}",
            value=f"{sector['job_count']} ilan"
        )

    tab1 = st.tabs(["🔬 Analiz Paneli"])[0]

    with tab1:
        st.markdown("### 📌 Sektör Dağılımı")
        if not df.empty:
            sector_dist = df['sector'].value_counts().reset_index()
            sector_dist.columns = ['sector', 'sector_count']
            st.plotly_chart(create_pie_chart(sector_dist, 'sector', 'sector_count', "Sektör Dağılımı"), use_container_width=True)
        else:
            st.warning("Sektör verisi bulunamadı.")

        st.markdown("### 🎯 Pozisyon Başlıkları")
        title_distribution = get_title_distribution(selected_month)
        if title_distribution:
            title_df = pd.DataFrame(title_distribution).sort_values(by='count', ascending=False)
            st.plotly_chart(create_bar_chart(title_df, 'count', 'title', "En Çok Geçen Pozisyon Başlıkları", px.colors.sequential.Purples), use_container_width=True)
        else:
            st.warning("Pozisyon başlığı verisi bulunamadı.")

        st.markdown("### 📍 Şehir Dağılımı")
        if not df.empty:
            loc_dist = df['location'].value_counts().reset_index()
            loc_dist.columns = ['location', 'location_count']
            st.plotly_chart(create_bar_chart(loc_dist, 'location_count', 'location', "Şehir Dağılımı", px.colors.sequential.Viridis), use_container_width=True)
        else:
            st.warning("Şehir verisi bulunamadı.")

        st.markdown("### 💻 Teknik Beceriler")
        hard_skills = get_skill_distribution(selected_month, 'hard_skills')
        if hard_skills:
            hard_skills_df = pd.DataFrame(hard_skills).sort_values(by='count', ascending=False)
            st.plotly_chart(create_bar_chart(hard_skills_df, 'count', 'skill', "En Çok Geçen Teknik Beceriler", px.colors.sequential.Blues), use_container_width=True)
        else:
            st.warning("Teknik beceri verisi bulunamadı.")

        st.markdown("### 🧠 Kişisel Beceriler")
        soft_skills = get_skill_distribution(selected_month, 'soft_skills')
        if soft_skills:
            soft_skills_df = pd.DataFrame(soft_skills).sort_values(by='count', ascending=False)
            st.plotly_chart(create_bar_chart(soft_skills_df, 'count', 'skill', "En Çok Geçen Kişisel Beceriler", px.colors.sequential.Greens), use_container_width=True)
        else:
            st.warning("Kişisel beceri verisi bulunamadı.")

        st.markdown("### 📋 Sorumluluklar")
        responsibilities = get_skill_distribution(selected_month, 'responsibilities')
        if responsibilities:
            responsibilities_df = pd.DataFrame(responsibilities).sort_values(by='count', ascending=False)
            st.plotly_chart(create_bar_chart(responsibilities_df, 'count', 'skill', "En Çok Geçen Sorumluluklar", px.colors.sequential.Oranges), use_container_width=True)
        else:
            st.warning("Sorumluluk verisi bulunamadı.")

    with st.expander("📂 Ham Veriyi Görüntüle"):
        st.dataframe(
            df,
            hide_index=True,
            use_container_width=True
        )

    st.divider()
    st.markdown(f"""
    <div style="text-align: center; color: {COLORS['grey']}; font-size: 0.9rem; margin-top: 30px;">
        <p>İş İlanı Analiz Paneli • Veriler düzenli olarak güncellenmektedir</p>
        <p>© 2025 İş Analiz Platformu • Tüm hakları saklıdır</p>
    </div>
    """, unsafe_allow_html=True)

elif page == "Zaman Serisi Analizi":
    st.title("📈 Zaman Serisi Analizi")
    st.markdown("Aylık iş ilanı verilerinin zaman içindeki değişimini, teknik/kisisel beceri trendlerini ve diğer önemli metrikleri analiz edin.")

    # --- Yardımcı Fonksiyonlar ---
    def flatten_skills(skills_list):
        """Düzleştirilmiş beceri listesi döndürür"""
        if not skills_list or not isinstance(skills_list, list):
            return []
        
        flat_skills = []
        for item in skills_list:
            if isinstance(item, list):
                flat_skills.extend([s for s in item if isinstance(s, str) and s.strip()])
            elif isinstance(item, str) and item.strip():
                flat_skills.append(item.strip())
        return flat_skills

    def get_time_series_data():
        """Veritabanından zaman serisi verilerini çeker"""
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()
            
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        DATE_TRUNC('month', analyzed_at) as month,
                        COUNT(job_id) as total_jobs,
                        ARRAY_REMOVE(ARRAY_AGG(DISTINCT NULLIF(sector, '')), NULL) as sectors,
                        ARRAY_REMOVE(ARRAY_AGG(DISTINCT NULLIF(work_type, '')), NULL) as work_types,
                        ARRAY_REMOVE(ARRAY_AGG(DISTINCT NULLIF(location, '')), NULL) as locations,
                        ARRAY_AGG(CASE WHEN hard_skills IS NOT NULL THEN hard_skills END) as hard_skills,
                        ARRAY_AGG(CASE WHEN soft_skills IS NOT NULL THEN soft_skills END) as soft_skills,
                        ARRAY_AGG(CASE WHEN salary_range IS NOT NULL AND salary_range != '' THEN salary_range END) as salary_ranges
                    FROM job_analysis
                    WHERE analyzed_at IS NOT NULL
                    GROUP BY month
                    ORDER BY month
                """)
                rows = cur.fetchall()
                return pd.DataFrame(rows) if rows else pd.DataFrame()
                
        except Exception as e:
            st.error(f"🔴 Zaman serisi verisi alınamadı: {str(e)}")
            return pd.DataFrame()
        finally:
            conn.close()

    def process_time_series_data(df):
        """Ham zaman serisi verilerini işler"""
        if df.empty:
            return df
            
        df = df.copy()
        aylar = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 
                'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
        
        # Tarih işlemleri
        df['month'] = pd.to_datetime(df['month']).dt.to_period('M').dt.to_timestamp()
        df['year'] = df['month'].dt.year
        df['ay_label'] = df['month'].apply(lambda dt: f"{aylar[dt.month-1]} {dt.year}")
        
        # Eksik değerleri doldur
        for col in ['sectors', 'work_types', 'locations', 'hard_skills', 'soft_skills', 'salary_ranges']:
            df[col] = df[col].apply(lambda x: x if isinstance(x, list) else [])
        
        # Sayısal alanları doldur
        df['total_jobs'] = df['total_jobs'].fillna(0).astype(int)
        
        return df

# --- Ana İşlem Akışı ---
if page == "Zaman Serisi Analizi":
    st.title("📈 Zaman Serisi Analizi")
    st.markdown("İş ilanlarının zaman içindeki değişimini analiz edin.")
    
    # Verileri yükle
    df_ts = get_time_series_data()
    
    if df_ts.empty:
        st.warning("Zaman serisi verisi bulunamadı. Lütfen veritabanında veri olduğundan emin olun.")
        st.stop()
    
    # Verileri işle
    df_ts = process_time_series_data(df_ts)
    
    # Yıl seçimi
    available_years = sorted(df_ts['year'].unique(), reverse=True)
    selected_year = st.sidebar.selectbox(
        "Yıl Seçiniz", 
        options=available_years, 
        index=0,
        key='year_selector'
    )
    
    # Seçilen yıla göre filtrele
    df_ts_year = df_ts[df_ts['year'] == selected_year].copy()
    
    # Eksik ayları tamamla
    all_months = pd.date_range(
        start=f"{selected_year}-01-01", 
        end=f"{selected_year}-12-31", 
        freq='MS'
    )
    
    df_full = pd.DataFrame({'month': all_months})
    df_full['year'] = selected_year
    df_ts_full = pd.merge(df_full, df_ts_year, on=['month', 'year'], how='left')
    
    # Eksik değerleri doldur
    df_ts_full['total_jobs'] = df_ts_full['total_jobs'].fillna(0).astype(int)
    df_ts_full['ay_label'] = df_ts_full['month'].dt.strftime('%B %Y')

    # --- Maaşları normalize et ---
    def parse_salary(s):
        if not s or not isinstance(s, str):
            return None
        s = s.replace(",", ".")
        s = re.sub(r"(\d+)\s*[Kk]", lambda m: str(int(m.group(1)) * 1000), s)
        found = re.findall(r"(\d+(?:\.\d+)?)", s)
        nums = [float(x) for x in found]
        if len(nums) == 2:
            return sum(nums) / 2
        elif len(nums) == 1:
            return nums[0]
        else:
            return None

    def extract_salary(salary_list):
        if not isinstance(salary_list, list):
            return None
        numbers = []
        for s in salary_list:
            if isinstance(s, list):
                for sub in s:
                    val = parse_salary(sub)
                    if val is not None:
                        numbers.append(val)
            else:
                val = parse_salary(s)
                if val is not None:
                    numbers.append(val)
        if numbers:
            return sum(numbers)/len(numbers)
        else:
            return None

    # Maaş verilerini işle
    if 'salary_ranges' in df_ts_full.columns:
        df_ts_full['avg_salary'] = df_ts_full['salary_ranges'].apply(extract_salary)

    # --- Timeline bar modern ve gerçekçi şekilde göster ---
    st.markdown("""
    <style>
    .timeline-wrap {
        display: flex;
        align-items: flex-end;
        gap: 18px;
        margin: 18px 0 30px 0;
        overflow-x: auto;
        padding-bottom: 16px;
    }
    .timeline-bar {
        width: 54px;
        min-width: 54px;
        background: linear-gradient(180deg, #4C84FF 60%, #8E44AD 100%);
        border-radius: 14px 14px 7px 7px;
        position: relative;
        transition: box-shadow 0.2s;
        box-shadow: 0 2px 8px rgba(76,132,255,0.10);
        cursor: pointer;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: center;
        margin-bottom: 0;
        min-height: 120px;
    }
    .timeline-bar.empty {
        background: repeating-linear-gradient(135deg, #222 0 8px, #333 8px 16px);
        opacity: 0.4;
        border: 1.5px dashed #888;
    }
    .timeline-bar .bar-label {
        text-align: center;
        font-size: 1.05rem;
        color: #B0B0B0;
        margin-top: 7px;
        font-weight: 600;
        min-height: 20px;
        letter-spacing: 0.5px;
        margin-bottom: 2px;
    }
    .timeline-bar .bar-value {
        color: white;
        font-size: 1.15rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 2px;
        margin-top: 2px;
        text-shadow: 0 2px 8px #0008;
        min-height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .timeline-bar .bar-salary {
        color: #FFD700;
        font-size: 0.98rem;
        font-weight: 600;
        text-align: center;
        margin-bottom: 2px;
        text-shadow: 0 2px 8px #0008;
        min-height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .timeline-bar.selected {
        box-shadow: 0 0 0 3px #FFD700, 0 4px 16px rgba(76,132,255,0.18);
        border: 2.5px solid #FFD700;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("#### Aylık İlan ve Maaş Zaman Çizgisi")
    max_jobs = df_ts_full['total_jobs'].max() if not df_ts_full['total_jobs'].isna().all() else 1
    timeline_html = "<div class='timeline-wrap'>"
    for idx, row in df_ts_full.iterrows():
        # Her bar için min yükseklik 120px, veri varsa orantılı büyüt
        if pd.isna(row['total_jobs']):
            bar_height = 120
        else:
            bar_height = 120 + int(100 * row['total_jobs']/max_jobs)
        bar_class = 'timeline-bar'
        if pd.isna(row['total_jobs']):
            bar_class += ' empty'
        if idx == len(df_ts_full)-1 and not pd.isna(row['total_jobs']):
            bar_class += ' selected'
        value_str = f"{int(row['total_jobs'])}" if not pd.isna(row['total_jobs']) else "-"
        salary_str = f"<div class='bar-salary'>{int(row['avg_salary'])}₺</div>" if not pd.isna(row['avg_salary']) else "<div class='bar-salary'>-</div>"
        timeline_html += f"""
        <div class='{bar_class}' style='height:{bar_height}px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;'>
            <div class='bar-value'>{value_str}</div>
            {salary_str}
            <div class='bar-label'>{row['ay_label']}</div>
        </div>
        """
    timeline_html += "</div>"
    st.markdown(timeline_html, unsafe_allow_html=True)

    # --- Teknik ve kişisel beceri trendleri ---
    st.markdown("### 📊 Teknik ve Kişisel Beceri Trendleri")
    
    # Beceri verilerini işle
    skill_data = []
    for idx, row in df_ts_full.iterrows():
        month_label = row['ay_label']
        
        # Hard skills işleme
        hard_skills = flatten_skills(row['hard_skills']) if 'hard_skills' in row and row['hard_skills'] is not None else []
        for skill in set(hard_skills):
            skill_data.append({
                'Beceri': skill,
                'Tür': 'Teknik',
                'Ay': month_label,
                'Sayı': hard_skills.count(skill),
                'Ay Sırası': idx
            })
        
        # Soft skills işleme
        soft_skills = flatten_skills(row['soft_skills']) if 'soft_skills' in row and row['soft_skills'] is not None else []
        for skill in set(soft_skills):
            skill_data.append({
                'Beceri': skill,
                'Tür': 'Kişisel',
                'Ay': month_label,
                'Sayı': soft_skills.count(skill),
                'Ay Sırası': idx
            })
    
    if skill_data:
        df_skills = pd.DataFrame(skill_data)
        
        # En popüler becerileri göster
        st.markdown("#### 🏆 En Popüler Beceriler")
        
        # Filtreleme seçenekleri
        col1, col2 = st.columns(2)
        with col1:
            skill_type = st.radio(
                "Beceri Türü",
                ['Tümü', 'Teknik', 'Kişisel'],
                horizontal=True
            )
        with col2:
            top_n = st.slider("Gösterilecek Beceri Sayısı", 5, 20, 10)
        
        # Filtreleme uygula
        if skill_type != 'Tümü':
            df_filtered = df_skills[df_skills['Tür'] == skill_type]
        else:
            df_filtered = df_skills
        
        # En çok geçen becerileri bul
        top_skills = df_filtered.groupby('Beceri')['Sayı'].sum().nlargest(top_n).index.tolist()
        df_top_skills = df_skills[df_skills['Beceri'].isin(top_skills)]
        
        # Çubuk grafik ile gösterim
        if not df_top_skills.empty:
            fig_skills = px.bar(
                df_top_skills.groupby(['Beceri', 'Tür'])['Sayı'].sum().reset_index().sort_values('Sayı', ascending=True),
                x='Sayı',
                y='Beceri',
                color='Tür',
                orientation='h',
                title=f'En Çok Aranan {top_n} Beceri',
                color_discrete_map={'Teknik': '#4C84FF', 'Kişisel': '#8E44AD'}
            )
            
            fig_skills.update_layout(
                height=500,
                xaxis_title='Toplam Geçiş Sayısı',
                yaxis_title='Beceriler',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                legend_title_text='Beceri Türü',
                margin=dict(l=50, r=50, t=80, b=50),
                yaxis=dict(autorange='reversed')
            )
            
            st.plotly_chart(fig_skills, use_container_width=True)
        
        # Zaman içinde beceri trendleri
        st.markdown("#### 📈 Zaman İçinde Beceri Trendleri")
        
        # Kullanıcıdan beceri seçimi al
        skill_options = df_skills['Beceri'].unique().tolist()
        selected_skills = st.multiselect(
            'Beceri seçin (en fazla 5)',
            options=skill_options,
            default=skill_options[:min(3, len(skill_options))],
            max_selections=5
        )
        
        if selected_skills:
            filtered_skills = df_skills[df_skills['Beceri'].isin(selected_skills)]
            if not filtered_skills.empty:
                # Sıralı görüntüleme için ay sırasını kullan
                month_order = {month: idx for idx, month in enumerate(df_ts_full['ay_label'])}
                filtered_skills['Sıra'] = filtered_skills['Ay'].map(month_order)
                filtered_skills = filtered_skills.sort_values('Sıra')
                
                fig_trend = px.line(
                    filtered_skills.groupby(['Ay', 'Beceri', 'Tür'])['Sayı'].sum().reset_index(),
                    x='Ay',
                    y='Sayı',
                    color='Beceri',
                    line_dash='Tür',
                    title='Seçilen Becerilerin Zaman İçindeki Değişimi',
                    markers=True,
                    line_shape='spline',
                    color_discrete_sequence=px.colors.qualitative.Plotly
                )
                
                fig_trend.update_layout(
                    xaxis_title='Dönem',
                    yaxis_title='Geçiş Sayısı',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'),
                    legend_title_text='Beceri ve Türü',
                    margin=dict(l=50, r=50, t=80, b=50),
                    hovermode='x unified',
                    xaxis=dict(
                        type='category',
                        categoryorder='array',
                        categoryarray=df_ts_full['ay_label'].tolist()
                    )
                )
                
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.warning("Seçilen beceriler için veri bulunamadı.")
        else:
            st.info("Lütfen analiz etmek için en az bir beceri seçin.")
    else:
        st.warning("Beceri verisi bulunamadı.")

    # --- Sektör ve Şehir Trendleri ---
    st.markdown("### 🌍 Sektör ve Şehir Trendleri")
    
    # Sektör ve şehir verilerini işle
    sector_data = []
    city_data = []
    
    for idx, row in df_ts_full.iterrows():
        month_label = row['ay_label']
        
        # Sektör verilerini işle
        sectors = row.get('sectors')
        if isinstance(sectors, (list, tuple)):
            for sector in set(sectors):
                if pd.notna(sector) and isinstance(sector, (str, int, float)):
                    sector_data.append({
                        'Sektör': str(sector),
                        'Ay': month_label,
                        'Sayı': sectors.count(sector),
                        'Ay Sırası': idx
                    })
        elif pd.notna(sectors) and isinstance(sectors, (str, int, float)):
            sector_data.append({
                'Sektör': str(sectors),
                'Ay': month_label,
                'Sayı': 1,
                'Ay Sırası': idx
            })
        
        # Şehir verilerini işle
        locations = row['locations'] if 'locations' in row and row['locations'] is not None else []
        for location in set(locations):
            city_data.append({
                'Şehir': location,
                'Ay': month_label,
                'Sayı': locations.count(location),
                'Ay Sırası': idx
            })
    # Sektör analizi
    st.markdown("#### 🏢 Sektör Analizi")
    
    if sector_data:
        df_sectors = pd.DataFrame(sector_data)
        
        # En popüler sektörler
        top_sectors = df_sectors.groupby('Sektör')['Sayı'].sum().nlargest(10).index.tolist()
        df_top_sectors = df_sectors[df_sectors['Sektör'].isin(top_sectors)]
        
        # Sektör dağılımı
        if not df_top_sectors.empty:
            # Çubuk grafik ile sektör dağılımı
            fig_sectors = px.bar(
                df_top_sectors.groupby('Sektör')['Sayı'].sum().reset_index().sort_values('Sayı', ascending=True),
                x='Sayı',
                y='Sektör',
                orientation='h',
                title='En Çok İlan Veren Sektörler',
                color='Sektör',
                color_discrete_sequence=px.colors.sequential.Plasma
            )
            
            fig_sectors.update_layout(
                height=500,
                xaxis_title='Toplam İlan Sayısı',
                yaxis_title='',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                showlegend=False,
                margin=dict(l=50, r=50, t=80, b=50),
                yaxis=dict(autorange='reversed')
            )
            
            st.plotly_chart(fig_sectors, use_container_width=True)
            
            # Zaman içinde sektör trendleri
            st.markdown("#### 📊 Zaman İçinde Sektör Trendleri")
            
            # Kullanıcıdan sektör seçimi al
            sector_options = df_sectors['Sektör'].unique().tolist()
            selected_sectors = st.multiselect(
                'Sektör seçin (en fazla 5)',
                options=sector_options,
                default=sector_options[:min(3, len(sector_options))],
                max_selections=5,
                key='sector_selector'
            )
            
            if selected_sectors:
                filtered_sectors = df_sectors[df_sectors['Sektör'].isin(selected_sectors)]
                if not filtered_sectors.empty:
                    # Sıralı görüntüleme için ay sırasını kullan
                    month_order = {month: idx for idx, month in enumerate(df_ts_full['ay_label'])}
                    filtered_sectors['Sıra'] = filtered_sectors['Ay'].map(month_order)
                    filtered_sectors = filtered_sectors.sort_values('Sıra')
                    
                    fig_sector_trend = px.line(
                        filtered_sectors.groupby(['Ay', 'Sektör'])['Sayı'].sum().reset_index(),
                        x='Ay',
                        y='Sayı',
                        color='Sektör',
                        title='Seçilen Sektörlerin Zaman İçindeki Değişimi',
                        markers=True,
                        line_shape='spline'
                    )
                    
                    fig_sector_trend.update_layout(
                        xaxis_title='Dönem',
                        yaxis_title='İlan Sayısı',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        legend_title_text='Sektörler',
                        margin=dict(l=50, r=50, t=80, b=50),
                        hovermode='x unified',
                        xaxis=dict(
                            type='category',
                            categoryorder='array',
                            categoryarray=df_ts_full['ay_label'].tolist()
                        )
                    )
                    
                    st.plotly_chart(fig_sector_trend, use_container_width=True)
                else:
                    st.warning("Seçilen sektörler için veri bulunamadı.")
            else:
                st.info("Lütfen analiz etmek için en az bir sektör seçin.")
    else:
        st.warning("Sektör verisi bulunamadı.")
    
    # Şehir analizi
    st.markdown("### 🏙️ Şehir Analizi")
    
    if city_data:
        df_cities = pd.DataFrame(city_data)
        
        # En popüler şehirler
        top_cities = df_cities.groupby('Şehir')['Sayı'].sum().nlargest(10).index.tolist()
        df_top_cities = df_cities[df_cities['Şehir'].isin(top_cities)]
        
        # Şehir dağılımı
        if not df_top_cities.empty:
            # Çubuk grafik ile şehir dağılımı
            fig_cities = px.bar(
                df_top_cities.groupby('Şehir')['Sayı'].sum().reset_index().sort_values('Sayı', ascending=True),
                x='Sayı',
                y='Şehir',
                orientation='h',
                title='En Çok İlan Veren Şehirler',
                color='Şehir',
                color_discrete_sequence=px.colors.sequential.Viridis
            )
            
            fig_cities.update_layout(
                height=500,
                xaxis_title='Toplam İlan Sayısı',
                yaxis_title='',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                showlegend=False,
                margin=dict(l=50, r=50, t=80, b=50),
                yaxis=dict(autorange='reversed')
            )
            
            st.plotly_chart(fig_cities, use_container_width=True)
            
            # Zaman içinde şehir trendleri
            st.markdown("#### 📊 Zaman İçinde Şehir Trendleri")
            
            # Kullanıcıdan şehir seçimi al
            city_options = df_cities['Şehir'].unique().tolist()
            selected_cities = st.multiselect(
                'Şehir seçin (en fazla 5)',
                options=city_options,
                default=city_options[:min(3, len(city_options))],
                max_selections=5,
                key='city_selector'
            )
            
            if selected_cities:
                filtered_cities = df_cities[df_cities['Şehir'].isin(selected_cities)]
                if not filtered_cities.empty:
                    # Sıralı görüntüleme için ay sırasını kullan
                    month_order = {month: idx for idx, month in enumerate(df_ts_full['ay_label'])}
                    filtered_cities['Sıra'] = filtered_cities['Ay'].map(month_order)
                    filtered_cities = filtered_cities.sort_values('Sıra')
                    
                    fig_city_trend = px.line(
                        filtered_cities.groupby(['Ay', 'Şehir'])['Sayı'].sum().reset_index(),
                        x='Ay',
                        y='Sayı',
                        color='Şehir',
                        title='Seçilen Şehirlerin Zaman İçindeki Değişimi',
                        markers=True,
                        line_shape='spline'
                    )
                    
                    fig_city_trend.update_layout(
                        xaxis_title='Dönem',
                        yaxis_title='İlan Sayısı',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        legend_title_text='Şehirler',
                        margin=dict(l=50, r=50, t=80, b=50),
                        hovermode='x unified',
                        xaxis=dict(
                            type='category',
                            categoryorder='array',
                            categoryarray=df_ts_full['ay_label'].tolist()
                        )
                    )
                    
                    st.plotly_chart(fig_city_trend, use_container_width=True)
                else:
                    st.warning("Seçilen şehirler için veri bulunamadı.")
            else:
                st.info("Lütfen analiz etmek için en az bir şehir seçin.")
    else:
        st.warning("Şehir verisi bulunamadı.")

    # --- Aylık Değişim Göstergeleri ---
    st.markdown("### 📊 Aylık İlan ve Maaş Zaman Çizgisi")
    
    try:
        if not df_ts_full.empty and 'month' in df_ts_full.columns and 'total_jobs' in df_ts_full.columns and 'avg_salary' in df_ts_full.columns:
            # Verileri işle
            df_ts = df_ts_full.copy()
            df_ts['month'] = pd.to_datetime(df_ts['month'])
            df_ts = df_ts.sort_values('month')
            
            # Aylık değişimleri hesapla
            df_ts['jobs_change'] = df_ts['total_jobs'].pct_change() * 100
            df_ts['salary_change'] = df_ts['avg_salary'].pct_change() * 100
            
            # Son aya ait değerler
            last_month = df_ts.iloc[-1] if not df_ts.empty else None
            
            if last_month is not None:
                # Metrik kartları oluştur
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        label="Toplam İlan",
                        value=f"{int(last_month['total_jobs']):,}" if pd.notna(last_month['total_jobs']) else "N/A"
                    )
                
                with col2:
                    st.metric(
                        label="Ortalama Maaş",
                        value=f"{int(last_month['avg_salary']):,}₺" if pd.notna(last_month['avg_salary']) else "N/A"
                    )
                
                with col3:
                    st.metric(
                        label="Aylık İlan Değişimi",
                        value=f"{df_ts['jobs_change'].iloc[-1]:.1f}%" if not df_ts.empty and not pd.isna(df_ts['jobs_change'].iloc[-1]) else "N/A",
                        delta=f"{df_ts['jobs_change'].iloc[-1]:.1f}%" if not df_ts.empty and not pd.isna(df_ts['jobs_change'].iloc[-1]) else None
                    )
                
                with col4:
                    st.metric(
                        label="Aylık Maaş Değişimi",
                        value=f"{df_ts['salary_change'].iloc[-1]:.1f}%" if not df_ts.empty and not pd.isna(df_ts['salary_change'].iloc[-1]) else "N/A",
                        delta=f"{df_ts['salary_change'].iloc[-1]:.1f}%" if not df_ts.empty and not pd.isna(df_ts['salary_change'].iloc[-1]) else None
                    )
                
                # Grafik oluştur
                try:
                    fig = go.Figure()
                    
                    # İlan sayıları için çubuk grafik
                    fig.add_trace(
                        go.Bar(
                            x=df_ts['month'],
                            y=df_ts['total_jobs'],
                            name='İlan Sayısı',
                            marker_color=COLORS['primary'],
                            opacity=0.8,
                            yaxis='y',
                            offsetgroup=1
                        )
                    )
                    
                    # Maaşlar için çizgi grafik (ikincil eksen)
                    fig.add_trace(
                        go.Scatter(
                            x=df_ts['month'],
                            y=df_ts['avg_salary'],
                            name='Ortalama Maaş (₺)',
                            line=dict(color=COLORS['accent'], width=3),
                            yaxis='y2',
                            mode='lines+markers',
                            marker=dict(size=8, line=dict(width=1, color=COLORS['accent']))
                        )
                    )
                    
                    # Düzenlemeler
                    fig.update_layout(
                        title='Aylık İlan ve Maaş Değişimleri',
                        xaxis=dict(
                            title='',
                            showgrid=False,
                            tickformat='%b %Y',
                            tickangle=45
                        ),
                        yaxis=dict(
                            title='İlan Sayısı',
                            showgrid=True,
                            gridcolor='rgba(255,255,255,0.1)',
                            zeroline=False
                        ),
                        yaxis2=dict(
                            title='Ortalama Maaş (₺)',
                            overlaying='y',
                            side='right',
                            showgrid=False,
                            zeroline=False
                        ),
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        legend=dict(
                            orientation='h',
                            yanchor='bottom',
                            y=1.02,
                            xanchor='right',
                            x=1
                        ),
                        margin=dict(l=50, r=50, t=80, b=50)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
                    
                    # Detaylı tablo
                    st.markdown("#### Detaylı Aylık Veriler")
                    
                    # Tablo için sütunları seç ve biçimlendir
                    display_cols = ['month', 'total_jobs', 'avg_salary', 'jobs_change', 'salary_change']
                    display_names = ['Ay', 'Toplam İlan', 'Ortalama Maaş (₺)', 'İlan Değişimi (%)', 'Maaş Değişimi (%)']
                    
                    if all(col in df_ts.columns for col in display_cols):
                        df_display = df_ts[display_cols].copy()
                        df_display.columns = display_names
                        df_display['Ay'] = df_display['Ay'].dt.strftime('%B %Y')
                        
                        # Sayısal sütunları formatla
                        num_cols = ['Toplam İlan', 'Ortalama Maaş (₺)', 'İlan Değişimi (%)', 'Maaş Değişimi (%)']
                        df_display[num_cols] = df_display[num_cols].round(2)
                        
                        # Tabloyu göster
                        st.dataframe(
                            df_display,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'Toplam İlan': st.column_config.NumberColumn(
                                    format="%d"
                                ),
                                'Ortalama Maaş (₺)': st.column_config.NumberColumn(
                                    format="%.2f ₺"
                                ),
                                'İlan Değişimi (%)': st.column_config.NumberColumn(
                                    format="%.2f %%"
                                ),
                                'Maaş Değişimi (%)': st.column_config.NumberColumn(
                                    format="%.2f %%"
                                )
                            }
                        )
                    
                    st.divider()
                    
                except Exception as e:
                    st.error(f"Grafik oluşturulurken bir hata oluştu: {str(e)}")
            
        except Exception as e:
            st.error(f"Veri işlenirken bir hata oluştu: {str(e)}")
            
            with col1:
                st.metric(
                    label="Toplam İlan",
                    value=f"{int(last_month['total_jobs']):,}"
                )
            
            with col2:
                st.metric(
                    label="Ortalama Maaş",
                    value=f"{int(last_month['avg_salary']):,}₺"
                )
            
            with col3:
                job_change = last_month.get('jobs_change', 0)
                job_arrow = '↑' if job_change > 0 else '↓' if job_change < 0 else '→'
                st.metric(
                    label="Aylık İlan Değişimi",
                    value=f"{job_change:+.1f}%",
                    delta=job_arrow
                )
            
            with col4:
                salary_change = last_month.get('salary_change', 0)
                salary_arrow = '↑' if salary_change > 0 else '↓' if salary_change < 0 else '→'
                st.metric(
                    label="Aylık Maaş Değişimi",
                    value=f"{salary_change:+.1f}%",
                    delta=salary_arrow
                )
        
        try:
            # Grafik oluştur
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # İlan sayıları için çubuk grafik
            fig.add_trace(
                go.Bar(
                name="İlan Sayısı",
                x=df_ts['month'].dt.strftime('%b %Y'),
                y=df_ts['total_jobs'],
                marker_color='#4C84FF',
                opacity=0.7,
                hovertemplate='<b>%{x}</b><br>' +
                            'İlan Sayısı: <b>%{y:,}</b><br>' +
                            'Değişim: %{customdata[0]:.1f}%<extra></extra>',
                customdata=df_ts[['jobs_change']],
                text=df_ts['total_jobs'].apply(lambda x: f"{x:,}"),
                textposition='auto'
            ),
            secondary_y=False
        )
        
        # Maaşlar için çizgi grafik
        fig.add_trace(
            go.Scatter(
                name="Ortalama Maaş (₺)",
                x=df_ts['month'].dt.strftime('%b %Y'),
                y=df_ts['avg_salary'],
                mode='lines+markers',
                line=dict(color='#FFD700', width=3),
                marker=dict(size=8, line=dict(width=1, color=COLORS['accent'])),
                hovertemplate='<b>%{x}</b><br>' +
                            'Ortalama Maaş: <b>%{y:,.0f} ₺</b><br>' +
                            'Değişim: %{customdata[0]:.1f}%<extra></extra>',
                customdata=df_ts[['salary_change']],
                yaxis='y2'
            ),
            secondary_y=True
        )
        
        # Grafik düzenlemeleri
        fig.update_layout(
            title='Aylık İlan ve Maaş Değişimleri',
            xaxis=dict(
                title='',
                showgrid=False,
                type='category',
                categoryorder='array',
                categoryarray=df_ts['month'].dt.strftime('%b %Y').tolist()
            ),
            yaxis=dict(
                title='İlan Sayısı',
                showgrid=True,
                gridcolor='rgba(255,255,255,0.1)',
                side='left',
                color='#4C84FF',
                showline=True,
                linewidth=1,
                linecolor='rgba(255,255,255,0.2)'
            ),
            yaxis2=dict(
                title='Ortalama Maaş (₺)',
                showgrid=False,
                side='right',
                overlaying='y',
                color='#FFD700',
                showline=True,
                linewidth=1,
                linecolor='rgba(255,255,255,0.2)'
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            ),
            margin=dict(l=50, r=50, t=80, b=50),
            height=500,
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor='rgba(0,0,0,0.8)',
                font_size=12,
                font_family='Arial, sans-serif'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        
        # Detaylı tablo
        st.markdown("#### Detaylı Aylık Veriler")
        
        # Tablo için veri hazırlama
        df_display = df_ts[['month', 'total_jobs', 'jobs_change', 'avg_salary', 'salary_change']].copy()
        df_display = df_display.rename(columns={
            'month': 'Ay',
            'total_jobs': 'İlan Sayısı',
            'jobs_change': 'İlan Değişim %',
            'avg_salary': 'Ort. Maaş (₺)',
            'salary_change': 'Maaş Değişim %'
        })
        
        # Tarih formatını düzenle
        df_display['Ay'] = df_display['Ay'].dt.strftime('%b %Y')
        
        # Sayısal sütunları formatla
        df_display['İlan Sayısı'] = df_display['İlan Sayısı'].apply(lambda x: f"{int(x):,}")
        df_display['Ort. Maaş (₺)'] = df_display['Ort. Maaş (₺)'].apply(lambda x: f"{int(x):,}")
        df_display['İlan Değişim %'] = df_display['İlan Değişim %'].apply(lambda x: f"{x:+.1f}%" if not pd.isna(x) else "-")
        df_display['Maaş Değişim %'] = df_display['Maaş Değişim %'].apply(lambda x: f"{x:+.1f}%" if not pd.isna(x) else "-")
        
        # Tabloyu göster
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                'Ay': st.column_config.TextColumn('Ay'),
                'İlan Sayısı': st.column_config.TextColumn('İlan Sayısı'),
                'İlan Değişim %': st.column_config.TextColumn('İlan Değişim %'),
                'Ort. Maaş (₺)': st.column_config.TextColumn('Ort. Maaş (₺)'),
                'Maaş Değişim %': st.column_config.TextColumn('Maaş Değişim %')
            }
        )
    # except Exception as e:
    #     st.error(f"Veri işlenirken bir hata oluştu: {str(e)}")

    st.divider()
    st.markdown(f"""
<div style="text-align: center; color: {COLORS['grey']}; font-size: 0.9rem; margin-top: 30px;">
    <p>İş İlanı Analiz Paneli • Veriler düzenli olarak güncellenmektedir</p>
    <p>© 2025 İş Analiz Platformu • Tüm hakları saklıdır</p>
</div>
""", unsafe_allow_html=True)

elif page == "Meslek Verisi Toplama":
    st.title("📚 Meslek Verisi Toplama")
    st.markdown("İş ilanlarından meslek verilerini otomatik olarak toplayın ve analiz edin.")

    with st.form("job_data_form"):
        st.subheader("Yeni Veri Analizi")
        job_description = st.text_area("İş Tanımı", height=300)
        analyze_button = st.button("Analiz Et", type="submit", 
            help="Girilen iş tanımını analiz etmek için tıklayın.")

        if analyze_button:
            if not job_description.strip():
                st.warning("Lütfen analiz edilecek bir iş tanımı girin.")
            else:
                # Basit anahtar kelime tabanlı analiz (örnek)
                keywords = re.findall(r"\b[A-Za-z]+\b", job_description)
                keyword_freq = pd.Series(keywords).value_counts().reset_index()
                keyword_freq.columns = ['keyword', 'count']

                st.markdown("### Anahtar Kelime Analizi Sonuçları")
                st.dataframe(keyword_freq, hide_index=True, use_container_width=True)

                # İlgili meslek başlıklarını öner
                if 'developer' in keywords or 'software' in keywords:
                    st.markdown("#### Önerilen Meslekler")
                    st.write("- Yazılım Geliştirici")
                    st.write("- Kıdemli Yazılım Mühendisi")
                elif 'data' in keywords:
                    st.markdown("#### Önerilen Meslekler")
                    st.write("- Veri Analisti")
                    st.write("- Veri Bilimci")
                else:
                    st.markdown("#### Önerilen Meslekler")
                    st.write("- Genel Başvuru")
                st.success("Analiz tamamlandı!")

    with st.expander("📊 Önceki Analizler"):
        st.markdown("Geçmişte yaptığınız analizleri buradan görüntüleyin.")
        # Geçmiş analiz verilerini göster (örnek veri ile)
        sample_data = {
            "Tarih": ["2025-01-15", "2025-02-20"],
            "İş Tanımı": ["Kıdemli Yazılım Geliştirici arıyoruz.", "Veri Analisti pozisyonu için başvurun."],
            "Anahtar Kelimeler": ["Kıdemli, Yazılım, Geliştirici", "Veri, Analisti"],
            "Önerilen Meslekler": ["Yazılım Geliştirici, Kıdemli Yazılım Mühendisi", "Veri Analisti, Veri Bilimci"]
        }
        sample_df = pd.DataFrame(sample_data)
        st.dataframe(sample_df, hide_index=True, use_container_width=True)

    st.divider()
    st.markdown(f"""
    <div style="text-align: center; color: {COLORS['grey']}; font-size: 0.9rem; margin-top: 30px;">
        <p>İş İlanı Analiz Paneli • Veriler düzenli olarak güncellenmektedir</p>
        <p>© 2025 İş Analiz Platformu • Tüm hakları saklıdır</p>
    </div>
    """, unsafe_allow_html=True)