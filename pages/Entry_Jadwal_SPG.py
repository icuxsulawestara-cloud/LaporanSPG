from datetime import date, timedelta
import json
import os

import pandas as pd
import streamlit as st


SCHEDULE_FILE = "Jadwal SPG.xlsx"
TEAM_NAMES_FILE = "master_nama_team.json"
ADMIN_PASSWORD = "admin123"
CITIES = ["Surabaya", "Gresik"]
WEEKDAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

st.set_page_config(page_title="Jadwal SPG", page_icon="📅", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #f5f7fb; }
    [data-testid="stForm"] {
        background: #ffffff; padding: 1.15rem 1.3rem; border: 1px solid #e6eaf0;
        border-radius: 16px; box-shadow: 0 5px 18px rgba(15, 23, 42, .045);
    }
    [data-testid="stExpander"] {
        background: #ffffff; border: 1px solid #e6eaf0; border-radius: 14px;
        margin-bottom: .55rem;
    }
    .schedule-hero {
        padding: 1.25rem 1.5rem; border-radius: 18px; color: white;
        background: linear-gradient(120deg, #991b1b, #dc2626 65%, #f97316);
        margin-bottom: 1rem;
    }
    .schedule-hero h1 { color: white; margin: 0; }
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


def team_choices():
    defaults = [f"Team SPG {number}" for number in range(1, 21)]
    if os.path.exists(TEAM_NAMES_FILE):
        try:
            with open(TEAM_NAMES_FILE, "r", encoding="utf-8") as file:
                mapping = json.load(file)
            return [str(mapping.get(team, team)) for team in defaults]
        except (OSError, ValueError, TypeError):
            pass
    return defaults


def get_geo_districts(city):
    filename = "Gresik.geojson" if city == "Gresik" else "Surabaya Barat.geojson"
    try:
        with open(filename, "r", encoding="utf-8") as file:
            geojson = json.load(file)
        frame = pd.DataFrame(feature.get("properties", {}) for feature in geojson.get("features", []))
        column = next(
            (name for name in ["nm_kecamatan", "KECAMATAN", "kecamatan", "Name", "NAME"] if name in frame.columns),
            None,
        )
        if column:
            return sorted(frame[column].dropna().astype(str).str.strip().unique().tolist())
    except (OSError, ValueError, TypeError):
        pass
    return ["Tegalsari", "Wonokromo", "Rungkut", "Asemrowo", "Benowo"]


def is_active(value):
    if pd.isna(value):
        return False
    return str(value).strip().lower() not in {"", "-", "nan", "none"}


def date_column(value):
    return pd.Timestamp(value).strftime("%Y-%m-%d 00:00:00")


def week_info(value):
    iso = pd.Timestamp(value).isocalendar()
    return f"Minggu ke-{iso.week} · {iso.year}", (iso.year, iso.week)


def find_meta_columns(frame):
    city = next((col for col in frame.columns if "kota" in str(col).strip().lower()), "Kota")
    district = next((col for col in frame.columns if "kecamatan" in str(col).strip().lower()), "Kecamatan")
    if city not in frame.columns:
        frame[city] = ""
    if district not in frame.columns:
        frame[district] = ""
    return city, district


def add_assignments(frame, city_col, district_col, dates, city, districts, team):
    date_cols = [col for col in frame.columns if col not in {city_col, district_col}]
    proposed = []
    conflicts = []

    for district in districts:
        matching = frame[
            frame[city_col].astype(str).str.strip().str.casefold().eq(city.strip().casefold())
            & frame[district_col].astype(str).str.strip().str.casefold().eq(district.strip().casefold())
        ]
        row_index = matching.index[0] if not matching.empty else None
        for workday in dates:
            column = date_column(workday)
            if row_index is not None and column in date_cols and is_active(frame.at[row_index, column]):
                conflicts.append(f"{district} — {workday.strftime('%d-%m-%Y')}")
            else:
                proposed.append((district, workday, row_index))

    if conflicts:
        return frame, conflicts

    for district, workday, row_index in proposed:
        column = date_column(workday)
        if column not in frame.columns:
            frame[column] = "-"
        matching = frame[
            frame[city_col].astype(str).str.strip().str.casefold().eq(city.strip().casefold())
            & frame[district_col].astype(str).str.strip().str.casefold().eq(district.strip().casefold())
        ]
        if row_index is None:
            row_index = matching.index[0] if not matching.empty else None
        if row_index is None:
            new_row = {col: "-" for col in frame.columns}
            new_row[city_col] = city
            new_row[district_col] = district
            new_row[column] = team
            frame = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
        else:
            frame.at[row_index, city_col] = city
            frame.at[row_index, district_col] = district
            frame.at[row_index, column] = team
    return frame, []


st.markdown(
    '<div class="schedule-hero"><h1>📅 Jadwal SPG</h1>'
    '<div style="opacity:.92; margin-top:.35rem">Kelola jadwal harian dan mingguan dalam form yang ringkas dan mudah dibaca.</div></div>',
    unsafe_allow_html=True,
)

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
city_col, district_col = find_meta_columns(schedule)
team_options = team_choices()

# Tab entry memungkinkan pembuatan hari kerja individual atau satu minggu kerja sekaligus.
tab_day, tab_week, tab_manage = st.tabs(["➕ Tambah Hari Kerja", "🗓️ Tambah Minggu Kerja", "✏️ Kelola Jadwal Aktif"])

with tab_day:
    st.markdown("#### Buat jadwal untuk satu hari")
    st.caption("Pilih satu tanggal, satu atau beberapa kecamatan, lalu tentukan team yang bertugas.")
    with st.form("form_add_schedule_day"):
        col_date, col_city, col_team = st.columns(3)
        with col_date:
            work_date = st.date_input("Tanggal kerja", value=date.today(), key="new_workday_date")
        with col_city:
            city = st.selectbox("Kota / Kabupaten", CITIES, key="new_workday_city")
        with col_team:
            team = st.selectbox("Team SPG", team_options, key="new_workday_team")
        districts = st.multiselect(
            "Kecamatan yang dijadwalkan",
            get_geo_districts(city),
            key="new_workday_districts",
            help="Pilih satu atau beberapa kecamatan untuk team ini.",
        )
        submit_day = st.form_submit_button("💾 Simpan Jadwal Hari Ini", type="primary")
    if submit_day:
        if not districts:
            st.warning("Pilih minimal satu kecamatan terlebih dahulu.")
        else:
            updated, conflicts = add_assignments(schedule.copy(), city_col, district_col, [work_date], city, districts, team)
            if conflicts:
                st.error("Sudah ada jadwal pada lokasi dan tanggal berikut: " + ", ".join(conflicts))
            elif save_schedule(updated):
                st.success(f"Jadwal {team} berhasil disimpan untuk {len(districts)} kecamatan.")
                st.rerun()

with tab_week:
    st.markdown("#### Buat jadwal untuk satu minggu")
    st.caption("Pilih tanggal apa saja dalam minggu tujuan, hari kerja, kecamatan, dan team. Sistem akan membuat jadwal untuk kombinasi yang dipilih.")
    with st.form("form_add_schedule_week"):
        col_anchor, col_city, col_team = st.columns(3)
        with col_anchor:
            week_anchor = st.date_input("Tanggal dalam minggu tujuan", value=date.today(), key="new_week_anchor")
        week_start = week_anchor - timedelta(days=week_anchor.weekday())
        week_end = week_start + timedelta(days=6)
        with col_city:
            week_city = st.selectbox("Kota / Kabupaten", CITIES, key="new_week_city")
        with col_team:
            week_team = st.selectbox("Team SPG", team_options, key="new_week_team")
        st.info(f"Periode minggu: {week_start.strftime('%d %b %Y')} – {week_end.strftime('%d %b %Y')}")
        workdays = st.multiselect(
            "Pilih hari kerja",
            WEEKDAYS,
            default=WEEKDAYS[:5],
            key="new_week_days",
            help="Default Senin–Jumat. Sabtu dan Minggu dapat ditambahkan bila diperlukan.",
        )
        week_districts = st.multiselect(
            "Kecamatan yang dijadwalkan",
            get_geo_districts(week_city),
            key="new_week_districts",
        )
        submit_week = st.form_submit_button("🗓️ Buat Jadwal Mingguan", type="primary")
    if submit_week:
        if not workdays or not week_districts:
            st.warning("Pilih minimal satu hari kerja dan satu kecamatan.")
        else:
            day_index = {label: index for index, label in enumerate(WEEKDAYS)}
            selected_dates = [week_start + timedelta(days=day_index[label]) for label in workdays]
            updated, conflicts = add_assignments(
                schedule.copy(), city_col, district_col, selected_dates, week_city, week_districts, week_team
            )
            if conflicts:
                st.error("Ada jadwal yang sudah terisi. Tidak ada perubahan yang disimpan: " + ", ".join(conflicts))
            elif save_schedule(updated):
                total = len(selected_dates) * len(week_districts)
                st.success(f"Berhasil membuat {total} penugasan untuk {week_team}.")
                st.rerun()

with tab_manage:
    st.markdown("#### Jadwal aktif")
    st.caption("Buka salah satu jadwal untuk mengubah tanggal/team atau mengosongkan penugasan.")
    date_cols = [col for col in schedule.columns if col not in {city_col, district_col}]
    entries = []
    for row_index, row in schedule.iterrows():
        for date_col in date_cols:
            parsed_date = pd.to_datetime(date_col, errors="coerce")
            if pd.isna(parsed_date) or not is_active(row.get(date_col, "")):
                continue
            label, sort_key = week_info(parsed_date)
            entries.append({
                "row": row_index,
                "date_col": date_col,
                "date": parsed_date.date(),
                "week": label,
                "week_sort": sort_key,
                "city": str(row.get(city_col, "") if pd.notna(row.get(city_col, "")) else "").strip(),
                "district": str(row.get(district_col, "") if pd.notna(row.get(district_col, "")) else "").strip(),
                "team": str(row.get(date_col, "")).strip(),
            })

    if not entries:
        st.info("Belum ada jadwal aktif. Gunakan tab **Tambah Hari Kerja** atau **Tambah Minggu Kerja** untuk mulai membuat jadwal.")
    else:
        weeks_by_sort = {}
        for entry in entries:
            weeks_by_sort[entry["week_sort"]] = entry["week"]
        ordered_week_keys = sorted(weeks_by_sort, reverse=True)
        week_labels = [weeks_by_sort[key] for key in ordered_week_keys]
        latest_week = week_labels[0]
        selected_weeks = st.multiselect(
            "Filter periode",
            week_labels,
            default=[latest_week],
            key="schedule_entry_weeks",
        )
        visible_entries = sorted(
            [entry for entry in entries if entry["week"] in selected_weeks],
            key=lambda entry: (entry["date"], entry["city"], entry["district"], entry["team"]),
        )
        st.markdown(f"**{len(visible_entries)} jadwal aktif**")

        for entry in visible_entries:
            title = (
                f"{entry['date'].strftime('%d-%m-%Y')}  ·  {entry['district'] or 'Kecamatan belum diisi'}"
                f"  ·  {entry['team']}"
            )
            entry_id = f"{entry['row']}_{entry['date_col']}"
            with st.expander(f"📍 {title}", expanded=False):
                st.caption(f"{entry['week']}  ·  {entry['city'] or 'Kota belum diisi'}")
                with st.form(f"edit_schedule_{entry_id}"):
                    date_input_col, team_input_col = st.columns(2)
                    with date_input_col:
                        edited_date = st.date_input(
                            "Tanggal kerja", value=entry["date"], key=f"date_{entry_id}"
                        )
                    with team_input_col:
                        default_team_index = team_options.index(entry["team"]) if entry["team"] in team_options else 0
                        team_choice = st.selectbox(
                            "Team SPG",
                            team_options,
                            index=default_team_index,
                            key=f"team_{entry_id}",
                        )
                    save_entry, clear_entry = st.columns(2)
                    with save_entry:
                        save_clicked = st.form_submit_button("💾 Simpan Perubahan", type="primary", use_container_width=True)
                    with clear_entry:
                        clear_clicked = st.form_submit_button("🗑️ Hapus Jadwal Ini", use_container_width=True)

                if save_clicked:
                    target_col = date_column(edited_date)
                    current_value = schedule.at[entry["row"], target_col] if target_col in schedule.columns else "-"
                    if target_col != entry["date_col"] and is_active(current_value):
                        st.error("Tanggal tujuan sudah memiliki jadwal untuk kecamatan ini. Pilih tanggal lain.")
                    else:
                        if target_col not in schedule.columns:
                            schedule[target_col] = "-"
                        if target_col != entry["date_col"]:
                            schedule.at[entry["row"], entry["date_col"]] = "-"
                        schedule.at[entry["row"], target_col] = team_choice
                        if save_schedule(schedule):
                            st.success("Perubahan jadwal berhasil disimpan.")
                            st.rerun()

                if clear_clicked:
                    schedule.at[entry["row"], entry["date_col"]] = "-"
                    if save_schedule(schedule):
                        st.success("Jadwal berhasil dihapus.")
                        st.rerun()

if st.button("🔄 Muat Ulang Jadwal", key="reload_schedule"):
    st.rerun()
