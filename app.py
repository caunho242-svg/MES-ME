import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import os
import json
import time
import io
from pathlib import Path
import streamlit.components.v1 as components

# -------------------------------------------------------------------
# 0. THIẾT LẬP HỆ THỐNG VÀ BẢO MẬT
# -------------------------------------------------------------------
ALLOWED_DATA_DIR = Path("./Data_Server").resolve()
ALLOWED_DATA_DIR.mkdir(parents=True, exist_ok=True)

try:
    COOKIE_KEY = st.secrets["COOKIE_KEY"]
except (KeyError, FileNotFoundError):
    COOKIE_KEY = "fallback_unsafe_key_change_me_in_production"

USER_FILE = "users.json"

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if 'lines' not in data: data['lines'] = {}
            return data
    else:
        default_creds = {
            'usernames': {
                'admin': {
                    'name': 'Quản trị viên', 'password': 'admin123', 'role': 'admin',
                    'position': 'Quản lý', 'department': 'Hệ thống', 'line': 'Tất cả',
                    'permissions': {'view': True, 'edit_data': True, 'edit_line': True, 'edit_account': True}
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
# 1. GIAO DIỆN ĐĂNG NHẬP
# -------------------------------------------------------------------
st.set_page_config(page_title="MES Dashboard & AI", layout="wide", page_icon="🏭")

credentials = load_users()
authenticator = stauth.Authenticate(
    credentials, 'mes_secure_cookie', COOKIE_KEY, cookie_expiry_days=1
)

authenticator.login(location='main')

authentication_status = st.session_state.get('authentication_status')
name = st.session_state.get('name')
username = st.session_state.get('username')

if authentication_status == False:
    st.error('⛔ Tài khoản hoặc mật khẩu không chính xác!')
elif authentication_status == None:
    st.warning('🔐 Vui lòng nhập thông tin tài khoản để truy cập hệ thống MES.')
elif authentication_status:
    authenticator.logout('Đăng xuất', 'sidebar')
    
    current_user_info = credentials['usernames'].get(username, {})
    current_position = current_user_info.get('position', 'Nhân viên')
    current_department = current_user_info.get('department', 'Chưa rõ')
    current_line = current_user_info.get('line', 'Chưa rõ')
    
    st.title(f"🏭 Hệ Thống MES & Quản Trị Sản Xuất")
    st.caption(f"👤 Tên: **{name}** | Vị trí: **{current_position}** | Phòng ban: **{current_department}** | Phụ trách: **{current_line}**")
    st.markdown("---")

    df = None 
    if os.path.exists("data_server.csv"):
        try:
            df = pd.read_csv("data_server.csv")
        except Exception:
            df = None

    approved_lines = [lname for lname, linfo in credentials.get('lines', {}).items() if linfo.get('status') == 'Đã phê duyệt']
    line_options = ["Chưa cập nhật", "Tất cả"] + approved_lines

    user_role = current_user_info.get('role', 'user')
    user_perms = current_user_info.get('permissions', {})
    
    can_view = user_perms.get('view', True)
    can_edit_data = user_perms.get('edit_data', False) or user_role == 'admin'
    can_edit_account = user_perms.get('edit_account', False) or user_role == 'admin'
    can_edit_line = user_perms.get('edit_line', False) or user_role == 'admin'

    menu_options = []
    if can_view: menu_options.extend(["📈 Dashboard", "📊 Báo Cáo Downtime (HTML)", "🔍 Tra cứu & Dữ liệu", "🖨️ In Tem"])
    if can_edit_data: menu_options.append("📂 Cập nhật File")
    if can_edit_account: menu_options.append("👥 Quản lý Users")
    if can_edit_line: menu_options.append("🏭 Quản lý LINE")
        
    if menu_options:
        if "admin_menu" not in st.session_state or st.session_state.admin_menu not in menu_options:
            st.session_state.admin_menu = menu_options[0]

        selected_tab = st.radio("Điều hướng Hệ thống:", menu_options, horizontal=True, key="admin_menu", label_visibility="collapsed")
        st.markdown("---")
        
        # ---------------------------------------------------------
        # TAB 1: DASHBOARD MẶC ĐỊNH
        # ---------------------------------------------------------
        if selected_tab == "📈 Dashboard":
            st.subheader("📈 Dashboard Sản Xuất Tổng Quan")
            if df is None or df.empty:
                st.info("💡 Chưa có dữ liệu. Vui lòng vào tab '📂 Cập nhật File' để tải lên file dữ liệu.")
            else:
                total_records = len(df)
                status_col = next((col for col in df.columns if any(kw in str(col).lower() for kw in ["status", "kết quả", "trạng thái", "result"])), None)
                ng_count = len(df[df[status_col].astype(str).str.upper().isin(["NG", "FAIL", "LỖI", "REJECT"])]) if status_col else 0
                ok_count = total_records - ng_count
                ng_rate = round((ng_count / total_records) * 100, 2) if total_records > 0 else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📦 Tổng Sản Lượng", f"{total_records:,} SP")
                c2.metric("✅ Hàng OK", f"{ok_count:,} SP")
                c3.metric("❌ Hàng NG", f"{ng_count:,} SP")
                c4.metric("📉 Tỉ Lệ Lỗi", f"{ng_rate}%")
                st.markdown("---")
                st.dataframe(df.tail(100).iloc[::-1], use_container_width=True, height=400)

        # ---------------------------------------------------------
        # TAB 2: GIAO DIỆN HTML QUẢN LÝ DOWNTIME (CHUẨN ẢNH MẪU)
        # ---------------------------------------------------------
        elif selected_tab == "📊 Báo Cáo Downtime (HTML)":
            st.subheader("📊 Giao Diện Phân Tích Downtime & Sức Khỏe Thiết Bị")
            
            # Kiểm tra và render file HTML giao diện quản lý
            html_path = Path("dashboard.html")
            if html_path.exists():
                components.html(html_path.read_text(encoding="utf-8"), height=950, scrolling=True)
            else:
                st.warning("⚠️ Chưa tìm thấy file `dashboard.html` trên hệ thống. Đang hiển thị giao diện mẫu tích hợp sẵn:")
                
                # HTML dự phòng hiển thị trực tiếp nếu chưa tạo file
                embedded_html = """
                <div style="background: #f8fafc; padding: 20px; font-family: sans-serif; border-radius: 8px;">
                    <div style="background: #b91c1c; color: white; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                        <h3 style="margin: 0 0 5px 0; font-size: 14px;">🚨 CẦN LÀM GÌ TRONG PHẠM VI ĐANG XEM</h3>
                        <p style="margin: 0; font-size: 13px;">Chưa xác định downtime lớn nhất (2.650 phút) -> Ưu tiên xử lý 5-Why ngay tại trạm.</p>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px;">
                        <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #e2e8f0;">
                            <div style="font-size: 11px; color: #64748b; font-weight: bold;">DOWNTIME RATE</div>
                            <div style="font-size: 22px; font-weight: bold; color: #dc2626; margin-top: 5px;">12.5%</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #e2e8f0;">
                            <div style="font-size: 11px; color: #64748b; font-weight: bold;">AVAILABILITY</div>
                            <div style="font-size: 22px; font-weight: bold; color: #1e293b; margin-top: 5px;">87.5%</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #e2e8f0;">
                            <div style="font-size: 11px; color: #64748b; font-weight: bold;">MTBF (PHÚT)</div>
                            <div style="font-size: 22px; font-weight: bold; color: #1e293b; margin-top: 5px;">316</div>
                        </div>
                        <div style="background: white; padding: 15px; border-radius: 6px; text-align: center; border: 1px solid #e2e8f0;">
                            <div style="font-size: 11px; color: #64748b; font-weight: bold;">SỐ SỰ CỐ</div>
                            <div style="font-size: 22px; font-weight: bold; color: #1e293b; margin-top: 5px;">247</div>
                        </div>
                    </div>
                </div>
                """
                components.html(embedded_html, height=350, scrolling=False)

        # ---------------------------------------------------------
        # TAB 3: TRA CỨU & DỮ LIỆU
        # ---------------------------------------------------------
        elif selected_tab == "🔍 Tra cứu & Dữ liệu":
            st.subheader("🔍 Tra Cứu Dữ Liệu Chi Tiết")
            if df is None: df = pd.DataFrame(columns=["Chưa có dữ liệu"])
            kw = st.text_input("🔎 Tìm kiếm từ khóa bất kỳ:")
            if kw:
                df_res = df[df.astype(str).apply(lambda r: r.str.contains(kw, case=False, na=False)).any(axis=1)]
                st.dataframe(df_res, use_container_width=True)
            else:
                st.dataframe(df, use_container_width=True)

        # ---------------------------------------------------------
        # TAB 4: IN TEM
        # ---------------------------------------------------------
        elif selected_tab == "🖨️ In Tem":
            st.subheader("🖨️ In Tem Mã Vạch (ZPL)")
            bc = st.text_input("Barcode:", value="MES-PROD-2026")
            if st.button("Tạo mã ZPL"):
                code = f"^XA\n^FO20,20^A0N,25,25^FD{bc}^FS\n^FO20,60^BCN,60,Y,N,N^FD{bc}^FS\n^XZ"
                st.code(code)

        # ---------------------------------------------------------
        # CÁC TAB QUẢN TRỊ
        # ---------------------------------------------------------
        elif selected_tab == "📂 Cập nhật File":
            upf = st.file_uploader("📂 Tải lên file dữ liệu (.csv/.xlsx)", type=["xlsx", "csv"])
            if upf:
                if upf.name.endswith('.csv'): df = pd.read_csv(upf)
                else: df = pd.read_excel(upf)
                df.to_csv("data_server.csv", index=False)
                st.success("✅ Cập nhật thành công!")

        elif selected_tab == "👥 Quản lý Users":
            st.subheader("👥 Danh sách tài khoản")
            u_list = [{"Username": k, "Tên": v.get('name'), "Vị trí": v.get('position')} for k, v in credentials['usernames'].items()]
            st.table(pd.DataFrame(u_list))

        elif selected_tab == "🏭 Quản lý LINE":
            st.subheader("🏭 Quản lý LINE sản xuất")
            with st.form("new_line"):
                nl = st.text_input("Tên Line mới:")
                if st.form_submit_button("Thêm"):
                    if nl:
                        credentials['lines'][nl] = {'status': 'Đã phê duyệt', 'machines': {}}
                        save_users(credentials)
                        st.success("✅ Đã thêm line!")
                        time.sleep(1)
                        st.rerun()
