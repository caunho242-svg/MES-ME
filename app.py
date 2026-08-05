import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
import os
import json
import time
import io

# -------------------------------------------------------------------
# 0. THIẾT LẬP BẢO MẬT HỆ THỐNG
# -------------------------------------------------------------------
# Đảm bảo thư mục dữ liệu nội bộ được tạo an toàn (Chống Path Traversal)
ALLOWED_DATA_DIR = os.path.abspath("./Data_Server")
os.makedirs(ALLOWED_DATA_DIR, exist_ok=True)

# Lấy khóa bảo mật Cookie từ Streamlit Secrets, nếu không có dùng fallback (cảnh báo)
try:
    COOKIE_KEY = st.secrets["COOKIE_KEY"]
except (KeyError, FileNotFoundError):
    COOKIE_KEY = "fallback_unsafe_key_change_me_in_production"

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
st.set_page_config(page_title="MES Dashboard & AI", layout="wide", page_icon="🏭")

credentials = load_users()

# BẢO MẬT 1: Không hardcode key mã hóa trên source code
authenticator = stauth.Authenticate(
    credentials,
    'mes_secure_cookie',
    COOKIE_KEY,
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
    if COOKIE_KEY == "fallback_unsafe_key_change_me_in_production":
         st.warning("⚠️ Cảnh báo Bảo mật: Hệ thống đang dùng khóa cookie mặc định. Vui lòng cấu hình st.secrets['COOKIE_KEY']!")

    # -------------------------------------------------------------------
    # 3. GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
    # -------------------------------------------------------------------
    authenticator.logout('Đăng xuất', 'sidebar')
    
    current_user_info = credentials['usernames'].get(username, {})
    current_position = current_user_info.get('position', 'Nhân viên')
    current_department = current_user_info.get('department', 'Chưa rõ')
    current_line = current_user_info.get('line', 'Chưa rõ')
    
    st.title(f"🏭 Hệ Thống MES & Trợ Lý AI")
    st.caption(f"👤 Xin chào: **{name}** | Chức vụ: **{current_position}** | Phòng ban: **{current_department}** | LINE: **{current_line}**")
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
    
    if can_view:
        menu_options.extend(["📈 Dashboard Tổng Quan", "🔍 Tra cứu & Báo cáo", "🖨️ In Tem Nhãn", "📊 DATA Máy Móc"])
        
    if can_edit_data: menu_options.append("📂 Cập nhật Dữ liệu")
    if can_edit_account: menu_options.append("👥 Quản lý Tài khoản")
    if can_edit_line: menu_options.append("🏭 Quản lý LINE")
        
    # ================= ĐIỀU HƯỚNG TABS =================
    if menu_options:
        if "admin_menu" not in st.session_state or st.session_state.admin_menu not in menu_options:
            st.session_state.admin_menu = menu_options[0]

        selected_tab = st.radio("Điều hướng Menu:", menu_options, horizontal=True, key="admin_menu", label_visibility="collapsed")
        st.markdown("---")
        
        # ---------------------------------------------------------
        # TAB 1: DASHBOARD TỔNG QUAN (ĐÃ ĐƯỢC NÂNG CẤP)
        # ---------------------------------------------------------
        if selected_tab == "📈 Dashboard Tổng Quan":
            st.subheader("📈 Dashboard Sản Xuất Tổng Quan")
            
            if df is None or df.empty:
                st.info("💡 Chưa có dữ liệu để hiển thị Dashboard. Vui lòng vào tab '📂 Cập nhật Dữ liệu' để tải file lên.")
            else:
                # 1. TÍNH TOÁN CÁC CHỈ SỐ
                total_records = len(df)
                
                # Tìm cột trạng thái để đếm NG/OK
                status_col = None
                for col in df.columns:
                    if any(kw in str(col).lower() for kw in ["status", "kết quả", "đánh giá", "trạng thái", "result"]):
                        status_col = col
                        break
                
                if status_col:
                    ng_count = len(df[df[status_col].astype(str).str.upper().isin(["NG", "FAIL", "LỖI", "REJECT"])])
                else:
                    ng_count = 0
                    
                ok_count = total_records - ng_count
                ng_rate = round((ng_count / total_records) * 100, 2) if total_records > 0 else 0

                # 2. HIỂN THỊ METRICS (Thẻ KPI)
                col1, col2, col3, col4 = st.columns(4)
                col1.metric(label="📦 Tổng Sản Lượng", value=f"{total_records:,} SP")
                col2.metric(label="✅ Sản Phẩm OK", value=f"{ok_count:,} SP")
                col3.metric(label="❌ Sản Phẩm NG (Lỗi)", value=f"{ng_count:,} SP")
                col4.metric(label="📉 Tỉ Lệ Lỗi (Defect Rate)", value=f"{ng_rate}%")
                
                st.markdown("---")
                
                # 3. HIỂN THỊ BIỂU ĐỒ TRỰC QUAN
                chart_col1, chart_col2 = st.columns([1, 2])
                
                with chart_col1:
                    st.markdown("##### 📊 Tỉ lệ Chất lượng (OK vs NG)")
                    quality_df = pd.DataFrame({
                        "Trạng thái": ["OK", "NG"],
                        "Số lượng": [ok_count, ng_count]
                    }).set_index("Trạng thái")
                    st.bar_chart(quality_df)

                with chart_col2:
                    st.markdown("##### 📈 Biểu đồ Xu hướng (Các thông số kỹ thuật)")
                    # Lấy các cột dữ liệu số để vẽ biểu đồ đường
                    numeric_df = df.select_dtypes(include='number')
                    if not numeric_df.empty:
                        # Hiển thị 100 bản ghi gần nhất để tránh lag
                        st.line_chart(numeric_df.tail(100))
                    else:
                        st.info("Không có cột dữ liệu dạng số (Ví dụ: Nhiệt độ, Kích thước...) để vẽ biểu đồ.")

                st.markdown("---")
                
                # 4. BẢNG DỮ LIỆU ĐƯỢC FORMAT LẠI (Sắp xếp mới nhất lên đầu)
                st.markdown("##### 📋 Bảng Dữ Liệu Sản Xuất Mới Nhất")
                st.caption("Hiển thị 100 dòng cập nhật gần nhất (Dòng mới nhất xếp trên cùng).")
                st.dataframe(
                    df.tail(100).iloc[::-1], # Đảo ngược thứ tự để Data mới nhất lên đầu
                    use_container_width=True,
                    height=300
                )

        # ---------------------------------------------------------
        # TAB 2: TRA CỨU, BÁO CÁO & AI
        # ---------------------------------------------------------
        elif selected_tab == "🔍 Tra cứu & Báo cáo":
            st.subheader("🔍 Tra cứu Dữ liệu & Xuất Báo cáo")
            
            if df is None:
                df = pd.DataFrame(columns=["Chưa có dữ liệu"])

            with st.expander("🎯 Công cụ Tìm kiếm Chuyên sâu", expanded=True):
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1: s_barcode = st.text_input("🏷️ Barcode:")
                with col_s2: s_lot = st.text_input("📦 Lot Number:")
                with col_s3: s_model = st.text_input("💻 Model:")
                with col_s4: s_serial = st.text_input("🔢 Serial:")
                
                st.markdown("---")
                col_f1, col_f2 = st.columns([7, 3])
                with col_f1: search_kw = st.text_input("🔎 Tìm kiếm tự do (Keyword chung):")
                with col_f2: enable_advanced = st.checkbox("⚙️ Bật Lọc Toán Học (>, <, =)")

                df_filtered = df.copy()

                def filter_by_kw(dataframe, keyword):
                    if keyword.strip():
                        mask = dataframe.astype(str).apply(lambda row: row.str.contains(keyword.strip(), case=False, na=False)).any(axis=1)
                        return dataframe[mask]
                    return dataframe

                df_filtered = filter_by_kw(df_filtered, s_barcode)
                df_filtered = filter_by_kw(df_filtered, s_lot)
                df_filtered = filter_by_kw(df_filtered, s_model)
                df_filtered = filter_by_kw(df_filtered, s_serial)
                df_filtered = filter_by_kw(df_filtered, search_kw)

                if enable_advanced:
                    st.markdown("##### 🎯 Điều kiện lọc toán học theo cột:")
                    cols = list(df.columns)
                    ca1, ca2, ca3 = st.columns(3)
                    with ca1: selected_col = st.selectbox("Chọn cột:", cols)
                    with ca2: filter_type = st.selectbox("Kiểu lọc:", ["Khớp chính xác", "Lớn hơn (>)", "Nhỏ hơn (<)"])
                    with ca3: filter_val = st.text_input("Giá trị lọc:")
                    
                    if filter_val.strip() and not df_filtered.empty:
                        val = filter_val.strip()
                        try:
                            if filter_type == "Khớp chính xác":
                                df_filtered = df_filtered[df_filtered[selected_col].astype(str).str.lower() == val.lower()]
                            elif filter_type == "Lớn hơn (>)":
                                df_filtered = df_filtered[pd.to_numeric(df_filtered[selected_col], errors='coerce') > float(val)]
                            elif filter_type == "Nhỏ hơn (<)":
                                df_filtered = df_filtered[pd.to_numeric(df_filtered[selected_col], errors='coerce') < float(val)]
                        except Exception:
                            # BẢO MẬT 2: Ẩn thông báo lỗi chi tiết hệ thống
                            st.warning("⚠️ Dữ liệu cột này không phải dạng số để so sánh Lớn/Nhỏ.")

            tab_data, tab_ai, tab_report = st.tabs(["🗄️ Dữ liệu đã lọc", "🤖 Trợ lý AI Phân tích", "📥 Xuất Báo cáo (Excel/PDF)"])
            
            with tab_data:
                st.caption(f"📌 **Hiển thị:** {len(df_filtered)} / {len(df)} dòng dữ liệu")
                st.dataframe(df_filtered, use_container_width=True, height=400)

            with tab_ai:
                st.info("💡 AI sẽ phân tích dựa trên dữ liệu BẠN VỪA LỌC ở trên.")
                query = st.text_input("💬 Nhập câu hỏi/yêu cầu cho AI:")
                if query:
                    if not openai_api_key: st.error("⚠️ Vui lòng nhập OpenAI API Key!")
                    elif len(df_filtered) == 0 or (len(df_filtered) == 1 and "Chưa có dữ liệu" in df_filtered.columns):
                        st.warning("⚠️ Không có dữ liệu để phân tích.")
                    else:
                        with st.spinner("AI đang xử lý..."):
                            try:
                                llm = ChatOpenAI(temperature=0, model="gpt-4o-mini", api_key=openai_api_key)
                                # BẢO MẬT 3: Tắt allow_dangerous_code (Chống RCE)
                                agent = create_pandas_dataframe_agent(llm, df_filtered, verbose=True, allow_dangerous_code=False)
                                response = agent.invoke({"input": query})
                                st.success("✅ Kết quả:")
                                st.write(response["output"])
                            except Exception:
                                # BẢO MẬT 2: Ẩn Data Leakage
                                st.error("❌ Đã xảy ra lỗi khi phân tích dữ liệu. Vui lòng cấu hình lại câu hỏi hoặc liên hệ Quản trị viên.")
                                
            with tab_report:
                st.markdown("### 📥 Xuất Báo Cáo Chuyên Nghiệp")
                if df_filtered.empty or (len(df_filtered) == 1 and "Chưa có dữ liệu" in df_filtered.columns):
                    st.warning("⚠️ Không có dữ liệu để xuất báo cáo.")
                else:
                    col_export1, col_export2 = st.columns(2)
                    with col_export1:
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_filtered.to_excel(writer, index=False, sheet_name='Bao_Cao_MES')
                        excel_data = output.getvalue()
                        
                        st.download_button(
                            label="📥 Tải Báo Cáo (.XLSX)",
                            data=excel_data,
                            file_name="Bao_Cao_MES.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
                    with col_export2:
                        st.info("📄 **Để xuất PDF:** Mở file Excel vừa tải xuống -> Bấm File -> Print -> Save as PDF.")

        # ---------------------------------------------------------
        # TAB 3: IN TEM NHÃN ZEBRA
        # ---------------------------------------------------------
        elif selected_tab == "🖨️ In Tem Nhãn":
            st.subheader("🖨️ Trình Điều Khiển Máy In Tem Zebra ZD421")
            st.info("Hệ thống sẽ tạo ra mã nguồn ZPL chuẩn mực. Bạn có thể tải file `.zpl` về để đẩy vào máy in Zebra.")
            
            with st.form("print_label_form"):
                col1, col2 = st.columns(2)
                with col1:
                    p_model = st.text_input("Mã Model (Part No):", value="MDL-10293")
                    p_lot = st.text_input("Lot Number:", value="LOT-2026-08")
                with col2:
                    p_serial = st.text_input("Serial Number:", value="SN0001")
                    p_barcode = st.text_input("Dữ liệu Barcode:", value="MDL-10293-LOT-2026-08-SN0001")
                
                print_qty = st.number_input("Số lượng tem cần in:", min_value=1, max_value=100, value=1)
                
                if st.form_submit_button("🔨 Tạo Mã In ZPL", type="primary"):
                    zpl_code = f"""^XA
^PW400
^LL240
^FO20,20^A0N,25,25^FDModel: {p_model}^FS
^FO20,55^A0N,25,25^FDLot: {p_lot}^FS
^FO20,90^A0N,25,25^FDSerial: {p_serial}^FS
^FO20,130^BCN,60,Y,N,N^FD{p_barcode}^FS
^PQ{print_qty}
^XZ"""
                    st.success("✅ Đã tạo mã ZPL thành công!")
                    st.code(zpl_code, language="text")
                    
                    st.download_button(
                        label="🖨️ Tải File In (.zpl)",
                        data=zpl_code,
                        file_name=f"label_{p_serial}.zpl",
                        mime="text/plain"
                    )

        # ---------------------------------------------------------
        # TAB 4: DATA TỔNG HỢP TỪ CÁC LINE (HỖ TRỢ .XLSB)
        # ---------------------------------------------------------
        elif selected_tab == "📊 DATA Máy Móc":
            st.subheader("📊 Trích Xuất Dữ Liệu Trực Tiếp Từ Máy / Server")
            st.info("💡 Hỗ trợ đọc file CSV, Excel, XLSB trực tiếp từ thư mục Mạng (LAN/Server).")
            
            lines_data = credentials.get('lines', {})
            approved_lines_data = {k: v for k, v in lines_data.items() if v.get('status') == 'Đã phê duyệt'}
            
            if not approved_lines_data:
                st.warning("⚠️ Chưa có LINE nào được phê duyệt.")
            else:
                if st.button("🔄 Quét lại thư mục dữ liệu", type="primary"): st.rerun()
                    
                for lname, linfo in approved_lines_data.items():
                    machines = linfo.get('machines', {})
                    active_machines = {k: v for k, v in machines.items() if v.get('active')}
                    
                    if active_machines:
                        st.markdown(f"### 🏭 LINE: {lname}")
                        for m_num, m_info in active_machines.items():
                            m_name = m_info.get('name', 'Chưa có tên')
                            m_path = m_info.get('path', '')
                            m_format = m_info.get('format', 'CSV')
                            
                            with st.expander(f"🖥️ Máy: {m_name} (ID: {m_num}) | 📁 File: {m_format} | 📍 {m_path}"):
                                if not m_path:
                                    st.warning("⚠️ Chưa cấu hình đường dẫn file.")
                                    continue
                                    
                                # BẢO MẬT 4: Xác thực thư mục (Chống Path Traversal)
                                requested_path = os.path.abspath(m_path)
                                if not requested_path.startswith(ALLOWED_DATA_DIR):
                                    st.error(f"⛔ BẢO MẬT: File phải nằm trong thư mục được cho phép ({ALLOWED_DATA_DIR})!")
                                    continue
                                
                                if not os.path.exists(requested_path):
                                    st.error(f"❌ Không tìm thấy file. (Kiểm tra lại kết nối mạng LAN/Server)")
                                    continue
                                    
                                try:
                                    m_df = None
                                    if m_format == "CSV": m_df = pd.read_csv(requested_path)
                                    elif m_format == "Excel": m_df = pd.read_excel(requested_path)
                                    elif m_format == "XLSB": m_df = pd.read_excel(requested_path, engine='pyxlsb')
                                    elif m_format == "JSON": m_df = pd.read_json(requested_path)
                                    elif m_format == "TXT": m_df = pd.read_csv(requested_path, sep=None, engine='python')
                                    else: st.warning(f"⚠️ Định dạng '{m_format}' chưa được hỗ trợ.")
                                        
                                    if m_df is not None:
                                        st.success(f"✅ Tải thành công {len(m_df)} dòng dữ liệu.")
                                        st.dataframe(m_df.head(100), use_container_width=True)
                                except Exception:
                                    # BẢO MẬT 2: Ẩn báo lỗi chi tiết
                                    st.error("❌ Lỗi cấu trúc file hoặc định dạng không tương thích. Vui lòng kiểm tra lại file gốc.")
                        st.markdown("---")

        # ---------------------------------------------------------
        # CÁC TAB QUẢN LÝ (DATA, ACCOUNT, LINE)
        # ---------------------------------------------------------
        elif selected_tab == "📂 Cập nhật Dữ liệu":
            uploaded_file = st.file_uploader("📂 Chọn file dữ liệu (Excel/CSV/XLSB) để cập nhật Data gốc", type=["xlsx", "xls", "xlsb", "csv"])
            if uploaded_file is not None:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith('.xlsb'):
                    df = pd.read_excel(uploaded_file, engine='pyxlsb')
                else:
                    df = pd.read_excel(uploaded_file)
                df.to_csv("data_server.csv", index=False)
                st.success("✅ Đã cập nhật cơ sở dữ liệu chung!")

        elif selected_tab == "👥 Quản lý Tài khoản":
            st.subheader("📋 Quản lý & Phân quyền người dùng")
            user_list = []
            for uname, info in credentials['usernames'].items():
                perms = info.get('permissions', {})
                perm_str = []
                if perms.get('view', True): perm_str.append("👁️ Tra cứu")
                if perms.get('edit_data') or info.get('role') == 'admin': perm_str.append("📂 Cập nhật Data")
                if perms.get('edit_line') or info.get('role') == 'admin': perm_str.append("🏭 Quản lý Line")
                if perms.get('edit_account') or info.get('role') == 'admin': perm_str.append("👑 Admin")
                
                user_list.append({
                    "Tài khoản": uname, 
                    "Tên": info.get('name', ''), 
                    "Chức vụ": info.get('position', ''),
                    "Phân quyền": " | ".join(perm_str)
                })
            st.table(pd.DataFrame(user_list))

            with st.expander("➕ Cấp tài khoản mới"):
                with st.form("new_user_form", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_user = st.text_input("Tên đăng nhập*:")
                        new_name = st.text_input("Tên hiển thị*:")
                        new_position = st.text_input("Chức vụ:") 
                    with c2:
                        new_dept = st.text_input("Phòng ban:")
                        new_line = st.selectbox("LINE:", line_options)
                        new_pass = st.text_input("Mật khẩu*:", type="password")
                    
                    p1, p2 = st.columns(2)
                    with p1:
                        new_perm_view = st.checkbox("👁️ Tra cứu & Xem Dashboard", value=True)
                        new_perm_data = st.checkbox("📂 Cập nhật file dữ liệu tổng", value=False)
                    with p2:
                        new_perm_line = st.checkbox("🏭 Quản lý LINE & Máy móc", value=False)
                        new_perm_acc = st.checkbox("👥 Quản trị viên (Toàn quyền)", value=False)
                    
                    if st.form_submit_button("Tạo tài khoản"):
                        if new_user == "" or new_pass == "" or new_name == "": st.error("⚠️ Điền đủ thông tin bắt buộc (*)")
                        elif new_user in credentials['usernames']: st.error("⚠️ Tài khoản đã tồn tại!")
                        else:
                            temp_cred = {'usernames': {new_user: {'password': new_pass}}}
                            stauth.Hasher.hash_passwords(temp_cred)
                            credentials['usernames'][new_user] = {
                                'name': new_name, 'password': temp_cred['usernames'][new_user]['password'], 
                                'role': 'admin' if new_perm_acc else 'user',
                                'position': new_position, 'department': new_dept, 'line': new_line,
                                'permissions': {'view': new_perm_view, 'edit_data': new_perm_data, 'edit_line': new_perm_line, 'edit_account': new_perm_acc}
                            }
                            save_users(credentials); st.success("✅ Đã tạo!"); time.sleep(1); st.rerun()

        elif selected_tab == "🏭 Quản lý LINE":
            st.subheader("🏭 Thiết lập Nhà máy & Thiết bị")
            
            with st.expander("➕ Tạo LINE mới"):
                with st.form("new_line_form", clear_on_submit=True):
                    new_lname = st.text_input("Tên LINE*:")
                    if st.form_submit_button("Tạo LINE"):
                        if new_lname.strip() != "":
                            credentials['lines'][new_lname] = {'status': 'Đã phê duyệt', 'machines': {}}
                            save_users(credentials); st.success("✅ Tạo LINE thành công!"); time.sleep(1); st.rerun()

            st.markdown("---")
            lines_data = credentials.get('lines', {})
            for lname, linfo in lines_data.items():
                with st.expander(f"🏭 LINE: {lname} | Máy: {len(linfo.get('machines', {}))}"):
                    line_machines = linfo.get('machines', {})
                    mac_list = [{"ID": m, "Tên": i.get('name'), "Format": i.get('format'), "Path": i.get('path')} for m, i in line_machines.items()]
                    df_mac = pd.DataFrame(mac_list)
                    if not df_mac.empty: st.dataframe(df_mac, hide_index=True, use_container_width=True)
                    
                    with st.form(f"add_mac_{lname}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            m_num = st.text_input("Mã Máy*:")
                            m_name = st.text_input("Tên Máy*:")
                        with c2:
                            m_format = st.selectbox("Định dạng file:", ["CSV", "Excel", "XLSB", "TXT", "JSON"]) 
                            m_path = st.text_input(f"Đường dẫn (Bắt buộc phải nằm trong {ALLOWED_DATA_DIR}):", value=f"{ALLOWED_DATA_DIR}/...")
                            
                        if st.form_submit_button("Thêm Máy"):
                            if m_num and m_name:
                                if 'machines' not in credentials['lines'][lname]: credentials['lines'][lname]['machines'] = {}
                                credentials['lines'][lname]['machines'][m_num] = {'name': m_name, 'format': m_format, 'path': m_path, 'active': True}
                                save_users(credentials); st.success("✅ Đã thêm!"); time.sleep(1); st.rerun()
