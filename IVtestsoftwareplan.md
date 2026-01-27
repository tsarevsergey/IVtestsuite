Milestone 1 — Backend skeleton & control plane

Goal: Establish a stable execution framework before touching hardware.

Deliverables

FastAPI backend server

Endpoints:

GET /health

GET /status

Global run manager with explicit state machine:

IDLE → ARMED → RUNNING → ABORTED / ERROR → IDLE

Centralized logging (file + console)

Deterministic shutdown logic (used later by abort)

Acceptance

Backend starts, reports status, and transitions state without hardware attached

Abort endpoint forces transition to safe IDLE

Milestone 2 — SMU MCP adapter + mock framework

Goal: Abstract the MCP SMU interface and allow full operation without real hardware.

2.1 SMU MCP client

Implement smu_mcp_client.py

Must map backend calls 1:1 to MCP skill commands:

connect

configure

set_source_mode

set_value

output_control

measure

run_iv_sweep

Support:

mock=True

channel_id (even if currently fixed to one channel)

2.2 Relay mock framework

If API receives mock=True:

Relay operations must not touch serial ports

Simulated responses must be returned with realistic timing

Mock relay behavior:

Pixel selection acknowledged

LED channel selection acknowledged

All-off always succeeds

Acceptance

Backend can execute full protocol flow in mock mode

No hardware required to test API, UI, or automation logic

Milestone 3 — Real SMU validation + trace capture

Goal: Lock down real SMU behavior before higher-level automation.

Tasks

Test against real SMU hardware

Record:

Output formats

Timing behavior

Order of MCP calls

Compliance behavior

Compare against:

Reference Python script behavior (scan_and_plot.py)

Document:

Required delays

Known MCP quirks or failure modes

Acceptance

IV sweep via backend reproduces reference script behavior within tolerance

All measurements saved in deterministic format

Milestone 4 — Physical device mock models (critical)

Goal: Enable realistic UI + API testing without hardware.

4.1 LED mock object

Default: Channel X = 1

Model:

Open voltage: ~6 V

Max current: 100 mA

Exponential diode IV curve with series resistance

Behavior:

Responds to SMU voltage/current commands

Saturates safely at max current

Mimics thermal roll-off qualitatively (optional)

4.2 Silicon photodetector mock object

Default: Channel X = 2

Model:

Uses realistic Si responsivity (e.g. 0.3–0.6 A/W depending on wavelength)

Output current computed as:

I_photo = Responsivity × Optical Power


Includes:

Dark current

Noise floor (Gaussian / shot noise approximation)

Behavior:

Responds to simulated LED flux

Correct polarity and scaling

Bias-dependent leakage (optional)

Purpose of mocks

Validate:

API correctness

UI plotting

Automation logic

Enable:

Development on laptops

CI testing

Debugging without lab access

Acceptance

Mock LED + mock PD produce physically plausible IV curves

UI behaves identically in mock and real modes

Milestone 5 — Arduino relay drivers (real + mock)

Goal: Finalize switching control with safe fallback.

Deliverables

arduino_relays.py

Support:

Pixel selection

LED channel selection

All-off

Status query (best-effort)

Seamless swap between:

real serial device

mock relay backend

Acceptance

Switching works reliably

Mock and real paths share the same API

Milestone 6 — IV sweep protocol MVP

Goal: Reproduce LabVIEW core functionality.

Features

Dark / Light modes

Per-pixel scanning

SMU compliance enforcement

Abort-safe shutdown

Data saving:

legacy .dat

structured CSV

metadata JSON

Acceptance

Dark + Light IV for multiple pixels completes reliably

Abort at any time leaves hardware safe

Saved data matches expected structure

Milestone 7 — Streamlit MVP

Goal: Thin UI layer for operators.

Features

Connection control

Parameter input

Start / Stop / Abort

Live plotting via SSE or WebSocket

Status display

Rules

No direct hardware access

API-only communication

Acceptance

UI usable for full IV workflow

No blocking or freezing during runs

Milestone 8 — Calibration module

Goal: Formalize optical power estimation.

Features

Calibration run using reference Si diode

Generate {channel}.cal files

Archive old calibrations

Use calibration to compute:

mW/cm²

responsivity

detectivity (where applicable)

Acceptance

Calibration files reproducible

Flux values correctly propagated into runs

Milestone 9 — Expanded protocols

Goal: Match and exceed LabVIEW capabilities.

Implement

Scan ordering strategies

List sweeps

Intensity sweeps

Linearity analysis

IV vs intensity

Drift analysis

Acceptance

Automation works headless

Protocol definitions reusable via API

Milestone 10 — Stabilization & documentation

Goal: Make it hand-off ready.

Deliverables

README (setup, mock vs real mode)

Example protocol JSONs

API schema (OpenAPI auto-generated)

Known limitations documented

Final Note for Developer

Mock support is not optional.
The system must be fully usable, testable, and debuggable without physical hardware.
