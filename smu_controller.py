"""
SMU Controller - Backward Compatibility Wrapper.

This module provides backward compatibility by importing from the factory.
New code should use smu_factory.create_smu() directly.

Default behavior: Auto-detect SMU type.
"""
from smu_factory import create_smu, SMUType, create_smu_from_string, list_available_smu_types
from smu_base import BaseSMU, SMUState

# Re-export InstrumentState for backward compatibility with existing code
# that imports from smu_controller
try:
    from base_controller import InstrumentState
except ImportError:
    # If base_controller doesn't exist, use SMUState
    InstrumentState = SMUState


class SMUController:
    """
    Backward-compatible SMU Controller wrapper.
    
    This class wraps the new factory-based SMU controllers to maintain
    compatibility with existing code.
    
    New code should use:
        from smu_factory import create_smu, SMUType
        smu = create_smu(SMUType.AUTO, address, channel)
    """
    
    def __new__(cls, address: str, name: str = "SMU", mock: bool = False, channel: int = 1):
        """
        Create appropriate SMU controller based on auto-detection.
        
        This uses the factory to create the right controller type automatically.
        """
        return create_smu(
            smu_type=SMUType.AUTO,
            address=address,
            channel=channel,
            mock=mock,
            name=name
        )


# Export commonly used items for backward compatibility
__all__ = [
    'SMUController',
    'BaseSMU',
    'SMUState',
    'InstrumentState',
    'create_smu',
    'create_smu_from_string',
    'SMUType',
    'list_available_smu_types',
]
