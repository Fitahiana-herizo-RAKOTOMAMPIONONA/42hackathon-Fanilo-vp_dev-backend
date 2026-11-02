from __future__ import annotations

import json
import os
from typing import Any

import cv2
import httpx
import numpy as np
from deepface import DeepFace
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.database import get_db
from app.modules.auth.dependency import get_current_user
from app.modules.auth.models import User
from app.modules.verification.schemas import (
    VerificationListResponse,
    VerificationResponse,
    VerifyRequest,
)
from app.modules.verification.service import VerificationService

verification_router = APIRouter(
    prefix="/verification",
    tags=["Verification"],
)


@verification_router.post(
    "/verify",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Vérifier une information / affirmation",
)
async def verify_claim(
    data: VerifyRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Vérifie une affirmation en analysant le web (Google) et les réseaux (Facebook).
    Extrait les sources pertinentes, évalue la convergence et attribue
    un verdict avec score de confiance.
    """
    verification = await VerificationService.verify_claim(
        session=session,
        claim=data.claim,
        user_id=current_user.id,
    )
    return verification


@verification_router.get(
    "/",
    response_model=VerificationListResponse,
    summary="Lister mes vérifications",
)
async def list_my_verifications(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Liste l'historique des vérifications soumises par l'utilisateur connecté."""
    items, total = await VerificationService.list_by_user(
        session=session,
        user_id=current_user.id,
        page=page,
        per_page=per_page,
    )
    return VerificationListResponse(
        total=total,
        page=page,
        per_page=per_page,
        verifications=[VerificationResponse.model_validate(v) for v in items],
    )


@verification_router.get(
    "/all",
    response_model=VerificationListResponse,
    summary="Lister toutes les vérifications (historique public)",
)
async def list_all_verifications(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """Liste paginée de toutes les vérifications publiques."""
    items, total = await VerificationService.list_all(
        session=session,
        page=page,
        per_page=per_page,
    )
    return VerificationListResponse(
        total=total,
        page=page,
        per_page=per_page,
        verifications=[VerificationResponse.model_validate(v) for v in items],
    )


@verification_router.get(
    "/{verification_id}",
    response_model=VerificationResponse,
    summary="Détail d'une vérification avec ses sources",
)
async def get_verification(
    verification_id: int,
    session: AsyncSession = Depends(get_db),
):
    """Récupère une vérification spécifique et toutes ses sources analysées."""
    verification = await VerificationService.get_by_id(
        session=session,
        verification_id=verification_id,
    )
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found",
        )
    return verification


@verification_router.delete(
    "/{verification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une vérification",
)
async def delete_verification(
    verification_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Supprime une vérification (réservé à son créateur ou admin)."""
    user_id_filter = None if current_user.is_admin else current_user.id
    deleted = await VerificationService.delete(
        session=session,
        verification_id=verification_id,
        user_id=user_id_filter,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification not found or unauthorized",
        )

@verification_router.post(
"/authentifier_images",
status_code=status.HTTP_200_OK,
summary="Authentifier une images",
)
async def authenticate_img(
        file1: UploadFile = File(..., description="First image"),
        file2: UploadFile = File(..., description="Base image")
):
    async def get_ai_response(prompt: str):
        client = Groq(
            api_key=os.environ.get("GROQ_API_KEY")
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Answer the user's request by using the deepface module as a reference.",
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="qwen/qwen3.8-27b"
        )
        # content = chat_completion.choices[0].message.content
        return {
            "prompt": prompt,
            "response": chat_completion.choices[0].message.content
        }

    def bytes_to_cv2_img(image_bytes: bytes) -> np.ndarray:
        """Converts uploaded raw file bytes into an OpenCV-compatible BGR image."""
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("Invalid image file format.")
            return img
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to process image data: {e.__str__()}"
            )

    img1_bytes = await file1.read()
    img2_bytes = await file2.read()

    img1 = bytes_to_cv2_img(img1_bytes)
    img2 = bytes_to_cv2_img(img2_bytes)
    try:
        result = DeepFace.verify(
            img1_path=img1,
            img2_path=img2,
            enforce_detection=False
        )
        prompt: str = f"""Explain this ouptut to me: {json.dumps(result)}"""
        response = await get_ai_response(prompt)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DeepFace verification error: {e.__str__()}"
        )
