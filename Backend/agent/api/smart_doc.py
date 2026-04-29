from fastapi import APIRouter, File, HTTPException, UploadFile


router = APIRouter()


@router.post("/api/smart/invoice", summary="Legacy smart invoice recognition")
async def smart_analyze_invoice(file: UploadFile = File(...)):
    """Compatibility endpoint for the legacy local DeepSeek/Tesseract flow.

    The Lite deployment intentionally does not ship the old ai_engine module
    because that module depends on local Windows paths and source-level secrets.
    The production document flow should use the algorithm service endpoints.
    """
    raise HTTPException(
        status_code=503,
        detail=(
            "Legacy smart document engine is not available in this Lite "
            "deployment. Use the algorithm-backed document processing APIs."
        ),
    )
