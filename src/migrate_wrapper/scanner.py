"""Migration file scanner"""
from pathlib import Path
from typing import List, Dict, Any
import re

from .models import Migration


class MigrationScanner:
    """Scans directory for migration files"""
    def __init__(self, migrations_path: Path):
        self.migrations_path = migrations_path
        
    def scan(self) -> List[Migration]:
        """Scan for all migration files"""
        migrations = {}
        
        # Pattern to match migration files: <version>_<name>.<direction>.sql
        pattern = re.compile(r'^(\d+)_(.+)\.(up|down)\.sql$')
        
        for file in self.migrations_path.glob("*.sql"):
            match = pattern.match(file.name)
            if not match:
                continue
                
            version = int(match.group(1))
            name = match.group(2)
            direction = match.group(3)
            
            if version not in migrations:
                migrations[version] = {
                    "version": version,
                    "name": name,
                    "up_file": None,
                    "down_file": None
                }
            
            if direction == "up":
                migrations[version]["up_file"] = file
            elif direction == "down":
                migrations[version]["down_file"] = file
        
        return sorted([
            Migration(**data) for data in migrations.values()
            if data["up_file"] is not None
        ], key=lambda m: m.version)
    
    def find_gaps(self, migrations: List[Migration]) -> List[int]:
        """Find gaps in migration sequence"""
        if not migrations:
            return []
            
        versions = sorted([m.version for m in migrations])
        gaps = []
        
        for i in range(versions[0], versions[-1]):
            if i not in versions:
                gaps.append(i)
                
        return gaps