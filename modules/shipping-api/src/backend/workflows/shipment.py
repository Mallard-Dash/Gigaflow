import asyncio
import random
from datetime import timedelta, datetime
from enum import Enum

from pydantic import BaseModel
from temporalio import activity, workflow
from temporalio.exceptions import ApplicationError

from ..utils.log import get_logger

logger = get_logger(__name__)


#### Enums ####


class OrderErrorReason(str, Enum):
    PRICE_MISMATCH = "PRICE_MISMATCH"
    INVALID_ITEMS = "INVALID_ITEMS"
    QUANTITY_ERROR = "QUANTITY_ERROR"


class PaymentErrorReason(str, Enum):
    NETWORK_ERROR = "NETWORK_ERROR"
    RECEIVER_ERROR = "RECEIVER_ERROR"
    SENDER_ERROR = "SENDER_ERROR"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    BANK_SERVER_DOWN = "BANK_SERVER_DOWN"
    TRANSACTION_ERROR = "TRANSACTION_ERROR"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    WAITING_FOR_RESOLUTION = "WAITING_FOR_RESOLUTION"


class ShipmentState(str, Enum):
    ORDER_RECEIVED = "ORDER_RECEIVED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    WAREHOUSE_ALLOCATION = "WAREHOUSE_ALLOCATION"
    PACKAGED = "PACKAGED"
    TRANSPORT_STARTED = "TRANSPORT_STARTED"
    CUSTOMS_CLEARANCE = "CUSTOMS_CLEARANCE"
    LOCAL_DELIVERY = "LOCAL_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELED = "CANCELED"


class HumanOperatorChoice(str, Enum):
    # Payment choices
    SEND_TO_TECH_SUPPORT = "SEND_TO_TECH_SUPPORT"
    RETRY_PAYMENT = "RETRY_PAYMENT"
    RESUME_WHEN_READY = "RESUME_WHEN_READY"
    CANCEL_ORDER = "CANCEL_ORDER"
    # Order validation choices
    ACCEPT_NEW_PRICE = "ACCEPT_NEW_PRICE"
    UPDATE_ORDER = "UPDATE_ORDER"
    ADJUST_QUANTITY = "ADJUST_QUANTITY"
    # Warehouse choices
    ALLOCATE_DIFFERENT = "ALLOCATE_DIFFERENT"
    WAIT_FOR_STOCK = "WAIT_FOR_STOCK"
    # Transport choices
    NOTICE_CUSTOMERS_REFUND = "NOTICE_CUSTOMERS_REFUND"
    WAIT_OUT_WEATHER = "WAIT_OUT_WEATHER"
    REROUTE_SHIPMENT = "REROUTE_SHIPMENT"
    # Customs choices
    PROVIDE_DOCUMENTATION = "PROVIDE_DOCUMENTATION"
    PAY_EXPEDITED_FEE = "PAY_EXPEDITED_FEE"
    ACCEPT_DELAY = "ACCEPT_DELAY"
    RETURN_SHIPMENT = "RETURN_SHIPMENT"
    # Delivery choices
    SCHEDULE_NEW_TIME = "SCHEDULE_NEW_TIME"
    LEAVE_SAFE_LOCATION = "LEAVE_SAFE_LOCATION"
    RETURN_TO_DEPOT = "RETURN_TO_DEPOT"
    # Delay resolution choices
    DO_NOTHING = "DO_NOTHING"
    INFORM_CUSTOMERS = "INFORM_CUSTOMERS"
    REARRANGE_LOGISTICS = "REARRANGE_LOGISTICS"


class DelayReason(str, Enum):
    LOGISTICS_DELAY = "LOGISTICS_DELAY"
    WEATHER_IMPACT = "WEATHER_IMPACT"
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    RESOURCE_SHORTAGE = "RESOURCE_SHORTAGE"
    TECHNICAL_ISSUES = "TECHNICAL_ISSUES"


#### Models ####


class PaymentError(BaseModel):
    reason: PaymentErrorReason
    details: str


class ShipmentInput(BaseModel):
    shipment_id: str
    order_details: dict
    payment_info: dict
    simulate_payment_failure: bool = False


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
async def update_shipment_state(shipment_id: str, state: ShipmentState) -> None:
    """Update the shipment state in the external system."""
    logger.info(f"🔄 Updating shipment {shipment_id} to state {state.value}")
    await asyncio.sleep(0.5)
    logger.info(f"✅ Successfully updated shipment {shipment_id} to state {state.value}")


@activity.defn
async def validate_order(order_details: dict) -> tuple[bool, ErrorDetails | None]:
    """Validate order - 100% failure for price-mismatch scenario."""
    logger.info("📋 Validating order details...")
    await asyncio.sleep(1)

    if order_details.get("simulate_validation_failure", False):
        logger.warning("⚠️ Order validation failed: Price mismatch detected")
        return False, ErrorDetails(
            reason="PRICE_MISMATCH",
            details="Price has changed since order placement - increased by 15%",
            resolution_options=[
                "Accept new price",
                "Update order with available items",
                "Adjust quantity",
                "Cancel order",
            ],
        )

    logger.info("✅ Order validation successful")
    return True, None


@activity.defn
async def verify_payment(
    payment_info: dict, simulate_failure: bool = False, retry_count: int = 0
) -> tuple[PaymentStatus, PaymentError | None]:
    """Verify payment - 100% failure on first attempt, 80% on retries for failure scenarios."""
    logger.info(f"💳 Verifying payment (attempt #{retry_count + 1})...")
    await asyncio.sleep(1)

    if not simulate_failure:
        logger.info("✅ Payment verification successful")
        return PaymentStatus.SUCCESS, None

    # 100% failure on first attempt, 80% failure on retries (attempts 2-3)
    failure_chance = 1.0 if retry_count == 0 else 0.8

    if random.random() < failure_chance:
        # Randomly select error type
        error_reasons = list(PaymentErrorReason)
        error_reason = random.choice(error_reasons)
        error_details_map = {
            PaymentErrorReason.NETWORK_ERROR: "Unable to connect to payment gateway",
            PaymentErrorReason.RECEIVER_ERROR: "Receiving bank system error",
            PaymentErrorReason.SENDER_ERROR: "Sending bank system error",
            PaymentErrorReason.INSUFFICIENT_FUNDS: "Insufficient funds in account",
            PaymentErrorReason.BANK_SERVER_DOWN: "Bank servers are currently unavailable",
            PaymentErrorReason.TRANSACTION_ERROR: "Error processing transaction",
        }

        logger.warning(f"❌ Payment verification failed: {error_details_map[error_reason]}")
        return PaymentStatus.FAILED, PaymentError(
            reason=error_reason, details=error_details_map[error_reason]
        )

    logger.info("✅ Payment verification successful (after retry)")
    return PaymentStatus.SUCCESS, None


@activity.defn
async def check_warehouse_allocation(
    shipment_id: str, order_details: dict
) -> WarehouseAllocationInput:
    """Check warehouse stock - 100% failure for warehouse-stock scenario."""
    logger.info(f"🏭 Checking warehouse allocation for shipment {shipment_id}")
    await asyncio.sleep(1)

    if order_details.get("simulate_stock_issue", False):
        logger.warning("⚠️ Insufficient stock in primary warehouse")
        return WarehouseAllocationInput(
            warehouse_id="WH001",
            stock_available=False,
            alternative_warehouses=["WH002 (Tokyo)", "WH003 (Singapore)"],
        )

    logger.info("✅ Stock available in warehouse WH001")
    return WarehouseAllocationInput(
        warehouse_id="WH001", stock_available=True, alternative_warehouses=[]
    )


@activity.defn
async def check_transport_status(
    shipment_id: str, order_details: dict
) -> tuple[bool, ErrorDetails | None]:
    """Check transport - 100% failure for transport-delay scenario."""
    logger.info(f"🚢 Checking transport status for shipment {shipment_id}")
    await asyncio.sleep(1)

    if order_details.get("simulate_transport_delay", False):
        delay_days = random.randint(2, 5)
        logger.warning("⚠️ Transport issue: Severe storm in Shanghai port")
        return False, ErrorDetails(
            reason="WEATHER_DELAY",
            details="Severe storm in Shanghai port - ship cannot depart due to dangerous conditions",
            eta_impact=timedelta(days=delay_days),
            resolution_options=[
                "Notice customers and offer refunds",
                "Do nothing and wait out bad weather (pause workflow)",
                "Reroute shipment from unaffected supplier (high cost)",
            ],
        )

    logger.info("✅ Transport status OK - departure on schedule")
    return True, None


@activity.defn
async def check_customs_status(
    shipment_id: str, order_details: dict
) -> tuple[bool, ErrorDetails | None]:
    """Check customs - 100% failure for customs-issue scenario."""
    logger.info(f"🛂 Checking customs status for shipment {shipment_id}")
    await asyncio.sleep(1)

    if order_details.get("simulate_customs_issue", False):
        delay_days = random.randint(2, 4)
        logger.warning("⚠️ Customs issue: Missing documentation")
        return False, ErrorDetails(
            reason="DOCUMENTATION_MISSING",
            details="Required customs documentation missing - certificate of origin not attached",
            eta_impact=timedelta(days=delay_days),
            resolution_options=[
                "Provide additional documentation",
                "Pay expedited processing fee",
                "Accept delay",
                "Return shipment",
            ],
        )

    logger.info("✅ Customs clearance approved")
    return True, None


@activity.defn
async def check_delivery_status(
    shipment_id: str, order_details: dict
) -> tuple[bool, ErrorDetails | None]:
    """Check delivery - 100% failure for delivery-delay scenario."""
    logger.info(f"🚚 Checking delivery status for shipment {shipment_id}")
    await asyncio.sleep(1)

    if order_details.get("simulate_delivery_delay", False):
        delay_hours = random.randint(12, 48)
        logger.warning("⚠️ Delivery issue: Recipient unavailable")
        return False, ErrorDetails(
            reason="RECIPIENT_UNAVAILABLE",
            details="Recipient not available at delivery address - multiple attempts failed",
            eta_impact=timedelta(hours=delay_hours),
            resolution_options=[
                "Schedule new delivery time",
                "Leave at safe location",
                "Return to depot for pickup",
                "Cancel delivery",
            ],
        )

    logger.info("✅ Delivery confirmed - recipient available")
    return True, None


@activity.defn
async def monitor_shipment_status(
    shipment_id: str, state: ShipmentState
) -> tuple[bool, ErrorDetails | None]:
    """Monitor for random delays - 20% chance after main issue resolved."""
    logger.info(f"🔍 Monitoring shipment {shipment_id} in state {state}")
    await asyncio.sleep(0.5)

    # 15% chance of random delay
    if random.random() < 0.15:
        delay_reasons = list(DelayReason)
        delay_reason = random.choice(delay_reasons)
        delay_hours = random.randint(1, 48)  # 1 hour to 2 days

        delay_details_map = {
            DelayReason.LOGISTICS_DELAY: f"Unexpected {delay_hours}h delay at logistics hub",
            DelayReason.WEATHER_IMPACT: f"Weather conditions causing {delay_hours}h delay",
            DelayReason.TRAFFIC_CONGESTION: f"Heavy traffic causing {delay_hours}h delay",
            DelayReason.RESOURCE_SHORTAGE: f"Resource constraints causing {delay_hours}h delay",
            DelayReason.TECHNICAL_ISSUES: f"Technical issues causing {delay_hours}h delay",
        }

        logger.warning(f"⚠️ Random delay detected: {delay_details_map[delay_reason]}")
        return False, ErrorDetails(
            reason=delay_reason.value,
            details=delay_details_map[delay_reason],
            eta_impact=timedelta(hours=delay_hours),
            resolution_options=[
                "Do nothing (small delay)",
                "Inform customers",
                "Contact and rearrange logistics-hub timeslots",
            ],
        )

    logger.info("✅ No delays detected")
    return True, None


@activity.defn
async def update_delivery_estimate(
    shipment_id: str, state: ShipmentState, error_details: ErrorDetails | None = None
) -> DeliveryUpdate:
    """Update delivery estimation."""
    logger.info(f"📅 Updating delivery estimate for shipment {shipment_id}")
    await asyncio.sleep(0.5)

    base_date = datetime.now() + timedelta(days=7)

    if error_details and error_details.eta_impact:
        new_date = base_date + error_details.eta_impact
        logger.info(
            f"⏰ ETA updated: {base_date.strftime('%Y-%m-%d')} → {new_date.strftime('%Y-%m-%d')}"
        )
        return DeliveryUpdate(
            estimated_delivery_date=base_date.strftime("%Y-%m-%d"),
            original_eta=base_date.strftime("%Y-%m-%d"),
            status="DELAYED",
            issues=[error_details.details],
            delay_reason=error_details.reason,
            new_eta=new_date.strftime("%Y-%m-%d"),
        )

    logger.info(f"✅ ETA: {base_date.strftime('%Y-%m-%d')} (On time)")
    return DeliveryUpdate(
        estimated_delivery_date=base_date.strftime("%Y-%m-%d"), status="ON_TIME", issues=[]
    )


@activity.defn
async def notify_human_operator(
    shipment_id: str, message: str, action_required: bool = False
) -> None:
    """Notify human operator about issues or status updates."""
    prefix = "🔔 [ACTION REQUIRED]" if action_required else "ℹ️  [INFO]"
    logger.info(f"{prefix} Shipment {shipment_id}: {message}")
    await asyncio.sleep(0.3)


#### Workflow ####


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
        self._warehouse_resolution = asyncio.Event()
        self._transport_resolution = asyncio.Event()
        self._customs_resolution = asyncio.Event()
        self._delivery_resolution = asyncio.Event()

    @workflow.run
    async def run(self, input: ShipmentInput) -> ShipmentResponse:
        workflow_id = workflow.info().workflow_id
        self._input = input

        logger.info(f"🚀 Starting shipment workflow for {workflow_id}")

        # Step 1: Order received and validation
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
                    f"❌ Order validation failed: {error_details.details}\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._order_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                logger.info(f"🚫 Workflow cancelled for {workflow_id}")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)

        # Check for random delays after order validation
        await self._check_for_random_delays(input.shipment_id)

        # Step 2: Payment verification with retries (up to 3 attempts, 80% failure on retries)
        while (
            self._payment_retries < 3
            and self._payment_status
            not in [PaymentStatus.SUCCESS, PaymentStatus.WAITING_FOR_RESOLUTION]
        ):
            self._payment_status, self._payment_error = await workflow.execute_activity(
                verify_payment,
                args=[input.payment_info, input.simulate_payment_failure, self._payment_retries],
                start_to_close_timeout=timedelta(seconds=30),
            )

            if self._payment_status == PaymentStatus.FAILED:
                self._payment_retries += 1
                if self._payment_retries == 3:
                    # After 3 failed attempts
                    if (
                        self._payment_error
                        and self._payment_error.reason == PaymentErrorReason.INSUFFICIENT_FUNDS
                    ):
                        # Auto-cancel for insufficient funds
                        await workflow.execute_activity(
                            notify_human_operator,
                            args=[
                                input.shipment_id,
                                f"🚫 Order automatically cancelled: {self._payment_error.details}",
                                False,
                            ],
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        self._state = ShipmentState.CANCELED
                        self._exit.set()
                        logger.info(f"🚫 Workflow cancelled due to insufficient funds")
                        return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)
                    else:
                        # Other payment errors - request human intervention
                        self._payment_status = PaymentStatus.WAITING_FOR_RESOLUTION
                        self._current_error = ErrorDetails(
                            reason=self._payment_error.reason.value if self._payment_error else "PAYMENT_ERROR",
                            details=f"Payment failed after 3 attempts: {self._payment_error.details if self._payment_error else 'Unknown error'}",
                            resolution_options=[
                                "Send to tech support",
                                "Retry payment",
                                "Resume when system is ready",
                                "Cancel order"
                            ]
                        )
                        await workflow.execute_activity(
                            notify_human_operator,
                            args=[
                                input.shipment_id,
                                f"⚠️ Payment failed after 3 attempts: {self._payment_error.details if self._payment_error else 'Unknown error'}\n"
                                "📋 Available options:\n"
                                "  1. Send to tech support\n"
                                "  2. Retry payment\n"
                                "  3. Resume when system is ready\n"
                                "  4. Cancel order",
                                True,
                            ],
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        await self._payment_resolution.wait()
                        if self._state == ShipmentState.CANCELED:
                            logger.info(f"🚫 Workflow cancelled by operator")
                            return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)
                else:
                    logger.info(f"🔄 Retrying payment (attempt {self._payment_retries + 1}/3)...")
                    await asyncio.sleep(2)
            else:
                self._state = ShipmentState.PAYMENT_RECEIVED
                await workflow.execute_activity(
                    update_shipment_state,
                    args=[input.shipment_id, self._state],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                # Check for random delays after payment success
                await self._check_for_random_delays(input.shipment_id)

        # Step 3: Warehouse allocation
        self._state = ShipmentState.WAREHOUSE_ALLOCATION
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        allocation = await workflow.execute_activity(
            check_warehouse_allocation,
            args=[input.shipment_id, input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not allocation.stock_available:
            self._current_error = ErrorDetails(
                reason="INSUFFICIENT_STOCK",
                details=f"Insufficient stock in primary warehouse",
                resolution_options=[
                    "Allocate from different warehouse",
                    "Cancel order and reorder from another supplier",
                    "Wait for stock to be replenished"
                ]
            )
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    input.shipment_id,
                    f"⚠️ Insufficient stock in primary warehouse\n"
                    f"📦 Alternative warehouses: {', '.join(allocation.alternative_warehouses)}\n"
                    "📋 Available options:\n"
                    "  1. Allocate from different warehouse\n"
                    "  2. Cancel order and reorder from another supplier\n"
                    "  3. Wait for stock to be replenished",
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._warehouse_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                logger.info(f"🚫 Workflow cancelled")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)

        self._state = ShipmentState.PACKAGED
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )
        await self._check_for_random_delays(input.shipment_id)

        # Step 4: Transport
        self._state = ShipmentState.TRANSPORT_STARTED
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        ok, error_details = await workflow.execute_activity(
            check_transport_status,
            args=[input.shipment_id, input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not ok:
            self._current_error = error_details
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[input.shipment_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    input.shipment_id,
                    f"⚠️ Transport issue: {error_details.details}\n"
                    f"⏰ ETA Impact: +{error_details.eta_impact.days} days\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._transport_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                logger.info(f"🚫 Workflow cancelled")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)
        else:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[input.shipment_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )

        await self._check_for_random_delays(input.shipment_id)

        # Step 5: Customs clearance
        self._state = ShipmentState.CUSTOMS_CLEARANCE
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        ok, error_details = await workflow.execute_activity(
            check_customs_status,
            args=[input.shipment_id, input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not ok:
            self._current_error = error_details
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[input.shipment_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    input.shipment_id,
                    f"⚠️ Customs issue: {error_details.details}\n"
                    f"⏰ ETA Impact: +{error_details.eta_impact.days} days\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._customs_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                logger.info(f"🚫 Workflow cancelled")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)
        else:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[input.shipment_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )

        await self._check_for_random_delays(input.shipment_id)

        # Step 6: Local delivery
        self._state = ShipmentState.LOCAL_DELIVERY
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        ok, error_details = await workflow.execute_activity(
            check_delivery_status,
            args=[input.shipment_id, input.order_details],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not ok:
            self._current_error = error_details
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[input.shipment_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    input.shipment_id,
                    f"⚠️ Delivery issue: {error_details.details}\n"
                    f"⏰ ETA Impact: +{error_details.eta_impact.total_seconds() // 3600:.0f} hours\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._delivery_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                logger.info(f"🚫 Workflow cancelled")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)
        else:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[input.shipment_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )

        await self._check_for_random_delays(input.shipment_id)

        # Step 7: Delivered
        self._state = ShipmentState.DELIVERED
        await workflow.execute_activity(
            update_shipment_state,
            args=[input.shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        await workflow.execute_activity(
            notify_human_operator,
            args=[input.shipment_id, "📦 Shipment completed!", False],
            start_to_close_timeout=timedelta(seconds=10),
        )

        logger.info(f"✅ Workflow completed - Final state: {self._state}")
        return ShipmentResponse(shipment_id=input.shipment_id, state=self._state)

    async def _check_for_random_delays(self, shipment_id: str) -> None:
        """Check for random delays (50% chance) that can occur after any stage."""
        if self._state in [ShipmentState.DELIVERED, ShipmentState.CANCELED]:
            return

        ok, error_details = await workflow.execute_activity(
            monitor_shipment_status,
            args=[shipment_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        if not ok and error_details:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[shipment_id, self._state, error_details],
                start_to_close_timeout=timedelta(seconds=10),
            )

            delay_hours = error_details.eta_impact.total_seconds() / 3600 if error_details.eta_impact else 0
            
            if delay_hours > 1:
                # Significant delay - require human decision
                self._current_error = error_details
                await workflow.execute_activity(
                    notify_human_operator,
                    args=[
                        shipment_id,
                        f"⚠️ Shipment delayed: {error_details.details}\n"
                        f"⏰ ETA Impact: +{delay_hours:.1f} hours\n"
                        f"📋 Available options:\n"
                        + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                        True,
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                # Create a delay resolution event and wait
                delay_resolution = asyncio.Event()
                self._delay_resolution = delay_resolution
                await delay_resolution.wait()
                self._current_error = None
            else:
                # Small delay - auto-resolve
                delay_minutes = error_details.eta_impact.total_seconds() / 60 if error_details.eta_impact else 0
                await workflow.execute_activity(
                    notify_human_operator,
                    args=[
                        shipment_id,
                        f"ℹ️ ETA changed by {delay_minutes:.0f} minutes due to {error_details.reason}. Issue auto-resolved.",
                        False,
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                )

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
                    f"⚠️ Insufficient stock in primary warehouse\n"
                    f"📦 Alternative warehouses: {', '.join(allocation.alternative_warehouses)}\n"
                    "📋 Available options:\n"
                    "  1. Allocate from different warehouse\n"
                    "  2. Cancel order and reorder from another supplier\n"
                    "  3. Wait for stock to be replenished",
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._warehouse_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                return

        self._state = ShipmentState.PACKAGED
        await workflow.execute_activity(
            update_shipment_state,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )
        
        # Check for random delays after warehouse allocation
        await self._check_for_random_delays(workflow_id)

    @workflow.signal
    async def start_transport(self) -> None:
        if self._state != ShipmentState.PACKAGED:
            raise ApplicationError(f"Cannot start transport in state {self._state}")

        self._state = ShipmentState.TRANSPORT_STARTED
        workflow_id = workflow.info().workflow_id

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
                    f"⚠️ Transport issue: {error_details.details}\n"
                    f"⏰ ETA Impact: +{error_details.eta_impact.days} days\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
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

        await workflow.execute_activity(
            update_shipment_state,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Check for random delays after transport
        await self._check_for_random_delays(workflow_id)

    @workflow.signal
    async def update_customs_status(self) -> None:
        if self._state != ShipmentState.TRANSPORT_STARTED:
            raise ApplicationError(f"Cannot update customs status in state {self._state}")

        self._state = ShipmentState.CUSTOMS_CLEARANCE
        workflow_id = workflow.info().workflow_id

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
                    f"⚠️ Customs issue: {error_details.details}\n"
                    f"⏰ ETA Impact: +{error_details.eta_impact.days} days\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
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

        await workflow.execute_activity(
            update_shipment_state,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Check for random delays after customs
        await self._check_for_random_delays(workflow_id)

    @workflow.signal
    async def start_local_delivery(self) -> None:
        if self._state != ShipmentState.CUSTOMS_CLEARANCE:
            raise ApplicationError(f"Cannot start local delivery in state {self._state}")

        self._state = ShipmentState.LOCAL_DELIVERY
        workflow_id = workflow.info().workflow_id

        ok, error_details = await workflow.execute_activity(
            check_delivery_status,
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
                    f"⚠️ Delivery issue: {error_details.details}\n"
                    f"⏰ ETA Impact: +{error_details.eta_impact.total_seconds() // 3600:.0f} hours\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await self._delivery_resolution.wait()
            if self._state == ShipmentState.CANCELED:
                return
        else:
            self._delivery_update = await workflow.execute_activity(
                update_delivery_estimate,
                args=[workflow_id, self._state],
                start_to_close_timeout=timedelta(seconds=10),
            )

        await workflow.execute_activity(
            update_shipment_state,
            args=[workflow_id, self._state],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Check for random delays after delivery starts
        await self._check_for_random_delays(workflow_id)

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

        await workflow.execute_activity(
            notify_human_operator,
            args=[workflow_id, "📦 Shipment completed!", False],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Workflow completed - set exit event to terminate workflow
        self._exit.set()

    @workflow.signal
    async def handle_order_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice in [HumanOperatorChoice.ACCEPT_NEW_PRICE, HumanOperatorChoice.UPDATE_ORDER, HumanOperatorChoice.ADJUST_QUANTITY]:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, f"✅ Order updated: {choice.value}. Proceeding to payment.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._order_resolution.set()
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._order_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_warehouse_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.ALLOCATE_DIFFERENT:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "✅ Allocating from alternative warehouse.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._warehouse_resolution.set()
        elif choice == HumanOperatorChoice.WAIT_FOR_STOCK:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "⏳ Waiting for stock replenishment.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._warehouse_resolution.set()
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._current_error = None
            self._warehouse_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_transport_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.WAIT_OUT_WEATHER:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "⏳ Pausing - waiting for weather to clear.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.REROUTE_SHIPMENT:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "🔄 Rerouting via alternative supplier (+$500).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.NOTICE_CUSTOMERS_REFUND:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "📧 Notifying customers with refund option.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._transport_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_customs_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.PROVIDE_DOCUMENTATION:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "📄 Documentation submitted to customs.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.PAY_EXPEDITED_FEE:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "💰 Expedited fee paid (+$200).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.ACCEPT_DELAY:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "⏳ Delay accepted. Monitoring progress.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.RETURN_SHIPMENT:
            self._state = ShipmentState.CANCELED
            self._customs_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_delivery_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._current_error = None
            self._delivery_resolution.set()
            self._exit.set()
        else:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, f"✅ Delivery resolved: {choice.value}", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._delivery_resolution.set()

    @workflow.signal
    async def handle_payment_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.CANCEL_ORDER:
            self._state = ShipmentState.CANCELED
            self._current_error = None
            self._exit.set()
        elif choice == HumanOperatorChoice.SEND_TO_TECH_SUPPORT:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "🔧 Escalated to tech support. Payment will be processed manually.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._payment_status = PaymentStatus.SUCCESS
            self._state = ShipmentState.PAYMENT_RECEIVED
            self._current_error = None
            self._payment_resolution.set()
        elif choice == HumanOperatorChoice.RETRY_PAYMENT:
            self._payment_retries = 0
            self._payment_status = PaymentStatus.PENDING
            self._current_error = None
            self._payment_resolution.set()
        elif choice == HumanOperatorChoice.RESUME_WHEN_READY:
            self._payment_status = PaymentStatus.SUCCESS
            self._state = ShipmentState.PAYMENT_RECEIVED
            self._current_error = None
            self._payment_resolution.set()
    
    @workflow.signal
    async def handle_delay_resolution(self, choice: HumanOperatorChoice) -> None:
        """Handle random delay resolutions."""
        workflow_id = workflow.info().workflow_id
        
        if choice == HumanOperatorChoice.DO_NOTHING:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "✅ Delay accepted. Continuing workflow.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
        elif choice == HumanOperatorChoice.INFORM_CUSTOMERS:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "📧 Customers notified about delay.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
        elif choice == HumanOperatorChoice.REARRANGE_LOGISTICS:
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "📞 Logistics hub contacted. Timeslots rearranged.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
        
        self._current_error = None
        if hasattr(self, '_delay_resolution'):
            self._delay_resolution.set()

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
    
    @workflow.query
    def get_current_error(self) -> ErrorDetails | None:
        """Get current error requiring human intervention."""
        return self._current_error
