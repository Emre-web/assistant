import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

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

# Koyu tema CSS
st.markdown(f"""
<style>
    body {{
        background-color: {COLORS['background']};
        color: {COLORS['grey']};
    }}
    .css-10trblm {{
        font-size: 3rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 2rem;
        color: white;
    }}
    .stMetric {{
        background: {COLORS['secondary']};
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        border-left: 6px solid {COLORS['primary']};
    }}
    .stMetric div {{
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: {COLORS['grey']} !important;
    }}
    .stMetric label {{
        font-size: 1rem !important;
        color: {COLORS['grey']} !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
        padding: 8px;
        background: {COLORS['black']};
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
    }}
    .stTabs [aria-selected="true"] {{
        background: {COLORS['primary']};
        color: white;
        box-shadow: 0 6px 12px rgba(76,132,255,0.5);
    }}
    .plotly-graph-div {{
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
        border: 1px solid {COLORS['secondary']};
    }}
    [data-testid="stSidebar"] {{
        background: {COLORS['black']};
        padding: 24px;
        box-shadow: 3px 0 20px rgba(0,0,0,0.3);
    }}
</style>
""", unsafe_allow_html=True)

# Veritabanı bağlantısı
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            cursor_factory=RealDictCursor
        )
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
            cur.execute("""SELECT sector, work_type, location, hard_skills, soft_skills, responsibilities, analyzed_at FROM job_analysis WHERE DATE_TRUNC('month', analyzed_at) = %s""", (selected_month,))
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
                    SELECT jsonb_array_elements_text({skill_type}) as skill
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
    if not conn: return []
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

# UI Başlık
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
        sector_dist.columns = ['sector', 'sector_count']  # Manuel ve tekil isim ver

        fig = px.pie(
            sector_dist,
            names='sector',
            values='sector_count',
            hole=0.4,
            color_discrete_sequence=[COLORS['primary'], COLORS['accent'], COLORS['grey'], COLORS['black']],
            template='plotly_dark'
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Sektör verisi bulunamadı.")

        # ... (önceki kodlar aynı kalacak, sadece aşağıdaki kısmı tab1 içine ekleyin)

with tab1:
    # ... (önceki görselleştirmeler aynı kalacak)
    
    st.markdown("### 🎯 Pozisyon Başlıkları")
    def get_title_distribution(month):
        conn = get_db_connection()
        if not conn: return []
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT skill as title, COUNT(*) as count
                    FROM (
                        SELECT jsonb_array_elements_text(title_skills) as skill
                        FROM job_analysis
                        WHERE DATE_TRUNC('month', analyzed_at) = %s
                        AND title_skills IS NOT NULL
                        AND jsonb_array_length(title_skills) > 0
                    ) subq
                    GROUP BY skill
                    ORDER BY count DESC
                    LIMIT 15
                """, (month,))
                return cur.fetchall()
        except Exception as e:
            st.error(f"🔴 Pozisyon başlıkları alınırken hata: {str(e)}")
            return []
        finally:
            conn.close()

    title_distribution = get_title_distribution(selected_month)
    if title_distribution:
        title_df = pd.DataFrame(title_distribution)
        fig = px.bar(
            title_df, 
            x='count', 
            y='title',
            orientation='h',
            color='count',
            color_continuous_scale=[COLORS['primary'], COLORS['accent']],
            template='plotly_dark',
            labels={'count': 'İlan Sayısı', 'title': 'Pozisyon'},
            height=500
        )
        fig.update_layout(
            margin=dict(t=30, b=10, l=10, r=10),
            xaxis_title="İlan Sayısı",
            yaxis_title="",
            yaxis={'categoryorder':'total ascending'},
            hoverlabel=dict(
                bgcolor=COLORS['black'],
                font_size=14,
                font_family="Arial"
            ),
            coloraxis_showscale=False
        )
        fig.update_traces(
            hovertemplate="<b>%{y}</b><br>%{x} ilan",
            marker_line_color=COLORS['black'],
            marker_line_width=1.5
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Pozisyon başlığı verisi bulunamadı.")


    st.markdown("### 📍 Şehir Dağılımı")
    if not df.empty:
        loc_dist = df['location'].value_counts().reset_index()
        loc_dist.columns = ['location', 'location_count']  # Sütun isimlerini benzersiz yap
        fig = px.bar(
            loc_dist, x='location', y='location_count',
            color='location',
            color_discrete_sequence=px.colors.sequential.Viridis,
            template='plotly_dark'
        )
        fig.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Şehir verisi bulunamadı.")

    st.markdown("### 💻 Teknik Beceriler")
    hard_skills = get_skill_distribution(selected_month, 'hard_skills')
    if hard_skills:
        hard_skills_df = pd.DataFrame(hard_skills)
        fig = px.bar(
            hard_skills_df, x='count', y='skill',
            orientation='h', color='count',
            color_continuous_scale=[COLORS['accent'], COLORS['primary']],
            template='plotly_dark'
        )
        fig.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Teknik beceri verisi bulunamadı.")

    st.markdown("### 🧠 Kişisel Beceriler")
    soft_skills = get_skill_distribution(selected_month, 'soft_skills')
    if soft_skills:
        soft_skills_df = pd.DataFrame(soft_skills)
        fig = px.bar(
            soft_skills_df, x='count', y='skill',
            orientation='h', color='count',
            color_continuous_scale=[COLORS['primary'], COLORS['accent']],
            template='plotly_dark'
        )
        fig.update_layout(height=450, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Kişisel beceri verisi bulunamadı.")

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
