import io
import time
import uuid
import hashlib
from datetime import datetime, date
from urllib.parse import quote_plus

import streamlit as st
from PIL import Image
from streamlit_paste_button import paste_image_button

import drive_store
from drive_store import load_db, save_db, get_trip, list_trip_names
from calendar_ui import render_month_calendar


# (표보기 링크 등) query params로 수정 모드 진입 지원
try:
    qp = st.query_params
except Exception:
    qp = {}

_qp_trip = qp.get("trip") if qp else None
_qp_edit = qp.get("edit_id") if qp else None
if isinstance(_qp_trip, list):
    _qp_trip = _qp_trip[0] if _qp_trip else None
if isinstance(_qp_edit, list):
    _qp_edit = _qp_edit[0] if _qp_edit else None

if _qp_trip:
    st.session_state["add_trip_select"] = _qp_trip
    st.session_state["edit_trip_name"] = _qp_trip
if _qp_edit:
    st.session_state["edit_id"] = _qp_edit

# 반복 실행 방지용으로 query params 제거
if _qp_trip or _qp_edit:
    try:
        st.query_params.clear()
    except Exception:
        pass

st.set_page_config(page_title="일정 추가", page_icon="📝", layout="centered")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("📝 일정 추가/수정")

# v3.7: 달력 날짜 클릭 시 jump(YYYY-MM-DD)로 날짜 자동 선택
jump_date_str = st.query_params.get("jump", "")

st.caption("PC: 캡쳐 후 '붙여넣기' 버튼 / 폰: 사진 업로드(여러 장 가능)")

db = load_db(ROOT_FOLDER_ID)
trip_names = list_trip_names(db)

if "draft_images" not in st.session_state:
    st.session_state["draft_images"] = []  # list of (bytes, mime)
if "last_paste_sig" not in st.session_state:
    st.session_state["last_paste_sig"] = None

if "add_cal_ym" not in st.session_state:
    today = date.today()
    st.session_state["add_cal_ym"] = (today.year, today.month)

with st.sidebar:
    st.subheader("여행 선택/생성")
    if st.button("🔄 새로고침", width='stretch'):
        st.rerun()
    new_trip = st.text_input("새 여행 이름", placeholder="예: 2026 오사카")
    if st.button("➕ 여행 만들기", width='stretch', disabled=not new_trip.strip()):
        db["trips"].append({"name": new_trip.strip(), "items": []})
        save_db(ROOT_FOLDER_ID, db)
        st.success("여행 생성 완료")
        st.rerun()

if not trip_names:
    st.info("왼쪽에서 여행을 먼저 만들어줘.")
    st.stop()


# (수정 모드) View에서 넘어올 때 여행을 자동 선택
_edit_trip = st.session_state.get("edit_trip_name")
if _edit_trip and _edit_trip in trip_names:
    st.session_state["add_trip_select"] = _edit_trip

trip_name = st.selectbox("여행", options=trip_names, key="add_trip_select")
trip = get_trip(db, trip_name)
if not trip:
    st.error("여행을 찾을 수 없어. 새로고침 후 다시 시도해줘.")
    st.stop()


# --- Edit mode (v3.12.2) ---
edit_id = st.session_state.get("edit_id")
edit_item = None
if edit_id:
    for _it in (trip.get("items", []) or []):
        if _it.get("id") == edit_id:
            edit_item = _it
            break

if edit_id and not edit_item:
    st.warning("수정할 일정을 찾지 못했어. (이미 삭제되었을 수 있어) 추가 모드로 전환할게.")
    st.session_state.pop("edit_id", None)
    st.session_state.pop("edit_trip_name", None)
    edit_id = None
# ---------------------------
items = trip.get("items", []) or []
events = {}
for it in items:
    d = it.get("date")
    if d:
        events.setdefault(d, []).append({"time": it.get("time",""), "title": it.get("title","")})

y, m = st.session_state["add_cal_ym"]
c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("◀ 이전달", width='stretch'):
        if m == 1:
            y, m = y - 1, 12
        else:
            y, m = y, m - 1
        st.session_state["add_cal_ym"] = (y, m)
        st.rerun()
with c2:
    st.markdown(f"### {y}년 {m}월")
with c3:
    if st.button("다음달 ▶", width='stretch'):
        if m == 12:
            y, m = y + 1, 1
        else:
            y, m = y, m + 1
        st.session_state["add_cal_ym"] = (y, m)
        st.rerun()

try:
    render_month_calendar(events, y, m, title="📅 이 여행 일정 달력", link_base_params={"trip": trip_name})
except TypeError:
    # 구버전 calendar_ui.py 호환(키워드 인자 미지원)
    render_month_calendar(events, y, m, title="📅 이 여행 일정 달력")


st.divider()

colA, colB = st.columns([1, 1])
with colA:
    _default_date = datetime.now().date()
    if edit_item and edit_item.get("date"):
        try:
            _default_date = datetime.strptime(edit_item["date"], "%Y-%m-%d").date()
        except Exception:
            pass
    date_str = st.date_input("날짜", value=_default_date).strftime("%Y-%m-%d")
with colB:
    _default_time = (edit_item.get("time") if edit_item else "") or ""
    time_str = st.text_input("시간(선택)", value=_default_time, placeholder="예: 14:30 / 오후 2시")

_default_title = (edit_item.get("title") if edit_item else "") or ""
title = st.text_input("제목", value=_default_title, placeholder="예: 공항 이동 / 맛집 / 관광지")

_default_memo = (edit_item.get("memo") if edit_item else "") or ""
memo = st.text_area("메모", value=_default_memo, height=120, placeholder="메모(선택)")

_default_map = (edit_item.get("map_text") if edit_item else "") or (edit_item.get("map_url") if edit_item else "") or ""
map_input = st.text_input("구글맵 링크 또는 주소(선택)", value=_default_map, placeholder="예: https://maps.app.goo.gl/... 또는 서울역")
map_text = map_input.strip()
map_url = ""
if map_text:
    if map_text.lower().startswith("http"):
        map_url = map_text
    else:
        map_url = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(map_text)

st.divider()
st.subheader("사진 추가(여러 장)")

# (수정 모드) 기존 사진 표시/삭제 선택
existing_ids = (edit_item.get("image_file_ids") if edit_item else []) or []
delete_ids = set()
if edit_item and existing_ids:
    st.caption("기존 사진(삭제할 사진을 체크)")
    cols_prev = st.columns(3)
    for i, fid in enumerate(existing_ids):
        b = drive_store.cached_image_bytes(fid)
        col = cols_prev[i % 3]
        if b:
            col.image(b, width='stretch')
        if col.checkbox("삭제", key=f"del_img_{fid}"):
            delete_ids.add(fid)
    st.divider()


pasted_or_uploaded_now = False

paste_result = paste_image_button("📋 클립보드 이미지 붙여넣기(누적)")
if paste_result is not None and getattr(paste_result, "image_data", None) is not None:
    img = paste_result.image_data
    raw = None
    mime = "image/png"
    if isinstance(img, Image.Image):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        raw = buf.getvalue()
    elif isinstance(img, (bytes, bytearray)):
        raw = bytes(img)

    if raw:
        sig = hashlib.sha1(raw).hexdigest()
        if sig != st.session_state["last_paste_sig"]:
            st.session_state["draft_images"].append((raw, mime))
            st.session_state["last_paste_sig"] = sig
            pasted_or_uploaded_now = True
        else:
            st.info("같은 이미지가 반복 감지되어 추가하지 않았어(중복 방지).")

uploaded_files = st.file_uploader(
    "📷 사진 업로드(여러 장 가능)",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
)
if uploaded_files:
    for uf in uploaded_files:
        st.session_state["draft_images"].append((uf.getvalue(), uf.type or "image/png"))
    pasted_or_uploaded_now = True

# 핵심: 추가 직후 rerun → 같은 화면에서 미리보기 즉시 노출
if pasted_or_uploaded_now:
    st.rerun()

if st.session_state["draft_images"]:
    st.caption(f"현재 추가된 이미지: {len(st.session_state['draft_images'])}장")
    cols = st.columns(3)
    for i, (b, _) in enumerate(st.session_state["draft_images"][:9]):
        cols[i % 3].image(b, width='stretch')
    if st.button("🧹 이미지 선택 전부 비우기", width='stretch'):
        st.session_state["draft_images"] = []
        st.session_state["last_paste_sig"] = None
        st.rerun()
else:
    st.caption("아직 추가된 이미지가 없어. 붙여넣기 또는 업로드 해줘.")

st.divider()

can_save = bool(title.strip())

# 모바일에서도 버튼이 한 줄로 보이도록(짧은 라벨 + columns)
btn1, btn2 = st.columns([1, 1], gap="small")

if edit_item:
    if btn1.button("💾 수정 저장", type="primary", width='stretch', disabled=not can_save):
        service = drive_store._drive_service()
        images_folder_id = drive_store.ensure_subfolder(service, ROOT_FOLDER_ID, drive_store.IMAGES_FOLDER_NAME)

        kept_ids = [fid for fid in (edit_item.get("image_file_ids") or []) if fid not in delete_ids]

        new_ids = []
        for (img_bytes, mime) in st.session_state["draft_images"]:
            ts = int(time.time() * 1000)
            ext = "png" if (mime or "").lower().endswith("png") else "jpg"
            safe_trip = trip_name.replace(" ", "_")
            filename = f"{safe_trip}_{date_str}_{ts}_{uuid.uuid4().hex[:6]}.{ext}"
            fid = drive_store.upload_image_bytes(service, images_folder_id, filename, img_bytes, mime or "image/png")
            new_ids.append(fid)

        edit_item.update({
            "date": date_str,
            "time": time_str.strip(),
            "title": title.strip(),
            "memo": memo.strip(),
            "map_text": map_text,
            "map_url": map_url,
            "image_file_ids": kept_ids + new_ids,
            "ts": int(time.time()),
        })

        def _sort_key(x):
            t = x.get("time") or ""
            return (x.get("date") or "", t, x.get("ts") or 0)
        trip["items"] = sorted(trip.get("items", []) or [], key=_sort_key)

        save_db(ROOT_FOLDER_ID, db)

        st.session_state["draft_images"] = []
        st.session_state["last_paste_sig"] = None
        st.session_state.pop("edit_id", None)
        st.session_state.pop("edit_trip_name", None)

        st.success("수정되었습니다. 일정 보기로 이동합니다…")
        try:
            st.switch_page("pages/2_View_Schedule.py")
        except Exception:
            st.info("왼쪽 메뉴에서 '일정 보기'로 이동해줘.")

    if btn2.button("➕ 추가 모드", width='stretch'):
        st.session_state.pop("edit_id", None)
        st.session_state.pop("edit_trip_name", None)
        st.session_state["draft_images"] = []
        st.session_state["last_paste_sig"] = None
        st.rerun()

else:
    if btn1.button("✅ 저장", type="primary", width='stretch', disabled=not can_save):
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
        st.session_state["last_paste_sig"] = None

        st.success("저장되었습니다. 일정 보기로 이동합니다…")
        try:
            st.switch_page("pages/2_View_Schedule.py")
        except Exception:
            st.info("왼쪽 메뉴에서 '일정 보기'로 이동해줘.")

    if btn2.button("📅 일정 보기", width='stretch'):
        try:
            st.switch_page("pages/2_View_Schedule.py")
        except Exception:
            pass