import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Flight Extension Tool",
    page_icon="🚀",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

if "li_data" not in st.session_state:
    st.session_state.li_data = {}

if "june_budgets" not in st.session_state:
    st.session_state.june_budgets = {}

if "jun_inputs" not in st.session_state:
    st.session_state.jun_inputs = {}

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def parse_date_val(v):

    if pd.isna(v) or v is None:
        return None

    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")

    s = str(v).strip()

    if len(s) >= 10 and s[4] == "-":
        return s[:10]

    return None


def parse_li_sheet(df, filter_end_date):

    required = [
        "IO Name",
        "LI ID",
        "LI Name",
        "Active Flight End Date",
        "Active Flight Budget",
    ]

    for c in required:

        if c not in df.columns:
            return [], f"Missing column: {c}"

    records = []

    for _, row in df.iterrows():

        ed = parse_date_val(
            row["Active Flight End Date"]
        )

        if not ed:
            continue

        if ed > filter_end_date:
            continue

        records.append({
            "io": str(row["IO Name"]).strip(),
            "li_id": str(row["LI ID"]).strip(),
            "li_name": str(row["LI Name"]).strip(),
            "end_date": ed,
            "prev_budget": float(
                row["Active Flight Budget"]
            ) if not pd.isna(
                row["Active Flight Budget"]
            ) else 0.0,
        })

    if not records:
        return [], "No valid rows found"

    # ─────────────────────────────────────────────────────────────────────
    # FIND LATEST END DATE PER IO
    # ─────────────────────────────────────────────────────────────────────

    latest_dates = {}

    for r in records:

        io = r["io"]

        if io not in latest_dates:

            latest_dates[io] = r["end_date"]

        else:

            latest_dates[io] = max(
                latest_dates[io],
                r["end_date"]
            )

    # ─────────────────────────────────────────────────────────────────────
    # KEEP ONLY LATEST DATE ROWS
    # ─────────────────────────────────────────────────────────────────────

    filtered = []

    for r in records:

        if r["end_date"] == latest_dates[r["io"]]:

            filtered.append(r)

    filtered.sort(
        key=lambda x: (x["io"], x["li_name"])
    )

    return filtered, None


def parse_june_budget_sheet(df):

    io_col = next(
        (
            c for c in df.columns
            if "io name" in c.lower()
        ),
        None,
    )

    bud_col = next(
        (
            c for c in df.columns
            if "budget" in c.lower()
        ),
        None,
    )

    if not io_col or not bud_col:
        return {}, "Missing IO/Budget columns"

    out = {}

    for _, row in df.iterrows():

        io = str(row[io_col]).strip()

        try:

            val = float(row[bud_col])

            if io:
                out[io] = val

        except:
            pass

    return out, None


def apply_proportional(io_name, june_total):

    lis = st.session_state.li_data[io_name]

    may_total = sum(
        x["prev_budget"]
        for x in lis
    )

    if may_total == 0:
        return

    remaining = june_total

    for i, li in enumerate(lis):

        if i == len(lis) - 1:

            st.session_state.jun_inputs[
                li["li_id"]
            ] = round(
                remaining,
                2,
            )

        else:

            share = round(
                (
                    li["prev_budget"]
                    / may_total
                ) * june_total,
                2,
            )

            st.session_state.jun_inputs[
                li["li_id"]
            ] = share

            remaining -= share


def build_output(
    month_start,
    month_end,
):

    rows = []

    for io, lis in st.session_state.li_data.items():

        for li in lis:

            budget = st.session_state.jun_inputs.get(
                li["li_id"],
                li["prev_budget"],
            )

            rows.append({
                "LI ID": li["li_id"],
                "LI Name": li["li_name"],
                "Start Date": month_start.strftime("%Y-%m-%d"),
                "End Date": month_end.strftime("%Y-%m-%d"),
                "Budget": round(budget, 2),
                "Daily Budget": 0,
                "IO": io,
            })

    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────────────
# TITLE
# ─────────────────────────────────────────────────────────────────────────────

st.title("🚀 Flight Extension Tool")

# ─────────────────────────────────────────────────────────────────────────────
# MONTH CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.header("1. Month Configuration")

c1, c2 = st.columns(2)

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

prev_end = month_start - timedelta(days=1)

st.info(
    f"Using latest available end date <= {prev_end}"
)

# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD CAMPAIGN FILES
# ─────────────────────────────────────────────────────────────────────────────

st.header("2. Upload Campaign Settings Files")

uploaded_li = st.file_uploader(
    "Upload Campaign Settings Files",
    type=["xlsx"],
    accept_multiple_files=True,
)

if uploaded_li:

    st.session_state.li_data = {}

    for f in uploaded_li:

        try:

            xl = pd.ExcelFile(f)

            if "LI-Setting" not in xl.sheet_names:

                st.error(
                    f"{f.name}: Missing LI-Setting tab"
                )

                continue

            df = xl.parse("LI-Setting")

            rows, err = parse_li_sheet(
                df,
                str(prev_end),
            )

            if err:

                st.error(err)

                continue

            for r in rows:

                io = r["io"]

                if io not in st.session_state.li_data:

                    st.session_state.li_data[io] = []

                st.session_state.li_data[io].append(r)

                if r["li_id"] not in st.session_state.jun_inputs:

                    st.session_state.jun_inputs[
                        r["li_id"]
                    ] = r["prev_budget"]

            st.success(f"{f.name} loaded")

        except Exception as ex:

            st.error(ex)

# ─────────────────────────────────────────────────────────────────────────────
# JUNE BUDGET FILE
# ─────────────────────────────────────────────────────────────────────────────

st.header("3. Upload June Budget File")

june_file = st.file_uploader(
    "Upload June Budget File",
    type=["xlsx"],
)

if june_file:

    try:

        dfj = pd.read_excel(june_file)

        budgets, err = parse_june_budget_sheet(dfj)

        if err:

            st.error(err)

        else:

            st.session_state.june_budgets = budgets

            st.success(
                "June budget file loaded"
            )

    except Exception as ex:

        st.error(ex)

# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

if (
    st.session_state.li_data
    and st.session_state.june_budgets
):

    st.header("4. IO Budget Comparison")

    correct_ios = []
    mismatch_ios = []

    for io, lis in st.session_state.li_data.items():

        may_total = round(
            sum(
                x["prev_budget"]
                for x in lis
            ),
            2,
        )

        june_total = round(
            st.session_state.june_budgets.get(
                io,
                0,
            ),
            2,
        )

        diff = round(
            june_total - may_total,
            2,
        )

        # MATCHING IO

        if abs(diff) < 0.01:

            correct_ios.append({
                "IO Name": io,
                "Previous Total": may_total,
                "June Budget": june_total,
            })

            # keep same budgets

            for li in lis:

                st.session_state.jun_inputs[
                    li["li_id"]
                ] = li["prev_budget"]

        # MISMATCH IO

        else:

            mismatch_ios.append({
                "IO Name": io,
                "Previous Total": may_total,
                "June Budget": june_total,
                "Difference": diff,
            })

            # proportional split

            apply_proportional(
                io,
                june_total,
            )

    # ─────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ─────────────────────────────────────────────────────────────────────

    c1, c2 = st.columns(2)

    with c1:
        st.success(
            f"✅ Matching IOs: {len(correct_ios)}"
        )

    with c2:
        st.warning(
            f"⚠️ IOs Needing Changes: {len(mismatch_ios)}"
        )

    # ─────────────────────────────────────────────────────────────────────
    # MATCHING IOS
    # ─────────────────────────────────────────────────────────────────────

    if correct_ios:

        st.subheader("✅ Matching IOs")

        st.dataframe(
            pd.DataFrame(correct_ios),
            use_container_width=True,
            hide_index=True,
        )

    # ─────────────────────────────────────────────────────────────────────
    # MISMATCH IOS
    # ─────────────────────────────────────────────────────────────────────

    if mismatch_ios:

        st.subheader(
            "⚠️ IOs Requiring Budget Changes"
        )

        st.dataframe(
            pd.DataFrame(mismatch_ios),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")

        for x in mismatch_ios:

            io = x["IO Name"]

            st.markdown(f"## {io}")

            lis = st.session_state.li_data[io]

            edit_rows = []

            for li in lis:

                li_id = li["li_id"]

                prev_budget = li["prev_budget"]

                current_budget = (
                    st.session_state.jun_inputs.get(
                        li_id,
                        prev_budget,
                    )
                )

                c1, c2, c3, c4 = st.columns(
                    [4, 2, 2, 2]
                )

                with c1:

                    st.write(li["li_name"])

                with c2:

                    st.write(
                        f"€{prev_budget:,.2f}"
                    )

                with c3:

                    new_budget = st.number_input(
                        f"{io}_{li_id}",
                        value=float(current_budget),
                        min_value=0.0,
                        step=1.0,
                    )

                    st.session_state.jun_inputs[
                        li_id
                    ] = new_budget

                with c4:

                    change = round(
                        new_budget - prev_budget,
                        2,
                    )

                    if abs(change) < 0.01:

                        st.success("MATCH")

                    else:

                        st.warning(
                            f"{change:+,.2f}"
                        )

                edit_rows.append({
                    "LI ID": li_id,
                    "LI Name": li["li_name"],
                    "Previous Budget": prev_budget,
                    "New Budget": new_budget,
                })

            st.dataframe(
                pd.DataFrame(edit_rows),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.li_data:

    st.header("5. Final Output")

    df_out = build_output(
        month_start,
        month_end,
    )

    st.dataframe(
        df_out,
        use_container_width=True,
        hide_index=True,
    )

    csv = df_out[
        [
            "LI ID",
            "Start Date",
            "End Date",
            "Budget",
            "Daily Budget",
        ]
    ].to_csv(index=False)

    st.download_button(
        "⬇️ Download CSV",
        csv,
        file_name="flight_extension.csv",
        mime="text/csv",
    )
