# IV Test Software — Implementation Walkthrough

> Last Updated: 2026-01-27

## Project Structure

```
SMU/
├── ivtest/                        # Main backend package
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry point
│   ├── run_manager.py             # Global state machine
│   ├── logging_config.py          # File + console logging
│   ├── smu_client.py              # SMU controller wrapper
│   ├── mock_devices.py            # LED + Photodetector models
│   ├── arduino_relays.py          # Relay controller (mock + real)
│   └── routers/
│       ├── __init__.py
│       ├── status.py              # Health, status, state transitions
│       ├── smu.py                 # SMU control endpoints
│       └── relays.py              # Relay control endpoints
├── smu_controller.py              # Low-level SMU hardware driver
├── logs/                          # Application logs
└── venv310/                       # Python 3.10 virtual environment
```

---

## Milestone 1 — Backend Skeleton

### Files
| File | Purpose |
|------|---------|
| `ivtest/main.py` | FastAPI app with lifespan, CORS |
| `ivtest/run_manager.py` | State machine: IDLE→ARMED→RUNNING→ABORTED/ERROR→IDLE |
| `ivtest/logging_config.py` | Centralized logging to file + console |
| `ivtest/routers/status.py` | `/health`, `/status`, `/arm`, `/start`, `/abort` |

### Run Server
```powershell
.\venv310\Scripts\python.exe -m uvicorn ivtest.main:app --host localhost --port 5000
```

---

## Milestone 2 — SMU MCP Adapter

### Files
| File | Purpose |
|------|---------|
| `ivtest/smu_client.py` | Wraps `SMUController`, thread-safe, abort-aware |
| `ivtest/routers/smu.py` | SMU API endpoints |

### Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/smu/connect` | POST | Connect (mock or real) |
| `/smu/disconnect` | POST | Safe disconnect |
| `/smu/status` | GET | Connection status |
| `/smu/configure` | POST | Set compliance/NPLC |
| `/smu/source-mode` | POST | VOLT or CURR mode |
| `/smu/set` | POST | Set voltage/current |
| `/smu/output` | POST | Enable/disable output |
| `/smu/measure` | GET | Single measurement |
| `/smu/sweep` | POST | IV sweep |

---

## Milestone 3 — Real SMU Validation

Tested with Keysight B2901A (single channel) + LED.

**Results:**
- LED turn-on: ~7V
- At 8V: 26.7 mA
- Backend behavior matches reference `scan_and_plot.py`

---

## Milestone 4 — Mock Device Models

### Files
| File | Purpose |
|------|---------|
| `ivtest/mock_devices.py` | LED and Photodetector mock models |

### LEDModel
- Interpolation from real captured IV data
- Turn-on ~7V, 26.7mA at 8V
- Outputs optical power (mW)

### PhotodetectorModel
- Coupled to LED via `couple_to_led(led, efficiency)`
- Responsivity: 0.4 A/W (Si at ~600nm)
- Dark current: 1 nA
- Calculates irradiance (mW/cm²)

---

## Milestone 5 — Arduino Relay Drivers

### Files
| File | Purpose |
|------|---------|
| `ivtest/arduino_relays.py` | Relay controller with mock support |
| `ivtest/routers/relays.py` | Relay API endpoints |

### Relay Configuration
- **Pixels**: 8 channels (exclusive selection)
- **LED Channels**: 4 channels (exclusive selection)

### Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/relays/connect` | POST | Connect (mock or real serial) |
| `/relays/disconnect` | POST | Disconnect |
| `/relays/status` | GET | Current relay state |
| `/relays/pixel` | POST | Select pixel (0-7) |
| `/relays/led` | POST | Select LED channel (0-3) |
| `/relays/all-off` | POST | Safe state - all relays off |

---

## API Summary

Base URL: `http://localhost:5000`

| Category | Endpoints |
|----------|-----------|
| System | `/health`, `/status`, `/arm`, `/start`, `/abort`, `/reset`, `/complete` |
| SMU | `/smu/*` (connect, disconnect, configure, sweep, measure, etc.) |
| Relays | `/relays/*` (connect, pixel, led, all-off, status) |

OpenAPI docs: `http://localhost:5000/docs`

---

## Dependencies

```
fastapi
uvicorn
pydantic
numpy
pyvisa
pyserial (for real relay hardware)
```

Install:
```powershell
.\venv310\Scripts\pip.exe install fastapi uvicorn pydantic numpy
```
