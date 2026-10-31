from fastapi import APIRouter, HTTPException

from app.schemas import (
    ScanStartResponse,
    SiteCreateRequest,
    SiteCreateResponse,
    SiteID,
    SiteVerifyResponse,
)

router = APIRouter(prefix="/sites", tags=["Situs"])


@router.post("", response_model=SiteCreateResponse)
def create_site(request: SiteCreateRequest):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")


@router.post("/{site_id}/verify", response_model=SiteVerifyResponse)
def verify_site(site_id: SiteID):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")


@router.post("/{site_id}/scan", response_model=ScanStartResponse)
def start_scan(site_id: SiteID):
    raise HTTPException(status_code=501, detail="Belum diimplementasikan")
