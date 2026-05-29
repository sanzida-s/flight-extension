# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.li_data and st.session_state.june_budgets:

    st.header("3. IO Budget Comparison")

    correct_ios = []
    mismatch_ios = []

    for io, lis in st.session_state.li_data.items():

        # ONLY latest-date LIs already exist here
        may_total = round(
            sum(x["prev_budget"] for x in lis),
            2,
        )

        june_total = round(
            st.session_state.june_budgets.get(io, 0),
            2,
        )

        diff = round(june_total - may_total, 2)

        # ── MATCHING IO ─────────────────────────────────────────────

        if abs(diff) < 0.01:

            correct_ios.append({
                "io": io,
                "prev_total": may_total,
                "june_total": june_total,
            })

            # keep same LI budgets
            for li in lis:

                st.session_state.jun_inputs[li["li_id"]] = (
                    li["prev_budget"]
                )

        # ── MISMATCH IO ────────────────────────────────────────────

        else:

            mismatch_ios.append({
                "io": io,
                "prev_total": may_total,
                "june_total": june_total,
                "diff": diff,
            })

            # proportional distribution
            apply_proportional(io, june_total)

    # ─────────────────────────────────────────────────────────────
    # SUMMARY CARDS
    # ─────────────────────────────────────────────────────────────

    c1, c2 = st.columns(2)

    with c1:
        st.success(f"✅ Matching IOs: {len(correct_ios)}")

    with c2:
        st.warning(f"⚠️ IOs Needing Changes: {len(mismatch_ios)}")

    # ─────────────────────────────────────────────────────────────
    # MATCHING IOS TABLE
    # ─────────────────────────────────────────────────────────────

    if correct_ios:

        st.subheader("✅ Matching IOs")

        df_correct = pd.DataFrame(correct_ios)

        df_correct.columns = [
            "IO Name",
            "Previous Total",
            "June Budget",
        ]

        st.dataframe(
            df_correct,
            use_container_width=True,
            hide_index=True,
        )

    # ─────────────────────────────────────────────────────────────
    # MISMATCH IOS TABLE + EDITING
    # ─────────────────────────────────────────────────────────────

    if mismatch_ios:

        st.subheader("⚠️ IOs Requiring Budget Changes")

        df_mismatch = pd.DataFrame(mismatch_ios)

        df_mismatch.columns = [
            "IO Name",
            "Previous Total",
            "June Budget",
            "Difference",
        ]

        st.dataframe(
            df_mismatch,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")

        for x in mismatch_ios:

            io = x["io"]

            st.markdown(f"## {io}")

            lis = st.session_state.li_data[io]

            edit_rows = []

            for li in lis:

                li_id = li["li_id"]

                prev_budget = li["prev_budget"]

                current_budget = st.session_state.jun_inputs.get(
                    li_id,
                    prev_budget,
                )

                c1, c2, c3, c4 = st.columns([4, 2, 2, 2])

                with c1:
                    st.write(li["li_name"])

                with c2:
                    st.write(f"€{prev_budget:,.2f}")

                with c3:

                    new_budget = st.number_input(
                        f"{io}_{li_id}",
                        value=float(current_budget),
                        min_value=0.0,
                        step=1.0,
                    )

                    st.session_state.jun_inputs[li_id] = new_budget

                with c4:

                    change = round(
                        new_budget - prev_budget,
                        2,
                    )

                    if abs(change) < 0.01:
                        st.success("MATCH")
                    else:
                        st.warning(f"{change:+,.2f}")

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
