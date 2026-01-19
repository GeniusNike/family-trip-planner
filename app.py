import streamlit as st
from drive_store import load_db, save_db, list_trip_names

st.set_page_config(page_title="가족 여행 플래너", page_icon="🧳", layout="centered")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("🧳 가족 여행 플래너")
st.caption("Streamlit Cloud + Google Drive 저장(OAuth)")

db = load_db(ROOT_FOLDER_ID)
names = list_trip_names(db)

col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("여행 목록")
    if names:
        for n in names:
            st.markdown(f"- **{n}**")
    else:
        st.info("아직 여행이 없어요. 오른쪽에서 새 여행을 만들어줘.")
with col2:
    st.markdown("### 새 여행 만들기")
    new_trip = st.text_input("여행 이름", placeholder="예: 2026 제주 가족여행")
    if st.button("➕ 생성", use_container_width=True, disabled=not new_trip.strip()):
        db["trips"].append({"name": new_trip.strip(), "items": []})
        save_db(ROOT_FOLDER_ID, db)
        st.success("생성 완료!")
        st.rerun()

st.divider()
st.markdown(
    """
### v3 추가 기능
- Add/View에 **월간 달력** 표시 (토/일 빨간색)
- View에서 **카드/표/타임라인** 보기 전환
- 날짜별 **그날 이동 코스(구글맵)** 버튼(입력 순서대로 경유지)
"""
)
