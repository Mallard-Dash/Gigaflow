import { useState, useEffect } from "react";
import type { Route } from "./+types/home";
import { Card, CardContent } from "~/components/ui/card";
import { Button } from "~/components/ui/button";
import { cn } from "~/lib/utils";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "Mysteryboxes Inc." },
    { name: "description", content: "Global Logistics Simulation" },
  ];
}

const mysteryBoxes = [
  {
    id: "happy-path",
    icon: "✨",
    name: "Standard Flow",
    scenario: "A simple shipment that completes successfully without any issues",
    selected: true,
  },
  {
    id: "payment-failure",
    icon: "💳",
    name: "Payment Network Issues",
    scenario: "Simulates payment gateway network errors, requiring operator intervention",
  },
  {
    id: "insufficient-funds",
    icon: "💸",
    name: "Insufficient Funds",
    scenario: "Payment fails due to insufficient funds, demonstrating automatic order cancellation",
  },
  {
    id: "price-mismatch",
    icon: "💱",
    name: "Price Change Scenario",
    scenario: "Shows how price changes during order processing are handled with operator decisions",
  },
  {
    id: "warehouse-stock",
    icon: "🏭",
    name: "Stock Management",
    scenario: "Demonstrates warehouse allocation strategies when stock is unavailable",
  },
  {
    id: "transport-delay",
    icon: "🌪️",
    name: "Weather Impact",
    scenario: "Shows how severe weather impacts are handled in the transport phase",
  },
  {
    id: "customs-issue",
    icon: "📄",
    name: "Customs Documentation",
    scenario: "Demonstrates customs clearance process with missing documentation",
  },
  {
    id: "delivery-delay",
    icon: "🚚",
    name: "Local Delivery Issues",
    scenario: "Shows how local delivery delays are handled and communicated",
  }
];

const shipmentSteps = [
  { name: "Order Received", icon: "📦", status: "completed" },
  { name: "Payment OK", icon: "💳", status: "completed" },
  { name: "Warehouse Allocation", icon: "🏢", status: "completed" },
  { name: "Packaged (Factory)", icon: "🏭", status: "active" },
  { name: "Transport Started", icon: "✈️", status: "pending" },
  { name: "Customs Clearance", icon: "🛂", status: "pending" },
  { name: "Local Delivery", icon: "🚚", status: "pending" },
  { name: "Delivered", icon: "🏠", status: "pending" },
];

function Header() {
  return (
    <header className="flex justify-between items-start">
      <div>
        <h1 className="text-4xl font-bold text-purple-300">Mysteryboxes Inc.</h1>
        <p className="text-gray-400">Global Logistics Simulation (Powered by Temporal)</p>
      </div>
      <WarehouseStatus />
    </header>
  );
}

function WarehouseStatus() {
  // Placeholder for fetching warehouse status
  const warehouse = {
    name: "Swedish Warehouse",
    stock: 77,
    capacity: 100,
    demand: "NORMAL",
  };

  const stockPercentage = (warehouse.stock / warehouse.capacity) * 100;
  const stockColor = stockPercentage > 50 ? "text-green-400" : stockPercentage > 20 ? "text-yellow-400" : "text-red-400";

  return (
    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
      <div className="flex items-center gap-3">
        <img src="https://raw.githubusercontent.com/temporalio/temporal-artwork/8a52a938a89a3347a3637499194b3d9a4c62b14c/logos/temporal-logo-hexagon-white.svg" alt="Temporal Logo" className="w-6 h-6" />
        <h3 className="font-bold text-lg">{warehouse.name}</h3>
      </div>
      <p className={cn("text-sm mt-2", stockColor)}>Current Stock: {warehouse.stock}/{warehouse.capacity}</p>
      <p className={cn("text-sm", stockColor)}>Demand: {warehouse.demand}</p>
    </div>
  );
}

function ChooseMysteryBox({ setOrder }: { setOrder: (order: any) => void }) {
  const handleOrder = async (box: any) => {
    try {
      // Create shipment with scenario ID
      const API_BASE = window.location.hostname === 'localhost' 
        ? 'http://localhost:32772' 
        : 'http://shipping-api:3030';
      const response = await fetch(`${API_BASE}/shipments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ scenario_id: box.id })
      });
      const data = await response.json();
      setOrder({ ...box, shipmentId: data.shipment_id });
    } catch (error) {
      console.error('Error creating order:', error);
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-bold mb-2 text-pink-400">Choose Your Mysterybox</h2>
      <p className="text-gray-400 mb-8">Each box simulates a unique global logistics flow.</p>
      <div className="space-y-4">
        {mysteryBoxes.map((box) => (
          <Card
            key={box.id}
            className={cn(
              "bg-gray-800 border-2 border-gray-700 cursor-pointer hover:border-purple-500 transition-all",
              box.selected && "border-purple-500 ring-2 ring-purple-500"
            )}
            onClick={() => handleOrder(box)}
          >
            <CardContent className="p-6">
              <div className="flex items-center gap-6">
                <div className="text-4xl">{box.icon}</div>
                <div>
                  <h3 className="font-bold text-xl text-white">
                    {box.name}
                  </h3>
                  <p className="text-sm text-gray-400">{box.scenario}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function OrderStatus({ order, setOrder }: { order: any; setOrder: (order: any) => void }) {
  type WorkflowState = {
    currentStep: number;
    eta: string;
    status: string;
    logs: string[];
    humanChoice: string | null;
    humanOptions: string[];
    humanMessage: string | null;
    shipmentId?: string;
  };

  const [workflowState, setWorkflowState] = useState<WorkflowState>({
    currentStep: 0,
    eta: "2025-11-23",
    status: "running",
    logs: [],
    humanChoice: null,
    humanOptions: [],
    humanMessage: null
  });
  
  const [seenEvents, setSeenEvents] = useState<Set<string>>(new Set());

  useEffect(() => {
    const startWorkflow = async () => {
      const addLog = (message: string, eventKey?: string) => {
        // Prevent duplicate events
        if (eventKey && seenEvents.has(eventKey)) {
          return;
        }
        
        if (eventKey) {
          setSeenEvents(prev => new Set(prev).add(eventKey));
        }
        
        setWorkflowState(prev => ({
          ...prev,
          logs: [...prev.logs, `[${new Date().toLocaleTimeString()}] ${message}`]
        }));
      };

      const updateStep = (step: number, eta?: string) => {
        setWorkflowState(prev => ({
          ...prev,
          currentStep: step,
          eta: eta || prev.eta
        }));
      };

      try {
        // Use existing shipment ID from order
        addLog("🚀 Starting shipment workflow...");
        const shipmentId = order.shipmentId;
        setWorkflowState(prev => ({
          ...prev,
          shipmentId
        }));
        addLog(`✅ Created shipment: ${shipmentId}`);

        // Poll for status updates
        const API_BASE = window.location.hostname === 'localhost' 
          ? 'http://localhost:32772' 
          : 'http://shipping-api:3030';
        const pollStatus = async () => {
          const statusResponse = await fetch(`${API_BASE}/shipments/${shipmentId}`);
          const statusData = await statusResponse.json();
          const status = statusData.status;
          const currentError = statusData.current_error;

          // Map status to step number
          const statusToStep: Record<string, number> = {
            'ORDER_RECEIVED': 0,
            'PAYMENT_RECEIVED': 1,
            'WAREHOUSE_ALLOCATION': 2,
            'PACKAGED': 3,
            'TRANSPORT_STARTED': 4,
            'CUSTOMS_CLEARANCE': 5,
            'LOCAL_DELIVERY': 6,
            'DELIVERED': 7,
            'CANCELED': -1
          };

          const step = statusToStep[status];
          
          // Handle cancelled state
          if (step === -1) {
            addLog("🚫 Shipment cancelled", `cancelled-${shipmentId}`);
            setWorkflowState(prev => ({
              ...prev,
              status: 'cancelled',
              humanMessage: null,
              humanOptions: []
            }));
            return false;
          }

          // Handle delivered state
          if (status === 'DELIVERED') {
            addLog("📦 Shipment completed!", `delivered-${shipmentId}`);
            setWorkflowState(prev => ({
              ...prev,
              status: 'completed',
              humanMessage: null,
              humanOptions: []
            }));
            return false;
          }

          // Update step only if changed (prevents duplicates)
          if (step !== workflowState.currentStep) {
            updateStep(step);
            addLog(`✅ Status updated: ${status}`, `status-${status}-${shipmentId}`);
          }

          // Check for human-in-the-loop errors
          if (currentError && currentError.resolution_options && currentError.resolution_options.length > 0) {
            const errorKey = `error-${currentError.reason}-${shipmentId}`;
            if (!seenEvents.has(errorKey)) {
              addLog(`⚠️ ${currentError.details}`, errorKey);
              setWorkflowState(prev => ({
                ...prev,
                humanMessage: currentError.details,
                humanOptions: currentError.resolution_options
              }));
            }
          } else if (workflowState.humanMessage && !currentError) {
            // Error was resolved, clear UI
            setWorkflowState(prev => ({
              ...prev,
              humanMessage: null,
              humanOptions: []
            }));
          }

          return step < 7 && status !== 'DELIVERED';
        };

        // Start polling
        const poll = async () => {
          while (await pollStatus()) {
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        };

        poll();

        // Simulate scenario-specific behavior
        if (order.id === 'transport-delay') {
          setTimeout(async () => {
            addLog("⚠️ Severe weather affecting transport route");
            const newEta = "2025-11-25";
            addLog("📅 New estimated delivery: " + newEta);
            setWorkflowState(prev => ({
              ...prev,
              eta: newEta,
              humanMessage: "Transport delayed due to weather. Please choose an action:",
              humanOptions: [
                "Wait for resolution",
                "Reroute shipment",
                "Expedite with premium service",
                "Cancel delivery"
              ]
            }));
          }, 5000);
        }

      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
        addLog(`❌ Error: ${errorMessage}`);
        setWorkflowState(prev => ({
          ...prev,
          status: 'error'
        }));
      }
    };

    startWorkflow();
  }, [order.id]);

  const handleHumanChoice = async (choice: string) => {
    const addLog = (message: string) => {
      setWorkflowState(prev => ({
        ...prev,
        logs: [...prev.logs, `[${new Date().toLocaleTimeString()}] ${message}`]
      }));
    };

    addLog(`👤 Human operator chose: ${choice}`);

    try {
      // Map frontend choices to backend enum values
      const choiceMap: Record<string, string> = {
        // Payment choices
        "Send to tech support": "SEND_TO_TECH_SUPPORT",
        "Retry payment": "RETRY_PAYMENT",
        "Resume when ready": "RESUME_WHEN_READY",
        "Resume when system is ready": "RESUME_WHEN_READY",
        "Cancel order": "CANCEL_ORDER",
        // Order validation choices
        "Accept new price": "ACCEPT_NEW_PRICE",
        "Update order": "UPDATE_ORDER",
        "Update order with available items": "UPDATE_ORDER",
        "Adjust quantity": "ADJUST_QUANTITY",
        // Warehouse choices
        "Allocate from different warehouse": "ALLOCATE_DIFFERENT",
        "Cancel order and reorder from another supplier": "CANCEL_ORDER",
        "Wait for stock to be replenished": "WAIT_FOR_STOCK",
        // Transport choices
        "Notice customers and offer refunds": "NOTICE_CUSTOMERS_REFUND",
        "Do nothing and wait out bad weather (pause workflow)": "WAIT_OUT_WEATHER",
        "Reroute shipment from unaffected supplier (high cost)": "REROUTE_SHIPMENT",
        "Wait for resolution": "WAIT_OUT_WEATHER",
        "Reroute shipment": "REROUTE_SHIPMENT",
        "Expedite with premium service": "REROUTE_SHIPMENT",
        // Customs choices
        "Provide additional documentation": "PROVIDE_DOCUMENTATION",
        "Pay expedited processing fee": "PAY_EXPEDITED_FEE",
        "Pay expedited fee": "PAY_EXPEDITED_FEE",
        "Accept delay": "ACCEPT_DELAY",
        "Return shipment": "RETURN_SHIPMENT",
        // Delivery choices
        "Schedule new delivery time": "SCHEDULE_NEW_TIME",
        "Leave at safe location": "LEAVE_SAFE_LOCATION",
        "Return to depot for pickup": "RETURN_TO_DEPOT",
        "Cancel delivery": "CANCEL_ORDER",
        // Delay resolution choices
        "Do nothing (small delay)": "DO_NOTHING",
        "Inform customers": "INFORM_CUSTOMERS",
        "Contact and rearrange logistics-hub timeslots": "REARRANGE_LOGISTICS"
      };

      const operatorChoice = choiceMap[choice];
      if (!operatorChoice) {
        throw new Error(`Unknown choice: ${choice}`);
      }

      const API_BASE = window.location.hostname === 'localhost' 
        ? 'http://localhost:32772' 
        : 'http://shipping-api:3030';
        
      if (operatorChoice === "CANCEL_ORDER" || operatorChoice === "RETURN_SHIPMENT") {
        await fetch(`${API_BASE}/shipments/${workflowState.shipmentId}`, {
          method: 'DELETE'
        });
        addLog("🚫 Order cancelled by human operator");
        setWorkflowState(prev => ({
          ...prev,
          status: "cancelled",
          humanMessage: null,
          humanOptions: []
        }));
        return;
      }

      // Send resolution to backend
      await fetch(`${API_BASE}/shipments/${workflowState.shipmentId}/handle-resolution`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ choice: operatorChoice })
      });

      // Workflow continues automatically after resolution
      addLog("✅ Resuming workflow");
      setWorkflowState(prev => ({
        ...prev,
        humanMessage: null,
        humanOptions: []
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      addLog(`❌ Error: ${errorMessage}`);
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-bold mb-4 text-pink-400">Order Status</h2>
      <div className="bg-gray-800 p-8 rounded-lg border border-gray-700">
        <div className="text-center text-lg mb-10">
          Estimated delivery date:{" "}
          <span className={cn(
            "font-bold",
            workflowState.status === "cancelled" ? "text-red-400" : "text-green-400"
          )}>
            {workflowState.status === "cancelled" ? "Cancelled" : workflowState.eta}
          </span>
        </div>
        
        <div className="relative flex justify-between items-start mb-4">
          <div className="absolute top-1/2 left-0 w-full h-0.5 bg-gray-600" style={{ transform: 'translateY(-50%)', top: '24px' }}></div>
          <div 
            className="absolute top-1/2 left-0 h-0.5 bg-purple-500" 
            style={{ 
              transform: 'translateY(-50%)', 
              top: '24px', 
              width: `${(workflowState.currentStep / (shipmentSteps.length - 1)) * 100}%`,
              transition: 'width 0.5s ease-in-out'
            }}
          ></div>
          {shipmentSteps.map((step, index) => (
            <div key={index} className="z-10 flex flex-col items-center text-center w-24">
              <div
                className={cn(
                  "w-12 h-12 rounded-full flex items-center justify-center text-2xl border-4",
                  index < workflowState.currentStep && "bg-purple-500 border-purple-700",
                  index === workflowState.currentStep && "bg-blue-500 border-blue-700 animate-pulse",
                  index > workflowState.currentStep && "bg-gray-700 border-gray-600",
                  workflowState.status === "cancelled" && "border-red-700"
                )}
              >
                {step.icon}
              </div>
              <p className="text-xs mt-2 h-8">{step.name}</p>
            </div>
          ))}
        </div>

        {workflowState.humanMessage && (
          <div className="mt-8 p-4 bg-yellow-900/50 rounded-lg border border-yellow-700">
            <p className="text-yellow-300 mb-4">{workflowState.humanMessage}</p>
            <div className="flex flex-wrap gap-2">
              {workflowState.humanOptions.map((option, index) => (
                <Button
                  key={index}
                  variant="outline"
                  className="bg-yellow-600 text-white hover:bg-yellow-700"
                  onClick={() => handleHumanChoice(option)}
                >
                  {option}
                </Button>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-4 mt-12">
          <Button 
            variant="secondary" 
            onClick={async () => {
              // Reset workflow by starting a new one with same scenario
              const prevOrder = order;
              setOrder(null);
              try {
                const API_BASE = window.location.hostname === 'localhost' 
                  ? 'http://localhost:32772' 
                  : 'http://shipping-api:3030';
                const response = await fetch(`${API_BASE}/shipments`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json'
                  },
                  body: JSON.stringify({ scenario_id: prevOrder.id })
                });
                const data = await response.json();
                setOrder({ ...prevOrder, shipmentId: data.shipment_id });
              } catch (error) {
                console.error('Error resetting scenario:', error);
              }
            }}
          >
            Reset Scenario
          </Button>
          
          <Button 
            variant="default"
            disabled={!workflowState.humanMessage} // Only enabled when worker is waiting
            onClick={() => {
              // Auto-resolve current step
              if (workflowState.humanOptions.length > 0) {
                // Choose first non-cancel option
                const choice = workflowState.humanOptions.find(opt => 
                  !opt.toLowerCase().includes('cancel')
                ) || workflowState.humanOptions[0];
                handleHumanChoice(choice);
              }
            }}
          >
            Continue
          </Button>

          {workflowState.status !== "running" && (
            <Button variant="secondary" onClick={() => setOrder(null)}>
              Start New Order
            </Button>
          )}
        </div>
      </div>

      <div className="mt-8 bg-black p-6 rounded-lg border border-gray-700 font-mono">
        <h3 className="font-bold mb-4 text-gray-300">Status Log:</h3>
        <div 
          ref={(el) => {
            if (el) {
              el.scrollTop = el.scrollHeight;
            }
          }}
          className="text-sm whitespace-pre-wrap text-gray-400 h-48 overflow-y-auto"
        >
          {workflowState.logs.map((log, index) => (
            <div key={index} className={cn(
              "py-0.5",
              log.includes("❌") && "text-red-400",
              log.includes("⚠️") && "text-yellow-400",
              log.includes("✅") && "text-green-400",
              log.includes("📦 Shipment completed!") && "text-green-500 font-bold"
            )}>
              {log}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [order, setOrder] = useState<any>(null);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        <Header />
        <main className="mt-10">
          {order ? (
            <OrderStatus order={order} setOrder={setOrder} />
          ) : (
            <ChooseMysteryBox setOrder={setOrder} />
          )}
        </main>
      </div>
    </div>
  );
}
