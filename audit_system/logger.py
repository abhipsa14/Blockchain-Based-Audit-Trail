"""
Audit Logger Module
Comprehensive audit logging for synthetic data generation and verification.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
from pathlib import Path


class LogLevel(Enum):
    """Log levels for audit entries."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events."""
    DATA_GENERATION = "data_generation"
    DATA_UPLOAD = "data_upload"
    PRIVACY_VERIFICATION = "privacy_verification"
    UTILITY_VERIFICATION = "utility_verification"
    BIAS_DETECTION = "bias_detection"
    COMPLIANCE_CHECK = "compliance_check"
    CONSENSUS_REQUEST = "consensus_request"
    CONSENSUS_RESULT = "consensus_result"
    BLOCKCHAIN_TRANSACTION = "blockchain_transaction"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    ERROR = "error"


@dataclass
class AuditEntry:
    """Represents a single audit log entry."""
    entry_id: str
    timestamp: str
    event_type: str
    level: str
    actor: str
    action: str
    resource: str
    resource_hash: Optional[str]
    details: Dict
    metadata: Dict
    previous_entry_hash: Optional[str]
    entry_hash: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


@dataclass
class AuditSession:
    """Represents an audit session."""
    session_id: str
    started_at: str
    ended_at: Optional[str]
    actor: str
    entries: List[str]  # List of entry IDs
    summary: Dict
    
    def to_dict(self) -> Dict:
        return asdict(self)


class AuditLogger:
    """
    Comprehensive audit logging system.
    
    Features:
    - Immutable audit trail with hash chaining
    - Multiple output formats (file, console, JSON)
    - Session management
    - Event categorization
    - Search and filtering
    """
    
    def __init__(self, 
                 log_dir: str = "logs",
                 log_file: str = "audit.log",
                 json_file: str = "audit.json",
                 console_output: bool = True,
                 file_output: bool = True,
                 json_output: bool = True):
        """
        Initialize the Audit Logger.
        
        Args:
            log_dir: Directory for log files
            log_file: Name of the text log file
            json_file: Name of the JSON log file
            console_output: Enable console logging
            file_output: Enable file logging
            json_output: Enable JSON logging
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / log_file
        self.json_file = self.log_dir / json_file
        
        self.console_output = console_output
        self.file_output = file_output
        self.json_output = json_output
        
        # Entry storage
        self.entries: Dict[str, AuditEntry] = {}
        self.entry_chain: List[str] = []  # Ordered list of entry IDs
        
        # Session management
        self.sessions: Dict[str, AuditSession] = {}
        self.current_session_id: Optional[str] = None
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize standard logger
        self._setup_logger()
        
        # Load existing entries if available
        self._load_existing_entries()
    
    def _setup_logger(self):
        """Set up the standard Python logger."""
        self.logger = logging.getLogger('AuditLogger')
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Console handler
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s'
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)
        
        # File handler
        if self.file_output:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
    
    def _load_existing_entries(self):
        """Load existing entries from JSON file."""
        if self.json_output and self.json_file.exists():
            try:
                with open(self.json_file, 'r') as f:
                    data = json.load(f)
                    for entry_data in data.get('entries', []):
                        entry = AuditEntry(**entry_data)
                        self.entries[entry.entry_id] = entry
                        self.entry_chain.append(entry.entry_id)
            except (json.JSONDecodeError, KeyError):
                pass  # Start fresh if file is corrupted
    
    def _save_entries(self):
        """Save all entries to JSON file."""
        if self.json_output:
            with open(self.json_file, 'w') as f:
                json.dump({
                    'entries': [self.entries[eid].to_dict() for eid in self.entry_chain],
                    'sessions': {sid: s.to_dict() for sid, s in self.sessions.items()},
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2, default=str)
    
    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        timestamp = datetime.now().isoformat()
        return hashlib.sha256(f"{timestamp}{len(self.entries)}".encode()).hexdigest()[:16]
    
    def _compute_entry_hash(self, entry_data: Dict) -> str:
        """Compute hash for an entry."""
        data_str = json.dumps(entry_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _get_previous_hash(self) -> Optional[str]:
        """Get the hash of the previous entry for chaining."""
        if self.entry_chain:
            last_entry_id = self.entry_chain[-1]
            return self.entries[last_entry_id].entry_hash
        return None
    
    def start_session(self, actor: str = "system") -> str:
        """
        Start a new audit session.
        
        Args:
            actor: The actor starting the session
            
        Returns:
            Session ID
        """
        session_id = hashlib.sha256(
            f"{datetime.now().isoformat()}{actor}".encode()
        ).hexdigest()[:16]
        
        session = AuditSession(
            session_id=session_id,
            started_at=datetime.now().isoformat(),
            ended_at=None,
            actor=actor,
            entries=[],
            summary={}
        )
        
        with self._lock:
            self.sessions[session_id] = session
            self.current_session_id = session_id
        
        self.log(
            event_type=AuditEventType.SYSTEM_EVENT,
            level=LogLevel.INFO,
            actor=actor,
            action="session_started",
            resource="session",
            details={'session_id': session_id}
        )
        
        return session_id
    
    def end_session(self, session_id: Optional[str] = None) -> Dict:
        """
        End an audit session.
        
        Args:
            session_id: Session ID to end (uses current if not specified)
            
        Returns:
            Session summary
        """
        sid = session_id or self.current_session_id
        if not sid or sid not in self.sessions:
            return {'error': 'Session not found'}
        
        with self._lock:
            session = self.sessions[sid]
            session.ended_at = datetime.now().isoformat()
            session.summary = {
                'total_entries': len(session.entries),
                'duration_seconds': self._calculate_duration(session),
                'event_counts': self._count_events(session.entries)
            }
            
            if self.current_session_id == sid:
                self.current_session_id = None
        
        self.log(
            event_type=AuditEventType.SYSTEM_EVENT,
            level=LogLevel.INFO,
            actor=session.actor,
            action="session_ended",
            resource="session",
            details={'session_id': sid, 'summary': session.summary}
        )
        
        self._save_entries()
        
        return session.to_dict()
    
    def _calculate_duration(self, session: AuditSession) -> float:
        """Calculate session duration in seconds."""
        start = datetime.fromisoformat(session.started_at)
        end = datetime.fromisoformat(session.ended_at) if session.ended_at else datetime.now()
        return (end - start).total_seconds()
    
    def _count_events(self, entry_ids: List[str]) -> Dict[str, int]:
        """Count events by type."""
        counts = {}
        for eid in entry_ids:
            if eid in self.entries:
                event_type = self.entries[eid].event_type
                counts[event_type] = counts.get(event_type, 0) + 1
        return counts
    
    def log(self,
            event_type: AuditEventType,
            level: LogLevel,
            actor: str,
            action: str,
            resource: str,
            details: Optional[Dict] = None,
            resource_hash: Optional[str] = None,
            metadata: Optional[Dict] = None) -> str:
        """
        Log an audit entry.
        
        Args:
            event_type: Type of audit event
            level: Log level
            actor: Who performed the action
            action: What action was performed
            resource: What resource was affected
            details: Additional details
            resource_hash: Hash of the resource
            metadata: Additional metadata
            
        Returns:
            Entry ID
        """
        entry_id = self._generate_entry_id()
        previous_hash = self._get_previous_hash()
        
        # Prepare entry data (without final hash)
        entry_data = {
            'entry_id': entry_id,
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type.value if isinstance(event_type, AuditEventType) else event_type,
            'level': level.value if isinstance(level, LogLevel) else level,
            'actor': actor,
            'action': action,
            'resource': resource,
            'resource_hash': resource_hash,
            'details': details or {},
            'metadata': metadata or {},
            'previous_entry_hash': previous_hash
        }
        
        # Compute hash
        entry_hash = self._compute_entry_hash(entry_data)
        entry_data['entry_hash'] = entry_hash
        
        # Create entry
        entry = AuditEntry(**entry_data)
        
        with self._lock:
            self.entries[entry_id] = entry
            self.entry_chain.append(entry_id)
            
            # Add to current session if active
            if self.current_session_id and self.current_session_id in self.sessions:
                self.sessions[self.current_session_id].entries.append(entry_id)
        
        # Log to standard logger
        log_message = f"[{event_type.value if isinstance(event_type, AuditEventType) else event_type}] {actor} - {action} on {resource}"
        getattr(self.logger, level.value if isinstance(level, LogLevel) else level)(log_message)
        
        # Save to JSON
        self._save_entries()
        
        return entry_id
    
    def log_generation(self, 
                       generator_type: str,
                       input_hash: str,
                       output_hash: str,
                       num_rows: int,
                       hyperparameters: Dict,
                       actor: str = "system") -> str:
        """Log a data generation event."""
        return self.log(
            event_type=AuditEventType.DATA_GENERATION,
            level=LogLevel.INFO,
            actor=actor,
            action="generate_synthetic_data",
            resource="synthetic_dataset",
            resource_hash=output_hash,
            details={
                'generator_type': generator_type,
                'input_hash': input_hash,
                'output_hash': output_hash,
                'num_rows': num_rows,
                'hyperparameters': hyperparameters
            }
        )
    
    def log_verification(self,
                         verification_type: str,
                         data_hash: str,
                         score: float,
                         passed: bool,
                         details: Dict,
                         actor: str = "system") -> str:
        """Log a verification event."""
        event_type_map = {
            'privacy': AuditEventType.PRIVACY_VERIFICATION,
            'utility': AuditEventType.UTILITY_VERIFICATION,
            'bias': AuditEventType.BIAS_DETECTION,
            'compliance': AuditEventType.COMPLIANCE_CHECK
        }
        
        return self.log(
            event_type=event_type_map.get(verification_type, AuditEventType.SYSTEM_EVENT),
            level=LogLevel.INFO,
            actor=actor,
            action=f"verify_{verification_type}",
            resource="verification_result",
            resource_hash=data_hash,
            details={
                'verification_type': verification_type,
                'score': score,
                'passed': passed,
                **details
            }
        )
    
    def log_consensus(self,
                      data_hash: str,
                      status: str,
                      scores: Dict,
                      num_verifiers: int,
                      actor: str = "system") -> str:
        """Log a consensus event."""
        return self.log(
            event_type=AuditEventType.CONSENSUS_RESULT,
            level=LogLevel.INFO,
            actor=actor,
            action="consensus_reached",
            resource="consensus_record",
            resource_hash=data_hash,
            details={
                'status': status,
                'scores': scores,
                'num_verifiers': num_verifiers
            }
        )
    
    def log_blockchain(self,
                       transaction_id: str,
                       data_hash: str,
                       transaction_type: str,
                       block_hash: str,
                       actor: str = "system") -> str:
        """Log a blockchain transaction."""
        return self.log(
            event_type=AuditEventType.BLOCKCHAIN_TRANSACTION,
            level=LogLevel.INFO,
            actor=actor,
            action=f"blockchain_{transaction_type}",
            resource="blockchain_entry",
            resource_hash=block_hash,
            details={
                'transaction_id': transaction_id,
                'data_hash': data_hash,
                'transaction_type': transaction_type,
                'block_hash': block_hash
            }
        )
    
    def log_error(self,
                  error_type: str,
                  error_message: str,
                  details: Dict,
                  actor: str = "system") -> str:
        """Log an error event."""
        return self.log(
            event_type=AuditEventType.ERROR,
            level=LogLevel.ERROR,
            actor=actor,
            action="error_occurred",
            resource="error",
            details={
                'error_type': error_type,
                'error_message': error_message,
                **details
            }
        )
    
    def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Get a specific entry by ID."""
        return self.entries.get(entry_id)
    
    def get_entries(self,
                    event_type: Optional[AuditEventType] = None,
                    level: Optional[LogLevel] = None,
                    actor: Optional[str] = None,
                    start_time: Optional[str] = None,
                    end_time: Optional[str] = None,
                    limit: Optional[int] = None) -> List[AuditEntry]:
        """
        Get entries with optional filtering.
        
        Args:
            event_type: Filter by event type
            level: Filter by log level
            actor: Filter by actor
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            limit: Maximum number of entries to return
            
        Returns:
            List of matching entries
        """
        results = []
        
        for entry_id in reversed(self.entry_chain):  # Most recent first
            entry = self.entries[entry_id]
            
            # Apply filters
            if event_type and entry.event_type != event_type.value:
                continue
            if level and entry.level != level.value:
                continue
            if actor and entry.actor != actor:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
            
            results.append(entry)
            
            if limit and len(results) >= limit:
                break
        
        return results
    
    def verify_chain_integrity(self) -> Dict:
        """
        Verify the integrity of the audit chain.
        
        Returns:
            Verification result with any integrity issues
        """
        issues = []
        
        for i, entry_id in enumerate(self.entry_chain):
            entry = self.entries[entry_id]
            
            # Verify entry hash
            entry_data = {
                'entry_id': entry.entry_id,
                'timestamp': entry.timestamp,
                'event_type': entry.event_type,
                'level': entry.level,
                'actor': entry.actor,
                'action': entry.action,
                'resource': entry.resource,
                'resource_hash': entry.resource_hash,
                'details': entry.details,
                'metadata': entry.metadata,
                'previous_entry_hash': entry.previous_entry_hash
            }
            
            computed_hash = self._compute_entry_hash(entry_data)
            if computed_hash != entry.entry_hash:
                issues.append({
                    'entry_id': entry_id,
                    'issue': 'hash_mismatch',
                    'expected': entry.entry_hash,
                    'computed': computed_hash
                })
            
            # Verify chain link
            if i > 0:
                previous_entry = self.entries[self.entry_chain[i - 1]]
                if entry.previous_entry_hash != previous_entry.entry_hash:
                    issues.append({
                        'entry_id': entry_id,
                        'issue': 'chain_break',
                        'expected_previous': previous_entry.entry_hash,
                        'stored_previous': entry.previous_entry_hash
                    })
        
        return {
            'integrity_valid': len(issues) == 0,
            'total_entries': len(self.entry_chain),
            'issues_found': len(issues),
            'issues': issues
        }
    
    def export_audit_trail(self, 
                           format: str = 'json',
                           filepath: Optional[str] = None) -> str:
        """
        Export the audit trail.
        
        Args:
            format: Export format ('json', 'csv', 'txt')
            filepath: Output file path (uses default if not specified)
            
        Returns:
            Path to exported file
        """
        if filepath is None:
            filepath = self.log_dir / f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        
        if format == 'json':
            with open(filepath, 'w') as f:
                json.dump({
                    'exported_at': datetime.now().isoformat(),
                    'total_entries': len(self.entry_chain),
                    'integrity': self.verify_chain_integrity(),
                    'entries': [self.entries[eid].to_dict() for eid in self.entry_chain]
                }, f, indent=2, default=str)
        
        elif format == 'csv':
            import csv
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['entry_id', 'timestamp', 'event_type', 'level', 
                                'actor', 'action', 'resource', 'resource_hash'])
                for eid in self.entry_chain:
                    entry = self.entries[eid]
                    writer.writerow([
                        entry.entry_id, entry.timestamp, entry.event_type,
                        entry.level, entry.actor, entry.action,
                        entry.resource, entry.resource_hash
                    ])
        
        elif format == 'txt':
            with open(filepath, 'w') as f:
                for eid in self.entry_chain:
                    entry = self.entries[eid]
                    f.write(f"[{entry.timestamp}] [{entry.level.upper()}] "
                           f"{entry.event_type}: {entry.actor} - {entry.action}\n")
                    f.write(f"  Resource: {entry.resource}\n")
                    if entry.details:
                        f.write(f"  Details: {json.dumps(entry.details, default=str)}\n")
                    f.write("\n")
        
        return str(filepath)
    
    def get_summary(self) -> Dict:
        """Get a summary of the audit log."""
        event_counts = {}
        level_counts = {}
        actor_counts = {}
        
        for entry in self.entries.values():
            event_counts[entry.event_type] = event_counts.get(entry.event_type, 0) + 1
            level_counts[entry.level] = level_counts.get(entry.level, 0) + 1
            actor_counts[entry.actor] = actor_counts.get(entry.actor, 0) + 1
        
        return {
            'total_entries': len(self.entries),
            'total_sessions': len(self.sessions),
            'active_session': self.current_session_id,
            'integrity': self.verify_chain_integrity(),
            'event_breakdown': event_counts,
            'level_breakdown': level_counts,
            'actor_breakdown': actor_counts,
            'first_entry': self.entries[self.entry_chain[0]].timestamp if self.entry_chain else None,
            'last_entry': self.entries[self.entry_chain[-1]].timestamp if self.entry_chain else None
        }


# Global logger instance
_global_logger: Optional[AuditLogger] = None


def get_logger(log_dir: str = "logs") -> AuditLogger:
    """Get or create the global audit logger."""
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditLogger(log_dir=log_dir)
    return _global_logger


def log_event(event_type: AuditEventType,
              level: LogLevel,
              actor: str,
              action: str,
              resource: str,
              **kwargs) -> str:
    """Convenience function to log an event."""
    logger = get_logger()
    return logger.log(event_type, level, actor, action, resource, **kwargs)
