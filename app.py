import os # Thêm thư viện quản lý file

# ... (Giữ nguyên phần cấu hình mật khẩu và đăng nhập ở trên) ...

elif authentication_status:
    authenticator.logout('Đăng xuất', 'sidebar')
    st.title(f"🤖 Trợ lý AI Truy xuất Dữ liệu - Xin chào {name}!")
    st.markdown("---")

    # 1. CẤU HÌNH API KEY (Chung)
    with st.sidebar:
        st.header("⚙️ Cấu hình API")
        openai_api_key = st.text_input("Nhập OpenAI API Key:", type="password")
        st.info("Lưu ý: API Key không được lưu lại để đảm bảo bảo mật.")

    # 2. PHÂN QUYỀN HIỂN THỊ VÀ XỬ LÝ DỮ LIỆU THEO TÀI KHOẢN
    df = None # Biến chứa dữ liệu chung

    if username == 'admin':
        st.success("👑 Quyền Quản trị viên: Bạn được phép tải dữ liệu mới lên hệ thống.")
        uploaded_file = st.file_uploader("📂 Chọn file dữ liệu mới (Excel/CSV) để cập nhật", type=["xlsx", "xls", "csv"])
        
        if uploaded_file is not None:
            # Đọc file upload
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            # Lưu đè dữ liệu xuống server dưới dạng CSV chuẩn hóa để tài khoản con đọc
            df.to_csv("data_server.csv", index=False)
            st.success("✅ Đã cập nhật cơ sở dữ liệu chung cho toàn bộ nhân viên!")
        
        # Nếu chưa tải file mới, tự động nạp lại file cũ nếu có
        elif os.path.exists("data_server.csv"):
            df = pd.read_csv("data_server.csv")

    else:
        # Giao diện dành cho tài khoản con (nhanvien1, nhanvien2...)
        st.info("👤 Quyền Nhân viên: Bạn chỉ được tra cứu dữ liệu đã được Quản trị viên cập nhật.")
        
        if os.path.exists("data_server.csv"):
            df = pd.read_csv("data_server.csv")
        else:
            st.warning("⚠️ Quản trị viên chưa cập nhật cơ sở dữ liệu nào lên hệ thống.")

    # 3. KHU VỰC TRUY XUẤT BẰNG AI (Chung cho những ai có dữ liệu)
    if df is not None:
        st.subheader("📊 Xem trước dữ liệu:")
        st.dataframe(df.head(5))

        st.markdown("---")
        query = st.text_input("💬 Nhập câu hỏi/yêu cầu truy xuất dữ liệu:")

        if query:
            if not openai_api_key:
                st.error("⚠️ Vui lòng nhập OpenAI API Key ở thanh bên trái để tiếp tục!")
            else:
                with st.spinner("AI đang xử lý..."):
                    try:
                        llm = ChatOpenAI(temperature=0, model="gpt-4o-mini", api_key=openai_api_key)
                        agent = create_pandas_dataframe_agent(
                            llm, 
                            df, 
                            verbose=True, 
                            allow_dangerous_code=True
                        )
                        response = agent.run(query)
                        st.success("✅ Kết quả:")
                        st.write(response)
                    except Exception as e:
                        st.error(f"Xảy ra lỗi trong quá trình xử lý: {e}")
