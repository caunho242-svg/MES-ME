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
                    'line': 'Tất cả'
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

    df = None 
    user_role = current_user_info.get('role', 'user')

    # Lọc ra danh sách các LINE ĐÃ PHÊ DUYỆT để đưa vào menu gán tài khoản
    approved_lines = [lname for lname, linfo in credentials.get('lines', {}).items() if linfo.get('status') == 'Đã phê duyệt']
    line_options = ["Chưa cập nhật", "Tất cả"] + approved_lines

    # ================= KHU VỰC DÀNH RIÊNG CHO ADMIN =================
    if user_role == 'admin':
        st.success("👑 Quyền Quản trị viên")
        
        tab1, tab2, tab3 = st.tabs(["📂 Cập nhật Dữ liệu", "👥 Quản lý Tài khoản", "🏭 Quản lý LINE"])
        
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

        # TAB 2: QUẢN LÝ TÀI KHOẢN
        with tab2:
            st.subheader("📋 Danh sách tài khoản hiện có")
            user_list = []
            for uname, info in credentials['usernames'].items():
                user_list.append({
                    "Username": uname, 
                    "Tên hiển thị": info.get('name', ''), 
                    "Chức vụ": info.get('position', 'Chưa cập nhật'),
                    "Phòng ban": info.get('department', 'Chưa cập nhật'),
                    "LINE": info.get('line', 'Chưa cập nhật'),
                    "Quyền": "Quản trị viên" if info.get('role') == 'admin' else "Nhân viên"
                })
            st.table(pd.DataFrame(user_list))

            # --- TẠO MỚI TÀI KHOẢN ---
            with st.expander("➕ Cấp tài khoản mới"):
                with st.form("new_user_form", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_user = st.text_input("Tên đăng nhập (Username)*:", placeholder="VD: nhanvien2")
                        new_name = st.text_input("Tên hiển thị*:", placeholder="VD: Trần Văn B")
                        new_position = st.text_input("Chức vụ:", placeholder="VD: Tổ trưởng...") 
                    with col2:
                        new_dept = st.text_input("Phòng ban:", placeholder="VD: Kho, Tài chính...")
                        new_line = st.selectbox("LINE:", line_options)
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
                                'department': new_dept if new_dept != "" else "Chưa cập nhật",
                                'line': new_line
                            }
                            save_users(credentials) 
                            st.success(f"✅ Đã tạo tài khoản '{new_user}' thành công!")
                            time.sleep(1.5)
                            st.rerun()

            # --- CHỈNH SỬA TÀI KHOẢN ---
            with st.expander("✏️ Chỉnh sửa thông tin tài khoản"):
                edit_user = st.selectbox("Chọn tài khoản cần sửa:", list(credentials['usernames'].keys()), key="edit_select")
                if edit_user:
                    edit_info = credentials['usernames'][edit_user]
                    with st.form("edit_user_form"):
                        e_name = st.text_input("Tên hiển thị*:", value=edit_info.get('name', ''))
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            e_pos = st.text_input("Chức vụ:", value=edit_info.get('position', ''))
                        with col2:
                            e_dept = st.text_input("Phòng ban:", value=edit_info.get('department', ''))
                        with col3:
                            curr_line = edit_info.get('line', 'Chưa cập nhật')
                            if curr_line not in line_options:
                                line_options.append(curr_line)
                            e_line = st.selectbox("LINE:", line_options, index=line_options.index(curr_line))
                            
                        e_pass = st.text_input("Mật khẩu mới (để trống nếu không muốn đổi):", type="password")
                        
                        if st.form_submit_button("Cập nhật tài khoản"):
                            if e_name.strip() == "":
                                st.error("❌ Cập nhật thất bại: 'Tên hiển thị' không được để trống!")
                            elif e_pass != "" and len(e_pass) < 5:
                                st.error("❌ Cập nhật thất bại: Mật khẩu mới phải có ít nhất 5 ký tự!")
                            else:
                                credentials['usernames'][edit_user]['name'] = e_name.strip()
                                credentials['usernames'][edit_user]['position'] = e_pos.strip()
                                credentials['usernames'][edit_user]['department'] = e_dept.strip()
                                credentials['usernames'][edit_user]['line'] = e_line
                                
                                if e_pass != "":
                                    t_cred = {'usernames': {edit_user: {'password': e_pass}}}
                                    stauth.Hasher.hash_passwords(t_cred)
                                    credentials['usernames'][edit_user]['password'] = t_cred['usernames'][edit_user]['password']
                                
                                save_users(credentials)
                                st.success(f"✅ Đã cập nhật thành công tài khoản '{edit_user}'!")
                                time.sleep(1.5) 
                                st.rerun()

            # --- XÓA TÀI KHOẢN ---
            with st.expander("❌ Xóa tài khoản"):
                del_list = [u for u in credentials['usernames'].keys() if u != 'admin']
                if not del_list:
                    st.info("Không có tài khoản con nào để xóa.")
                else:
                    del_user = st.selectbox("Chọn tài khoản cần xóa:", del_list, key="del_select")
                    st.warning(f"⚠️ Bạn có chắc chắn muốn xóa vĩnh viễn tài khoản '{del_user}' không?")
                    if st.button("Xác nhận Xóa Tài Khoản"):
                        del credentials['usernames'][del_user]
                        save_users(credentials)
                        st.success(f"✅ Đã xóa tài khoản {del_user}!")
                        time.sleep(1.5)
                        st.rerun()

        # TAB 3: QUẢN LÝ LINE
        with tab3:
            st.subheader("🏭 Danh sách LINE hiện có")
            
            manager_options = ["Chưa phân công"]
            for u_name, u_info in credentials['usernames'].items():
                manager_options.append(f"{u_name} ({u_info.get('name', '')})")
            
            line_list = []
            for lname, linfo in credentials.get('lines', {}).items():
                line_list.append({
                    "Số LINE": linfo.get('number', 'Chưa cập nhật'), 
                    "Tên LINE": lname,
                    "Khu vực": linfo.get('area', 'Chưa cập nhật'),
                    "Người phụ trách": linfo.get('manager', 'Chưa phân công'),
                    "Số lượng Máy": len(linfo.get('machines', {})), # Đếm số lượng máy
                    "Trạng thái": linfo.get('status', 'Không phê duyệt')
                })
            
            if line_list:
                st.table(pd.DataFrame(line_list))
            else:
                st.info("Hệ thống chưa có LINE nào. Hãy tạo mới bên dưới.")

            # --- THIẾT LẬP MÁY MÓC BÊN TRONG LINE ---
            with st.expander("⚙️ Thiết lập Máy móc (Bên trong LINE)"):
                lines_keys = list(credentials.get('lines', {}).keys())
                if not lines_keys:
                    st.info("Chưa có LINE nào. Vui lòng tạo LINE trước.")
                else:
                    selected_line_for_mac = st.selectbox("1. Chọn LINE để mở thiết lập:", lines_keys, key="mac_line_select")
                    
                    if selected_line_for_mac:
                        st.markdown(f"**Danh sách Máy thuộc {selected_line_for_mac}:**")
                        line_machines = credentials['lines'][selected_line_for_mac].get('machines', {})
                        
                        mac_list = []
                        for m_num, m_info in line_machines.items():
                            mac_list.append({
                                "Số máy": m_num,
                                "Tên máy": m_info.get('name', ''),
                                "Định dạng file": m_info.get('format', ''),
                                "Đường dẫn": m_info.get('path', ''),
                                "Kích hoạt (Lấy dữ liệu)": "✅ Có" if m_info.get('active') else "❌ Chưa lấy"
                            })
                        
                        if mac_list:
                            st.table(pd.DataFrame(mac_list))
                        else:
                            st.warning("LINE này hiện chưa có thiết lập máy nào.")

                        st.markdown("**2. Thêm mới / Cập nhật Máy:**")
                        with st.form("machine_setup_form", clear_on_submit=True):
                            col_m1, col_m2 = st.columns(2)
                            with col_m1:
                                mac_num = st.text_input("Số máy* (Mã định danh):", placeholder="VD: M01")
                                mac_name = st.text_input("Tên máy*:", placeholder="VD: Máy Cắt CNC")
                            with col_m2:
                                mac_format = st.selectbox("Định dạng file:", ["CSV", "Excel", "TXT", "JSON", "Khác"])
                                mac_path = st.text_input("Đường dẫn / Link Folder:", placeholder="VD: C:/Data/May01")
                            
                            mac_active = st.checkbox("Kích hoạt (Tích chọn để hệ thống bắt đầu lấy dữ liệu từ máy này)", value=True)
                            
                            if st.form_submit_button("Lưu cấu hình Máy"):
                                if mac_num.strip() == "" or mac_name.strip() == "":
                                    st.error("⚠️ 'Số máy' và 'Tên máy' không được để trống!")
                                else:
                                    if 'machines' not in credentials['lines'][selected_line_for_mac]:
                                        credentials['lines'][selected_line_for_mac]['machines'] = {}
                                    
                                    credentials['lines'][selected_line_for_mac]['machines'][mac_num.strip()] = {
                                        'name': mac_name.strip(),
                                        'format': mac_format,
                                        'path': mac_path.strip(),
                                        'active': mac_active
                                    }
                                    save_users(credentials)
                                    st.success(f"✅ Đã lưu cấu hình máy '{mac_num.strip()}' vào '{selected_line_for_mac}'!")
                                    time.sleep(1.5)
                                    st.rerun()
                        
                        if line_machines:
                            st.markdown("**3. Xóa máy khỏi LINE:**")
                            col_del1, col_del2 = st.columns([3, 1])
                            with col_del1:
                                del_mac_num = st.selectbox("Chọn máy cần xóa:", list(line_machines.keys()))
                            with col_del2:
                                st.write("") # Căn chỉnh nút cho đều với ô nhập
                                if st.button("Xác nhận Xóa"):
                                    del credentials['lines'][selected_line_for_mac]['machines'][del_mac_num]
                                    save_users(credentials)
                                    st.success(f"✅ Đã xóa máy '{del_mac_num}' khỏi LINE {selected_line_for_mac}!")
                                    time.sleep(1.5)
                                    st.rerun()

            # --- TẠO LINE MỚI ---
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
                        if new_lname.strip() == "":
                            st.error("⚠️ Tên LINE không được để trống!")
                        elif new_lname in credentials.get('lines', {}):
                            st.error("⚠️ Tên LINE này đã tồn tại!")
                        else:
                            credentials['lines'][new_lname] = {
                                'number': new_lnumber.strip() if new_lnumber.strip() != "" else "Chưa cập nhật",
                                'area': new_larea.strip() if new_larea.strip() != "" else "Chưa cập nhật",
                                'manager': new_lmanager, 
                                'description': new_ldescription.strip(),
                                'status': new_lstatus,
                                'machines': {} # Khởi tạo danh sách máy trống
                            }
                            save_users(credentials)
                            st.success(f"✅ Đã tạo LINE '{new_lname}' thành công!")
                            time.sleep(1.5)
                            st.rerun()

            # --- CHỈNH SỬA LINE ---
            with st.expander("✏️ Chỉnh sửa / Bỏ phê duyệt LINE"):
                lines_keys = list(credentials.get('lines', {}).keys())
                if not lines_keys:
                    st.info("Không có LINE nào để chỉnh sửa.")
                else:
                    edit_lname = st.selectbox("Chọn LINE cần sửa:", lines_keys, key="edit_line_select")
                    if edit_lname:
                        line_info = credentials['lines'][edit_lname]
                        with st.form("edit_line_form"):
                            col1, col2 = st.columns(2)
                            with col1:
                                el_number = st.text_input("Số LINE:", value=line_info.get('number', '')) 
                                el_area = st.text_input("Khu vực:", value=line_info.get('area', '')) 
                                
                                curr_manager = line_info.get('manager', 'Chưa phân công')
                                if curr_manager not in manager_options:
                                    manager_options.append(curr_manager)
                                el_manager = st.selectbox("Người phụ trách:", manager_options, index=manager_options.index(curr_manager))
                            
                            with col2:
                                el_desc = st.text_input("Mô tả:", value=line_info.get('description', ''))
                                el_status = st.selectbox("Trạng thái:", ["Đã phê duyệt", "Không phê duyệt"], index=0 if line_info.get('status') == 'Đã phê duyệt' else 1)
                            
                            if st.form_submit_button("Cập nhật LINE"):
                                credentials['lines'][edit_lname]['number'] = el_number.strip() 
                                credentials['lines'][edit_lname]['area'] = el_area.strip()
                                credentials['lines'][edit_lname]['manager'] = el_manager 
                                credentials['lines'][edit_lname]['description'] = el_desc.strip()
                                credentials['lines'][edit_lname]['status'] = el_status
                                save_users(credentials)
                                st.success(f"✅ Đã cập nhật LINE '{edit_lname}'!")
                                time.sleep(1.5)
                                st.rerun()
                                
            # --- PHÊ DUYỆT LINE ---
            with st.expander("✅ Phê duyệt LINE"):
                pending_lines = [k for k, v in credentials.get('lines', {}).items() if v.get('status') != 'Đã phê duyệt']
                if not pending_lines:
                    st.success("Tuyệt vời! Tất cả các LINE đều đang ở trạng thái Đã phê duyệt.")
                else:
                    approve_lname = st.selectbox("Chọn LINE để phê duyệt:", pending_lines)
                    if st.button("Xác nhận Phê duyệt"):
                        credentials['lines'][approve_lname]['status'] = 'Đã phê duyệt'
                        save_users(credentials)
                        st.success(f"✅ Đã phê duyệt thành công LINE '{approve_lname}'!")
                        time.sleep(1.5)
                        st.rerun()

            # --- XÓA LINE ---
            with st.expander("❌ Xóa LINE"):
                if not lines_keys:
                    st.info("Không có LINE nào để xóa.")
                else:
                    del_lname = st.selectbox("Chọn LINE cần xóa:", lines_keys, key="del_line_select")
                    st.warning(f"⚠️ Chú ý: Việc xóa LINE sẽ không ảnh hưởng đến tài khoản đang có tên LINE này. Bạn có chắc muốn xóa '{del_lname}' khỏi danh sách?")
                    if st.button("Xác nhận Xóa LINE"):
                        del credentials['lines'][del_lname]
                        save_users(credentials)
                        st.success(f"✅ Đã xóa LINE '{del_lname}'!")
                        time.sleep(1.5)
                        st.rerun()

    # ================= KHU VỰC DÀNH CHO NHÂN VIÊN CON =================
    else:
        st.info("👤 Quyền Nhân viên: Bạn chỉ được phép tra cứu dữ liệu từ nguồn do Quản trị viên cập nhật.")
        if os.path.exists("data_server.csv"):
            df = pd.read_csv("data_server.csv")
        else:
            st.warning("⚠️ Quản trị viên chưa cập nhật cơ sở dữ liệu nào lên hệ thống.")

    # ================= KHU VỰC HỎI ĐÁP AI (CHUNG) =================
    
    is_line_approved = True
    if user_role != 'admin' and current_line not in ["Chưa cập nhật", "Tất cả"]:
        line_data = credentials.get('lines', {}).get(current_line, {})
        if line_data and line_data.get('status') != 'Đã phê duyệt':
            is_line_approved = False

    if not is_line_approved:
        st.error(f"⛔ Truy cập bị từ chối: LINE '{current_line}' của bạn hiện đang ở trạng thái 'Không phê duyệt' (hoặc đã bị bỏ phê duyệt). Hệ thống tạm thời khóa chức năng truy xuất dữ liệu đối với LINE này!")
    elif df is not None:
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
