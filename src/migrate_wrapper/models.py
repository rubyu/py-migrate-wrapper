"""Data models for migrate-wrapper"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List


@dataclass
class Migration:
    """Represents a single migration"""
    version: int
    name: str
    up_file: Path
    down_file: Optional[Path] = None
    timestamp: Optional[int] = None
    
    @property
    def filename_prefix(self) -> str:
        """Get the filename prefix (version_name)"""
        if self.timestamp:
            return f"{self.timestamp}_{self.name}"
        return f"{self.version:06d}_{self.name}"
    
    def has_up_file(self) -> bool:
        """Check if up migration file exists"""
        return self.up_file.exists()
    
    def has_down_file(self) -> bool:
        """Check if down migration file exists"""
        return self.down_file is not None and self.down_file.exists()


@dataclass
class MigrationResult:
    """Result of a migration operation"""
    success: bool
    version: Optional[int]
    message: str
    error: Optional[Exception] = None
    dirty: bool = False


@dataclass
class DatabaseInfo:
    """Current database migration information"""
    version: Optional[int]
    dirty: bool
    
    @property
    def is_clean(self) -> bool:
        return not self.dirty


@dataclass
class MissingDownFile:
    """Information about a migration missing its down file"""
    version: int
    name: str


@dataclass
class ValidationResult:
    """Result of migration validation"""
    valid: bool
    total_migrations: int
    gaps: List[int]
    missing_down_files: List[MissingDownFile]
    
    @property
    def has_gaps(self) -> bool:
        """Check if there are gaps in migration sequence"""
        return len(self.gaps) > 0
    
    @property
    def has_missing_down_files(self) -> bool:
        """Check if there are missing down files"""
        return len(self.missing_down_files) > 0