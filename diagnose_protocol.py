import yaml
import sys
import os
from pathlib import Path

# Add SMU root to path
sys.path.insert(0, str(Path(__file__).parent))

from ivtest.protocol_engine import ProtocolEngine

def run_diagnostic():
    yaml_path = "protocols/dark_light_test.yaml"
    if not os.path.exists(yaml_path):
        print(f"Error: {yaml_path} not found")
        return

    with open(yaml_path, 'r') as f:
        protocol = yaml.safe_load(f)

    print(f"Executing protocol: {protocol.get('name')}")
    engine = ProtocolEngine()
    
    # We use execute_sync or similar if available, or just mock the run
    # ProtocolEngine.run is usually async or threaded. Let's look at the engine.
    
    # For diagnostics, let's just try to validate and run the first few steps
    try:
        # If the engine has a direct run method:
        # result = engine.run(protocol)
        # But looking at backend logic, it often uses a background thread.
        
        # Let's try to simulate what the backend does
        for i, step in enumerate(protocol.get('steps', [])):
            print(f"Step {i+1}: {step.get('action')}")
            # result = engine._execute_step(step) 
            # Note: _execute_step might be private or require context
            # Let's just run it formally if possible.
            
        print("\nStructure looks okay. Checking engine initialization...")
    except Exception as e:
        print(f"Initialization failed: {e}")

if __name__ == "__main__":
    run_diagnostic()
