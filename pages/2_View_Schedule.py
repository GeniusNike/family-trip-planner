import io
import time
import uuid
import hashlib
from datetime import date
from urllib.parse import quote_plus, urlparse, parse_qs, unquote_plus

import streamlit as st

# === INLINE EDIT (View Schedule에서 바로 수정) ===
import io
import time
import uuid
import hashlib
from urllib.parse import quote_plus

from PIL import Image
from streamlit_paste_button import paste_image_button

import drive_store
from drive_store import save_db
from PIL import Image
from streamlit_paste_button import paste_image_button

import drive_store
from drive_store import load_db, save_db, list_trip_names, get_trip, get_image_bytes
from calendar_ui import render_month_calendar
from map_utils import render_day_map
from routing_utils import format_date_with_dow_kr, driving_km_between, compute_day_driving_km

st.set_page_config(page_title="일정 보기", page_icon="👀", layout="wide")

# v3_15: 사진은 일정별로 버튼을 눌렀을 때만 불러옵니다(지연 로딩).
if "photo_open" not in st.session_state:
    st.session_state.photo_open = {}  # item_id -> bool
if "photo_data" not in st.session_state:
    st.session_state.photo_data = {}  # item_id -> list[bytes]


ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

def _find_item_by_id(db: dict, trip_name: str, item_id: str):
    trip = None
    for t in (db.get("trips") or []):
        if t.get("name") == trip_name:
            trip = t
            break
    if not trip:
        return None, None
    for it in (trip.get("items") or []):
        if it.get("id") == item_id:
            return trip, it
    return trip, None


def _make_map_url(map_text: str) -> tuple[str, str]:
    map_text = (map_text or "").strip()
    if not map_text:
        return "", ""
    if map_text.lower().startswith("http"):
        return map_text, map_text
    return map_text, "https://www.google.com/maps/search/?api=1&query=" + quote_plus(map_text)


def _inline_edit_dialog(db: dict, trip_name: str, item: dict):
    """
    수정 다이얼로그: View Schedule 안에서 바로 수정/저장.
    """
    item_id = item.get("id") or ""
    key_prefix = f"inline_edit_{trip_name}_{item_id}_"

    @st.dialog("✏️ 일정 수정", width="large")
    def _dlg():
        st.caption("이 창에서 바로 수정하고 저장할 수 있어요.")

        # 초기값 세팅(1회)
        init_flag = key_prefix + "init"
        if not st.session_state.get(init_flag):
            st.session_state[key_prefix + "date"] = item.get("date") or ""
            st.session_state[key_prefix + "time"] = item.get("time") or ""
            st.session_state[key_prefix + "title"] = item.get("title") or ""
            st.session_state[key_prefix + "memo"] = item.get("memo") or ""
            st.session_state[key_prefix + "map_text"] = item.get("map_text") or (item.get("map_url") or "")
            st.session_state[key_prefix + "draft_images"] = []
            st.session_state[key_prefix + "last_paste_sig"] = None
            st.session_state[init_flag] = True

        # date input
        from datetime import datetime as _dt
        try:
            d0 = _dt.strptime(st.session_state[key_prefix + "date"], "%Y-%m-%d").date()
        except Exception:
            d0 = _dt.now().date()

        c1, c2 = st.columns([1, 1], gap="small")
        new_date = c1.date_input("날짜", value=d0, key=key_prefix + "date_input")
        new_time = c2.text_input("시간", value=st.session_state[key_prefix + "time"], placeholder="예: 09:30", key=key_prefix + "time_input")

        new_title = st.text_input("제목", value=st.session_state[key_prefix + "title"], key=key_prefix + "title_input")
        new_memo = st.text_area("메모", value=st.session_state[key_prefix + "memo"], height=120, key=key_prefix + "memo_input")
        new_map_text = st.text_input("장소/지도 링크", value=st.session_state[key_prefix + "map_text"], placeholder="maps 링크 또는 주소", key=key_prefix + "map_input")

        st.divider()
        st.subheader("사진(삭제/추가)")

        existing_ids = (item.get("image_file_ids") or [])[:]
        delete_ids = set()
        if existing_ids:
            st.caption("기존 사진(삭제할 사진 체크)")
            cols_prev = st.columns(3)
            for i, fid in enumerate(existing_ids):
                b = drive_store.get_image_bytes(fid)
                col = cols_prev[i % 3]
                if b:
                    col.image(b, width='stretch')
                if col.checkbox("삭제", key=key_prefix + f"del_{fid}"):
                    delete_ids.add(fid)

        pasted_or_uploaded_now = False

        paste_result = paste_image_button("📋 클립보드 이미지 붙여넣기(누적)", key=key_prefix + "paste_btn")
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
                if sig != st.session_state[key_prefix + "last_paste_sig"]:
                    st.session_state[key_prefix + "draft_images"].append((raw, mime))
                    st.session_state[key_prefix + "last_paste_sig"] = sig
                    pasted_or_uploaded_now = True
                else:
                    st.info("같은 이미지가 반복 감지되어 추가하지 않았어(중복 방지).")

        uploaded_files = st.file_uploader(
            "📷 사진 업로드(여러 장 가능)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=key_prefix + "uploader",
        )
        if uploaded_files:
            for uf in uploaded_files:
                st.session_state[key_prefix + "draft_images"].append((uf.getvalue(), uf.type or "image/png"))
            pasted_or_uploaded_now = True

        if pasted_or_uploaded_now:
            st.rerun()

        drafts = st.session_state.get(key_prefix + "draft_images") or []
        if drafts:
            st.caption(f"추가될 이미지: {len(drafts)}장")
            cols = st.columns(3)
            for i, (b, _) in enumerate(drafts[:9]):
                cols[i % 3].image(b, width='stretch')
            if st.button("🧹 추가 이미지 비우기", width='stretch', key=key_prefix + "clear_drafts"):
                st.session_state[key_prefix + "draft_images"] = []
                st.session_state[key_prefix + "last_paste_sig"] = None
                st.rerun()

        st.divider()
        b1, b2 = st.columns([1, 1], gap="small")
        if b1.button("💾 수정 저장", type="primary", width='stretch', key=key_prefix + "save_btn", disabled=not bool(new_title.strip())):
            date_str = new_date.strftime("%Y-%m-%d")
            map_text, map_url = _make_map_url(new_map_text)

            service = drive_store._drive_service()
            images_folder_id = drive_store.ensure_subfolder(service, ROOT_FOLDER_ID, drive_store.IMAGES_FOLDER_NAME)

            kept_ids = [fid for fid in existing_ids if fid not in delete_ids]
            new_ids = []
            for (img_bytes, mime) in (st.session_state.get(key_prefix + "draft_images") or []):
                ts = int(time.time() * 1000)
                ext = "png" if (mime or "").lower().endswith("png") else "jpg"
                safe_trip = trip_name.replace(" ", "_")
                filename = f"{safe_trip}_{date_str}_{ts}_{uuid.uuid4().hex[:6]}.{ext}"
                fid = drive_store.upload_image_bytes(service, images_folder_id, filename, img_bytes, mime or "image/png")
                new_ids.append(fid)

            item.update({
                "date": date_str,
                "time": (new_time or "").strip(),
                "title": new_title.strip(),
                "memo": (new_memo or "").strip(),
                "map_text": map_text,
                "map_url": map_url,
                "image_file_ids": kept_ids + new_ids,
                "ts": int(time.time()),
            })

            def _sort_key(x):
                t = x.get("time") or ""
                return (x.get("date") or "", t, x.get("ts") or 0)

            # 재정렬 후 저장
            trip, _ = _find_item_by_id(db, trip_name, item_id)
            if trip:
                trip["items"] = sorted(trip.get("items") or [], key=_sort_key)

            save_db(ROOT_FOLDER_ID, db)

            # 세션 정리
            st.session_state.pop("inline_edit_id", None)
            st.session_state.pop("inline_edit_trip", None)
            for k in list(st.session_state.keys()):
                if k.startswith(key_prefix):
                    st.session_state.pop(k, None)
            st.session_state.pop(init_flag, None)

            st.success("수정 완료! 화면을 새로고침합니다.")
            st.rerun()

        if b2.button("닫기", width='stretch', key=key_prefix + "close_btn"):
            st.session_state.pop("inline_edit_id", None)
            st.session_state.pop("inline_edit_trip", None)
            st.rerun()

    _dlg()

st.title("👀 일정 보기")

db = load_db(ROOT_FOLDER_ID)
trip_names = list_trip_names(db)

# v3.7: 달력에서 날짜 클릭 시 trip/jump를 query param으로 유지
qp_trip = st.query_params.get("trip", "")
qp_jump = st.query_params.get("jump", "")

if not trip_names:
    st.info("아직 여행이 없어. 홈에서 여행을 먼저 만들어줘.")
    st.stop()

default_trip = None
if isinstance(qp_trip, list):
    qp_trip_val = qp_trip[0] if qp_trip else ""
else:
    qp_trip_val = qp_trip
if qp_trip_val and qp_trip_val in trip_names:
    default_trip = qp_trip_val
default_index = trip_names.index(default_trip) if default_trip else 0
trip_name = st.selectbox("여행 선택", options=trip_names, index=default_index, key="view_trip_select")

# (Inline edit) 수정 요청이 있으면 이 페이지에서 바로 다이얼로그로 열기
if st.session_state.get("inline_edit_id") and st.session_state.get("inline_edit_trip"):
    _tname = st.session_state["inline_edit_trip"]
    _iid = st.session_state["inline_edit_id"]
    _trip, _it = _find_item_by_id(db, _tname, _iid)
    if _it:
        _inline_edit_dialog(db, _tname, _it)
    else:
        st.warning("수정할 일정을 찾지 못했어. (여행/일정이 변경되었을 수 있어요)")
        st.session_state.pop("inline_edit_id", None)
        st.session_state.pop("inline_edit_trip", None)
trip = get_trip(db, trip_name)
if not trip:
    st.error("여행을 찾을 수 없어. 새로고침 후 다시 시도해줘.")
    st.stop()

items = trip.get("items", []) or []
if not items:
    st.info("아직 일정이 없어. '일정 추가'에서 추가해줘.")
    st.stop()

if "view_cal_ym" not in st.session_state:
    today = date.today()
    st.session_state["view_cal_ym"] = (today.year, today.month)

# edit state init
if "edit_new_imgs" not in st.session_state:
    st.session_state["edit_new_imgs"] = {}  # item_id -> list[(bytes,mime)]
if "edit_last_sig" not in st.session_state:
    st.session_state["edit_last_sig"] = {}  # item_id -> sig

# Backward compatibility
for idx, it in enumerate(items):
    if "image_file_ids" not in it:
        it["image_file_ids"] = [it["image_file_id"]] if it.get("image_file_id") else []
    if "id" not in it:
        it["id"] = f"legacy_{int(time.time()*1000)}_{idx}"
    if "map_url" not in it:
        it["map_url"] = ""
    if "map_text" not in it:
        mu = (it.get("map_url") or "").strip()
        txt = ""
        if mu:
            try:
                u = urlparse(mu)
                q = parse_qs(u.query).get("query", [""])[0]
                txt = unquote_plus(q) if q else mu
            except Exception:
                txt = mu
        it["map_text"] = txt

with st.sidebar:
    st.subheader("보기 옵션 · v3_15")
    view_mode = st.radio("보기", ["카드", "표", "타임라인"], index=0)
    keyword = st.text_input("키워드(제목/메모)", placeholder="예: 맛집 / 공항 / 호텔")

def _match(it):
    if not keyword.strip():
        return True
    k = keyword.strip().lower()
    blob = f"{it.get('title','')} {it.get('memo','')}".lower()
    return k in blob

grouped = {}
for it in items:
    d = it.get("date", "미정")
    if _match(it):
        grouped.setdefault(d, []).append(it)

dates_sorted = sorted(grouped.keys())
if not dates_sorted:
    st.info("필터 조건에 맞는 일정이 없어.")
    st.stop()

day_map = {d: i + 1 for i, d in enumerate(dates_sorted)}

# Calendar events + month nav
events = {}
for d in dates_sorted:
    for it in grouped[d]:
        events.setdefault(d, []).append({"time": it.get("time",""), "title": it.get("title","")})

y, m = st.session_state["view_cal_ym"]
c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("◀ 이전달", key="view_prev", width='stretch'):
        if m == 1:
            y, m = y - 1, 12
        else:
            y, m = y, m - 1
        st.session_state["view_cal_ym"] = (y, m)
        st.rerun()
with c2:
    st.markdown(f"### {y}년 {m}월")
with c3:
    if st.button("다음달 ▶", key="view_next", width='stretch'):
        if m == 12:
            y, m = y + 1, 1
        else:
            y, m = y, m + 1
        st.session_state["view_cal_ym"] = (y, m)
        st.rerun()

try:
    render_month_calendar(events, y, m, title="📅 일정 달력", link_base_params={"trip": trip_name})
except TypeError:
    # 구버전 calendar_ui.py 호환(키워드 인자 미지원)
    render_month_calendar(events, y, m, title="📅 일정 달력")


st.divider()

# v3.7: 달력에서 날짜 클릭 시 해당 Day 섹션으로 자동 스크롤
jump_val = ''
if isinstance(qp_jump, list):
    jump_val = qp_jump[0] if qp_jump else ''
else:
    jump_val = qp_jump or ''
if jump_val:
    st.components.v1.html(f"""
    <script>
      const targetId = 'day-anchor-' + {jump_val!r};
      // streamlit은 콘텐츠 렌더링이 늦을 수 있어서 약간 기다렸다가 스크롤
      setTimeout(() => {{
        try {{
          const el = window.parent.document.getElementById(targetId);
          if (el) el.scrollIntoView({{behavior:'smooth', block:'start'}});
        }} catch(e) {{}}
      }}, 300);
    </script>
    """, height=0)

if "confirm_delete_id" not in st.session_state:
    st.session_state["confirm_delete_id"] = None

def _maps_search_url(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if text.lower().startswith("http"):
        return text
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(text)

def _day_route_url(day_items: list) -> str:
    stops = []
    for it in day_items:
        mt = (it.get("map_text") or "").strip()
        if mt:
            stops.append(mt)
    if len(stops) < 2:
        return ""
    origin = quote_plus(stops[0])
    destination = quote_plus(stops[-1])
    waypoints = "|".join(quote_plus(s) for s in stops[1:-1])
    url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}"
    if waypoints:
        url += f"&waypoints={waypoints}"
    url += "&travelmode=driving"
    return url

def _delete_item(item_id: str):
    trip["items"] = [x for x in trip.get("items", []) if x.get("id") != item_id]
    save_db(ROOT_FOLDER_ID, db)

def _update_item(item_id: str, patch: dict):
    for x in trip.get("items", []):
        if x.get("id") == item_id:
            x.update(patch)
            break
    def _sort_key(x):
        t = x.get("time") or ""
        return (x.get("date") or "", t, x.get("ts") or 0)
    trip["items"] = sorted(trip.get("items", []), key=_sort_key)
    save_db(ROOT_FOLDER_ID, db)

def _sort_key(x):
    t = x.get("time") or ""
    return (x.get("date") or "", t, x.get("ts") or 0)

for d in dates_sorted:
    grouped[d] = sorted(grouped[d], key=_sort_key)

if view_mode == "표":
    # 표 보기(모바일 가로 스크롤): _id는 표에 표시하지 않고 내부로만 보관
    rows = []
    row_ids = []
    for d in dates_sorted:
        day_items = grouped[d]
        prev_coord = None

        from map_utils import collect_day_points
        pts = collect_day_points(day_items)
        title_to_coord = {title: (lat, lng) for lat, lng, title in pts if title}

        for it in day_items:
            title = (it.get("title") or "").strip()
            coord = title_to_coord.get(title)

            km_from_prev = None
            if prev_coord and coord:
                km_from_prev = driving_km_between(prev_coord, coord)
            if coord:
                prev_coord = coord

            map_url = (it.get("map_url") or "").strip()
            item_id = it.get("id") or ""

            row_ids.append(item_id)
            rows.append({
                "선택": False,
                "Day": f"Day {day_map[d]}",
                "Date": format_date_with_dow_kr(d),
                "Time": it.get("time") or "",
                "Title": title,
                "Drive(km)": "" if km_from_prev is None else round(float(km_from_prev), 1),
                "Map": map_url,
            })

    st.session_state[f"_table_row_ids_{trip_name}"] = row_ids

    st.markdown("📊 **일정 표 보기 (좌우 스크롤 가능)**")
    st.caption("수정: 표에서 한 행을 체크한 뒤, 아래 '선택한 일정 수정' 버튼을 누르세요.")

    edited = st.data_editor(
        rows,
        use_container_width=True,
        hide_index=True,
        key=f"table_editor_{trip_name}",
        column_config={
            "선택": st.column_config.CheckboxColumn("선택", help="수정할 일정 체크", width="small"),
            "Map": st.column_config.LinkColumn("Map", display_text="열기", width="small"),
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Drive(km)": st.column_config.TextColumn("Drive(km)", width="small"),
        },
        disabled=["Day", "Date", "Time", "Title", "Drive(km)", "Map"],
        column_order=["선택", "Day", "Date", "Time", "Title", "Drive(km)", "Map"],
    )

    selected_idx = None
    if isinstance(edited, list):
        for i, r in enumerate(edited):
            if r.get("선택"):
                selected_idx = i
                break

    btn_cols = st.columns([1.4, 1.0, 6], gap="small")
    if btn_cols[0].button("✏️ 선택한 일정 수정", type="primary", use_container_width=True, disabled=(selected_idx is None)):
        ids = st.session_state.get(f"_table_row_ids_{trip_name}", [])
        if 0 <= selected_idx < len(ids):
            st.session_state["edit_trip_name"] = trip_name
            st.session_state["add_trip_select"] = trip_name
            st.session_state["edit_id"] = ids[selected_idx]
            st.switch_page("pages/1_Add_Schedule.py")
        else:
            st.warning("선택한 행의 ID를 찾지 못했어. 새로고침 후 다시 시도해줘.")

    if btn_cols[1].button("✅ 선택 해제", use_container_width=True):
        st.session_state.pop(f"table_editor_{trip_name}", None)
        st.rerun()

    st.stop()

if view_mode == "타임라인":
    circ = "①②③④⑤⑥⑦⑧⑨⑩"
    for d in dates_sorted:
        day_items = grouped[d]
        seg_km, total_km = compute_day_driving_km(day_items)
        st.markdown(f"<div id='day-anchor-{d}'></div>", unsafe_allow_html=True)
        st.subheader(f"Day {day_map[d]} · 📅 {format_date_with_dow_kr(d)}")
        st.caption(f"🚗 예상 운전거리(도로): **{total_km} km** (좌표가 있는 일정 기준)")

        route_url = _day_route_url(day_items)
        if route_url:
            st.link_button("🧭 그날 이동 코스(구글맵)", route_url)
        else:
            st.caption("이동 코스를 만들려면 지도/주소가 2개 이상 필요해.")

        with st.expander("🗺️ 그날 전체 지도(번호 표시) 보기", expanded=False):
            render_day_map(day_items, height=560, map_key=f"daymap_{trip_name}_{d}")

        for idx2, it in enumerate(day_items, start=1):
            t = (it.get("time") or "").strip()
            title = (it.get("title") or "").strip()
            map_url = (it.get("map_url") or "").strip()
            prefix = circ[idx2-1] if idx2 <= len(circ) else f"{idx2}."
            cols = st.columns([1, 6, 2])
            cols[0].markdown(f"### {prefix}")
            cols[1].markdown(f"**{t} {title}**".strip())
            dist = seg_km[idx2-1] if (idx2-1) < len(seg_km) else None
            right_parts = []
            if dist is not None:
                right_parts.append(f"🚗 {round(float(dist),1)}km")
            if map_url:
                right_parts.append(f"[지도]({map_url})")
            if right_parts:
                cols[2].markdown(" · ".join(right_parts))
            memo = (it.get("memo") or "").strip()
            if memo:
                st.write(memo)

        st.divider()
    st.stop()

# Card view
for d in dates_sorted:
    day_items = grouped[d]
    seg_km, total_km = compute_day_driving_km(day_items)

    st.markdown(f"<div id='day-anchor-{d}'></div>", unsafe_allow_html=True)
    st.subheader(f"Day {day_map[d]} · 📅 {format_date_with_dow_kr(d)}")
    st.caption(f"🚗 예상 운전거리(도로): **{total_km} km** (좌표가 있는 일정 기준)")

    route_url = _day_route_url(day_items)
    if route_url:
        st.link_button("🧭 그날 이동 코스(구글맵)", route_url)

    with st.expander("🗺️ 그날 전체 지도(번호 표시) 보기", expanded=False):
        render_day_map(day_items, height=560, map_key=f"daymap_{trip_name}_{d}")

    st.caption("구글맵에서 경유지가 입력된 순서(시간순)대로 잡혀요.")

    for idx, it in enumerate(day_items):
        t = (it.get("time") or "").strip()
        head = f"{('⏰ ' + t + '  |  ') if t else ''}{it.get('title','(제목 없음)')}"

        with st.container(border=True):
            st.markdown(f"**{head}**")

            dist = seg_km[idx] if idx < len(seg_km) else None
            if dist is not None:
                st.caption(f"🚗 이전 일정에서 약 {round(float(dist), 1)} km")

            map_url = (it.get("map_url") or "").strip()
            if map_url:
                st.markdown(f"🗺️ [지도 열기]({map_url})")

            memo = (it.get("memo") or "").strip()
            if memo:
                st.write(memo)

            # photos (lazy-load per item)
            image_ids = it.get("image_file_ids") or []
            if image_ids:
                item_id = it.get("id") or f"{it.get('date','')}_{it.get('time','')}_{it.get('title','')}"
                opened = st.session_state.photo_open.get(item_id, False)
                btn_label = "📷 사진 보기" if not opened else "🙈 사진 숨기기"
                if st.button(btn_label, key=f"photo_btn_{item_id}", width='stretch'):
                    st.session_state.photo_open[item_id] = not opened
                    st.rerun()

                if st.session_state.photo_open.get(item_id, False):
                    # Load only once per session
                    if item_id not in st.session_state.photo_data:
                        with st.spinner("사진 불러오는 중..."):
                            imgs = []
                            for fid in image_ids:
                                b = get_image_bytes(fid)
                                if b:
                                    imgs.append(b)
                            st.session_state.photo_data[item_id] = imgs

                    imgs = st.session_state.photo_data.get(item_id, [])
                    if imgs:
                        st.caption("📷 사진")
                        st.image(imgs, width='stretch')
                    else:
                        st.warning("표시할 사진이 없습니다.")
            # actions (edit/delete) - keep existing helper function if present
            cols = st.columns([1, 1, 6])
            if cols[0].button("✏️ 수정", key=f"edit_{it.get('id','')}", width='stretch'):
                st.session_state["edit_id"] = it.get("id")
                st.session_state["edit_trip_name"] = trip_name
                st.session_state["add_trip_select"] = trip_name
                st.switch_page("pages/1_Add_Schedule.py")
            if cols[1].button("🗑️ 삭제", key=f"del_{it.get('id','')}", width='stretch'):
                st.session_state["delete_id"] = it.get("id")
                st.rerun()

    st.divider()