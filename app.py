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
st.set_page_config(page_title="협력업체 서류 심사 시스템", layout="wide", page_icon="📋")

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

def analyze_document_with_ai(prompt_text, file_buffer, mime_type):
    """Gemini 2.5 Flash를 이용해 서류를 분석하고 결과를 반환합니다."""
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    vision_model = genai.GenerativeModel('gemini-2.5-flash')
    response = vision_model.generate_content([prompt_text, {"mime_type": mime_type, "data": file_buffer}])
    
    result_text = response.text
    judgment = "결과 파싱 실패"
    if "판정결과:" in result_text:
        parts = result_text.split("상세사유:")
        judgment = parts[0].replace("판정결과:", "").strip()
        reason = parts[1].strip() if len(parts) > 1 else result_text
    else:
        reason = result_text
        if "만점" in result_text: judgment = "만점 부여"
        elif "0점" in result_text: judgment = "0점 처리"
        
    admin_score = "만점 (AI판정)" if "만점" in judgment else "0점 (재확인요망)"
    return judgment, reason, admin_score

# ==========================================
# [3] 사이드바 메뉴 구성
# ==========================================
st.sidebar.title("시스템 메뉴")
menu = st.sidebar.radio("접속 화면을 선택하세요", ["업체 서류 일괄 제출 (AI 검증)", "관리자 대시보드 (육안 재확인 및 수정)"])

# ==========================================
# [4] 업체 서류 일괄 제출 화면
# ==========================================
if menu == "업체 서류 일괄 제출 (AI 검증)":
    st.title("협력업체 서류 심사 일괄 제출 시스템")
    
    # 헬프데스크 챗봇
    with st.expander("💬 챗봇 헬프데스크 (제출 기준 문의)", expanded=False):
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "제출 안내 매뉴얼에 기반하여 답변해 드립니다."}]
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("질문을 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                chat_model = genai.GenerativeModel('gemini-2.5-flash')
                sys_ctx = "당신은 서류 심사 헬프데스크 직원입니다. 이메일: rhkrwjdgur@naver.com, 전화: 041-913-1175. 팩트 기반 안내 필수."
                resp = chat_model.generate_content(sys_ctx + "\n질문: " + prompt)
                st.session_state.messages.append({"role": "assistant", "content": resp.text})
                st.chat_message("assistant").write(resp.text)
            except Exception as e:
                st.error("챗봇 오류")
                
    st.markdown("---")
    st.info("📌 [공통 시트] → [개별 시트] → [검사내용 시트] 순서대로 입력 및 서류를 첨부하신 후, 맨 아래의 **[최종 일괄 제출]** 버튼을 단 1회만 눌러주시면 됩니다.")
    
    # 탭 영역 (입력 공간)
    tab1, tab2, tab3 = st.tabs(["[1] 공통 시트", "[2] 개별 시트", "[3] 검사내용 시트"])

    # ----------------------------------------
    # 탭 1: 공통 시트 영역
    # ----------------------------------------
    with tab1:
        st.markdown("### 🏢 공통 프로필 및 거래 형태")
        col_a, col_b = st.columns(2)
        with col_a:
            company_name = st.text_input("업체명 (필수):")
            ceo_name = st.text_input("대표자:")
        with col_b:
            biz_type = st.text_input("영업의 종류:")
            manager_email = st.text_input("담당자 이메일:")
            
        st.markdown("#### 📌 거래 형태 (체크 시 개별 시트 서류 목록이 자동 등록됩니다)")
        trade_mfg = st.checkbox("원재료(제조), 부자재(제조), OEM, 세제류 외(제조)")
        trade_dist = st.checkbox("수입판매, 국내유통(미제조)")

    # ----------------------------------------
    # 탭 2: 개별 시트 영역
    # ----------------------------------------
    mfg_files = {}
    dist_files = {}
    with tab2:
        if not trade_mfg and not trade_dist:
            st.info("💡 [공통 시트] 탭에서 거래 형태를 먼저 선택해 주십시오.")
            
        if trade_mfg:
            st.markdown("### 🏭 [제조] 평가항목 전체 서류 업로드")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**1. 서류관리**")
                mfg_files["영업허가증"] = st.file_uploader("① 영업허가증/신고증", key="m1")
                mfg_files["인증서"] = st.file_uploader("② 인증서 (HACCP, FSSC 등)", key="m2")
                mfg_files["품목제조보고서"] = st.file_uploader("③ 품목제조보고서", key="m3")
                mfg_files["원료수불부"] = st.file_uploader("④ 원료수불부 (최근 1개월)", key="m4")
                mfg_files["보건증"] = st.file_uploader("⑤ 건강진단서 (보건증)", key="m5")
            with col2:
                st.markdown("**2. 환경 및 시설관리**")
                mfg_files["위생교육"] = st.file_uploader("⑥ 위생교육 수료증", key="m6")
                mfg_files["수질검사"] = st.file_uploader("⑦ 수질검사 성적서 (지하수 시)", key="m7")
                mfg_files["검교정일지"] = st.file_uploader("⑧ 계측기 검교정 성적서/일지", key="m8")
                mfg_files["방충방서"] = st.file_uploader("⑨ 방충방서 소독 일지", key="m9")
                mfg_files["온도기록"] = st.file_uploader("⑩ 냉장/냉동 창고 온도기록지", key="m10")
            st.markdown("---")

        if trade_dist:
            st.markdown("### 🚚 [유통/수입] 평가항목 전체 서류 업로드")
            col3, col4 = st.columns(2)
            with col3:
                st.markdown("**1. 유통 서류관리**")
                dist_files["수입신고필증"] = st.file_uploader("① 수입신고필증 및 COA", key="d1")
                dist_files["제조사성적서"] = st.file_uploader("② 제조사 자가/공인 성적서", key="d2")
            with col4:
                st.markdown("**2. 보관 및 출고관리**")
                dist_files["차량타코메타"] = st.file_uploader("③ 입고/보관/차량 타코메타 기록지", key="d3")
                dist_files["클레임일지"] = st.file_uploader("④ 부적합(클레임) 관리 대장", key="d4")
            st.markdown("---")

    # ----------------------------------------
    # 탭 3: 검사내용 시트 영역
    # ----------------------------------------
    mfg_df, dist_df = pd.DataFrame(), pd.DataFrame()
    mfg_coa_file, dist_coa_file = None, None
    with tab3:
        if not trade_mfg and not trade_dist:
            st.info("💡 [공통 시트] 탭에서 거래 형태를 먼저 선택해 주십시오.")
            
        if trade_mfg:
            st.markdown("### 🧪 [제조] 법적 기준 입력 및 성적서 대조")
            mfg_df = st.data_editor(pd.DataFrame([{"제품명": "", "검사항목(예: 납)": "", "법적기준(예: 3.5이하)": "", "자가검사수치": ""}]), num_rows="dynamic", key="mdf")
            mfg_coa_file = st.file_uploader("위 표와 대조할 [자가/공인 검사 성적서] 원본 업로드", key="mdf_file")
            
        if trade_dist:
            st.markdown("### 🚢 [수입] COA 통관 검사 기준 입력")
            dist_df = st.data_editor(pd.DataFrame([{"제품명": "", "COA검사항목": "", "COA법적기준": "", "수입시검사수치": ""}]), num_rows="dynamic", key="ddf")
            dist_coa_file = st.file_uploader("위 표와 대조할 [수입 COA 성적서] 원본 업로드", key="ddf_file")

    # ==========================================
    # 🚀 최종 통합 제출 버튼 (탭 영역 외부 하단에 단 1개만 위치)
    # ==========================================
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.markdown("### 📤 작성 완료 후 제출")
    
    if st.button("🚀 모든 시트 작성 완료 및 최종 일괄 제출", type="primary", use_container_width=True):
        if not company_name:
            st.error("오류: [공통 시트] 탭에서 업체명을 반드시 입력해 주십시오.")
        elif not trade_mfg and not trade_dist:
            st.error("오류: [공통 시트] 탭에서 거래 형태를 최소 1개 이상 선택해 주십시오.")
        else:
            tasks = []
            
            # 1. 제조 서류 수집
            if trade_mfg:
                for doc_name, file_obj in mfg_files.items():
                    if file_obj:
                        tasks.append({"doc_name": f"[제조] {doc_name}", "criteria": f"{doc_name} 필수 정보 및 유효기간 확인", "file": file_obj})
                if mfg_coa_file:
                    grid_data = mfg_df.to_dict('records')
                    tasks.append({"doc_name": "[제조] 최종 검사성적서", "criteria": f"입력된 법적기준({grid_data})과 성적서 수치 대조", "file": mfg_coa_file})
            
            # 2. 유통/수입 서류 수집
            if trade_dist:
                for doc_name, file_obj in dist_files.items():
                    if file_obj:
                        tasks.append({"doc_name": f"[유통] {doc_name}", "criteria": f"{doc_name} 필수 정보 확인", "file": file_obj})
                if dist_coa_file:
                    grid_data = dist_df.to_dict('records')
                    tasks.append({"doc_name": "[수입] COA 검사성적서", "criteria": f"입력된 COA기준({grid_data})과 성적서 수치 대조", "file": dist_coa_file})
                    
            if not tasks:
                st.warning("업로드된 파일이 없습니다. [개별 시트] 또는 [검사내용 시트] 탭에서 서류를 올려주십시오.")
            else:
                progress_text = "AI가 3개 시트 전체 서류를 일괄 검증 및 구글 드라이브/시트에 저장 중입니다..."
                my_bar = st.progress(0, text=progress_text)
                
                success_count = 0
                for idx, task in enumerate(tasks):
                    doc_name = task["doc_name"]
                    file_obj = task["file"]
                    criteria = task["criteria"]
                    
                    try:
                        current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        formatted_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        unique_id = f"{company_name}_{doc_name}_{current_time_str}"
                        file_name = f"{unique_id}_{file_obj.name}"
                        file_buffer = io.BytesIO(file_obj.getvalue())
                        
                        # 구글 드라이브 저장
                        drive_link = upload_to_google_drive(file_buffer, file_name, file_obj.type)
                        
                        # AI 판독
                        prompt = f"""당신은 전문 심사관입니다.
                        [항목]: {doc_name}
                        [입력기준]: {criteria}
                        지시사항: 이미지 내 수치를 확인하여 기준을 100% 충족하면 '만점 부여', 미달 시 '0점 처리'로 판정.
                        출력양식:
                        판정결과: (만점 부여 또는 0점 처리)
                        상세사유: (팩트 기재)"""
                        
                        judgment, reason, admin_score = analyze_document_with_ai(prompt, file_obj.getvalue(), file_obj.type)
                        
                        # 구글 시트 저장
                        row_data = [unique_id, formatted_time, company_name, doc_name, criteria, judgment, reason, admin_score, drive_link]
                        append_to_google_sheet(row_data)
                        success_count += 1
                        
                    except Exception as e:
                        st.error(f"{doc_name} 처리 중 오류 발생: {e}")
                        
                    my_bar.progress((idx + 1) / len(tasks), text=f"({idx+1}/{len(tasks)}) {doc_name} 제출 및 검증 완료...")
                
                my_bar.empty()
                st.success(f"🎉 성공! 모든 시트의 서류({success_count}건)가 구글 드라이브와 구글 시트에 일괄 등록 및 AI 검증 완료되었습니다.")
                st.balloons()

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
                    st.markdown("### ✍️ 관리자 최종 점수 일괄 수정 (Override)")
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
