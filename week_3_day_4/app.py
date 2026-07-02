import os
import base64
import csv
import numpy as np
import streamlit as st

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
HERE = os.path.dirname(os.path.abspath(__file__))   # файлы рядом с app.py, не зависит от cwd

# красивое фото Казахстана (альпийское озеро в горах) для шапки — Unsplash, свободная лицензия
HERO_PHOTO = "https://images.unsplash.com/photo-1530480667809-b655d4dc3aaa?w=1600&q=80"

st.set_page_config(page_title="Qazaq Book Advisor", page_icon="📖", layout="centered")

# ----- локализация: тексты интерфейса на 3 языках -----
TR = {
    "kk": {
        "title": "Қазақ кітап кеңесшісі",
        "subtitle": "Мағынасы бойынша ұқсас кітаптарды табады",
        "tab_book": "🔗 Ұқсас кітап",
        "tab_interest": "🔎 Қызығушылық бойынша",
        "pick": "Кітапты таңдаңыз",
        "count": "Қанша кітап көрсету",
        "similar_to": "ұқсас кітаптар",
        "interest_help": "Нені оқығыңыз келетінін сипаттаңыз — кез келген тілде.",
        "interest_label": "Қызығушылығыңыз",
        "interest_default": "көшпенділер мен хандар туралы тарихи роман",
        "matches": "сәйкес кітаптар",
        "author": "Авторы",
    },
    "ru": {
        "title": "Советник казахских книг",
        "subtitle": "Находит похожие по смыслу книги",
        "tab_book": "🔗 Похожая книга",
        "tab_interest": "🔎 По интересам",
        "pick": "Выберите книгу",
        "count": "Сколько книг показать",
        "similar_to": "похожие книги",
        "interest_help": "Опишите, что хотите почитать — на любом языке.",
        "interest_label": "Ваши интересы",
        "interest_default": "исторический роман про кочевников и ханов",
        "matches": "подходящие книги",
        "author": "Автор",
    },
    "en": {
        "title": "Kazakh Book Advisor",
        "subtitle": "Finds books similar in meaning",
        "tab_book": "🔗 Similar book",
        "tab_interest": "🔎 By interest",
        "pick": "Choose a book",
        "count": "How many books to show",
        "similar_to": "similar books",
        "interest_help": "Describe what you'd like to read — in any language.",
        "interest_label": "Your interests",
        "interest_default": "a historical novel about nomads and khans",
        "matches": "matching books",
        "author": "Author",
    },
}
LANGS = {"Қазақша": "kk", "Русский": "ru", "English": "en"}

# ----- казахский орнамент (ою-өрнек) как SVG-полоса: золото на бирюзе -----
ORNAMENT_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' width='72' height='30' viewBox='0 0 72 30'>
  <rect width='72' height='30' fill='#26A5C4'/>
  <g fill='none' stroke='#F4C542' stroke-width='2.4'>
    <path d='M2 15 q9 -13 18 0 q9 13 18 0 q9 -13 18 0 q9 13 18 0'/>
    <path d='M11 15 q5 -7 10 0 M47 15 q5 -7 10 0'/>
  </g>
  <g fill='#F4C542'>
    <circle cx='11' cy='9' r='1.6'/><circle cx='29' cy='21' r='1.6'/>
    <circle cx='47' cy='9' r='1.6'/><circle cx='65' cy='21' r='1.6'/>
  </g>
</svg>
"""
ORN_URI = "data:image/svg+xml;base64," + base64.b64encode(ORNAMENT_SVG.encode()).decode()

# ----- национальный фон: повторяющийся ою-өрнек (қошқар мүйіз + ромб) -----
BG_SVG = """
<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160' viewBox='0 0 160 160'>
  <rect width='160' height='160' fill='#FBF6EA'/>
  <g fill='none' stroke='#26A5C4' stroke-width='3' opacity='0.14'>
    <path d='M80 20 L120 80 L80 140 L40 80 Z'/>
    <path d='M80 44 L100 80 L80 116 L60 80 Z'/>
    <path d='M40 80 q-18 -18 0 -36 M40 80 q-18 18 0 36'/>
    <path d='M120 80 q18 -18 0 -36 M120 80 q18 18 0 36'/>
  </g>
  <g fill='none' stroke='#C8912A' stroke-width='3' opacity='0.16'>
    <path d='M80 0 q-16 16 0 32 q16 -16 0 -32 M80 160 q-16 -16 0 -32 q16 16 0 32'/>
    <path d='M0 80 q16 -16 32 0 q-16 16 -32 0 M160 80 q-16 -16 -32 0 q16 16 32 0'/>
    <circle cx='80' cy='80' r='4'/>
  </g>
</svg>
"""
BG_URI = "data:image/svg+xml;base64," + base64.b64encode(BG_SVG.encode()).decode()

# ----- 4 загруженных казахских орнамента (assets/ornament_1..4.png) -----
def _img_uri(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

ORN_IMGS = [_img_uri(os.path.join(HERE, "assets", f"ornament_{i}.png")) for i in range(1, 5)]

# фоновый казахский ковёр (фон.webp)
BG_PHOTO_URI = _img_uri(os.path.join(HERE, "assets", "background.webp"))

def ornament_row():
    imgs = "".join(f'<img class="orn-tile" src="{u}"/>' for u in ORN_IMGS)
    st.markdown(f'<div class="orn-row">{imgs}</div>', unsafe_allow_html=True)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Merriweather:wght@400;700&display=swap');
h1, h2, h3, .book-title, .hero h1 {{ font-family:'Playfair Display', Georgia, serif !important; }}
.stApp, .book-desc, .book-author, .query-card, .hero p {{ font-family:'Merriweather', Georgia, serif; }}
.stApp {{
    background-color:#FBF6EA;
    background-image: linear-gradient(rgba(251,246,234,.80), rgba(251,246,234,.80)), url("{BG_PHOTO_URI}");
    background-size: cover; background-position:center; background-attachment:fixed;
}}
.block-container {{ max-width: 820px; }}
.ornament {{
    height: 30px; margin: 6px 0 14px 0; border-radius: 6px;
    background-image: url("{ORN_URI}"); background-repeat: repeat-x; background-size: auto 30px;
    box-shadow: 0 1px 3px rgba(0,0,0,.15);
}}
/* ряд из 4 загруженных орнаментов */
.orn-row {{ display:flex; justify-content:center; gap:16px; margin:12px 0 16px 0; }}
.orn-tile {{ height:60px; width:60px; border-radius:12px; object-fit:cover;
    box-shadow:0 2px 6px rgba(0,0,0,.20); }}
/* кнопки-языки вверху справа */
div[data-testid="stHorizontalBlock"] .stButton button {{ border-radius:20px; font-family:Georgia,serif; }}
/* фото-шапка */
.hero {{
    height:210px; border-radius:16px; margin-bottom:4px;
    background-image: linear-gradient(rgba(14,92,116,.35), rgba(14,92,116,.60)), url("{HERO_PHOTO}");
    background-size:cover; background-position:center;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    box-shadow:0 6px 20px rgba(0,0,0,.28); font-family:Georgia,serif;
}}
.hero h1 {{ color:#fff; margin:.1em 0; font-size:2.3rem; text-shadow:0 2px 8px rgba(0,0,0,.5); }}
.hero p  {{ color:#FCE9BE; margin:.2em 0 0 0; font-style:italic; text-shadow:0 1px 6px rgba(0,0,0,.5); }}
/* карточка книги */
.book-card {{
    position:relative; background:#FFFFFF; border-radius:12px;
    border:1px solid #EADFBF; border-left:6px solid #F4C542;
    padding:14px 84px 14px 18px; margin:12px 0;
    box-shadow:0 2px 8px rgba(14,92,116,.10); font-family:'Merriweather',Georgia,serif;
    transition: transform .18s ease, box-shadow .18s ease, border-left-color .18s ease;
}}
.book-card:hover {{
    transform: translateY(-5px);
    box-shadow:0 12px 26px rgba(14,92,116,.22);
    border-left-color:#26A5C4;
}}
.book-title  {{ font-size:1.12rem; font-weight:700; color:#0E5C74; }}
.book-author {{ font-size:.9rem;  color:#9A7B2E; margin:2px 0 6px 0; }}
.book-desc   {{ font-size:.92rem; color:#4A4A4A; line-height:1.4; }}
.sim-badge {{
    position:absolute; top:14px; right:14px;
    background:linear-gradient(135deg,#26A5C4,#0E5C74); color:#fff;
    font-family:Georgia,serif; font-weight:700; font-size:.82rem;
    padding:5px 10px; border-radius:20px; box-shadow:0 1px 3px rgba(0,0,0,.2);
}}
.query-card {{
    background:#FFFDF6; border:1px dashed #D9C486; border-radius:10px;
    padding:10px 16px; margin:4px 0 10px 0; color:#0E5C74; font-family:Georgia,serif;
}}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load():
    vecs = np.load(os.path.join(HERE, "rec_vectors.npy"))
    names = np.load(os.path.join(HERE, "rec_names.npy"), allow_pickle=True)
    vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)  # единичные векторы
    return vecs, list(names)


@st.cache_data
def load_meta():
    "аннотация из books.csv по названию"
    meta = {}
    with open(os.path.join(HERE, "books.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            meta[r["name"]] = r["description"]
    return meta


@st.cache_resource
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL)


def split_author(name):
    "«Название — Автор» -> (название, автор)"
    for sep in (" — ", " – "):
        if sep in name:
            title, author = name.rsplit(sep, 1)
            return title, author
    return name, ""


def card(name, score, meta, t):
    title, author = split_author(name)
    desc = meta.get(name, "")
    pct = max(0, round(float(score) * 100))
    st.markdown(f"""
    <div class="book-card">
      <div class="sim-badge">{pct}%</div>
      <div class="book-title">{title}</div>
      <div class="book-author">✍️ {t['author']}: {author}</div>
      <div class="book-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def top_k(sims, k, skip=None):
    order = np.argsort(-sims)
    return [j for j in order if j != skip][:k]


vecs, names = load()
meta = load_meta()

# ----- переключатель языка: кнопки вверху справа -----
if "lang" not in st.session_state:
    st.session_state.lang = "kk"
_spacer, b1, b2, b3 = st.columns([5, 1.5, 1.5, 1.5])
for col, (code, label) in zip((b1, b2, b3), [("kk", "Қазақша"), ("ru", "Русский"), ("en", "English")]):
    if col.button(label, key=f"lang_{code}", use_container_width=True,
                  type=("primary" if st.session_state.lang == code else "secondary")):
        st.session_state.lang = code
        st.rerun()
t = TR[st.session_state.lang]

# ----- шапка с фото и орнаментами -----
st.markdown(f"""
<div class="hero">
  <h1>📖 {t['title']}</h1>
  <p>{t['subtitle']}</p>
</div>
""", unsafe_allow_html=True)
ornament_row()

tab1, tab2 = st.tabs([t["tab_book"], t["tab_interest"]])

with tab1:
    pick = st.selectbox(t["pick"], names)
    k = st.slider(t["count"], 1, 10, 3, key="k1")
    i = names.index(pick)
    sims = vecs @ vecs[i]
    st.markdown(f'<div class="query-card">📚 <b>{split_author(pick)[0]}</b> — {t["similar_to"]}:</div>',
                unsafe_allow_html=True)
    for j in top_k(sims, k, skip=i):
        card(names[j], sims[j], meta, t)

with tab2:
    st.write(t["interest_help"])
    query = st.text_input(t["interest_label"], t["interest_default"])
    k = st.slider(t["count"], 1, 10, 3, key="k2")
    if query.strip():
        qv = get_model().encode([query], normalize_embeddings=True)[0]
        sims = vecs @ qv
        st.markdown(f'<div class="query-card">🔎 «{query}» — {t["matches"]}:</div>',
                    unsafe_allow_html=True)
        for j in top_k(sims, k):
            card(names[j], sims[j], meta, t)

ornament_row()
