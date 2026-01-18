import io
import time
from datetime import datetime

import streamlit as st
from PIL import Image

from streamlit_paste_button import paste_image_button

import drive_store
from drive_store import load_db, save_db, get_trip, list_trip_names, upload_image_bytes


st.set_page_config(page_title="일정 추가", page_icon="📝", layout="centered")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("📝 일정 추가")
st.caption("PC: 캡쳐 후 '붙여넣기 버튼' / 폰: 사진 업로드")

db = load_db(ROOT_FOLDER_ID)
trip_names = list_trip_names(db)

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

colA, colB = st.columns([1, 1])
with colA:
    date_str = st.date_input("날짜", value=datetime.now().date()).strftime("%Y-%m-%d")
with colB:
    time_str = st.text_input("시간(선택)", placeholder="예: 14:30 / 오후 2시")

title = st.text_input("제목", placeholder="예: 공항 이동 / 맛집 / 관광지")
memo = st.text_area("메모", height=140, placeholder="주소/링크/메모")

st.divider()
st.subheader("사진 추가")

paste_result = paste_image_button("📋 클립보드 이미지 붙여넣기")
uploaded = st.file_uploader("📷 사진 업로드", type=["png", "jpg", "jpeg", "webp"])

img_bytes = None
mime = None

if paste_result is not None and getattr(paste_result, "image_data", None) is not None:
    img = paste_result.image_data
    if isinstance(img, Image.Image):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        mime = "image/png"
        st.image(img, caption="붙여넣은 이미지", use_container_width=True)
    elif isinstance(img, (bytes, bytearray)):
        img_bytes = bytes(img)
        mime = "image/png"
        st.image(img_bytes, caption="붙여넣은 이미지", use_container_width=True)
    else:
        st.warning("붙여넣기 이미지 형식을 처리하지 못했어. 업로드로 시도해줘.")

elif uploaded is not None:
    img_bytes = uploaded.getvalue()
    mime = uploaded.type or "image/png"
    st.image(img_bytes, caption="업로드 이미지", use_container_width=True)

st.divider()

can_save = bool(title.strip())
if st.button("✅ 저장", type="primary", use_container_width=True, disabled=not can_save):
    service = drive_store._drive_service()
    images_folder_id = drive_store.ensure_subfolder(service, ROOT_FOLDER_ID, drive_store.IMAGES_FOLDER_NAME)

    image_file_id = None
    if img_bytes:
        ts = int(time.time())
        ext = "png" if (mime or "").lower().endswith("png") else "jpg"
        safe_trip = trip_name.replace(" ", "_")
        filename = f"{safe_trip}_{date_str}_{ts}.{ext}"
        image_file_id = upload_image_bytes(service, images_folder_id, filename, img_bytes, mime or "image/png")

    item = {
        "date": date_str,
        "time": time_str.strip(),
        "title": title.strip(),
        "memo": memo.strip(),
        "image_file_id": image_file_id,
        "ts": int(time.time()),
    }

    trip["items"].append(item)

    def _sort_key(x):
        t = x.get("time") or ""
        return (x.get("date") or "", t, x.get("ts") or 0)

    trip["items"] = sorted(trip["items"], key=_sort_key)

    save_db(ROOT_FOLDER_ID, db)
    st.success("저장 완료!")
    st.rerun()

st.caption("팁) PC: 캡쳐(Ctrl+C) → 위 버튼 클릭 → 저장")
