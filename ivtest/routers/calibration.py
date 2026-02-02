"""
Light Source Calibration API Router.

Provides endpoint for running LED current sweep with photodiode measurement
to generate irradiance calibration curves.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pathlib import Path
import numpy as np
import time

from ..smu_client import smu_client
from ..logging_config import get_logger

logger = get_logger("routers.calibration")
router = APIRouter(prefix="/calibration", tags=["calibration"])

# Default save directory for calibration files
CALIBRATION_SAVE_DIR = Path(__file__).parent.parent.parent


class CalibrationRequest(BaseModel):
    """Request parameters for light source calibration."""
    calibration_name: str = Field(default="calBLUE", description="Name for the calibration file (without extension)")
    led_channel: int = Field(default=1, ge=1, le=2, description="LED/light source channel")
    pd_channel: int = Field(default=2, ge=1, le=2, description="Photodiode channel")
    led_start: float = Field(default=0.001, description="LED start current (A)")
    led_stop: float = Field(default=0.100, description="LED stop current (A)")
    num_points: int = Field(default=20, ge=2, le=200, description="Number of sweep points")
    delay: float = Field(default=1.0, ge=0.1, description="Delay between points (s)")
    nplc: float = Field(default=4.0, gt=0, le=100, description="Integration time")
    pd_bias: float = Field(default=0.0, description="Photodiode bias voltage (V)")
    led_compliance: float = Field(default=9.0, gt=0, description="LED voltage compliance (V)")
    pd_compliance: float = Field(default=0.01, gt=0, description="PD current compliance (A)")
    responsivity: float = Field(default=0.2, gt=0, description="Si diode responsivity (A/W)")
    pd_area_cm2: float = Field(default=1.0, gt=0, description="PD active area (cm²)")


class CalibrationPoint(BaseModel):
    """Single calibration measurement point."""
    led_current: float
    pd_current: float
    pd_current_corrected: float
    irradiance: float


class CalibrationResponse(BaseModel):
    """Response from calibration run."""
    success: bool
    message: Optional[str] = None
    dark_current: Optional[float] = None
    points: Optional[List[CalibrationPoint]] = None
    saved_file: Optional[str] = None
    error: Optional[str] = None


@router.post("/run", response_model=CalibrationResponse)
async def run_calibration(request: CalibrationRequest):
    """
    Run LED current sweep and measure photodiode response.
    
    Uses smu_client directly for hardware control.
    """
    logger.info(f"Starting calibration: LED ch{request.led_channel} -> PD ch{request.pd_channel}")
    logger.info(f"Sweep: {request.led_start*1000:.1f}mA to {request.led_stop*1000:.1f}mA, {request.num_points} points")
    
    try:
        # Generate LED current points (including 0 for dark measurement)
        led_currents = np.linspace(request.led_start, request.led_stop, request.num_points).tolist()
        led_currents_with_dark = [0.0] + led_currents
        
        # 1. Check SMU connection status
        status = smu_client.status
        logger.info(f"SMU status: connected={status.connected}, mock={status.mock}")
        
        # 2. Connect if not connected (use real hardware)
        if not status.connected:
            logger.info("SMU not connected, connecting now...")
            result = smu_client.connect(mock=False, channel=request.led_channel)
            logger.info(f"LED channel connect result: {result}")
            
            result = smu_client.connect(mock=False, channel=request.pd_channel)
            logger.info(f"PD channel connect result: {result}")
        
        # 3. Configure LED channel (current source)
        logger.info(f"Configuring LED channel {request.led_channel} as CURR source...")
        smu_client.set_source_mode("CURR", channel=request.led_channel)
        smu_client.configure(
            compliance=request.led_compliance,
            compliance_type="VOLT",
            nplc=request.nplc,
            channel=request.led_channel
        )
        
        # 4. Configure PD channel (voltage source, measure current)
        logger.info(f"Configuring PD channel {request.pd_channel} as VOLT source...")
        smu_client.set_source_mode("VOLT", channel=request.pd_channel)
        smu_client.configure(
            compliance=request.pd_compliance,
            compliance_type="CURR",
            nplc=request.nplc,
            channel=request.pd_channel
        )
        
        # 5. Set initial values and enable outputs
        logger.info("Setting initial values and enabling outputs...")
        smu_client.set_value(request.pd_bias, channel=request.pd_channel)
        smu_client.output_control(True, channel=request.pd_channel)
        
        smu_client.set_value(0.0, channel=request.led_channel)
        smu_client.output_control(True, channel=request.led_channel)
        
        time.sleep(1.0)  # Initial stabilization
        
        # 6. Sweep through LED currents
        raw_results = []
        for i, led_current in enumerate(led_currents_with_dark):
            logger.info(f"Point {i+1}/{len(led_currents_with_dark)}: LED = {led_current*1000:.2f} mA")
            
            # Set LED current
            smu_client.set_value(led_current, channel=request.led_channel)
            
            # Wait for stabilization
            time.sleep(request.delay)
            
            # Measure PD current
            meas = smu_client.measure(channel=request.pd_channel)
            pd_current = meas.get("current", 0.0) if meas else 0.0
            
            raw_results.append({
                "led_current": led_current,
                "pd_current": pd_current
            })
            
            logger.info(f"  -> PD current: {pd_current*1e9:.2f} nA")
        
        # 7. Turn off outputs
        logger.info("Turning off outputs...")
        smu_client.output_control(False, channel=request.led_channel)
        smu_client.output_control(False, channel=request.pd_channel)
        
        # 8. Process results - use absolute values since photocurrent can be measured as negative
        logger.info("Processing results...")
        dark_current = abs(raw_results[0]["pd_current"])
        
        processed_points = []
        
        # Add dark point first (LED=0, corrected=0, irradiance=0)
        processed_points.append(CalibrationPoint(
            led_current=0.0,
            pd_current=dark_current,
            pd_current_corrected=0.0,
            irradiance=0.0
        ))
        
        # Process remaining points
        for r in raw_results[1:]:  # Skip dark measurement (already added)
            pd_current_abs = abs(r["pd_current"])
            corrected = pd_current_abs - dark_current
            irradiance = abs(corrected) / (request.responsivity * request.pd_area_cm2)
            processed_points.append(CalibrationPoint(
                led_current=r["led_current"],
                pd_current=pd_current_abs,
                pd_current_corrected=abs(corrected),
                irradiance=irradiance
            ))
        
        logger.info(f"Calibration complete! Dark current: {dark_current*1e9:.2f} nA")
        
        # 9. Save calibration file
        saved_file = None
        try:
            save_path = CALIBRATION_SAVE_DIR / f"{request.calibration_name}.txt"
            save_data = np.array([
                [p.led_current, p.pd_current_corrected, p.irradiance] 
                for p in processed_points
            ])
            np.savetxt(
                save_path, 
                save_data, 
                delimiter='\t', 
                header="LED_Current(A)\tPD_Current(A)\tIrradiance(W/cm2)",
                comments=''
            )
            saved_file = str(save_path)
            logger.info(f"Saved calibration to: {save_path}")
        except Exception as save_err:
            logger.error(f"Failed to save calibration file: {save_err}")
        
        return CalibrationResponse(
            success=True,
            message=f"Calibration complete. Measured {len(processed_points)} points. Dark current: {dark_current*1e9:.2f} nA",
            dark_current=dark_current,
            points=processed_points,
            saved_file=saved_file
        )
        
    except Exception as e:
        logger.error(f"Calibration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Try to turn off outputs
        try:
            smu_client.output_control(False, channel=request.led_channel)
            smu_client.output_control(False, channel=request.pd_channel)
        except:
            pass
        
        return CalibrationResponse(
            success=False,
            error=str(e)
        )
