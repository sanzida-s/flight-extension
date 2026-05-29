import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import calendar

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

.section-header {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #55637a;
    margin-bottom: 8px;
    margin-top: 4px;
}

.info-box {
    background: rgba(93,184,255,.07);
    border: 1px solid rgba(93,184,255,.2);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
    color: #5db8ff;
    margin-bottom: 10px;
}

.warn-box {
    background: rgba(255,201,77,.07);
    border: 1px solid rgba(255,201,77,.2);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    font-family: 'IBM Plex Mono', monospace;
    color: #ffc94d;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "li_data": {},
        "loaded_files": [],
        "june_budgets": {},
        "june_ref_file": None,
        "jun_inputs": {},
        "io_split": {},
    }

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_date_val(v):

    if pd.isna(v) or v is None:
        return None

    if isinstance(v, (date,)):
        return v.strftime("%Y-%m-%d")

    if hasattr(v, 'date'):
        return v.strftime("%Y-%m-%d")

    s = str(v).strip()

    if len(s) >= 10 and s[4] == '-':
        return s[:10]

    return None


def parse_li_sheet(df, filter_end_date: str):
    """
    Per IO:
    - Find MOST RECENT Active Flight End Date <= filter_end_date
    - Keep ONLY rows from that date
    """

    required = [
        "IO Name",
        "LI ID",
        "LI Name",
        "Active Flight End Date",
        "Active Flight Budget"
    ]

    for col in required:
        if col not in df.columns:
            return [], f"Missing column: '{col}'"

    records = []

    for _, row in df.iterrows():

        ed = parse_date_val(row["Active Flight End Date"])

        if not ed:
            continue

        if ed > filter_end_date:
            continue

        records.append({
            "io": str(row["IO Name"]).strip(),
            "li_id": row["LI ID"],
            "li_name": str(row["LI Name"]).strip(),
            "end_date": ed,
            "prev_budget": float(row["Active Flight Budget"])
            if not pd.isna(row["Active Flight Budget"])
            else 0.0,
        })

    if not records:
        return [], f"No rows with Active Flight End Date ≤ {filter_end_date}"

    # ── Find latest end date PER IO ─────────────────────────────────────────

    latest_io_dates = {}

    for r in records:

        io = r["io"]

        if io not in latest_io_dates:
            latest_io_dates[io] = r["end_date"]
        else:
            latest_io_dates[io] = max(
                latest_io_dates[io],
                r["end_date"]
            )

    # ── Keep ONLY latest date rows ──────────────────────────────────────────

    filtered = []

    for r in records:
        if r["end_date"] == latest_io_dates[r["io"]]:
            filtered.append(r)

    # ── Deduplicate ──────────────────────────────────────────────────────────

    best = {}

    for r in filtered:
        key = (r["io"], r["li_id"])
        best[key] = r

    result = list(best.values())

    result.sort(key=lambda x: (x["io"], x["li_name"]))

    return result, None


def parse_june_budget_sheet(df):

    io_col = next(
        (c for c in df.columns if "io name" in c.lower()),
        None
    )

    bud_col = next(
        (c for c in df.columns if "budget" in c.lower()),
        None
    )

    if not io_col or not bud_col:
        return {}, f"Could not find IO Name/Budget columns"

    out = {}

    for _, row in df.iterrows():

        io = str(row[io_col]).strip()

        try:
            bud = float(row[bud_col])

            if io and not np.isnan(bud):
                out[io] = bud

        except:
            pass

    return out, None


def days_in_month(y, m):
    return calendar.monthrange(y, m)[1]


def build_flights(
    li_id,
    li_name,
    budget,
    month_start,
    month_end,
    split_cfg,
    min_budget
):

    def flight(s, e, b):
        return {
            "li_id": li_id,
            "li_name": li_name,
            "start": s.strftime("%Y-%m-%d"),
            "end": e.strftime("%Y-%m-%d"),
            "budget": round(b, 2),
            "daily_budget": 0,
        }

    if not split_cfg:
        return [flight(month_start, month_end, budget)]

    cut = max(
        1,
        min(
            split_cfg["cut_day"],
            days_in_month(month_start.year, month_start.month) - 1
        )
    )

    d1_end = date(month_start.year, month_start.month, cut)
    d2_start = d1_end + timedelta(days=1)

    b1 = round(budget * split_cfg["pct1"] / 100, 2)
    b2 = round(budget - b1, 2)

    if b1 < min_budget or b2 < min_budget:
        return [flight(month_start, month_end, budget)]

    return [
        flight(month_start, d1_end, b1),
        flight(d2_start, month_end, b2),
    ]


def apply_june_budgets_proportional():

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

                    st.session_state.jun_inputs[l["li_id"]] = round(
                        remaining,
                        2
                    )

                else:

                    share = round(
                        (l["prev_budget"] / may_total) * june_total,
                        2
                    )

                    st.session_state.jun_inputs[l["li_id"]] = share

                    remaining = round(remaining - share, 2)


def get_jun(li_id):
    return st.session_state.jun_inputs.get(li_id, None)


def get_split(io):
    return st.session_state.io_split.get(
        io,
        {
            "enabled": False,
            "cut_day": 15,
            "pct1": 50
        }
    )


def build_all_flights(month_start, month_end, min_budget):

    rows = []

    for io in sorted(st.session_state.li_data.keys()):

        sp = get_split(io)

        split_cfg = (
            {
                "cut_day": sp["cut_day"],
                "pct1": sp["pct1"]
            }
            if sp["enabled"]
            else None
        )

        for li in st.session_state.li_data[io]:

            jn = get_jun(li["li_id"])

            if jn is None:
                continue

            flights = build_flights(
                li["li_id"],
                li["li_name"],
                jn,
                month_start,
                month_end,
                split_cfg,
                min_budget
            )

            for f in flights:

                f["io"] = io
                f["prev_budget"] = li["prev_budget"]
                f["match"] = abs(jn - li["prev_budget"]) < 0.001

                rows.append(f)

    return rows

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("## 🚀 Flight Extension Tool")

with st.expander("⚙️ Month Configuration", expanded=True):

    c1, c2, c3 = st.columns(3)

    with c1:
        month_start = st.date_input(
            "New Month Start",
            value=date(2026, 6, 1)
        )

    with c2:
        month_end = st.date_input(
            "New Month End",
            value=date(2026, 6, 30)
        )

    with c3:
        min_budget = st.number_input(
            "Min Flight Budget (€)",
            value=25.0,
            min_value=0.0
        )

    prev_end = month_start - timedelta(days=1)

    st.markdown(
        f"""
        <div class='info-box'>
        Filter date: <b>{prev_end}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

# ── Upload Files ──────────────────────────────────────────────────────────────

uploaded_li = st.file_uploader(
    "Upload Campaign Settings Files",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_li:

    for f in uploaded_li:

        if f.name not in st.session_state.loaded_files:

            try:

                xl = pd.ExcelFile(f)

                if "LI-Setting" not in xl.sheet_names:
                    st.error(f"{f.name}: Missing LI-Setting tab")
                    continue

                df = xl.parse("LI-Setting", dtype=str)

                if "Active Flight Budget" in df.columns:
                    df["Active Flight Budget"] = pd.to_numeric(
                        df["Active Flight Budget"],
                        errors="coerce"
                    )

                rows, err = parse_li_sheet(df, str(prev_end))

                if err:
                    st.error(err)
                    continue

                added = 0

                for r in rows:

                    io = r["io"]
                    li_id = r["li_id"]

                    if io not in st.session_state.li_data:
                        st.session_state.li_data[io] = []

                    if not any(
                        x["li_id"] == li_id
                        for x in st.session_state.li_data[io]
                    ):

                        st.session_state.li_data[io].append(r)

                        added += 1

                        if li_id not in st.session_state.jun_inputs:
                            st.session_state.jun_inputs[li_id] = r["prev_budget"]

                st.session_state.loaded_files.append(f.name)

                st.success(f"{f.name}: {added} LIs loaded")

            except Exception as ex:
                st.error(ex)

# ── June Budget Upload ────────────────────────────────────────────────────────

june_file = st.file_uploader(
    "Upload June Budget File",
    type=["xlsx"]
)

if june_file:

    try:

        df_june = pd.read_excel(june_file)

        budgets, err = parse_june_budget_sheet(df_june)

        if err:
            st.error(err)

        else:

            st.session_state.june_budgets = budgets

            st.success(
                f"{len(budgets)} IO budgets loaded"
            )

    except Exception as ex:
        st.error(ex)

if st.session_state.june_budgets:

    if st.button("Apply June Budgets"):
        apply_june_budgets_proportional()
        st.success("Budgets Applied")

# ── IO Editing ────────────────────────────────────────────────────────────────

if st.session_state.li_data:

    io_list = sorted(st.session_state.li_data.keys())

    sel_io = st.selectbox(
        "Select IO",
        io_list
    )

    lis = st.session_state.li_data[sel_io]

    may_total = sum(l["prev_budget"] for l in lis)

    jun_total = sum(
        st.session_state.jun_inputs.get(l["li_id"], 0)
        for l in lis
    )

    c1, c2 = st.columns(2)

    c1.metric("Previous Total", f"€{may_total:,.2f}")
    c2.metric("June Total", f"€{jun_total:,.2f}")

    st.markdown("### Line Items")

    for li in lis:

        li_id = li["li_id"]

        c1, c2, c3 = st.columns([4, 2, 2])

        with c1:
            st.write(li["li_name"])

        with c2:
            st.write(f"€{li['prev_budget']:,.2f}")

        with c3:

            new_val = st.number_input(
                f"Budget {li_id}",
                value=float(
                    st.session_state.jun_inputs.get(
                        li_id,
                        li["prev_budget"]
                    )
                ),
                min_value=0.0,
                step=1.0
            )

            st.session_state.jun_inputs[li_id] = new_val

# ── Output ────────────────────────────────────────────────────────────────────

if st.session_state.li_data:

    flights = build_all_flights(
        month_start,
        month_end,
        min_budget
    )

    if flights:

        st.markdown("## Output")

        df_out = pd.DataFrame(flights)

        display_cols = [
            "li_id",
            "li_name",
            "start",
            "end",
            "budget",
            "daily_budget"
        ]

        st.dataframe(
            df_out[display_cols],
            use_container_width=True,
            hide_index=True
        )

        csv_out = df_out[
            [
                "li_id",
                "start",
                "end",
                "budget",
                "daily_budget"
            ]
        ].to_csv(index=False)

        st.download_button(
            label="Download CSV",
            data=csv_out,
            file_name=f"extension_{month_start}.csv",
            mime="text/csv",
        )
