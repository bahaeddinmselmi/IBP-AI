from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pathlib import Path
import pandas as pd
import numpy as np

from ...core.security import require_role, UserContext


router = APIRouter(tags=["data"])


# Use the same base data directory as the feature store so that uploaded
# datasets (e.g. sales.csv) are visible to forecasting. For this file,
# parents[4] points to the repository root (c:\IBP_ai), so data lives in
# c:\IBP_ai\data and uploads in c:\IBP_ai\data\uploads.
DATA_DIR = Path(__file__).resolve().parents[4] / "data"
UPLOAD_DIR = DATA_DIR / "uploads"


def _required_columns(dataset_type: str) -> set[str]:
    mapping: dict[str, set[str]] = {
        # For sales we do not require any specific column names; we rely on
        # heuristic detection in the frontend and schema analysis instead.
        "sales": set(),
        "inventory": {"date", "sku", "location", "stock_level"},
        "production": {"date", "line_id", "sku", "capacity"},
        "purchase_orders": {"po_id", "sku", "supplier", "location", "order_date", "eta_date"},
        "master_data": {"sku", "description", "category", "uom"},
        "external_signals": {"date", "location"},
    }
    return mapping.get(dataset_type, set())


def _analyze_dataframe(df: pd.DataFrame, dataset_type: str) -> tuple[list[dict], list[str]]:
    schema: list[dict] = []
    for col in df.columns:
        series = df[col]
        dtype_str = str(series.dtype)
        role = "categorical"
        if np.issubdtype(series.dtype, np.number):
            role = "numeric"
        if np.issubdtype(series.dtype, "datetime64[ns]") or "date" in col.lower():
            role = "date"
        schema.append({"name": col, "dtype": dtype_str, "role": role})

    warnings: list[str] = []
    required = _required_columns(dataset_type)

    def _norm(name: str) -> str:
        return name.lower().replace(" ", "").replace("_", "")

    col_norms = {_norm(col): col for col in df.columns}

    missing: list[str] = []
    if dataset_type == "sales" and required:
        # For sales we are lenient and accept common aliases for date/quantity
        alias_map: dict[str, set[str]] = {
            "date": {"date", "orderdate", "order_date", "transactiondate", "saledate"},
            "quantity": {"quantity", "qty", "units", "unitssold", "salesqty", "salesunits"},
        }

        for base in required:
            aliases = alias_map.get(base, {base})
            base_missing = True
            for col_key in col_norms.keys():
                if any(alias == col_key or alias in col_key for alias in aliases):
                    base_missing = False
                    break
            if base_missing:
                missing.append(base)
    else:
        for req in required:
            if _norm(req) not in col_norms:
                missing.append(req)

    if missing:
        warnings.append(
            f"Missing expected columns for {dataset_type}: {', '.join(sorted(missing))}"
        )

    return schema, warnings


def _build_dataset_response(
    dataset_type: str,
    df: pd.DataFrame,
    path: Path,
    *,
    limit: int = 20,
) -> JSONResponse:
    head = df.head(limit)
    schema, warnings = _analyze_dataframe(df, dataset_type)
    return JSONResponse(
        {
            "dataset_type": dataset_type,
            "rows": int(len(df)),
            "columns": list(df.columns),
            "preview": head.to_dict(orient="records"),
            "path": str(path),
            "schema": schema,
            "warnings": warnings,
        }
    )


@router.post("/data/upload")
async def upload_dataset(
    dataset_type: str = Form(..., description="sales|inventory|production|purchase_orders|master_data|external_signals"),
    file: UploadFile = File(...),
    user: UserContext = Depends(require_role(["planner", "admin"])),
) -> JSONResponse:
    allowed = {
        "sales",
        "inventory",
        "production",
        "purchase_orders",
        "master_data",
        "external_signals",
    }
    if dataset_type not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid dataset_type",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    original_name = file.filename or ""
    ext = Path(original_name).suffix.lower()
    if ext not in {".csv", ".xlsx", ".xls"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Please upload a CSV or Excel file.",
        )

    content = await file.read()

    if ext in {".xlsx", ".xls"}:
        temp_path = UPLOAD_DIR / f"{dataset_type}{ext}"
        temp_path.write_bytes(content)
        try:
            df = pd.read_excel(temp_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse Excel file: {exc}",
            ) from exc
        target_path = UPLOAD_DIR / f"{dataset_type}.csv"
        df.to_csv(target_path, index=False)
    else:
        target_path = UPLOAD_DIR / f"{dataset_type}.csv"
        target_path.write_bytes(content)
        try:
            df = pd.read_csv(target_path)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV: {exc}",
            ) from exc

    return _build_dataset_response(dataset_type, df, target_path)


@router.get("/data/preview")
async def preview_dataset(
    dataset_type: str,
    limit: int = 20,
    user: UserContext = Depends(require_role(["planner", "admin", "viewer"])),
) -> JSONResponse:
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )

    df = pd.read_csv(path)

    return _build_dataset_response(dataset_type, df, path, limit=limit)
