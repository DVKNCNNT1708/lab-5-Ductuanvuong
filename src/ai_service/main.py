from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

SERVICE_NAME = "vision-model"
SERVICE_VERSION = "1.0.0"
MODEL_VERSION = "yolov11n-hospital-2.3.1"

app = FastAPI(
    title="FIT4110 Lab 05 - Vision Model Service",
    version=SERVICE_VERSION,
    description="Mock model runtime used by the AI Vision API in Docker Compose.",
)


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


class Prediction(BaseModel):
    status: str
    confidence: float = Field(..., ge=0, le=1)
    riskLevel: str
    modelVersion: str
    summary: str
    alertHint: str
    thumbnailUrl: str
    objects: List[DetectedObject]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.post("/predict", response_model=Prediction)
def predict(payload: Dict[str, Any]) -> Prediction:
    motion_level = payload.get("motionLevel") or 0.86
    confidence = round(max(float(motion_level), 0.86), 2)
    risk_level = "HIGH" if confidence >= 0.85 else "MEDIUM"

    return Prediction(
        status="COMPLETED",
        confidence=confidence,
        riskLevel=risk_level,
        modelVersion=MODEL_VERSION,
        summary="Person detected in restricted hospital area",
        alertHint="REVIEW_SECURITY" if risk_level == "HIGH" else "MONITOR",
        thumbnailUrl="https://media.hospital.local/thumbnails/mock-detection.jpg",
        objects=[
            DetectedObject(
                objectType="PERSON",
                label="human",
                confidence=confidence,
                trackId="TRACK-77",
                boundingBox=BoundingBox(x=0.12, y=0.08, width=0.41, height=0.82),
            )
        ],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
