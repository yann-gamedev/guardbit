from fastapi import APIRouter, HTTPException

from app.schemas import QuickCheckRequest, QuickCheckResponse

router = APIRouter(tags=["Cek Cepat"])


@router.post("/quick-check", response_model=QuickCheckResponse)
def quick_check(request: QuickCheckRequest):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")
