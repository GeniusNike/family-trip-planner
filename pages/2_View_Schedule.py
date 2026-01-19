import time
from datetime import date
from urllib.parse import quote_plus, urlparse, parse_qs, unquote_plus

import streamlit as st

import drive_store
from drive_store import load_db, save_db, list_trip_names, get_trip, get_image_bytes
from calendar_ui import render_month_calendar

st.set_page_config(page_title="일정 보기", page_icon="👀", layout="wide")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("👀 일정 보기")

db = load_db(ROOT_FOLDER_ID)
trip_names = list_trip_names(db)

if not trip_names:
    st.info("아직 여행이 없어. 홈에서 여행을 먼저 만들어줘.")
    st.stop()

trip_name = st.selectbox("여행 선택", options=trip_names, key="view_trip_select")
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
    st.subheader("보기 옵션")
    view_mode = st.radio("보기", ["카드", "표", "타임라인"], index=0)
    show_images = st.checkbox("이미지 표시(카드)", value=True)
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

events = {}
for d in dates_sorted:
    for it in grouped[d]:
        events.setdefault(d, []).append({"time": it.get("time",""), "title": it.get("title","")})

y, m = st.session_state["view_cal_ym"]
c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    if st.button("◀ 이전달", key="view_prev", use_container_width=True):
        if m == 1:
            y, m = y - 1, 12
        else:
            y, m = y, m - 1
        st.session_state["view_cal_ym"] = (y, m)
        st.rerun()
with c2:
    st.markdown(f"### {y}년 {m}월")
with c3:
    if st.button("다음달 ▶", key="view_next", use_container_width=True):
        if m == 12:
            y, m = y + 1, 1
        else:
            y, m = y, m + 1
        st.session_state["view_cal_ym"] = (y, m)
        st.rerun()

render_month_calendar(events, y, m, title="📅 일정 달력")

st.divider()

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
    rows = []
    for d in dates_sorted:
        for it in grouped[d]:
            rows.append({
                "Day": f"Day {day_map[d]}",
                "Date": d,
                "Time": (it.get("time") or ""),
                "Title": (it.get("title") or ""),
                "Memo": (it.get("memo") or ""),
                "Map": (it.get("map_url") or ""),
            })
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("표 보기에서는 수정/삭제는 카드 보기에서 해줘.")

elif view_mode == "타임라인":
    circ = "①②③④⑤⑥⑦⑧⑨⑩"
    for d in dates_sorted:
        day_items = grouped[d]
        st.subheader(f"Day {day_map[d]} · 📅 {d}")
        route_url = _day_route_url(day_items)
        if route_url:
            st.link_button("🧭 그날 이동 코스(구글맵)", route_url)
        else:
            st.caption("이동 코스를 만들려면 지도/주소가 2개 이상 필요해.")

        for idx2, it in enumerate(day_items, start=1):
            t = (it.get("time") or "").strip()
            title = (it.get("title") or "").strip()
            map_url = (it.get("map_url") or "").strip()
            prefix = circ[idx2-1] if idx2 <= len(circ) else f"{idx2}."
            cols = st.columns([1, 6, 2])
            cols[0].markdown(f"### {prefix}")
            cols[1].markdown(f"**{t} {title}**".strip())
            if map_url:
                cols[2].markdown(f"[지도]({map_url})")
            memo = (it.get("memo") or "").strip()
            if memo:
                st.write(memo)
        st.divider()

else:
    for d in dates_sorted:
        day_items = grouped[d]
        st.subheader(f"Day {day_map[d]} · 📅 {d}")
        route_url = _day_route_url(day_items)
        if route_url:
            st.link_button("🧭 그날 이동 코스(구글맵)", route_url)
            st.caption("구글맵에서 경유지가 입력된 순서(시간순)대로 잡혀요.")
        else:
            st.caption("이동 코스를 만들려면 지도/주소가 2개 이상 필요해.")

        for it in day_items:
            item_id = it.get("id")
            t = (it.get("time") or "").strip()
            head = f"{('⏰ ' + t + '  |  ') if t else ''}{it.get('title','(제목 없음)')}"

            with st.container(border=True):
                st.markdown(f"**{head}**")
                map_url = (it.get("map_url") or "").strip()
                if map_url:
                    st.markdown(f"🗺️ [지도 열기]({map_url})")
                memo = (it.get("memo") or "").strip()
                if memo:
                    st.write(memo)

                if show_images:
                    ids = it.get("image_file_ids", []) or []
                    if ids:
                        cols = st.columns(min(3, len(ids)))
                        for idx3, fid in enumerate(ids[:6]):
                            img = get_image_bytes(fid)
                            if img:
                                cols[idx3 % len(cols)].image(img, use_container_width=True)
                        if len(ids) > 6:
                            st.caption(f"이미지 {len(ids)}장 중 6장만 표시했어.")

                c1, c2, c3 = st.columns([1, 1, 3])
                with c1:
                    if st.button("✏️ 수정", key=f"edit_btn_{item_id}", use_container_width=True):
                        st.session_state[f"editing_{item_id}"] = True
                with c2:
                    if st.button("🗑️ 삭제", key=f"del_btn_{item_id}", use_container_width=True):
                        st.session_state["confirm_delete_id"] = item_id
                with c3:
                    if st.session_state.get("confirm_delete_id") == item_id:
                        st.warning("정말 삭제할까?", icon="⚠️")
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("삭제 확정", key=f"confirm_del_{item_id}", type="primary", use_container_width=True):
                                _delete_item(item_id)
                                st.session_state["confirm_delete_id"] = None
                                st.success("삭제 완료")
                                st.rerun()
                        with cc2:
                            if st.button("취소", key=f"cancel_del_{item_id}", use_container_width=True):
                                st.session_state["confirm_delete_id"] = None
                                st.rerun()

                if st.session_state.get(f"editing_{item_id}"):
                    st.divider()
                    st.markdown("#### ✏️ 일정 수정")

                    e_date = st.text_input("날짜(YYYY-MM-DD)", value=it.get("date", ""), key=f"e_date_{item_id}")
                    e_time = st.text_input("시간(선택)", value=it.get("time", ""), key=f"e_time_{item_id}")
                    e_title = st.text_input("제목", value=it.get("title", ""), key=f"e_title_{item_id}")
                    e_memo = st.text_area("메모", value=it.get("memo", ""), height=110, key=f"e_memo_{item_id}")

                    e_map_text = st.text_input(
                        "구글맵 링크 또는 주소(선택)",
                        value=(it.get("map_text") or it.get("map_url") or ""),
                        key=f"e_map_text_{item_id}",
                    )
                    e_map_url = _maps_search_url(e_map_text)

                    add_files = st.file_uploader(
                        "이미지 추가(여러 장)",
                        type=["png", "jpg", "jpeg", "webp"],
                        accept_multiple_files=True,
                        key=f"add_img_{item_id}",
                    )

                    a1, a2 = st.columns(2)
                    with a1:
                        if st.button("저장", key=f"save_edit_{item_id}", type="primary", use_container_width=True):
                            new_ids = []
                            if add_files:
                                service = drive_store._drive_service()
                                images_folder_id = drive_store.ensure_subfolder(service, ROOT_FOLDER_ID, drive_store.IMAGES_FOLDER_NAME)
                                for uf in add_files:
                                    ts = int(time.time() * 1000)
                                    mime = uf.type or "image/png"
                                    ext = "png" if (mime or "").lower().endswith("png") else "jpg"
                                    filename = f"{trip_name.replace(' ','_')}_{e_date}_{ts}.{ext}"
                                    nid = drive_store.upload_image_bytes(service, images_folder_id, filename, uf.getvalue(), mime)
                                    new_ids.append(nid)

                            kept_ids = [x for x in it.get("image_file_ids", []) or []]
                            kept_ids.extend(new_ids)

                            _update_item(
                                item_id,
                                {
                                    "date": e_date.strip(),
                                    "time": e_time.strip(),
                                    "title": e_title.strip(),
                                    "memo": e_memo.strip(),
                                    "map_text": e_map_text.strip(),
                                    "map_url": e_map_url,
                                    "image_file_ids": kept_ids,
                                    "ts": it.get("ts") or int(time.time()),
                                },
                            )
                            st.session_state[f"editing_{item_id}"] = False
                            st.success("수정 완료")
                            st.rerun()
                    with a2:
                        if st.button("닫기", key=f"close_edit_{item_id}", use_container_width=True):
                            st.session_state[f"editing_{item_id}"] = False
                            st.rerun()
        st.divider()
