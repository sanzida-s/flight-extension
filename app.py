import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import calendar
import io

st.set_page_config(
    page_title="Flight Extension Tool",
    page_icon="🚀",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Syne:wght@600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
code, pre, .stCode { font-family: 'IBM Plex Mono', monospace !important; }

.metric-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.metric-box {
    background: #131720; border: 1px solid #252d42; border-radius: 10px;
    padding: 10px 16px; min-width: 120px;
}
.metric-box .lbl { font-size: 10px; color: #55637a; text-transform: uppercase; letter-spacing: 0.5px; font-family: 'IBM Plex Mono', monospace; }
.metric-box .val { font-size: 20px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; margin-top: 2px; }
.grn { color: #2effa0; } .ylw { color: #ffc94d; } .blu { color: #5db8ff; } .red { color: #ff5272; }

.badge {
    display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace; font-weight: 600; text-transform: uppercase;
}
.b-match { background: rgba(46,255,160,.1); color: #2effa0; border: 1px solid rgba(46,255,160,.25); }
.b-diff  { background: rgba(255,201,77,.1); color: #ffc94d; border: 1px solid rgba(255,201,77,.25); }
.b-warn  { background: rgba(255,82,114,.1);  color: #ff5272; border: 1px solid rgba(255,82,114,.25); }

.section-header {
    font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
    color: #55637a; margin-bottom: 8px; margin-top: 4px;
}
.info-box {
    background: rgba(93,184,255,.07); border: 1px solid rgba(93,184,255,.2);
    border-radius: 8px; padding: 10px 14px; font-size: 12px;
    font-family: 'IBM Plex Mono', monospace; color: #5db8ff; margin-bottom: 10px;
}
.warn-box {
    background: rgba(255,201,77,.07); border: 1px solid rgba(255,201,77,.2);
    border-radius: 8px; padding: 10px 14px; font-size: 12px;
    font-family: 'IBM Plex Mono', monospace; color: #ffc94d; margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "li_data": {},          # { io_name -> [{li_id, li_name, prev_budget}] }
        "loaded_files": [],
        "june_budgets": {},     # { io_name -> total_june_budget }
        "june_ref_file": None,
        "jun_inputs": {},       # { li_id -> float }
        "io_split": {},         # { io_name -> {enabled, cut_day, pct1} }
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_date_val(v):
    """Try to extract YYYY-MM-DD from various cell formats."""
    if pd.isna(v) or v is None:
        return None
    if isinstance(v, (date,)):
        return v.strftime("%Y-%m-%d")
    if hasattr(v, 'date'):  # datetime
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    # try YYYY-MM-DD prefix
    if len(s) >= 10 and s[4] == '-':
        return s[:10]
    return None

def parse_li_sheet(df, filter_end_date: str):
    """
    From LI-Setting dataframe, return list of dicts.
    Picks the most recent Active Flight End Date <= filter_end_date per LI.
    """
    required = ["IO Name", "LI ID", "LI Name", "Active Flight End Date", "Active Flight Budget"]
    for col in required:
        if col not in df.columns:
            return [], f"Missing column: '{col}'"

    records = []
    for _, row in df.iterrows():
        ed = parse_date_val(row["Active Flight End Date"])
        if not ed or ed > filter_end_date:
            continue
        records.append({
            "io":         str(row["IO Name"]).strip(),
            "li_id":      row["LI ID"],
            "li_name":    str(row["LI Name"]).strip(),
            "end_date":   ed,
            "prev_budget": float(row["Active Flight Budget"]) if not pd.isna(row["Active Flight Budget"]) else 0.0,
        })

    if not records:
        return [], f"No rows with Active Flight End Date ≤ {filter_end_date}"

    # Keep most recent end_date per (io, li_id)
    best = {}
    for r in records:
        key = (r["io"], r["li_id"])
        if key not in best or r["end_date"] > best[key]["end_date"]:
            best[key] = r

    result = list(best.values())
    result.sort(key=lambda x: (x["io"], x["li_name"]))
    return result, None

def parse_june_budget_sheet(df):
    """Parse IO Name + budget column. Flexible column name matching."""
    io_col  = next((c for c in df.columns if "io name" in c.lower()), None)
    bud_col = next((c for c in df.columns if "budget" in c.lower()), None)
    if not io_col or not bud_col:
        return {}, f"Could not find 'IO Name' and 'Budget' columns. Found: {list(df.columns)}"
    out = {}
    for _, row in df.iterrows():
        io = str(row[io_col]).strip()
        try:
            bud = float(row[bud_col])
            if io and not np.isnan(bud):
                out[io] = bud
        except (ValueError, TypeError):
            pass
    return out, None

def days_in_month(y, m):
    return calendar.monthrange(y, m)[1]

def build_flights(li_id, li_name, budget, month_start: date, month_end: date, split_cfg, min_budget):
    """
    Returns list of dicts: {li_id, li_name, start, end, budget, daily_budget}
    split_cfg: None | {cut_day: int, pct1: float}
    Collapses to single flight if either leg < min_budget.
    """
    def flight(s, e, b):
        return {"li_id": li_id, "li_name": li_name,
                "start": s.strftime("%Y-%m-%d"), "end": e.strftime("%Y-%m-%d"),
                "budget": round(b, 2), "daily_budget": 0}

    if not split_cfg:
        return [flight(month_start, month_end, budget)]

    cut = max(1, min(split_cfg["cut_day"], days_in_month(month_start.year, month_start.month) - 1))
    d1_end   = date(month_start.year, month_start.month, cut)
    d2_start = d1_end + timedelta(days=1)

    b1 = round(budget * split_cfg["pct1"] / 100, 2)
    b2 = round(budget - b1, 2)

    if b1 < min_budget or b2 < min_budget:
        return [flight(month_start, month_end, budget)]  # collapse

    return [flight(month_start, d1_end, b1), flight(d2_start, month_end, b2)]

def apply_june_budgets_proportional():
    """Distribute june_budgets proportionally across LIs by May ratio."""
    for io, june_total in st.session_state.june_budgets.items():
        lis = st.session_state.li_data.get(io, [])
        if not lis:
            continue
        may_total = sum(l["prev_budget"] for l in lis)
        if may_total == 0:
            each = round(june_total / len(lis), 2)
            for l in lis:
                st.session_state.jun_inputs[l["li_id"]] = each
        else:
            remaining = june_total
            for i, l in enumerate(lis):
                if i == len(lis) - 1:
                    st.session_state.jun_inputs[l["li_id"]] = round(remaining, 2)
                else:
                    share = round((l["prev_budget"] / may_total) * june_total, 2)
                    st.session_state.jun_inputs[l["li_id"]] = share
                    remaining = round(remaining - share, 2)

def get_jun(li_id):
    return st.session_state.jun_inputs.get(li_id, None)

def get_split(io):
    return st.session_state.io_split.get(io, {"enabled": False, "cut_day": 15, "pct1": 50})

def build_all_flights(month_start, month_end, min_budget):
    rows = []
    for io in sorted(st.session_state.li_data.keys()):
        sp = get_split(io)
        split_cfg = {"cut_day": sp["cut_day"], "pct1": sp["pct1"]} if sp["enabled"] else None
        for li in st.session_state.li_data[io]:
            jn = get_jun(li["li_id"])
            if jn is None:
                continue
            flights = build_flights(li["li_id"], li["li_name"], jn,
                                    month_start, month_end, split_cfg, min_budget)
            for f in flights:
                f["io"] = io
                f["prev_budget"] = li["prev_budget"]
                f["match"] = abs(jn - li["prev_budget"]) < 0.001
            rows.extend(flights)
    return rows

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("## 🚀 Flight Extension Tool")
st.markdown("<div style='color:#55637a;font-family:IBM Plex Mono,monospace;font-size:12px;margin-bottom:20px'>Monthly campaign rollover · GSheets export</div>", unsafe_allow_html=True)

# ── Step 1: Month config ──────────────────────────────────────────────────────
with st.expander("⚙️ Month Configuration", expanded=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        prev_end = st.date_input("Previous Month End (filter)", value=date(2026, 5, 31), key="prev_end")
    with c2:
        month_start = st.date_input("New Month Start", value=date(2026, 6, 1), key="month_start")
    with c3:
        month_end = st.date_input("New Month End", value=date(2026, 6, 30), key="month_end")
    with c4:
        min_budget = st.number_input("Min Flight Budget (€)", value=25.0, min_value=0.0, step=1.0, key="min_budget")
    st.markdown(f"<div class='info-box'>📅 Filtering LI-Setting for flights ending on or before <b>{prev_end}</b> · New flights: <b>{month_start}</b> → <b>{month_end}</b></div>", unsafe_allow_html=True)

# ── Step 2: Upload LI sheets ──────────────────────────────────────────────────
with st.expander("📂 Upload Campaign-Settings Sheets (LI-Setting tab)", expanded=True):
    uploaded_li = st.file_uploader(
        "Drop one or more Campaign-Settings .xlsx files (up to 15 IOs each)",
        type=["xlsx"], accept_multiple_files=True, key="li_uploader"
    )
    if uploaded_li:
        for f in uploaded_li:
            if f.name not in st.session_state.loaded_files:
                try:
                    xl = pd.ExcelFile(f)
                    if "LI-Setting" not in xl.sheet_names:
                        st.error(f"❌ {f.name}: No 'LI-Setting' tab found")
                        continue
                    df = xl.parse("LI-Setting", dtype=str)
                    # Re-parse budget as float
                    if "Active Flight Budget" in df.columns:
                        df["Active Flight Budget"] = pd.to_numeric(df["Active Flight Budget"], errors="coerce")

                    rows, err = parse_li_sheet(df, str(prev_end))
                    if err:
                        st.error(f"❌ {f.name}: {err}")
                        continue

                    added = 0
                    for r in rows:
                        io = r["io"]
                        if io not in st.session_state.li_data:
                            st.session_state.li_data[io] = []
                        if not any(x["li_id"] == r["li_id"] for x in st.session_state.li_data[io]):
                            st.session_state.li_data[io].append(r)
                            added += 1
                            # pre-fill june = prev
                            if r["li_id"] not in st.session_state.jun_inputs:
                                st.session_state.jun_inputs[r["li_id"]] = r["prev_budget"]

                    # sort LIs per IO
                    for io in st.session_state.li_data:
                        st.session_state.li_data[io].sort(key=lambda x: x["li_name"])

                    st.session_state.loaded_files.append(f.name)
                    st.success(f"✅ {f.name}: {added} LIs added across {len(set(r['io'] for r in rows))} IOs")
                except Exception as ex:
                    st.error(f"❌ {f.name}: {ex}")

    if st.session_state.loaded_files:
        st.markdown(f"**Loaded files:** " + " · ".join([f"`{f}`" for f in st.session_state.loaded_files]))
        total_ios = len(st.session_state.li_data)
        total_lis = sum(len(v) for v in st.session_state.li_data.values())
        st.markdown(f"**{total_ios} IOs · {total_lis} LIs** loaded")

    if st.button("🗑️ Clear all loaded data", type="secondary"):
        for k in ["li_data","loaded_files","june_budgets","june_ref_file","jun_inputs","io_split"]:
            st.session_state[k] = {} if k != "loaded_files" else []
        st.rerun()

# ── Step 3: June budget reference ─────────────────────────────────────────────
with st.expander("📋 June Budget Reference File", expanded=True):
    june_file = st.file_uploader(
        "Upload reference sheet with IO Name + June Budget columns",
        type=["xlsx"], key="june_uploader"
    )
    if june_file and june_file.name != st.session_state.june_ref_file:
        try:
            df_june = pd.read_excel(june_file)
            budgets, err = parse_june_budget_sheet(df_june)
            if err:
                st.error(f"❌ {err}")
            else:
                st.session_state.june_budgets = budgets
                st.session_state.june_ref_file = june_file.name
                st.success(f"✅ {june_file.name}: {len(budgets)} IOs loaded")
        except Exception as ex:
            st.error(f"❌ {ex}")

    if st.session_state.june_budgets:
        loaded_ios = set(st.session_state.li_data.keys())
        ref_ios    = set(st.session_state.june_budgets.keys())
        in_ref_not_loaded = ref_ios - loaded_ios
        in_loaded_not_ref = loaded_ios - ref_ios

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚡ Apply June Budgets (proportional)", type="primary"):
                apply_june_budgets_proportional()
                st.success("June budgets applied! Adjust individual LIs below if needed.")
                st.rerun()
        with col2:
            st.markdown(f"`{len(st.session_state.june_budgets)}` IOs in reference · `{len(loaded_ios)}` loaded")

        if in_ref_not_loaded:
            st.markdown(f"<div class='warn-box'>⚠️ {len(in_ref_not_loaded)} IOs in June file but not yet in LI sheets:<br>" +
                        "<br>".join(f"• {io}" for io in sorted(in_ref_not_loaded)) + "</div>", unsafe_allow_html=True)
        if in_loaded_not_ref:
            st.markdown(f"<div class='warn-box'>⚠️ {len(in_loaded_not_ref)} loaded IOs missing from June file → keeping previous budget:<br>" +
                        "<br>".join(f"• {io}" for io in sorted(in_loaded_not_ref)) + "</div>", unsafe_allow_html=True)

# ── Step 4: Per-IO config + LI budget editing ─────────────────────────────────
if st.session_state.li_data:
    st.markdown("---")
    st.markdown("### 📊 IO Groups & Line Items")

    io_list = sorted(st.session_state.li_data.keys())

    # IO selector
    sel_io = st.selectbox("Select IO Group", io_list, key="sel_io")

    if sel_io:
        lis = st.session_state.li_data[sel_io]
        sp  = get_split(sel_io)
        jun_ref = st.session_state.june_budgets.get(sel_io)

        # IO config
        with st.container():
            st.markdown(f"<div class='section-header'>IO Split Settings — {sel_io}</div>", unsafe_allow_html=True)
            sc1, sc2, sc3, sc4 = st.columns([1, 1, 1, 2])
            with sc1:
                split_on = st.toggle("Mid-flight Split", value=sp["enabled"], key=f"split_{sel_io}")
            if split_on:
                with sc2:
                    cut_day = st.number_input("Cut Day", min_value=1, max_value=27, value=sp["cut_day"], key=f"cut_{sel_io}")
                with sc3:
                    pct1 = st.number_input("1st Period %", min_value=1, max_value=99, value=float(sp["pct1"]), key=f"pct_{sel_io}")
                with sc4:
                    last_day = days_in_month(month_start.year, month_start.month)
                    cut = max(1, min(int(cut_day), last_day - 1))
                    d1e = date(month_start.year, month_start.month, cut)
                    d2s = d1e + timedelta(days=1)
                    st.markdown(f"<div class='info-box' style='margin-top:22px'>"
                                f"{month_start} → {d1e} ({pct1}%)  |  {d2s} → {month_end} ({100-pct1}%)"
                                f"</div>", unsafe_allow_html=True)
                st.session_state.io_split[sel_io] = {"enabled": True, "cut_day": int(cut_day), "pct1": float(pct1)}
            else:
                st.session_state.io_split[sel_io] = {"enabled": False, "cut_day": sp["cut_day"], "pct1": sp["pct1"]}

        # Totals
        may_total = sum(l["prev_budget"] for l in lis)
        jun_total = sum(st.session_state.jun_inputs.get(l["li_id"], 0) or 0 for l in lis)
        delta     = round(jun_total - (jun_ref or may_total), 2)

        cols = st.columns(4)
        cols[0].metric("Prev Month Total", f"€{may_total:,.2f}")
        if jun_ref is not None:
            cols[1].metric("June Reference", f"€{jun_ref:,.2f}", delta=f"€{jun_ref - may_total:,.2f}")
        cols[2].metric("June Entered", f"€{jun_total:,.2f}",
                       delta=f"€{delta:,.2f}" if jun_ref is not None else None)
        cols[3].metric("LIs", f"{sum(1 for l in lis if get_jun(l['li_id']) is not None)}/{len(lis)} filled")

        if jun_ref is not None and abs(jun_total - jun_ref) > 0.01:
            st.warning(f"⚠️ June entered (€{jun_total:,.2f}) doesn't match reference (€{jun_ref:,.2f}) — difference: €{delta:+,.2f}")

        # LI table
        st.markdown(f"<div class='section-header'>Line Items</div>", unsafe_allow_html=True)

        sp_cfg = get_split(sel_io)
        split_cfg_preview = {"cut_day": sp_cfg["cut_day"], "pct1": sp_cfg["pct1"]} if sp_cfg["enabled"] else None

        for li in lis:
            li_id   = li["li_id"]
            prev_b  = li["prev_budget"]
            cur_jun = st.session_state.jun_inputs.get(li_id, prev_b)

            c1, c2, c3, c4 = st.columns([4, 1.2, 1.4, 2])
            with c1:
                st.markdown(f"<span style='font-family:IBM Plex Mono,monospace;font-size:11px'>{li['li_name']}</span><br>"
                            f"<span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:#55637a'>{li_id}</span>",
                            unsafe_allow_html=True)
            with c2:
                st.markdown(f"<span style='font-family:IBM Plex Mono,monospace;color:#ffc94d'>€{prev_b:,.2f}</span>",
                            unsafe_allow_html=True)
            with c3:
                new_val = st.number_input("", value=float(cur_jun or prev_b),
                                          min_value=0.0, step=1.0,
                                          key=f"jun_{li_id}", label_visibility="collapsed")
                st.session_state.jun_inputs[li_id] = new_val
            with c4:
                if split_cfg_preview and new_val > 0:
                    flights = build_flights(li_id, li["li_name"], new_val,
                                           month_start, month_end, split_cfg_preview, min_budget)
                    if len(flights) == 2:
                        st.markdown(f"<span style='font-family:IBM Plex Mono,monospace;font-size:9px;color:#55637a'>"
                                    f"F1 {flights[0]['start']}→{flights[0]['end']} €{flights[0]['budget']} | "
                                    f"F2 {flights[1]['start']}→{flights[1]['end']} €{flights[1]['budget']}</span>",
                                    unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span style='font-family:IBM Plex Mono,monospace;font-size:9px;color:#ff5272'>"
                                    f"1 flight (below €{min_budget} min)</span>", unsafe_allow_html=True)
                else:
                    match = abs(new_val - prev_b) < 0.001
                    label = "✓ match" if match else "≠ changed"
                    color = "#2effa0" if match else "#ffc94d"
                    st.markdown(f"<span style='font-family:IBM Plex Mono,monospace;font-size:10px;color:{color}'>{label}</span>",
                                unsafe_allow_html=True)
            st.markdown("<hr style='margin:4px 0;border-color:#1e2436'>", unsafe_allow_html=True)

# ── Step 5: Output ────────────────────────────────────────────────────────────
if st.session_state.li_data:
    flights = build_all_flights(month_start, month_end, min_budget)
    if flights:
        st.markdown("---")
        st.markdown("### 📤 Extension Output")

        df_out = pd.DataFrame(flights)[["li_id","li_name","start","end","budget","daily_budget","io","prev_budget","match"]]

        # Summary
        total_flights = len(df_out)
        match_count   = df_out["match"].sum()
        diff_count    = total_flights - match_count
        june_total    = df_out["budget"].sum()

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Total Flights",   total_flights)
        mc2.metric("Budget Match",    int(match_count))
        mc3.metric("Budget Changed",  int(diff_count))
        mc4.metric("June Total €",    f"€{june_total:,.2f}")

        # Filter tabs
        view = st.radio("View", ["All", "Match only", "Changed only"], horizontal=True, key="out_view")
        if view == "Match only":
            df_show = df_out[df_out["match"]]
        elif view == "Changed only":
            df_show = df_out[~df_out["match"]]
        else:
            df_show = df_out

        # Display table
        display_cols = ["li_id","start","end","budget","daily_budget"]
        st.dataframe(
            df_show[display_cols + ["li_name"]].rename(columns={
                "li_id": "LI ID", "start": "Start Date", "end": "End Date",
                "budget": "Budget €", "daily_budget": "Daily Budget", "li_name": "LI Name"
            }),
            use_container_width=True, hide_index=True
        )

        st.markdown(f"**{len(df_show)} rows** ready to copy/download")

        # Download CSV
        csv_out = df_show[display_cols].to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv_out,
            file_name=f"extension_{month_start.strftime('%Y-%m')}.csv",
            mime="text/csv",
        )

        # TSV for GSheets copy
        tsv_out = df_show[display_cols].to_csv(index=False, sep="\t")
        st.download_button(
            label="📋 Download TSV (paste into GSheets)",
            data=tsv_out,
            file_name=f"extension_{month_start.strftime('%Y-%m')}.tsv",
            mime="text/tab-separated-values",
        )

        st.markdown("""
        <div class='info-box'>
        💡 <b>To paste into Google Sheets:</b> Download the TSV file → open it in a text editor → select all → copy → paste into GSheets cell A1
        </div>
        """, unsafe_allow_html=True)
