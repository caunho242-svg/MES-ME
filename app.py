import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
import os

# -------------------------------------------------------------------
# 1. CẤU HÌNH TÀI KHOẢN ĐĂNG NHẬP (USER & PASSWORD)
# -------------------------------------------------------------------
# 1. Khai báo tài khoản với mật khẩu GỐC
credentials = {
    'usernames': {
        'admin': {
            'name': 'Quản trị viên',
            'password': 'admin123' 
        },
        'nhanvien1': {
            'name': 'Thành viên A',
            'password': 'user123' 
        }
    }
}

# 2. Truyền toàn bộ biến credentials vào để thư viện tự động mã hóa
stauth.Hasher.hash_passwords(credentials)

authenticator = stauth.Authenticate(
    credentials,
    'excel_ai_cookie',
    'auth_key_123456',
    cookie_expiry_days=1
)

# -------------------------------------------------------------------
# 2. XỬ LÝ GIAO DIỆN ĐĂNG NHẬP
# -------------------------------------------------------------------
st.set_page_config(page_title="Hệ thống Trợ lý AI Excel", layout="wide")

# Gọi hàm login chuẩn tương thích phiên bản mới
authenticator.login(location='main')

authentication_status = st.session_state.get('authentication_status')
name = st.session_state.get('name')
username = st.session_state.get('username')

if authentication_status == False:
    st.error('Tài khoản hoặc mật khẩu không chính xác!')
elif authentication_status == None:
    st.warning('Vui lòng nhập Nickname và Mật khẩu để tiếp tục.')
elif authentication_status:
    # -------------------------------------------------------------------
    # 3. GIAO DIỆN CHÍNH SAU KHI ĐĂNG NHẬP THÀNH CÔNG
    # -------------------------------------------------------------------
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
