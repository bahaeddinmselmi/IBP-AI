from __future__ import annotations

from typing import List, Dict, Any

import logging
from string import Template

import requests

from ..core.config import get_settings
from ..models.copilot import CopilotContext, CopilotQueryRequest, CopilotQueryResponse
from ..services.store import store
from ..api.v1.routes_data import DATA_DIR, UPLOAD_DIR  # reuse dataset locations
import pandas as pd


class CopilotService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _summarize_forecast(self, forecast_id: str | None) -> str:
        if not store.forecasts:
            return "No forecasts are available in the current session."

        if forecast_id is not None and forecast_id in store.forecasts:
            forecast = store.forecasts[forecast_id]
        else:
            # take latest created
            _, forecast = next(reversed(store.forecasts.items()))

        totals: dict[str, float] = {}
        for p in forecast.points:
            totals[p.sku] = totals.get(p.sku, 0.0) + p.mean

        parts: List[str] = []
        parts.append(
            f"Forecast {forecast.forecast_id} uses model {forecast.metadata.model_name} "
            f"v{forecast.metadata.model_version}."
        )
        ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
        if ranked:
            top_lines = [f"{sku} (~{total:.1f} units)" for sku, total in ranked[:5]]
            parts.append("Top SKUs by volume: " + ", ".join(top_lines) + ".")

        if forecast.metadata.per_sku_model:
            model_counts: dict[str, int] = {}
            for model in forecast.metadata.per_sku_model.values():
                model_counts[model] = model_counts.get(model, 0) + 1
            summary = ", ".join(f"{m}: {c} SKUs" for m, c in model_counts.items())
            parts.append("Per-SKU model selection: " + summary + ".")

        return " ".join(parts)

    def _summarize_plan(self, plan_id: str | None) -> str:
        if not store.plans:
            return "No plans are available in the current session."

        if plan_id is not None and plan_id in store.plans:
            plan = store.plans[plan_id]
        else:
            _, plan = next(reversed(store.plans.items()))

        parts: List[str] = []
        parts.append(f"Plan {plan.plan_id} is linked to forecast {plan.forecast_id}.")
        if plan.kpis:
            kpi_lines = [f"{k.name}: {k.value:.2f} {k.unit or ''}" for k in plan.kpis[:6]]
            parts.append("Key KPIs: " + "; ".join(kpi_lines) + ".")

        return " ".join(parts)

    def _summarize_scenarios(self, scenario_id: str | None) -> str:
        if not store.scenarios:
            return "No scenarios have been created yet."

        if scenario_id is not None and scenario_id in store.scenarios:
            scenario = store.scenarios[scenario_id]
            parts: List[str] = []
            name = scenario.name or "Scenario"
            parts.append(
                f"Selected scenario {name} ({scenario.scenario_id}) for forecast {scenario.forecast_id}."
            )
            if getattr(scenario, "narrative", None):
                parts.append(str(scenario.narrative))
            elif scenario.kpis:
                top = scenario.kpis[0]
                parts.append(
                    f"Primary KPI {top.name}: base={top.base:.1f}, scenario={top.scenario:.1f}, "
                    f"delta={top.delta:.1f}."
                )
            return " ".join(parts)

        # otherwise provide a brief list overview
        parts = [f"There are {len(store.scenarios)} scenarios in the current session."]
        examples: List[str] = []
        for scenario in list(store.scenarios.values())[:5]:
            label = scenario.name or "Scenario"
            examples.append(f"{label} ({scenario.scenario_id[:8]}...) for forecast {scenario.forecast_id}")
        if examples:
            parts.append("Examples: " + "; ".join(examples) + ".")
        return " ".join(parts)

    def _summarize_dataset(self, dataset_type: str | None) -> str:
        if dataset_type is None:
            return "No dataset type specified. Choose one of sales, inventory, production, purchase_orders, master_data, external_signals."

        sample_map = {
            "sales": DATA_DIR / "sample_sales.csv",
            "inventory": DATA_DIR / "sample_inventory.csv",
            "production": DATA_DIR / "sample_production.csv",
            "purchase_orders": DATA_DIR / "sample_purchase_orders.csv",
            "master_data": DATA_DIR / "sample_master_data.csv",
            "external_signals": DATA_DIR / "sample_external_signals.csv",
        }

        upload_path = UPLOAD_DIR / f"{dataset_type}.csv"
        if upload_path.exists():
            path = upload_path
        else:
            path = sample_map.get(dataset_type)

        if path is None or not path.exists():
            return f"Dataset {dataset_type} is not available."

        df = pd.read_csv(path)
        cols = list(df.columns)
        parts: List[str] = []

        n_rows = len(df)
        n_cols = len(cols)
        preview_cols = cols[:6]
        extra = n_cols - len(preview_cols)
        col_text = ", ".join(preview_cols)
        if extra > 0:
            col_text += f" (+{extra} more columns)"

        parts.append(
            f"Dataset {dataset_type} currently loaded from {path.name} has {n_rows} rows and {n_cols} columns. "
            f"Example columns: {col_text}."
        )
        if "sku" in df.columns:
            parts.append(f"Distinct SKUs: {df['sku'].nunique()}.")
        if "location" in df.columns:
            parts.append(f"Distinct locations: {df['location'].nunique()}.")
        if "date" in df.columns:
            try:
                dt = pd.to_datetime(df["date"])
                parts.append(
                    f"Date coverage: {dt.min().date()} to {dt.max().date()}."
                )
            except Exception:
                pass

        return " ".join(parts)

    def answer_query(self, request: CopilotQueryRequest) -> CopilotQueryResponse:
        # For now we implement a deterministic summariser that inspects the in-memory
        # context instead of calling an external LLaMA server.
        # The request structure is designed so a future LLaMA integration can turn
        # these summaries into richer natural-language answers.
        pieces: List[str] = []
        actions: List[str] = []

        query_text = (request.query or "").strip()
        lower_q = query_text.lower()

        is_greeting = (
            lower_q in {"hi", "hello", "hey"}
            or lower_q.startswith("hi ")
            or lower_q.startswith("hello ")
            or lower_q.startswith("hey ")
        )
        is_capability_question = (
            "what can you do" in lower_q
            or "what u can do" in lower_q
            or ("help" in lower_q and "can you" in lower_q)
        )

        if is_greeting or is_capability_question:
            capability_lines: List[str] = [
                "- Summarise the latest forecast and highlight top risk SKUs.",
                "- Explain your current supply plan KPIs and key trade-offs.",
                "- Describe scenarios (upside / downside) versus the base plan.",
                "- Inspect the uploaded Sales dataset and point out its structure.",
            ]
            session_bits: List[str] = []
            if store.forecasts:
                session_bits.append(f"{len(store.forecasts)} forecast(s)")
            if store.plans:
                session_bits.append(f"{len(store.plans)} plan(s)")
            if store.scenarios:
                session_bits.append(f"{len(store.scenarios)} scenario(s)")
            if request.dataset_type:
                session_bits.append(f"dataset '{request.dataset_type}'")

            context_line = ""
            if session_bits:
                context_line = "Right now I can see " + ", ".join(session_bits) + " in this session."

            greeting = "Hi! I'm your IBP AI copilot."
            if query_text and not is_capability_question and not is_greeting:
                greeting = f"You asked: '{query_text}'. I am your IBP AI copilot."

            answer = greeting + "\n" + "\n".join(capability_lines)
            if context_line:
                answer += "\n\n" + context_line

            greeting_actions: List[str] = [
                "Ask me to summarise the latest forecast and highlight risk SKUs.",
                "Ask me to explain your current plan KPIs.",
                "Ask me to compare a scenario against the base plan.",
                "Ask me to review the Sales dataset for basic data quality issues.",
            ]

            used_context = {
                "has_forecast": bool(store.forecasts),
                "has_plan": bool(store.plans),
                "scenario_count": len(store.scenarios),
                "dataset_type": request.dataset_type,
            }

            return CopilotQueryResponse(
                answer=answer,
                suggested_actions=greeting_actions,
                used_context=used_context,
            )

        # Base actions driven by selected contexts
        if CopilotContext.forecast in request.contexts:
            pieces.append("• Forecast: " + self._summarize_forecast(request.forecast_id))
            actions.append("Review top risk SKUs and consider running a scenario on the Control tower.")

        if CopilotContext.plan in request.contexts:
            pieces.append("• Plan: " + self._summarize_plan(request.plan_id))
            actions.append("Check whether plan KPIs meet your service and inventory targets.")

        if CopilotContext.scenario in request.contexts:
            pieces.append("• Scenarios: " + self._summarize_scenarios(request.scenario_id))
            actions.append("Open Scenario Lab to compare scenarios side by side.")

        if CopilotContext.data in request.contexts:
            pieces.append("• Data: " + self._summarize_dataset(request.dataset_type))
            actions.append("Use the Data import tab to adjust or validate source data.")

        # Light query understanding to tailor guidance
        if "risk" in lower_q or "downside" in lower_q:
            actions.append(
                "Focus on the highest-volume or most volatile SKUs and stress-test them with downside scenarios."
            )
        if "inventory" in lower_q or "stock" in lower_q:
            actions.append(
                "Compare forecast demand with inventory KPIs and adjust safety stock or reorder rules where needed."
            )
        if "scenario" in lower_q or "what if" in lower_q:
            actions.append(
                "Create at least one upside and one downside scenario in Scenario Lab to frame the planning range."
            )
        if any(word in lower_q for word in ["data", "file", "csv", "dataset"]):
            actions.append(
                "Inspect the uploaded dataset on the Data import tab and fix missing or unexpected columns before trusting results."
            )

        # Deduplicate actions while preserving order
        unique_actions: List[str] = []
        seen: set[str] = set()
        for a in actions:
            if a not in seen:
                unique_actions.append(a)
                seen.add(a)

        intro_parts: List[str] = []
        if query_text:
            intro_parts.append(f"You asked: '{query_text}'.")
        intro_parts.append("Here is a quick summary of the current planning context:")

        if pieces:
            summary_text = " ".join(intro_parts) + "\n" + "\n".join(pieces)
        else:
            summary_text = " ".join(intro_parts)

        answer = summary_text
        used_context = {
            "has_forecast": bool(store.forecasts),
            "has_plan": bool(store.plans),
            "scenario_count": len(store.scenarios),
            "dataset_type": request.dataset_type,
        }

        if self.settings.groq_api_key:
            try:
                answer = self._call_groq_model(
                    query_text=query_text,
                    summary=summary_text,
                    contexts=request.contexts,
                )
            except Exception as exc:  # pragma: no cover - logging fallback path
                logging.getLogger(__name__).warning("Groq call failed: %s", exc)

        return CopilotQueryResponse(
            answer=answer,
            suggested_actions=unique_actions,
            used_context=used_context,
        )

    def _call_groq_model(
        self,
        query_text: str,
        summary: str,
        contexts: List[CopilotContext],
    ) -> str:
        system_template = Template(
            "\n".join(
                [
                    "You are the SAP IBP copilot.",
                    "Use the following planning context to answer user questions professionally.",
                    "Context summary:\n${summary}",
                ]
            )
        )

        system_prompt = system_template.substitute(summary=summary or "No context available.")

        payload: Dict[str, Any] = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query_text or "Provide a concise status update."},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return summary

        message = choices[0].get("message", {})
        return message.get("content") or summary
