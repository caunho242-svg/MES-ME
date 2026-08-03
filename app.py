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
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        default_creds = {
            'usernames': {
                'admin': {
                    'name': 'Quản trị viên',
                    'password': 'admin123',
                    'role': 'admin',
                    'position': 'Quản lý',
                    'department': 'Hệ thống'
                }
            }
        }
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
    
    current_user_info = credentials['usernames'].get(username, {})
    current_position = current_user_info.get('position', 'Nhân viên')
    current_department = current_user_info.get('department', 'Chưa rõ')
    
    # Tiêu đề hiển thị: Tên (Chức vụ - Phòng ban)
    st.title(f"🤖 Trợ lý AI - Xin chào {name} ({current_position} - {current_department})!")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Cấu hình API")
        openai_api_key = st.text_input("Nhập OpenAI API Key:", type="password")
        st.info("Lưu ý: API Key không được lưu lại để đảm bảo bảo mật.")

    df = None 
    user_role = current_user_info.get('role', 'user')

    # ================= KHU VỰC DÀNH RIÊNG CHO ADMIN =================
    if user_role == 'admin':
        st.success("👑 Quyền Quản trị viên")
        
        tab1, tab2 = st.tabs(["📂 Cập nhật Dữ liệu", "👥 Quản lý Tài khoản"])
        
        # TAB 1: TẢI FILE
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

        # TAB 2: QUẢN LÝ TÀI KHOẢN (Bảng điều khiển siêu cấp)
        with tab2:
            st.subheader("📋 Danh sách tài khoản hiện có")
            user_list = []
            for uname, info in credentials['usernames'].items():
                user_list.append({
                    "Username": uname, 
                    "Tên hiển thị": info.get('name', ''), 
                    "Chức vụ": info.get('position', 'Chưa cập nhật'),
                    "Phòng ban": info.get('department', 'Chưa cập nhật'),
                    "Quyền": "Quản trị viên" if info.get('role') == 'admin' else "Nhân viên tra cứu"
                })
            st.table(pd.DataFrame(user_list))

            # --- TẠO MỚI ---
            with st.expander("➕ Cấp tài khoản mới"):
                with st.form("new_user_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_user = st.text_input("Tên đăng nhập (Username)*:", placeholder="VD: nhanvien2")
                        new_name = st.text_input("Tên hiển thị*:", placeholder="VD: Trần Văn B")
                    with col2:
                        new_position = st.text_input("Chức vụ:", placeholder="VD: Tổ trưởng, Kế toán viên...") 
                        new_dept = st.text_input("Phòng ban:", placeholder="VD: Kho, Line 1, Tài chính...")
                    
                    new_pass = st.text_input("Mật khẩu*:", type="password")
                    
                    if st.form_submit_button("Tạo tài khoản"):
                        if new_user == "" or new_pass == "" or new_name == "":
                            st.error("⚠️ Vui lòng nhập đầy đủ các trường bắt buộc (*)")
                        elif new_user in credentials['usernames']:
                            st.error("⚠️ Tên đăng nhập này đã tồn tại!")
                        else:
                            temp_cred = {'usernames': {new_user: {'password': new_pass}}}
                            stauth.Hasher.hash_passwords(temp_cred)
                            hashed_pass = temp_cred['usernames'][new_user]['password']
                            
                            credentials['usernames'][new_user] = {
                                'name': new_name,
                                'password': hashed_pass,
                                'role': 'user',
                                'position': new_position if new_position != "" else "Chưa cập nhật",
                                'department': new_dept if new_dept != "" else "Chưa cập nhật"
                            }
                            save_users(credentials) 
                            st.success(f"✅ Đã tạo tài khoản '{new_user}' thành công!")
                            st.rerun()

# --- CHỈNH SỬA ---
            with st.expander("✏️ Chỉnh sửa thông tin tài khoản"):
                import time # Thêm thư viện để tạo khoảng chờ thông báo
                
                edit_user = st.selectbox("Chọn tài khoản cần sửa:", list(credentials['usernames'].keys()), key="edit_select")
                if edit_user:
                    edit_info = credentials['usernames'][edit_user]
                    with st.form("edit_user_form"):
                        e_name = st.text_input("Tên hiển thị*:", value=edit_info.get('name', ''))
                        col1, col2 = st.columns(2)
                        with col1:
                            e_pos = st.text_input("Chức vụ:", value=edit_info.get('position', ''))
                        with col2:
                            e_dept = st.text_input("Phòng ban:", value=edit_info.get('department', ''))
                            
                        e_pass = st.text_input("Mật khẩu mới (để trống nếu không muốn đổi):", type="password")
                        
                        if st.form_submit_button("Cập nhật tài khoản"):
                            # 1. KIỂM TRA LỖI (BÁO THẤT BẠI)
                            if e_name.strip() == "":
                                st.error("❌ Cập nhật thất bại: 'Tên hiển thị' không được để trống!")
                            elif e_pass != "" and len(e_pass) < 5:
                                st.error("❌ Cập nhật thất bại: Mật khẩu mới phải có ít nhất 5 ký tự!")
                            else:
                                # 2. TIẾN HÀNH CẬP NHẬT (NẾU KHÔNG CÓ LỖI)
                                credentials['usernames'][edit_user]['name'] = e_name.strip()
                                credentials['usernames'][edit_user]['position'] = e_pos.strip()
                                credentials['usernames'][edit_user]['department'] = e_dept.strip()
                                
                                if e_pass != "":
                                    t_cred = {'usernames': {edit_user: {'password': e_pass}}}
                                    stauth.Hasher.hash_passwords(t_cred)
                                    credentials['usernames'][edit_user]['password'] = t_cred['usernames'][edit_user]['password']
                                
                                save_users(credentials)
                                st.success(f"✅ Đã cập nhật thành công tài khoản '{edit_user}'!")
                                
                                # Dừng 1.5 giây để người dùng kịp đọc thông báo trước khi hệ thống tải lại trang
                                time.sleep(1.5) 
                                st.rerun()
                            save_users(credentials)
                            st.success(f"✅ Đã cập nhật thành công tài khoản {edit_user}!")
                            st.rerun()

            # --- XÓA ---
            with st.expander("❌ Xóa tài khoản"):
                del_list = [u for u in credentials['usernames'].keys() if u != 'admin']
                if not del_list:
                    st.info("Không có tài khoản con nào để xóa.")
                else:
                    del_user = st.selectbox("Chọn tài khoản cần xóa:", del_list, key="del_select")
                    st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn tài khoản '{del_user}' không?")
                    if st.button("Xác nhận Xóa"):
                        del credentials['usernames'][del_user]
                        save_users(credentials)
                        st.success(f"✅ Đã xóa tài khoản {del_user}!")
                        st.rerun()

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
