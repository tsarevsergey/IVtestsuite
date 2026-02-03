"""
Data API Endpoints - Save/Load measurement data.
"""
import os
import csv
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Query
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
    """
    try:
        # Resolve output directory
        base_path = Path(".").resolve()
        output_dir = (base_path / request.folder).resolve()
        
        # Security check: ensure we stay within project bounds (optional, but good practice)
        # For now, allowing flexible paths but ensuring it exists
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


@router.get("/list")
async def list_files(folder: str = ".", extension: Optional[str] = None):
    """List files in a directory."""
    try:
        path = Path(folder).resolve()
        if not path.is_dir():
             # Try relative to current working dir
            path = (Path(".") / folder).resolve()
            
        if not path.is_dir():
            return {"success": False, "message": "Directory not found", "files": []}
            
        files = []
        for p in path.iterdir():
            if p.is_file():
                if extension and not p.name.endswith(extension):
                    continue
                stats = p.stat()
                files.append({
                    "name": p.name,
                    "size": stats.st_size,
                    "modified": stats.st_mtime
                })
        
        # Sort by name
        files.sort(key=lambda x: x["name"])
        return {"success": True, "files": files}
    except Exception as e:
        logger.error(f"List files error: {e}")
        return {"success": False, "message": str(e), "files": []}


@router.get("/load")
async def load_file(folder: str = ".", filename: str = ""):
    """Load file content (CSV/JSON/TXT)."""
    try:
        path = Path(folder).resolve() / filename
        if not path.exists():
             # Try relative
            path = (Path(".") / folder / filename).resolve()
            
        if not path.exists():
            return {"success": False, "message": "File not found"}

        ext = path.suffix.lower()
        
        if ext == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {"success": True, "data": data}
            
        elif ext == ".csv":
            data = []
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                data = [row for row in reader]
                # Try to convert numbers
                for row in data:
                    for k, v in row.items():
                        try:
                            row[k] = float(v)
                        except:
                            pass
            
            # Helper to extract separate channel arrays typical in this app
            result = {"raw": data}
            if data:
                keys = data[0].keys()
                for k in keys:
                    result[k] = [row[k] for row in data]
            
            return {"success": True, "data": result}
            
        elif ext == ".txt":
            # Assume tab delimited or plain text
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Try parsing as tab-delimited data (like cal files)
            try:
                lines = content.strip().split('\n')
                # Check if first line is header
                has_header = any(c.isalpha() for c in lines[0])
                first_data_idx = 1 if has_header else 0
                
                rows = []
                for line in lines[first_data_idx:]:
                    if line.strip():
                        rows.append([float(x) for x in line.strip().split('\t')])
                
                return {"success": True, "content": content, "parsed_rows": rows}
            except:
                pass

            return {"success": True, "content": content}

        else:
            return {"success": False, "message": "Unsupported file format"}

    except Exception as e:
        logger.error(f"Load file error: {e}")
        return {"success": False, "message": str(e)}


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
