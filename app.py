import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

# -------------------------------------------------------------------
# Tự động mã hóa mật khẩu bằng Hasher chuẩn của thư viện để tránh lỗi
hashed_passwords = stauth.Hasher(['admin123', 'user123']).generate()

credentials = {
    'usernames': {
        'admin': {
            'name': 'Quản trị viên',
            'password': hashed_passwords[0] # Tương ứng mật khẩu: admin123
        },
        'nhanvien1': {
            'name': 'Thành viên A',
            'password': hashed_passwords[1] # Tương ứng mật khẩu: user123
        }
    }
}
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
