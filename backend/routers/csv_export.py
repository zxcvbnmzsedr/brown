from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.auth import CurrentUser
from backend.models import Asset, Transaction

router = APIRouter(tags=["export"])

DbSession = Annotated[Session, Depends(get_db)]

CSV_HEADERS = ["date", "asset_name", "asset_code", "type", "qty", "price", "fee", "note"]


@router.get("/export/transactions")
def export_transactions(db: DbSession, current_user: CurrentUser):
    transactions = db.scalars(
        select(Transaction)
        .options(selectinload(Transaction.asset))
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date, Transaction.id)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)
    for tx in transactions:
        writer.writerow([
            tx.date.isoformat(),
            tx.asset.name,
            tx.asset.code or "",
            tx.type,
            tx.qty,
            tx.price,
            tx.fee,
            tx.note or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=brown_transactions.csv"},
    )


@router.post("/import/transactions")
async def import_transactions(db: DbSession, current_user: CurrentUser, file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 CSV 文件")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    assets = db.scalars(select(Asset).where(Asset.user_id == current_user.id)).all()
    assets_by_name = {a.name: a for a in assets}
    assets_by_code = {a.code: a for a in assets if a.code}

    imported = 0
    errors: list[str] = []

    for line_num, row in enumerate(reader, start=2):
        try:
            asset_name = row.get("asset_name", "").strip()
            asset_code = row.get("asset_code", "").strip()

            asset = assets_by_name.get(asset_name) or (assets_by_code.get(asset_code) if asset_code else None)
            if not asset:
                errors.append(f"行 {line_num}: 找不到标的 '{asset_name}'")
                continue

            tx = Transaction(
                user_id=current_user.id,
                date=date.fromisoformat(row["date"]),
                asset_id=asset.id,
                type=row["type"],
                qty=float(row["qty"]),
                price=float(row["price"]),
                fee=float(row.get("fee", 0)),
                note=row.get("note") or None,
            )
            db.add(tx)
            imported += 1
        except (KeyError, ValueError) as e:
            errors.append(f"行 {line_num}: {e}")

    if imported > 0:
        db.commit()

    return {"imported": imported, "errors": errors}
