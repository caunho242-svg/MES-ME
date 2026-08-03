import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
import os
import json

# -------------------------------------------------------------------
# 1. HỆ THỐNG QUẢN LÝ DỮ LIỆU TÀI KHOẢN (JSON)
# -------------------------------------------------------------------
USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        # Nếu đã có file, tải danh sách tài khoản (đã được mã hóa mật khẩu)
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # Nếu chưa có, tạo tài khoản Admin mặc định
        default_creds = {
            'usernames': {
                'admin': {
                    'name': 'Quản trị viên',
                    'password': 'admin123',
                    'role': 'admin' # Quyền cao nhất
                }
            }
        }
        # Mã hóa mật khẩu lần đầu và lưu file
        stauth.Hasher.hash_passwords(default_creds)
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(default_creds, f, ensure_ascii=False, indent=4)
        return default_creds

def save_users(creds):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, ensure_ascii=False, indent=4)

# -------------------------------------------------------------------
# 2. XỬ LÝ GIAO DIỆN ĐĂNG NHẬP
# -------------------------------------------------------------------
st.set_page_config(page_title="Hệ thống Trợ lý AI Excel", layout="wide")

# Tải credentials từ file JSON
credentials = load_users()

authenticator = stauth.Authenticate(
    credentials,
    'excel_ai_cookie',
    'auth_key_123456',
    cookie_expiry_days=1
)

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
    # 3. GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
    # -------------------------------------------------------------------
    authenticator.logout('Đăng xuất', 'sidebar')
    st.title(f"🤖 Trợ lý AI Truy xuất Dữ liệu - Xin chào {name}!")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Cấu hình API")
        openai_api_key = st.text_input("Nhập OpenAI API Key:", type="password")
        st.info("Lưu ý: API Key không được lưu lại để đảm bảo bảo mật.")

    df = None 
    # Xác định quyền của người dùng hiện tại
    user_role = credentials['usernames'][username].get('role', 'user')

    # ================= KHU VỰC DÀNH RIÊNG CHO ADMIN =================
    if user_role == 'admin':
        st.success("👑 Quyền Quản trị viên")
        
        # Chia giao diện làm 2 Tab
        tab1, tab2 = st.tabs(["📂 Cập nhật Dữ liệu", "👥 Quản lý Tài khoản (Cấp quyền)"])
        
        with tab1:
            uploaded_file = st.file_uploader("📂 Chọn file dữ liệu (Excel/CSV) để cập nhật", type=["xlsx", "xls", "csv"])
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                df.to_csv("data_server.csv", index=False)
                st.success("✅ Đã cập nhật cơ sở dữ liệu chung cho toàn bộ nhân viên!")
            elif os.path.exists("data_server.csv"):
                df = pd.read_csv("data_server.csv")

        with tab2:
            st.subheader("➕ Cấp tài khoản mới cho nhân viên")
            with st.form("new_user_form", clear_on_submit=True):
                new_user = st.text_input("Tên đăng nhập (Username):", placeholder="VD: nhanvien2")
                new_name = st.text_input("Tên hiển thị:", placeholder="VD: Trần Văn B")
                new_pass = st.text_input("Mật khẩu:", type="password")
                
                submitted = st.form_submit_button("Tạo tài khoản")
                if submitted:
                    if new_user == "" or new_pass == "":
                        st.error("⚠️ Vui lòng nhập đầy đủ Username và Mật khẩu!")
                    elif new_user in credentials['usernames']:
                        st.error("⚠️ Tên đăng nhập này đã tồn tại!")
                    else:
                        # Mã hóa mật khẩu của nhân viên mới
                        temp_cred = {'usernames': {new_user: {'password': new_pass}}}
                        stauth.Hasher.hash_passwords(temp_cred)
                        hashed_pass = temp_cred['usernames'][new_user]['password']
                        
                        # Cấp quyền "user" mặc định cho tài khoản con
                        credentials['usernames'][new_user] = {
                            'name': new_name,
                            'password': hashed_pass,
                            'role': 'user'
                        }
                        save_users(credentials) # Lưu vào file
                        st.success(f"✅ Đã tạo tài khoản '{new_user}' thành công! Nhân viên có thể đăng nhập ngay.")
            
            st.subheader("📋 Danh sách tài khoản hiện có:")
            # Tạo bảng hiển thị danh sách tài khoản
            user_list = []
            for uname, info in credentials['usernames'].items():
                user_list.append({
                    "Username": uname, 
                    "Tên hiển thị": info.get('name', ''), 
                    "Quyền": "Quản trị viên" if info.get('role') == 'admin' else "Nhân viên tra cứu"
                })
            st.table(pd.DataFrame(user_list))

    # ================= KHU VỰC DÀNH CHO NHÂN VIÊN CON =================
    else:
        st.info("👤 Quyền Nhân viên: Bạn chỉ được phép tra cứu dữ liệu từ nguồn do Quản trị viên cập nhật.")
        if os.path.exists("data_server.csv"):
            df = pd.read_csv("data_server.csv")
        else:
            st.warning("⚠️ Quản trị viên chưa cập nhật cơ sở dữ liệu nào lên hệ thống.")

    # ================= KHU VỰC HỎI ĐÁP AI (CHUNG) =================
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
