"""
Light Calibration Module

Converts between LED current and irradiance (W/cm²) using calibration data
from a reference silicon diode measurement.

Usage:
    from ivtest.calibration import CalibrationManager
    
    cal = CalibrationManager()
    cal.load("calBLUE.txt")
    
    # Convert LED current to irradiance
    irradiance = cal.current_to_irradiance(0.01)  # 10mA LED current
    
    # Convert irradiance to LED current
    current = cal.irradiance_to_current(0.001)  # 1 mW/cm²
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple, List
from .logging_config import get_logger

logger = get_logger("calibration")


class CalibrationManager:
    """
    Manages LED current ↔ irradiance calibration.
    
    Calibration file format (tab or comma separated):
        New format (3 columns):
            Column 1: LED current (A)
            Column 2: PD photocurrent (A) - not used, kept for reference
            Column 3: Irradiance (W/cm²)
        
        Legacy format (2 columns):
            Column 1: LED current (A)
            Column 2: Irradiance (W/cm²)
    """
    
    def __init__(self):
        self._currents: np.ndarray = np.array([])
        self._irradiances: np.ndarray = np.array([])
        self._loaded_file: Optional[str] = None
    
    @property
    def is_loaded(self) -> bool:
        """Check if calibration data is loaded."""
        return len(self._currents) > 0
    
    @property
    def current_range(self) -> Tuple[float, float]:
        """Return (min, max) LED current range."""
        if not self.is_loaded:
            return (0.0, 0.0)
        return (float(self._currents.min()), float(self._currents.max()))
    
    @property
    def irradiance_range(self) -> Tuple[float, float]:
        """Return (min, max) irradiance range."""
        if not self.is_loaded:
            return (0.0, 0.0)
        return (float(self._irradiances.min()), float(self._irradiances.max()))
    
    def load(self, filepath: str, diode_area_cm2: float = 0.0, 
             led_wavelength_nm: float = 0.0, 
             si_responsivity_file: Optional[str] = None) -> bool:
        """
        Load calibration data from file.
        
        Args:
            filepath: Path to calibration file (e.g., calBLUE.txt)
            diode_area_cm2: Si diode active area in cm². If provided with responsivity,
                           will convert diode current to irradiance.
            led_wavelength_nm: LED wavelength in nm. Used to lookup Si responsivity.
            si_responsivity_file: Path to SiDiodeResponsivity.csv
            
        Returns:
            True if loaded successfully
            
        File format:
            New format (3 columns): LED_Current(A), PD_Current(A), Irradiance(W/cm²)
            Legacy format (2 columns): LED_Current(A), Irradiance(W/cm²)
        """
        try:
            path = Path(filepath)
            if not path.exists():
                logger.error(f"Calibration file not found: {filepath}")
                return False
            
            # Try to detect delimiter and header
            with open(path, 'r') as f:
                first_line = f.readline()
            
            delimiter = '\t' if '\t' in first_line else ','
            
            # Check if first line is a header (contains non-numeric text)
            has_header = False
            try:
                # Try to parse first value as float - if it fails, it's a header
                float(first_line.split(delimiter)[0].strip())
            except ValueError:
                has_header = True
            
            # Load data, skip header if present
            data = np.loadtxt(path, delimiter=delimiter, skiprows=1 if has_header else 0)
            
            if data.ndim == 1:
                # Single row - reshape
                data = data.reshape(1, -1)
            
            if data.shape[1] < 2:
                logger.error(f"Calibration file must have at least 2 columns")
                return False
            
            self._currents = data[:, 0]
            
            # New format: 3 columns (LED current, PD current, Irradiance)
            # Legacy format: 2 columns (LED current, Irradiance)
            if data.shape[1] >= 3:
                # New format - irradiance is in column 3
                raw_irradiance = data[:, 2]
                logger.info(f"Detected new 3-column format, using column 3 for irradiance")
            else:
                # Legacy format - irradiance is in column 2
                raw_irradiance = data[:, 1]
                logger.info(f"Detected legacy 2-column format, using column 2 for irradiance")
            
            # Check if we need to convert raw values using diode parameters
            if diode_area_cm2 > 0 and led_wavelength_nm > 0 and si_responsivity_file:
                # Raw value is assumed to be diode current, convert to irradiance
                responsivity = self._lookup_responsivity(si_responsivity_file, led_wavelength_nm)
                if responsivity > 0:
                    # Irradiance = Diode_Current / (Responsivity * Area)
                    self._irradiances = raw_irradiance / (responsivity * diode_area_cm2)
                    logger.info(f"Converted diode current to irradiance using R={responsivity} A/W, Area={diode_area_cm2} cm²")
                else:
                    # Use raw values as irradiance
                    self._irradiances = raw_irradiance
            else:
                # Assume raw values are already irradiance (new format: they are)
                self._irradiances = raw_irradiance
            
            self._loaded_file = str(path)
            logger.info(f"Loaded calibration: {len(self._currents)} points from {filepath}")
            logger.info(f"  Current range: {self.current_range[0]:.4f} - {self.current_range[1]:.4f} A")
            logger.info(f"  Irradiance range: {self.irradiance_range[0]:.6f} - {self.irradiance_range[1]:.6f} W/cm²")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False
    
    def _lookup_responsivity(self, si_file: str, wavelength_nm: float) -> float:
        """
        Look up Si diode responsivity at given wavelength.
        
        Args:
            si_file: Path to SiDiodeResponsivity.csv (wavelength_nm, responsivity_A_W)
            wavelength_nm: Target wavelength
            
        Returns:
            Responsivity in A/W (interpolated), or 0 if not found
        """
        try:
            path = Path(si_file)
            if not path.exists():
                logger.warning(f"Si responsivity file not found: {si_file}")
                return 0.0
            
            data = np.loadtxt(path, delimiter=',')
            wavelengths = data[:, 0]
            responsivities = data[:, 1]
            
            # Interpolate
            responsivity = np.interp(wavelength_nm, wavelengths, responsivities)
            logger.info(f"Si diode responsivity at {wavelength_nm}nm: {responsivity:.3f} A/W")
            return float(responsivity)
            
        except Exception as e:
            logger.error(f"Failed to lookup Si responsivity: {e}")
            return 0.0
    
    def current_to_irradiance(self, led_current: float) -> float:
        """
        Convert LED current to irradiance using interpolation.
        
        Args:
            led_current: LED current in Amps
            
        Returns:
            Irradiance in W/cm², or 0 if calibration not loaded
        """
        if not self.is_loaded:
            logger.warning("Calibration not loaded, returning 0")
            return 0.0
        
        irradiance = np.interp(led_current, self._currents, self._irradiances)
        return float(irradiance)
    
    def irradiance_to_current(self, irradiance: float) -> float:
        """
        Convert irradiance to LED current using interpolation.
        
        Args:
            irradiance: Target irradiance in W/cm²
            
        Returns:
            LED current in Amps, or 0 if calibration not loaded
        """
        if not self.is_loaded:
            logger.warning("Calibration not loaded, returning 0")
            return 0.0
        
        # Interpolate in reverse direction
        current = np.interp(irradiance, self._irradiances, self._currents)
        return float(current)
    
    def get_calibration_points(self) -> List[Tuple[float, float]]:
        """
        Get all calibration points as (current, irradiance) tuples.
        """
        if not self.is_loaded:
            return []
        return list(zip(self._currents.tolist(), self._irradiances.tolist()))


# Global singleton for convenient access
_default_manager: Optional[CalibrationManager] = None


def get_calibration_manager() -> CalibrationManager:
    """Get or create the default calibration manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = CalibrationManager()
    return _default_manager
