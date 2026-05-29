import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(
    page_title="Flight Extension Tool",
    layout="wide"
)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

for k, v in {
    "li_data": {},
    "june_budgets": {},
    "jun_inputs": {},
    "approved": {}
}.items():

    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def parse_date(v):

    try:
        return pd.to_datetime(v)
    except:
        return None


def parse_li_sheet(df, cutoff_date):

    required = [
        "IO Name",
        "LI ID",
        "LI Name",
        "Active Flight End Date",
        "Active Flight Budget",
    ]

    for c in required:

        if c not in df.columns:
            return []

    rows = []

    for _, r in df.iterrows():

        end_date = parse_date(
            r["Active Flight End Date"]
        )

        if end_date is None:
            continue

        if end_date > cutoff_date:
            continue

        rows.append({
            "io": str(r["IO Name"]).strip(),
            "li_id": str(r["LI ID"]).strip(),
            "li_name": str(r["LI Name"]).strip(),
            "end_date": end_date,
            "budget": float(
                r["Active Flight Budget"]
            ) if not pd.isna(
                r["Active Flight Budget"]
            ) else 0
        })

    if not rows:
        return []

    # latest date per IO

    latest = {}

    for r in rows:

        io = r["io"]

        if io not in latest:
            latest[io] = r["end_date"]
        else:
            latest[io] = max(
                latest[io],
                r["end_date"]
            )

    final_rows = []

    for r in rows:

        if r["end_date"] == latest[r["io"]]:
            final_rows.append(r)

    return final_rows


def parse_budget_sheet(df):

    io_col = next(
        (
            c for c in df.columns
            if "io" in c.lower()
        ),
        None
    )

    budget_col = next(
        (
            c for c in df.columns
            if "budget" in c.lower()
        ),
        None
    )

    out = {}

    if not io_col or not budget_col:
        return out

    for _, r in df.iterrows():

        try:

            io = str(r[io_col]).strip()

            out[io] = float(
                r[budget_col]
            )

        except:
            pass

    return out


def build_output(start_date, end_date):

    rows = []

    for io, lis in sorted(
        st.session_state.li_data.items(),
        key=lambda x: x[0].lower()
    ):

        for li in sorted(
            lis,
            key=lambda x: x["li_name"].lower()
        ):

            budget = st.session_state.jun_inputs.get(
                li["li_id"],
                li["budget"]
            )

            rows.append({
                "LI ID": li["li_id"],
                "Start Date": start_date.strftime("%Y-%m-%d"),
                "End Date": end_date.strftime("%Y-%m-%d"),
                "Budget": round(float(budget), 2),
                "Daily Budget": 0,
            })

    return pd.DataFrame(rows)

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.title("🚀 Flight Extension Tool")

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

cutoff_date = pd.Timestamp(
    month_start - timedelta(days=1)
)

# ─────────────────────────────────────────────
# FILES
# ─────────────────────────────────────────────

st.header("1. Upload Files")

campaign_files = st.file_uploader(
    "Campaign Setting Files",
    type=["xlsx"],
    accept_multiple_files=True
)

budget_file = st.file_uploader(
    "June Budget File",
    type=["xlsx"]
)

# ─────────────────────────────────────────────
# RUN VALIDATION
# ─────────────────────────────────────────────

if st.button("🚀 Run Validation"):

    li_data = {}

    # campaign files

    if campaign_files:

        for f in campaign_files:

            try:

                xl = pd.ExcelFile(f)

                if "LI-Setting" not in xl.sheet_names:
                    continue

                df = xl.parse("LI-Setting")

                rows = parse_li_sheet(
                    df,
                    cutoff_date
                )

                for r in rows:

                    io = r["io"]

                    if io not in li_data:
                        li_data[io] = []

                    li_data[io].append(r)

                    if r["li_id"] not in st.session_state.jun_inputs:

                        st.session_state.jun_inputs[
                            r["li_id"]
                        ] = r["budget"]

            except Exception as ex:

                st.error(ex)

    st.session_state.li_data = li_data

    # budget file

    if budget_file:

        try:

            dfb = pd.read_excel(
                budget_file
            )

            st.session_state.june_budgets = parse_budget_sheet(
                dfb
            )

        except Exception as ex:

            st.error(ex)

# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

if st.session_state.li_data:

    st.header("2. IOs Requiring Attention")

    mismatch_found = False

    for io, lis in sorted(
        st.session_state.li_data.items(),
        key=lambda x: x[0].lower()
    ):

        expected_total = round(
            st.session_state.june_budgets.get(
                io,
                0
            ),
            2
        )

        current_total = round(
            sum(
                st.session_state.jun_inputs.get(
                    li["li_id"],
                    li["budget"]
                )
                for li in lis
            ),
            2
        )

        diff = round(
            expected_total - current_total,
            2
        )

        approved = st.session_state.approved.get(
            io,
            False
        )

        if approved:
            continue

        if abs(diff) < 0.01:
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

        approve = st.checkbox(
            "This mismatch is intentional",
            key=f"approve_{io}"
        )

        st.session_state.approved[
            io
        ] = approve

        for li in sorted(
            lis,
            key=lambda x: x["li_name"].lower()
        ):

            li_id = li["li_id"]

            c1, c2, c3 = st.columns([5,2,2])

            with c1:
                st.write(li["li_name"])

            with c2:
                st.write(
                    f"€{li['budget']:,.2f}"
                )

            with c3:

                current = st.session_state.jun_inputs.get(
                    li_id,
                    li["budget"]
                )

                val = st.text_input(
                    f"{io}_{li_id}",
                    value=str(current)
                )

                try:

                    st.session_state.jun_inputs[
                        li_id
                    ] = float(val)
                except:
                    pass

        updated_total = round(
            sum(
                st.session_state.jun_inputs.get(
                    li["li_id"],
                    li["budget"]
                )
                for li in lis
            ),
            2
        )

        updated_diff = round(
            expected_total - updated_total,
            2
        )

        if abs(updated_diff) < 0.01:

            st.success(
                "✅ Now Matching"
            )

        else:

            st.warning(
                f"Remaining Difference: €{updated_diff:+,.2f}"
            )

    if not mismatch_found:

        st.success(
            "✅ All IOs are matching correctly"
        )

# ─────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────

if st.session_state.li_data:

    st.header("3. Final Output")

    df_out = build_output(
        month_start,
        month_end
    )

    st.dataframe(
        df_out,
        use_container_width=True,
        hide_index=True
    )

    csv = df_out.to_csv(index=False)

    st.download_button(
        "⬇️ Download CSV",
        csv,
        file_name="flight_extension.csv",
        mime="text/csv"
    )
