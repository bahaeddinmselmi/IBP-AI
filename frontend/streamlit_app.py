import datetime as dt
from typing import List

import pandas as pd
import requests
import streamlit as st


API_BASE_URL_DEFAULT = "http://localhost:8000"
API_KEY_DEFAULT = "dev-api-key-change-me"


def call_api(method: str, path: str, json: dict | None = None):
    base_url = st.session_state.get("api_base_url", API_BASE_URL_DEFAULT)
    api_key = st.session_state.get("api_key", API_KEY_DEFAULT)

    headers = {"X-API-Key": api_key}

    url = base_url.rstrip("/") + path
    response = requests.request(method, url, headers=headers, json=json, timeout=30)

    if not response.ok:
        raise RuntimeError(f"API error {response.status_code}: {response.text}")

    return response.json()


def page_sidebar():
    st.sidebar.header("IBP API Settings")
    api_base = st.sidebar.text_input("API base URL", value=API_BASE_URL_DEFAULT)
    api_key = st.sidebar.text_input("API key", value=API_KEY_DEFAULT, type="password")

    st.session_state["api_base_url"] = api_base
    st.session_state["api_key"] = api_key


def page_control_tower():
    st.title("IBP Control Tower")

    st.write("Generate a forecast and plan, then analyze KPIs and scenarios.")

    cols = st.columns(2)

    with cols[0]:
        sku_input = st.text_input("SKUs (comma-separated)", value="SKU-001,SKU-002,SKU-003")
        start_date = st.date_input("Start date", value=dt.date(2025, 1, 1))
        end_date = st.date_input("End date", value=dt.date(2025, 1, 30))
        granularity = st.selectbox("Granularity", options=["D", "W", "M"], index=0)
        location = st.text_input("Location (optional)", value="WH-1")

        if st.button("Generate Forecast"):
            sku_list: List[str] = [s.strip() for s in sku_input.split(",") if s.strip()]
            payload = {
                "sku_list": sku_list,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "granularity": granularity,
                "location": location or None,
            }
            try:
                data = call_api("POST", "/api/v1/forecast", json=payload)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["forecast"] = data
                st.session_state["forecast_id"] = data["forecast_id"]
                st.success(f"Created forecast {data['forecast_id']}")

    with cols[1]:
        if "forecast_id" in st.session_state:
            st.markdown("### Plan generation")
            objective = st.selectbox("Objective", ["service_level", "margin", "cost"], index=0)
            target_service_level = st.slider("Target service level", 0.5, 0.999, 0.95)
            lead_time_days = st.number_input("Lead time (days)", min_value=1, max_value=90, value=10)

            if st.button("Generate Plan", disabled="forecast_id" not in st.session_state):
                payload = {
                    "forecast_id": st.session_state["forecast_id"],
                    "objective": objective,
                    "constraints": {
                        "target_service_level": target_service_level,
                        "max_days_of_cover": 90,
                        "min_days_of_cover": 0,
                        "lead_time_days": lead_time_days,
                    },
                    "location": location or None,
                }
                try:
                    data = call_api("POST", "/api/v1/plan/generate", json=payload)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.session_state["plan"] = data
                    st.session_state["plan_id"] = data["plan_id"]
                    st.success(f"Created plan {data['plan_id']}")
        else:
            st.info("Generate a forecast first.")

    st.markdown("---")

    if "forecast" in st.session_state:
        st.subheader("Forecast vs time")
        points = st.session_state["forecast"]["points"]
        df = pd.DataFrame(points)
        df["date"] = pd.to_datetime(df["date"])
        st.line_chart(
            df.pivot_table(index="date", columns="sku", values="mean"),
        )

        st.subheader("Top risk SKUs (by total volume)")
        top = (
            df.groupby("sku")["mean"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
            .rename(columns={"mean": "total_forecast"})
        )
        st.table(top.head(5))

    if "plan" in st.session_state:
        st.subheader("Plan KPIs")
        kpis = pd.DataFrame(st.session_state["plan"]["kpis"])
        st.table(kpis)

    if "forecast_id" in st.session_state:
        st.markdown("---")
        st.subheader("Explainability")
        if st.button("Fetch forecast explanation"):
            try:
                data = call_api("GET", f"/api/v1/explain/{st.session_state['forecast_id']}")
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["explain"] = data

        if "explain" in st.session_state:
            explain = st.session_state["explain"]
            global_imp = pd.DataFrame(explain["global_importance"])
            st.bar_chart(global_imp.set_index("feature")["importance"])

    if "plan_id" in st.session_state:
        st.markdown("---")
        st.subheader("Scenario simulation")
        demand_factor = st.slider("Demand factor", 0.5, 2.0, 1.2, step=0.05)
        start_date_scn = st.date_input("Scenario start", value=dt.date(2025, 1, 1), key="scn_start")
        end_date_scn = st.date_input("Scenario end", value=dt.date(2025, 1, 30), key="scn_end")

        if st.button("Run scenario"):
            payload = {
                "forecast_id": st.session_state["forecast_id"],
                "plan_id": st.session_state["plan_id"],
                "name": f"Demand x{demand_factor:.2f}",
                "shocks": [
                    {
                        "type": "demand",
                        "sku": None,
                        "location": None,
                        "start_date": start_date_scn.isoformat(),
                        "end_date": end_date_scn.isoformat(),
                        "factor": demand_factor,
                        "delta": 0.0,
                    }
                ],
            }
            try:
                data = call_api("POST", "/api/v1/scenario", json=payload)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.session_state["scenario"] = data

        if "scenario" in st.session_state:
            kpis = pd.DataFrame(st.session_state["scenario"]["kpis"])
            kpis["delta_percent"] = 100.0 * kpis["delta"] / kpis["base"].replace({0: None})
            st.table(kpis)


def main():
    page_sidebar()
    page_control_tower()


if __name__ == "__main__":
    main()
