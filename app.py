import streamlit as st
from google import genai
from google.genai import types
import pandas as pd
import datetime
import os
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import gspread

# ==========================================
# [1] 시스템 기본 설정
# ==========================================
st.set_page_config(page_title="협력업체 서류 심사 시스템", layout="wide")

DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
GOOGLE_SHEET_ID = st.secrets["GOOGLE_SHEET_ID"]
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

GEMINI_MODEL_VISION = "gemini-3.6-flash"
GEMINI_MODEL_CHAT = "gemini-3.5-flash-lite"

TARGET_COMPANIES = [
    "선택하세요",
    "테트라팩(유)", "SIG Combibloc(인천세관장)", "에스아이지패키징코리아", "(주)한국팩키지",
    "(주)케이아이비", "삼륭물산(주)", "(주)서일", "삼성포장", "국일피앤피 주식회사",
    "명진포장(주)", "덕원기업", "현대이피 주식회사", "호명화학공업(주)", "신성이노텍(주) 음성공장",
    "주식회사신원통상", "신성이노텍(주)", "희성폴리머(주)", "동원시스템즈(주)", "(주)피엠아이",
    "(주)유래코", "(주)엘컴화인", "(주)유한산업", "주식회사 선일인더스트리", "에스알테크노팩(주)",
    "고문당인쇄(주)", "삼육식품(천안)", "(주)서울에프엔비", "삼육네이처세븐", "(주)푸드코아",
    "(주)참조은에스에프", "(주)아인츠푸드", "남양유업 경주공장_탈지,생크림", "비락(OEM)", "비락_진천",
    "(주)한국씨엔에스팜", "합동산업(주)", "명가유업(주)_탈지,생크림", "(주)데어리젠", "동그린주식회사",
    "유라가", "(주)제이앤이 아산공장", "풀무원다논(주)", "푸르밀", "(주)조흥", "(주)에스알인터내셔널",
    "범산목장", "건국유업_상품", "유성씨앤에프(주)", "금성이엔씨(주)", "한화컴파운드(주)서울",
    "헨켈코리아(유)", "새한실리켐(주)", "이팩킹(주)", "한국이콜랩(유)", "아쿠아테크코리아",
    "(주)남강", "한국에이피이", "대덕가스(주)", "영천환경화학(주)", "웨이브티피에스",
    "에스제이푸드", "제이에이치푸드앤케미칼서비스", "신창교역", "아그라나프루트코리아(주)",
    "(유)사조CPK", "(주)코맥스인터내셔널", "롯데푸드(주) 파스퇴르", "롯데푸드(주) (유지)", "(주)바름",
    "가우통상", "씨.에스에프(주)", "(주)나래에프앤씨", "(주)일신웰스", "(주)티알코리아", "동성글로벌",
    "(주)진성에프엠", "(주)주피터인터내셔널", "(주)티오에프", "(주)비케이바이오", "다름인터내셔널",
    "(주)제이케이뉴트라", "대종자임스", "본식품", "페트라", "성원에프원(법인)", "(주)선그린",
    "(주)아로마에프아이", "미립물산(주)", "(주)엠에스씨", "웨스트마이크로", "이시푸드", "누리지에프에스",
    "(주)네추럴웨이", "유맥", "기문물산", "해찬솔푸드", "(주)중앙타프라", "에스앤이티(주)", "(주)희창유업",
    "(주)앤스에프에스", "프레시코", "(주)동은(탈지)", "(주)태영에프에이", "브랜탁코리아(주)",
    "(주)뉴트렉스테크놀러지", "(주)삼익유가공", "주식회사 혜원", "제이에프에프(법인)", "주식회사 영푸드텍",
    "녹스코리아(주)", "주식회사 제이씨월드(원료)", "남영상사주식회사", "송은통상(주)", "(주)빅솔반월공장",
    "휴나텍", "케이피씨", "(주)와이씨에프", "서울향료(주)", "디에프아이", "티앤피코리아", "한국베름주식회사",
    "(주)조향", "한국마쯔다니(주)", "영진염업사", "(주)삼화에프앤에프", "화인향료(주)", "성원에프아이",
    "향림산업(주)", "삼정향료", "주식회사지금", "한빛향료", "삼인케미칼", "(주)한불화농", "베리에프앤비",
    "주식회사 원아", "동서식품(주)", "아로마라인주식회사", "트라이콤바이오", "에이스향료", "제이제이글로벌",
    "빙그레_원재료", "(주)세보글로벌", "에이치와이푸드텍", "(주)동광상사", "(주)제이스에프아이", "엔바이오텍",
    "(주)네오크레마", "(주)성천", "신한솔루션 주식회사", "젤텍", "선경트레이딩(주)", "(주)건우에프피",
    "아이비티 주식회사", "현진그린밀 (주)", "(주)에이치엠", "(주)제이더스화학", "롯데칠성(본사)", "서울우유",
    "보락", "한국식품산업협회", "케이솔트(주)", "대우양봉영농조합법인", "라라스윗", "(주)제이에스켐트론",
    "에프시아로마(주)", "(주)광일아산공장", "(주)한국카라겐", "(주)대평", "성지물산", "유일에프아이",
    "(주)삼우티. 디", "농업회사법인 주식회사 보림제다", "(주)파이토메디", "코스맥스엔에스", "가우인터내셔널(주)",
    "우리피엔에프", "유성식품", "(주)뉴웨이브코퍼레이션", "주식회사 앤앤피", "케이엔바이오", "제리와이(JY)유통",
    "어니언즈 주식회사", "에이치엔바이오", "한가람지에프", "엠엔에스코리아", "주식회사 예산농산", "유니언상사",
    "대상다이브스", "농업회사법인 수산북해", "리첼스코리아", "파텍상사", "솔시드", "신화트레이딩",
    "인크레더블 주식회사", "(주)테크니아", "비전바이오켐", "가우리트레이딩", "제이원상사(신규)", "벤엘통상",
    "프리맨뉴트라(유)", "피엠아이바이오텍", "비금농협", "(주)미트인터내셔날", "주식회사 태성", "(주)교토아이앤씨",
    "가향", "(주)홀리스틱바이오", "(주)파르마코리아", "(주)뉴트리_원료", "메이", "농업회사법인 (주)보향다원",
    "해인향료", "알프스", "(주)청우라이프사이언스", "(주)빅솔", "티지에프", "한미사이언스", "연두", "건강마을",
    "OKF (진평)", "비오팜", "세종바이오팜", "희망그린식품", "노바렉스", "서흥", "코스맥스엔비티", "콜마BNH", "인성제약"
]

# ==========================================
# [2] 외부 연동 함수
# ==========================================
def get_credentials():
    try:
        creds = Credentials(
            token=None,
            refresh_token=st.secrets["google_oauth"]["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=st.secrets["google_oauth"]["client_id"],
            client_secret=st.secrets["google_oauth"]["client_secret"]
        )
        return creds
    except Exception as e:
        st.error(f"구글 인증 정보 로드 오류: {e}")
        return None

def upload_to_google_drive(file_buffer, file_name, mime_type):
    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': file_name, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(file_buffer, mimetype=mime_type, resumable=True)
        uploaded_file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id, webViewLink',
            supportsAllDrives=True
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

def get_gemini_client():
    if "gemini_client" not in st.session_state:
        st.session_state.gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return st.session_state.gemini_client

def analyze_document_with_ai(prompt_text, file_bytes, mime_type):
    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL_VISION,
        contents=[
            prompt_text,
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
        ],
    )

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

def render_upload_block(label, key_prefix, default_criteria_hint, is_editable=False):
    st.markdown(f"**{label}**")
    
    is_na = st.checkbox("해당사항 없음 (N/A)", key=f"{key_prefix}_na")
    na_reason = ""
    if is_na:
        na_reason = st.text_input("해당사항 없음 사유를 입력하십시오:", key=f"{key_prefix}_na_reason")
    
    if is_editable:
        crit = st.text_input(
            "업체 자체 관리 기준 입력 (귀사의 기준 수치에 맞게 수정해주십시오)",
            value=default_criteria_hint,
            key=f"{key_prefix}_crit",
            disabled=is_na
        )
    else:
        crit = st.text_input(
            "연세유업 고정 심사 기준 (수정 불가 - 해당 조건 충족 필수)",
            value=default_criteria_hint,
            key=f"{key_prefix}_crit",
            disabled=True
        )
    file = st.file_uploader("스캔본 증빙자료 업로드", key=f"{key_prefix}_file", label_visibility="collapsed", disabled=is_na)
    st.markdown("---")
    return {"criteria": crit, "file": file, "is_na": is_na, "na_reason": na_reason}

def get_completed_count(prefixes):
    count = 0
    for p in prefixes:
        if st.session_state.get(f"{p}_na", False) or st.session_state.get(f"{p}_file") is not None:
            count += 1
    return count

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

    with st.expander("챗봇 헬프데스크 (제출 기준 문의)", expanded=False):
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "연세유업 서류심사 제출 가이드라인에 기반하여 팩트로 답변해 드립니다."}]
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("질문을 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            try:
                client = get_gemini_client()

                sys_ctx = """
                당신은 연세유업 아산공장의 협력업체 서류심사 헬프데스크 AI 직원입니다.
                아래의 '서류심사 체크리스트 작성 방법' 문서 규정을 엄격하게 적용하여 팩트만 답변하십시오.

                [기본 연락처 및 문의 안내 지침]
                - 담당자: 식품안전팀 곽정혁
                - 이메일: rhkrwjdgur@yonseidairy.com
                - 전화번호: 041-913-1175
                - 중요 지침: 사용자가 "추가 문의", "연락처", "담당자", "누구에게 물어봐야 해?" 등을 질문할 경우, 즉시 곽정혁 담당자의 연락처와 이메일을 명시하여 친절히 안내하십시오.

                [거래형태별 제출 시트 규정]
                1. 원재료(제조) 및 OEM: 공통시트 + 개별시트(제조) + 검사시트 작성
                2. 부자재(제조) 및 세제류 외(제조): 공통시트 + 개별시트(제조) 작성 (검사내용 시트는 작성 X 면제됨)
                3. 수입판매 및 국내유통(미제조): 공통시트 + 개별시트(수입/유통) + 검사시트 작성

                [자주 묻는 질문(FAQ) 팩트]
                - 두 가지 이상 납품 시: 공통시트는 1회만, 개별/검사시트는 유형별로 전부 다 작성해야 합니다.
                - 부자재(제조) 업체란: 내, 외포장재 납품업체를 의미합니다.
                - 파일 제출 범위: '품목제조보고서'와 '자가/공인 검사 성적서'는 납품하는 전 품목을 내야 하고, 나머지 품질일지나 교육 수료증 등은 '최근 1개월 내 대표 샘플 1부'만 내면 됩니다.
                - 부자재/세제류 업체의 서류 제외(N/A): 부자재나 세제류 생산 공정의 특성상 CCP(중요관리점) 일지나 품목제조보고서처럼 해당사항이 없는 서류는 화면에 노출되지 않으며 제출 의무가 없습니다.
                - 대외비 서류: 배합비 등 민감한 수치는 지우고(블라인드) 제출해도 무방합니다. 단 양식과 기준은 보여야 합니다.
                """

                resp = client.models.generate_content(
                    model=GEMINI_MODEL_CHAT,
                    contents=sys_ctx + "\n질문: " + prompt,
                )
                st.session_state.messages.append({"role": "assistant", "content": resp.text})
                st.chat_message("assistant").write(resp.text)
            except Exception as e:
                st.error(f"챗봇 상세 오류: {e}")

    st.info("[안내] 작성 방법: [공통 시트] -> [개별 시트] -> [검사내용 시트] 순서대로 입력 후 맨 아래 [최종 일괄 제출] 버튼을 누르십시오.")

    tab1, tab2, tab3 = st.tabs(["공통 시트", "개별 시트", "검사내용 시트"])

    # ----------------------------------------
    # 탭 1: 공통 시트
    # ----------------------------------------
    with tab1:
        st.markdown("### Ⅲ. 업체 프로필")
        col_a, col_b = st.columns(2)
        with col_a:
            company_name = st.selectbox("업체명 (필수):", TARGET_COMPANIES)
            manager_name = st.text_input("담당자명:")
            manager_email = st.text_input("담당자 이메일:")
        with col_b:
            biz_type = st.text_input("영업의 종류 (보고서 '구분' 란에 표기됨):")
            delivered_items = st.text_input("납품 품목 (예: 우유팩, 탈지분유 등):")

        st.markdown("### Ⅱ. 거래 형태 (복수선택 가능)")
        st.caption("[주의] 2가지 이상 납품 시 모두 체크하셔야 해당 폼이 활성화됩니다.")
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
        requires_inspection_sheet = t1 or t3 or t5 or t6

        if is_mfg or is_dist:
            guide_texts = []
            if t1 or t3:
                guide_texts.append("- 원재료 / OEM: [개별시트] 서류, 환경, 공정 등 제조 평가항목 27개 작성 대상 / [검사내용시트] 작성 대상 (성적서 대조)")
            if t2 or t4:
                guide_texts.append("- 부자재 / 세제류 외: [개별시트] 불필요 항목(CCP, 품목제조보고)이 자동 제외된 전용 폼 노출 / [검사내용시트] 규정에 따라 작성 면제")
            if t5:
                guide_texts.append("- 수입판매: [개별시트] 유통/수입 평가항목 4개 작성 대상 / [검사내용시트] 작성 대상 (COA 통관 기준)")
            if t6:
                guide_texts.append("- 국내유통(미제조): [개별시트] 유통/수입 평가항목 4개 작성 대상 / [검사내용시트] 작성 대상 (성적서 대조)")
            
            st.info("[안내] 선택하신 거래 형태별 제출 안내\n\n" + "\n".join(guide_texts))

        st.markdown("### Ⅳ. 인증상황")
        st.caption("[안내] 표의 빈칸을 더블클릭하여 내용을 선택하거나 입력하십시오.")
        cert_df_init = pd.DataFrame([
            {"인증명": "HACCP", "법적필수(O,X)": None, "인증대상": None, "최초인증일": None, "비고": None},
            {"인증명": "GMP", "법적필수(O,X)": None, "인증대상": None, "최초인증일": None, "비고": None},
            {"인증명": "FSSC22000", "법적필수(O,X)": None, "인증대상": None, "최초인증일": None, "비고": None},
            {"인증명": "ISO9001,14001", "법적필수(O,X)": None, "인증대상": None, "최초인증일": None, "비고": None},
            {"인증명": "기타", "법적필수(O,X)": None, "인증대상": None, "최초인증일": None, "비고": None}
        ])
        
        cert_df = st.data_editor(
            cert_df_init, 
            hide_index=True, 
            use_container_width=True, 
            key="cert_editor",
            column_config={
                "인증명": st.column_config.TextColumn("인증명", disabled=True),
                "법적필수(O,X)": st.column_config.SelectboxColumn(
                    "법적필수(O,X)",
                    options=["O", "X"],
                    required=False
                ),
                "최초인증일": st.column_config.DateColumn(
                    "최초인증일",
                    format="YYYY-MM-DD"
                )
            }
        )

        st.markdown("### Ⅴ. 변동사항")
        st.caption("[안내] 변동사항이 있을 시 체크하여 상세 내용을 기재해 주십시오.")
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
    # 탭 2: 개별 시트
    # ----------------------------------------
    mfg_data = {}
    dist_data = {}
    with tab2:
        if not is_mfg and not is_dist:
            st.info("[안내] [공통 시트] 탭에서 거래 형태를 먼저 선택해 주십시오.")

        if is_mfg:
            st.markdown("### [제조] 서류 심사 (증빙 자료 제출)")
            st.caption("[안내] 증빙자료 업로드 원칙: 품목제조보고서와 자가/공인 성적서는 '납품 전 품목', 나머지는 '최근 1개월 대표 샘플 1부'를 업로드합니다.")

            exp1_prefixes = ["mf1", "mf2", "mf4", "mf5", "mf6", "mf7", "mf8"]
            if t1 or t3:
                exp1_prefixes.insert(2, "mf3")
            exp1_completed = get_completed_count(exp1_prefixes)
            with st.expander(f"1. 서류관리 (총 {len(exp1_prefixes)}개 항목 / {exp1_completed}개 완료)", expanded=True):
                mfg_data["영업신고"] = render_upload_block("(1) 영업허가증/신고증", "mf1", "사업현황 및 생산제품 유형 일치 여부 확인", is_editable=False)
                mfg_data["인증서"] = render_upload_block("(2) 인증서 종류별 (HACCP, ISO 등)", "mf2", "인증 사항 일치 및 유효기간 만료 여부 확인", is_editable=False)
                
                if t1 or t3:
                    mfg_data["품목제조보고"] = render_upload_block("(3) 품목제조보고서", "mf3", "제품명/원료/유통기한 신고 내역 일치 여부", is_editable=False)
                
                mfg_data["원료수불부"] = render_upload_block("(4) 원료수불부", "mf4", "원료 입고/출고/사용 기록 매일 작성 및 누락 여부", is_editable=False)
                mfg_data["자가품질검사"] = render_upload_block("(5) 자가/공인 검사 성적서 (납품 전 품목)", "mf5", "주기적 실시 및 전 항목 적합 판정 여부", is_editable=False)
                mfg_data["건강진단"] = render_upload_block("(6) 건강진단서 (보건증)", "mf6", "종사자 전원 실시 및 유효기간 이탈 여부", is_editable=False)
                mfg_data["위생교육"] = render_upload_block("(7) 법정 교육 수료증", "mf7", "영업자 위생교육 이수 여부", is_editable=False)
                mfg_data["수질검사"] = render_upload_block("(8) 수질검사 성적서 (지하수 사용 등 해당 업체만)", "mf8", "용수 전 항목 적합 여부", is_editable=False)

            exp2_prefixes = [f"mf{i}" for i in range(9, 18)]
            exp2_completed = get_completed_count(exp2_prefixes)
            with st.expander(f"2. 환경 및 시설관리 (총 {len(exp2_prefixes)}개 항목 / {exp2_completed}개 완료)", expanded=False):
                mfg_data["구분구획"] = render_upload_block("(1) 작업장 평면도/설비 배치도", "mf9", "구획/구분 표시 여부 및 설비 배치 적절성", is_editable=False)
                mfg_data["환기/청정도"] = render_upload_block("(2) 환기시설 이력카드 및 공중낙하세균 일지", "mf10", "예: 낙하세균 30 CFU 이하 유지 여부", is_editable=True)
                mfg_data["조명관리"] = render_upload_block("(3) 조도관리일지", "mf11", "예: 일반 220Lux 이상, 검사 540Lux 이상 유지 여부", is_editable=True)
                mfg_data["청결관리"] = render_upload_block("(4) 세척/소독 기준서 및 CIP 기준서", "mf12", "작업장 및 설비 세척/소독 기준 수립 및 실시 여부", is_editable=False)
                mfg_data["설비_온도"] = render_upload_block("(5) 냉장/냉동 온도기록일지", "mf13", "예: 냉장 10도 이하, 냉동 -18도 이하 한계기준 이탈 여부", is_editable=True)
                mfg_data["설비_검교정"] = render_upload_block("(6) 검교정 계획표 및 일지", "mf14", "예: 계측기 유효기간 이내 및 오차범위 ±1도 충족 여부", is_editable=True)
                mfg_data["보관관리"] = render_upload_block("(7) 시설사진(MSDS) 및 제품 보관기준서", "mf15", "화학물질 별도 보관 및 원/부재료 기준 적합 보관 여부", is_editable=False)
                mfg_data["저수시설"] = render_upload_block("(8) 저수조 청소 필증", "mf16", "연 1회 이상 세척/소독 실시 여부", is_editable=False)
                mfg_data["부대시설"] = render_upload_block("(9) 화장실 시설 사진", "mf17", "손세척 및 환기 시설 구비 여부", is_editable=False)

            exp3_prefixes = ["mf18"]
            exp3_completed = get_completed_count(exp3_prefixes)
            with st.expander(f"3. 방충·방서관리 (총 1개 항목 / {exp3_completed}개 완료)", expanded=False):
                mfg_data["방충방서"] = render_upload_block("(1) 방충방서 소독 일지", "mf18", "매월 정기 소독 실시 및 기록 여부", is_editable=False)

            exp4_prefixes = ["mf20", "mf21", "mf22"]
            if t1 or t3:
                exp4_prefixes.insert(0, "mf19")
            exp4_completed = get_completed_count(exp4_prefixes)
            with st.expander(f"4. 공정 및 규격관리 (총 {len(exp4_prefixes)}개 항목 / {exp4_completed}개 완료)", expanded=False):
                if t1 or t3:
                    mfg_data["공정관리"] = render_upload_block("(1) 각 공정별 공정관리일지 (CCP 일지)", "mf19", "예: 가열 121도 15분 이상 등 업체 설정 한계기준 100% 충족 여부", is_editable=True)
                
                mfg_data["완제품관리"] = render_upload_block("(2) 완제품 검 일지", "mf20", "규격 검사 실시 및 전 항목 적합 여부", is_editable=False)
                mfg_data["원부자재관리"] = render_upload_block("(3) 입고검사일지 및 협력업체 점검표", "mf21", "입고 시 기준 부합 검사 및 성적서(GMO등) 수취 여부", is_editable=False)
                mfg_data["클레임관리"] = render_upload_block("(4) 클레임 관리일지", "mf22", "부적합 발생 내역 및 개선조치 기록 여부", is_editable=False)

            exp5_prefixes = ["mf23", "mf24"]
            exp5_completed = get_completed_count(exp5_prefixes)
            with st.expander(f"5. 작업자관리 (총 2개 항목 / {exp5_completed}개 완료)", expanded=False):
                mfg_data["개인위생"] = render_upload_block("(1) 작업장 출입절차 및 개인위생관리일지", "mf23", "위생복/장신구 등 작업자 위생 상태 양호 여부", is_editable=False)
                mfg_data["위생교육일지"] = render_upload_block("(2) 자체 위생교육일지", "mf24", "작업자 대상 위생교육 주기적 실시 여부", is_editable=False)

        if is_dist:
            st.markdown("### [유통/수입] 평가항목 서류 및 기준 입력")
            exp_dist_prefixes = ["df1", "df2", "df3", "df4"]
            exp_dist_completed = get_completed_count(exp_dist_prefixes)
            with st.expander(f"유통 서류 관리 (총 4개 항목 / {exp_dist_completed}개 완료)", expanded=True):
                dist_data["수입신고필증"] = render_upload_block("(1) 수입신고필증 및 COA", "df1", "수입신고 내역 일치 및 COA 제출 여부", is_editable=False)
                dist_data["제조사성적서"] = render_upload_block("(2) 제조사 자가/공인 성적서 (납품 전 품목)", "df2", "수령 주기 확인 및 검사결과 적합 여부", is_editable=False)
                dist_data["차량타코메타"] = render_upload_block("(3) 차량 타코메타 기록지", "df3", "예: 차량 온도 10도 이하 한계 이탈 여부 확인", is_editable=True)
                dist_data["클레임일지"] = render_upload_block("(4) 부적합(클레임) 관리 대장", "df4", "부적합품 식별 표시 및 반품 처리 내역 확인", is_editable=False)

    # ----------------------------------------
    # 탭 3: 검사내용 시트
    # ----------------------------------------
    mfg_df, dist_df = pd.DataFrame(), pd.DataFrame()
    mfg_coa_file, dist_coa_file = None, None
    mfg_coa_na, dist_coa_na = False, False
    mfg_coa_na_reason, dist_coa_na_reason = "", ""
    
    with tab3:
        if not is_mfg and not is_dist:
            st.info("[안내] [공통 시트] 탭에서 거래 형태를 먼저 선택해 주십시오.")
        elif not requires_inspection_sheet:
            st.success("귀하의 거래 형태(부자재 또는 세제류 외)는 매뉴얼 규정에 따라 [검사내용 시트] 작성이 면제됩니다. 하단의 최종 제출 버튼을 눌러주십시오.")
        else:
            if t1 or t3 or t6:
                st.markdown("### [제조/국내유통] 법적 기준 입력 및 성적서 대조")
                mfg_df = st.data_editor(pd.DataFrame([{"제품명": "", "검사항목(예: 납)": "", "법적기준(예: 3.5이하)": "", "자가검사수치": ""}]), num_rows="dynamic", key="mdf")
                mfg_coa_na = st.checkbox("해당사항 없음 (N/A) - 검사성적서", key="mfg_coa_na")
                if mfg_coa_na:
                    mfg_coa_na_reason = st.text_input("검사성적서 해당사항 없음 사유:", key="mfg_coa_na_reason")
                mfg_coa_file = st.file_uploader("위 표와 대조할 자가/공인 검사 성적서 원본 업로드", key="mdf_file", disabled=mfg_coa_na)

            if t5:
                st.markdown("### [수입판매] COA 통관 검사 기준 입력")
                dist_df = st.data_editor(pd.DataFrame([{"제품명": "", "COA검사항목": "", "COA법적기준": "", "수입시검사수치": ""}]), num_rows="dynamic", key="ddf")
                dist_coa_na = st.checkbox("해당사항 없음 (N/A) - COA", key="dist_coa_na")
                if dist_coa_na:
                    dist_coa_na_reason = st.text_input("COA 해당사항 없음 사유:", key="dist_coa_na_reason")
                dist_coa_file = st.file_uploader("위 표와 대조할 수입 COA 성적서 원본 업로드", key="ddf_file", disabled=dist_coa_na)

    # ==========================================
    # 최종 통합 제출 버튼
    # ==========================================
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.markdown("### 작성 완료 후 일괄 검증 제출")

    if st.button("모든 시트 작성 완료 및 최종 일괄 제출 (AI 심사)", type="primary", use_container_width=True):
        validation_failed = False
        
        if company_name == "선택하세요":
            st.error("오류: 공통 시트 탭에서 업체명을 반드시 선택해 주십시오.")
            validation_failed = True
        elif not is_mfg and not is_dist:
            st.error("오류: 공통 시트 탭에서 거래 형태를 최소 1개 이상 선택해 주십시오.")
            validation_failed = True

        if not validation_failed:
            cert_summary_list = []
            for idx, row in cert_df.iterrows():
                if pd.notna(row['법적필수(O,X)']) or pd.notna(row['인증대상']) or pd.notna(row['최초인증일']):
                    cert_summary_list.append(f"[{row['인증명']}] 필수:{row['법적필수(O,X)']}, 대상:{row['인증대상']}, 인증일:{row['최초인증일']}, 비고:{row['비고']}")
            cert_str = "\n".join(cert_summary_list) if cert_summary_list else "입력된 인증 내역 없음"

            changes_summary = []
            if v_item: changes_summary.append(f"거래품목 변동: {v_item_detail}")
            if v_type: changes_summary.append(f"유형 변동: {v_type_detail}")
            if v_insp: changes_summary.append(f"검사항목 변동: {v_insp_detail}")
            changes_str = " / ".join(changes_summary) if changes_summary else "해당사항 없음"

            tasks = []
            instant_logs = []

            def process_doc_submission(doc_name, data):
                if data["is_na"]:
                    if not data["na_reason"]:
                        st.error(f"오류: '{doc_name}'의 해당사항 없음 사유를 입력해 주십시오.")
                        return False
                    instant_logs.append({
                        "doc_name": doc_name, "criteria": data["criteria"],
                        "judgment": "만점 부여", "reason": f"해당사항 없음: {data['na_reason']}",
                        "admin_score": "만점 (해당사항 없음)", "file": None
                    })
                elif data["file"] is None:
                    instant_logs.append({
                        "doc_name": doc_name, "criteria": data["criteria"],
                        "judgment": "0점 처리", "reason": "필수 파일 미제출 (누락)",
                        "admin_score": "0점 (미제출)", "file": None
                    })
                else:
                    tasks.append({"doc_name": doc_name, "criteria": data["criteria"], "file": data["file"]})
                return True

            if is_mfg:
                for doc_key, data in mfg_data.items():
                    if not process_doc_submission(f"[제조] {doc_key}", data):
                        validation_failed = True

            if requires_inspection_sheet:
                if t1 or t3 or t6:
                    if mfg_coa_na:
                        if not mfg_coa_na_reason:
                            st.error("오류: 제조/국내유통 검사성적서의 해당사항 없음 사유를 입력해 주십시오.")
                            validation_failed = True
                        else:
                            instant_logs.append({
                                "doc_name": "[제조] 최종 검사성적서", "criteria": "N/A",
                                "judgment": "만점 부여", "reason": f"해당사항 없음: {mfg_coa_na_reason}",
                                "admin_score": "만점 (해당사항 없음)", "file": None
                            })
                    elif mfg_coa_file is None:
                        instant_logs.append({
                            "doc_name": "[제조] 최종 검사성적서", "criteria": "성적서 대조",
                            "judgment": "0점 처리", "reason": "필수 검사성적서 미제출",
                            "admin_score": "0점 (미제출)", "file": None
                        })
                    else:
                        grid_data = mfg_df.to_dict('records')
                        tasks.append({"doc_name": "[제조] 최종 검사성적서", "criteria": f"입력된 법적기준({grid_data})과 성적서 수치 일치/통과 여부 대조", "file": mfg_coa_file})

            if is_dist:
                for doc_key, data in dist_data.items():
                    if not process_doc_submission(f"[유통] {doc_key}", data):
                        validation_failed = True
                    
                if dist_coa_na:
                    if not dist_coa_na_reason:
                        st.error("오류: 수입 COA 성적서의 해당사항 없음 사유를 입력해 주십시오.")
                        validation_failed = True
                    else:
                        instant_logs.append({
                            "doc_name": "[수입] COA 검사성적서", "criteria": "N/A",
                            "judgment": "만점 부여", "reason": f"해당사항 없음: {dist_coa_na_reason}",
                            "admin_score": "만점 (해당사항 없음)", "file": None
                        })
                elif dist_coa_file is None:
                    instant_logs.append({
                        "doc_name": "[수입] COA 검사성적서", "criteria": "COA 성적서 대조",
                        "judgment": "0점 처리", "reason": "필수 COA 성적서 미제출",
                        "admin_score": "0점 (미제출)", "file": None
                    })
                else:
                    grid_data = dist_df.to_dict('records')
                    tasks.append({"doc_name": "[수입] COA 검사성적서", "criteria": f"입력된 COA기준({grid_data})과 성적서 수치 대조", "file": dist_coa_file})

            if not validation_failed:
                if not tasks and not instant_logs:
                    st.warning("제출할 항목이 구성되지 않았습니다. 거래 형태를 다시 확인해 주십시오.")
                else:
                    progress_text = "서류 제출 및 검증이 진행 중입니다. 잠시만 기다려주십시오..."
                    my_bar = st.progress(0, text=progress_text)

                    total_expected = len(tasks) + len(instant_logs)
                    current_idx = 0
                    
                    pass_count = 0
                    fail_count = 0
                    na_count = 0

                    current_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    formatted_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    for log in instant_logs:
                        current_idx += 1
                        unique_id = f"{company_name}_{log['doc_name']}_{current_time_str}"
                        
                        if "만점" in log["judgment"]:
                            pass_count += 1
                            if "해당사항 없음" in log["reason"]:
                                na_count += 1
                        else:
                            fail_count += 1
                        
                        row_data = [unique_id, formatted_time, company_name, log["doc_name"], log["criteria"], log["judgment"], log["reason"], log["admin_score"], "첨부파일 없음", manager_name, manager_email, biz_type, delivered_items, cert_str, changes_str]
                        append_to_google_sheet(row_data)
                        my_bar.progress(current_idx / total_expected, text=f"({current_idx}/{total_expected}) {log['doc_name']} 처리 중...")

                    for task in tasks:
                        current_idx += 1
                        doc_name = task["doc_name"]
                        file_obj = task["file"]
                        criteria = task["criteria"]

                        try:
                            unique_id = f"{company_name}_{doc_name}_{current_time_str}"
                            file_name = f"{unique_id}_{file_obj.name}"
                            file_buffer = io.BytesIO(file_obj.getvalue())

                            drive_link = upload_to_google_drive(file_buffer, file_name, file_obj.type)
                            
                            prompt = f"""당신은 엄격한 식품안전 품질 심사관입니다.
                            [평가 대상 업체 정보]
                            - 신고된 영업의 종류: {biz_type}
                            - 납품 예정 품목: {delivered_items}

                            [심사항목]: {doc_name}
                            [업체 자체 관리 기준(반드시 지켜야 할 기준치)]: {criteria}

                            지시사항:
                            1. 첨부된 이미지/문서를 읽고, 기록된 모든 데이터를 꼼꼼히 스캔하십시오.
                            2. [특별 지시] 심사항목이 '영업허가증/신고증' 또는 '품목제조보고서'일 경우, 제출된 서류상에 적힌 '업종(영업의 종류)'이 신고된 [{biz_type}]과 정확히 일치하는지 반드시 확인하십시오. (예: 식품제조가공업을 제출해야 하는데 축산물가공업 허가증을 제출한 경우 등 일치하지 않으면 즉시 0점 처리). 또한 문서의 내용이 [{delivered_items}]와 관련이 있는지 교차 검증하십시오.
                            3. 사용자가 제시한 [업체 자체 관리 기준]에 명시된 수치와 문서의 실제 기록을 완벽하게 대조하십시오.
                            4. 단 1회라도 기준 범위를 벗어나거나(이탈), 누락되었거나, 부적합한 내용이 기록되어 있다면 무조건 '0점 처리' 하십시오.
                            5. 모든 기록이 기준 수치를 100% 충족하고 정상일 때만 '만점 부여'로 판정하십시오.

                            출력양식:
                            판정결과: (만점 부여 또는 0점 처리)
                            상세사유: (문서에서 발견한 정확한 팩트 수치나 이탈 상태를 근거로 사유 기재)"""

                            judgment, reason, admin_score = analyze_document_with_ai(prompt, file_obj.getvalue(), file_obj.type)

                            if "만점" in judgment:
                                pass_count += 1
                            else:
                                fail_count += 1

                            row_data = [unique_id, formatted_time, company_name, doc_name, criteria, judgment, reason, admin_score, drive_link, manager_name, manager_email, biz_type, delivered_items, cert_str, changes_str]
                            append_to_google_sheet(row_data)

                        except Exception as e:
                            st.error(f"{doc_name} 검증 중 오류 발생: {e}")

                        my_bar.progress(current_idx / total_expected, text=f"({current_idx}/{total_expected}) {doc_name} 검증 완료...")

                    my_bar.empty()
                    
                    total_evaluated = pass_count + fail_count
                    comp_score = int((pass_count / total_evaluated) * 100) if total_evaluated > 0 else 0
                    
                    st.success(f"성공: 모든 서류에 대한 자동 검증(N/A 기본 통과 처리 및 미제출 패널티 적용)이 완료되었습니다.\n\n"
                               f"[{company_name}] 종합 심사 결과: 환산 총점 {comp_score}점 (통과 {pass_count}건 / 미비 및 누락 {fail_count}건 / 평가 면제 {na_count}건)")

# ==========================================
# [5] 관리자 대시보드
# ==========================================
elif menu == "관리자 대시보드 (육안 재확인 및 수정)":
    st.title("품질 관리 책임자 최종 검증 대시보드")
    admin_pw = st.text_input("관리자 비밀번호:", type="password")

    if admin_pw == "2082":
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
                time_col = log_df.columns[1]
                log_df[time_col] = pd.to_datetime(log_df[time_col], errors='coerce')
                
                valid_dates = log_df[log_df[time_col].notnull()]
                if not valid_dates.empty:
                    min_date = valid_dates[time_col].min().date()
                    max_date = valid_dates[time_col].max().date()
                else:
                    min_date = datetime.date.today()
                    max_date = datetime.date.today()

                st.markdown("### 심사 기간 필터링")
                date_range = st.date_input("조회할 심사 기간을 선택하십시오:", value=(min_date, max_date), min_value=min_date, max_value=max_date)
                
                if len(date_range) == 2:
                    start_date, end_date = date_range
                    mask = (log_df[time_col].dt.date >= start_date) & (log_df[time_col].dt.date <= end_date)
                    filtered_df = log_df.loc[mask]
                else:
                    filtered_df = log_df

                # 제출 현황 파악 기능 추가
                st.markdown("### 1. 심사 서류 제출 현황 파악")
                all_targets = [c for c in TARGET_COMPANIES if c != "선택하세요"]
                submitted_set = set(filtered_df['업체명'].dropna().unique())
                
                submitted_list = [c for c in all_targets if c in submitted_set]
                pending_list = [c for c in all_targets if c not in submitted_set]
                
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("전체 심사 대상 업체", f"{len(all_targets)}개")
                col_b.metric("제출 완료 업체", f"{len(submitted_list)}개")
                col_c.metric("미제출 대기 업체", f"{len(pending_list)}개")
                
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    with st.expander("제출 완료 업체 세부 목록"):
                        for comp in submitted_list:
                            st.write(comp)
                with col_s2:
                    with st.expander("미제출 대기 업체 세부 목록"):
                        for comp in pending_list:
                            st.write(comp)
                
                extra_submitted = [c for c in submitted_set if c not in all_targets]
                if extra_submitted:
                    st.caption("목록 외 추가 제출 업체: " + ", ".join(extra_submitted))

                st.markdown("---")

                if filtered_df.empty:
                    st.warning("해당 기간에 접수된 심사 데이터가 없습니다.")
                else:
                    company_scores = {}
                    for company in filtered_df['업체명'].unique():
                        comp_df = filtered_df[filtered_df['업체명'] == company]
                        pass_docs = comp_df['관리자최종점수'].str.contains("만점", na=False).sum()
                        fail_docs = comp_df['관리자최종점수'].str.contains("0점", na=False).sum()
                        
                        total_evaluated = pass_docs + fail_docs
                        score = int((pass_docs / total_evaluated) * 100) if total_evaluated > 0 else 0

                        if score >= 85: grade = "승인"
                        elif score >= 70: grade = "지도"
                        else: grade = "등급 외"

                        biz_type_val = comp_df['영업의종류'].iloc[-1] if '영업의종류' in comp_df.columns else ""
                        item_val = comp_df['납품품목'].iloc[-1] if '납품품목' in comp_df.columns else ""

                        company_scores[company] = {
                            "score": score,
                            "grade": grade,
                            "biz_type": biz_type_val,
                            "item": item_val
                        }

                    grade_counts = {"승인": 0, "지도": 0, "등급 외": 0}
                    for data in company_scores.values():
                        grade_counts[data["grade"]] += 1

                    top_table_data = [
                        {"등 급": "승 인", "점 수": "85 ~ 100점", "업 체 수": grade_counts["승인"], "조 치": "승 인"},
                        {"등 급": "지 도", "점 수": "70 ~ 84점", "업 체 수": grade_counts["지도"], "조 치": "업체별 개선사항 피드백"},
                        {"등 급": "등급 외", "점 수": "70점미만, 미제출", "업 체 수": grade_counts["등급 외"], "조 치": "복수거래, 거래중지 등 검토"},
                        {"등 급": "합 계", "점 수": "", "업 체 수": sum(grade_counts.values()), "조 치": "-"}
                    ]
                    
                    st.markdown("### 2. 품질안전부문 실무 평가 보고 (요약)")
                    st.dataframe(pd.DataFrame(top_table_data), hide_index=True, use_container_width=True)

                    st.markdown("<br>", unsafe_allow_html=True)

                    bottom_table_data = []
                    for idx, (company, data) in enumerate(company_scores.items(), 1):
                        bottom_table_data.append({
                            "NO": idx,
                            "구분": data["biz_type"],
                            "업체명": company,
                            "품목": data["item"],
                            "점수": data["score"],
                            "결과": data["grade"],
                            "비고": ""
                        })

                    st.markdown("### 3. 업체별 평가 결과 상세")
                    st.dataframe(pd.DataFrame(bottom_table_data), hide_index=True, use_container_width=True)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        summary_excel_df = pd.DataFrame(top_table_data)
                        summary_excel_df.to_excel(writer, sheet_name='서류점검결과', index=False, startrow=0)
                        
                        detail_excel_df = pd.DataFrame(bottom_table_data)
                        detail_excel_df.to_excel(writer, sheet_name='서류점검결과', index=False, startrow=len(summary_excel_df) + 3)
                        
                    st.download_button(
                        label="현재 필터링된 결과 보고서 엑셀 다운로드",
                        data=output.getvalue(),
                        file_name=f"협력업체_서류점검_결과_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    st.markdown("---")
                    
                    st.markdown("### 4. 업체별 상세 조회 및 담당자 정보 확인")
                    selected_info_company = st.selectbox("조회할 업체를 선택하십시오 (선택 시 하단 목록이 해당 업체 기준으로 필터링됩니다):", ["전체 보기"] + list(filtered_df['업체명'].unique()))
                    
                    if selected_info_company != "전체 보기":
                        comp_df = filtered_df[filtered_df['업체명'] == selected_info_company]
                        contact_manager = comp_df['담당자명'].iloc[-1] if '담당자명' in comp_df.columns and pd.notna(comp_df['담당자명'].iloc[-1]) and str(comp_df['담당자명'].iloc[-1]).strip() != "" else "기록 없음"
                        contact_email = comp_df['담당자이메일'].iloc[-1] if '담당자이메일' in comp_df.columns and pd.notna(comp_df['담당자이메일'].iloc[-1]) and str(comp_df['담당자이메일'].iloc[-1]).strip() != "" else "기록 없음"
                        st.info(f"[{selected_info_company}] 담당자명: {contact_manager} | 이메일: {contact_email}")
                        
                        display_df = comp_df
                        zero_score_df = comp_df[comp_df['관리자최종점수'].str.contains("0점", na=False)]
                        na_score_df = comp_df[comp_df['관리자최종점수'].str.contains("해당사항 없음", na=False)]
                    else:
                        display_df = filtered_df
                        zero_score_df = filtered_df[filtered_df['관리자최종점수'].str.contains("0점", na=False)]
                        na_score_df = filtered_df[filtered_df['관리자최종점수'].str.contains("해당사항 없음", na=False)]
                    
                    st.markdown("---")

                    st.markdown("### 5. 관리자 최종 점수 일괄 수정 (해당사항 없음 사유 검토)")
                    
                    if na_score_df.empty:
                        if selected_info_company != "전체 보기":
                            st.success(f"[알림] [{selected_info_company}] 업체는 육안으로 타당성을 검토할 해당사항 없음(N/A) 제출 건이 없습니다.")
                        else:
                            st.success("[알림] 필터링된 기간 내 전체 업체 중 육안으로 타당성을 검토할 해당사항 없음(N/A) 제출 건이 없습니다.")
                    else:
                        target_na_id = st.selectbox("타당성을 검토할 고유ID를 선택하세요 (해당사항 없음 검토용):", ["선택하세요"] + na_score_df['고유ID'].tolist())
                        
                        if target_na_id != "선택하세요":
                            target_na_row = na_score_df[na_score_df['고유ID'] == target_na_id].iloc[0]
                            
                            st.info(f"업체 제출 사유: {target_na_row.get('AI상세사유', '사유 없음')}")
                            
                            col_na1, col_na2 = st.columns(2)
                            with col_na1:
                                new_na_status = st.selectbox("수정할 점수를 선택하세요:", ["유지 (만점 처리 타당함)", "0점 (관리자 최종 반려 - 사유 부적합)"], key="na_status")
                            with col_na2:
                                na_admin_memo = st.text_input("수정 사유 입력 (선택):", key="na_memo")

                            if st.button("해당사항 없음 검토 결과 구글 시트 반영"):
                                if "0점" in new_na_status:
                                    memo_text = f"{new_na_status} / 사유: {na_admin_memo}" if na_admin_memo else new_na_status
                                    if update_google_sheet_admin_score(target_na_id, memo_text) == True:
                                        st.success(f"'{target_na_id}' 건이 부적합 판단되어 0점으로 강등 처리되었습니다.")
                                        st.rerun()
                                else:
                                    st.info("해당사항 없음 사유가 타당하여 기존 점수(만점)가 유지됩니다.")

                    st.markdown("---")

                    st.markdown("### 6. 관리자 최종 점수 일괄 수정 (미비 서류 검토)")
                    
                    if zero_score_df.empty:
                        if selected_info_company != "전체 보기":
                            st.success(f"[알림] [{selected_info_company}] 업체는 육안으로 재확인하여 점수를 수정할 0점 처리 건이 없습니다.")
                        else:
                            st.success("[알림] 필터링된 기간 내 전체 업체 중 육안으로 재확인하여 점수를 수정할 0점 처리 건이 없습니다.")
                    else:
                        target_id = st.selectbox("수정할 건의 고유ID를 선택하세요 (0점 처리 건 검토용):", ["선택하세요"] + zero_score_df['고유ID'].tolist())
                        
                        if target_id != "선택하세요":
                            target_row = zero_score_df[zero_score_df['고유ID'] == target_id].iloc[0]
                            drive_url = target_row.get('드라이브링크', '#')
                            
                            st.error(f"[0점 처리 사유] {target_row.get('AI상세사유', '사유 없음')}")
                            
                            if drive_url != "첨부파일 없음":
                                st.markdown(f"**[제출된 파일 직접 확인하기 (클릭 시 새 창 열림)]({drive_url})**")
                            else:
                                st.warning("[주의] 미제출로 인해 첨부된 파일이 없습니다.")
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            col1, col2 = st.columns(2)
                            with col1:
                                new_status = st.selectbox("수정할 점수를 선택하세요:", ["만점 (관리자 육안 확인 통과)", "0점 (관리자 최종 반려)"])
                            with col2:
                                admin_memo = st.text_input("수정 사유 입력 (선택):")

                            if st.button("최종 점수 구글 시트 반영"):
                                memo_text = f"{new_status} / 사유: {admin_memo}" if admin_memo else new_status
                                if update_google_sheet_admin_score(target_id, memo_text) == True:
                                    st.success(f"해당 건의 최종 점수가 성공적으로 수정되었습니다.")
                                    st.rerun()

                    st.markdown("---")
                    
                    if selected_info_company != "전체 보기":
                        st.markdown(f"### 7. [{selected_info_company}] 전체 심사 이력 (만점/미비/면제 포함)")
                    else:
                        st.markdown("### 7. 실시간 전체 심사 이력 (필터링됨)")
                        
                    st.dataframe(
                        display_df, 
                        use_container_width=True,
                        column_config={
                            "드라이브링크": st.column_config.LinkColumn("드라이브링크")
                        }
                    )
        except Exception as e:
            st.error(f"데이터베이스 연결 오류: {e}")
    elif admin_pw != "":
        st.error("비밀번호가 일치하지 않습니다.")
