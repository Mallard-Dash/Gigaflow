from uuid import uuid4
from fastapi import APIRouter, HTTPException
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.contrib.pydantic import pydantic_data_converter

from ..workflows.shipment import (
    ShipmentWorkflow,
    ShipmentInput,
    ShipmentState,
    HumanOperatorChoice
)

router = APIRouter()

async def get_temporal_client():
    return await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

@router.post("/shipments")
async def create_shipment(scenario_id: str | None = None):
    """Create a new shipment workflow."""
    client = await get_temporal_client()
    
    # Generate unique workflow ID
    workflow_id = str(uuid4())
    
    # Configure scenario-specific parameters based on selected scenario
    order_details = {
        "items": ["mystery-box"],
        "quantity": 1,
        "simulate_validation_failure": scenario_id == "price-mismatch",
        "simulate_stock_issue": scenario_id == "warehouse-stock",
        "simulate_transport_delay": scenario_id == "transport-delay",
        "simulate_customs_issue": scenario_id == "customs-issue",
        "simulate_delivery_delay": scenario_id == "delivery-delay"
    }
    simulate_payment_failure = scenario_id in ["payment-failure", "insufficient-funds"]
    payment_info = {"method": "card", "amount": 100}
    
    # Start workflow
    handle = await client.start_workflow(
        ShipmentWorkflow.run,
        ShipmentInput(
            shipment_id=workflow_id,
            order_details=order_details,
            payment_info=payment_info,
            simulate_payment_failure=simulate_payment_failure
        ),
        id=workflow_id,
        task_queue="main-task-queue",
    )
    
    return {"shipment_id": workflow_id}

@router.get("/shipments/{shipment_id}")
async def get_shipment_status(shipment_id: str):
    """Get current status of a shipment."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        
        # Get current status
        status = await handle.query(ShipmentWorkflow.get_status)
        
        # Get delivery update if available
        try:
            delivery_update = await handle.query(ShipmentWorkflow.get_delivery_update)
        except ApplicationError:
            delivery_update = None
        
        return {
            "status": status,
            "delivery_update": delivery_update.dict() if delivery_update else None
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

@router.delete("/shipments/{shipment_id}")
async def cancel_shipment(shipment_id: str):
    """Cancel a shipment workflow."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.cancel_shipment)
        return {"status": "cancelled"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

@router.post("/shipments/{shipment_id}/allocate-warehouse")
async def allocate_warehouse(shipment_id: str):
    """Signal workflow to start warehouse allocation."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.allocate_warehouse)
        return {"status": "warehouse_allocation_started"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

@router.post("/shipments/{shipment_id}/start-transport")
async def start_transport(shipment_id: str):
    """Signal workflow to start transport phase."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.start_transport)
        return {"status": "transport_started"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

@router.post("/shipments/{shipment_id}/update-customs")
async def update_customs(shipment_id: str):
    """Signal workflow to update customs status."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.update_customs_status)
        return {"status": "customs_update_started"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

@router.post("/shipments/{shipment_id}/start-local-delivery")
async def start_local_delivery(shipment_id: str):
    """Signal workflow to start local delivery."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.start_local_delivery)
        return {"status": "local_delivery_started"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

@router.post("/shipments/{shipment_id}/handle-resolution")
async def handle_resolution(shipment_id: str, choice: HumanOperatorChoice):
    """Handle human operator resolution choices."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        status = await handle.query(ShipmentWorkflow.get_status)
        
        # Route to appropriate resolution handler based on current state and choice
        if status == ShipmentState.ORDER_RECEIVED:
            await handle.signal(ShipmentWorkflow.handle_order_resolution, choice)
        elif status == ShipmentState.TRANSPORT_STARTED:
            # Auto-resolve transport issues to keep workflow moving
            if choice == HumanOperatorChoice.WAIT_FOR_RESOLUTION:
                choice = HumanOperatorChoice.REROUTE_SHIPMENT
            await handle.signal(ShipmentWorkflow.handle_transport_resolution, choice)
        elif status == ShipmentState.CUSTOMS_CLEARANCE:
            # Auto-resolve customs issues to keep workflow moving
            if choice == HumanOperatorChoice.ACCEPT_DELAY:
                choice = HumanOperatorChoice.PROVIDE_DOCUMENTATION
            await handle.signal(ShipmentWorkflow.handle_customs_resolution, choice)
        elif choice in [HumanOperatorChoice.NOTIFY_ALL_PARTIES, HumanOperatorChoice.NO_ACTION_NEEDED]:
            await handle.signal(ShipmentWorkflow.handle_delay_resolution, choice)
        else:
            # Auto-resolve payment issues to keep workflow moving
            if choice == HumanOperatorChoice.RESUME_WHEN_READY:
                choice = HumanOperatorChoice.SEND_TO_TECH_SUPPORT
            await handle.signal(ShipmentWorkflow.handle_payment_resolution, choice)
            
        return {"status": "resolution_handled"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")
