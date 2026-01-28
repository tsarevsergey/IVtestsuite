"""
Protocol Loader - Load and validate YAML protocol files.


Protocols are stored in the ./protocols/ directory.
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import yaml

from .logging_config import get_logger

logger = get_logger("protocol_loader")

# Default protocols directory (relative to project root)
PROTOCOLS_DIR = Path(__file__).parent.parent / "protocols"


@dataclass
class ProtocolDefinition:
    """A loaded protocol definition."""
    name: str
    description: str
    version: str
    steps: List[Dict[str, Any]]
    filepath: str


class ProtocolLoader:
    """
    Loads and validates protocol files from the protocols directory.
    """
    
    def __init__(self, protocols_dir: Path = PROTOCOLS_DIR):
        self.protocols_dir = Path(protocols_dir)
        self._cache: Dict[str, ProtocolDefinition] = {}
    
    def list_protocols(self) -> List[Dict[str, str]]:
        """
        List all available protocol files.
        
        Returns:
            List of dicts with 'name', 'description', 'filepath'
        """
        if not self.protocols_dir.exists():
            logger.warning(f"Protocols directory does not exist: {self.protocols_dir}")
            return []
        
        protocols = []
        # Recursive glob to find protocols in subfolders like 'users/'
        for filepath in self.protocols_dir.glob("**/*.yaml"):
            try:
                # Use relative path without extension as the identifier name
                # e.g. "users/myproto" or "iv_sweep"
                rel_name = filepath.relative_to(self.protocols_dir).with_suffix("").as_posix()
                
                proto = self.load(rel_name)
                protocols.append({
                    "name": proto.name, # The display name inside valid yaml
                    "id": rel_name,     # The unique ID for loading
                    "description": proto.description,
                    "version": proto.version,
                    "filename": filepath.name
                })
            except Exception as e:
                logger.warning(f"Failed to load {filepath}: {e}")
                protocols.append({
                    "name": filepath.stem,
                    "id": filepath.relative_to(self.protocols_dir).with_suffix("").as_posix(),
                    "description": f"Error: {e}",
                    "version": "?",
                    "filename": filepath.name
                })
        
        return protocols
    
    def load(self, name: str) -> ProtocolDefinition:
        """
        Load a protocol by name.
        
        Args:
            name: Protocol name (filename without .yaml)
        
        Returns:
            ProtocolDefinition
        
        Raises:
            FileNotFoundError: If protocol file doesn't exist
            ValueError: If protocol is invalid
        """
        # Check cache
        if name in self._cache:
            return self._cache[name]
        
        filepath = self.protocols_dir / f"{name}.yaml"
        if not filepath.exists():
            raise FileNotFoundError(f"Protocol not found: {name}")
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # Validate required fields
        if not isinstance(data, dict):
            raise ValueError(f"Protocol must be a YAML mapping, got: {type(data)}")
        
        if "steps" not in data:
            raise ValueError("Protocol must have 'steps' field")
        
        if not isinstance(data["steps"], list):
            raise ValueError("Protocol 'steps' must be a list")
        
        # Validate each step
        for i, step in enumerate(data["steps"]):
            if not isinstance(step, dict):
                raise ValueError(f"Step {i} must be a mapping")
            if "action" not in step:
                raise ValueError(f"Step {i} must have 'action' field")
        
        proto = ProtocolDefinition(
            name=data.get("name", name),
            description=data.get("description", ""),
            version=str(data.get("version", "1.0")),
            steps=data["steps"],
            filepath=str(filepath)
        )
        
        self._cache[name] = proto
        logger.info(f"Loaded protocol: {proto.name} ({len(proto.steps)} steps)")
        
        return proto
    
    def reload(self, name: str) -> ProtocolDefinition:
        """Force reload a protocol (bypass cache)."""
        if name in self._cache:
            del self._cache[name]
        return self.load(name)
    
    def clear_cache(self):
        """Clear the protocol cache."""
        self._cache.clear()


# Global singleton instance
protocol_loader = ProtocolLoader()
