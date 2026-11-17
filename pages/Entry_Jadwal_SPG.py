from datetime import date
import os

import pandas as pd
import streamlit as st


SCHEDULE_FILE = "Jadwal SPG.xlsx"
ADMIN_PASSWORD = "admin123"

st.set_page_config(page_title="Entry Jadwal SPG", page_icon="📅", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #f7f8fc; }
    [data-testid="stForm"] {
        background: #fff; padding: 1.1rem 1.25rem; border: 1px solid #e5e7eb;
        border-radius: 14px; box-shadow: 0 4px 14px rgba(15, 23, 42, .05);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_schedule():
    if not os.path.exists(SCHEDULE_FILE):
        return pd.DataFrame(columns=["Kota", "Kecamatan"])
    try:
        frame = pd.read_excel(SCHEDULE_FILE)
        frame.columns = [str(column).strip() for column in frame.columns]
        return frame
    except Exception as exc:
        st.error(f"Gagal membaca {SCHEDULE_FILE}: {exc}")
        return pd.DataFrame(columns=["Kota", "Kecamatan"])


def save_schedule(frame):
    try:
        frame.to_excel(SCHEDULE_FILE, index=False)
        return True
    except Exception as exc:
        st.error(f"Gagal menyimpan {SCHEDULE_FILE}: {exc}")
        return False


def week_label(value):
    return f"Minggu ke-{pd.Timestamp(value).isocalendar().week}"


def is_active(value):
    return str(value).strip().lower() not in {"", "-", "nan", "none"}


st.title("📅 Entry Jadwal SPG Aktif")
st.caption("Ubah jadwal melalui kolom entry yang jelas—tanpa mengedit tabel. Perubahan disimpan ke Jadwal SPG.xlsx.")

if not st.session_state.get("schedule_admin_authenticated", False):
    with st.form("schedule_admin_login"):
        st.subheader("🔐 Akses Admin")
        password = st.text_input("Password Admin", type="password")
        login = st.form_submit_button("Masuk", type="primary")
    if login:
        if password == ADMIN_PASSWORD:
            st.session_state["schedule_admin_authenticated"] = True
            st.rerun()
        st.error("Password salah.")
    st.stop()

schedule = load_schedule()
if schedule.empty:
    st.info("Belum ada jadwal. Silakan tambahkan jadwal melalui form entry di aplikasi.")
    st.stop()

city_col = next((col for col in schedule.columns if col.strip().lower() == "kota"), "Kota")
district_col = next((col for col in schedule.columns if col.strip().lower() == "kecamatan"), "Kecamatan")
if city_col not in schedule.columns:
    schedule[city_col] = ""
if district_col not in schedule.columns:
    schedule[district_col] = ""
date_cols = [col for col in schedule.columns if col not in {city_col, district_col}]

entries = []
for row_index, row in schedule.iterrows():
    for date_col in date_cols:
        parsed_date = pd.to_datetime(date_col, errors="coerce")
        if pd.isna(parsed_date) or not is_active(row.get(date_col, "")):
            continue
        entries.append({
            "row": row_index,
            "date_col": date_col,
            "date": parsed_date.date(),
            "week": week_label(parsed_date),
            "city": str(row.get(city_col, "") or "").strip(),
            "district": str(row.get(district_col, "") or "").strip(),
            "team": str(row.get(date_col, "")).strip(),
        })

if not entries:
    st.info("Tidak ada jadwal aktif untuk diedit.")
    st.stop()

# Label minggu berbentuk "Minggu ke-47"; ambil bagian setelah tanda hubung agar bisa diurutkan sebagai angka.
weeks = sorted(
    {entry["week"] for entry in entries},
    key=lambda label: int(label.rsplit("-", 1)[-1]),
    reverse=True,
)
selected_weeks = st.multiselect("Filter periode minggu", weeks, default=weeks, key="schedule_entry_weeks")
visible_entries = [entry for entry in entries if entry["week"] in selected_weeks]
st.markdown(f"**{len(visible_entries)} jadwal aktif**")

for entry in visible_entries:
    title = f"{entry['date'].strftime('%d-%m-%Y')} · {entry['district'] or 'Kecamatan belum diisi'} · {entry['team']}"
    with st.expander(f"📍 {title}", expanded=False):
        with st.form(f"edit_schedule_{entry['row']}_{entry['date_col']}"):
            st.caption(f"{entry['week']} · Edit detail jadwal lalu simpan perubahan.")
            date_field, city_field = st.columns(2)
            with date_field:
                edited_date = st.date_input("Tanggal jadwal", value=entry["date"], key=f"date_{entry['row']}_{entry['date_col']}")
            with city_field:
                edited_city = st.selectbox(
                    "Kota / Kabupaten",
                    ["Surabaya", "Gresik"],
                    index=0 if entry["city"].lower() != "gresik" else 1,
                    key=f"city_{entry['row']}_{entry['date_col']}",
                )
            district_field, team_field = st.columns(2)
            with district_field:
                edited_district = st.text_input("Kecamatan", value=entry["district"], key=f"district_{entry['row']}_{entry['date_col']}")
            with team_field:
                edited_team = st.text_input("Nama Team", value=entry["team"], key=f"team_{entry['row']}_{entry['date_col']}")
            save_entry = st.form_submit_button("💾 Simpan Jadwal Ini", type="primary")

        if save_entry:
            if not edited_district.strip() or not edited_team.strip():
                st.warning("Kecamatan dan nama team wajib diisi.")
                continue
            target_col = edited_date.strftime("%Y-%m-%d 00:00:00")
            if target_col not in schedule.columns:
                schedule[target_col] = "-"
            if target_col != entry["date_col"]:
                schedule.at[entry["row"], entry["date_col"]] = "-"
            schedule.at[entry["row"], target_col] = edited_team.strip()
            schedule.at[entry["row"], city_col] = edited_city
            schedule.at[entry["row"], district_col] = edited_district.strip()
            if save_schedule(schedule):
                st.success("Jadwal berhasil disimpan.")
                st.rerun()

if st.button("🔄 Muat Ulang Jadwal"):
    st.rerun()
