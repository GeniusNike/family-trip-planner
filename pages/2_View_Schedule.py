import streamlit as st

from drive_store import load_db, list_trip_names, get_trip, get_image_bytes


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

# Group by date
grouped = {}
for it in items:
    d = it.get("date", "미정")
    grouped.setdefault(d, []).append(it)

dates_sorted = sorted(grouped.keys())

with st.expander("필터", expanded=False):
    keyword = st.text_input("키워드(제목/메모)", placeholder="예: 맛집 / 공항 / 호텔")
    show_images = st.checkbox("이미지 표시", value=True)

def _match(it):
    if not keyword.strip():
        return True
    k = keyword.strip().lower()
    blob = f"{it.get('title','')} {it.get('memo','')}".lower()
    return k in blob

for d in dates_sorted:
    day_items = [it for it in grouped[d] if _match(it)]
    if not day_items:
        continue

    st.subheader(f"📅 {d}")
    for it in day_items:
        t = (it.get("time") or "").strip()
        head = f"{('⏰ ' + t + '  |  ') if t else ''}{it.get('title','(제목 없음)')}"
        with st.container(border=True):
            st.markdown(f"**{head}**")
            memo = (it.get("memo") or "").strip()
            if memo:
                st.write(memo)

            if show_images and it.get("image_file_id"):
                img = get_image_bytes(it["image_file_id"])
                if img:
                    st.image(img, use_container_width=True)
                else:
                    st.caption("이미지를 불러오지 못했어(권한/파일 문제일 수 있음).")

st.caption("팁) 이미지가 안 보이면: 서비스계정(client_email)이 해당 Drive 폴더에 '편집자'로 공유됐는지 확인해줘.")
