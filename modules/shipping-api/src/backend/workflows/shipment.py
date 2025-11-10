import asyncio
import random  # Used only in activities, NOT in workflows
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
    CRITICAL_HALT = "CRITICAL_HALT"


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


class ResolutionOption(BaseModel):
    """Enhanced resolution option with cost and time impact."""
    text: str
    cost: str = "$0"  # e.g. "$0", "$200", "$500"
    time_impact: str = "No delay"  # e.g. "No delay", "+2 days", "+24 hours"


class ErrorDetails(BaseModel):
    reason: str
    details: str
    eta_impact: timedelta | None = None
    resolution_options: list[str] = []  # Legacy support
    enhanced_options: list[ResolutionOption] = []  # Enhanced options with cost/time
    backup_warehouse_capacity_hours: int | None = None  # Random 5-48 hours


class DeliveryUpdate(BaseModel):
    estimated_delivery_date: str
    original_eta: str | None = None
    status: str
    issues: list[str] = []
    delay_reason: str | None = None
    new_eta: str | None = None


class WorkflowSummary(BaseModel):
    """Comprehensive workflow summary with cost and time analysis."""
    total_cost: float = 0.0  # Total cost in dollars
    time_saved_hours: float = 0.0  # Negative if delayed
    production_line_stopped: bool = False
    production_stop_duration_hours: float = 0.0
    production_loss_cost: float = 0.0  # Cost due to production stoppage
    decisions_made: list[str] = []  # List of HITL decisions
    avoided_production_stop: bool = False  # True if expensive option avoided stoppage
    final_status: str = "COMPLETED"


class ShipmentResponse(BaseModel):
    shipment_id: str
    state: ShipmentState
    summary: WorkflowSummary | None = None


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
            enhanced_options=[
                ResolutionOption(text="Notice customers and offer refunds", cost="$0", time_impact=f"+{delay_days} days delay"),
                ResolutionOption(text="Do nothing and wait out bad weather (pause workflow)", cost="$0", time_impact=f"+{delay_days} days delay"),
                ResolutionOption(text="Reroute shipment from unaffected supplier (high cost)", cost="$500", time_impact="+1 day"),
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
                "Reroute from another supplier (more expensive, but faster)",
            ],
            enhanced_options=[
                ResolutionOption(text="Provide additional documentation", cost="$0", time_impact="+1 day"),
                ResolutionOption(text="Pay expedited processing fee", cost="$200", time_impact="+4 hours"),
                ResolutionOption(text="Accept delay", cost="$0", time_impact=f"+{delay_days} days"),
                ResolutionOption(text="Reroute from another supplier (more expensive, but faster)", cost="$800", time_impact="+12 hours"),
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
            enhanced_options=[
                ResolutionOption(text="Schedule new delivery time", cost="$0", time_impact=f"+{delay_hours}h"),
                ResolutionOption(text="Leave at safe location", cost="$0", time_impact="Immediate"),
                ResolutionOption(text="Return to depot for pickup", cost="$25", time_impact="Customer pickup"),
                ResolutionOption(text="Cancel delivery", cost="$0", time_impact="Immediate"),
            ],
        )

    logger.info("✅ Delivery confirmed - recipient available")
    return True, None


# DISABLED: Random events feature removed per user request
# @activity.defn
# async def monitor_shipment_status(
#     shipment_id: str, state: ShipmentState
# ) -> tuple[bool, ErrorDetails | None]:
#     """Monitor for random delays - DISABLED."""
#     return True, None


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
        
        # Tracking state for summary
        self._summary = WorkflowSummary()
        self._original_eta_hours: float = 168.0  # 7 days baseline
        self._workflow_paused = asyncio.Event()
        self._pause_requested = False
        self._workflow_start_time: datetime | None = None

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
                            ],
                            enhanced_options=[
                                ResolutionOption(text="Send to tech support", cost="$50", time_impact="+2-4 hours"),
                                ResolutionOption(text="Retry payment", cost="$0", time_impact="+5 min"),
                                ResolutionOption(text="Resume when system is ready", cost="$0", time_impact="Pause workflow"),
                                ResolutionOption(text="Cancel order", cost="$0", time_impact="Immediate")
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
            backup_capacity = int(workflow.random().random() * 43) + 5  # Random 5-48 hours
            self._current_error = ErrorDetails(
                reason="INSUFFICIENT_STOCK",
                details=f"Insufficient stock in primary warehouse",
                resolution_options=[
                    "Allocate from different warehouse",
                    "Cancel order and reorder from another supplier",
                    "Wait for stock to be replenished"
                ],
                enhanced_options=[
                    ResolutionOption(text="Allocate from different warehouse", cost="$150", time_impact="+1 day"),
                    ResolutionOption(text="Cancel order and reorder from another supplier", cost="$0", time_impact="Immediate"),
                    ResolutionOption(text="Wait for stock to be replenished", cost="$0", time_impact="+3-5 days")
                ],
                backup_warehouse_capacity_hours=backup_capacity
            )
            await workflow.execute_activity(
                notify_human_operator,
                args=[
                    input.shipment_id,
                    f"⚠️ Insufficient stock in primary warehouse\n"
                    f"📦 Alternative warehouses: {', '.join(allocation.alternative_warehouses)}\n"
                    f"⏱️  Production line capacity remaining: {backup_capacity} hours\n"
                    "📋 Available options:\n"
                    "  1. Allocate from different warehouse\n"
                    "  2. Cancel order and reorder from another supplier\n"
                    "  3. Wait for stock to be replenished",
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            # Race between human resolution and 15-second HARD DEADLINE
            HITL_DEADLINE_SECONDS = 15
            try:
                await asyncio.wait_for(
                    self._warehouse_resolution.wait(),
                    timeout=HITL_DEADLINE_SECONDS
                )
            except asyncio.TimeoutError:
                # CRITICAL FAILURE - LINE HALTED!
                self._summary.production_line_stopped = True
                self._summary.production_stop_duration_hours = float(backup_capacity)
                self._summary.production_loss_cost = backup_capacity * 60 * 100  # $100/minute
                
                await workflow.execute_activity(
                    notify_human_operator,
                    args=[
                        input.shipment_id,
                        f"🚨 CRITICAL FAILURE! **LINE HALTED.** Deadline missed. Workflow terminated.\n"
                        f"⏱️  15-second deadline expired - no human response received\n"
                        f"💰 Production loss: ${self._summary.production_loss_cost:,.2f}\n"
                        f"🏭 Factory shutdown triggered!",
                        True,
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                self._state = ShipmentState.CRITICAL_HALT
                self._summary.final_status = "CRITICAL_HALT"
                logger.error(f"🚨 CRITICAL FAILURE! LINE HALTED. Deadline missed. Workflow terminated.")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state, summary=self._summary)
            
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
                    f"⏱️  15-second deadline for HITL response\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            # Race between human resolution and 15-second HARD DEADLINE
            try:
                await asyncio.wait_for(
                    self._transport_resolution.wait(),
                    timeout=15
                )
            except asyncio.TimeoutError:
                # CRITICAL FAILURE - LINE HALTED!
                await workflow.execute_activity(
                    notify_human_operator,
                    args=[
                        input.shipment_id,
                        f"🚨 CRITICAL FAILURE! **LINE HALTED.** Deadline missed. Workflow terminated.",
                        True,
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                self._state = ShipmentState.CRITICAL_HALT
                self._summary.final_status = "CRITICAL_HALT"
                logger.error(f"🚨 CRITICAL FAILURE! LINE HALTED. Deadline missed. Workflow terminated.")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state, summary=self._summary)
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
                    f"⏱️  15-second deadline for HITL response\n"
                    f"📋 Available options:\n"
                    + "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(error_details.resolution_options)),
                    True,
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )
            
            # Race between human resolution and 15-second HARD DEADLINE
            try:
                await asyncio.wait_for(
                    self._customs_resolution.wait(),
                    timeout=15
                )
            except asyncio.TimeoutError:
                # CRITICAL FAILURE - LINE HALTED!
                await workflow.execute_activity(
                    notify_human_operator,
                    args=[
                        input.shipment_id,
                        f"🚨 CRITICAL FAILURE! **LINE HALTED.** Deadline missed. Workflow terminated.",
                        True,
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                )
                self._state = ShipmentState.CRITICAL_HALT
                self._summary.final_status = "CRITICAL_HALT"
                logger.error(f"🚨 CRITICAL FAILURE! LINE HALTED. Deadline missed. Workflow terminated.")
                return ShipmentResponse(shipment_id=input.shipment_id, state=self._state, summary=self._summary)
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
        """DISABLED: Random events feature removed per user request."""
        # No-op: Random delays have been disabled
        return

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
            # Track decision: $150 cost, +1 day delay
            self._track_decision("Allocate from different warehouse", cost=150.0, time_impact_hours=-24.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "✅ Allocating from alternative warehouse (+$150, +1 day).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._warehouse_resolution.set()
        elif choice == HumanOperatorChoice.WAIT_FOR_STOCK:
            # Track decision: $0 cost, +3-5 days delay (use average 4 days)
            self._track_decision("Wait for stock replenishment", cost=0.0, time_impact_hours=-96.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "⏳ Waiting for stock replenishment (+3-5 days).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._warehouse_resolution.set()
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._track_decision("Cancel order", cost=0.0, time_impact_hours=0.0)
            self._state = ShipmentState.CANCELED
            self._current_error = None
            self._warehouse_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_transport_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.WAIT_OUT_WEATHER:
            # Track: $0 cost, delay varies (2-5 days)
            self._track_decision("Wait out bad weather", cost=0.0, time_impact_hours=-72.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "⏳ Pausing - waiting for weather to clear (+2-5 days).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.REROUTE_SHIPMENT:
            # Track: $500 cost, +1 day but avoids longer delay
            self._track_decision("Reroute via alternative supplier", cost=500.0, time_impact_hours=-24.0)
            self._summary.avoided_production_stop = True
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "🔄 Rerouting via alternative supplier (+$500, +1 day).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.NOTICE_CUSTOMERS_REFUND:
            # Track: $0 cost, accepts delay
            self._track_decision("Notice customers with refund option", cost=0.0, time_impact_hours=-72.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "📧 Notifying customers with refund option.", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._transport_resolution.set()
        elif choice == HumanOperatorChoice.CANCEL_ORDER:
            self._track_decision("Cancel order", cost=0.0, time_impact_hours=0.0)
            self._state = ShipmentState.CANCELED
            self._transport_resolution.set()
            self._exit.set()

    @workflow.signal
    async def handle_customs_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.PROVIDE_DOCUMENTATION:
            self._track_decision("Provide additional documentation", cost=0.0, time_impact_hours=-24.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "📄 Documentation submitted to customs (+1 day).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.PAY_EXPEDITED_FEE:
            self._track_decision("Pay expedited processing fee", cost=200.0, time_impact_hours=-4.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "💰 Expedited fee paid (+$200, +4 hours).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.ACCEPT_DELAY:
            self._track_decision("Accept customs delay", cost=0.0, time_impact_hours=-72.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "⏳ Delay accepted. Monitoring progress (+2-4 days).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()
        elif choice == HumanOperatorChoice.REROUTE_SHIPMENT:
            self._track_decision("Reroute from alternative supplier", cost=800.0, time_impact_hours=-12.0)
            self._summary.avoided_production_stop = True
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "🔄 Rerouting from alternative supplier (+$800, +12 hours).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._customs_resolution.set()

    @workflow.signal
    async def handle_delivery_resolution(self, choice: HumanOperatorChoice) -> None:
        workflow_id = workflow.info().workflow_id

        if choice == HumanOperatorChoice.CANCEL_ORDER:
            self._track_decision("Cancel order", cost=0.0, time_impact_hours=0.0)
            self._state = ShipmentState.CANCELED
            self._current_error = None
            self._delivery_resolution.set()
            self._exit.set()
        elif choice == HumanOperatorChoice.RETURN_TO_DEPOT:
            self._track_decision("Return to depot for pickup", cost=25.0, time_impact_hours=0.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "✅ Delivery resolved: Return to depot for pickup (+$25)", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._current_error = None
            self._delivery_resolution.set()
        else:
            self._track_decision(f"Delivery resolved: {choice.value}", cost=0.0, time_impact_hours=-24.0)
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
            self._track_decision("Cancel order", cost=0.0, time_impact_hours=0.0)
            self._state = ShipmentState.CANCELED
            self._current_error = None
            self._exit.set()
        elif choice == HumanOperatorChoice.SEND_TO_TECH_SUPPORT:
            self._track_decision("Send to tech support", cost=50.0, time_impact_hours=-3.0)
            await workflow.execute_activity(
                notify_human_operator,
                args=[workflow_id, "🔧 Escalated to tech support (+$50, +2-4 hours).", False],
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._payment_status = PaymentStatus.SUCCESS
            self._state = ShipmentState.PAYMENT_RECEIVED
            self._current_error = None
            self._payment_resolution.set()
        elif choice == HumanOperatorChoice.RETRY_PAYMENT:
            self._track_decision("Retry payment", cost=0.0, time_impact_hours=-0.08)
            self._payment_retries = 0
            self._payment_status = PaymentStatus.PENDING
            self._current_error = None
            self._payment_resolution.set()
        elif choice == HumanOperatorChoice.RESUME_WHEN_READY:
            self._track_decision("Resume when system is ready", cost=0.0, time_impact_hours=0.0)
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
    
    @workflow.query
    def get_summary(self) -> WorkflowSummary:
        """Get workflow summary with cost and time analysis."""
        return self._summary
    
    @workflow.query
    def is_paused(self) -> bool:
        """Check if workflow is currently paused."""
        return self._pause_requested
    
    @workflow.signal
    async def pause_workflow(self) -> None:
        """Pause the workflow execution."""
        if not self._pause_requested:
            self._pause_requested = True
            self._workflow_paused.clear()
            logger.info("⏸️  Workflow paused by user")
    
    @workflow.signal
    async def resume_workflow(self) -> None:
        """Resume the workflow execution."""
        if self._pause_requested:
            self._pause_requested = False
            self._workflow_paused.set()
            logger.info("▶️  Workflow resumed by user")
    
    def _track_decision(self, decision: str, cost: float = 0.0, time_impact_hours: float = 0.0) -> None:
        """Track a human decision with its cost and time impact."""
        self._summary.decisions_made.append(decision)
        self._summary.total_cost += cost
        self._summary.time_saved_hours += time_impact_hours
    
    def _parse_cost(self, cost_str: str) -> float:
        """Parse cost string like '$500' to float."""
        return float(cost_str.replace('$', '').replace(',', ''))
    
    def _parse_time_impact(self, time_str: str) -> float:
        """Parse time impact string to hours. Negative means delay."""
        if "No delay" in time_str or "Immediate" in time_str:
            return 0.0
        
        # Extract number
        import re
        match = re.search(r'[+-]?\d+', time_str)
        if not match:
            return 0.0
        
        value = float(match.group())
        
        # Check if it's a delay (positive) or speedup (negative)
        if "day" in time_str.lower():
            return -value * 24  # Days to hours (negative = delay)
        elif "hour" in time_str or "h" in time_str:
            return -value  # Hours (negative = delay)
        elif "min" in time_str.lower():
            return -value / 60  # Minutes to hours
        
        return 0.0
