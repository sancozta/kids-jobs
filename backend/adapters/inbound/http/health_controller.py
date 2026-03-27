"""
Health Controller - Inbound Adapter
"""
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check():
    return {"status": "ok", "service": "kids-jobs-backend"}
