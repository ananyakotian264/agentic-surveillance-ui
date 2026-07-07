from typing import Dict, Any, List
from mcp_server import MCPServer

class MCPClient:
    """
    Acts as the interface bridge layer that binds the host application
    to the active MCP Server capabilities.
    """
    def __init__(self, server: MCPServer):
        self.server = server

    def discover_tools(self) -> List[Dict[str, Any]]:
        """Queries the MCP Server for available tool declarations."""
        return self.server.list_tools()

    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Forwards execution instructions securely down to the target server."""
        print(f"[MCP Client] Sending request execution for tool: '{name}'")
        return self.server.call_tool(name, args)

# Execution Verification Step
if __name__ == "__main__":
    print("Testing decoupled MCP Architecture Loop...")
    
    # 1. Start Server Instance
    server_instance = MCPServer(db_path="test_surveillance.db")
    
    # 2. Connect Client Pipeline
    client = MCPClient(server=server_instance)
    
    # 3. Discover tool capabilities
    available_tools = client.discover_tools()
    print(f"\nDiscovered {len(available_tools)} tools from server:")
    for t in available_tools:
        print(f" - {t['name']}: {t['description']}")

    # 4. Test tool invocation isolation
    test_args = {
        "image_path": "temp_frames/event_101.jpg",
        "vlm_description": "A dark human silhouette detected near the rear doorway.",
        "severity_score": 4,
        "agent_rationale": "High structural anomaly risk. Potential break-in attempt."
    }
    
    response = client.execute_tool("log_security_event", test_args)
    print(f"\nServer Response Execution Output:\n{response}")
    
    # Clean up test database file cleanly
    if os.path.exists("test_surveillance.db"):
        os.remove("test_surveillance.db")