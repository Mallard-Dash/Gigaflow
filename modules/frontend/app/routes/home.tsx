import { useState, useEffect, useRef } from "react";
import type { Route } from "./+types/home";
import {
  Clock, Package, Plane, Zap, XOctagon, CheckCircle, Truck, RefreshCw, 
  AlertTriangle, User, Ban, ArrowUpRight, GitFork, Pause, Play, DollarSign
} from 'lucide-react';

export function meta({}: Route.MetaArgs) {
  return [
    { title: "ResilientFlow - Global Logistics" },
    { name: "description", content: "Global Logistics Simulation powered by Temporal" },
  ];
}

// --- CONSTANTS ---

const WORKFLOW_STEPS = [
  'Order Received', 'Payment OK', 'Warehouse Allocation',
  'Packaged (Factory)', 'Transport Started', 'Customs Clearance',
  'Local Delivery', 'Delivered'
];

const BASELINE_ETA_MS = 5 * 24 * 60 * 60 * 1000; // 5 days baseline

const SCENARIOS = [
  { 
    id: 'happy-path', 
    name: 'EU Standard', 
    icon: CheckCircle, 
    description: 'Successful flow. Ships from Estonia.' 
  },
  { 
    id: 'payment-failure', 
    name: 'Far East', 
    icon: XOctagon, 
    description: 'Bank Server Down. Payment failed/retried.' 
  },
  { 
    id: 'warehouse-stock', 
    name: 'Volatile Stock', 
    icon: Package, 
    description: 'High-Demand Stock Failure. Requires Human Intervention.' 
  },
  { 
    id: 'transport-delay', 
    name: 'High Risk', 
    icon: Plane, 
    description: 'Severe weather delay. Requires Logistics Intervention.' 
  },
  { 
    id: 'customs-issue', 
    name: 'High-Spec', 
    icon: Truck, 
    description: 'Lab inspection failure on a critical component. Requires Business Decision.' 
  },
];

// Map backend states to step indices
const STATE_TO_STEP: Record<string, number> = {
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

// --- HELPER FUNCTIONS ---

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:32776';

// --- UI COMPONENTS ---

const Timeline = ({ currentStepIndex, status, hitlRequired }: { 
  currentStepIndex: number; 
  status: string; 
  hitlRequired: boolean;
}) => {
  return (
    <div className="flex flex-col items-center p-4">
      <h3 className="text-xl font-bold text-gray-200 mb-6 border-b border-indigo-700 w-full text-center pb-2">
        Order Status Timeline
      </h3>
      <div className="w-full flex justify-between relative">
        {/* Horizontal Progress Line */}
        <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-700 -translate-y-1/2 rounded-full">
          <div
            className={`absolute h-1 rounded-full transition-all duration-1000 ease-in-out ${
              status === 'Cancelled' || status === 'CRITICAL_HALT' ? 'bg-fuchsia-600' : 'bg-teal-500'
            }`}
            style={{ width: `${(currentStepIndex / (WORKFLOW_STEPS.length - 1)) * 100}%` }}
          ></div>
        </div>

        {WORKFLOW_STEPS.map((step, index) => {
          const isCompleted = index < currentStepIndex;
          const isActive = index === currentStepIndex;
          const isFailed = (status === 'Cancelled' || status === 'CRITICAL_HALT') && index === currentStepIndex;

          let dotClasses = 'w-6 h-6 rounded-full border-4 flex items-center justify-center transition-all duration-500 relative';
          let icon = null;

          if (isCompleted) {
            dotClasses += ' bg-teal-500 border-teal-800';
            icon = <CheckCircle className="w-4 h-4 text-white" />;
          } else if (isActive) {
            if (status === 'Cancelled' || status === 'CRITICAL_HALT') {
              dotClasses += ' bg-fuchsia-600 border-fuchsia-900 shadow-fuchsia-600/50 shadow-lg animate-pulse';
              icon = <Ban className="w-4 h-4 text-white" />;
            } else if (status === 'Paused' && hitlRequired) {
              dotClasses += ' bg-amber-500 border-amber-800 shadow-amber-500/50 shadow-lg animate-pulse';
              icon = <AlertTriangle className="w-4 h-4 text-white" />;
            } else {
              dotClasses += ' bg-indigo-600 border-indigo-900 shadow-indigo-600/50 shadow-lg animate-pulse';
              icon = <GitFork className="w-4 h-4 text-white" />;
            }
          } else {
            dotClasses += ' bg-gray-600 border-gray-800';
            icon = <ArrowUpRight className="w-4 h-4 text-gray-400" />;
          }

          return (
            <div key={step} className="flex flex-col items-center z-10 w-1/8">
              <div className={dotClasses}>
                {icon}
              </div>
              <span className={`mt-3 text-xs text-center font-medium ${
                isCompleted ? 'text-teal-400' : isActive ? 'text-white font-semibold' : 'text-gray-400'
              }`}>
                {step}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const StatusBadge = ({ status }: { status: string }) => {
  let color = 'bg-gray-600';
  let text = status;
  let icon = <RefreshCw className="w-4 h-4 mr-1" />;

  switch (status) {
    case 'Running':
      color = 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/50';
      icon = <RefreshCw className="w-4 h-4 mr-1 animate-spin" />;
      break;
    case 'Paused':
      color = 'bg-amber-600 text-black shadow-lg shadow-amber-500/50';
      icon = <AlertTriangle className="w-4 h-4 mr-1" />;
      break;
    case 'Completed':
      color = 'bg-teal-500 text-black shadow-lg shadow-teal-500/50';
      icon = <CheckCircle className="w-4 h-4 mr-1" />;
      break;
    case 'Cancelled':
      color = 'bg-fuchsia-600 text-white shadow-lg shadow-fuchsia-500/50';
      icon = <XOctagon className="w-4 h-4 mr-1" />;
      break;
    case 'CRITICAL_HALT':
      color = 'bg-red-800 text-white shadow-xl shadow-red-700/50 animate-pulse';
      icon = <Ban className="w-4 h-4 mr-1" />;
      text = 'CRITICAL HALT';
      break;
  }
  
  return (
    <span className={`inline-flex items-center px-4 py-1 text-sm font-bold uppercase rounded-full ${color}`}>
      {icon} {text}
    </span>
  );
};

const ScenarioSelector = ({ startWorkflow, isLoading }: { 
  startWorkflow: (id: string) => void; 
  isLoading: boolean;
}) => (
  <div className="p-8 rounded-2xl shadow-2xl bg-gray-800/70 border-t-4 border-indigo-700/50 backdrop-blur-sm">
    <h2 className="text-3xl font-extrabold mb-6 text-white border-b border-fuchsia-500 pb-3">
      Start a New ResilientFlow
    </h2>
    <div className="grid grid-cols-1 gap-4">
      {SCENARIOS.map(scenario => {
        const Icon = scenario.icon;
        const isFocus = ['warehouse-stock', 'transport-delay', 'customs-issue', 'payment-failure'].includes(scenario.id);
        const focusClass = isFocus 
          ? 'border-2 border-fuchsia-500/80 bg-fuchsia-950/30' 
          : 'border border-gray-700 bg-gray-900/50';

        return (
          <button
            key={scenario.id}
            onClick={() => startWorkflow(scenario.id)}
            disabled={isLoading}
            className={`text-left p-4 rounded-xl transition duration-300 transform hover:scale-[1.01] disabled:opacity-50 disabled:cursor-not-allowed ${focusClass}`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <Icon className="w-6 h-6 text-teal-400 mr-3" />
                <span className={`text-xl font-bold ${isFocus ? 'text-fuchsia-300' : 'text-white'}`}>
                  {scenario.name}
                </span>
              </div>
            </div>
            <p className="mt-1 text-sm text-gray-400 ml-9">{scenario.description}</p>
            {isLoading && <span className="text-xs text-indigo-500 mt-1 ml-9">Starting Temporal Worker...</span>}
          </button>
        );
      })}
    </div>
  </div>
);

const TerminalLog = ({ logs }: { logs: Array<{ id: string; message: string; timestamp: string }> }) => {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  const reversedLogs = [...logs].reverse();

  return (
    <div className="flex flex-col h-full">
      <h3 className="text-xl font-extrabold mb-3 text-white border-b border-indigo-700 pb-2">
        <Zap className="inline w-5 h-5 mr-2 text-teal-400" />
        Activity Log (Temporal History)
      </h3>
      <div
        ref={logRef}
        className="flex-grow overflow-y-auto bg-gray-950 text-green-400 p-4 rounded-xl font-mono text-xs shadow-inner border border-gray-700 space-y-1 custom-scrollbar"
        style={{ height: '300px' }}
      >
        {reversedLogs.map((log) => (
          <div key={log.id} className="text-right">
            <span className="text-gray-500 mr-2">
              [{new Date(log.timestamp).toLocaleTimeString()}]
            </span>
            <span 
              className="text-left inline-block" 
              dangerouslySetInnerHTML={{ 
                __html: log.message
                  .replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-yellow-300">$1</strong>')
                  .replace(/➡️/g, '<span class="text-teal-400">➡️</span>')
                  .replace(/⚠️/g, '<span class="text-amber-400">⚠️</span>')
                  .replace(/🛑/g, '<span class="text-red-500">🛑</span>')
                  .replace(/🚨/g, '<span class="text-red-500">🚨</span>')
                  .replace(/🚀/g, '<span class="text-fuchsia-400">🚀</span>')
                  .replace(/✅/g, '<span class="text-teal-400">✅</span>')
                  .replace(/❌/g, '<span class="text-red-400">❌</span>')
              }} 
            />
          </div>
        ))}
        <div className="text-teal-500 text-right sticky bottom-0 bg-gray-950 pt-1">
          <span>{'>'} Worker is listening for Signals...</span>
        </div>
      </div>
    </div>
  );
};

const HitlPanel = ({ 
  message, 
  options,
  enhancedOptions,
  backupCapacityHours,
  signalWorkflow 
}: { 
  message: string; 
  options: string[];
  enhancedOptions?: Array<{text: string; cost: string; time_impact: string}>;
  backupCapacityHours?: number;
  signalWorkflow: (choice: string) => void;
}) => {
  if (!message) return null;

  const displayOptions = enhancedOptions && enhancedOptions.length > 0 ? enhancedOptions : 
    options.map(opt => ({ text: opt, cost: '$0', time_impact: 'Unknown' }));

  return (
    <div className="bg-fuchsia-950/70 border-4 border-fuchsia-500/50 p-6 rounded-xl shadow-2xl mt-6 backdrop-blur-sm animate-flash-border">
      <h3 className="text-2xl font-extrabold text-fuchsia-300 flex items-center mb-4 border-b border-fuchsia-500/50 pb-2">
        <AlertTriangle className="w-6 h-6 mr-3 text-fuchsia-400" /> 
        CRITICAL HUMAN-IN-THE-LOOP INTERVENTION
      </h3>
      <p
        className="text-lg text-gray-100 mb-4 font-medium"
        dangerouslySetInnerHTML={{ 
          __html: message.replace(/\*\*(.*?)\*\*/g, '<strong class="font-extrabold text-yellow-300">$1</strong>') 
        }}
      />
      
      {backupCapacityHours && (
        <div className="mb-6 p-4 bg-amber-900/30 border-2 border-amber-500/50 rounded-lg">
          <p className="text-amber-200 font-bold flex items-center">
            <Clock className="w-5 h-5 mr-2" />
            ⚠️ Backup Warehouse Parts Available: Only <span className="text-amber-400 mx-1 text-xl">{backupCapacityHours}</span> hours of production capacity!
          </p>
          <p className="text-amber-300/80 text-sm mt-1">
            Choose wisely - production line may stop if parts run out.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3">
        {displayOptions.map((option, index) => (
          <button
            key={index}
            onClick={() => signalWorkflow(option.text)}
            className="w-full p-4 rounded-lg font-bold text-left transition duration-300 transform hover:scale-[1.01] bg-indigo-700/80 text-white border border-indigo-500 hover:bg-indigo-600 group"
          >
            <div className="flex justify-between items-start">
              <span className="text-base uppercase tracking-wide">{option.text}</span>
              <div className="flex flex-col items-end">
                <span className={`text-lg font-extrabold ${option.cost === '$0' ? 'text-teal-400' : 'text-amber-400'}`}>
                  {option.cost}
                </span>
                <span className="text-xs text-gray-300 mt-1">
                  {option.time_impact}
                </span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

// --- MAIN COMPONENT ---

export default function Home() {
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [workflowState, setWorkflowState] = useState<any>(null);
  const [logs, setLogs] = useState<Array<{ id: string; message: string; timestamp: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startTime, setStartTime] = useState<number>(Date.now());
  const seenEventsRef = useRef(new Set<string>());

  // Poll workflow status
  useEffect(() => {
    if (!workflowId) return;

    let active = true;
    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE}/shipments/${workflowId}`);
        const data = await response.json();
        
        if (active) {
          setWorkflowState(data);
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    poll();
    const interval = setInterval(poll, 2000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [workflowId]);

  // Process workflow state changes into logs
  useEffect(() => {
    if (!workflowState) return;

    const addLog = (message: string, eventKey: string) => {
      if (seenEventsRef.current.has(eventKey)) return;
      
      seenEventsRef.current.add(eventKey);
      setLogs(prev => [...prev, {
        id: Date.now().toString() + Math.random(),
        message,
        timestamp: new Date().toISOString()
      }]);
    };

    const status = workflowState.status;
    const currentError = workflowState.current_error;
    
    // Log status changes
    const statusKey = `status-${status}`;
    if (!seenEventsRef.current.has(statusKey)) {
      addLog(`✅ Status updated: **${status}**`, statusKey);
    }

    // Log errors
    if (currentError) {
      const errorKey = `error-${currentError.reason}`;
      if (!seenEventsRef.current.has(errorKey)) {
        addLog(`⚠️ ${currentError.details}`, errorKey);
      }
    }

    // Log completion
    if (status === 'DELIVERED') {
      const doneKey = 'workflow-completed';
      if (!seenEventsRef.current.has(doneKey)) {
        addLog('🎉 **Shipment completed! Workflow done.**', doneKey);
      }
    }

    // Log cancellation
    if (status === 'CANCELED') {
      const cancelKey = 'workflow-cancelled';
      if (!seenEventsRef.current.has(cancelKey)) {
        addLog('❌ **Workflow cancelled.**', cancelKey);
      }
    }
  }, [workflowState]);

  const startWorkflow = async (scenarioId: string) => {
    setIsLoading(true);
    setError(null);
    setLogs([]);
    seenEventsRef.current.clear();
    
    try {
      const response = await fetch(`${API_BASE}/shipments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId })
      });
      
      const data = await response.json();
      setWorkflowId(data.shipment_id);
      setStartTime(Date.now());
      
      const scenario = SCENARIOS.find(s => s.id === scenarioId);
      setLogs([{
        id: Date.now().toString(),
        message: `🚀 Workflow started for scenario: **${scenario?.name}**`,
        timestamp: new Date().toISOString()
      }]);
    } catch (err) {
      setError('Failed to start workflow');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const signalWorkflow = async (choice: string) => {
    if (!workflowId) return;

    // Map frontend choices to backend enum values
    const choiceMap: Record<string, string> = {
      "Send to tech support": "SEND_TO_TECH_SUPPORT",
      "Retry payment": "RETRY_PAYMENT",
      "Resume when ready": "RESUME_WHEN_READY",
      "Cancel order": "CANCEL_ORDER",
      "Accept new price": "ACCEPT_NEW_PRICE",
      "Update order": "UPDATE_ORDER",
      "Adjust quantity": "ADJUST_QUANTITY",
      "Allocate from different warehouse": "ALLOCATE_DIFFERENT",
      "Wait for stock to be replenished": "WAIT_FOR_STOCK",
      "Notice customers and offer refunds": "NOTICE_CUSTOMERS_REFUND",
      "Do nothing and wait out bad weather (pause workflow)": "WAIT_OUT_WEATHER",
      "Reroute shipment from unaffected supplier (high cost)": "REROUTE_SHIPMENT",
      "Provide additional documentation": "PROVIDE_DOCUMENTATION",
      "Pay expedited processing fee": "PAY_EXPEDITED_FEE",
      "Accept delay": "ACCEPT_DELAY",
      "Return shipment": "RETURN_SHIPMENT",
      "Reroute from another supplier (more expensive, but faster)": "REROUTE_SHIPMENT",
      "Schedule new delivery time": "SCHEDULE_NEW_TIME",
      "Leave at safe location": "LEAVE_SAFE_LOCATION",
      "Return to depot for pickup": "RETURN_TO_DEPOT",
      "Do nothing (small delay)": "DO_NOTHING",
      "Inform customers": "INFORM_CUSTOMERS",
      "Contact and rearrange logistics-hub timeslots": "REARRANGE_LOGISTICS"
    };

    const operatorChoice = choiceMap[choice];
    
    try {
      if (operatorChoice === "CANCEL_ORDER" || operatorChoice === "RETURN_SHIPMENT") {
        await fetch(`${API_BASE}/shipments/${workflowId}`, { method: 'DELETE' });
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          message: '❌ **Order cancelled by operator**',
          timestamp: new Date().toISOString()
        }]);
      } else {
        await fetch(`${API_BASE}/shipments/${workflowId}/handle-resolution`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ choice: operatorChoice })
        });
        
        setLogs(prev => [...prev, {
          id: Date.now().toString(),
          message: `✅ **HITL Action:** ${choice}`,
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (err) {
      console.error('Error sending signal:', err);
      setError('Failed to send signal');
    }
  };

  const isWorkflowActive = !!workflowId && workflowState;
  const currentStatus = workflowState?.status || 'Idle';
  const currentStepIndex = STATE_TO_STEP[currentStatus] || 0;
  const currentError = workflowState?.current_error;
  const hitlRequired = !!currentError?.resolution_options?.length;
  
  // Handle CRITICAL_HALT state
  const displayStatus = currentStatus === 'CRITICAL_HALT' ? 'CRITICAL_HALT' 
    : currentStatus === 'DELIVERED' ? 'Completed' 
    : currentStatus === 'CANCELED' ? 'Cancelled' 
    : hitlRequired ? 'Paused' 
    : 'Running';

  // Calculate ETA
  let etaDate = 'N/A';
  let isPastDue = false;
  
  if (workflowState && startTime) {
    const finalEtaMs = startTime + BASELINE_ETA_MS;
    const finalEta = new Date(finalEtaMs);
    etaDate = finalEta.toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
    
    if (currentStatus !== 'DELIVERED' && currentStatus !== 'CANCELED' && Date.now() > finalEtaMs) {
      isPastDue = true;
    }
  }

  const currentScenario = SCENARIOS.find(s => s.id === workflowState?.scenario);

  return (
    <div className="min-h-screen bg-[#130722] text-white font-sans p-4 sm:p-8">
      <header className="py-6 mb-10">
        <div className="flex justify-between items-center border-b border-indigo-700 pb-4">
          <h1 className="text-4xl font-extrabold text-fuchsia-400 tracking-wider">
            ResilientFlow
          </h1>
          <div className="text-right">
            <p className="text-xs text-gray-500 mt-2 flex items-center justify-end">
              <User className="w-4 h-4 mr-1"/> 
              Operator ID: <span className="font-mono text-xs ml-1 bg-gray-800 text-teal-300 px-2 py-0.5 rounded-md">
                temporal-1
              </span>
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto">
        {error && (
          <div className="bg-red-900 border border-red-500 text-red-300 px-4 py-3 rounded-lg relative mb-6" role="alert">
            {error}
          </div>
        )}

        {!isWorkflowActive && (
          <ScenarioSelector startWorkflow={startWorkflow} isLoading={isLoading} />
        )}

        {isWorkflowActive && (
          <div className="space-y-6">
            {/* Main Status Card */}
            <div className="bg-gray-800/70 p-6 rounded-2xl shadow-2xl backdrop-blur-sm border-t-4 border-teal-500/50">
              <h2 className="text-3xl font-extrabold mb-4 text-white border-b border-indigo-700 pb-2">
                Active Workflow: <span className="text-teal-400">{currentScenario?.name || 'Loading...'}</span>
              </h2>
              <div className="flex flex-wrap items-center gap-4">
                <StatusBadge status={displayStatus} />

                <span className="text-lg font-bold flex items-center text-gray-300">
                  ID: <span className="font-mono text-sm ml-2 text-fuchsia-400">{workflowId?.slice(-8) || 'N/A'}</span>
                </span>

                <span className={`text-lg font-bold flex items-center ${isPastDue ? 'text-fuchsia-400 animate-pulse' : 'text-gray-300'}`}>
                  <Clock className="w-5 h-5 mr-2" />
                  ETA: {etaDate}
                  {isPastDue && (
                    <span className="ml-2 text-xs bg-fuchsia-600 text-white px-2 py-0.5 rounded-full font-bold shadow-lg shadow-fuchsia-500/50">
                      PAST DUE!
                    </span>
                  )}
                </span>

                {currentStatus !== 'DELIVERED' && currentStatus !== 'CANCELED' && (
                  <button
                    onClick={async () => {
                      try {
                        const endpoint = workflowState?.is_paused ? 'resume' : 'pause';
                        await fetch(`${API_BASE}/shipments/${workflowId}/${endpoint}`, {
                          method: 'POST'
                        });
                        setLogs(prev => [...prev, {
                          id: Date.now().toString(),
                          message: `${workflowState?.is_paused ? '▶️' : '⏸️'} Workflow ${workflowState?.is_paused ? 'resumed' : 'paused'} by operator`,
                          timestamp: new Date().toISOString()
                        }]);
                      } catch (err) {
                        console.error('Pause/resume error:', err);
                      }
                    }}
                    className={`px-4 py-2 rounded-lg font-bold text-sm uppercase tracking-wider transition duration-300 transform hover:scale-105 flex items-center ${
                      workflowState?.is_paused 
                        ? 'bg-teal-600 hover:bg-teal-500 text-white' 
                        : 'bg-amber-600 hover:bg-amber-500 text-black'
                    }`}
                  >
                    {workflowState?.is_paused ? (
                      <><Play className="w-4 h-4 mr-1" /> Resume</>
                    ) : (
                      <><Pause className="w-4 h-4 mr-1" /> Pause</>
                    )}
                  </button>
                )}
              </div>
            </div>

            {/* Timeline */}
            <div className="bg-gray-800/70 p-6 rounded-2xl shadow-2xl backdrop-blur-sm border border-indigo-700/50">
              <Timeline
                currentStepIndex={currentStepIndex}
                status={displayStatus}
                hitlRequired={hitlRequired}
              />
            </div>

            {/* Show CRITICAL HALT message */}
            {currentStatus === 'CRITICAL_HALT' && (
              <div className="bg-red-950/70 border-4 border-red-500/50 p-6 rounded-xl shadow-2xl mt-6 backdrop-blur-sm animate-flash-border">
                <h3 className="text-2xl font-extrabold text-red-300 flex items-center mb-4">
                  <Ban className="w-6 h-6 mr-3 text-red-400" /> PRODUCTION HALTED
                </h3>
                <p className="text-lg text-gray-100">
                  🚨 <strong>CRITICAL FAILURE!</strong> The 15-second deadline for human intervention was missed. 
                  Production line has <strong>**HALTED**</strong>. Workflow terminated.
                </p>
                <p className="text-red-300/80 text-sm mt-3">
                  Management has been notified. Order permanently cancelled.
                </p>
              </div>
            )}

            {/* HITL Intervention Panel */}
            {hitlRequired && currentStatus !== 'CRITICAL_HALT' && (
              <HitlPanel
                message={currentError.details}
                options={currentError.resolution_options}
                enhancedOptions={currentError.enhanced_options}
                backupCapacityHours={currentError.backup_warehouse_capacity_hours}
                signalWorkflow={signalWorkflow}
              />
            )}

            {/* Workflow Summary - Shown on completion */}
            {currentStatus === 'DELIVERED' && workflowState?.summary && (
              <div className="bg-teal-900/30 border-2 border-teal-500 p-6 rounded-xl shadow-2xl backdrop-blur-sm">
                <h3 className="text-2xl font-extrabold text-teal-300 flex items-center mb-4 border-b border-teal-500/50 pb-2">
                  <CheckCircle className="w-6 h-6 mr-3" />
                  📊 Workflow Summary & Cost Analysis
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-gray-900/50 p-4 rounded-lg">
                    <p className="text-gray-400 text-sm mb-1">Total Cost</p>
                    <p className="text-3xl font-extrabold text-amber-400 flex items-center">
                      <DollarSign className="w-6 h-6 mr-1" />
                      {workflowState.summary.total_cost.toFixed(2)}
                    </p>
                  </div>
                  <div className="bg-gray-900/50 p-4 rounded-lg">
                    <p className="text-gray-400 text-sm mb-1">Time Impact</p>
                    <p className={`text-3xl font-extrabold ${workflowState.summary.time_saved_hours >= 0 ? 'text-teal-400' : 'text-fuchsia-400'}`}>
                      {workflowState.summary.time_saved_hours >= 0 ? '+' : ''}{workflowState.summary.time_saved_hours.toFixed(1)}h
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {workflowState.summary.time_saved_hours >= 0 ? 'Saved' : 'Delayed'}
                    </p>
                  </div>
                </div>

                {workflowState.summary.production_line_stopped && (
                  <div className="mt-4 bg-red-900/30 border-2 border-red-500 p-4 rounded-lg">
                    <p className="text-red-300 font-bold text-lg mb-2">⚠️ Production Line Stoppage Occurred</p>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-gray-400 text-sm">Stop Duration</p>
                        <p className="text-xl font-bold text-red-400">{workflowState.summary.production_stop_duration_hours.toFixed(1)}h</p>
                      </div>
                      <div>
                        <p className="text-gray-400 text-sm">Production Loss</p>
                        <p className="text-xl font-bold text-red-400">${workflowState.summary.production_loss_cost.toFixed(2)}</p>
                      </div>
                    </div>
                    <p className="text-red-300/80 text-sm mt-2">
                      Loss calculated at $100/minute of downtime
                    </p>
                  </div>
                )}

                {workflowState.summary.avoided_production_stop && (
                  <div className="mt-4 bg-teal-900/30 border-2 border-teal-500 p-4 rounded-lg">
                    <p className="text-teal-300 font-bold text-lg">✅ Production Stop Avoided!</p>
                    <p className="text-teal-300/90 text-sm mt-1">
                      Expensive option prevented production line stoppage. Cost was high (${workflowState.summary.total_cost.toFixed(2)}) but loss is zero because production never stopped.
                    </p>
                  </div>
                )}

                {workflowState.summary.decisions_made && workflowState.summary.decisions_made.length > 0 && (
                  <div className="mt-4">
                    <p className="text-gray-300 font-bold mb-2">Decisions Made:</p>
                    <ul className="space-y-1">
                      {workflowState.summary.decisions_made.map((decision: string, i: number) => (
                        <li key={i} className="text-sm text-gray-400 flex items-start">
                          <span className="text-teal-400 mr-2">→</span>
                          {decision}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
            
            {/* Terminal Log Panel */}
            <div className="bg-gray-800/70 p-6 rounded-2xl shadow-2xl backdrop-blur-sm border border-gray-700">
              <TerminalLog logs={logs} />
            </div>
          </div>
        )}
      </main>

      <footer className="mt-16 pt-4 border-t border-indigo-700 text-center text-sm text-gray-500 max-w-4xl mx-auto">
        <p>A Global Logistics Simulation powered by Temporal Workflow principles.</p>
      </footer>

      {/* Custom CSS */}
      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes flash-border {
          0%, 100% { border-color: rgba(236, 72, 153, 0.3); }
          50% { border-color: rgba(236, 72, 153, 0.8); }
        }
        .animate-flash-border {
          animation: flash-border 2s infinite;
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #1f2937;
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #10b981;
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #059669;
        }
      `}} />
    </div>
  );
}
