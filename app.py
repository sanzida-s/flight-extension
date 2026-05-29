def parse_li_sheet(df, filter_end_date: str):
    """
    From LI-Setting dataframe:
    - Find latest Active Flight End Date per IO (<= filter_end_date)
    - Keep ONLY rows from that latest date for that IO
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

    # Build clean records first
    records = []

    for _, row in df.iterrows():

        ed = parse_date_val(row["Active Flight End Date"])

        if not ed:
            continue

        # ignore future dates
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

    # ---------------------------------------------------
    # STEP 1: Find MOST RECENT end date PER IO
    # ---------------------------------------------------

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

    # ---------------------------------------------------
    # STEP 2: Keep ONLY rows matching latest IO date
    # ---------------------------------------------------

    filtered = []

    for r in records:
        if r["end_date"] == latest_io_dates[r["io"]]:
            filtered.append(r)

    # ---------------------------------------------------
    # STEP 3: Deduplicate LI IDs
    # ---------------------------------------------------

    best = {}

    for r in filtered:
        key = (r["io"], r["li_id"])
        best[key] = r

    result = list(best.values())

    result.sort(key=lambda x: (x["io"], x["li_name"]))

    return result, None
