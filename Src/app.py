import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(
    page_title="Hay Day Production Optimizer",
    layout="wide"
)

# ==========================================================
# DATA LOADING
# ==========================================================

@st.cache_data

def load_data():
    BASE_DIR = Path(__file__).resolve().parent

    DATA_FILE = (
        BASE_DIR.parent /
        "Data" /
        "products.xlsx"
    )

    df = pd.read_excel(DATA_FILE)
    return df

df = load_data()

# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def get_set_ingredients(df, player_level):

    ingredients = set()

    for i in range(1, 6):

        col = f"igt{i}"
        df = df[df["level_req"] <= player_level]
        vals = df[col].dropna().unique()

        ingredients.update(vals)

    return sorted(ingredients)


def evaluate_product(row, inventory):

    missing_types = 0
    missing_qty = 0

    missing_list = []

    availability_values = []

    max_possible = []

    for i in range(1, 6):

        ing_col = f"igt{i}"
        qty_col = f"igt{i}_qty"

        ingredient = row.get(ing_col)

        if pd.isna(ingredient):
            continue

        required = row.get(qty_col, 0)

        owned = inventory.get(ingredient, 0)

        availability_values.append(
            min(owned / required, 1)
            if required > 0 else 1
        )

        max_possible.append(
            owned // required
            if required > 0 else 9999
        )

        if owned < required:

            missing_types += 1

            diff = required - owned

            missing_qty += diff

            missing_list.append(
                f"{ingredient} ({diff})"
            )

    availability_score = (
        np.mean(availability_values)
        if availability_values
        else 1
    )

    max_units = (
        min(max_possible)
        if max_possible
        else 0
    )

    overlap = 0
    
    for i in range(1, 6):
    
        ingredient = row.get(f"igt{i}")
    
        if pd.isna(ingredient):
            continue
    
        if inventory.get(ingredient, 0) > 0:
            overlap += 1

    return pd.Series({
        "missing_types": missing_types,
        "missing_qty": missing_qty,
        "missing_ingredients": ", ".join(missing_list),
        "availability_score": round(availability_score, 3),
        "max_units": max_units,
        "ingredient_overlap": overlap
    })


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.title("Player Settings")

player_level = st.sidebar.number_input(
    "Player Level",
    min_value=1,
    max_value=200,
    value=40
)

available_hours = st.sidebar.number_input(
    "Available Production Time (hours)",
    min_value=1,
    max_value=24,
    value=8
)

available_minutes = available_hours * 60

# ==========================================================
# INVENTORY INPUT
# ==========================================================

st.title("Hay Day Production Optimizer")

st.subheader("Barn Inventory")

ingredients = get_set_ingredients(df, player_level)

inventory_df = pd.DataFrame({
    "ingredient": ingredients,
    "quantity": 0
})

inventory_input = st.data_editor(
    inventory_df,
    use_container_width=True,
    num_rows="fixed"
)

inventory = dict(
    zip(
        inventory_input["ingredient"],
        inventory_input["quantity"]
    )
)

# ==========================================================
# CALCULATE
# ==========================================================

if st.button("Recommend Products"):

    eligible = df[
        df["level_req"] <= player_level
    ].copy()

    metrics = eligible.apply(
        lambda row: evaluate_product(
            row,
            inventory
        ),
        axis=1
    )

    eligible = pd.concat(
        [eligible, metrics],
        axis=1
    )

    # --------------------------------------------
    # Cycles in selected time
    # --------------------------------------------

    eligible["cycles"] = (
        available_minutes //
        eligible["time_min"]
    )

    eligible["possible_profit"] = (
        eligible["stack_profit"] *
        eligible["max_units"]
    )

    eligible["overnight_idle"] = (
        available_minutes %
        eligible["time_min"]
    )

    eligible["recommendation_score"] = (
        eligible["stack_profit_hr"] * 0.5
        + eligible["availability_score"] * 100
        - eligible["missing_types"] * 20
        - eligible["missing_qty"] * 2
    )

    eligible = eligible[
    eligible["ingredient_overlap"] > 0
    ]

    # ======================================================
    # TABS
    # ======================================================

    tab1, tab2, tab3, tab4 = st.tabs([
        "Ready",
        "Almost Ready",
        "Best Profit",
        "Overnight"
    ])

    # ======================================================
    # READY
    # ======================================================

    with tab1:

        ready = eligible[
            eligible["missing_types"] == 0
        ].sort_values(
            "stack_profit_hr",
            ascending=False
        ).head(5)

        ready["xp"] = ready["xp"].astype(int) * ready["max_units"]
        ready["time_min"] = ready["time_min"] * ready["max_units"]
        ready["time_hours"] = ready["time_min"] / 60
        ready["total_profit"] = (ready["stack_profit"])/10 * ready["max_units"]

        st.subheader("Ready To Produce")

        st.dataframe(
            ready[
                [
                    "name",
                    "source",
                    "stack_profit",
                    "stack_profit_hr",
                    "xp",
                    "time_min",
                    "time_hours",
                    "total_profit",
                    "max_units"
                ]
            ],
            use_container_width=True
        )

    # ======================================================
    # ALMOST READY
    # ======================================================

    with tab2:

        almost = eligible[
            eligible["missing_types"] <= 2
        ].sort_values(
            [
                "missing_types",
                "missing_qty",
                "stack_profit_hr"
            ],
            ascending=[
                True,
                True,
                False
            ]
        ).head(5)

        st.subheader("Almost Ready")

        st.dataframe(
            almost[
                [
                    "name",
                    "missing_ingredients",
                    "missing_types",
                    "missing_qty",
                    "stack_profit_hr",
                    "availability_score"
                ]
            ],
            use_container_width=True
        )

    # ======================================================
    # PROFIT
    # ======================================================

    with tab3:

        profit = eligible.sort_values(
            "recommendation_score",
            ascending=False
        ).head(5)

        st.subheader("Best Overall Recommendations")

        st.dataframe(
            profit[
                [
                    "name",
                    "source",
                    "stack_profit",
                    "stack_profit_hr",
                    "availability_score",
                    "missing_types",
                    "missing_qty",
                    "recommendation_score"
                ]
            ],
            use_container_width=True
        )

    # ======================================================
    # OVERNIGHT
    # ======================================================

    with tab4:

        overnight = eligible.copy()

        overnight["overnight_score"] = (
            overnight["stack_profit_hr"]
            - overnight["overnight_idle"] * 0.5
        )

        overnight = overnight.sort_values(
            "overnight_score",
            ascending=False
        ).head(5)

        st.subheader(
            f"Best Products For {available_hours} Hours"
        )
        st.warning(
            "Note: This is a simplified calculation and may not account for all factors. For example, number of slots in your machine may vary."
        )

        st.dataframe(
            overnight[
                [
                    "name",
                    "source",
                    "time_min",
                    "overnight_idle",
                    "stack_profit_hr",
                    "overnight_score"
                ]
            ],
            use_container_width=True
        )