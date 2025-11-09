"""Centralized initialization and deinitialization for the API."""

from fastapi import FastAPI

from .temporal import init_temporal, deinit_temporal


async def init(app: FastAPI) -> None:
    """Initialize all components during app startup."""
    await init_temporal(app)
    pass


async def deinit(app: FastAPI) -> None:
    """Deinitialize all components during app shutdown."""
    await deinit_temporal(app)
    pass
