import streamlit as st
import google.generativeai as genai
import pandas as pd
import datetime
import os
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread

# ==========================================
# [1] 시스템 기본 설정 및 API 인증 정보
# ==========================================
st.set_page_config(page_title="식품심사 서류 제출 시스템", layout="wide", page_icon="📋")

DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
GOOGLE_SHEET_ID = st.secrets["GOOGLE_SHEET_ID"]
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

# ==========================================
# [2] 외부 연동 함수 (드라이브 & 시트 - Secrets 연동)
# ==========================================
def get_credentials():
    """Streamlit Secrets에서 구글 클라우드 인증 정보를 불러옵니다."""
    return service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )

def upload_to_google_drive(file_buffer, file_name, mime_type):
    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(file_buffer, mimetype=mime_type, resumable=True)
        uploaded_file = service.files().create(
            body=file_metadata, media_body=media, fields='id, webViewLink'
        ).execute()
        return uploaded_file.get('webViewLink')
    except Exception as e:
        return str(e)

def append_to_google_sheet(row_data):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.sheet1
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        return str(e)

def update_google_sheet_admin_score(unique_id, new_score):
    try:
        creds = get_credentials()
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.sheet1
        all_records = worksheet.get_all_records()
        for idx, record in enumerate(all_records):
            if record.get('고유ID') == unique_id:
                worksheet.update_cell(idx + 2, 8, new_score)
                break
        return True
    except Exception as e:
        return str(e)

# ==========================================
# [3] 사이드바 메뉴 구성
# ==========================================
st.sidebar.title("시스템 메뉴")
menu = st.sidebar.radio("접속 화면을 선택하세요", ["업체 제출 화면 (1차 AI 검증)", "관리자 대시보드 (육안 재확인 및 수정)"])

# ==========================================
# [4] 업체 제출 화면 (엑셀 시트형 탭 UI 적용)
# ==========================================
if menu == "업체 제출 화면 (1차 AI 검증)":
    st.title("식품심사 서류 자동 제출 및 검증 (업체용)")
    
    # 헬프데스크 챗봇 영역 (API 키 입력란 제거, Secrets에서 자동 로드)
    with st.expander("💬 서류 제출 방법이나 기준에 대해 궁금한 점을 챗봇에게 물어보세요!", expanded=False):
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "안녕하세요! 제출 안내 매뉴얼에 기반하여 답변해 드립니다. 어떤 점이 궁금하신가요?"}
            ]
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("질문을 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            
            try:
                # Secrets에서 Gemini API 키 로드
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                chat_model = genai.GenerativeModel('gemini-1.5-flash')
                system_context = """
                당신은 서류 심사 헬프데스크 직원입니다. 
                - 이메일: rhkrwjdgur@naver.com, 전화: 041-913-1175
                - 공통 시트는 1부만, 개별/검사 시트는 납품 유형별 전부 작성
                - 부자재(제조)는 내/외포장재 납품업체
                - 대외비(배합비 등)는 민감 수치를 지우고 제출 가능
                위 팩트를 기반으로 친절하게 안내하십시오.
                """
                response = chat_model.generate_content(system_context + "\n질문: " + prompt)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.chat_message("assistant").write(response.text)
            except Exception as e:
                st.error(f"챗봇 연결 오류가 발생했습니다: {e}")
                    
    st.markdown("---")
    st.markdown("아래의 탭(Tab)을 순서대로 클릭하여 엑셀 시트와 동일한 방식으로 서류를 제출해 주십시오.")

    tab1, tab2, tab3 = st.tabs(["[1] 공통 시트 (기본 정보)", "[2] 개별 시트 (서류 제출)", "[3] 검사내용 시트 (성적서 대조)"])

    # ----------------------------------------
    # 탭 1: 공통 시트 영역
    # ----------------------------------------
    with tab1:
        st.markdown("### 🏢 공통 시트 작성")
        company_name = st.text_input("업체명을 입력하세요:")
        trade_type = st.selectbox("거래 형태를 선택하세요:", ["원재료(제조)", "부자재(제조)", "OEM", "수입판매", "국내유통(미제조)"])
        st.info("이곳에 입력한 업체명은 다음 시트(탭)에서도 자동으로 연동됩니다.")

    # ----------------------------------------
    # 탭 2: 개별 시트 영역 (제조 및 공정 서류)
    # ----------------------------------------
    with tab2:
        st.markdown(f"### 📋 개별 시트 서류 제출 (선택된 형태: {trade_type if 'trade_type' in locals() else '미선택'})")
        document_type_2 = st.selectbox(
            "제출할 서류 항목 선택 (개별 시트):",
            ["선택해주세요", "영업등록증", "CCP 가열/멸균 공정 일지", "CCP 금속검출 공정 일지", "조도 관리 대장", "보건증", "위생교육 수료증"],
            key="doc_type_tab2"
        )

        custom_criteria_2 = ""
        if document_type_2 == "CCP 가열/멸균 공정 일지":
            col1, col2 = st.columns(2)
            with col1:
                temp_limit = st.text_input("기준 온도 (예: 121℃ 이상)", key="temp_tab2")
                time_limit = st.text_input("기준 시간 (예: 15분 이상)", key="time_tab2")
            custom_criteria_2 = f"기준 온도: {temp_limit}, 기준 시간: {time_limit}"
        elif document_type_2 == "CCP 금속검출 공정 일지":
            fe_size = st.text_input("Fe (철) 기준", key="fe_tab2")
            sus_size = st.text_input("SUS (스테인리스) 기준", key="sus_tab2")
            custom_criteria_2 = f"Fe 기준: {fe_size}, SUS 기준: {sus_size}"
        elif document_type_2 == "조도 관리 대장":
            lux_limit = st.text_input("기준 조도", key="lux_tab2")
            custom_criteria_2 = f"기준 조도: {lux_limit}"
        elif document_type_2 in ["영업등록증", "보건증", "위생교육 수료증"]:
            custom_criteria_2 = f"{document_type_2} 필수 기재사항 확인 및 유효기간 만료 여부 확인"

        uploaded_file_2 = st.file_uploader(f"[{document_type_2}] 스캔본 업로드", type=["pdf", "jpg", "png"], key="file_tab2")

        if st.button("개별 시트 서류 제출 및 검증", key="btn_tab2"):
            if document_type_2 == "선택해주세요" or not company_name or not uploaded_file_2:
                st.warning("공통 시트의 업체명 설정 및 업로드 파일을 모두 확인해 주십시오.")
            else:
                with st.spinner("개별 시트 서류 분석 및 구글 시트 연동 중..."):
                    try:
                        current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        formatted_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        unique_id = f"{company_name}_{current_time_str}"
                        file_name = f"{unique_id}_{uploaded_file_2.name}"
                        
                        file_buffer = io.BytesIO(uploaded_file_2.getvalue())
                        drive_link = upload_to_google_drive(file_buffer, file_name, uploaded_file_2.type)
                        
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        vision_model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = f"""
                        당신은 전문 심사관입니다.
                        [항목]: {document_type_2}
                        [입력기준]: {custom_criteria_2}
                        
                        지시사항:
                        1. 이미지 내 수기 기록을 확인하십시오.
                        2. 모든 기록이 입력기준을 100% 충족하면 '만점 부여'.
                        3. 기준 이탈, 서류 불일치 시 '0점 처리'로 판정하십시오.
                        
                        출력양식:
                        판정결과: (만점 부여 또는 0점 처리)
                        상세사유: (팩트 기재)
                        """
                        response = vision_model.generate_content([prompt, {"mime_type": uploaded_file_2.type, "data": uploaded_file_2.getvalue()}])
                        
                        result_text = response.text
                        judgment = "결과 파싱 실패"
                        if "판정결과:" in result_text:
                            parts = result_text.split("상세사유:")
                            judgment = parts[0].replace("판정결과:", "").strip()
                            reason = parts[1].strip() if len(parts) > 1 else result_text

                        admin_score = "만점 (AI판정)" if "만점" in judgment else "0점 (재확인요망)"
                        row_data = [unique_id, formatted_time, company_name, document_type_2, custom_criteria_2, judgment, reason, admin_score, drive_link]
                        append_to_google_sheet(row_data)
                        
                        st.success("개별 시트 검증 완료!")
                        st.info(result_text)
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

    # ----------------------------------------
    # 탭 3: 검사내용 시트 영역 (법적 성적서 제출)
    # ----------------------------------------
    with tab3:
        st.markdown("### 🧪 검사내용 시트 (법적 기준 및 성적서 대조)")
        document_type_3 = st.selectbox(
            "제출할 검사 항목 선택:",
            ["선택해주세요", "자가품질검사 성적서", "공인기관 검사 성적서", "수질검사 성적서"],
            key="doc_type_tab3"
        )
        
        st.info("검사내용 엑셀 시트에서 작성하던 법적 기준을 아래에 입력하십시오. (예: 납 3.5ppm 이하)")
        legal_criteria = st.text_area("해당 제품의 국내 법적 기준 및 자가 검사 기준 입력:", key="legal_criteria")
        
        uploaded_file_3 = st.file_uploader(f"[{document_type_3}] 스캔본 업로드", type=["pdf", "jpg", "png"], key="file_tab3")
        
        if st.button("검사내용 시트 서류 제출 및 검증", key="btn_tab3"):
            if document_type_3 == "선택해주세요" or not company_name or not uploaded_file_3 or not legal_criteria:
                st.warning("공통 시트의 업체명 설정, 법적 기준, 업로드 파일을 모두 확인해 주십시오.")
            else:
                with st.spinner("검사 성적서 수치 분석 및 구글 시트 연동 중..."):
                    try:
                        current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        formatted_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        unique_id = f"{company_name}_검사_{current_time_str}"
                        file_name = f"{unique_id}_{uploaded_file_3.name}"
                        
                        file_buffer = io.BytesIO(uploaded_file_3.getvalue())
                        drive_link = upload_to_google_drive(file_buffer, file_name, uploaded_file_3.type)
                        
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        vision_model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = f"""
                        당신은 식품 규격 성적서를 검증하는 전문 심사관입니다.
                        [항목]: {document_type_3}
                        [법적 기준]: {legal_criteria}
                        
                        지시사항:
                        1. 성적서 이미지 내의 실제 검사 결과 수치(결과값)를 확인하십시오.
                        2. 성적서의 결과 수치가 제시된 [법적 기준]의 허용 범위 이내이거나 불검출인 경우 '만점 부여'.
                        3. 기준을 초과하거나 검출된 경우 '0점 처리'.
                        
                        출력양식:
                        판정결과: (만점 부여 또는 0점 처리)
                        상세사유: (성적서에서 확인한 정확한 팩트 수치 기재)
                        """
                        response = vision_model.generate_content([prompt, {"mime_type": uploaded_file_3.type, "data": uploaded_file_3.getvalue()}])
                        
                        result_text = response.text
                        judgment = "결과 파싱 실패"
                        if "판정결과:" in result_text:
                            parts = result_text.split("상세사유:")
                            judgment = parts[0].replace("판정결과:", "").strip()
                            reason = parts[1].strip() if len(parts) > 1 else result_text

                        admin_score = "만점 (AI판정)" if "만점" in judgment else "0점 (재확인요망)"
                        row_data = [unique_id, formatted_time, company_name, document_type_3, legal_criteria, judgment, reason, admin_score, drive_link]
                        append_to_google_sheet(row_data)
                        
                        st.success("검사내용 성적서 검증 완료!")
                        st.info(result_text)
                    except Exception as e:
                        st.error(f"오류 발생: {e}")

# ==========================================
# [5] 관리자 대시보드
# ==========================================
elif menu == "관리자 대시보드 (육안 재확인 및 수정)":
    st.title("품질 관리 책임자 최종 검증 대시보드")
    admin_pw = st.text_input("관리자 비밀번호:", type="password")
    
    if admin_pw == "admin1234":
        try:
            creds = get_credentials()
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(GOOGLE_SHEET_ID)
            worksheet = sh.sheet1
            all_data = worksheet.get_all_records()
            log_df = pd.DataFrame(all_data)
            
            if log_df.empty:
                st.warning("아직 구글 시트에 기록된 심사 데이터가 없습니다.")
            else:
                st.markdown("### 🚨 0점 처리 건 (육안 재확인 필요)")
                zero_score_df = log_df[log_df['관리자최종점수'].str.contains("0점", na=False)]
                
                if zero_score_df.empty:
                    st.success("현재 육안으로 재확인해야 할 0점 처리 건이 없습니다.")
                else:
                    st.dataframe(zero_score_df[['고유ID', '업체명', '심사항목', 'AI상세사유', '관리자최종점수', '드라이브링크']], use_container_width=True)
                    
                    st.markdown("---")
                    st.markdown("### ✍️ 관리자 최종 점수 구글 시트 수정 (Override)")
                    col1, col2 = st.columns(2)
                    with col1:
                        target_id = st.selectbox("수정할 건의 [고유ID]를 선택하세요:", zero_score_df['고유ID'].tolist())
                    with col2:
                        new_status = st.selectbox("수정할 점수를 선택하세요:", ["만점 (관리자 육안 확인 통과)", "0점 (관리자 최종 반려)"])
                    admin_memo = st.text_input("수정 사유 입력:")
                    
                    if st.button("최종 점수 구글 시트 반영"):
                        memo_text = f"{new_status} / 사유: {admin_memo}" if admin_memo else new_status
                        if update_google_sheet_admin_score(target_id, memo_text) == True:
                            st.success(f"{target_id} 건의 최종 점수가 성공적으로 수정되었습니다.")
                            st.rerun()
                
                st.markdown("---")
                st.markdown("### 📊 실시간 전체 심사 이력 (구글 시트 연동)")
                st.dataframe(log_df, use_container_width=True)
        except Exception as e:
            st.error(f"데이터베이스 연결 오류: {e}")
    elif admin_pw != "":
        st.error("비밀번호가 일치하지 않습니다.")
