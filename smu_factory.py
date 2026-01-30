"""
SMU Factory - Creates appropriate SMU controller based on type or auto-detection.

This module provides a factory function that instantiates the correct SMU driver
based on explicit type selection or auto-detection from the instrument's *IDN? response.
"""
from enum import Enum
from typing import Optional
import logging

try:
    import pyvisa
except ImportError:
    pyvisa = None

logger = logging.getLogger("smu_factory")


class SMUType(Enum):
    """Supported SMU types."""
    AUTO = "auto"
    KEYSIGHT_B2901 = "keysight_b2901"  # Single-channel (B2901A, B2911A)
    KEYSIGHT_B2902 = "keysight_b2902"  # Dual-channel (B2902A, B2912A)
    KEITHLEY_2400 = "keithley_2400"    # Keithley 2400 series
    KEITHLEY_2600 = "keithley_2600"    # Keithley 2600 series (future)


def _detect_smu_type(address: str) -> SMUType:
    """
    Auto-detect SMU type by querying *IDN?.
    
    Args:
        address: VISA resource address
        
    Returns:
        Detected SMUType
        
    Raises:
        RuntimeError: If detection fails or SMU type is unknown
    """
    if pyvisa is None:
        raise RuntimeError("PyVISA not installed, cannot auto-detect SMU type")
    
    rm = pyvisa.ResourceManager()
    try:
        resource = rm.open_resource(address, open_timeout=10000)
        resource.timeout = 10000
        
        try:
            resource.clear()
        except:
            pass
        
        idn = resource.query("*IDN?").strip()
        resource.close()
        
        logger.info(f"SMU identification: {idn}")
        
        # Parse manufacturer and model
        parts = idn.split(",")
        if len(parts) >= 2:
            manufacturer = parts[0].strip().upper()
            model = parts[1].strip().upper()
            
            # Keysight/Agilent detection
            if "KEYSIGHT" in manufacturer or "AGILENT" in manufacturer:
                if "B2901" in model or "B2911" in model:
                    logger.info("Detected Keysight single-channel SMU (B2901/B2911)")
                    return SMUType.KEYSIGHT_B2901
                elif "B2902" in model or "B2912" in model:
                    logger.info("Detected Keysight dual-channel SMU (B2902/B2912)")
                    return SMUType.KEYSIGHT_B2902
            
            # Keithley detection
            if "KEITHLEY" in manufacturer or "TEKTRONIX" in manufacturer:
                if "2400" in model or "2410" in model or "2420" in model or "2430" in model or "2440" in model:
                    logger.info("Detected Keithley 2400 series SMU")
                    return SMUType.KEITHLEY_2400
                elif "2600" in model or "2601" in model or "2602" in model:
                    logger.info("Detected Keithley 2600 series SMU")
                    return SMUType.KEITHLEY_2600
        
        raise RuntimeError(f"Unknown SMU type: {idn}")
        
    except Exception as e:
        raise RuntimeError(f"Failed to auto-detect SMU type: {e}")
    finally:
        rm.close()


def create_smu(
    smu_type: SMUType,
    address: str,
    channel: int = 1,
    mock: bool = False,
    name: str = "SMU"
):
    """
    Factory function to create the appropriate SMU controller.
    
    Args:
        smu_type: Type of SMU (use SMUType.AUTO for auto-detection)
        address: VISA resource address
        channel: Channel number (1 or 2, for dual-channel SMUs)
        mock: If True, use mock mode (no hardware)
        name: Name for logging
        
    Returns:
        Appropriate SMU controller instance
        
    Raises:
        ValueError: If SMU type is not supported
        RuntimeError: If auto-detection fails
    """
    # Auto-detect if requested
    if smu_type == SMUType.AUTO:
        if mock:
            # Can't auto-detect in mock mode, default to B2902 (most capable)
            logger.warning("Cannot auto-detect in mock mode, defaulting to Keysight B2902")
            smu_type = SMUType.KEYSIGHT_B2902
        else:
            smu_type = _detect_smu_type(address)
    
    # Import and instantiate the appropriate controller
    if smu_type == SMUType.KEYSIGHT_B2901:
        from smu_keysight_b2901 import KeysightB2901Controller
        return KeysightB2901Controller(address=address, channel=channel, mock=mock, name=name)
    
    elif smu_type == SMUType.KEYSIGHT_B2902:
        from smu_keysight_b2902 import KeysightB2902Controller
        return KeysightB2902Controller(address=address, channel=channel, mock=mock, name=name)
    
    elif smu_type == SMUType.KEITHLEY_2400:
        from smu_keithley_2400 import Keithley2400Controller
        return Keithley2400Controller(address=address, channel=channel, mock=mock, name=name)
    
    elif smu_type == SMUType.KEITHLEY_2600:
        raise NotImplementedError("Keithley 2600 series support not yet implemented")
    
    else:
        raise ValueError(f"Unsupported SMU type: {smu_type}")


def create_smu_from_string(
    smu_type_str: str,
    address: str,
    channel: int = 1,
    mock: bool = False,
    name: str = "SMU"
):
    """
    Factory function that accepts SMU type as a string.
    
    Convenience wrapper for API endpoints.
    
    Args:
        smu_type_str: String SMU type (e.g., "auto", "keysight_b2902")
        address: VISA resource address
        channel: Channel number
        mock: Mock mode flag
        name: Name for logging
        
    Returns:
        Appropriate SMU controller instance
    """
    try:
        smu_type = SMUType(smu_type_str.lower())
    except ValueError:
        valid_types = [t.value for t in SMUType]
        raise ValueError(f"Invalid SMU type '{smu_type_str}'. Valid types: {valid_types}")
    
    return create_smu(smu_type, address, channel, mock, name)


def list_available_smu_types() -> list:
    """Return list of available SMU type strings."""
    return [t.value for t in SMUType]


def get_smu_type_description(smu_type: SMUType) -> str:
    """Get human-readable description for an SMU type."""
    descriptions = {
        SMUType.AUTO: "Auto-detect from *IDN? response",
        SMUType.KEYSIGHT_B2901: "Keysight B2901A/B2911A (Single-channel)",
        SMUType.KEYSIGHT_B2902: "Keysight B2902A/B2912A (Dual-channel)",
        SMUType.KEITHLEY_2400: "Keithley 2400/2410/2420/2430/2440 series",
        SMUType.KEITHLEY_2600: "Keithley 2600 series (Not yet implemented)",
    }
    return descriptions.get(smu_type, "Unknown SMU type")
