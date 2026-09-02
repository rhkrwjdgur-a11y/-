# (수정 전) col_s1, col_s2 = st.columns(2)
                # ... (중략) ...
                # (수정 후) 아래 코드로 교체해 주세요.
                
                col_s1, col_s2, col_s3 = st.columns(3)
                
                with col_s1:
                    with st.expander("제출 완료 업체 세부 목록", expanded=True):
                        with st.container(height=200):
                            if not submitted_set:
                                st.write("해당 없음")
                            for comp in sorted(list(submitted_set)):
                                st.write(comp)
                                
                with col_s2:
                    with st.expander("심사 제외 업체 세부 목록", expanded=True):
                        with st.container(height=200):
                            if not exempt_set:
                                st.write("해당 없음")
                            for comp in sorted(list(exempt_set)):
                                st.write(comp)
                                
                with col_s3:
                    with st.expander("미제출 대기 업체 세부 목록", expanded=True):
                        with st.container(height=200):
                            if not pending_list:
                                st.write("해당 없음")
                            for comp in pending_list:
                                st.write(comp)
