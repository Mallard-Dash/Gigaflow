import asyncio
from datetime import timedelta
from enum import Enum

from pydantic import BaseModel
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

from ..utils.log import get_logger

logger = get_logger(__name__)


#### Models ####


class OrderErrorReason(str, Enum):
    INVALID_ITEMS = "INVALID_ITEMS"
    PRICE_MISMATCH = "PRICE_MISMATCH"
    QUANTITY_ERROR = "QUANTITY_ERROR"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SYSTEM_ERROR = "SYSTEM_ERROR"

class PaymentErrorReason(str, Enum):
    NETWORK_ERROR = "NETWORK_ERROR"
    RECEIVER_ERROR = "RECEIVER_ERROR"
    SENDER_ERROR = "SENDER_ERROR"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    BANK_SERVER_DOWN = "BANK_SERVER_DOWN"
    TRANSACTION_ERROR = "TRANSACTION_ERROR"
    RECEIVER_BANK_REJECTED = "RECEIVER_BANK_REJECTED"

class WarehouseErrorReason(str, Enum):
    NO_STOCK = "NO_STOCK"
    PARTIAL_STOCK = "PARTIAL_STOCK"
    SYSTEM_DOWN = "SYSTEM_DOWN"
    LOCATION_UNAVAILABLE = "LOCATION_UNAVAILABLE"
    ITEM_DISCONTINUED = "ITEM_DISCONTINUED"

class TransportErrorReason(str, Enum):
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    WEATHER_DELAY = "WEATHER_DELAY"
    ROUTE_BLOCKED = "ROUTE_BLOCKED"
    DRIVER_UNAVAILABLE = "DRIVER_UNAVAILABLE"
    LOADING_ISSUES = "LOADING_ISSUES"

class CustomsErrorReason(str, Enum):
    DOCUMENTATION_MISSING = "DOCUMENTATION_MISSING"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"
    PROHIBITED_ITEMS = "PROHIBITED_ITEMS"
    DUTY_PAYMENT_ISSUES = "DUTY_PAYMENT_ISSUES"
    CLEARANCE_DELAY = "CLEARANCE_DELAY"

class DeliveryErrorReason(str, Enum):
    ADDRESS_NOT_FOUND = "ADDRESS_NOT_FOUND"
    RECIPIENT_UNAVAILABLE = "RECIPIENT_UNAVAILABLE"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    LOCAL_RESTRICTIONS = "LOCAL_RESTRICTIONS"
    SCHEDULING_CONFLICT = "SCHEDULING_CONFLICT"

class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    WAITING_FOR_RESOLUTION = "WAITING_FOR_RESOLUTION"

class HumanOperatorChoice(str, Enum):
    SEND_TO_TECH_SUPPORT = "SEND_TO_TECH_SUPPORT"
    RETRY_PAYMENT = "RETRY_PAYMENT"
    RESUME_WHEN_READY = "RESUME_WHEN_READY"
    CANCEL_ORDER = "CANCEL_ORDER"
    UPDATE_ORDER = "UPDATE_ORDER"
    ACCEPT_NEW_PRICE = "ACCEPT_NEW_PRICE"
    ADJUST_QUANTITY = "ADJUST_QUANTITY"
    WAIT_FOR_RESOLUTION = "WAIT_FOR_RESOLUTION"
    REROUTE_SHIPMENT = "REROUTE_SHIPMENT"
    EXPEDITE_SERVICE = "EXPEDITE_SERVICE"
    PROVIDE_DOCUMENTATION = "PROVIDE_DOCUMENTATION"
    PAY_EXPEDITED_FEE = "PAY_EXPEDITED_FEE"
    ACCEPT_DELAY = "ACCEPT_DELAY"
    RETURN_SHIPMENT = "RETURN_SHIPMENT"
    NOTIFY_ALL_PARTIES = "NOTIFY_ALL_PARTIES"
    NO_ACTION_NEEDED = "NO_ACTION_NEEDED"

class DelayReason(str, Enum):
    LOGISTICS_DELAY = "LOGISTICS_DELAY"
    WEATHER_IMPACT = "WEATHER_IMPACT"
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    RESOURCE_SHORTAGE = "RESOURCE_SHORTAGE"
    TECHNICAL_ISSUES = "TECHNICAL_ISSUES"

class WarehouseAction(str, Enum):
    ALLOCATE_DIFFERENT = "ALLOCATE_DIFFERENT"
    CANCEL_ORDER = "CANCEL_ORDER"
    WAIT_FOR_STOCK = "WAIT_FOR_STOCK"

class ShipmentState(str, Enum):
    ORDER_RECEIVED = "ORDER_RECEIVED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    WAREHOUSE_ALLOCATION = "WAREHOUSE_ALLOCATION"
    PACKAGED = "PACKAGED"
    TRANSPORT_STARTED = "TRANSPORT_STARTED"
    IN_TRANSIT = "IN_TRANSIT"
    CUSTOMS_CLEARANCE = "CUSTOMS_CLEARANCE"
    LOCAL_DELIVERY = "LOCAL_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELED = "CANCELED"


class PaymentError(BaseModel):
    reason: PaymentErrorReason
    details: str

class ShipmentInput(BaseModel):
    shipment_id: str
    order_details: dict
    payment_info: dict
    simulate_payment_failure: bool = False  # For testing scenarios

class WarehouseAllocationInput(BaseModel):
    warehouse_id: str
    stock_available: bool
    alternative_warehouses: list[str]

class ErrorDetails(BaseModel):
    reason: str
    details: str
    eta_impact: timedelta | None = None
    resolution_options: list[str] = []

class DeliveryUpdate(BaseModel):
    estimated_delivery_date: str
    original_eta: str | None = None
    status: str
    issues: list[str] = []
    delay_reason: str | None = None
    new_eta: str | None = None


class ShipmentResponse(BaseModel):
    shipment_id: str
    state: ShipmentState


#### Activities ####

@activity.defn
async def monitor_shipment_status(shipment_id: str, state: ShipmentState) -> tuple[bool, ErrorDetails | None]:
    """Monitor shipment for potential delays or issues."""
    logger.info(f"Monitoring shipment {shipment_id} in state {state}")
    await asyncio.sleep(1)
    
    # 30% chance of delay after main scenario is resolved
    import random
    if random.random() < 0.3:
        delay_reasons = list(DelayReason)
        delay_reason = random.choice(delay_reasons)
        delay_days = random.randint(1, 3)
        delay_details = {
            DelayReason.LOGISTICS_DELAY: "Unexpected delay at logistics hub",
            DelayReason.WEATHER_IMPACT: "Weather conditions affecting delivery schedule",
            DelayReason.TRAFFIC_CONGESTION: "Heavy traffic causing delivery delays",
            DelayReason.RESOURCE_SHORTAGE: "Temporary resource constraints",
            DelayReason.TECHNICAL_ISSUES: "Technical issues affecting delivery system"
        }[delay_reason]
        
        return False, ErrorDetails(
            reason=delay_reason.value,
            details=delay_details,
            eta_impact=timedelta(days=delay_days),
            resolution_options=[
                "Notify all parties and adjust schedules",
                "No immediate action needed"
            ]
        )
    return True, None


@activity.defn
async def update_shipment_state(shipment_id: str, state: ShipmentState) -> None:
    """Update the shipment state in the external system."""
    logger.info(f"Updating shipment {shipment_id} to state {state.value}")
    await asyncio.sleep(1)
    logger.info(f"Successfully updated shipment {shipment_id} to state {state.value}")

@activity.defn
async def verify_payment(payment_info: dict, simulate_failure: bool = False) -> tuple[PaymentStatus, PaymentError | None]:
    """Verify payment status with payment processor."""
    logger.info("Verifying payment")
    await asyncio.sleep(1)

    if not simulate_failure:
        return PaymentStatus.SUCCESS, None

    # Simulate 80% chance of failure after 3rd attempt
    import random
    if random.random() < 0.8:
        error_reasons = list(PaymentErrorReason)
        error_reason = random.choice(error_reasons)
        error_details = {
            PaymentErrorReason.NETWORK_ERROR: "Unable to connect to payment gateway",
            PaymentErrorReason.RECEIVER_ERROR: "Receiving bank system error",
            PaymentErrorReason.SENDER_ERROR: "Sending bank system error",
            PaymentErrorReason.INSUFFICIENT_FUNDS: "Insufficient funds in account",
            PaymentErrorReason.BANK_SERVER_DOWN: "Bank servers are currently unavailable",
            PaymentErrorReason.TRANSACTION_ERROR: "Error processing transaction",
            PaymentErrorReason.RECEIVER_BANK_REJECTED: "Payment rejected by receiving bank"
        }[error_reason]
        
        return PaymentStatus.FAILED, PaymentError(reason=error_reason, details=error_details)
    
    return PaymentStatus.SUCCESS, None

@activity.defn
async def notify_human_operator(shipment_id: str, message: str, action_required: bool = False) -> None:
    """Notify human operator about issues or required actions."""
    logger.info(f"Notifying operator about shipment {shipment_id}: {message}")
    await asyncio.sleep(1)

@activity.defn
async def check_warehouse_allocation(shipment_id: str, order_details: dict) -> WarehouseAllocationInput:
    """Check warehouse stock and allocation possibilities."""
    logger.info(f"Checking warehouse allocation for shipment {shipment_id}")
    await asyncio.sleep(1)
    # Mock implementation - would actually check warehouse management system
    if "simulate_stock_issue" in order_details and order_details["simulate_stock_issue"]:
        return WarehouseAllocationInput(
            warehouse_id="WH001",
            stock_available=False,
            alternative_warehouses=["WH002", "WH003"]
        )
    return WarehouseAllocationInput(
        warehouse_id="WH001",
        stock_available=True,
        alternative_warehouses=["WH002", "WH003"]
    )

@activity.defn
async def validate_order(order_details: dict) -> tuple[bool, ErrorDetails | None]:
    """Validate order details and check for issues."""
    logger.info("Validating order details")
    await asyncio.sleep(1)
    # Mock implementation - would validate against order management system
    if "simulate_validation_failure" in order_details and order_details["simulate_validation_failure"]:
        error_reason = random.choice(list(OrderErrorReason))
        error_details = {
            OrderErrorReason.INVALID_ITEMS: "One or more items are no longer available",
            OrderErrorReason.PRICE_MISMATCH: "Price has changed since order placement",
            OrderErrorReason.QUANTITY_ERROR: "Requested quantity exceeds maximum allowed",
            OrderErrorReason.VALIDATION_FAILED: "Order validation failed",
            OrderErrorReason.SYSTEM_ERROR: "Order system is experiencing issues"
        }[error_reason]
        return False, ErrorDetails(
            reason=error_reason.value,
            details=error_details,
            resolution_options=[
                "Update order with available items",
                "Accept new price",
                "Adjust quantity",
                "Cancel order"
            ]
        )
    return True, None

@activity.defn
async def check_transport_status(shipment_id: str, order_details: dict) -> tuple[bool, ErrorDetails | None]:
    """Check transport status and potential issues."""
    logger.info(f"Checking transport status for shipment {shipment_id}")
    await asyncio.sleep(1)
    # Mock implementation - would check with transport management system
    if "simulate_transport_delay" in order_details and order_details["simulate_transport_delay"]:
        error_reason = random.choice(list(TransportErrorReason))
        error_details = {
            TransportErrorReason.VEHICLE_BREAKDOWN: "Vehicle requires emergency repair",
            TransportErrorReason.WEATHER_DELAY: "Severe weather conditions affecting route",
            TransportErrorReason.ROUTE_BLOCKED: "Main route is blocked, detour required",
            TransportErrorReason.DRIVER_UNAVAILABLE: "Driver unavailable due to emergency",
            TransportErrorReason.LOADING_ISSUES: "Issues with cargo loading"
        }[error_reason]
        return False, ErrorDetails(
            reason=error_reason.value,
            details=error_details,
            eta_impact=timedelta(days=random.randint(1, 3)),
            resolution_options=[
                "Wait for resolution",
                "Reroute shipment",
                "Expedite with premium service",
                "Cancel delivery"
            ]
        )
    return True, None

@activity.defn
async def check_customs_status(shipment_id: str, order_details: dict) -> tuple[bool, ErrorDetails | None]:
    """Check customs clearance status and issues."""
    logger.info(f"Checking customs status for shipment {shipment_id}")
    await asyncio.sleep(1)
    # Mock implementation - would check with customs system
    if "simulate_customs_issue" in order_details and order_details["simulate_customs_issue"]:
        error_reason = random.choice(list(CustomsErrorReason))
        error_details = {
            CustomsErrorReason.DOCUMENTATION_MISSING: "Required customs documentation missing",
            CustomsErrorReason.INSPECTION_REQUIRED: "Package selected for detailed inspection",
            CustomsErrorReason.PROHIBITED_ITEMS: "Potentially prohibited items detected",
            CustomsErrorReason.DUTY_PAYMENT_ISSUES: "Issues with duty payment processing",
            CustomsErrorReason.CLEARANCE_DELAY: "General customs clearance delay"
        }[error_reason]
        return False, ErrorDetails(
            reason=error_reason.value,
            details=error_details,
            eta_impact=timedelta(days=random.randint(2, 5)),
            resolution_options=[
                "Provide additional documentation",
                "Pay expedited processing fee",
                "Accept delay",
                "Return shipment"
            ]
        )
    return True, None

@activity.defn
async def update_delivery_estimate(
    shipment_id: str,
    state: ShipmentState,
    error_details: ErrorDetails | None = None
) -> DeliveryUpdate:
    """Update delivery estimation and check for issues."""
    logger.info(f"Updating delivery estimate for shipment {shipment_id}")
    await asyncio.sleep(1)
    
    from datetime import datetime, timedelta
    base_date = datetime(2025, 11, 15)
    
    if error_details and error_details.eta_impact:
        new_date = base_date + error_details.eta_impact
        return DeliveryUpdate(
            estimated_delivery_date=base_date.strftime("%Y-%m-%d"),
            original_eta=base_date.strftime("%Y-%m-%d"),
            status="DELAYED",
            issues=[error_details.details],
            delay_reason=error_details.reason,
            new_eta=new_date.strftime("%Y-%m-%d")
        )
    
    return DeliveryUpdate(
        estimated_delivery_date=base_date.strftime("%Y-%m-%d"),
        status="ON_TIME",
        issues=[]
    )


#### Workflows ####


@workflow.defn
class ShipmentWorkflow:
    def __init__(self) -> None:
        self._state: ShipmentState = ShipmentState.ORDER_RECEIVED
        self._payment_retries = 0
        self._payment_status = PaymentStatus.PENDING
        self._payment_error: PaymentError | None = None
        self._delivery_update: DeliveryUpdate | None = None
        self._current_error: ErrorDetails | None = None
        self._input: ShipmentInput | None = None
        self._exit = asyncio.Event()
        self._payment_resolution = asyncio.Event()
        self._order_resolution = asyncio.Event()
        self._transport_resolution = asyncio.Event()
        self._customs_resolution = asyncio.Event()
        self._delay_resolution = asyncio.Event()

    @workflow.run
    async def run(self, input: ShipmentInput) -> ShipmentResponse:
        workflow_id = workflow.info().workflow_id
        self._input = input
        
        # Order received and validation
        self._state = ShipmentState.ORDER_RECEIVED
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Validate order
        valid, error_details = await workflow.execute_activity(
            validate_order,
            args=[input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not valid:
            self._current_error = error_details
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    input.shipment_id,
                    f"Order validation failed: {error_details.details}\n"
                    f"Options:\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._order_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)

        # Payment verification with retries
        while self._payment_retries < 3 and self._payment_status not in [PaymentStatus.SUCCESS, PaymentStatus.WAITING_FOR_RESOLUTION]:
            self._payment_status, self._payment_error = await workflow.execute_activity(
                verify_payment,
                args=[input.payment_info, input.simulate_payment_failure],
                start_to_close_timeout=timedelta(seconds=30),
            )
            
            if self._payment_status == PaymentStatus.FAILED:
                self._payment_retries += 1
                if self._payment_retries == 3:
                    if self._payment_error and self._payment_error.reason == PaymentErrorReason.INSUFFICIENT_FUNDS:
                        await workflow.execute_activity(
                            notify_human_operator,
                            args=[
                                input.shipment_id,
                                f"Order cancelled: {self._payment_error.details}",
                                False
                            ],
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        self._state = ShipmentState.CANCELED
                        self._exit.set()
                        return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)
                    else:
                        self._payment_status = PaymentStatus.WAITING_FOR_RESOLUTION
                        await workflow.execute_activity(
                            notify_human_operator,
                            args=[
                                input.shipment_id,
                                f"Payment issue: {self._payment_error.details if self._payment_error else 'Unknown error'}\n"
                                "Options:\n"
                                "1. Send to tech support\n"
                                "2. Retry payment\n"
                                "3. Resume when system is ready\n"
                                "4. Cancel order",
                                True
                            ],
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        # Wait for human operator decision
                        await self._payment_resolution.wait()
                else:
                    await asyncio.sleep(60)  # Wait before retry
            else:
                self._state = ShipmentState.PAYMENT_RECEIVED

        try:
            # Wait for workflow completion
            await self._exit.wait()
        except asyncio.CancelledError:
            self._state = ShipmentState.CANCELED
            await workflow.execute_activity(
                update_shipment_state,
                args=[workflow_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )
            raise

        return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)

    @workflow.signal
    async def allocate_warehouse(self) -> None:
        if self._state != ShipmentState.PAYMENT_RECEIVED:
            raise ApplicationError(f"Cannot allocate warehouse in state {self._state}")
        
        self._state = ShipmentState.WAREHOUSE_ALLOCATION
        workflow_id = workflow.info().workflow_id
        
        allocation = await workflow.execute_activity(
            check_warehouse_allocation,
            args=[workflow_id, self._input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )
        
        if not allocation.stock_available:
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    workflow_id,
                    f"Insufficient stock. Options: {allocation.alternative_warehouses}",
                    True
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            self._state = ShipmentState.PACKAGED
            await workflow.execute_activity(
                update_shipment_state,
                args=[workflow_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )
            # Check for delays after warehouse allocation
            await self.check_for_delays(workflow_id)

    @workflow.signal
    async def start_transport(self) -> None:
        if self._state != ShipmentState.PACKAGED:
            raise ApplicationError(f"Cannot start transport in state {self._state}")
        
        self._state = ShipmentState.TRANSPORT_STARTED
        workflow_id = workflow.info().workflow_id

        # Check transport status
        ok, error_details = await workflow.execute_activity(
            check_transport_status,
            args=[workflow_id, self._input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not ok:
            self._current_error = error_details
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[workflow_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    workflow_id,
                    f"Transport issue: {error_details.details}\n"
                    f"ETA Impact: {error_details.eta_impact.days} days\n"
                    f"Options:\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._transport_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                return
        else:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[workflow_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )
            # Check for delays after transport resolution
            await self.check_for_delays(workflow_id)
        
        await workflow.execute_activity(
            update_shipment_state,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

    @workflow.signal
    async def update_customs_status(self) -> None:
        if self._state != ShipmentState.TRANSPORT_STARTED:
            raise ApplicationError(f"Cannot update customs status in state {self._state}")
        
        self._state = ShipmentState.CUSTOMS_CLEARANCE
        workflow_id = workflow.info().workflow_id

        # Check customs status
        ok, error_details = await workflow.execute_activity(
            check_customs_status,
            args=[workflow_id, self._input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not ok:
            self._current_error = error_details
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[workflow_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    workflow_id,
                    f"Customs issue: {error_details.details}\n"
                    f"ETA Impact: {error_details.eta_impact.days} days\n"
                    f"Options:\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._customs_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                return
        else:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[workflow_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )
            # Check for delays after customs resolution
            await self.check_for_delays(workflow_id)

    @workflow.signal
    async def start_local_delivery(self) -> None:
        if self._state != ShipmentState.CUSTOMS_CLEARANCE:
            raise ApplicationError(f"Cannot start local delivery in state {self._state}")
        
        self._state = ShipmentState.LOCAL_DELIVERY
        workflow_id = workflow.info().workflow_id
        
        self._delivery_update = await workflow.execute_activity(
            update_delivery_estimate,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        if self._delivery_update.issues:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, f"Delivery issues: {self._delivery_update.issues}", True],
                start_to_close_timeout=timedelta(seconds=10),
            )
        else:
            # Check for delays after local delivery starts
            await self.check_for_delays(workflow_id)

    @workflow.signal
    async def mark_delivered(self) -> None:
        if self._state != ShipmentState.LOCAL_DELIVERY:
            raise ApplicationError(f"Cannot mark as delivered in state {self._state}")
        
        self._state = ShipmentState.DELIVERED
        workflow_id = workflow.info().workflow_id
        
        await workflow.execute_activity(
            update_shipment_state,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        # Reset all workflow state before exiting
        self._payment_retries = 0
        self._payment_status = PaymentStatus.PENDING
        self._payment_error = None
        self._delivery_update = None
        self._current_error = None
        self._input = None
        self._payment_resolution = asyncio.Event()
        self._order_resolution = asyncio.Event()
        self._transport_resolution = asyncio.Event()
        self._customs_resolution = asyncio.Event()
        self._delay_resolution = asyncio.Event()
        self._exit.set()

    @workflow.signal
    async def handle_order_resolution(self, choice: HumanOperatorChoice) -> None:
        if not self._current_error:
            raise ApplicationError("No order issue pending resolution")

        workflow_id = workflow.info().workflow_id

        if choice in [HumanOperatorChoice.UPDATE_ORDER, HumanOperatorChoice.ACCEPT_NEW_PRICE, HumanOperatorChoice.ADJUST_QUANTITY]:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Order updated. Proceeding with payment.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._order_resolution.set()
            # Check for delays after order resolution
            await self.check_for_delays(workflow_id)
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._order_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_transport_resolution(self, choice: HumanOperatorChoice) -> None:
        if not self._current_error:
            raise ApplicationError("No transport issue pending resolution")

        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.WAIT_FOR_RESOLUTION:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Waiting for transport issue resolution.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.REROUTE_SHIPMENT:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Rerouting shipment to alternate route.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.EXPEDITE_SERVICE:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Upgrading to expedited shipping service.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._transport_resolution.set()
            # Check for delays after transport resolution
            await self.check_for_delays(workflow_id)
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._transport_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_customs_resolution(self, choice: HumanOperatorChoice) -> None:
        if not self._current_error:
            raise ApplicationError("No customs issue pending resolution")

        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.PROVIDE_DOCUMENTATION:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Additional documentation submitted to customs.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.PAY_EXPEDITED_FEE:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Expedited processing fee paid.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.ACCEPT_DELAY:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Delay accepted. Will monitor for updates.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._customs_resolution.set()
            # Check for delays after customs resolution
            await self.check_for_delays(workflow_id)
        elif choice == HumanOperatorChoice.RETURN_SHIPMENT:
            self._state = ShipmentState.CANCELED
            self._customs_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_payment_resolution(self, choice: HumanOperatorChoice) -> None:
        if self._payment_status != PaymentStatus.WAITING_FOR_RESOLUTION:
            raise ApplicationError("No payment resolution pending")

        workflow_id = workflow.info().workflow_id
        
        if choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._exit.set()
        elif choice == HumanOperatorChoice.SEND_TO_TECH_SUPPORT:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Issue sent to tech support. Will resume when fixed.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._payment_status = PaymentStatus.SUCCESS
            self._state = ShipmentState.PAYMENT_RECEIVED
            self._payment_resolution.set()
            # Check for delays after payment resolution
            await self.check_for_delays(workflow_id)
        elif choice == HumanOperatorChoice.RETRY_PAYMENT:
            self._payment_retries = 0
            self._payment_status = PaymentStatus.PENDING
            self._payment_resolution.set()
        elif choice == HumanOperatorChoice.RESUME_WHEN_READY:
            self._payment_status = PaymentStatus.SUCCESS
            self._state = ShipmentState.PAYMENT_RECEIVED
            self._payment_resolution.set()

    @workflow.signal
    async def handle_delay_resolution(self, choice: HumanOperatorChoice) -> None:
        """Handle resolution for random delays that can occur after any stage."""
        if not self._current_error:
            raise ApplicationError("No delay issue pending resolution")

        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.NOTIFY_ALL_PARTIES:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Notifying all parties and adjusting schedules.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._delay_resolution.set()
        elif choice == HumanOperatorChoice.NO_ACTION_NEEDED:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "No immediate action needed. Continuing with current schedule.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._delay_resolution.set()

    async def check_for_delays(self, workflow_id: str) -> None:
        """Check for random delays that can occur after any stage."""
        # Skip delay checks for completed or cancelled workflows
        if self._state in [ShipmentState.DELIVERED, ShipmentState.CANCELED]:
            return

        ok, error_details = await workflow.execute_activity(
            monitor_shipment_status,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        if not ok:
            self._current_error = error_details
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[workflow_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    workflow_id,
                    f"Delay detected: {error_details.details}\n"
                    f"ETA Impact: {error_details.eta_impact.days} days\n"
                    f"Options:\n" + "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            # Auto-resolve delays to keep workflow moving
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "Auto-resolving delay: No immediate action needed.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._delay_resolution = asyncio.Event()

    @workflow.signal
    def cancel_shipment(self) -> None:
        if self._state in [ShipmentState.DELIVERED, ShipmentState.CANCELED]:
            raise ApplicationError(f"Cannot cancel shipment in state {self._state}")
        
        self._state = ShipmentState.CANCELED
        self._exit.set()

    @workflow.query
    def get_status(self) -> ShipmentState:
        return self._state

    @workflow.query
    def get_delivery_update(self) -> DeliveryUpdate | None:
        return self._delivery_update
