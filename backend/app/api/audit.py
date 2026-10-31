from fastapi import APIRouter, HTTPException

from app.schemas import AuditLogResponse

router = APIRouter(tags=["Audit"])


@router.get("/audit-log", response_model=AuditLogResponse)
def get_audit_log():
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")
