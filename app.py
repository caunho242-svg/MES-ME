import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
import os
import json
import time

# -------------------------------------------------------------------
# 1. HỆ THỐNG QUẢN LÝ DỮ LIỆU TÀI KHOẢN VÀ LINE (JSON)
# -------------------------------------------------------------------
USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if 'lines' not in data:
                data['lines'] = {}
            return data
    else:
        default_creds = {
            'usernames': {
                'admin': {
                    'name': 'Quản trị viên',
                    'password': 'admin123',
                    'role': 'admin',
                    'position': 'Quản lý',
                    'department': 'Hệ thống',
                    'line': 'Tất cả',
                    'permissions': {
                        'view': True, 
                        'edit_data': True, 
                        'edit_line': True, 
                        'edit_account': True
                    }
                }
            },
            'lines': {}
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

# ĐÃ FIX LỖI BẢO MẬT: Sử dụng khóa Cookie mạnh hơn
authenticator = stauth.Authenticate(
    credentials,
    'mes_system_cookie_secure',
    'MES_super_secret_key_2026_!@#', 
    cookie_expiry_days=1
)

try:
    authenticator.login(location='main')
except Exception as e:
    st.error(f"Lỗi đăng nhập: {e}")

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
    current_line = current_user_info.get('line', 'Chưa rõ')
    
    st.title(f"🤖 Trợ lý AI - Xin chào {name} ({current_position} - {current_department} - {current_line})!")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Cấu hình API")
        openai_api_key = st.text_input("Nhập OpenAI API Key:", type="password")
        st.info("Lưu ý: API Key không được lưu lại để đảm bảo bảo mật.")

    df = None 
    if os.path.exists("data_server.csv"):
        df = pd.read_csv("data_server.csv")

    approved_lines = [lname for lname, linfo in credentials.get('lines', {}).items() if linfo.get('status') == 'Đã phê duyệt']
    line_options = ["Chưa cập nhật", "Tất cả"] + approved_lines

    # --- LẤY QUYỀN HẠN CỦA TÀI KHOẢN ĐANG ĐĂNG NHẬP ---
    user_role = current_user_info.get('role', 'user')
    user_perms = current_user_info.get('permissions', {})
    
    can_view = user_perms.get('view', True)
    can_edit_data = user_perms.get('edit_data', False) or user_role == 'admin'
    can_edit_account = user_perms.get('edit_account', False) or user_role == 'admin'
    can_edit_line = user_perms.get('edit_line', False) or user_role == 'admin'

    # Xây dựng Menu Động dựa trên quyền hạn
    menu_options = ["🏠 Trang chủ (Tra cứu AI)"]
    if can_edit_data: menu_options.append("📂 Cập nhật Dữ liệu")
    if can_edit_account: menu_options.append("👥 Quản lý Tài khoản")
    if can_edit_line: menu_options.append("🏭 Quản lý LINE")

    if "nav_menu" not in st.session_state or st.session_state.nav_menu not in menu_options:
        st.session_state.nav_menu = menu_options[0]
        
    def go_home():
        st.session_state.nav_menu = menu_options[0]

    col1, col2 = st.columns([8.5, 1.5])
    with col1:
        st.success("🛠️ Khu vực Làm việc (Hiển thị các tab theo phân quyền của bạn)")
    with col2:
        st.button("🏠 Về Trang chủ", on_click=go_home, use_container_width=True)

    selected_tab = st.radio("Điều hướng:", menu_options, horizontal=True, key="nav_menu", label_visibility="collapsed")
    st.markdown("---")
    
    # =========================================================================
    # TAB 1: TRANG CHỦ (TÌM KIẾM DỮ LIỆU & HỎI ĐÁP AI)
    # =========================================================================
    if selected_tab == "🏠 Trang chủ (Tra cứu AI)":
        st.subheader("📊 Cơ sở Dữ liệu & Tra cứu AI")
        
        is_line_approved = True
        if user_role != 'admin' and current_line not in ["Chưa cập nhật", "Tất cả"]:
            line_data = credentials.get('lines', {}).get(current_line, {})
            if line_data and line_data.get('status') != 'Đã phê duyệt':
                is_line_approved = False

        if not is_line_approved:
            st.error(f"⛔ Truy cập bị từ chối: LINE '{current_line}' của bạn hiện đang bị khóa hoặc chưa phê duyệt.")
        elif not can_view:
            st.error("⛔ Truy cập bị từ chối: Tài khoản của bạn đã bị vô hiệu hóa tính năng Xem & Tra cứu dữ liệu AI. Vui lòng liên hệ Admin!")
        elif df is not None:
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
                            agent = create_pandas_dataframe_agent(llm, df, verbose=True, allow_dangerous_code=True)
                            response = agent.run(query)
                            st.success("✅ Kết quả:")
                            st.write(response)
                        except Exception as e:
                            st.error(f"Xảy ra lỗi trong quá trình xử lý: {e}")
        else:
            st.info("⚠️ Hệ thống chưa có dữ liệu. Hãy yêu cầu người có quyền Cập nhật dữ liệu tải file lên.")

    # =========================================================================
    # TAB 2: CẬP NHẬT DỮ LIỆU
    # =========================================================================
    elif selected_tab == "📂 Cập nhật Dữ liệu":
        st.subheader("📂 Tải lên file & Cập nhật Dữ liệu mới")
        uploaded_file = st.file_uploader("Chọn file dữ liệu (Excel/CSV) để cập nhật cho toàn hệ thống:", type=["xlsx", "xls", "csv"])
        if uploaded_file is not None:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            df.to_csv("data_server.csv", index=False)
            st.success("✅ Đã cập nhật cơ sở dữ liệu chung cho toàn bộ nhân viên!")
            time.sleep(1.5)
            st.rerun()
        elif df is not None:
            st.info("Hệ thống đang sử dụng dữ liệu đã được cập nhật trước đó.")

    # =========================================================================
    # TAB 3: QUẢN LÝ TÀI KHOẢN
    # =========================================================================
    elif selected_tab == "👥 Quản lý Tài khoản":
        st.subheader("📋 Danh sách tài khoản & Phân quyền thao tác")
        user_list = []
        for uname, info in credentials['usernames'].items():
            perms = info.get('permissions', {})
            perm_str = []
            if perms.get('view', True): perm_str.append("👁️ Xem")
            if perms.get('edit_data') or info.get('role') == 'admin': perm_str.append("📂 Dữ liệu")
            if perms.get('edit_line') or info.get('role') == 'admin': perm_str.append("🏭 Line")
            if perms.get('edit_account') or info.get('role') == 'admin': perm_str.append("👑 Admin")
            
            user_list.append({
                "Username": uname, 
                "Tên hiển thị": info.get('name', ''), 
                "Chức vụ": info.get('position', 'Chưa cập nhật'),
                "LINE": info.get('line', 'Chưa cập nhật'),
                "Quyền hạn": " | ".join(perm_str) if perm_str else "❌ Khóa hoàn toàn"
            })
        st.table(pd.DataFrame(user_list))

        with st.expander("➕ Cấp tài khoản mới"):
            with st.form("new_user_form", clear_on_submit=True):
                st.markdown("**1. Thông tin cơ bản:**")
                col1, col2 = st.columns(2)
                with col1:
                    new_user = st.text_input("Tên đăng nhập (Username)*:", placeholder="VD: nhanvien2")
                    new_name = st.text_input("Tên hiển thị*:", placeholder="VD: Trần Văn B")
                    new_position = st.text_input("Chức vụ:", placeholder="VD: Tổ trưởng...") 
                with col2:
                    new_dept = st.text_input("Phòng ban:", placeholder="VD: Kho, Tài chính...")
                    new_line = st.selectbox("LINE:", line_options)
                    new_pass = st.text_input("Mật khẩu*:", type="password")
                
                st.markdown("**2. Phân quyền chi tiết (Check vào các mục cho phép):**")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    new_perm_view = st.checkbox("👁️ Xem và tra cứu dữ liệu AI (Cơ bản)", value=True)
                    new_perm_data = st.checkbox("📂 Cập nhật file dữ liệu (Excel/CSV)", value=False)
                with col_p2:
                    new_perm_line = st.checkbox("🏭 Quản lý LINE & Cấu hình máy móc", value=False)
                    new_perm_acc = st.checkbox("👥 Quản lý Tài khoản (Quyền Admin)", value=False)
                
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
                            'name': new_name, 'password': hashed_pass, 
                            'role': 'admin' if new_perm_acc else 'user',
                            'position': new_position if new_position != "" else "Chưa cập nhật",
                            'department': new_dept if new_dept != "" else "Chưa cập nhật",
                            'line': new_line,
                            'permissions': {
                                'view': new_perm_view, 'edit_data': new_perm_data, 
                                'edit_line': new_perm_line, 'edit_account': new_perm_acc
                            }
                        }
                        save_users(credentials) 
                        st.success(f"✅ Đã tạo tài khoản '{new_user}' thành công!")
                        time.sleep(1.5)
                        st.rerun()

        with st.expander("✏️ Chỉnh sửa thông tin & Phân quyền"):
            edit_user = st.selectbox("Chọn tài khoản cần sửa:", list(credentials['usernames'].keys()), key="edit_select")
            if edit_user:
                edit_info = credentials['usernames'][edit_user]
                curr_perms = edit_info.get('permissions', {})
                is_legacy_admin = edit_info.get('role') == 'admin'
                
                with st.form("edit_user_form"):
                    st.markdown("**1. Thông tin cơ bản:**")
                    e_name = st.text_input("Tên hiển thị*:", value=edit_info.get('name', ''))
                    col1, col2, col3 = st.columns(3)
                    with col1: e_pos = st.text_input("Chức vụ:", value=edit_info.get('position', ''))
                    with col2: e_dept = st.text_input("Phòng ban:", value=edit_info.get('department', ''))
                    with col3:
                        curr_line = edit_info.get('line', 'Chưa cập nhật')
                        if curr_line not in line_options: line_options.append(curr_line)
                        e_line = st.selectbox("LINE:", line_options, index=line_options.index(curr_line))
                    e_pass = st.text_input("Mật khẩu mới (để trống nếu không đổi):", type="password")
                    
                    st.markdown("**2. Phân quyền chi tiết (Check vào các mục cho phép):**")
                    col_ep1, col_ep2 = st.columns(2)
                    with col_ep1:
                        e_perm_view = st.checkbox("👁️ Xem và tra cứu dữ liệu AI (Cơ bản)", value=curr_perms.get('view', True))
                        e_perm_data = st.checkbox("📂 Cập nhật file dữ liệu (Excel/CSV)", value=curr_perms.get('edit_data', False) or is_legacy_admin)
                    with col_ep2:
                        e_perm_line = st.checkbox("🏭 Quản lý LINE & Cấu hình máy móc", value=curr_perms.get('edit_line', False) or is_legacy_admin)
                        e_perm_acc = st.checkbox("👥 Quản lý Tài khoản (Quyền Admin)", value=curr_perms.get('edit_account', False) or is_legacy_admin)
                        
                    if st.form_submit_button("Cập nhật tài khoản"):
                        if e_name.strip() == "": st.error("❌ 'Tên hiển thị' không được để trống!")
                        elif e_pass != "" and len(e_pass) < 5: st.error("❌ Mật khẩu mới phải có ít nhất 5 ký tự!")
                        else:
                            credentials['usernames'][edit_user].update({
                                'name': e_name.strip(), 'position': e_pos.strip(), 
                                'department': e_dept.strip(), 'line': e_line,
                                'role': 'admin' if e_perm_acc else 'user',
                                'permissions': {
                                    'view': e_perm_view, 'edit_data': e_perm_data, 
                                    'edit_line': e_perm_line, 'edit_account': e_perm_acc
                                }
                            })
                            if e_pass != "":
                                t_cred = {'usernames': {edit_user: {'password': e_pass}}}
                                stauth.Hasher.hash_passwords(t_cred)
                                credentials['usernames'][edit_user]['password'] = t_cred['usernames'][edit_user]['password']
                            save_users(credentials); st.success(f"✅ Đã cập nhật '{edit_user}'!"); time.sleep(1.5); st.rerun()

        with st.expander("❌ Xóa tài khoản"):
            del_list = [u for u in credentials['usernames'].keys() if u != 'admin']
            if not del_list: st.info("Không có tài khoản con nào để xóa.")
            else:
                del_user = st.selectbox("Chọn tài khoản cần xóa:", del_list, key="del_select")
                st.warning(f"⚠️ Chắc chắn muốn xóa vĩnh viễn tài khoản '{del_user}'?")
                if st.button("Xác nhận Xóa Tài Khoản"):
                    del credentials['usernames'][del_user]; save_users(credentials); st.success(f"✅ Đã xóa!"); time.sleep(1.5); st.rerun()

    # =========================================================================
    # TAB 4: QUẢN LÝ LINE
    # =========================================================================
    elif selected_tab == "🏭 Quản lý LINE":
        manager_options = ["Chưa phân công"]
        for u_name, u_info in credentials['usernames'].items():
            manager_options.append(f"{u_name} ({u_info.get('name', '')})")
        
        with st.expander("➕ Tạo LINE mới"):
            with st.form("new_line_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    new_lnumber = st.text_input("Số LINE (Tùy chọn):", placeholder="VD: 01, 02...")
                    new_lname = st.text_input("Tên LINE*:", placeholder="VD: Line 1, Lò nung...")
                    new_larea = st.text_input("Khu vực (Tùy chọn):", placeholder="VD: Khu A...") 
                with col2:
                    new_lmanager = st.selectbox("Người phụ trách:", manager_options) 
                    new_ldescription = st.text_input("Mô tả / Ghi chú:")
                    new_lstatus = st.selectbox("Trạng thái ban đầu:", ["Đã phê duyệt", "Không phê duyệt"])
                
                if st.form_submit_button("Tạo LINE"):
                    if new_lname.strip() == "": st.error("⚠️ Tên LINE không được để trống!")
                    elif new_lname in credentials.get('lines', {}): st.error("⚠️ Tên LINE này đã tồn tại!")
                    else:
                        credentials['lines'][new_lname] = {
                            'number': new_lnumber.strip() if new_lnumber.strip() != "" else "Chưa cập nhật",
                            'area': new_larea.strip() if new_larea.strip() != "" else "Chưa cập nhật",
                            'manager': new_lmanager, 'description': new_ldescription.strip(), 'status': new_lstatus, 'machines': {}
                        }
                        save_users(credentials); st.success(f"✅ Đã tạo LINE '{new_lname}'!"); time.sleep(1.5); st.rerun()

        with st.expander("✏️ Chỉnh sửa / Bỏ phê duyệt LINE"):
            lines_keys = list(credentials.get('lines', {}).keys())
            if lines_keys:
                edit_lname = st.selectbox("Chọn LINE cần sửa:", lines_keys, key="edit_line_select")
                if edit_lname:
                    line_info = credentials['lines'][edit_lname]
                    with st.form("edit_line_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            el_number = st.text_input("Số LINE:", value=line_info.get('number', '')) 
                            el_area = st.text_input("Khu vực:", value=line_info.get('area', '')) 
                            curr_manager = line_info.get('manager', 'Chưa phân công')
                            if curr_manager not in manager_options: manager_options.append(curr_manager)
                            el_manager = st.selectbox("Người phụ trách:", manager_options, index=manager_options.index(curr_manager))
                        with col2:
                            el_desc = st.text_input("Mô tả:", value=line_info.get('description', ''))
                            el_status = st.selectbox("Trạng thái:", ["Đã phê duyệt", "Không phê duyệt"], index=0 if line_info.get('status') == 'Đã phê duyệt' else 1)
                        if st.form_submit_button("Cập nhật LINE"):
                            credentials['lines'][edit_lname].update({'number': el_number.strip(), 'area': el_area.strip(), 'manager': el_manager, 'description': el_desc.strip(), 'status': el_status})
                            save_users(credentials); st.success(f"✅ Đã cập nhật LINE '{edit_lname}'!"); time.sleep(1.5); st.rerun()

        with st.expander("✅ Phê duyệt LINE"):
            pending_lines = [k for k, v in credentials.get('lines', {}).items() if v.get('status') != 'Đã phê duyệt']
            if not pending_lines: st.success("Tuyệt vời! Tất cả các LINE đều đang ở trạng thái Đã phê duyệt.")
            else:
                approve_lname = st.selectbox("Chọn LINE để phê duyệt:", pending_lines)
                if st.button("Xác nhận Phê duyệt"):
                    credentials['lines'][approve_lname]['status'] = 'Đã phê duyệt'
                    save_users(credentials); st.success(f"✅ Đã phê duyệt '{approve_lname}'!"); time.sleep(1.5); st.rerun()

        with st.expander("❌ Xóa LINE"):
            if lines_keys:
                del_lname = st.selectbox("Chọn LINE cần xóa:", lines_keys, key="del_line_select")
                st.warning(f"⚠️ Chú ý: Việc xóa sẽ không ảnh hưởng đến tài khoản đang có tên LINE này. Chắc chắn xóa '{del_lname}'?")
                if st.button("Xác nhận Xóa LINE"):
                    del credentials['lines'][del_lname]; save_users(credentials); st.success(f"✅ Đã xóa!"); time.sleep(1.5); st.rerun()

        st.markdown("---")
        st.subheader("🏭 Danh sách LINE & Thiết lập")
        
        lines_data = credentials.get('lines', {})
        if not lines_data:
            st.info("Hệ thống chưa có LINE nào. Hãy tạo mới ở phía trên.")
        else:
            for lname, linfo in lines_data.items():
                num_macs = len(linfo.get('machines', {}))
                status_icon = "🟢" if linfo.get('status') == 'Đã phê duyệt' else "🔴"
                
                with st.expander(f"{status_icon} LINE: {lname} &nbsp;&nbsp;|&nbsp;&nbsp; Khu vực: {linfo.get('area', 'Chưa cập nhật')} &nbsp;&nbsp;|&nbsp;&nbsp; Máy móc: {num_macs}"):
                    st.caption(f"**Số LINE:** {linfo.get('number', '---')} &nbsp;|&nbsp; **Trạng thái:** {linfo.get('status')} &nbsp;|&nbsp; **Phụ trách:** {linfo.get('manager', '---')}")
                    
                    line_machines = linfo.get('machines', {})
                    edit_key = f"edit_mode_{lname}"
                    if edit_key not in st.session_state: st.session_state[edit_key] = False

                    if st.session_state[edit_key]: st.markdown(f"**🖥️ Danh sách Máy thuộc {lname} *(Đang chỉnh sửa)*:**")
                    else: st.markdown(f"**🖥️ Danh sách Máy thuộc {lname}:**")
                    
                    mac_list = []
                    for m_num, m_info in line_machines.items():
                        mac_list.append({
                            "Số máy (Mã ID)": m_num, "Tên máy": m_info.get('name', ''),
                            "Vị trí (Ô CSV)": m_info.get('position', ''), "Định dạng file": m_info.get('format', 'CSV'),
                            "Đường dẫn": m_info.get('path', ''), "Lấy dữ liệu": bool(m_info.get('active', True))
                        })
                    
                    df_mac = pd.DataFrame(mac_list)
                    if df_mac.empty:
                        df_mac = pd.DataFrame(columns=["Số máy (Mã ID)", "Tên máy", "Vị trí (Ô CSV)", "Định dạng file", "Đường dẫn", "Lấy dữ liệu"])

                    if not st.session_state[edit_key]:
                        st.dataframe(df_mac, hide_index=True, use_container_width=True)
                        if not df_mac.empty:
                            if st.button(f"✏️ Chỉnh sửa bảng máy ({lname})", key=f"btn_edit_{lname}"):
                                st.session_state[edit_key] = True; st.rerun()
                    else:
                        edited_df = st.data_editor(
                            df_mac,
                            column_config={
                                "Số máy (Mã ID)": st.column_config.TextColumn("Số máy (Mã ID)", disabled=True),
                                "Định dạng file": st.column_config.SelectboxColumn("Định dạng file", options=["CSV", "Excel", "TXT", "JSON", "Khác"]),
                            },
                            hide_index=True, use_container_width=True, key=f"editor_{lname}"
                        )
                        if not df_mac.empty:
                            col_b1, col_b2 = st.columns([2, 8])
                            with col_b1:
                                if st.button(f"💾 Lưu", type="primary", key=f"save_inline_{lname}"):
                                    has_err = False
                                    new_machines = {}
                                    safe_str = lambda x: "" if pd.isna(x) or x is None else str(x).strip()
                                    for idx, row in edited_df.iterrows():
                                        m_num = safe_str(row["Số máy (Mã ID)"])
                                        m_name = safe_str(row["Tên máy"])
                                        if m_name == "":
                                            st.error(f"⚠️ Lỗi: Máy '{m_num}' đang bị trống Tên! Vui lòng điền tên máy.")
                                            has_err = True; break
                                        new_machines[m_num] = {
                                            'name': m_name, 'position': safe_str(row["Vị trí (Ô CSV)"]),
                                            'format': safe_str(row["Định dạng file"]), 'path': safe_str(row["Đường dẫn"]), 'active': bool(row["Lấy dữ liệu"])
                                        }
                                    if not has_err:
                                        credentials['lines'][lname]['machines'] = new_machines
                                        save_users(credentials); st.success(f"✅ Đã lưu thay đổi LINE {lname}!")
                                        st.session_state[edit_key] = False; time.sleep(1); st.rerun()
                            with col_b2:
                                if st.button(f"❌ Hủy", key=f"cancel_inline_{lname}"):
                                    st.session_state[edit_key] = False; st.rerun()

                    st.write("")
                    tab_add, tab_del = st.tabs(["➕ Thêm máy mới", "❌ Xóa máy"])
                    
                    with tab_add:
                        with st.form(f"add_mac_form_{lname}", clear_on_submit=True):
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                mac_num = st.text_input("Số máy* (Mã định danh):", key=f"add_num_{lname}")
                                mac_name = st.text_input("Tên máy*:", key=f"add_name_{lname}")
                                mac_pos = st.text_input("Vị trí (Ô trong CSV):", key=f"add_pos_{lname}")
                            with col_m2:
                                mac_format = st.selectbox("Định dạng file:", ["CSV", "Excel", "TXT", "JSON", "Khác"], key=f"add_fmt_{lname}")
                                mac_path = st.text_input("Đường dẫn / Link Folder:", key=f"add_path_{lname}")
                            mac_active = st.checkbox("Kích hoạt (Lấy dữ liệu)", value=True, key=f"add_act_{lname}")
                            
                            if st.form_submit_button("Thêm Máy Mới"):
                                if mac_num.strip() == "" or mac_name.strip() == "": st.error("⚠️ 'Số máy' và 'Tên máy' không được để trống!")
                                elif mac_num.strip() in line_machines: st.error("⚠️ Số máy này đã tồn tại!")
                                else:
                                    if 'machines' not in credentials['lines'][lname]: credentials['lines'][lname]['machines'] = {}
                                    credentials['lines'][lname]['machines'][mac_num.strip()] = {
                                        'name': mac_name.strip(), 'position': mac_pos.strip(), 
                                        'format': mac_format, 'path': mac_path.strip(), 'active': mac_active
                                    }
                                    save_users(credentials); st.success(f"✅ Đã thêm máy '{mac_num.strip()}'!"); time.sleep(1.5); st.rerun()

                    with tab_del:
                        if not line_machines: st.info("Chưa có máy nào để xóa.")
                        else:
                            del_mac_num = st.selectbox("Chọn máy cần xóa:", list(line_machines.keys()), key=f"del_sel_{lname}")
                            if st.button("Xác nhận Xóa Máy", key=f"del_btn_{lname}"):
                                del credentials['lines'][lname]['machines'][del_mac_num]
                                save_users(credentials); st.success(f"✅ Đã xóa máy '{del_mac_num}'!"); time.sleep(1.5); st.rerun()
