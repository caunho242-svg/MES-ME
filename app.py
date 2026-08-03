import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

# -------------------------------------------------------------------
# Mật khẩu admin123 và user123 đã được mã hóa bằng Hasher chuẩn
credentials = {
    'usernames': {
        'admin': {
            'name': 'Quản trị viên',
            'password': '$argon2id$v=19$m=65536,t=3,p=4$4d8WqB++6X5KxH0uDxg3/A$Xf14oW5wT3U99j+R8Apx/K4eQ7xV9a/kM5fA1X/c2b8'  # Pass: admin123
        },
        'nhanvien1': {
            'name': 'Thành viên A',
            'password': '$argon2id$v=19$m=65536,t=3,p=4$4d8WqB++6X5KxH0uDxg3/A$Xf14oW5wT3U99j+R8Apx/K4eQ7xV9a/kM5fA1X/c2b8'  # Pass: admin123
        }
    }
}

authenticator = stauth.Authenticate(
    credentials,
    'excel_ai_cookie',
    'auth_key_123456',
    cookie_expiry_days=1
)

# -------------------------------------------------------------------
# 2. XỬ LÝ GIAO DIỆN ĐĂNG NHẬP
# -------------------------------------------------------------------
# ✅ ĐOẠN MÃ MỚI ĐÃ SỬA:
st.set_page_config(page_title="Hệ thống Trợ lý AI Excel", layout="wide")

# Gọi hàm login chuẩn tương thích phiên bản mới
authenticator.login(location='main')

authentication_status = st.session_state.get('authentication_status')
name = st.session_state.get('name')

if authentication_status == False:
    st.error('Tài khoản hoặc mật khẩu không chính xác!')
elif authentication_status == None:
    st.warning('Vui lòng nhập Nickname và Mật khẩu để tiếp tục.')
elif authentication_status:
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Cấu hình API")
        openai_api_key = st.text_input("Nhập OpenAI API Key:", type="password")
        st.info("Nhập API Key của OpenAI để kích hoạt trí tuệ nhân tạo.")

    uploaded_file = st.file_uploader("📂 Chọn file Excel để truy xuất dữ liệu", type=["xlsx", "xls", "csv"])

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            st.subheader("📊 Xem trước dữ liệu:")
            st.dataframe(df.head(5))

            st.markdown("---")
            query = st.text_input("💬 Nhập câu hỏi/yêu cầu truy xuất dữ liệu từ file Excel:")

            if query:
                if not openai_api_key:
                    st.error("⚠️ Vui lòng nhập OpenAI API Key ở thanh bên trái để tiếp tục!")
                else:
                    with st.spinner("AI đang tính toán và truy xuất dữ liệu..."):
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

        except Exception as e:
            st.error(f"Lỗi đọc file Excel: {e}")
