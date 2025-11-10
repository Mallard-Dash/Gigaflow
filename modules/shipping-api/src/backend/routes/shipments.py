from uuid import uuid4
from fastapi import APIRouter, HTTPException, Body
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.contrib.pydantic import pydantic_data_converter
from pydantic import BaseModel

from ..workflows.shipment import (
    ShipmentWorkflow,
    ShipmentInput,
    ShipmentState,
    HumanOperatorChoice
)

router = APIRouter()

class CreateShipmentRequest(BaseModel):
    scenario_id: str | None = None

async def get_temporal_client():
    return await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

@router.post("/shipments")
async def create_shipment(request: CreateShipmentRequest):
    """Create a new shipment workflow."""
    scenario_id = request.scenario_id
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
        
        # Get current error if available
        try:
            current_error = await handle.query(ShipmentWorkflow.get_current_error)
        except ApplicationError:
            current_error = None
        
        # Get summary if available
        try:
            summary = await handle.query(ShipmentWorkflow.get_summary)
        except ApplicationError:
            summary = None
        
        # Get pause status if available
        try:
            is_paused = await handle.query(ShipmentWorkflow.is_paused)
        except ApplicationError:
            is_paused = False
        
        return {
            "status": status,
            "delivery_update": delivery_update.dict() if delivery_update else None,
            "current_error": current_error.dict() if current_error else None,
            "summary": summary.dict() if summary else None,
            "is_paused": is_paused
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

@router.post("/shipments/{shipment_id}/mark-delivered")
async def mark_delivered(shipment_id: str):
    """Signal workflow to mark shipment as delivered."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.mark_delivered)
        return {"status": "delivered"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Shipment not found: {str(e)}")

class HandleResolutionRequest(BaseModel):
    choice: str

@router.post("/shipments/{shipment_id}/pause")
async def pause_workflow(shipment_id: str):
    """Pause the workflow execution."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.pause_workflow)
        return {"status": "paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pausing workflow: {str(e)}")

@router.post("/shipments/{shipment_id}/resume")
async def resume_workflow(shipment_id: str):
    """Resume the workflow execution."""
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        await handle.signal(ShipmentWorkflow.resume_workflow)
        return {"status": "resumed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resuming workflow: {str(e)}")

@router.post("/shipments/{shipment_id}/handle-resolution")
async def handle_resolution(shipment_id: str, request: HandleResolutionRequest):
    """Handle human operator resolution choices."""
    # Convert string choice to enum
    try:
        choice = HumanOperatorChoice[request.choice]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid choice: {request.choice}")
    
    client = await get_temporal_client()
    
    try:
        handle = client.get_workflow_handle(shipment_id)
        status = await handle.query(ShipmentWorkflow.get_status)
        current_error = await handle.query(ShipmentWorkflow.get_current_error)
        
        # Check if this is a delay-specific resolution (can happen in any state)
        if choice in [HumanOperatorChoice.DO_NOTHING, HumanOperatorChoice.INFORM_CUSTOMERS, HumanOperatorChoice.REARRANGE_LOGISTICS]:
            await handle.signal(ShipmentWorkflow.handle_delay_resolution, choice)
        # Check if this is a payment-specific resolution based on choice type
        elif choice in [HumanOperatorChoice.SEND_TO_TECH_SUPPORT, HumanOperatorChoice.RETRY_PAYMENT, 
                       HumanOperatorChoice.RESUME_WHEN_READY] or \
             (current_error and current_error.reason in ["NETWORK_ERROR", "RECEIVER_ERROR", "SENDER_ERROR", 
                                                          "INSUFFICIENT_FUNDS", "BANK_SERVER_DOWN", "TRANSACTION_ERROR"]):
            await handle.signal(ShipmentWorkflow.handle_payment_resolution, choice)
        # Route to appropriate resolution handler based on current state
        elif status == ShipmentState.ORDER_RECEIVED:
            await handle.signal(ShipmentWorkflow.handle_order_resolution, choice)
        elif status == ShipmentState.WAREHOUSE_ALLOCATION or status == ShipmentState.PACKAGED:
            await handle.signal(ShipmentWorkflow.handle_warehouse_resolution, choice)
        elif status == ShipmentState.TRANSPORT_STARTED:
            await handle.signal(ShipmentWorkflow.handle_transport_resolution, choice)
        elif status == ShipmentState.CUSTOMS_CLEARANCE:
            await handle.signal(ShipmentWorkflow.handle_customs_resolution, choice)
        elif status == ShipmentState.LOCAL_DELIVERY:
            await handle.signal(ShipmentWorkflow.handle_delivery_resolution, choice)
        else:
            raise HTTPException(status_code=400, detail=f"Cannot handle resolution in state {status}")
            
        return {"status": "resolution_handled"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling resolution: {str(e)}")
