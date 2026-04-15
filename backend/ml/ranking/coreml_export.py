"""CoreML export + Cloudflare R2 upload for the learned ranker.

Converts a trained XGBoost model to CoreML ``.mlmodel`` format using
coremltools, verifies the model size is under 500KB, and uploads to
Cloudflare R2. Registers the model in the ``ml_models`` table.

coremltools is an optional dependency (macOS/Linux only, ~150MB). On
Railway production (where coremltools may not be installed), CoreML
export is skipped gracefully, and only the XGBoost model metadata is
registered.

All heavy imports are lazy inside function bodies per the cold-boot contract.

See ``~/.claude/plans/harmonic-meandering-stardust.md`` for the full
Phase 7A spec.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_MODEL_SIZE_BYTES = 500 * 1024  # 500KB


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ExportResult:
    """Output of a CoreML export attempt."""

    success: bool
    mlmodel_path: str | None = None
    file_hash: str | None = None
    file_size_bytes: int | None = None
    error: str | None = None


@dataclass
class UploadResult:
    """Output of an R2 upload."""

    success: bool
    r2_key: str | None = None
    download_url: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# CoreML conversion
# ---------------------------------------------------------------------------


def export_to_coreml(
    xgb_model: object,
    feature_names: list[str],
    output_dir: str | None = None,
    model_version: str = "ranker",
) -> ExportResult:
    """Convert an XGBoost booster to CoreML .mlmodel format.

    Uses ``coremltools.converters.xgboost.convert`` with mode='regressor'
    (LambdaMART inference is identical to regression tree summation).

    Returns ExportResult with the path, SHA-256 hash, and file size.
    Asserts file size < 500KB.
    """
    try:
        import coremltools as ct
    except ImportError:
        logger.info("coremltools not installed; skipping CoreML export")
        return ExportResult(success=False, error="coremltools not installed")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="meld-coreml-")

    filename = f"{model_version}.mlmodel"
    output_path = os.path.join(output_dir, filename)

    try:
        coreml_model = ct.converters.xgboost.convert(
            xgb_model,
            feature_names=feature_names,
            mode="regressor",
            force_32bit_float=True,
        )
        coreml_model.save(output_path)
    except Exception as e:
        logger.warning("CoreML conversion failed: %s", e, exc_info=True)
        return ExportResult(success=False, error=str(e))

    # Compute file hash and size.
    file_size = os.path.getsize(output_path)
    with open(output_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    if file_size > MAX_MODEL_SIZE_BYTES:
        logger.error(
            "CoreML model too large: %d bytes (max %d)",
            file_size,
            MAX_MODEL_SIZE_BYTES,
        )
        return ExportResult(
            success=False,
            mlmodel_path=output_path,
            file_hash=file_hash,
            file_size_bytes=file_size,
            error=f"Model size {file_size} exceeds {MAX_MODEL_SIZE_BYTES} byte limit",
        )

    logger.info(
        "CoreML export success: %s (%d bytes, hash=%s)",
        output_path,
        file_size,
        file_hash[:16],
    )
    return ExportResult(
        success=True,
        mlmodel_path=output_path,
        file_hash=file_hash,
        file_size_bytes=file_size,
    )


# ---------------------------------------------------------------------------
# R2 upload
# ---------------------------------------------------------------------------


def upload_to_r2(
    local_path: str,
    r2_key: str,
    bucket: str | None = None,
) -> UploadResult:
    """Upload a file to Cloudflare R2 via S3-compatible API.

    Reads R2 credentials from MLSettings. If credentials are not configured,
    returns a graceful failure (model metadata is still registered without
    a download URL).
    """
    from ml.config import get_ml_settings

    settings = get_ml_settings()

    if not settings.r2_endpoint_url or not settings.r2_access_key_id:
        logger.info("R2 credentials not configured; skipping upload")
        return UploadResult(success=False, error="R2 credentials not configured")

    if bucket is None:
        bucket = settings.r2_bucket_models

    try:
        import boto3

        s3 = boto3.client(
            service_name="s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )

        with open(local_path, "rb") as f:
            s3.upload_fileobj(f, bucket, r2_key)

        # Construct download URL.
        # For public bucket with custom domain: https://models.heymeld.com/{r2_key}
        # For direct R2: https://{account_id}.r2.cloudflarestorage.com/{bucket}/{r2_key}
        download_url = f"{settings.r2_endpoint_url}/{bucket}/{r2_key}"

        logger.info("R2 upload success: %s -> %s/%s", local_path, bucket, r2_key)
        return UploadResult(
            success=True,
            r2_key=r2_key,
            download_url=download_url,
        )
    except Exception as e:
        logger.warning("R2 upload failed: %s", e, exc_info=True)
        return UploadResult(success=False, error=str(e))


# ---------------------------------------------------------------------------
# Model registration
# ---------------------------------------------------------------------------


async def register_model(
    db: "AsyncSession",
    model_version: str,
    feature_names: list[str],
    hyperparams: dict,
    train_samples: int,
    val_ndcg: float,
    file_hash: str | None = None,
    file_size_bytes: int | None = None,
    r2_key: str | None = None,
    download_url: str | None = None,
) -> int:
    """Persist model metadata to ml_models and activate it.

    Deactivates any previously active model of the same type, then
    inserts the new one as active.

    Returns the new model's id.
    """
    from app.core.time import utcnow_naive
    from app.models.ml_models import MLModel
    from sqlalchemy import update

    # Deactivate previous active models of this type.
    await db.execute(
        update(MLModel)
        .where(MLModel.model_type == "ranker", MLModel.is_active.is_(True))
        .values(is_active=False)
    )

    model = MLModel(
        model_type="ranker",
        model_version=model_version,
        file_hash=file_hash,
        file_size_bytes=file_size_bytes,
        r2_key=r2_key,
        download_url=download_url,
        train_samples=train_samples,
        val_ndcg=val_ndcg,
        feature_names_json=json.dumps(feature_names),
        hyperparams_json=json.dumps(hyperparams),
        is_active=True,
        created_at=utcnow_naive(),
    )
    db.add(model)
    await db.flush()
    logger.info(
        "Registered model %s (id=%d, ndcg=%.4f, samples=%d, r2=%s)",
        model_version,
        model.id,
        val_ndcg,
        train_samples,
        r2_key or "none",
    )
    return model.id
