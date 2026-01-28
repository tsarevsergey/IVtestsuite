"""
Data API Endpoints - Save measurement data to files.
"""
import os
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger

logger = get_logger("routers.data")
router = APIRouter(prefix="/data", tags=["data"])


class SaveDataRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="List of data rows to save")
    filename: str = Field(..., description="Base filename (without extension)")
    folder: str = Field(default="./data", description="Output folder")
    format: str = Field(default="csv", pattern="^(csv|json)$", description="Output format")
    append_timestamp: bool = Field(default=True, description="Append timestamp to filename")


class SaveDataResponse(BaseModel):
    success: bool
    filepath: str = ""
    rows_written: int = 0
    message: Optional[str] = None


@router.post("/save", response_model=SaveDataResponse)
async def save_data(request: SaveDataRequest):
    """
    Save measurement data to a file.
    
    Supports CSV and JSON formats.
    """
    try:
        # Ensure output directory exists
        output_dir = Path(request.folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build filename
        if request.append_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{request.filename}_{timestamp}"
        else:
            base_name = request.filename
        
        ext = ".csv" if request.format == "csv" else ".json"
        filepath = output_dir / f"{base_name}{ext}"
        
        # Write data
        if request.format == "csv":
            rows_written = _write_csv(filepath, request.data)
        else:
            rows_written = _write_json(filepath, request.data)
        
        logger.info(f"Saved {rows_written} rows to {filepath}")
        
        return SaveDataResponse(
            success=True,
            filepath=str(filepath),
            rows_written=rows_written
        )
        
    except Exception as e:
        logger.error(f"Failed to save data: {e}")
        return SaveDataResponse(
            success=False,
            message=str(e)
        )


def _write_csv(filepath: Path, data: List[Dict[str, Any]]) -> int:
    """Write data to CSV file."""
    if not data:
        # Create empty file
        filepath.touch()
        return 0
    
    # Get all unique keys across all rows
    keys = set()
    for row in data:
        keys.update(row.keys())
    keys = sorted(keys)
    
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(data)
    
    return len(data)


def _write_json(filepath: Path, data: List[Dict[str, Any]]) -> int:
    """Write data to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    return len(data)
