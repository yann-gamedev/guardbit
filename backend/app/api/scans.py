from fastapi import APIRouter, HTTPException

from app.schemas import ScanID, ScanResponse

router = APIRouter(prefix="/scans", tags=["Pemindaian"])


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: ScanID):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")
