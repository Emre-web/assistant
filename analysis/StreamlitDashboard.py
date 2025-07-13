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
    options=["Analiz Paneli", "Meslek Verisi Toplama"]
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