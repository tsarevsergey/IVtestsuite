"""
Physical Device Mock Models.

Provides realistic simulated IV responses for:
- LED (exponential diode curve)
- Silicon photodetector (responsivity-based)

Used for mock mode testing without hardware.
"""
import numpy as np
from dataclasses import dataclass
from typing import Optional
import random

from .logging_config import get_logger

logger = get_logger("mock_devices")


@dataclass
class LEDModel:
    """
    Mock LED based on real captured IV data.
    
    Uses interpolation from actual B2901A measurements of a blue/white LED.
    """
    max_current: float = 0.1  # 100mA compliance
    
    # Internal state
    optical_power: float = 0.0  # mW output
    wavelength: float = 450  # nm (blue LED default)
    
    # Real captured IV data (voltage, current in Amps)
    # From actual LED sweep: 0-8V, 41 points
    _iv_data: list = None
    
    def __post_init__(self):
        # Real LED IV curve data captured from hardware
        # (set_voltage, measured_current in Amps)
        self._iv_data = [
            (0.0, 0.0),
            (1.0, 1e-10),
            (2.0, 1e-10),
            (3.0, 1e-10),
            (4.0, 1e-10),
            (5.0, 1e-10),
            (6.0, 5e-9),
            (6.5, 1e-7),
            (7.0, 3.3e-5),
            (7.2, 4.2e-5),
            (7.4, 3.8e-4),
            (7.6, 2.85e-3),
            (7.8, 1.15e-2),
            (8.0, 2.67e-2),
        ]
    
    def calculate_current(self, voltage: float, compliance: float = 0.1) -> float:
        """
        Calculate LED current using interpolation from real data.
        """
        import random
        
        if voltage <= 0:
            return random.gauss(0, 1e-10)
        
        # Find interpolation points
        v_prev, i_prev = self._iv_data[0]
        for v, i in self._iv_data:
            if voltage <= v:
                # Linear interpolation
                if v == v_prev:
                    current = i
                else:
                    ratio = (voltage - v_prev) / (v - v_prev)
                    current = i_prev + ratio * (i - i_prev)
                break
            v_prev, i_prev = v, i
        else:
            # Beyond data range - extrapolate with resistance
            last_v, last_i = self._iv_data[-1]
            extra_v = voltage - last_v
            current = last_i + extra_v * 0.01  # ~100 ohm series resistance
        
        # Apply compliance
        current = min(current, compliance)
        
        # Add measurement noise
        noise = random.gauss(0, max(abs(current) * 0.01, 1e-10))
        current += noise
        
        # Update optical power (approximate LED efficiency)
        if current > 1e-6:
            efficiency = 0.3  # 30% wall-plug efficiency
            self.optical_power = voltage * current * efficiency * 1000  # mW
        else:
            self.optical_power = 0.0
        
        return current
    
    def measure(self, set_voltage: float, compliance: float = 0.1) -> dict:
        """
        Simulate a measurement at given voltage.
        """
        current = self.calculate_current(set_voltage, compliance)
        
        # Measured voltage (small offset from set)
        import random
        measured_voltage = set_voltage + random.gauss(0, 1e-6)
        
        return {
            "voltage": measured_voltage,
            "current": current,
            "set_voltage": set_voltage,
            "optical_power_mw": self.optical_power
        }


@dataclass
class PhotodetectorModel:
    """
    Silicon photodetector mock model.
    
    Generates photocurrent based on incident optical power.
    
    Attributes:
        responsivity: A/W (wavelength dependent, ~0.3-0.6 for Si)
        dark_current: Background current with no light (A)
        area_cm2: Active area in cm²
    """
    responsivity: float = 0.4  # A/W at ~600nm
    dark_current: float = 1e-9  # 1 nA dark current
    area_cm2: float = 0.01  # 0.1 cm x 0.1 cm
    shunt_resistance: float = 1e9  # 1 GOhm
    
    # Coupled LED for simulation
    _coupled_led: Optional[LEDModel] = None
    _coupling_efficiency: float = 0.1  # 10% of LED light reaches detector
    
    def couple_to_led(self, led: LEDModel, efficiency: float = 0.1):
        """Couple this detector to an LED for light simulation."""
        self._coupled_led = led
        self._coupling_efficiency = efficiency
        logger.info(f"Photodetector coupled to LED with {efficiency*100}% efficiency")
    
    def calculate_current(self, bias_voltage: float = 0.0) -> float:
        """
        Calculate photocurrent.
        
        Args:
            bias_voltage: Reverse bias voltage (usually 0 or small negative)
        
        Returns:
            Photocurrent in Amps (negative for reverse bias convention)
        """
        # Optical power from coupled LED
        if self._coupled_led:
            optical_power_mw = self._coupled_led.optical_power * self._coupling_efficiency
        else:
            optical_power_mw = 0.0
        
        optical_power_w = optical_power_mw / 1000.0
        
        # Photocurrent = responsivity * optical power
        photocurrent = self.responsivity * optical_power_w
        
        # Add dark current
        total_current = photocurrent + self.dark_current
        
        # Bias-dependent leakage (small effect)
        leakage = abs(bias_voltage) / self.shunt_resistance
        total_current += leakage
        
        # Add shot noise (Poisson-like)
        shot_noise = random.gauss(0, np.sqrt(2 * 1.6e-19 * total_current * 1e6))
        
        return total_current + shot_noise
    
    def measure(self, bias_voltage: float = 0.0) -> dict:
        """
        Simulate a measurement.
        
        Returns:
            Dict with voltage, current, and derived irradiance
        """
        current = self.calculate_current(bias_voltage)
        
        # Calculate irradiance if we know the optical power
        optical_power_mw = 0.0
        if self._coupled_led:
            optical_power_mw = self._coupled_led.optical_power * self._coupling_efficiency
        
        irradiance = optical_power_mw / self.area_cm2 if self.area_cm2 > 0 else 0.0
        
        return {
            "voltage": bias_voltage,
            "current": current,
            "optical_power_mw": optical_power_mw,
            "irradiance_mw_cm2": irradiance
        }


# Default mock device instances
mock_led = LEDModel()
mock_photodetector = PhotodetectorModel()

# Pre-couple them for integrated testing
mock_photodetector.couple_to_led(mock_led)
