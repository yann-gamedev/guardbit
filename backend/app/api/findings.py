from fastapi import APIRouter, HTTPException

from app.schemas import FindingID, FindingResponse, RemediationResponse

router = APIRouter(prefix="/findings", tags=["Temuan"])


@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(finding_id: FindingID):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")


@router.post("/{finding_id}/remediation", response_model=RemediationResponse)
def get_remediation(finding_id: FindingID):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")
