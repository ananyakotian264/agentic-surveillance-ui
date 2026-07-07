import cv2
import time
import os
import threading

# Import your LangGraph architecture
from agent_orchestrator import AIModelGateway, MCPServer, MCPClient, SurveillanceAgents, build_surveillance_graph

class MotionDetector:
    def __init__(self, threshold=25, min_area=5000, cooldown=10):
        self.threshold = threshold
        self.min_area = min_area
        self.cooldown = cooldown # Increased cooldown to 10s to give agents time to process
        
        self.last_capture_time = 0
        self.baseline_image = None
        self.output_dir = "temp_frames"
        os.makedirs(self.output_dir, exist_ok=True)

        
        # Initialize the Agentic Infrastructure once on startup
        print("Initializing Agentic AI Infrastructure...")
        gateway = AIModelGateway()
        mcp_server = MCPServer()
        mcp_client = MCPClient(server=mcp_server)
        agents = SurveillanceAgents(model_gateway=gateway, mcp_client=mcp_client)
        
        self.agent_app = build_surveillance_graph(agents)
        print("Agents ready.")

    def process_frame(self, frame):
        # [Same CV logic as before]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.baseline_image is None:
            self.baseline_image = gray
            return False, frame

        frame_delta = cv2.absdiff(self.baseline_image, gray)
        _, thresh = cv2.threshold(frame_delta, self.threshold, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) < self.min_area:
                continue
            (x, y, w, h) = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            motion_detected = True

        return motion_detected, frame

    def run_agent_workflow(self, filepath):
        """Runs the LangGraph orchestration in a separate thread to prevent camera lag."""
        print(f"\n[TRIGGER] Handing frame {filepath} to LangGraph...")
        self.agent_app.invoke({"image_path": filepath})
        print("[COMPLETE] Agent workflow finished.\n")
        
    def capture_feed(self):
        print("Starting smart surveillance feed... Press 'q' to quit.")
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        time.sleep(2.0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            motion, processed_frame = self.process_frame(frame)
            
            if motion:
                current_time = time.time()
                if current_time - self.last_capture_time > self.cooldown:
                    filepath = os.path.join(self.output_dir, f"event_{int(current_time)}.jpg")
                    cv2.imwrite(filepath, processed_frame)
                    
                    self.last_capture_time = current_time
                    
                    # Fire off the agent logic asynchronously
                    threading.Thread(target=self.run_agent_workflow, args=(filepath,)).start()
            
            cv2.imshow("Surveillance Feed (Background Task)", processed_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    detector = MotionDetector()
    detector.capture_feed()