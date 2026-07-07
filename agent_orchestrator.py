import os
import json
import base64
from typing import TypedDict, Optional, Dict, Any
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

# Import our custom modules from previous steps
from gateway import AIModelGateway
from mcp_server import MCPServer
from mcp_client import MCPClient

# ==========================================
# 1. DEFINE THE LANGGRAPH STATE SCHEMA
# ==========================================
class SurveillanceState(TypedDict):
    """
    The shared memory blueprint for our surveillance graph execution.
    Tracks data accumulation and multi-agent reasoning paths.
    """
    image_path: str
    vlm_description: Optional[str]
    severity_score: Optional[int]
    planner_rationale: Optional[str]
    next_step: Optional[str]  # Controls conditional routing ("log_and_alert", "log_only", "ignore")
    execution_summary: Optional[str]

# ==========================================
# 2. IMPLEMENT THE AGENT NODES
# ==========================================
class SurveillanceAgents:
    def __init__(self, model_gateway: AIModelGateway, mcp_client: MCPClient):
        self.gateway = model_gateway
        self.mcp = mcp_client

    def encode_image_to_base64(self, image_path: str) -> str:
        """Helper function to format local binary images for Groq VLM consumption."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def vision_analysis_node(self, state: SurveillanceState) -> Dict[str, Any]:
        """
        Vision Agent: Uses Groq's open vision model to transform raw image pixels 
        into highly analytical textual context descriptions.
        """
        print("\n--- [Vision Agent] Analyzing Captured Frame ---")
        image_path = state["image_path"]
        
        try:
            base64_image = self.encode_image_to_base64(image_path)
            vision_model = self.gateway.get_model("vision")
            
            # Formulate structural multimodal message payload
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "Analyze this security surveillance frame. Describe what you see in detail. Focus specifically on safety anomalies, presence of humans, animals, objects left behind, or environmental hazards."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            )
            
            response = vision_model.invoke([message])
            return {"vlm_description": response.content}
        except Exception as e:
            print(f"[Vision Agent Error] Analysis failed: {e}")
            return {"vlm_description": f"Failed to parse image frame natively. Error: {str(e)}"}

    def planner_agent_node(self, state: SurveillanceState) -> Dict[str, Any]:
        """
        Planner Agent: Assesses the unstructured description, determines threat severity,
        and constructs a tactical execution directive.
        """
        print("\n--- [Planner Agent] Evaluating Threat Levels & Routing Paths ---")
        reasoning_model = self.gateway.get_model("reasoning")
        
        system_prompt = (
            "You are the central decision intelligence component of an Agentic Security Framework.\n"
            "You must review the visual description provided by the Vision Model and evaluate it across two strict criteria:\n"
            "1. Severity Score: An integer rating from 1 (completely safe/routine) to 5 (extreme hazard/breach).\n"
            "2. Next Action Step: Choose exactly one value from: ['ignore', 'log_only', 'log_and_alert']\n\n"
            "Guidelines:\n"
            "- Routine events (family pets, wind blowing trees, clear empty views) -> Severity 1 or 2 -> 'ignore'\n"
            "- Noticeable changes requiring audits (delivery drivers dropping packages, generic unknown personnel passing by) -> Severity 3 -> 'log_only'\n"
            "- High-risk activity (forced entries, fires, night-time boundary breaches) -> Severity 4 or 5 -> 'log_and_alert'\n\n"
            "🚨 ZERO TOLERANCE RULES 🚨\n"
            "- IF the description mentions a person with an OBSCURED FACE (mask, niqab, heavy head covering) AND they are holding ANY SHARP OBJECT or WEAPON (scissors, knives, tools), you MUST instantly assign Severity 5 and choose 'log_and_alert'. Do not assume they are safe. Assume hostile intent.\n\n"
            "Output your reasoning STRICTLY as a valid JSON object matching this structure:\n"
            "{\n"
            "  \"severity\": int,\n"
            "  \"rationale\": \"string explaining your assessment details\",\n"
            "  \"action\": \"string matching ignore/log_only/log_and_alert\"\n"
            "}"
        )
        
        user_prompt = f"Visual Input Description from Frame:\n{state['vlm_description']}"
        
        # Enforce structural JSON outputs from Groq LLM
        response = reasoning_model.invoke([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        
        try:
            # Strip markdown formatting if the LLM gets too helpful
            clean_text = response.content.replace("```json", "").replace("```", "").strip()
            
            # Parse response content cleanly
            data = json.loads(clean_text)
            return {
                "severity_score": data.get("severity", 3),
                "planner_rationale": data.get("rationale", "No explanation compiled."),
                "next_step": data.get("action", "log_only")
            }
        except Exception as parse_err:
            print(f"[Planner Error] Failed to extract strict JSON. Content: {response.content}")
            return {"severity_score": 3, "planner_rationale": "Fallback triggered due to formatting anomalies.", "next_step": "log_only"}
        
    def execution_agent_node(self, state: SurveillanceState) -> Dict[str, Any]:
        """
        Execution Agent: Reads the planner's routing directives and interacts with
        physical infrastructure by invoking tools through the MCP Client bridge.
        """
        print("\n--- [Execution Agent] Running System Interoperability Actions via MCP ---")
        action = state["next_step"]
        img = state["image_path"]
        desc = state["vlm_description"]
        sev = state["severity_score"]
        rat = state["planner_rationale"]
        
        logs = []
        
        # Action Step 1: Execute DB log logging tool if action is verified to need retention
        if action in ["log_only", "log_and_alert"]:
            db_args = {
                "image_path": img,
                "vlm_description": desc,
                "severity_score": sev,
                "agent_rationale": rat
            }
            db_res = self.mcp.execute_tool("log_security_event", db_args)
            logs.append(f"DB Action Result: {db_res}")
            
        # Action Step 2: Fire real-time notification alerts if severity demands it
        if action == "log_and_alert":
            alert_args = {
                "channel": "email", # Changed from 'console' to 'email'
                "message": f"CRITICAL SECURITY ALERT (Level {sev}): {rat}\n\nVision Model Analysis:\n{desc}",
                "image_path": img   # Passing the image to the MCP Server!
            }
            alert_res = self.mcp.execute_tool("dispatch_alert_notification", alert_args)
            logs.append(f"Alert Action Result: {alert_res}")

        if not logs:
            logs.append("Event determined benign. Graph closed execution with zero IO side-effects.")
            
        return {"execution_summary": "\n".join(logs)}

# ==========================================
# 3. COMPILING THE LANGGRAPH TOPOLOGY
# ==========================================
def router_logic(state: SurveillanceState) -> str:
    """The conditional routing function determining graph edge traversal paths."""
    target_action = state["next_step"]
    if target_action in ["log_only", "log_and_alert"]:
        return "execute_actions"
    return "terminate"

def build_surveillance_graph(agents_core: SurveillanceAgents) -> StateGraph:
    # Initialize the workflow graph bound to our structural state map
    workflow = StateGraph(SurveillanceState)
    
    # Register functional nodes onto the graph grid
    workflow.add_node("vision_analyzer", agents_core.vision_analysis_node)
    workflow.add_node("planner_brain", agents_core.planner_agent_node)
    workflow.add_node("mcp_executor", agents_core.execution_agent_node)
    
    # Establish base graph execution flow topology
    workflow.set_entry_point("vision_analyzer")
    workflow.add_edge("vision_analyzer", "planner_brain")
    
    # Configure conditional routing branch nodes out of the planner agent
    workflow.add_conditional_edges(
        "planner_brain",
        router_logic,
        {
            "execute_actions": "mcp_executor",
            "terminate": END
        }
    )
    
    # Loop completion out of execution nodes back to standard termination
    workflow.add_edge("mcp_executor", END)
    
    return workflow.compile()

if __name__ == "__main__":
    print("Verifying multi-agent orchestration setup...")
    
    # 1. Initialize core infrastructure dependencies 
    gateway = AIModelGateway()
    mcp_server = MCPServer(db_path="live_surveillance.db")
    mcp_client = MCPClient(server=mcp_server)
    
    # 2. Wire up the agent controllers
    agents = SurveillanceAgents(model_gateway=gateway, mcp_client=mcp_client)
    
    # 3. Compile the graph
    app = build_surveillance_graph(agents)
    
    # 4. Mock an incoming file trigger from Module 2 (Ensure temp_frames/test.jpg exists!)
    mock_frame = "temp_frames/event_1783334247.jpg" # Use your actual captured filename
    if not os.path.exists(mock_frame):
        os.makedirs("temp_frames", exist_ok=True)
        # Create a tiny dummy file for compilation validation if none exists
        with open(mock_frame, "wb") as f:
            f.write(b"\x00" * 1000)
            
    initial_state = {"image_path": mock_frame}
    
    print("\nStarting graph run invocation...")
    final_output = app.invoke(initial_state)
    print("\n--- [Graph Run Complete] Final Evaluated State Output ---")
    print(json.dumps(final_output, indent=2))