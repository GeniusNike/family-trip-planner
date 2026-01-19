import streamlit as st
from drive_store import load_db, save_db, list_trip_names

st.set_page_config(page_title="가족 여행 플래너", page_icon="🧳", layout="centered")

ROOT_FOLDER_ID = st.secrets["drive"]["root_folder_id"]

st.title("🧳 가족 여행 플래너")
st.caption("Streamlit Cloud + Google Drive 저장(OAuth)")

db = load_db(ROOT_FOLDER_ID)

st.subheader("여행 목록")
names = list_trip_names(db)

col1, col2 = st.columns([2, 1])

with col1:
    if names:
        st.write("현재 여행:")
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
        st.success("생성 완료! 왼쪽 메뉴에서 '일정 추가'로 가봐.")
        st.rerun()

st.divider()
st.markdown(
    """
### 추가된 기능
- 일정 **수정/삭제** (확인창 포함)
- 일정당 **사진 여러 장**
- **구글맵 링크 버튼**(주소/링크 입력)
- 날짜별 **Day 1 / Day 2** 자동 표시
"""
)
