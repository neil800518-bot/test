from pathlib import Path
import json, io, math
import streamlit as st
import numpy as np
from PIL import Image, ImageOps

BASE = Path(__file__).parent
DATA = BASE / 'data' / 'games.json'
IMG_DIR = BASE / 'data' / 'images'

st.set_page_config(page_title='遊戲圖片辨識搜尋', page_icon='🎮', layout='wide', initial_sidebar_state='expanded')
st.title('🎮 遊戲圖片辨識搜尋')
st.caption('網頁版 MVP｜使用 Excel 遊戲百科建立遊戲圖片資料庫。部署到雲端時，查詢圖片會傳送至該網站主機進行即時比對；本程式不會主動將圖片轉送至第三方辨識 API。')

@st.cache_data
def load_games():
    if not DATA.exists(): return []
    items = json.loads(DATA.read_text(encoding='utf-8'))
    for x in items:
        x['path'] = str(BASE / x['image'])
    return [x for x in items if Path(x['path']).exists()]

games = load_games()

@st.cache_data(show_spinner=False)
def load_pil(path):
    return Image.open(path).convert('RGB')

def phash(image, hash_size=8, highfreq_factor=4):
    # DCT-free perceptual hash: low-frequency image structure via resized grayscale pixels.
    # Lightweight baseline; not as robust as learned visual embeddings.
    img = ImageOps.fit(image.convert('L'), (hash_size*highfreq_factor, hash_size*highfreq_factor))
    arr = np.asarray(img, dtype=np.float32)
    # Resize to a small grid; compare each pixel with the median.
    small = np.asarray(Image.fromarray(arr.astype('uint8')).resize((hash_size, hash_size), Image.Resampling.LANCZOS), dtype=np.float32)
    bits = small > np.median(small)
    return bits.flatten()

def color_hist(image, bins=8):
    arr = np.asarray(ImageOps.fit(image.convert('RGB'), (96, 96)), dtype=np.uint8)
    hist = []
    for ch in range(3):
        h, _ = np.histogram(arr[:,:,ch], bins=bins, range=(0,256), density=False)
        h = h.astype(np.float32); h /= (np.linalg.norm(h) + 1e-8)
        hist.extend(h.tolist())
    return np.asarray(hist, dtype=np.float32)

@st.cache_resource(show_spinner=False)
def load_clip_model():
    try:
        import open_clip, torch
        model, _, preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
        model.eval()
        return model, preprocess, torch
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def clip_embeddings(paths):
    loaded = load_clip_model()
    if loaded is None: return None
    model, preprocess, torch = loaded
    vectors=[]
    with torch.no_grad():
        for path in paths:
            img=load_pil(path)
            tensor=preprocess(img).unsqueeze(0)
            vec=model.encode_image(tensor)
            vec=vec / vec.norm(dim=-1, keepdim=True)
            vectors.append(vec.cpu().numpy()[0])
    return np.asarray(vectors, dtype=np.float32)

if not games:
    st.error('找不到資料庫。請確認 data/games.json 與 data/images/ 存在。')
    st.stop()

with st.sidebar:
    st.subheader('資料庫狀態')
    st.metric('已匯入遊戲圖片', len(games))
    st.caption('資料來源：上傳的 Excel「CG电子」工作表。')
    st.divider()
    st.subheader('辨識模式')
    has_clip = load_clip_model() is not None
    if has_clip:
        mode = st.radio('比對方式', ['AI 視覺模型（CLIP）','快速相似圖比對'], index=0)
        st.caption('CLIP 可比對較大幅度的畫面差異，但首次啟動需下載模型。')
    else:
        mode = st.radio('比對方式', ['快速相似圖比對'], index=0)
        st.caption('目前使用輕量模式，較適合封面／圖示近似比對。若要辨識不同截圖，建議安裝可選的 CLIP 模型。')
    st.divider()
    st.caption('搜尋範圍限於已匯入的遊戲圖片，並非直接搜尋整個網際網路。')

uploaded = st.file_uploader('上傳一張遊戲圖片或截圖', type=['png','jpg','jpeg','webp','bmp'])
col_a, col_b = st.columns([1, 2], gap='large')
with col_a:
    st.subheader('待辨識圖片')
    if uploaded:
        try:
            query_img = Image.open(uploaded).convert('RGB')
            st.image(query_img, use_container_width=True)
        except Exception:
            st.error('無法讀取圖片，請換一個檔案。')
            query_img = None
    else:
        query_img = None
        st.info('請上傳圖片開始搜尋。建議使用清晰的遊戲封面、圖示或遊戲畫面。首次部署建議先使用快速相似圖比對；CLIP AI 模式需另外安裝模型套件，且首次啟動需下載模型權重。')

with col_b:
    st.subheader('搜尋結果')
    top_n = st.slider('顯示結果數量', min_value=3, max_value=min(15, len(games)), value=min(6, len(games)))
    if query_img is not None:
        results=[]
        if mode.startswith('AI 視覺') and has_clip:
            with st.spinner('正在計算 AI 圖片特徵…（首次使用可能需要下載模型）'):
                vectors = clip_embeddings(tuple(g['path'] for g in games))
                loaded = load_clip_model()
                if vectors is not None and loaded:
                    model, preprocess, torch = loaded
                    with torch.no_grad():
                        q = preprocess(query_img).unsqueeze(0)
                        qv = model.encode_image(q); qv = qv / qv.norm(dim=-1, keepdim=True)
                        qv = qv.cpu().numpy()[0]
                    sims = vectors @ qv
                    order = np.argsort(-sims)[:top_n]
                    results = [(games[i], float(sims[i]), 'CLIP 視覺相似度') for i in order]
                else:
                    st.warning('AI 模型載入失敗，改用快速相似圖比對。')
        if not results:
            qh = phash(query_img); qhist = color_hist(query_img)
            scores=[]
            for g in games:
                ref = load_pil(g['path'])
                rh = phash(ref); hist = color_hist(ref)
                hash_sim = 1.0 - float(np.mean(qh != rh))
                hist_sim = float(np.dot(qhist, hist))
                score = 0.75*hash_sim + 0.25*hist_sim
                scores.append((g, score, hash_sim, hist_sim))
            scores.sort(key=lambda x:x[1], reverse=True)
            results=[(g, score, f'快速相似度｜結構 {hs:.0%}、色彩 {cs:.0%}') for g,score,hs,cs in scores[:top_n]]
        if results:
            st.caption('相似度是排序用的分數，不等同於「辨識正確率」。請核對前幾個候選結果。')
            for rank,(g,score,method) in enumerate(results,1):
                with st.container(border=True):
                    c1,c2,c3=st.columns([0.8,2.4,1.1], vertical_alignment='center')
                    with c1: st.image(g['path'], use_container_width=True)
                    with c2:
                        st.markdown(f'**{rank}. {g["name"]}**')
                        st.caption(f'工作表：{g.get("sheet","—")}｜原始儲存格：{g.get("cell","—")}')
                        st.caption(method)
                    with c3:
                        st.metric('排序分數', f'{score:.1%}')
    else:
        st.markdown('上傳後會列出最相似的遊戲圖片。')

st.divider()
st.subheader('瀏覽遊戲資料庫')
search = st.text_input('依遊戲名稱搜尋', placeholder='輸入遊戲名稱，例如：金字塔')
filtered = [g for g in games if search.strip().lower() in g['name'].lower()] if search.strip() else games
st.caption(f'顯示 {len(filtered)} / {len(games)} 筆。資料庫目前來自 Excel「CG电子」工作表的 51 張圖片；可逐步補充其他工作表及每款遊戲的多張參考圖。')
cols = st.columns(4)
for i,g in enumerate(filtered):
    with cols[i%4]:
        st.image(g['path'], use_container_width=True)
        st.markdown(f'**{g["name"]}**')
