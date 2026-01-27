import sys
import os
import json
import threading
import time

# Add project root and MCP directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from smu_mcp_server import connect, run_iv_sweep, measure
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test():
    print("--- Test 3: Concurrency Blocking ---")
    
    # 1. Setup
    connect.fn(address="MOCK::ADDRESS", mock=True)
    
    # 2. Start a long running operation in a thread
    # A sweep with 100 points will take some time
    results = {"task1": None, "task2": None}
    
    def long_task():
        print("Task 1: Starting sweep...")
        results["task1"] = json.loads(run_iv_sweep.fn(start=0, stop=2, steps=20))
        print("Task 1: Finished.")

    def quick_task():
        time.sleep(0.1) # Ensure task 1 starts first
        print("Task 2: Attempting measure during sweep...")
        results["task2"] = json.loads(measure.fn())
        print("Task 2: Finished.")

    t1 = threading.Thread(target=long_task)
    t2 = threading.Thread(target=quick_task)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    # 3. Verify
    print("\nTask 1 Status:", results["task1"]["status"])
    print("Task 2 Status:", results["task2"]["status"])
    
    assert results["task1"]["status"] == "success"
    assert results["task2"]["status"] == "error"
    assert "busy" in results["task2"]["message"]
    
    print("\nTest 3 PASSED")

if __name__ == "__main__":
    test()
