import asyncio
import uuid

import pytest
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.contrib.pydantic import pydantic_data_converter

from ..workflows.shipment import (
    ShipmentWorkflow, ShipmentInput, ShipmentState, PaymentStatus,
    PaymentErrorReason, HumanOperatorChoice, OrderErrorReason,
    update_shipment_state, verify_payment, notify_human_operator,
    check_warehouse_allocation, update_delivery_estimate, validate_order,
    check_transport_status, check_customs_status
)


@pytest.mark.asyncio
async def test_complete_shipment_workflow():
    task_queue = "test-shipment-workflow"
    workflow_id = f"test-shipment-workflow-{uuid.uuid4()}"

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities=[
            update_shipment_state,
            verify_payment,
            notify_human_operator,
            check_warehouse_allocation,
            update_delivery_estimate,
        ],
    ):
        # Start workflow with order and payment info
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Verify initial state
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.PAYMENT_RECEIVED

        # Test warehouse allocation
        await handle.signal(ShipmentWorkflow.allocate_warehouse)
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.PACKAGED

        # Test transport start
        await handle.signal(ShipmentWorkflow.start_transport)
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.TRANSPORT_STARTED

        delivery_update = await handle.query(ShipmentWorkflow.get_delivery_update)
        assert delivery_update is not None
        assert delivery_update.status == "ON_TIME"

        # Test customs clearance
        await handle.signal(ShipmentWorkflow.update_customs_status)
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.CUSTOMS_CLEARANCE

        # Test local delivery
        await handle.signal(ShipmentWorkflow.start_local_delivery)
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.LOCAL_DELIVERY

        # Test delivery completion
        await handle.signal(ShipmentWorkflow.mark_delivered)
        
        result = await handle.result()
        assert result.state == ShipmentState.DELIVERED


@pytest.mark.asyncio
async def test_payment_failure_insufficient_funds():
    task_queue = "test-payment-failure"
    workflow_id = f"test-payment-failure-{uuid.uuid4()}"

    # Mock payment verification to fail with insufficient funds
    async def mock_verify_payment(payment_info: dict, simulate_failure: bool = False) -> tuple[PaymentStatus, dict | None]:
        return PaymentStatus.FAILED, {
            "reason": PaymentErrorReason.INSUFFICIENT_FUNDS,
            "details": "Insufficient funds in account"
        }

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities={
            "verify_payment": mock_verify_payment,
            "notify_human_operator": notify_human_operator,
            "update_shipment_state": update_shipment_state,
        },
    ):
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
                simulate_payment_failure=True
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Wait for payment verification attempts
        await asyncio.sleep(5)
        
        # Check final state
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.CANCELED


@pytest.mark.asyncio
async def test_payment_failure_with_resolution():
    task_queue = "test-payment-resolution"
    workflow_id = f"test-payment-resolution-{uuid.uuid4()}"

    # Mock payment verification to fail with network error
    async def mock_verify_payment(payment_info: dict, simulate_failure: bool = False) -> tuple[PaymentStatus, dict | None]:
        return PaymentStatus.FAILED, {
            "reason": PaymentErrorReason.NETWORK_ERROR,
            "details": "Unable to connect to payment gateway"
        }

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities={
            "verify_payment": mock_verify_payment,
            "notify_human_operator": notify_human_operator,
            "update_shipment_state": update_shipment_state,
        },
    ):
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
                simulate_payment_failure=True
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Wait for payment verification attempts
        await asyncio.sleep(5)
        
        # Check that we're waiting for resolution
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.ORDER_RECEIVED

        # Simulate human operator choosing to send to tech support
        await handle.signal(ShipmentWorkflow.handle_payment_resolution, HumanOperatorChoice.SEND_TO_TECH_SUPPORT)
        
        # Verify the workflow continues
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.PAYMENT_RECEIVED

        # Continue with happy path
        await handle.signal(ShipmentWorkflow.allocate_warehouse)
        await handle.signal(ShipmentWorkflow.start_transport)
        await handle.signal(ShipmentWorkflow.update_customs_status)
        await handle.signal(ShipmentWorkflow.start_local_delivery)
        await handle.signal(ShipmentWorkflow.mark_delivered)
        
        result = await handle.result()
        assert result.state == ShipmentState.DELIVERED
        with pytest.raises(Exception) as exc_info:
            await client.execute_workflow(
                ShipmentWorkflow.run,
                ShipmentInput(
                    shipment_id=workflow_id,
                    order_details={"items": ["test-item"], "quantity": 1},
                    payment_info={"method": "card", "amount": 100},
                ),
                id=workflow_id,
                task_queue=task_queue,
            )
        
        assert "Payment verification failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_order_validation_failure():
    task_queue = "test-order-validation"
    workflow_id = f"test-order-validation-{uuid.uuid4()}"

    # Mock order validation to fail
    async def mock_validate_order(order_details: dict) -> tuple[bool, dict | None]:
        return False, {
            "reason": OrderErrorReason.PRICE_MISMATCH,
            "details": "Price has changed since order placement",
            "resolution_options": [
                "Accept new price",
                "Cancel order"
            ]
        }

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities={
            "validate_order": mock_validate_order,
            "notify_human_operator": notify_human_operator,
            "update_shipment_state": update_shipment_state,
        },
    ):
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Wait for order validation
        await asyncio.sleep(2)
        
        # Check that we're in ORDER_RECEIVED state
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.ORDER_RECEIVED

        # Simulate accepting new price
        await handle.signal(ShipmentWorkflow.handle_order_resolution, HumanOperatorChoice.ACCEPT_NEW_PRICE)
        
        # Verify the workflow continues to payment
        await asyncio.sleep(2)
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.PAYMENT_RECEIVED

@pytest.mark.asyncio
async def test_transport_delay_workflow():
    task_queue = "test-transport-delay"
    workflow_id = f"test-transport-delay-{uuid.uuid4()}"

    # Mock transport check to report weather delay
    async def mock_check_transport(shipment_id: str) -> tuple[bool, dict | None]:
        return False, {
            "reason": "WEATHER_DELAY",
            "details": "Severe weather conditions affecting route",
            "eta_impact": timedelta(days=2),
            "resolution_options": [
                "Wait for resolution",
                "Reroute shipment",
                "Expedite with premium service",
                "Cancel delivery"
            ]
        }

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities={
            "verify_payment": verify_payment,
            "check_warehouse_allocation": check_warehouse_allocation,
            "check_transport_status": mock_check_transport,
            "notify_human_operator": notify_human_operator,
            "update_shipment_state": update_shipment_state,
            "update_delivery_estimate": update_delivery_estimate,
        },
    ):
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Progress to transport stage
        await handle.signal(ShipmentWorkflow.allocate_warehouse)
        await handle.signal(ShipmentWorkflow.start_transport)

        # Check delivery update shows delay
        delivery_update = await handle.query(ShipmentWorkflow.get_delivery_update)
        assert delivery_update is not None
        assert delivery_update.status == "DELAYED"
        assert delivery_update.delay_reason == "WEATHER_DELAY"
        assert delivery_update.new_eta is not None

        # Simulate choosing to expedite shipping
        await handle.signal(ShipmentWorkflow.handle_transport_resolution, HumanOperatorChoice.EXPEDITE_SERVICE)
        
        # Continue with workflow
        await handle.signal(ShipmentWorkflow.update_customs_status)
        await handle.signal(ShipmentWorkflow.start_local_delivery)
        await handle.signal(ShipmentWorkflow.mark_delivered)
        
        result = await handle.result()
        assert result.state == ShipmentState.DELIVERED


@pytest.mark.asyncio
async def test_customs_delay_workflow():
    task_queue = "test-customs-delay"
    workflow_id = f"test-customs-delay-{uuid.uuid4()}"

    # Mock customs check to report documentation issue
    async def mock_check_customs(shipment_id: str) -> tuple[bool, dict | None]:
        return False, {
            "reason": "DOCUMENTATION_MISSING",
            "details": "Required customs documentation missing",
            "eta_impact": timedelta(days=3),
            "resolution_options": [
                "Provide additional documentation",
                "Pay expedited fee",
                "Accept delay",
                "Return shipment"
            ]
        }

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities={
            "verify_payment": verify_payment,
            "check_warehouse_allocation": check_warehouse_allocation,
            "check_transport_status": check_transport_status,
            "check_customs_status": mock_check_customs,
            "notify_human_operator": notify_human_operator,
            "update_shipment_state": update_shipment_state,
            "update_delivery_estimate": update_delivery_estimate,
        },
    ):
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Progress to customs stage
        await handle.signal(ShipmentWorkflow.allocate_warehouse)
        await handle.signal(ShipmentWorkflow.start_transport)
        await handle.signal(ShipmentWorkflow.update_customs_status)

        # Check delivery update shows delay
        delivery_update = await handle.query(ShipmentWorkflow.get_delivery_update)
        assert delivery_update is not None
        assert delivery_update.status == "DELAYED"
        assert delivery_update.delay_reason == "DOCUMENTATION_MISSING"
        assert delivery_update.new_eta is not None

        # Simulate providing documentation
        await handle.signal(ShipmentWorkflow.handle_customs_resolution, HumanOperatorChoice.PROVIDE_DOCUMENTATION)
        
        # Continue with workflow
        await handle.signal(ShipmentWorkflow.start_local_delivery)
        await handle.signal(ShipmentWorkflow.mark_delivered)
        
        result = await handle.result()
        assert result.state == ShipmentState.DELIVERED


@pytest.mark.asyncio
async def test_insufficient_stock_workflow():
    task_queue = "test-insufficient-stock"
    workflow_id = f"test-insufficient-stock-{uuid.uuid4()}"

    # Mock warehouse check to report no stock
    async def mock_check_warehouse(shipment_id: str):
        return {
            "warehouse_id": "WH001",
            "stock_available": False,
            "alternative_warehouses": ["WH002", "WH003"]
        }

    client = await Client.connect(
        "temporal:7233",
        data_converter=pydantic_data_converter,
    )

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[ShipmentWorkflow],
        activities={
            "verify_payment": verify_payment,
            "check_warehouse_allocation": mock_check_warehouse,
            "notify_human_operator": notify_human_operator,
            "update_shipment_state": update_shipment_state,
        },
    ):
        handle = await client.start_workflow(
            ShipmentWorkflow.run,
            ShipmentInput(
                shipment_id=workflow_id,
                order_details={"items": ["test-item"], "quantity": 1},
                payment_info={"method": "card", "amount": 100},
            ),
            id=workflow_id,
            task_queue=task_queue,
        )

        # Wait for payment verification
        await asyncio.sleep(2)
        
        # Try warehouse allocation
        await handle.signal(ShipmentWorkflow.allocate_warehouse)
        status = await handle.query(ShipmentWorkflow.get_status)
        assert status == ShipmentState.WAREHOUSE_ALLOCATION
