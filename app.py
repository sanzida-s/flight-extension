import streamlit as st
import pandas as pd
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

if "processed" not in st.session_state:
    st.session_state.processed = False

if "li_data" not in st.session_state:
    st.session_state.li_data = {}

if "june_budgets" not in st.session_state:
    st.session_state.june_budgets = {}

if "jun_inputs" not in st.session_state:
    st.session_state.jun_inputs = {}

if "approved_mismatch" not in st.session_state:
    st.session_state.approved_mismatch = {}

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


def build_output(
    month_start,
    month_end,
):

    rows = []

    if not st.session_state.li_data:
        return pd.DataFrame()

    for io, lis in st.session_state.li_data.items():

        for li in lis:

            li_id = li["li_id"]

            budget = st.session_state.jun_inputs.get(
                li_id,
                li["prev_budget"],
            )

            rows.append({
                "LI ID": li_id,
                "Start Date": month_start.strftime("%Y-%m-%d"),
                "End Date": month_end.strftime("%Y-%m-%d"),
                "Budget": round(float(budget), 2),
                "Daily Budget": 0,
            })

    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────────────
# TITLE
# ─────────────────────────────────────────────────────────────────────────────

st.title("🚀 Flight Extension Tool")

# ─────────────────────────────────────────────────────────────────────────────
# MONTH CONFIG
# ─────────────────────────────────────────────────────────────────────────────

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

# ─────────────────────────────────────────────────────────────────────────────
# FILE UPLOADS
# ─────────────────────────────────────────────────────────────────────────────

st.header("1. Upload Files")

uploaded_li = st.file_uploader(
    "Upload Campaign Settings Files",
    type=["xlsx"],
    accept_multiple_files=True,
)

june_file = st.file_uploader(
    "Upload June Budget File",
    type=["xlsx"],
)

# ─────────────────────────────────────────────────────────────────────────────
# RUN BUTTON
# ─────────────────────────────────────────────────────────────────────────────

run_clicked = st.button("🚀 Run Validation")

if run_clicked:

    st.session_state.processed = False

    # RESET ONLY THESE
    st.session_state.li_data = {}
    st.session_state.june_budgets = {}

    # ─────────────────────────────────────────────────────────────────
    # PROCESS CAMPAIGN FILES
    # ─────────────────────────────────────────────────────────────────

    if uploaded_li:

        for f in uploaded_li:

            try:

                xl = pd.ExcelFile(f)

                if "LI-Setting" not in xl.sheet_names:
                    continue

                df = xl.parse("LI-Setting")

                rows, err = parse_li_sheet(
                    df,
                    str(prev_end),
                )

                if err:
                    continue

                for r in rows:

                    io = r["io"]

                    if io not in st.session_state.li_data:

                        st.session_state.li_data[io] = []

                    st.session_state.li_data[io].append(r)

                    # DO NOT OVERWRITE EXISTING EDITS

                    if r["li_id"] not in st.session_state.jun_inputs:

                        st.session_state.jun_inputs[
                            r["li_id"]
                        ] = r["prev_budget"]

            except Exception as ex:

                st.error(ex)

    # ─────────────────────────────────────────────────────────────────
    # PROCESS JUNE FILE
    # ─────────────────────────────────────────────────────────────────

    if june_file:

        try:

            dfj = pd.read_excel(june_file)

            budgets, err = parse_june_budget_sheet(dfj)

            if not err:

                st.session_state.june_budgets = budgets

        except Exception as ex:

            st.error(ex)

    st.session_state.processed = True

# ─────────────────────────────────────────────────────────────────────────────
# SHOW ONLY IOS NEEDING ATTENTION
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.processed:

    st.header("2. IOs Requiring Attention")

    mismatch_found = False

    for io, lis in st.session_state.li_data.items():

        expected_total = round(
            st.session_state.june_budgets.get(
                io,
                0,
            ),
            2,
        )

        current_total = round(
            sum(
                st.session_state.jun_inputs.get(
                    li["li_id"],
                    li["prev_budget"],
                )
                for li in lis
            ),
            2,
        )

        remaining_diff = round(
            expected_total - current_total,
            2,
        )

        approved = st.session_state.approved_mismatch.get(
            io,
            False,
        )

        # SKIP APPROVED
        if approved:
            continue

        # SKIP MATCHED
        if abs(remaining_diff) < 0.01:
            continue

        mismatch_found = True

        st.markdown("---")

        st.subheader(io)

        st.write(
            f"Current Total: €{current_total:,.2f}"
        )

        st.write(
            f"Expected June Total: €{expected_total:,.2f}"
        )

        st.warning(
            f"Difference: €{remaining_diff:+,.2f}"
        )

        approve = st.checkbox(
            "This mismatch is intentional",
            key=f"approve_{io}",
        )

        st.session_state.approved_mismatch[
            io
        ] = approve

        # ─────────────────────────────────────────────────────────
        # LI EDITING
        # ─────────────────────────────────────────────────────────

        for li in lis:

            li_id = li["li_id"]

            prev_budget = li["prev_budget"]

            current_budget = st.session_state.jun_inputs.get(
                li_id,
                prev_budget,
            )

            c1, c2, c3 = st.columns([5, 2, 2])

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

        # ─────────────────────────────────────────────────────────
        # LIVE VALIDATION
        # ─────────────────────────────────────────────────────────

        updated_total = round(
            sum(
                st.session_state.jun_inputs.get(
                    li["li_id"],
                    0,
                )
                for li in lis
            ),
            2,
        )

        updated_diff = round(
            expected_total - updated_total,
            2,
        )

        if abs(updated_diff) < 0.01:

            st.success("✅ Now Matching")

        else:

            st.warning(
                f"⚠ Remaining Difference: €{updated_diff:+,.2f}"
            )

    if not mismatch_found:

        st.success(
            "✅ All IOs are matching correctly"
        )

# ─────────────────────────────────────────────────────────────────────────────
# FINAL OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

if (
    st.session_state.processed
    and st.session_state.li_data
):

    st.header("3. Final Output")

    df_out = build_output(
        month_start,
        month_end,
    )

    if len(df_out) > 0:

        st.dataframe(
            df_out,
            use_container_width=True,
            hide_index=True,
        )

        csv = df_out.to_csv(index=False)

        st.download_button(
            "⬇️ Download CSV",
            csv,
            file_name="flight_extension.csv",
            mime="text/csv",
        )

    else:

        st.warning(
            "No output rows generated."
        )
