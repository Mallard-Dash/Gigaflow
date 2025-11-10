"""Temporal client initialization and deinitialization."""

"""Temporal client initialization and deinitialization."""

from fastapi import FastAPI

from temporal_client import TemporalClient
from ..conf.temporal import get_temporal_conf
from ..workflows import WORKFLOWS
from ..workflows.shipment import (
    update_shipment_state,
    verify_payment,
    notify_human_operator,
    check_warehouse_allocation,
    validate_order,
    check_transport_status,
    check_customs_status,
    check_delivery_status,
    update_delivery_estimate,
    monitor_shipment_status
)
from ..utils.log import get_logger

logger = get_logger(__name__)


async def init_temporal(app: FastAPI) -> None:
    """Initialize Temporal client."""
    logger.info("Initializing Temporal client...")
    temporal_config = get_temporal_conf()

    if not WORKFLOWS:
        logger.info("No workflows found. You can add workflows using the add-temporal-workflow tool.")

    activities = [
        update_shipment_state,
        verify_payment,
        notify_human_operator,
        check_warehouse_allocation,
        validate_order,
        check_transport_status,
        check_customs_status,
        check_delivery_status,
        update_delivery_estimate,
        monitor_shipment_status
    ]

    app.state.temporal_client = TemporalClient(
        config=temporal_config,
        workflows=WORKFLOWS,
        activities=activities
    )
    await app.state.temporal_client.initialize()
    logger.info(f"Temporal client initialized with {len(WORKFLOWS)} workflow(s)")


async def deinit_temporal(app: FastAPI) -> None:
    """Close Temporal client connection."""
    logger.info("Closing Temporal client connection...")
    await app.state.temporal_client.close()
    logger.info("Temporal client connection closed")
