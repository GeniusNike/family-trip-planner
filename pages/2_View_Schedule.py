import time
from urllib.parse import quote_plus

import streamlit as st

import drive_store
from drive_store import load_db, save_db, list_trip_names, get_trip, get_image_bytes

st.set_page_config(page_title="일정 보기", page_icon="👀", layout="centered")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("👀 일정 보기")
db = load_db(ROOT_FOLDER_ID)
trip_names = list_trip_names(db)

if not trip_names:
    st.info("아직 여행이 없어. 홈에서 여행을 먼저 만들어줘.")
    st.stop()

trip_name = st.selectbox("여행 선택", options=trip_names)
trip = get_trip(db, trip_name)
if not trip:
    st.error("여행을 찾을 수 없어. 새로고침 후 다시 시도해줘.")
    st.stop()

items = trip.get("items", [])
if not items:
    st.info("아직 일정이 없어. '일정 추가'에서 추가해줘.")
    st.stop()

# Backward compatibility: image_file_id -> image_file_ids, add id/map_url if missing
for idx, it in enumerate(items):
    if "image_file_ids" not in it:
        if it.get("image_file_id"):
            it["image_file_ids"] = [it["image_file_id"]]
        else:
            it["image_file_ids"] = []
    if "id" not in it:
        it["id"] = f"legacy_{int(time.time()*1000)}_{idx}"
    if "map_url" not in it:
        it["map_url"] = ""

with st.expander("필터", expanded=False):
    keyword = st.text_input("키워드(제목/메모)", placeholder="예: 맛집 / 공항 / 호텔")
    show_images = st.checkbox("이미지 표시", value=True)

def _match(it):
    if not keyword.strip():
        return True
    k = keyword.strip().lower()
    blob = f"{it.get('title','')} {it.get('memo','')}".lower()
    return k in blob

# group by date
grouped = {}
for it in items:
    d = it.get("date", "미정")
    if _match(it):
        grouped.setdefault(d, []).append(it)

dates_sorted = sorted(grouped.keys())
if not dates_sorted:
    st.info("필터 조건에 맞는 일정이 없어.")
    st.stop()

# Day N mapping (sorted by date)
day_map = {d: i + 1 for i, d in enumerate(dates_sorted)}

# confirmation state for delete
if "confirm_delete_id" not in st.session_state:
    st.session_state["confirm_delete_id"] = None

def _maps_url_from_text(text: str) -> str:
    if not text.strip():
        return ""
    if text.strip().lower().startswith("http"):
        return text.strip()
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(text.strip())

def _delete_item(item_id: str):
    trip["items"] = [x for x in trip.get("items", []) if x.get("id") != item_id]
    save_db(ROOT_FOLDER_ID, db)

def _update_item(item_id: str, patch: dict):
    for x in trip.get("items", []):
        if x.get("id") == item_id:
            x.update(patch)
            break
    # sort again
    def _sort_key(x):
        t = x.get("time") or ""
        return (x.get("date") or "", t, x.get("ts") or 0)
    trip["items"] = sorted(trip.get("items", []), key=_sort_key)
    save_db(ROOT_FOLDER_ID, db)

for d in dates_sorted:
    day_items = grouped[d]

    st.subheader(f"Day {day_map[d]} · 📅 {d}")
    for it in day_items:
        item_id = it.get("id")
        t = (it.get("time") or "").strip()
        head = f"{('⏰ ' + t + '  |  ') if t else ''}{it.get('title','(제목 없음)')}"

        with st.container(border=True):
            st.markdown(f"**{head}**")

            # map link button
            map_url = it.get("map_url") or ""
            if map_url:
                st.markdown(f"🗺️ [지도 열기]({map_url})")

            memo = (it.get("memo") or "").strip()
            if memo:
                st.write(memo)

            # images (multiple)
            if show_images:
                ids = it.get("image_file_ids", []) or []
                if ids:
                    cols = st.columns(min(3, len(ids)))
                    for idx2, fid in enumerate(ids[:6]):  # show up to 6
                        img = get_image_bytes(fid)
                        if img:
                            cols[idx2 % len(cols)].image(img, use_container_width=True)
                    if len(ids) > 6:
                        st.caption(f"이미지 {len(ids)}장 중 6장만 표시했어.")

            # action row
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

            # edit panel
            if st.session_state.get(f"editing_{item_id}"):
                st.divider()
                st.markdown("#### ✏️ 일정 수정")

                e_date = st.text_input("날짜(YYYY-MM-DD)", value=it.get("date", ""), key=f"e_date_{item_id}")
                e_time = st.text_input("시간(선택)", value=it.get("time", ""), key=f"e_time_{item_id}")
                e_title = st.text_input("제목", value=it.get("title", ""), key=f"e_title_{item_id}")
                e_memo = st.text_area("메모", value=it.get("memo", ""), height=110, key=f"e_memo_{item_id}")

                e_map_raw = st.text_input(
                    "구글맵 링크 또는 주소(선택)",
                    value=it.get("map_url", ""),
                    key=f"e_map_{item_id}",
                )
                e_map_url = _maps_url_from_text(e_map_raw) if e_map_raw else ""

                st.markdown("##### 이미지 관리")
                existing_ids = it.get("image_file_ids", []) or []
                remove_ids = set()
                if existing_ids:
                    st.caption("삭제할 이미지에 체크(Drive 파일 자체를 지우진 않고, 일정에서만 제거).")
                    for fid in existing_ids:
                        img = get_image_bytes(fid)
                        cols = st.columns([1, 5])
                        with cols[0]:
                            chk = st.checkbox("삭제", key=f"rm_{item_id}_{fid}")
                        with cols[1]:
                            if img:
                                st.image(img, use_container_width=True)
                            else:
                                st.write(f"(이미지 로드 실패) {fid}")
                        if chk:
                            remove_ids.add(fid)
                else:
                    st.caption("등록된 이미지가 없어.")

                add_files = st.file_uploader(
                    "이미지 추가(여러 장)",
                    type=["png", "jpg", "jpeg", "webp"],
                    accept_multiple_files=True,
                    key=f"add_img_{item_id}",
                )

                a1, a2 = st.columns(2)
                with a1:
                    if st.button("저장", key=f"save_edit_{item_id}", type="primary", use_container_width=True):
                        # upload new images
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

                        kept_ids = [x for x in existing_ids if x not in remove_ids]
                        kept_ids.extend(new_ids)

                        _update_item(
                            item_id,
                            {
                                "date": e_date.strip(),
                                "time": e_time.strip(),
                                "title": e_title.strip(),
                                "memo": e_memo.strip(),
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
