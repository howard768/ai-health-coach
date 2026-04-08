from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.health import OuraToken
from app.services.oura import OuraClient

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/oura")
async def oura_auth():
    """Redirect user to Oura OAuth authorization page."""
    client = OuraClient()
    return RedirectResponse(url=client.get_auth_url())


@router.get("/oura/callback")
async def oura_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle Oura OAuth callback — exchange code for tokens."""
    client = OuraClient()
    token_data = await client.exchange_code(code)

    # Store tokens
    oura_token = OuraToken(
        user_id="default",  # TODO: get from authenticated user session
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_at=datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 86400)),
    )
    db.add(oura_token)
    await db.commit()

    return {"status": "connected", "message": "Oura Ring connected successfully"}
