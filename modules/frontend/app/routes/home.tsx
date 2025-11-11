import { useState, useEffect, useRef } from "react";
import type { Route } from "./+types/home";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "ResilientFlow - Production Continuity Demo" },
    { name: "description", content: "Human-in-the-Loop AI for Nordic Industry" },
  ];
}

// Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";

const scenarios = {
  "happy-path": { name: "EU Standard Flow", emoji: "🇪🇺" },
  "customs-issue": { name: "Customs Clearance Challenge", emoji: "🛂" },
  "warehouse-stock": { name: "High Demand Stock Failure", emoji: "🔄" },
  "transport-delay": { name: "Geopolitical Crisis Impact", emoji: "🚨" },
  "delivery-delay": { name: "Lab Inspection Failure", emoji: "🔩" },
  "price-mismatch": { name: "Logistics Jam Delay", emoji: "❄️" },
  "carrier-bankruptcy": { name: "Carrier Bankruptcy", emoji: "💸" },
  "currency-volatility": { name: "Currency Volatility", emoji: "💱" }
};

const scenarioDescriptions: Record<string, string> = {
  "happy-path": "Successful order flow shipped from Estonia. Full happy path with no errors.",
  "customs-issue": "👤 Customs hold-up on import/export. Requires human decision on resolution.",
  "warehouse-stock": "Estonian warehouse out of stock. System automatically reroutes order to China factory.",
  "transport-delay": "👤 Geopolitical crisis blocks main shipping route. Workflow halts for human decision.",
  "delivery-delay": "👤 Material composition failure in screw batch during QA testing. Requires management intervention.",
  "price-mismatch": "👤 Major snowstorm hits Sweden between customs and delivery. AI monitors and updates customers, or hand over to HITL.",
  "carrier-bankruptcy": "Shipping carrier goes bankrupt mid-route. System automatically switches to alternative carrier.",
  "currency-volatility": "Rapid currency exchange fluctuations affect payment margin. Automatic price adjustment."
};

const steps = [
  { id: "step-1", name: "Order Received", icon: "📦" },
  { id: "step-2", name: "Warehouse Allocation", icon: "🗺️" },
  { id: "step-3", name: "Packaged (Factory)", icon: "🏭" },
  { id: "step-4", name: "Transport Started", icon: "✈️" },
  { id: "step-5", name: "Customs Clearance", icon: "🛂" },
  { id: "step-6", name: "Local Delivery", icon: "🚚" },
  { id: "step-7", name: "Delivered", icon: "🏠" }
];


interface ConfigViewProps {
  onSelectScenario: (scenarioId: string) => void;
}

function ConfigView({ onSelectScenario }: ConfigViewProps) {
  const [selectedScenario, setSelectedScenario] = useState("happy-path");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSelectScenario(selectedScenario);
  };

  return (
    <div>
      <h2 className="resilient-h2">Choose Your Production Scenario</h2>
      <p style={{ color: "var(--text-muted)", marginBottom: "20px" }}>
        Each scenario simulates a unique production challenge and demonstrates how AI and human operators collaborate to prevent downtime.
      </p>
      <form onSubmit={handleSubmit}>
        {Object.entries(scenarios).map(([id, info]) => (
          <div key={id} className="form-group-radio">
            <input
              type="radio"
              id={`scenario-${id}`}
              name="scenario"
              value={id}
              checked={selectedScenario === id}
              onChange={(e) => setSelectedScenario(e.target.value)}
            />
            <label htmlFor={`scenario-${id}`}>
              {info.emoji} {info.name}
              <span><b>Scenario:</b> {scenarioDescriptions[id]}</span>
            </label>
          </div>
        ))}
        <button type="submit" className="btn-gradient">Start Scenario</button>
      </form>
    </div>
  );
}

interface WorkflowViewProps {
  scenario: string;
  shipmentId: string;
  onReset: () => void;
}

interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error' | 'human' | 'ai';
}

function WorkflowView({ scenario, shipmentId, onReset }: WorkflowViewProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [deliveryDate, setDeliveryDate] = useState("");
  const [dateColor, setDateColor] = useState("var(--success-color)");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState("running");
  const [humanMessage, setHumanMessage] = useState<string | null>(null);
  const [humanOptions, setHumanOptions] = useState<string[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [selectedChoice, setSelectedChoice] = useState<string>("");
  
  const logOutputRef = useRef<HTMLPreElement>(null);
  const seenEventsRef = useRef<Set<string>>(new Set());
  
  // Calculate initial delivery date (7 days from now)
  useEffect(() => {
    const initialDate = new Date();
    initialDate.setDate(initialDate.getDate() + 7);
    setDeliveryDate(initialDate.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    }));
  }, []);

  const addLog = (message: string, eventKey?: string) => {
    if (eventKey && seenEventsRef.current.has(eventKey)) {
      return;
    }
    if (eventKey) {
      seenEventsRef.current.add(eventKey);
    }
    const timestamp = new Date().toLocaleTimeString();
    
    // Determine log type based on content
    let logType: 'info' | 'success' | 'warning' | 'error' | 'human' | 'ai' = 'info';
    if (message.includes('✅') || message.includes('completed') || message.includes('successful')) {
      logType = 'success';
    } else if (message.includes('⚠️') || message.includes('warning') || message.includes('caution') || message.includes('⏳')) {
      logType = 'warning';
    } else if (message.includes('❌') || message.includes('🚫') || message.includes('error') || message.includes('failed') || message.includes('cancelled')) {
      logType = 'error';
    } else if (message.includes('👤') || message.includes('human') || message.includes('operator')) {
      logType = 'human';
    } else if (message.includes('🤖') || message.includes('AI')) {
      logType = 'ai';
    }
    
    setLogs(prev => [...prev, { timestamp, message, type: logType }]);
  };

  const getLogColor = (type: LogEntry['type']): string => {
    switch (type) {
      case 'success':
        return 'var(--success-color)';
      case 'warning':
        return 'var(--warning-color)';
      case 'error':
        return 'var(--error-color)';
      case 'human':
        return '#a78bfa';
      case 'ai':
        return '#60a5fa';
      default:
        return 'var(--text-color)';
    }
  };

  const updateStep = (step: number) => {
    setCurrentStep(step);
  };

  useEffect(() => {
    if (logOutputRef.current) {
      logOutputRef.current.scrollTop = logOutputRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    let shouldContinuePolling = true;
    let lastDeliveryStatus = "";

    const pollStatus = async () => {
      if (!shouldContinuePolling) return false;

      try {
        const statusResponse = await fetch(`${API_BASE_URL}/shipments/${shipmentId}`);
        const statusData = await statusResponse.json();
        const currentStatus = statusData.status;
        const currentError = statusData.current_error;
        const deliveryUpdate = statusData.delivery_update;

        // Update delivery date if available
        if (deliveryUpdate) {
          const newDate = deliveryUpdate.new_eta || deliveryUpdate.estimated_delivery_date;
          if (newDate) {
            const dateObj = new Date(newDate);
            const formattedDate = dateObj.toLocaleDateString('en-US', { 
              year: 'numeric', 
              month: 'long', 
              day: 'numeric' 
            });
            setDeliveryDate(formattedDate);
          }

          // Update color based on delay status
          if (deliveryUpdate.status === 'DELAYED' && lastDeliveryStatus !== 'DELAYED') {
            setDateColor('var(--error-color)');
            const delayKey = `delay-notification-${shipmentId}`;
            if (!seenEventsRef.current.has(delayKey)) {
              addLog("📧 Delay notification sent to Logistics department", delayKey);
            }
            lastDeliveryStatus = 'DELAYED';
          } else if (deliveryUpdate.status === 'ON_TIME') {
            setDateColor('var(--success-color)');
            lastDeliveryStatus = 'ON_TIME';
          }
        }

        const statusToStep: Record<string, number> = {
          'ORDER_RECEIVED': 0,
          'PAYMENT_RECEIVED': 0, // Skip payment step in UI
          'WAREHOUSE_ALLOCATION': 1,
          'PACKAGED': 2,
          'TRANSPORT_STARTED': 3,
          'CUSTOMS_CLEARANCE': 4,
          'LOCAL_DELIVERY': 5,
          'DELIVERED': 6,
          'CANCELED': -1
        };

        const step = statusToStep[currentStatus];

        if (step === -1) {
          const eventKey = `cancelled-${shipmentId}`;
          if (!seenEventsRef.current.has(eventKey)) {
            addLog("🚫 Production order cancelled", eventKey);
            setStatus('cancelled');
            setHumanMessage(null);
            setHumanOptions([]);
            setShowModal(false);
          }
          return false;
        }

        if (currentStatus === 'DELIVERED') {
          const eventKey = `delivered-${shipmentId}`;
          if (!seenEventsRef.current.has(eventKey)) {
            updateStep(6);
            addLog("✅ Production flow completed successfully!", eventKey);
            setStatus('completed');
            setHumanMessage(null);
            setHumanOptions([]);
            setShowModal(false);
          }
          return false;
        }

        const statusKey = `status-${currentStatus}-${shipmentId}`;
        if (!seenEventsRef.current.has(statusKey) && currentStatus !== 'PAYMENT_RECEIVED') {
          updateStep(step);
          addLog(`ℹ️ Status: ${currentStatus}`, statusKey);
        }

        if (currentError && currentError.resolution_options && currentError.resolution_options.length > 0) {
          const errorKey = `error-${currentError.reason}-${currentStatus}-${shipmentId}`;
          if (!seenEventsRef.current.has(errorKey)) {
            addLog(`⚠️ ${currentError.details}`, errorKey);
            setHumanMessage(currentError.details);
            setHumanOptions(currentError.resolution_options);
            setShowModal(true);
            if (currentError.resolution_options.length > 0) {
              setSelectedChoice(currentError.resolution_options[0]);
            }
          }
        } else if (humanMessage && !currentError) {
          const resolvedKey = `resolved-${currentStatus}-${shipmentId}`;
          if (!seenEventsRef.current.has(resolvedKey)) {
            addLog("✅ Issue resolved, continuing workflow", resolvedKey);
            setHumanMessage(null);
            setHumanOptions([]);
            setShowModal(false);
          }
        }

        return step < 6 && currentStatus !== 'DELIVERED';
      } catch (error) {
        console.error('Polling error:', error);
        return true;
      }
    };

    const startPolling = async () => {
      addLog("🚀 Starting production workflow...");
      addLog(`📋 Order ID: ${shipmentId}`);
      
      while (await pollStatus()) {
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    };

    startPolling();

    return () => {
      shouldContinuePolling = false;
    };
  }, [shipmentId]);

  const handleHumanChoice = async (choice: string, isAiChoice: boolean = false) => {
    if (isAiChoice) {
      addLog(`🤖 AI auto-resolved: ${choice}`);
    } else {
      addLog(`👤 Human operator intervened: ${choice}`);
    }

    try {
      const choiceMap: Record<string, string> = {
        "Send to tech support": "SEND_TO_TECH_SUPPORT",
        "Retry payment": "RETRY_PAYMENT",
        "Resume when ready": "RESUME_WHEN_READY",
        "Resume when system is ready": "RESUME_WHEN_READY",
        "Cancel order": "CANCEL_ORDER",
        "Accept new price": "ACCEPT_NEW_PRICE",
        "Update order": "UPDATE_ORDER",
        "Update order with available items": "UPDATE_ORDER",
        "Adjust quantity": "ADJUST_QUANTITY",
        "Allocate from different warehouse": "ALLOCATE_DIFFERENT",
        "Cancel order and reorder from another supplier": "CANCEL_ORDER",
        "Wait for stock to be replenished": "WAIT_FOR_STOCK",
        "Notice customers and offer refunds": "NOTICE_CUSTOMERS_REFUND",
        "Do nothing and wait out bad weather (pause workflow)": "WAIT_OUT_WEATHER",
        "Reroute shipment from unaffected supplier (high cost)": "REROUTE_SHIPMENT",
        "Wait for resolution": "WAIT_OUT_WEATHER",
        "Reroute shipment": "REROUTE_SHIPMENT",
        "Expedite with premium service": "REROUTE_SHIPMENT",
        "Provide additional documentation": "PROVIDE_DOCUMENTATION",
        "Pay expedited processing fee": "PAY_EXPEDITED_FEE",
        "Pay expedited fee": "PAY_EXPEDITED_FEE",
        "Accept delay": "ACCEPT_DELAY",
        "Return shipment": "RETURN_SHIPMENT",
        "Submit emergency CE certification (2-day expedited process)": "PROVIDE_DOCUMENTATION",
        "Reroute through alternative customs point with lower requirements": "PAY_EXPEDITED_FEE",
        "Accept standard 4-day processing delay": "ACCEPT_DELAY",
        "Cancel shipment and source domestically": "RETURN_SHIPMENT",
        "Schedule new delivery time": "SCHEDULE_NEW_TIME",
        "Leave at safe location": "LEAVE_SAFE_LOCATION",
        "Return to depot for pickup": "RETURN_TO_DEPOT",
        "Cancel delivery": "CANCEL_ORDER",
        "Do nothing (small delay)": "DO_NOTHING",
        "Inform customers": "INFORM_CUSTOMERS",
        "Contact and rearrange logistics-hub timeslots": "REARRANGE_LOGISTICS",
        "Agree to recall and order new batch from local supplier": "AGREE_RECALL_ORDER_NEW",
        "Receive the batch and ignore the recall (Catastrophic consequences could happen. Your company could be held accountable for this, high risk)": "IGNORE_RECALL_HIGH_RISK",
        "Hand over to human operator for manual handling": "HAND_OVER_TO_HITL",
        "AI monitors weather and automatically resumes when clear": "AI_MONITOR_AND_WAIT"
      };

      const operatorChoice = choiceMap[choice];
      if (!operatorChoice) {
        throw new Error(`Unknown choice: ${choice}`);
      }

      if (operatorChoice === "CANCEL_ORDER" || operatorChoice === "RETURN_SHIPMENT") {
        await fetch(`${API_BASE_URL}/shipments/${shipmentId}`, {
          method: 'DELETE'
        });
        addLog("🚫 Order cancelled by operator");
        setStatus("cancelled");
        setHumanMessage(null);
        setHumanOptions([]);
        setShowModal(false);
        return;
      }

      await fetch(`${API_BASE_URL}/shipments/${shipmentId}/handle-resolution`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ choice: operatorChoice })
      });

      addLog("✅ Decision submitted, resuming workflow");
      setHumanMessage(null);
      setHumanOptions([]);
      setShowModal(false);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      addLog(`❌ Error: ${errorMessage}`);
    }
  };

  return (
    <div>
      <h2 className="resilient-h2">Production Flow Status</h2>
      <div className="delivery-date-wrapper">
        Estimated completion date: <span className="delivery-date" style={{ color: dateColor }}>{deliveryDate}</span>
      </div>

      <div className="workflow-container">
        <ul className="workflow-steps">
          {steps.map((step, index) => {
            let className = "step";
            if (index < currentStep) className += " completed";
            if (index === currentStep) className += " active";
            if (status === "cancelled") className += " error";

            return (
              <li key={step.id} id={step.id} className={className}>
                <div className="step-icon">{step.icon}</div>
                <div className="step-label">{step.name}</div>
              </li>
            );
          })}
        </ul>
      </div>

      <div style={{ marginTop: "20px" }}>
        <button className="btn-secondary" onClick={onReset}>
          Start New Order
        </button>
      </div>

      <div className="status-log-wrapper">
        <h3>Production Log:</h3>
        <pre ref={logOutputRef} className="log-output">
          {logs.map((log, index) => (
            <div key={index} style={{ color: getLogColor(log.type) }}>
              [{log.timestamp}] {log.message}
            </div>
          ))}
        </pre>
      </div>

      {showModal && (
        <div className="intervention-modal-overlay" onClick={(e) => {
          if (e.target === e.currentTarget) {
            // Don't close on backdrop click - force decision
          }
        }}>
          <div className="intervention-modal">
            <div className="modal-header">
              <h3><span className="logo-emoji">🚨</span> Critical Decision Required</h3>
              <span>TO: Production Control Team</span>
            </div>
            <div className="modal-body">
              <p><strong>PRODUCTION ALERT:</strong> {humanMessage}</p>
              <p>The automated system has paused and requires <strong>human intervention</strong>. How do you want to proceed?</p>

              <form id="intervention-form">
                {!humanMessage?.includes("Zinc-coated screws") && !humanMessage?.includes("snowstorm") && (
                  <div className="intervention-choice" style={{ 
                    borderColor: "var(--primary-accent)", 
                    backgroundColor: "rgba(98, 58, 162, 0.2)" 
                  }}>
                    <input
                      type="radio"
                      id="choice-ai"
                      name="solution"
                      value="ai-auto"
                      checked={selectedChoice === "ai-auto"}
                      onChange={() => setSelectedChoice("ai-auto")}
                    />
                    <label htmlFor="choice-ai">
                      <strong>🤖 Let AI Handle This (Recommended)</strong>
                      <span>AI will automatically select the optimal resolution based on historical data and current conditions.</span>
                    </label>
                  </div>
                )}

                {humanOptions.map((option, index) => (
                  <div key={index} className="intervention-choice">
                    <input
                      type="radio"
                      id={`choice-${index}`}
                      name="solution"
                      value={option}
                      checked={selectedChoice === option}
                      onChange={() => setSelectedChoice(option)}
                    />
                    <label htmlFor={`choice-${index}`}>
                      <strong>{option}</strong>
                      <span>Manual operator decision</span>
                    </label>
                  </div>
                ))}

                {humanMessage?.includes("Zinc-coated screws") && (
                  <div style={{ 
                    marginTop: "15px", 
                    padding: "12px", 
                    backgroundColor: "rgba(5, 217, 160, 0.1)", 
                    border: "1px solid var(--success-color)", 
                    borderRadius: "8px" 
                  }}>
                    <p style={{ margin: 0, color: "var(--success-color)", fontSize: "0.95rem" }}>
                      <strong>🤖 AI Recommendation:</strong> Option 1 is recommended - agreeing to the recall and ordering a new batch from local supplier ensures NO downtime and maintains production safety standards.
                    </p>
                  </div>
                )}
              </form>
            </div>
            <div className="modal-footer">
              <button
                className="btn-gradient"
                type="button"
                onClick={() => {
                  if (selectedChoice === "ai-auto") {
                    const choice = humanOptions.find(opt => !opt.toLowerCase().includes('cancel')) || humanOptions[0];
                    handleHumanChoice(choice, true);
                  } else {
                    handleHumanChoice(selectedChoice, false);
                  }
                }}
              >
                Implement & Resume Flow
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [view, setView] = useState<"config" | "workflow">("config");
  const [selectedScenario, setSelectedScenario] = useState("");
  const [shipmentId, setShipmentId] = useState("");

  const handleSelectScenario = async (scenarioId: string) => {
    setSelectedScenario(scenarioId);
    
    // Skip checkout view, go directly to workflow
    try {
      const response = await fetch(`${API_BASE_URL}/shipments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ scenario_id: scenarioId })
      });
      const data = await response.json();
      setShipmentId(data.shipment_id);
      setView("workflow");
    } catch (error) {
      console.error('Error creating order:', error);
    }
  };

  const handleReset = () => {
    setView("config");
    setSelectedScenario("");
    setShipmentId("");
  };

  return (
    <div style={{ minHeight: "10vh", backgroundColor: "var(--bg-color)", color: "var(--text-color)" }}>
      <header className="resilient-header">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "0" }}>
          <img 
            src="/RF-transparent.png" 
            alt="ResilientFlow Logo" 
            style={{ 
              height: "300px",
              width: "auto",
              filter: "drop-shadow(0 8px 24px rgba(0, 0, 0, 0.4)) drop-shadow(0 0 40px rgba(139, 92, 246, 0.4))",
              opacity: "0.98"
            }}
          />
        </div>
        <p style={{ 
          marginTop: "0",
          fontSize: "1.2rem",
          fontWeight: "300",
          letterSpacing: "2px",
          textTransform: "uppercase",
          background: "linear-gradient(90deg, #a78bfa 0%, #60a5fa 50%, #14b8a6 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text"
        }}>
          Powered by Temporal
        </p>
      </header>

      <main className="resilient-main">
        {view === "config" && <ConfigView onSelectScenario={handleSelectScenario} />}
        {view === "workflow" && <WorkflowView scenario={selectedScenario} shipmentId={shipmentId} onReset={handleReset} />}
      </main>
    </div>
  );
}
