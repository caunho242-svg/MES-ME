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
    current_line = current_user_info.get('line', 'Chưa rõ')
    
    st.title(f"🤖 Trợ lý AI - Xin chào {name} ({current_position} - {current_department} - {current_line})!")
    st.markdown("---")

    with st.sidebar:
        st.header("⚙️ Cấu hình API")
        openai_api_key = st.text_input("Nhập OpenAI API Key:", type="password")
        st.info("Lưu ý: API Key không được lưu lại để đảm bảo bảo mật.")

    # Đọc trước file dữ liệu nếu có
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
    menu_options = []
    
    # Bất kỳ ai có quyền xem (hoặc admin) đều thấy tab tổng hợp DATA này
    if can_view:
        menu_options.append("📊 DATA Tổng hợp")
        
    if can_edit_data:
        menu_options.append("📂 Cập nhật Dữ liệu")
    if can_edit_account:
        menu_options.append("👥 Quản lý Tài khoản")
    if can_edit_line:
        menu_options.append("🏭 Quản lý LINE")
    # ================= KHU VỰC DÀNH CHO QUẢN LÝ TÙY THEO QUYỀN =================
    if menu_options:
        if "admin_menu" not in st.session_state or st.session_state.admin_menu not in menu_options:
            st.session_state.admin_menu = menu_options[0]
            
        def go_home():
            st.session_state.admin_menu = menu_options[0]

        col1, col2 = st.columns([8.5, 1.5])
        with col1:
            st.success("🛠️ Khu vực Quản lý & Cấu hình (Hiển thị theo phân quyền)")
        with col2:
            st.button("🏠 Trang chủ", on_click=go_home, use_container_width=True)

        selected_tab = st.radio("Điều hướng:", menu_options, horizontal=True, key="admin_menu", label_visibility="collapsed")
        st.markdown("---")
        
        # TAB 1: CẬP NHẬT DỮ LIỆU
        if selected_tab == "📂 Cập nhật Dữ liệu":
            uploaded_file = st.file_uploader("📂 Chọn file dữ liệu (Excel/CSV) để cập nhật", type=["xlsx", "xls", "csv"])
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                df.to_csv("data_server.csv", index=False)
                st.success("✅ Đã cập nhật cơ sở dữ liệu chung cho toàn bộ nhân viên!")

        # TAB 2: QUẢN LÝ TÀI KHOẢN (VÀ PHÂN QUYỀN CHI TIẾT)
        elif selected_tab == "👥 Quản lý Tài khoản":
            st.subheader("📋 Danh sách tài khoản & Phân quyền thao tác")
            user_list = []
            for uname, info in credentials['usernames'].items():
                perms = info.get('permissions', {})
                perm_str = []
                if perms.get('view', True): perm_str.append("👁️ Xem")
                if perms.get('edit_data') or info.get('role') == 'admin': perm_str.append("📂 File")
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

        # TAB 3: QUẢN LÝ LINE
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
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False

                    if st.session_state[edit_key]:
                        st.markdown(f"**🖥️ Danh sách Máy thuộc {lname} *(Đang chỉnh sửa)*:**")
                    else:
                        st.markdown(f"**🖥️ Danh sách Máy thuộc {lname}:**")

                    mac_list = []
                    for m_num, m_info in line_machines.items():
                        mac_list.append({
                            "Số máy (Mã ID)": m_num,
                            "Tên máy": m_info.get('name', ''),
                            "Vị trí (Ô CSV)": m_info.get('position', ''),
                            "Định dạng file": m_info.get('format', 'CSV'),
                            "Đường dẫn gốc": m_info.get('path', ''),
                            "File mẫu (Template)": m_info.get('template_path', ''),
                            "Lấy dữ liệu": bool(m_info.get('active', True))
                        })
                    
                    df_mac = pd.DataFrame(mac_list)
                    if df_mac.empty:
                        df_mac = pd.DataFrame(columns=["Số máy (Mã ID)", "Tên máy", "Vị trí (Ô CSV)", "Định dạng file", "Đường dẫn gốc", "File mẫu (Template)", "Lấy dữ liệu"])
                        if df_mac.empty:
                            df_mac = pd.DataFrame(columns=["Số máy (Mã ID)", "Tên máy", "Vị trí (Ô CSV)", "Định dạng file", "Đường dẫn gốc", "File mẫu (Template)", "Lấy dữ liệu"])
                            df_mac = pd.DataFrame(columns=["Số máy (Mã ID)", "Tên máy", "Vị trí (Ô CSV)", "Định dạng file", "Đường dẫn gốc", "File mẫu (Template)", "Lấy dữ liệu"])

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
                                    'name': m_name,
                                    'position': safe_str(row.get("Vị trí (Ô CSV)", "")),
                                    'format': safe_str(row.get("Định dạng file", "CSV")),
                                    'path': safe_str(row.get("Đường dẫn gốc", "")),
                                    'template_path': safe_str(row.get("File mẫu (Template)", "")), # <-- Thêm dòng này
                                    'active': bool(row.get("Lấy dữ liệu", True))
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
                                    mac_path = st.text_input("Đường dẫn file gốc:", key=f"add_path_{lname}")
                                    mac_template = st.text_input("Đường dẫn File mẫu (Excel):", placeholder="Để trống nếu không dùng...", key=f"add_tpl_{lname}") # <-- Form tải file mẫu
                                    mac_active = st.checkbox("Kích hoạt (Lấy dữ liệu)", value=True, key=f"add_act_{lname}")
                                    
                            if st.form_submit_button("Thêm Máy Mới"):
                                if mac_num.strip() == "" or mac_name.strip() == "":
                                    st.error("⚠️ 'Số máy' và 'Tên máy' không được để trống!")
                                elif mac_num.strip() in line_machines:
                                    st.error("⚠️ Số máy này đã tồn tại!")
                                else:
                                    if 'machines' not in credentials['lines'][lname]:
                                        credentials['lines'][lname]['machines'] = {}
                                    credentials['lines'][lname]['machines'][mac_num.strip()] = {
                                        'name': mac_name.strip(),
                                        'position': mac_pos.strip(),
                                        'format': mac_format,
                                        'path': mac_path.strip(),
                                        'template_path': mac_template.strip(), # <-- Lưu file mẫu
                                        'active': mac_active
                                    }
                                        save_users(credentials); st.success(f"✅ Đã thêm máy '{mac_num.strip()}'!"); time.sleep(1.5); st.rerun()

                        with tab_del:
                            if not line_machines: st.info("Chưa có máy nào để xóa.")
                            else:
                                del_mac_num = st.selectbox("Chọn máy cần xóa:", list(line_machines.keys()), key=f"del_sel_{lname}")
                                if st.button("Xác nhận Xóa Máy", key=f"del_btn_{lname}"):
                                    del credentials['lines'][lname]['machines'][del_mac_num]
                                    save_users(credentials); st.success(f"✅ Đã xóa máy '{del_mac_num}'!"); time.sleep(1.5); st.rerun()
        # TAB 4: DATA TỔNG HỢP TỪ CÁC LINE
        elif selected_tab == "📊 DATA Tổng hợp":
            st.subheader("📊 Dữ liệu Tổng hợp từ các Máy & LINE")
            st.info("💡 Hệ thống tự động truy xuất dữ liệu từ các 'Đường dẫn' file mà bạn đã khai báo trong Quản lý LINE.")
            
            lines_data = credentials.get('lines', {})
            approved_lines_data = {k: v for k, v in lines_data.items() if v.get('status') == 'Đã phê duyệt'}
            
            if not approved_lines_data:
                st.warning("⚠️ Chưa có LINE nào được phê duyệt để thu thập dữ liệu.")
            else:
                if st.button("🔄 Làm mới dữ liệu", type="primary"):
                    st.rerun()
                    
                for lname, linfo in approved_lines_data.items():
                    st.markdown(f"### 🏭 LINE: {lname}")
                    machines = linfo.get('machines', {})
                    # Lọc ra các máy đang bật "Kích hoạt (Lấy dữ liệu)"
                    active_machines = {k: v for k, v in machines.items() if v.get('active')}
                    
                    if not active_machines:
                        st.caption(f"Không có máy nào đang được kích hoạt thu thập dữ liệu trong LINE {lname}.")
                        st.markdown("---")
                        continue
                        
                    for m_num, m_info in active_machines.items():
                        m_name = m_info.get('name', 'Chưa có tên')
                        m_path = m_info.get('path', '')
                        m_format = m_info.get('format', 'CSV')
                        
                        with st.expander(f"🖥️ Máy: {m_name} (ID: {m_num}) | 📁 Định dạng: {m_format} | 📍 Đường dẫn: {m_path}"):
                            if not m_path:
                                st.warning("⚠️ Máy này chưa được cấu hình đường dẫn file dữ liệu.")
                                continue
                            
                            if not os.path.exists(m_path):
                                st.error(f"❌ Không tìm thấy file tại đường dẫn: `{m_path}`. Vui lòng kiểm tra lại thiết lập.")
                                continue
                                
                            try:
                                m_df = None
                                # Xử lý đọc file theo định dạng đã khai báo
                                if m_format == "CSV":
                                    m_df = pd.read_csv(m_path)
                                elif m_format == "Excel":
                                    m_df = pd.read_excel(m_path)
                                elif m_format == "JSON":
                                    m_df = pd.read_json(m_path)
                                elif m_format == "TXT":
                                    m_df = pd.read_csv(m_path, sep=None, engine='python')
                                else:
                                    st.warning(f"⚠️ Định dạng '{m_format}' hiện chưa được hỗ trợ đọc tự động.")
                                    
                                if m_df is not None:
                                    # ====================================================
                                    # CHUẨN HÓA DỮ LIỆU THEO FILE MẪU (EXCEL TEMPLATE)
                                    # ====================================================
                                    m_template_path = m_info.get('template_path', '')
                                    if m_template_path and str(m_template_path).strip() != "":
                                        if os.path.exists(m_template_path):
                                            try:
                                                # Đọc file mẫu chỉ để lấy tên cột (không lấy dữ liệu)
                                                tpl_df = pd.read_excel(m_template_path, nrows=0)
                                                standard_cols = tpl_df.columns.tolist()
                                                
                                                # Ép dữ liệu gốc (m_df) theo đúng các cột của file mẫu
                                                m_df = m_df.reindex(columns=standard_cols)
                                                
                                                st.info(f"✨ **Dữ liệu đã được chuẩn hóa theo Form mẫu ({len(standard_cols)} cột).**")
                                            except Exception as tpl_e:
                                                st.warning(f"⚠️ Không thể đọc File mẫu '{m_template_path}': {tpl_e}")
                                        else:
                                            st.warning(f"⚠️ Không tìm thấy File mẫu tại: `{m_template_path}`. Dữ liệu hiển thị nguyên bản.")
                                    # ====================================================
                                    
                                    st.success(f"✅ Đã tải thành công {len(m_df)} dòng dữ liệu từ máy {m_name}.")
                                    st.dataframe(m_df, use_container_width=True)
    else:
        # NẾU USER KHÔNG CÓ BẤT CỨ QUYỀN QUẢN LÝ NÀO
        st.info("👤 Giao diện Nhân viên: Bạn chỉ được cấp quyền tra cứu dữ liệu từ hệ thống.")
        if df is None:
            st.warning("⚠️ Quản trị viên chưa cập nhật cơ sở dữ liệu nào lên hệ thống.")

    # ================= KHU VỰC HỎI ĐÁP AI (CHUNG) =================
    # Điều kiện để nhận biết người dùng đang ở Trang chủ (Tab Cập nhật dữ liệu hoặc giao diện mặc định)
    is_on_home_page = (not menu_options) or (selected_tab == "📂 Cập nhật Dữ liệu")

    if is_on_home_page:
        is_line_approved = True
        if user_role != 'admin' and current_line not in ["Chưa cập nhật", "Tất cả"]:
            line_data = credentials.get('lines', {}).get(current_line, {})
            if line_data and line_data.get('status') != 'Đã phê duyệt':
                is_line_approved = False

        if not is_line_approved:
            st.error(f"⛔ Truy cập bị từ chối: LINE '{current_line}' của bạn hiện đang ở trạng thái 'Không phê duyệt'. Hệ thống tạm thời khóa chức năng AI đối với LINE này!")
        else:
            # Nếu chưa có file dữ liệu, tạo một bảng rỗng để thanh tìm kiếm luôn hiển thị
            if df is None:
                df = pd.DataFrame(columns=["Chưa có dữ liệu"])

            st.subheader("📊 Cơ sở Dữ liệu & Tìm kiếm")
            
            # --- BỘ LỌC TÌM KIẾM VÀ TÌM KIẾM NÂNG CAO ---
            with st.expander("🔍 Tìm kiếm & Lọc dữ liệu nâng cao", expanded=True):
                col_s1, col_s2 = st.columns([7, 3])
                
                with col_s1:
                    search_kw = st.text_input("🔎 Tìm kiếm nhanh (từ khóa chung):", placeholder="Nhập từ khóa cần tìm...")
                with col_s2:
                    enable_advanced = st.checkbox("⚙️ Bật Lọc nâng cao")
                
                df_filtered = df.copy()
                
                # 1. Tìm kiếm nhanh trên toàn bộ các cột
                if search_kw.strip() and not df_filtered.empty:
                    mask = df_filtered.astype(str).apply(
                        lambda row: row.str.contains(search_kw.strip(), case=False, na=False)
                    ).any(axis=1)
                    df_filtered = df_filtered[mask]
                    
                # 2. Tìm kiếm nâng cao theo cột cụ thể
                if enable_advanced:
                    st.markdown("---")
                    st.markdown("##### 🎯 Điều kiện lọc theo cột:")
                    cols = list(df.columns)
                    
                    col_f1, col_f2, col_f3 = st.columns(3)
                    with col_f1:
                        selected_col = st.selectbox("Chọn cột cần lọc:", cols)
                    with col_f2:
                        filter_type = st.selectbox("Kiểu lọc:", ["Chứa từ khóa", "Khớp chính xác", "Lớn hơn (>)", "Nhỏ hơn (<)"])
                    with col_f3:
                        filter_val = st.text_input("Giá trị lọc:", placeholder="Nhập giá trị...")
                    
                    if filter_val.strip() and not df_filtered.empty:
                        val = filter_val.strip()
                        try:
                            if filter_type == "Chứa từ khóa":
                                df_filtered = df_filtered[df_filtered[selected_col].astype(str).str.contains(val, case=False, na=False)]
                            elif filter_type == "Khớp chính xác":
                                df_filtered = df_filtered[df_filtered[selected_col].astype(str).str.lower() == val.lower()]
                            elif filter_type == "Lớn hơn (>)":
                                df_filtered = df_filtered[pd.to_numeric(df_filtered[selected_col], errors='coerce') > float(val)]
                            elif filter_type == "Nhỏ hơn (<)":
                                df_filtered = df_filtered[pd.to_numeric(df_filtered[selected_col], errors='coerce') < float(val)]
                        except Exception as filter_err:
                            st.warning(f"⚠️ Lỗi định dạng giá trị lọc: {filter_err}")

            # Hiển thị số lượng kết quả lọc được
            st.caption(f"📌 **Hiển thị:** {len(df_filtered)} / {len(df)} dòng dữ liệu")
            
            # Bảng hiển thị dữ liệu sau khi tìm kiếm/lọc
            st.dataframe(df_filtered, use_container_width=True, height=300)

            # --- KHU VỰC HỎI ĐÁP BẰNG AI ---
            st.markdown("---")
            query = st.text_input("💬 Nhập câu hỏi/yêu cầu AI phân tích dữ liệu:")

            if query:
                if not openai_api_key:
                    st.error("⚠️ Vui lòng nhập OpenAI API Key ở thanh bên trái để tiếp tục!")
                elif len(df) == 0 or (len(df) == 1 and "Chưa có dữ liệu" in df.columns):
                    # Báo lỗi nếu người dùng hỏi AI khi hệ thống chưa được upload file nào
                    st.warning("⚠️ Hệ thống hiện chưa có dữ liệu để AI phân tích. Quản trị viên cần tải file Excel/CSV lên trước!")
                else:
                    with st.spinner("AI đang xử lý dữ liệu..."):
                        try:
                            llm = ChatOpenAI(temperature=0, model="gpt-4o-mini", api_key=openai_api_key)
                            # AI sẽ ưu tiên phân tích dữ liệu đã được lọc (df_filtered)
                            agent = create_pandas_dataframe_agent(
                                llm, 
                                df_filtered if search_kw or enable_advanced else df, 
                                verbose=True, 
                                allow_dangerous_code=True
                            )
                            response = agent.invoke({"input": query})
                            st.success("✅ Kết quả phân tích từ AI:")
                            st.write(response["output"])
                        except Exception as e:
                            st.error(f"Xảy ra lỗi trong quá trình xử lý: {e}")
