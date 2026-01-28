# Protocol Engine Walkthrough

## Overview

The **Protocol Designer** allows users to compose measurement protocols as YAML files that orchestrate low-level SMU and Relay API calls. The system consists of:

| Component | File | Purpose |
|-----------|------|---------|
| **Protocol Engine** | `ivtest/protocol_engine.py` | Sequential step executor |
| **Protocol Loader** | `ivtest/protocol_loader.py` | YAML file loader with caching |
| **Protocol Router** | `ivtest/routers/protocol.py` | REST API endpoints |

---

## API Endpoints

### Protocol Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/protocol/list` | List available protocols from `./protocols/` |
| `POST` | `/protocol/run` | Run a named protocol `{"name": "protocol_name"}` |
| `POST` | `/protocol/run-inline` | Run inline steps `{"steps": [...], "name": "inline"}` |
| `POST` | `/protocol/reload` | Clear protocol cache (after editing YAML) |
| `GET` | `/protocol/status` | Get execution status |
| `POST` | `/protocol/abort` | Abort running protocol |

---

## Available Actions

### SMU Actions

| Action | Parameters | Description |
|--------|------------|-------------|
| `smu/connect` | `mock`, `channel`, `address` | Connect to SMU |
| `smu/disconnect` | — | Disconnect from SMU |
| `smu/configure` | `compliance`, `compliance_type`, `nplc` | Configure compliance |
| `smu/source-mode` | `mode` (VOLT/CURR) | Set source mode |
| `smu/set` | `value` | Set source value |
| `smu/output` | `enabled` | Enable/disable output |
| `smu/measure` | — | Single measurement |
| `smu/sweep` | `start`, `stop`, `points`, `delay`, `sweep_type` | IV sweep |
| `smu/list-sweep` | `points`, `source_mode`, `compliance`, `nplc`, `delay` | Custom point list |

### Relay Actions

| Action | Parameters | Description |
|--------|------------|-------------|
| `relays/connect` | `mock`, `port` | Connect to relay controller |
| `relays/disconnect` | — | Disconnect |
| `relays/pixel` | `pixel_id` | Select pixel (exclusive) |
| `relays/led` | `channel_id` | Select LED channel |
| `relays/all-off` | — | Turn all relays off |

### Status Actions

| Action | Parameters | Description |
|--------|------------|-------------|
| `status/arm` | — | Arm run manager |
| `status/start` | — | Start run |
| `status/complete` | — | Complete run |
| `status/abort` | — | Abort run |

### Utility Actions

| Action | Parameters | Description |
|--------|------------|-------------|
| `wait` | `seconds` | Wait for specified duration |
| `data/save` | `data`, `filename`, `folder` | Save captured data to CSV |

---

## YAML Protocol Format

```yaml
name: Protocol Name
description: Brief description
version: 1.0

steps:
  - action: smu/connect
    params:
      mock: false
      channel: 1

  - action: smu/sweep
    params:
      start: 0
      stop: 8
      points: 41
    capture_as: iv_data  # Store result in variable

  - action: data/save
    params:
      data: $iv_data     # Reference captured variable
      filename: output
      folder: ./data
```

---

## Variable Capture

Use `capture_as` to store action results, then reference with `$variable_name`:

```yaml
- action: smu/sweep
  params:
    start: 0
    stop: 5
  capture_as: sweep_data

- action: data/save
  params:
    data: $sweep_data
    filename: results
```

---

## Example: Running a Protocol

```powershell
# 1. Clear cache after editing YAML
curl.exe -X POST http://localhost:5000/protocol/reload

# 2. Reset system state
curl.exe -X POST http://localhost:5000/reset

# 3. Run protocol
curl.exe -X POST http://localhost:5000/protocol/run -H "Content-Type: application/json" -d '{"name": "iv_sweep_light"}'
```

---

## Protocol Response

```json
{
  "success": true,
  "name": "Protocol Name",
  "steps_completed": 8,
  "total_steps": 8,
  "aborted": false,
  "error": null,
  "captured_data": {
    "iv_data": { "results": [...], "points": 41 }
  }
}
```

---

## Files Structure

```
protocols/
├── iv_sweep_light.yaml     # Example: Real SMU sweep with data save
├── real_smu_sweep.yaml     # Alternative protocol

ivtest/
├── protocol_engine.py      # Step executor with action dispatch
├── protocol_loader.py      # YAML loader with caching
├── routers/
│   ├── protocol.py         # REST API endpoints
│   └── data.py             # Data save endpoint
```
