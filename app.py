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
# [2] 외부 연동 함수
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
# [UI 헬퍼 함수] 업체 자가 기준 입력 + 파일 업로드
# ==========================================
def render_upload_block(label, key_prefix, default_criteria_hint):
    st.markdown(f"**{label}**")
    crit = st.text_input(
        "💡 [업체 자체 관리 기준 입력] (AI가 이 수치를 기준으로 이탈 여부를 판독합니다)", 
        value=default_criteria_hint, 
        key=f"{key_prefix}_crit"
    )
    file = st.file_uploader("스캔본 증빙자료 업로드", key=f"{key_prefix}_file", label_visibility="collapsed")
    st.markdown("---")
    return {"criteria": crit, "file": file}

# ==========================================
# [3] 사이드바 메뉴
# ==========================================
st.sidebar.title("시스템 메뉴")
menu = st.sidebar.radio("접속 화면을 선택하세요", ["업체 서류 일괄 제출 (AI 검증)", "관리자 대시보드 (육안 재확인 및 수정)"])

# ==========================================
# [4] 업체 서류 일괄 제출 화면
# ==========================================
if menu == "업체 서류 일괄 제출 (AI 검증)":
    st.title("협력업체 서류 심사 일괄 제출 시스템")
    
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
                st.error(f"챗봇 상세 오류: {e}")
                
    st.info("📌 [공통 시트] → [개별 시트] → [검사내용 시트] 순서대로 입력 및 서류 첨부 후, 맨 아래 **[최종 일괄 제출]** 버튼을 누르십시오.")
    
    tab1, tab2, tab3 = st.tabs(["[1] 공통 시트", "[2] 개별 시트", "[3] 검사내용 시트"])

    # ----------------------------------------
    # 탭 1: 공통 시트
    # ----------------------------------------
    with tab1:
        st.markdown("### 🏢 Ⅲ. 업체 프로필")
        col_a, col_b = st.columns(2)
        with col_a:
            company_name = st.text_input("업체명 (필수):")
            ceo_name = st.text_input("대표자:")
        with col_b:
            biz_type = st.text_input("영업의 종류:")
            manager_email = st.text_input("담당자 이메일:")
            
        st.markdown("### 📌 Ⅱ. 거래 형태 (복수선택 가능)")
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            t1 = st.checkbox("원재료(제조)")
            t4 = st.checkbox("세제류 외(제조)")
        with col_t2:
            t2 = st.checkbox("부자재(제조)")
            t5 = st.checkbox("수입판매")
        with col_t3:
            t3 = st.checkbox("OEM")
            t6 = st.checkbox("국내유통(미제조)")
            
        is_mfg = t1 or t2 or t3 or t4
        is_dist = t5 or t6

        st.markdown("### 📋 Ⅳ. 인증상황")
        cert_df_init = pd.DataFrame([
            {"인증명": "HACCP", "법적필수(O,X)": "", "인증대상": "", "최초인증일": "", "비고": ""},
            {"인증명": "GMP", "법적필수(O,X)": "", "인증대상": "", "최초인증일": "", "비고": ""},
            {"인증명": "FSSC22000", "법적필수(O,X)": "", "인증대상": "", "최초인증일": "", "비고": ""},
            {"인증명": "ISO9001,14001", "법적필수(O,X)": "", "인증대상": "", "최초인증일": "", "비고": ""},
            {"인증명": "기타", "법적필수(O,X)": "", "인증대상": "", "최초인증일": "", "비고": ""}
        ])
        st.data_editor(cert_df_init, hide_index=True, use_container_width=True, key="cert_editor")

        st.markdown("### 🔄 Ⅴ. 변동사항")
        col_v1, col_v2 = st.columns([1, 3])
        with col_v1:
            v_item = st.checkbox("거래품목 변동 여부")
            v_type = st.checkbox("유형(법적) 변동 여부")
            v_insp = st.checkbox("유형에 따른 검사항목 변동 여부")
        with col_v2:
            v_item_detail = st.text_input("거래품목 변동 내용 기재:", disabled=not v_item)
            v_type_detail = st.text_input("유형(법적) 변동 내용 기재:", disabled=not v_type)
            v_insp_detail = st.text_input("검사항목 변동 내용 기재:", disabled=not v_insp)

    # ----------------------------------------
    # 탭 2: 개별 시트 (27개 세부항목 및 기준 폼)
    # ----------------------------------------
    mfg_data = {}
    dist_data = {}
    with tab2:
        if not is_mfg and not is_dist:
            st.info("💡 [공통 시트] 탭에서 거래 형태를 먼저 선택해 주십시오.")
            
        if is_mfg:
            st.markdown("### 🏭 [제조] 서류 심사 (업체 기준치 세부 입력)")
            
            with st.expander("1. 서류관리 (8개 항목)", expanded=True):
                mfg_data["영업신고"] = render_upload_block("(1) 영업허가증/신고증", "mf1", "사업현황 및 생산제품 유형 일치 여부 확인")
                mfg_data["인증서"] = render_upload_block("(2) 인증서 종류별 (HACCP, ISO 등)", "mf2", "인증 사항 일치 및 유효기간 만료 여부 확인")
                mfg_data["품목제조보고"] = render_upload_block("(3) 품목제조보고서 (전 품목)", "mf3", "제품명/원료/유통기한 신고 내역 일치 여부")
                mfg_data["원료수불부"] = render_upload_block("(4) 원료수불부", "mf4", "원료 입고/출고/사용 기록 매일 작성 및 누락 여부")
                mfg_data["자가품질검사"] = render_upload_block("(5) 자가/공인 검사 성적서", "mf5", "주기적 실시 및 전 항목 적합 판정 여부")
                mfg_data["건강진단"] = render_upload_block("(6) 건강진단서 (보건증)", "mf6", "종사자 전원 실시 및 유효기간 이탈 여부")
                mfg_data["위생교육"] = render_upload_block("(7) 법정 교육 수료증", "mf7", "영업자 위생교육 이수 여부")
                mfg_data["수질검사"] = render_upload_block("(8) 수질검사 성적서", "mf8", "용수 전 항목 적합 여부 (상수도 외 지하수 사용 시)")

            with st.expander("2. 환경 및 시설관리 (9개 항목)", expanded=False):
                mfg_data["구분구획"] = render_upload_block("(1) 작업장 평면도/설비 배치도", "mf9", "구획/구분 표시 여부 및 설비 배치 적절성")
                mfg_data["환기/청정도"] = render_upload_block("(2) 환기시설 이력카드 및 공중낙하세균 일지", "mf10", "충분한 환기 및 세균 수치 기준 이내 여부")
                mfg_data["조명관리"] = render_upload_block("(3) 조도관리일지", "mf11", "예: 일반 220Lux 이상, 검사 540Lux 이상 유지 여부")
                mfg_data["청결관리"] = render_upload_block("(4) 세척/소독 기준서 및 CIP 기준서", "mf12", "작업장 및 설비 세척/소독 기준 수립 및 실시 여부")
                mfg_data["설비_온도"] = render_upload_block("(5) 냉장/냉동 온도기록일지", "mf13", "예: 냉장 10도 이하, 냉동 -18도 이하 한계기준 이탈 여부")
                mfg_data["설비_검교정"] = render_upload_block("(6) 검교정 계획표 및 일지", "mf14", "계측기 유효기간 이내 및 오차범위 충족 여부")
                mfg_data["보관관리"] = render_upload_block("(7) 시설사진(MSDS) 및 제품 보관기준서", "mf15", "화학물질 별도 보관 및 원/부재료 기준 적합 보관 여부")
                mfg_data["저수시설"] = render_upload_block("(8) 저수조 청소 필증", "mf16", "연 1회 이상 세척/소독 실시 여부")
                mfg_data["부대시설"] = render_upload_block("(9) 화장실 시설 사진", "mf17", "손세척 및 환기 시설 구비 여부")

            with st.expander("3. 방충·방서관리 (1개 항목)", expanded=False):
                mfg_data["방충방서"] = render_upload_block("(1) 방충방서 소독 일지", "mf18", "매월 정기 소독 실시 및 기록 여부")

            with st.expander("4. 공정 및 규격관리 (4개 항목)", expanded=False):
                mfg_data["공정관리"] = render_upload_block("(1) 각 공정별 공정관리일지 (CCP 일지)", "mf19", "예: 가열 121도 15분 이상 등 업체 설정 한계기준 100% 충족 여부")
                mfg_data["완제품관리"] = render_upload_block("(2) 완제품 검사 일지", "mf20", "규격 검사 실시 및 전 항목 적합 여부")
                mfg_data["원부자재관리"] = render_upload_block("(3) 입고검사일지 및 협력업체 점검표", "mf21", "입고 시 기준 부합 검사 및 성적서(GMO등) 수취 여부")
                mfg_data["클레임관리"] = render_upload_block("(4) 클레임 관리일지", "mf22", "부적합 발생 내역 및 개선조치 기록 여부")

            with st.expander("5. 작업자관리 (2개 항목)", expanded=False):
                mfg_data["개인위생"] = render_upload_block("(1) 작업장 출입절차 및 개인위생관리일지", "mf23", "위생복/장신구 등 작업자 위생 상태 양호 여부")
                mfg_data["위생교육일지"] = render_upload_block("(2) 자체 위생교육일지", "mf24", "작업자 대상 위생교육 주기적 실시 여부")

        if is_dist:
            st.markdown("### 🚚 [유통/수입] 평가항목 서류 및 기준 입력")
            with st.expander("유통 서류 관리", expanded=True):
                dist_data["수입신고필증"] = render_upload_block("(1) 수입신고필증 및 COA", "df1", "수입신고 내역 일치 및 COA 제출 여부")
                dist_data["제조사성적서"] = render_upload_block("(2) 제조사 자가/공인 성적서", "df2", "수령 주기 확인 및 검사결과 적합 여부")
                dist_data["차량타코메타"] = render_upload_block("(3) 차량 타코메타 기록지", "df3", "입고/보관 시 지정 온도 한계 이탈 여부 확인")
                dist_data["클레임일지"] = render_upload_block("(4) 부적합(클레임) 관리 대장", "df4", "부적합품 식별 표시 및 반품 처리 내역 확인")

    # ----------------------------------------
    # 탭 3: 검사내용 시트
    # ----------------------------------------
    mfg_df, dist_df = pd.DataFrame(), pd.DataFrame()
    mfg_coa_file, dist_coa_file = None, None
    with tab3:
        if not is_mfg and not is_dist:
            st.info("💡 [공통 시트] 탭에서 거래 형태를 먼저 선택해 주십시오.")
            
        if is_mfg:
            st.markdown("### 🧪 [제조] 법적 기준 입력 및 성적서 대조")
            mfg_df = st.data_editor(pd.DataFrame([{"제품명": "", "검사항목(예: 납)": "", "법적기준(예: 3.5이하)": "", "자가검사수치": ""}]), num_rows="dynamic", key="mdf")
            mfg_coa_file = st.file_uploader("위 표와 대조할 [자가/공인 검사 성적서] 원본 업로드", key="mdf_file")
            
        if is_dist:
            st.markdown("### 🚢 [수입] COA 통관 검사 기준 입력")
            dist_df = st.data_editor(pd.DataFrame([{"제품명": "", "COA검사항목": "", "COA법적기준": "", "수입시검사수치": ""}]), num_rows="dynamic", key="ddf")
            dist_coa_file = st.file_uploader("위 표와 대조할 [수입 COA 성적서] 원본 업로드", key="ddf_file")

    # ==========================================
    # 🚀 최종 통합 제출 버튼
    # ==========================================
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.markdown("### 📤 작성 완료 후 일괄 검증 제출")
    
    if st.button("🚀 모든 시트 작성 완료 및 최종 일괄 제출 (AI 심사)", type="primary", use_container_width=True):
        if not company_name:
            st.error("오류: [공통 시트] 탭에서 업체명을 반드시 입력해 주십시오.")
        elif not is_mfg and not is_dist:
            st.error("오류: [공통 시트] 탭에서 거래 형태를 최소 1개 이상 선택해 주십시오.")
        else:
            tasks = []
            
            if is_mfg:
                for doc_name, data in mfg_data.items():
                    if data["file"]:
                        tasks.append({"doc_name": f"[제조] {doc_name}", "criteria": data["criteria"], "file": data["file"]})
                if mfg_coa_file:
                    grid_data = mfg_df.to_dict('records')
                    tasks.append({"doc_name": "[제조] 최종 검사성적서", "criteria": f"입력된 법적기준({grid_data})과 성적서 수치 일치/통과 여부 대조", "file": mfg_coa_file})
            
            if is_dist:
                for doc_name, data in dist_data.items():
                    if data["file"]:
                        tasks.append({"doc_name": f"[유통] {doc_name}", "criteria": data["criteria"], "file": data["file"]})
                if dist_coa_file:
                    grid_data = dist_df.to_dict('records')
                    tasks.append({"doc_name": "[수입] COA 검사성적서", "criteria": f"입력된 COA기준({grid_data})과 성적서 수치 대조", "file": dist_coa_file})
                    
            if not tasks:
                st.warning("업로드된 파일이 없습니다. [개별 시트] 탭 등에서 심사받을 증빙자료를 첨부해 주십시오.")
            else:
                progress_text = "AI가 등록하신 업체의 자체 관리 기준(수치)을 바탕으로 서류 기록을 엄격히 검증하고 있습니다..."
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
                        
                        drive_link = upload_to_google_drive(file_buffer, file_name, file_obj.type)
                        
                        # 팩트: AI가 '제출 유무'가 아니라 '입력된 기준치 대비 실제 수치 이탈'을 잡아내도록 프롬프트 룰 강화
                        prompt = f"""당신은 엄격한 식품안전 품질 심사관입니다.
                        [심사항목]: {doc_name}
                        [업체 자체 관리 기준(반드시 지켜야 할 기준치)]: {criteria}
                        
                        지시사항:
                        1. 첨부된 이미지/문서를 읽고, 기록된 온도, 시간, 룩스(Lux), 검사 수치, 날짜 등 모든 데이터를 꼼꼼히 스캔하십시오.
                        2. 사용자가 제시한 [업체 자체 관리 기준]에 명시된 수치와 문서의 실제 기록을 완벽하게 대조하십시오.
                        3. 단 1회라도 기준 범위를 벗어나거나(이탈), 누락되었거나, 부적합한 내용이 기록되어 있다면 무조건 '0점 처리' 하십시오.
                        4. 모든 기록이 기준 수치를 100% 충족하고 정상일 때만 '만점 부여'로 판정하십시오.
                        
                        출력양식:
                        판정결과: (만점 부여 또는 0점 처리)
                        상세사유: (문서에서 발견한 정확한 팩트 수치나 이탈 상태를 근거로 사유 기재)"""
                        
                        judgment, reason, admin_score = analyze_document_with_ai(prompt, file_obj.getvalue(), file_obj.type)
                        
                        row_data = [unique_id, formatted_time, company_name, doc_name, criteria, judgment, reason, admin_score, drive_link]
                        append_to_google_sheet(row_data)
                        success_count += 1
                        
                    except Exception as e:
                        st.error(f"{doc_name} 처리 중 오류 발생: {e}")
                        
                    my_bar.progress((idx + 1) / len(tasks), text=f"({idx+1}/{len(tasks)}) {doc_name} 검증 완료...")
                
                my_bar.empty()
                st.success(f"🎉 성공! 모든 서류({success_count}건)가 설정하신 자체 관리 기준에 따라 AI 수치 검증을 마쳤으며, 구글 시트에 이탈 여부가 팩트로 기록되었습니다.")
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
                st.markdown("### 🚨 0점 처리 건 (수치 이탈 발견 건)")
                zero_score_df = log_df[log_df['관리자최종점수'].str.contains("0점", na=False)]
                
                if zero_score_df.empty:
                    st.success("현재 기준치를 이탈하여 육안으로 재확인해야 할 0점 처리 건이 없습니다.")
                else:
                    st.dataframe(zero_score_df[['고유ID', '업체명', '심사항목', 'AI상세사유', '관리자최종점수', '드라이브링크']], use_container_width=True)
                    
                    st.markdown("---")
                    st.markdown("### ✍️ 관리자 최종 점수 일괄 수정")
                    col1, col2 = st.columns(2)
                    with col1:
                        target_id = st.selectbox("수정할 건의 [고유ID]를 선택하세요:", zero_score_df['고유ID'].tolist())
                    with col2:
                        new_status = st.selectbox("수정할 점수를 선택하세요:", ["만점 (관리자 육안 확인 통과)", "0점 (관리자 최종 반려)"])
                    admin_memo = st.text_input("수정 사유 입력 (선택):")
                    
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
