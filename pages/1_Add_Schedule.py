import io
import time
import uuid
from datetime import datetime, date
from urllib.parse import quote_plus

import streamlit as st
from PIL import Image
from streamlit_paste_button import paste_image_button

import drive_store
from drive_store import load_db, save_db, get_trip, list_trip_names
from calendar_ui import render_month_calendar

st.set_page_config(page_title="일정 추가", page_icon="📝", layout="centered")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("📝 일정 추가")
st.caption("PC: 캡쳐 후 '붙여넣기' 버튼 / 폰: 사진 업로드(여러 장 가능)")

db = load_db(ROOT_FOLDER_ID)
trip_names = list_trip_names(db)

if "draft_images" not in st.session_state:
    st.session_state["draft_images"] = []  # list of (bytes, mime)

with st.sidebar:
    st.subheader("여행 선택/생성")
    if st.button("🔄 새로고침", use_container_width=True):
        st.rerun()
    new_trip = st.text_input("새 여행 이름", placeholder="예: 2026 오사카")
    if st.button("➕ 여행 만들기", use_container_width=True, disabled=not new_trip.strip()):
        db["trips"].append({"name": new_trip.strip(), "items": []})
        save_db(ROOT_FOLDER_ID, db)
        st.success("여행 생성 완료")
        st.rerun()

if not trip_names:
    st.info("왼쪽에서 여행을 먼저 만들어줘.")
    st.stop()

trip_name = st.selectbox("여행", options=trip_names)
trip = get_trip(db, trip_name)
if not trip:
    st.error("여행을 찾을 수 없어. 새로고침 후 다시 시도해줘.")
    st.stop()

# Calendar: month picker + month view
items = trip.get("items", []) or []
events = {}
for it in items:
    d = it.get("date")
    if d:
        events.setdefault(d, []).append({"time": it.get("time",""), "title": it.get("title","")})

cal_month = st.date_input("달력 월 선택", value=date.today(), help="이 달의 일정이 한 번에 보여요.")
render_month_calendar(events, cal_month.year, cal_month.month, title="📅 이 여행 일정 달력")

st.divider()

colA, colB = st.columns([1, 1])
with colA:
    date_str = st.date_input("날짜", value=datetime.now().date()).strftime("%Y-%m-%d")
with colB:
    time_str = st.text_input("시간(선택)", placeholder="예: 14:30 / 오후 2시")

title = st.text_input("제목", placeholder="예: 공항 이동 / 맛집 / 관광지")
memo = st.text_area("메모", height=120, placeholder="메모(선택)")

map_input = st.text_input("구글맵 링크 또는 주소(선택)", placeholder="예: https://maps.app.goo.gl/... 또는 서울역")
map_text = map_input.strip()
map_url = ""
if map_text:
    if map_text.lower().startswith("http"):
        map_url = map_text
    else:
        map_url = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(map_text)

st.divider()
st.subheader("사진 추가(여러 장)")

paste_result = paste_image_button("📋 클립보드 이미지 붙여넣기(누적)")
if paste_result is not None and getattr(paste_result, "image_data", None) is not None:
    img = paste_result.image_data
    if isinstance(img, Image.Image):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        st.session_state["draft_images"].append((buf.getvalue(), "image/png"))
        st.success("붙여넣기 이미지 1장 추가됨(저장 전).")
    elif isinstance(img, (bytes, bytearray)):
        st.session_state["draft_images"].append((bytes(img), "image/png"))
        st.success("붙여넣기 이미지 1장 추가됨(저장 전).")

uploaded_files = st.file_uploader(
    "📷 사진 업로드(여러 장 가능)",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
)
if uploaded_files:
    for uf in uploaded_files:
        st.session_state["draft_images"].append((uf.getvalue(), uf.type or "image/png"))
    st.success(f"업로드 이미지 {len(uploaded_files)}장 추가됨(저장 전).")

if st.session_state["draft_images"]:
    st.caption(f"현재 추가된 이미지: {len(st.session_state['draft_images'])}장")
    cols = st.columns(3)
    for i, (b, _) in enumerate(st.session_state["draft_images"][:9]):
        cols[i % 3].image(b, use_container_width=True)
    if st.button("🧹 이미지 선택 전부 비우기", use_container_width=True):
        st.session_state["draft_images"] = []
        st.rerun()

st.divider()

can_save = bool(title.strip())
if st.button("✅ 저장", type="primary", use_container_width=True, disabled=not can_save):
    service = drive_store._drive_service()
    images_folder_id = drive_store.ensure_subfolder(service, ROOT_FOLDER_ID, drive_store.IMAGES_FOLDER_NAME)

    image_file_ids = []
    for (img_bytes, mime) in st.session_state["draft_images"]:
        ts = int(time.time() * 1000)
        ext = "png" if (mime or "").lower().endswith("png") else "jpg"
        safe_trip = trip_name.replace(" ", "_")
        filename = f"{safe_trip}_{date_str}_{ts}_{uuid.uuid4().hex[:6]}.{ext}"
        fid = drive_store.upload_image_bytes(service, images_folder_id, filename, img_bytes, mime or "image/png")
        image_file_ids.append(fid)

    item = {
        "id": uuid.uuid4().hex,
        "date": date_str,
        "time": time_str.strip(),
        "title": title.strip(),
        "memo": memo.strip(),
        "map_text": map_text,
        "map_url": map_url,
        "image_file_ids": image_file_ids,
        "ts": int(time.time()),
    }
    trip["items"].append(item)

    def _sort_key(x):
        t = x.get("time") or ""
        return (x.get("date") or "", t, x.get("ts") or 0)
    trip["items"] = sorted(trip["items"], key=_sort_key)

    save_db(ROOT_FOLDER_ID, db)
    st.session_state["draft_images"] = []
    st.success("저장 완료!")
    st.rerun()
