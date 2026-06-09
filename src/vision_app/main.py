import json
import os
from datetime import datetime, timezone
from enum import Enum
from http import HTTPStatus
from typing import Any, Dict, List, Literal, Optional

import psycopg
import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, ConfigDict, Field, model_validator


SERVICE_NAME = os.getenv("SERVICE_NAME", "ai-vision")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")
USE_DATABASE = os.getenv("USE_DATABASE", "false").lower() in {"1", "true", "yes", "on"}
USE_MODEL_SERVICE = os.getenv("USE_MODEL_SERVICE", "false").lower() in {"1", "true", "yes", "on"}
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "vision")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "visionpass")
POSTGRES_DB = os.getenv("POSTGRES_DB", "visiondb")
MODEL_SERVICE_URL = os.getenv("MODEL_SERVICE_URL", "http://localhost:9000").rstrip("/")
MODEL_VERSION = os.getenv("MODEL_VERSION", "yolov11n-hospital-2.3.1")


app = FastAPI(
    title="FIT4110 Lab 05 - AI Vision Detection Service",
    version=SERVICE_VERSION,
    description=(
        "AI Vision API for Camera Stream detection requests. "
        "The service stores detection metadata in PostgreSQL and calls an "
        "internal model service through Docker Compose."
    ),
)


class DetectionStatus(str, Enum):
    processing = "PROCESSING"
    completed = "COMPLETED"
    failed = "FAILED"


class RiskLevel(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"
    critical = "CRITICAL"


class BoundingBox(BaseModel):
    x: float = Field(..., ge=0, le=1)
    y: float = Field(..., ge=0, le=1)
    width: float = Field(..., ge=0, le=1)
    height: float = Field(..., ge=0, le=1)


class DetectedObject(BaseModel):
    objectType: str
    label: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    trackId: Optional[str] = None
    boundingBox: BoundingBox


class ImageSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sourceType: Literal["IMAGE_URL", "OBJECT_STORAGE_REF"]
    url: Optional[str] = None
    bucket: Optional[str] = None
    objectKey: Optional[str] = None
    expiresAt: Optional[str] = None

    @model_validator(mode="after")
    def validate_source_fields(self) -> "ImageSource":
        if self.sourceType == "IMAGE_URL" and not self.url:
            raise ValueError("imageSource.url is required for IMAGE_URL")

        if self.sourceType == "OBJECT_STORAGE_REF":
            missing = [
                field
                for field in ("bucket", "objectKey", "expiresAt")
                if getattr(self, field) is None
            ]
            if missing:
                raise ValueError(
                    "imageSource requires "
                    + ", ".join(missing)
                    + " for OBJECT_STORAGE_REF"
                )

        return self


class DetectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requestId: str = Field(..., pattern=r"^REQ-[A-Z0-9-]+$")
    cameraId: str = Field(..., pattern=r"^CAM-[A-Z0-9-]+$")
    capturedAt: str
    traceId: str = Field(..., pattern=r"^TRACE-[A-Z0-9-]+$")
    zoneId: Optional[str] = Field(default=None, min_length=2, max_length=80)
    motionLevel: Optional[float] = Field(default=None, ge=0, le=1)
    notes: Optional[str] = Field(default=None, min_length=1, max_length=300)
    imageSource: ImageSource


DETECTIONS: List[Dict[str, Any]] = []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def reason_phrase(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "HTTP Error"


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "https://hospital-campus.local/errors/request-failed",
    errors: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    return {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "errors": errors or [],
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=reason_phrase(exc.status_code),
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", reason_phrase(exc.status_code))
    problem.setdefault("type", "https://hospital-campus.local/errors/request-failed")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))
    problem.setdefault("errors", [])

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    validation_errors = []
    for error in exc.errors():
        field = ".".join(str(item) for item in error.get("loc", []) if item != "body")
        validation_errors.append(
            {
                "field": field or "body",
                "code": error.get("type", "VALIDATION_ERROR"),
                "message": error.get("msg", "Invalid request body"),
            }
        )

    detail = validation_errors[0]["message"] if validation_errors else "Invalid request body"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Invalid request body",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://hospital-campus.local/errors/validation",
            errors=validation_errors,
        ),
        media_type="application/problem+json",
    )


def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Authentication required",
                detail="Bearer token is missing",
                problem_type="https://hospital-campus.local/errors/unauthorized",
            ),
        )

    if authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Authentication required",
                detail="Bearer token is invalid",
                problem_type="https://hospital-campus.local/errors/unauthorized",
            ),
        )


def get_db_connection() -> psycopg.Connection:
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        row_factory=dict_row,
    )


def init_db() -> None:
    if not USE_DATABASE:
        return

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS vision_detections (
                    detection_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    trace_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    zone_id TEXT,
                    motion_level DOUBLE PRECISION,
                    image_source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    risk_level TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    summary TEXT,
                    alert_hint TEXT,
                    thumbnail_url TEXT,
                    objects TEXT NOT NULL,
                    accepted_at TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )


@app.on_event("startup")
def startup_event() -> None:
    init_db()


def next_detection_id(conn: Optional[psycopg.Connection] = None) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"DET-{today}-"

    if USE_DATABASE and conn is not None:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total FROM vision_detections WHERE detection_id LIKE %s",
                (f"{prefix}%",),
            )
            row = cur.fetchone()
        total = int(row["total"]) if row else 0
    else:
        total = len([item for item in DETECTIONS if item["detectionId"].startswith(prefix)])

    return f"{prefix}{total + 1:04d}"


def run_model_inference(payload: DetectionRequest) -> Dict[str, Any]:
    if not USE_MODEL_SERVICE:
        return fallback_prediction(payload)

    try:
        response = requests.post(
            f"{MODEL_SERVICE_URL}/predict",
            json=payload.model_dump(),
            timeout=3,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=build_problem(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                title="Service temporarily unavailable",
                detail=f"Detection backend is unavailable at {MODEL_SERVICE_URL}: {exc}",
                problem_type="https://hospital-campus.local/errors/service-unavailable",
            ),
        ) from exc


def fallback_prediction(payload: DetectionRequest) -> Dict[str, Any]:
    confidence = max(payload.motionLevel or 0.72, 0.72)
    risk_level = "HIGH" if confidence >= 0.85 else "MEDIUM"
    return {
        "status": "COMPLETED",
        "confidence": round(confidence, 2),
        "riskLevel": risk_level,
        "modelVersion": MODEL_VERSION,
        "summary": "Person detected in monitored camera frame",
        "alertHint": "REVIEW_SECURITY" if risk_level == "HIGH" else "MONITOR",
        "thumbnailUrl": "https://media.hospital.local/thumbnails/mock-detection.jpg",
        "objects": [
            {
                "objectType": "PERSON",
                "label": "human",
                "confidence": round(confidence, 2),
                "trackId": "TRACK-77",
                "boundingBox": {"x": 0.12, "y": 0.08, "width": 0.41, "height": 0.82},
            }
        ],
    }


def build_detection_record(
    *,
    detection_id: str,
    payload: DetectionRequest,
    prediction: Dict[str, Any],
    accepted_at: str,
) -> Dict[str, Any]:
    processed_at = now_iso()
    status_value = prediction.get("status", DetectionStatus.completed.value)

    return {
        "detectionId": detection_id,
        "requestId": payload.requestId,
        "traceId": payload.traceId,
        "cameraId": payload.cameraId,
        "capturedAt": payload.capturedAt,
        "zoneId": payload.zoneId,
        "motionLevel": payload.motionLevel,
        "imageSource": payload.imageSource.model_dump(exclude_none=True),
        "status": status_value,
        "confidence": prediction.get("confidence", 0.0),
        "riskLevel": prediction.get("riskLevel", RiskLevel.medium.value),
        "modelVersion": prediction.get("modelVersion", MODEL_VERSION),
        "summary": prediction.get("summary"),
        "alertHint": prediction.get("alertHint"),
        "processedAt": processed_at,
        "completedAt": processed_at if status_value == DetectionStatus.completed.value else None,
        "thumbnailUrl": prediction.get("thumbnailUrl"),
        "objects": prediction.get("objects", []),
        "acceptedAt": accepted_at,
    }


def snapshot_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": record["status"],
        "confidence": record["confidence"],
        "riskLevel": record["riskLevel"],
        "modelVersion": record["modelVersion"],
        "summary": record["summary"],
        "alertHint": record["alertHint"],
        "completedAt": record["completedAt"],
        "thumbnailUrl": record["thumbnailUrl"],
        "objects": record["objects"],
    }


def result_from_record(record: Dict[str, Any]) -> Dict[str, Any]:
    result = snapshot_from_record(record)
    result.update(
        {
            "detectionId": record["detectionId"],
            "requestId": record["requestId"],
            "traceId": record["traceId"],
            "processedAt": record["processedAt"],
        }
    )
    return result


def db_row_to_record(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "detectionId": row["detection_id"],
        "requestId": row["request_id"],
        "traceId": row["trace_id"],
        "cameraId": row["camera_id"],
        "capturedAt": row["captured_at"],
        "zoneId": row["zone_id"],
        "motionLevel": row["motion_level"],
        "imageSource": json.loads(row["image_source"]),
        "status": row["status"],
        "confidence": row["confidence"],
        "riskLevel": row["risk_level"],
        "modelVersion": row["model_version"],
        "summary": row["summary"],
        "alertHint": row["alert_hint"],
        "thumbnailUrl": row["thumbnail_url"],
        "objects": json.loads(row["objects"]),
        "acceptedAt": row["accepted_at"],
        "processedAt": row["processed_at"],
        "completedAt": row["completed_at"],
    }


def insert_detection(conn: psycopg.Connection, record: Dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO vision_detections (
                detection_id,
                request_id,
                trace_id,
                camera_id,
                captured_at,
                zone_id,
                motion_level,
                image_source,
                status,
                confidence,
                risk_level,
                model_version,
                summary,
                alert_hint,
                thumbnail_url,
                objects,
                accepted_at,
                processed_at,
                completed_at
            )
            VALUES (
                %(detectionId)s,
                %(requestId)s,
                %(traceId)s,
                %(cameraId)s,
                %(capturedAt)s,
                %(zoneId)s,
                %(motionLevel)s,
                %(imageSourceJson)s,
                %(status)s,
                %(confidence)s,
                %(riskLevel)s,
                %(modelVersion)s,
                %(summary)s,
                %(alertHint)s,
                %(thumbnailUrl)s,
                %(objectsJson)s,
                %(acceptedAt)s,
                %(processedAt)s,
                %(completedAt)s
            )
            """,
            {
                **record,
                "imageSourceJson": json.dumps(record["imageSource"]),
                "objectsJson": json.dumps(record["objects"]),
            },
        )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "time": now_iso()}


@app.post(
    "/vision/detect",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_bearer_token)],
)
def create_detection(
    payload: DetectionRequest,
    x_correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-Id"),
) -> Dict[str, Any]:
    accepted_at = now_iso()
    prediction = run_model_inference(payload)

    if USE_DATABASE:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM vision_detections WHERE request_id = %s",
                    (payload.requestId,),
                )
                existing = cur.fetchone()

            if existing:
                record = db_row_to_record(existing)
            else:
                detection_id = next_detection_id(conn)
                record = build_detection_record(
                    detection_id=detection_id,
                    payload=payload,
                    prediction=prediction,
                    accepted_at=accepted_at,
                )
                insert_detection(conn, record)
    else:
        existing = next(
            (item for item in DETECTIONS if item["requestId"] == payload.requestId),
            None,
        )
        if existing:
            record = existing
        else:
            record = build_detection_record(
                detection_id=next_detection_id(),
                payload=payload,
                prediction=prediction,
                accepted_at=accepted_at,
            )
            DETECTIONS.append(record)

    return {
        "detectionId": record["detectionId"],
        "requestId": record["requestId"],
        "traceId": x_correlation_id or record["traceId"],
        "status": "PROCESSING",
        "acceptedAt": record["acceptedAt"],
        "preliminaryResult": snapshot_from_record(record),
    }


@app.get(
    "/vision/detections/{detection_id}",
    dependencies=[Depends(verify_bearer_token)],
)
def get_detection(
    detection_id: str,
    x_correlation_id: Optional[str] = Header(default=None, alias="X-Correlation-Id"),
) -> Dict[str, Any]:
    if USE_DATABASE:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM vision_detections WHERE detection_id = %s",
                    (detection_id,),
                )
                row = cur.fetchone()

        record = db_row_to_record(row) if row else None
    else:
        record = next(
            (item for item in DETECTIONS if item["detectionId"] == detection_id),
            None,
        )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Detection not found",
                detail=f"detectionId {detection_id} does not exist",
                instance=f"/vision/detections/{detection_id}",
                problem_type="https://hospital-campus.local/errors/not-found",
            ),
        )

    result = result_from_record(record)
    if x_correlation_id:
        result["traceId"] = x_correlation_id
    return result


@app.get("/vision/models/info", dependencies=[Depends(verify_bearer_token)])
def get_model_info() -> Dict[str, Any]:
    return {
        "modelName": "yolo-hospital-monitor",
        "modelVersion": MODEL_VERSION,
        "supportedObjectTypes": [
            "PERSON",
            "WHEELCHAIR",
            "STRETCHER",
            "SMOKE",
            "FIRE_EXTINGUISHER",
            "UNKNOWN",
        ],
        "supportedImageSourceTypes": ["IMAGE_URL", "OBJECT_STORAGE_REF"],
        "maxImageSizeBytes": 5242880,
        "notes": "Mock model tuned for indoor hospital corridor and entrance cameras.",
        "lastUpdatedAt": "2026-05-01T00:00:00Z",
    }
