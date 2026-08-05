import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI
import os
import json
import time
import io
from pathlib import Path

# -------------------------------------------------------------------
# 0. THIẾT LẬP BẢO MẬT HỆ THỐNG
# -------------------------------------------------------------------
ALLOWED_DATA_DIR = Path("./Data_Server").resolve()
ALLOWED_DATA_DIR.mkdir(parents=True, exist_ok=True)

try:
    COOKIE_KEY = st.secrets["COOKIE_KEY"]
except (KeyError, FileNotFoundError):
    COOKIE_KEY = "fallback_unsafe_key_change_me_in_production"

ENV_API_KEY = st.secrets.get("OPENAI_API_KEY", "")

# -------------------------------------------------------------------
# 1. HỆ THỐNG QUẢN LÝ DỮ LIỆU TÀI KHOẢN VÀ LINE (JSON)
# -------------------------------------------------------------------
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
# 2. XỬ LÝ GIAO DIỆN ĐĂNG NHẬP
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
    st.warning('🔐 Vui lòng nhập thông tin để truy cập hệ thống MES.')
elif authentication_status:
    # -------------------------------------------------------------------
    # 3. GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
    # -------------------------------------------------------------------
    authenticator.logout('Đăng xuất', 'sidebar')
    
    current_user_info = credentials['usernames'].get(username, {})
    current_position = current_user_info.get('position', 'Nhân viên')
    current_department = current_user_info.get('department', 'Chưa rõ')
    current_line = current_user_info.get('line', 'Chưa rõ')
    
    st.title(f"🏭 Hệ Thống MES & Trợ Lý AI")
    st.caption(f"👤 Tên: **{name}** | Vị trí: **{current_position}** | Phòng ban: **{current_department}** | Phụ trách: **{current_line}**")
    st.markdown("---")

    openai_api_key = ENV_API_KEY
    if not openai_api_key:
        with st.sidebar:
            st.warning("⚠️ Cấu hình API Key trên Streamlit Secrets để ẩn khung nhập này.")
            openai_api_key = st.text_input("🔑 Nhập OpenAI API Key:", type="password")

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
    if can_view: menu_options.extend(["📈 Dashboard", "🔍 Tra cứu & Báo cáo", "🖨️ In Tem", "📊 DATA Máy Móc"])
    if can_edit_data: menu_options.append("📂 Cập nhật File")
    if can_edit_account: menu_options.append("👥 Quản lý Users")
    if can_edit_line: menu_options.append("🏭 Quản lý LINE")
        
    if menu_options:
        if "admin_menu" not in st.session_state or st.session_state.admin_menu not in menu_options:
            st.session_state.admin_menu = menu_options[0]

        selected_tab = st.radio("Điều hướng Hệ thống:", menu_options, horizontal=True, key="admin_menu", label_visibility="collapsed")
        st.markdown("---")
        
        # ---------------------------------------------------------
        # TAB 1: DASHBOARD
        # ---------------------------------------------------------
        if selected_tab == "📈 Dashboard":
            st.subheader("📈 Dashboard Sản Xuất Tổng Quan")
            if df is None or df.empty:
                st.info("💡 Chưa có dữ liệu hoặc file dữ liệu trống. Vui lòng vào tab '📂 Cập nhật File' để tải lên file mới.")
            else:
                total_records = len(df)
                status_col = next((col for col in df.columns if any(kw in str(col).lower() for kw in ["status", "kết quả", "đánh giá", "trạng thái", "result"])), None)
                ng_count = len(df[df[status_col].astype(str).str.upper().isin(["NG", "FAIL", "LỖI", "REJECT"])]) if status_col else 0
                ok_count = total_records - ng_count
                ng_rate = round((ng_count / total_records) * 100, 2) if total_records > 0 else 0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("📦 Tổng Sản Lượng", f"{total_records:,} SP")
                c2.metric("✅ Hàng OK", f"{ok_count:,} SP")
                c3.metric("❌ Hàng NG", f"{ng_count:,} SP")
                c4.metric("📉 Tỉ Lệ Lỗi", f"{ng_rate}%")
                st.markdown("---")
                
                ch1, ch2 = st.columns([1, 2])
                with ch1:
                    st.markdown("##### 📊 Tỉ lệ Chất lượng")
                    st.bar_chart(pd.DataFrame({"Trạng thái": ["OK", "NG"], "Số lượng": [ok_count, ng_count]}).set_index("Trạng thái"))
                with ch2:
                    st.markdown("##### 📈 Biểu đồ Xu hướng (100 SP cuối)")
                    num_df = df.select_dtypes(include='number')
                    if not num_df.empty: st.line_chart(num_df.tail(100))
                    else: st.info("Không có dữ liệu dạng số.")
                
                st.markdown("##### 📋 Dữ liệu Gần Nhất (Top 100)")
                st.dataframe(df.tail(100).iloc[::-1], use_container_width=True, height=300)

        # ---------------------------------------------------------
        # TAB 2: TRA CỨU, BÁO CÁO & AI
        # ---------------------------------------------------------
        elif selected_tab == "🔍 Tra cứu & Báo cáo":
            st.subheader("🔍 Tra cứu & Phân tích AI")
            if df is None: df = pd.DataFrame(columns=["Chưa có dữ liệu"])

            with st.expander("🎯 Bộ Lọc Dữ Liệu", expanded=True):
                cs1, cs2, cs3, cs4 = st.columns(4)
                with cs1: s_bc = st.text_input("🏷️ Barcode:")
                with cs2: s_lot = st.text_input("📦 Lot Number:")
                with cs3: s_mod = st.text_input("💻 Model:")
                with cs4: search_kw = st.text_input("🔎 Tự do:")

                df_filtered = df.copy()
                def filt(d, kw):
                    return d[d.astype(str).apply(lambda r: r.str.contains(kw.strip(), case=False, na=False)).any(axis=1)] if kw.strip() else d

                df_filtered = filt(df_filtered, s_bc)
                df_filtered = filt(df_filtered, s_lot)
                df_filtered = filt(df_filtered, s_mod)
                df_filtered = filt(df_filtered, search_kw)

            tb_data, tb_ai, tb_rep = st.tabs(["🗄️ Bảng Dữ Liệu", "🤖 AI Phân Tích", "📥 Báo Cáo (Xuất File)"])
            with tb_data:
                st.caption(f"📌 Hiển thị: {len(df_filtered)} / {len(df)} dòng")
                st.dataframe(df_filtered, use_container_width=True, height=400)
            
            with tb_ai:
                query = st.text_input("💬 Nhập câu hỏi cho AI (VD: Tính tổng lỗi, nguyên nhân lỗi cao nhất?):")
                if query:
                    if not openai_api_key: st.error("⚠️ Hệ thống chưa được cấu hình OpenAI API Key!")
                    elif len(df_filtered) == 0: st.warning("⚠️ Bảng dữ liệu trống.")
                    else:
                        with st.spinner("Đang tính toán..."):
                            try:
                                llm = ChatOpenAI(temperature=0, model="gpt-4o-mini", api_key=openai_api_key)
                                agent = create_pandas_dataframe_agent(llm, df_filtered, verbose=True, allow_dangerous_code=False)
                                response = agent.invoke({"input": query})
                                st.success("✅ Kết quả:")
                                st.write(response["output"])
                            except Exception:
                                st.error("❌ Lỗi AI. Vui lòng thử lại câu lệnh khác.")
            with tb_rep:
                if not df_filtered.empty:
                    out = io.BytesIO()
                    with pd.ExcelWriter(out, engine='xlsxwriter') as w: df_filtered.to_excel(w, index=False, sheet_name='MES')
                    st.download_button("📥 Tải File Excel (.xlsx)", data=out.getvalue(), file_name="Bao_Cao.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

        # ---------------------------------------------------------
        # TAB 3: IN TEM NHÃN
        # ---------------------------------------------------------
        elif selected_tab == "🖨️ In Tem":
            st.subheader("🖨️ In Tem Zebra (ZPL)")
            with st.form("print_form"):
                c1, c2 = st.columns(2)
                with c1:
                    pm = st.text_input("Model:", value="MDL-10293")
                    pl = st.text_input("Lot:", value="LOT-2026")
                with c2:
                    ps = st.text_input("Serial:", value="SN001")
                    pb = st.text_input("Barcode:", value="MDL-10293-LOT-2026-SN001")
                pq = st.number_input("Số lượng:", min_value=1, value=1)
                if st.form_submit_button("Tạo File .ZPL"):
                    code = f"^XA\n^PW400\n^LL240\n^FO20,20^A0N,25,25^FDModel: {pm}^FS\n^FO20,55^A0N,25,25^FDLot: {pl}^FS\n^FO20,90^A0N,25,25^FDSerial: {ps}^FS\n^FO20,130^BCN,60,Y,N,N^FD{pb}^FS\n^PQ{pq}\n^XZ"
                    st.code(code, language="text")
                    st.download_button("📥 Tải Tem In", data=code, file_name=f"tem_{ps}.zpl")

        # ---------------------------------------------------------
        # TAB 4: DATA TỪ MÁY CHỦ
        # ---------------------------------------------------------
        elif selected_tab == "📊 DATA Máy Móc":
            st.subheader("📊 Trích Xuất Dữ Liệu Máy")
            lines_data = {k: v for k, v in credentials.get('lines', {}).items() if v.get('status') == 'Đã phê duyệt'}
            if not lines_data: st.warning("Chưa có LINE được duyệt.")
            else:
                if st.button("🔄 Quét hệ thống"): st.rerun()
                for lname, linfo in lines_data.items():
                    active = {k: v for k, v in linfo.get('machines', {}).items() if v.get('active')}
                    if active:
                        st.markdown(f"### 🏭 {lname}")
                        for m_num, m_info in active.items():
                            with st.expander(f"🖥️ {m_info.get('name')} | {m_info.get('format')} | 📍 {m_info.get('path')}"):
                                try:
                                    req_path = Path(m_info.get('path', '')).resolve()
                                    if ALLOWED_DATA_DIR not in req_path.parents and req_path != ALLOWED_DATA_DIR:
                                        st.error(f"⛔ BẢO MẬT: Đường dẫn phải nằm trong {ALLOWED_DATA_DIR}!")
                                        continue
                                    if not req_path.exists():
                                        st.error("❌ Không tìm thấy file gốc.")
                                        continue
                                    
                                    fmt = m_info.get('format')
                                    if fmt == "CSV": m_df = pd.read_csv(req_path)
                                    elif fmt == "Excel": m_df = pd.read_excel(req_path)
                                    elif fmt == "XLSB": m_df = pd.read_excel(req_path, engine='pyxlsb')
                                    else: st.warning("Định dạng chưa hỗ trợ."); continue
                                    
                                    st.success(f"Tải thành công {len(m_df)} dòng.")
                                    st.dataframe(m_df.head(100), use_container_width=True)
                                except Exception:
                                    st.error("❌ Lỗi định dạng dữ liệu.")

        # ---------------------------------------------------------
        # CÁC TAB QUẢN TRỊ
        # ---------------------------------------------------------
        elif selected_tab == "📂 Cập nhật File":
            upf = st.file_uploader("📂 Chọn file (Excel/CSV/XLSB)", type=["xlsx", "xls", "xlsb", "csv"])
            if upf:
                if upf.name.endswith('.csv'): df = pd.read_csv(upf)
                elif upf.name.endswith('.xlsb'): df = pd.read_excel(upf, engine='pyxlsb')
                else: df = pd.read_excel(upf)
                df.to_csv("data_server.csv", index=False)
                st.success("✅ Đã ghi đè dữ liệu thành công! Hãy bấm làm mới hoặc chuyển tab.")

        elif selected_tab == "👥 Quản lý Users":
            st.subheader("📋 Phân quyền")
            u_list = [{"Tài khoản": k, "Tên": v.get('name'), "Chức vụ": v.get('position')} for k, v in credentials['usernames'].items()]
            st.table(pd.DataFrame(u_list))

            with st.expander("➕ Tạo Tài Khoản"):
                with st.form("new_u"):
                    c1, c2 = st.columns(2)
                    with c1: nu = st.text_input("Username*"); nn = st.text_input("Tên*")
                    with c2: np = st.text_input("Mật khẩu*", type="password"); nl = st.selectbox("Line:", line_options)
                    p_admin = st.checkbox("Quyền Quản Trị Viên", value=False)
                    if st.form_submit_button("Tạo"):
                        if nu and np and nn:
                            if nu in credentials['usernames']: st.error("Đã tồn tại!")
                            else:
                                h = {'u': {nu: {'password': np}}}; stauth.Hasher.hash_passwords(h)
                                credentials['usernames'][nu] = {'name': nn, 'password': h['u'][nu]['password'], 'line': nl, 'role': 'admin' if p_admin else 'user', 'permissions': {'view': True, 'edit_data': p_admin, 'edit_line': p_admin, 'edit_account': p_admin}}
                                save_users(credentials); st.success("✅ Xong!"); time.sleep(1); st.rerun()

        elif selected_tab == "🏭 Quản lý LINE":
            st.subheader("🏭 Thiết Lập Thiết Bị")
            with st.form("new_l", clear_on_submit=True):
                n_ln = st.text_input("Tên LINE mới*:")
                if st.form_submit_button("Tạo"):
                    if n_ln: credentials['lines'][n_ln] = {'status': 'Đã phê duyệt', 'machines': {}}; save_users(credentials); st.success("✅ Đã tạo!"); time.sleep(1); st.rerun()
            
            for ln, li in credentials.get('lines', {}).items():
                with st.expander(f"🏭 {ln}"):
                    df_m = pd.DataFrame([{"Mã": m, "Tên": i.get('name'), "Đường dẫn": i.get('path')} for m, i in li.get('machines', {}).items()])
                    if not df_m.empty: st.dataframe(df_m, hide_index=True)
                    with st.form(f"add_{ln}"):
                        c1, c2 = st.columns(2)
                        with c1: mn = st.text_input("Mã Máy*"); mt = st.text_input("Tên*")
                        with c2: mf = st.selectbox("Định dạng:", ["CSV", "Excel", "XLSB"]); mp = st.text_input("Path:", value=f"{ALLOWED_DATA_DIR}/...")
                        if st.form_submit_button("Lưu"):
                            if mn and mt:
                                if 'machines' not in credentials['lines'][ln]: credentials['lines'][ln]['machines'] = {}
                                credentials['lines'][ln]['machines'][mn] = {'name': mt, 'format': mf, 'path': mp, 'active': True}
                                save_users(credentials); st.success("✅ Đã lưu!"); time.sleep(1); st.rerun()
