from datetime import datetime, timedelta
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    RootModel,
    model_validator,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def require_wib(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(hours=7):
        raise ValueError("Waktu harus menggunakan zona +07:00")
    return value


WIBDatetime = Annotated[AwareDatetime, AfterValidator(require_wib)]
Score = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, strict=True)]
SiteID = Annotated[str, Field(pattern=r"^ste_[A-Za-z0-9_-]+$")]
ScanID = Annotated[str, Field(pattern=r"^scn_[A-Za-z0-9_-]+$")]
PageID = Annotated[str, Field(pattern=r"^pg_[A-Za-z0-9_-]+$")]
FindingID = Annotated[str, Field(pattern=r"^fnd_[A-Za-z0-9_-]+$")]
Domain = Annotated[
    str,
    Field(
        max_length=253,
        pattern=r"^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$",
    ),
]
QuickCheckStatus = Literal["aman", "terindikasi", "tidak_dapat_diperiksa"]
PageLabel = Literal["aman", "waspada", "terinfeksi", "tidak_dapat_diperiksa"]
ScanStatus = Literal["running", "done", "failed"]
LayerStatus = Literal["ok", "partial", "blocked", "skipped"]
Profile = Literal["browser", "crawler", "search"]
QuickCheckReason = Literal[
    "konten_judi_tersembunyi",
    "konten_berbeda_untuk_mesin_pencari",
    "pengalihan_ke_situs_luar",
    "teks_judi_tersamarkan",
    "tautan_keluar_mencurigakan",
    "situs_memblokir_pemeriksaan",
]
L2Reason = Literal[
    "display_none", "visibility_hidden", "opacity_zero", "offscreen",
    "tiny_text", "same_color", "zero_size", "clipped",
]


class HealthResponse(ContractModel):
    status: Literal["ok"]
    version: Literal["0.1.0"]


class QuickCheckRequest(ContractModel):
    url: HttpUrl


class QuickCheckResponse(ContractModel):
    status: QuickCheckStatus
    reasons: list[QuickCheckReason]
    pages_checked: Count
    checked_at: WIBDatetime
    cached: bool


class SiteCreateRequest(ContractModel):
    domain: Domain


class SiteCreateResponse(ContractModel):
    site_id: SiteID
    domain: Domain
    token: str
    verify_path: str
    verified: bool


class SiteVerifyResponse(ContractModel):
    verified: bool
    verified_at: WIBDatetime | None
    message: str


class ScanStartResponse(ContractModel):
    scan_id: ScanID
    status: Literal["running"]


class ScanSummary(ContractModel):
    pages: Count
    terinfeksi: Count
    waspada: Count
    tidak_dapat_diperiksa: Count


class ScanPage(ContractModel):
    page_id: PageID
    url: HttpUrl
    r_score: Score
    label: PageLabel
    triggers: list[str]
    finding_id: FindingID | None

    @model_validator(mode="after")
    def safe_page_has_no_finding(self):
        if self.label == "aman" and self.finding_id is not None:
            raise ValueError("Halaman aman harus memiliki finding_id null")
        return self


class ScanResponse(ContractModel):
    scan_id: ScanID
    site_alias: str
    status: ScanStatus
    started_at: WIBDatetime
    finished_at: WIBDatetime | None
    summary: ScanSummary
    pages: list[ScanPage]


class L1Evidence(ContractModel):
    profile: Profile
    note: str


class L2Evidence(ContractModel):
    selector: str
    reason: L2Reason
    link_count: Count
    snippet: str


class L3Evidence(ContractModel):
    selector: str
    prob: Score
    top_ngrams: list[str]


class L4Evidence(ContractModel):
    foreign_host_ratio: Score
    note: str


Evidence = TypeVar("Evidence", bound=ContractModel)


class LayerResult(ContractModel, Generic[Evidence]):
    status: LayerStatus
    score: Score
    evidence: list[Evidence]


class FindingLayers(ContractModel):
    L1: LayerResult[L1Evidence]
    L2: LayerResult[L2Evidence]
    L3: LayerResult[L3Evidence]
    L4: LayerResult[L4Evidence]


class FindingResponse(ContractModel):
    finding_id: FindingID
    page_id: PageID
    url: HttpUrl
    label: PageLabel
    r_score: Score
    layers: FindingLayers
    screenshots: dict[Profile, str]
    checked_at: WIBDatetime


class RemediationStep(ContractModel):
    title: str
    detail: str


class RemediationResponse(ContractModel):
    finding_id: FindingID
    cms: str
    steps: list[RemediationStep]
    source: Literal["template", "template+llm"]
    incident_report_draft: str


class AuditEntry(ContractModel):
    id: Annotated[int, Field(ge=1)]
    user: str
    site_alias: str
    action: str
    created_at: WIBDatetime


class AuditLogResponse(RootModel[list[AuditEntry]]):
    pass


class ErrorResponse(ContractModel):
    detail: str
