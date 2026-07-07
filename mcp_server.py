import psycopg2
import os
import json
import smtplib
from datetime import datetime
from typing import Dict, Any, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from dotenv import load_dotenv

# Load credentials
load_dotenv()

class MCPServer:
    def __init__(self):
        # Read the cloud database URL from the .env file
        self.db_url = os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("CRITICAL: DATABASE_URL is missing from environment variables.")
            
        self._initialize_database()
        self.tools_registry = {}
        self._register_tools()

    def _get_db_connection(self):
        """Helper to establish a fresh connection to the Supabase Cloud DB."""
        return psycopg2.connect(self.db_url)

    def _initialize_database(self):
        """Creates the PostgreSQL event table in the cloud if it doesn't exist."""
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # PostgreSQL uses SERIAL instead of AUTOINCREMENT
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS security_events (
                            id SERIAL PRIMARY KEY,
                            timestamp TEXT NOT NULL,
                            image_path TEXT NOT NULL,
                            vlm_description TEXT NOT NULL,
                            severity_score INTEGER NOT NULL,
                            agent_rationale TEXT NOT NULL,
                            action_taken TEXT NOT NULL
                        )
                    """)
                conn.commit()
            print("[MCP Server] Successfully connected to Cloud PostgreSQL Database.")
        except Exception as e:
            print(f"[MCP Server Error] Failed to initialize cloud database: {e}")

    def _register_tools(self):
        self.tools_registry["log_security_event"] = {
            "name": "log_security_event",
            "description": "Logs a critical or verified security event directly into the cloud database.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string"},
                    "vlm_description": {"type": "string"},
                    "severity_score": {"type": "integer"},
                    "agent_rationale": {"type": "string"}
                },
                "required": ["image_path", "vlm_description", "severity_score", "agent_rationale"]
            },
            "handler": self._tool_log_security_event
        }

        self.tools_registry["dispatch_alert_notification"] = {
            "name": "dispatch_alert_notification",
            "description": "Dispatches real-time high-priority text alerts regarding critical security breaches.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "enum": ["console", "email"]},
                    "message": {"type": "string"},
                    "image_path": {"type": "string"}
                },
                "required": ["channel", "message"]
            },
            "handler": self._tool_dispatch_alert_notification
        }

    def _tool_log_security_event(self, image_path: str, vlm_description: str, severity_score: int, agent_rationale: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action_taken = "Logged to Cloud DB"
        try:
            with self._get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # PostgreSQL uses %s for parameterized queries instead of ?
                    cursor.execute("""
                        INSERT INTO security_events (timestamp, image_path, vlm_description, severity_score, agent_rationale, action_taken)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (timestamp, image_path, vlm_description, severity_score, agent_rationale, action_taken))
                conn.commit()
            return json.dumps({"status": "SUCCESS", "message": "Successfully inserted incident into Cloud DB."})
        except Exception as e:
            return json.dumps({"status": "ERROR", "message": str(e)})

    # ... [Keep your exact _tool_dispatch_alert_notification method here] ...
    def _tool_dispatch_alert_notification(self, channel: str, message: str, image_path: str = None) -> str:
        if channel == "email":
            sender = os.getenv("SENDER_EMAIL")
            password = os.getenv("EMAIL_APP_PASSWORD")
            receiver = os.getenv("RECEIVER_EMAIL")
            
            if not all([sender, password, receiver]):
                return json.dumps({"status": "ERROR", "message": "Email credentials missing in .env file."})

            try:
                msg = MIMEMultipart()
                msg['Subject'] = "🚨 AGENTIC AI SURVEILLANCE: CRITICAL THREAT DETECTED"
                msg['From'] = sender
                msg['To'] = receiver
                
                msg.attach(MIMEText(message, 'plain'))
                
                if image_path and os.path.exists(image_path):
                    with open(image_path, 'rb') as f:
                        img_data = f.read()
                    image_attachment = MIMEImage(img_data, name=os.path.basename(image_path))
                    msg.attach(image_attachment)
                
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(sender, password)
                    server.send_message(msg)
                    
                print(f"[MCP EMAIL ROUTER] Successfully sent threat report to {receiver}")
                return json.dumps({"status": "SUCCESS", "message": "Email dispatched with image attachment."})
                
            except Exception as e:
                print(f"[MCP EMAIL ROUTER ERROR] {str(e)}")
                return json.dumps({"status": "ERROR", "message": f"SMTP failed: {str(e)}"})

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"⚠️ [ALERT VIA {channel.upper()}] @ {timestamp} -> {message}")
        return json.dumps({"status": "SUCCESS", "dispatched_channel": channel})

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{k: v for k, v in tool.items() if k != "handler"} for tool in self.tools_registry.values()]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if tool_name not in self.tools_registry:
            return json.dumps({"status": "ERROR", "message": f"Tool '{tool_name}' not found."})
        handler = self.tools_registry[tool_name]["handler"]
        try:
            return handler(**arguments)
        except TypeError as e:
            return json.dumps({"status": "ERROR", "message": f"Invalid arguments: {str(e)}"})