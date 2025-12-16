"""
Blockchain Client Module
Python SDK wrapper for blockchain interactions.
Supports both simulation mode and Hyperledger Fabric integration.
"""

import hashlib
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import os


class BlockchainMode(Enum):
    """Blockchain operation mode."""
    SIMULATION = "simulation"
    FABRIC = "fabric"
    ETHEREUM = "ethereum"


@dataclass
class AuditEntry:
    """Represents an audit entry on the blockchain."""
    entry_id: str
    data_hash: str
    entry_type: str
    payload: Dict
    timestamp: str
    previous_hash: str
    block_hash: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Block:
    """Represents a block in the simulated blockchain."""
    index: int
    timestamp: str
    entries: List[AuditEntry]
    previous_hash: str
    nonce: int
    hash: str
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['entries'] = [e.to_dict() for e in self.entries]
        return result


class SimulatedBlockchain:
    """
    Simulated blockchain for development and testing.
    Implements basic blockchain functionality without network overhead.
    """
    
    def __init__(self):
        self.chain: List[Block] = []
        self.pending_entries: List[AuditEntry] = []
        self.entry_index: Dict[str, AuditEntry] = {}
        self._lock = threading.Lock()
        
        # Create genesis block
        self._create_genesis_block()
    
    def _create_genesis_block(self):
        """Create the genesis (first) block."""
        genesis = Block(
            index=0,
            timestamp=datetime.now().isoformat(),
            entries=[],
            previous_hash="0" * 64,
            nonce=0,
            hash=self._compute_hash(0, "0" * 64, [], 0)
        )
        self.chain.append(genesis)
    
    def _compute_hash(self, index: int, previous_hash: str, 
                      entries: List, nonce: int) -> str:
        """Compute block hash."""
        content = f"{index}{previous_hash}{json.dumps([e.to_dict() if hasattr(e, 'to_dict') else e for e in entries])}{nonce}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def add_entry(self, data_hash: str, entry_type: str, payload: Dict) -> str:
        """
        Add an entry to the pending pool.
        
        Args:
            data_hash: Hash of the data being audited
            entry_type: Type of audit entry (e.g., 'generation', 'verification')
            payload: Entry payload data
            
        Returns:
            Entry ID
        """
        entry_id = hashlib.sha256(
            f"{data_hash}{entry_type}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        entry = AuditEntry(
            entry_id=entry_id,
            data_hash=data_hash,
            entry_type=entry_type,
            payload=payload,
            timestamp=datetime.now().isoformat(),
            previous_hash=self.chain[-1].hash if self.chain else "0" * 64,
            block_hash=""  # Will be set when mined
        )
        
        with self._lock:
            self.pending_entries.append(entry)
        
        return entry_id
    
    def mine_block(self) -> Optional[Block]:
        """
        Mine a new block with pending entries.
        
        Returns:
            New block if entries were pending, None otherwise
        """
        with self._lock:
            if not self.pending_entries:
                return None
            
            entries = self.pending_entries.copy()
            self.pending_entries = []
        
        previous_hash = self.chain[-1].hash
        index = len(self.chain)
        nonce = 0
        
        # Simple proof-of-work (find hash starting with "00")
        while True:
            block_hash = self._compute_hash(index, previous_hash, entries, nonce)
            if block_hash.startswith("00"):
                break
            nonce += 1
            if nonce > 100000:  # Limit for testing
                break
        
        # Update entry block hashes
        for entry in entries:
            entry.block_hash = block_hash
            self.entry_index[entry.entry_id] = entry
        
        block = Block(
            index=index,
            timestamp=datetime.now().isoformat(),
            entries=entries,
            previous_hash=previous_hash,
            nonce=nonce,
            hash=block_hash
        )
        
        with self._lock:
            self.chain.append(block)
        
        return block
    
    def get_entry(self, entry_id: str) -> Optional[AuditEntry]:
        """Get an entry by ID."""
        return self.entry_index.get(entry_id)
    
    def get_entries_by_hash(self, data_hash: str) -> List[AuditEntry]:
        """Get all entries for a data hash."""
        return [e for e in self.entry_index.values() if e.data_hash == data_hash]
    
    def verify_chain(self) -> bool:
        """Verify blockchain integrity."""
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]
            
            # Check previous hash reference
            if current.previous_hash != previous.hash:
                return False
            
            # Verify block hash
            computed_hash = self._compute_hash(
                current.index, 
                current.previous_hash,
                current.entries,
                current.nonce
            )
            if computed_hash != current.hash:
                return False
        
        return True
    
    def get_chain_info(self) -> Dict:
        """Get blockchain information."""
        return {
            'chain_length': len(self.chain),
            'total_entries': len(self.entry_index),
            'pending_entries': len(self.pending_entries),
            'chain_valid': self.verify_chain(),
            'latest_block_hash': self.chain[-1].hash if self.chain else None
        }


class BlockchainClient:
    """
    Unified blockchain client supporting multiple backends.
    """
    
    def __init__(self, mode: BlockchainMode = BlockchainMode.SIMULATION,
                 config: Optional[Dict] = None):
        """
        Initialize blockchain client.
        
        Args:
            mode: Operating mode (simulation, fabric, ethereum)
            config: Backend-specific configuration
        """
        self.mode = mode
        self.config = config or {}
        
        if mode == BlockchainMode.SIMULATION:
            self.backend = SimulatedBlockchain()
        elif mode == BlockchainMode.FABRIC:
            self.backend = self._init_fabric_backend()
        elif mode == BlockchainMode.ETHEREUM:
            self.backend = self._init_ethereum_backend()
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        
        # Auto-mine thread for simulation mode
        self._auto_mine = False
        self._mine_thread = None
    
    def _init_fabric_backend(self):
        """Initialize Hyperledger Fabric backend."""
        # Placeholder for Fabric SDK integration
        # In production, this would connect to a Fabric network
        print("Warning: Fabric backend not implemented, using simulation")
        return SimulatedBlockchain()
    
    def _init_ethereum_backend(self):
        """Initialize Ethereum backend."""
        # Placeholder for Web3 integration
        print("Warning: Ethereum backend not implemented, using simulation")
        return SimulatedBlockchain()
    
    def start_auto_mine(self, interval: int = 5):
        """Start automatic block mining (simulation mode only)."""
        if self.mode != BlockchainMode.SIMULATION:
            return
        
        self._auto_mine = True
        
        def mine_loop():
            while self._auto_mine:
                self.backend.mine_block()
                time.sleep(interval)
        
        self._mine_thread = threading.Thread(target=mine_loop, daemon=True)
        self._mine_thread.start()
    
    def stop_auto_mine(self):
        """Stop automatic block mining."""
        self._auto_mine = False
    
    # ==================== Audit Trail Operations ====================
    
    def log_generation(self, data_hash: str, generator_type: str,
                       parameters: Dict, metadata: Optional[Dict] = None) -> str:
        """
        Log synthetic data generation event.
        
        Args:
            data_hash: Hash of generated synthetic data
            generator_type: Type of generator (e.g., 'CTGAN', 'VAE')
            parameters: Generator parameters
            metadata: Additional metadata
            
        Returns:
            Entry ID
        """
        payload = {
            'event': 'data_generation',
            'generator_type': generator_type,
            'parameters': parameters,
            'metadata': metadata or {},
            'data_hash': data_hash
        }
        
        entry_id = self.backend.add_entry(data_hash, 'generation', payload)
        
        # Auto-mine if not in auto-mine mode
        if self.mode == BlockchainMode.SIMULATION and not self._auto_mine:
            self.backend.mine_block()
        
        return entry_id
    
    def log_verification(self, data_hash: str, verification_id: str,
                         verifier_id: str, results: Dict) -> str:
        """
        Log verification submission.
        
        Args:
            data_hash: Hash of data being verified
            verification_id: Verification request ID
            verifier_id: ID of the verifier
            results: Verification results
            
        Returns:
            Entry ID
        """
        payload = {
            'event': 'verification_submission',
            'verification_id': verification_id,
            'verifier_id': verifier_id,
            'results': results,
            'data_hash': data_hash
        }
        
        entry_id = self.backend.add_entry(data_hash, 'verification', payload)
        
        if self.mode == BlockchainMode.SIMULATION and not self._auto_mine:
            self.backend.mine_block()
        
        return entry_id
    
    def log_consensus(self, data_hash: str, verification_id: str,
                      consensus_result: Dict) -> str:
        """
        Log consensus result.
        
        Args:
            data_hash: Hash of verified data
            verification_id: Verification ID
            consensus_result: Consensus results
            
        Returns:
            Entry ID
        """
        payload = {
            'event': 'consensus_reached',
            'verification_id': verification_id,
            'consensus_result': consensus_result,
            'data_hash': data_hash
        }
        
        entry_id = self.backend.add_entry(data_hash, 'consensus', payload)
        
        if self.mode == BlockchainMode.SIMULATION and not self._auto_mine:
            self.backend.mine_block()
        
        return entry_id
    
    def log_compliance_check(self, data_hash: str, regulation: str,
                             compliance_result: Dict) -> str:
        """
        Log regulatory compliance check.
        
        Args:
            data_hash: Hash of data being checked
            regulation: Regulation name (e.g., 'GDPR', 'HIPAA')
            compliance_result: Compliance check results
            
        Returns:
            Entry ID
        """
        payload = {
            'event': 'compliance_check',
            'regulation': regulation,
            'result': compliance_result,
            'data_hash': data_hash
        }
        
        entry_id = self.backend.add_entry(data_hash, 'compliance', payload)
        
        if self.mode == BlockchainMode.SIMULATION and not self._auto_mine:
            self.backend.mine_block()
        
        return entry_id
    
    # ==================== Query Operations ====================
    
    def get_audit_trail(self, data_hash: str) -> List[Dict]:
        """
        Get complete audit trail for a data hash.
        
        Args:
            data_hash: Hash of the data
            
        Returns:
            List of audit entries
        """
        entries = self.backend.get_entries_by_hash(data_hash)
        return [e.to_dict() for e in sorted(entries, key=lambda x: x.timestamp)]
    
    def get_entry(self, entry_id: str) -> Optional[Dict]:
        """Get a specific audit entry."""
        entry = self.backend.get_entry(entry_id)
        return entry.to_dict() if entry else None
    
    def verify_data_integrity(self, data_hash: str, 
                              expected_hash: str) -> Dict:
        """
        Verify data integrity against blockchain records.
        
        Args:
            data_hash: Current data hash
            expected_hash: Expected hash from records
            
        Returns:
            Verification result
        """
        matches = data_hash == expected_hash
        entries = self.backend.get_entries_by_hash(expected_hash)
        
        return {
            'data_matches': matches,
            'hash_recorded': len(entries) > 0,
            'num_audit_entries': len(entries),
            'chain_valid': self.backend.verify_chain() if hasattr(self.backend, 'verify_chain') else True
        }
    
    def get_verification_history(self, data_hash: str) -> List[Dict]:
        """Get all verifications for a data hash."""
        entries = self.backend.get_entries_by_hash(data_hash)
        return [
            e.to_dict() for e in entries 
            if e.entry_type in ['verification', 'consensus']
        ]
    
    def get_blockchain_stats(self) -> Dict:
        """Get blockchain statistics."""
        if hasattr(self.backend, 'get_chain_info'):
            return self.backend.get_chain_info()
        return {'mode': self.mode.value}
    
    # ==================== Export/Import ====================
    
    def export_audit_trail(self, data_hash: str, 
                           filepath: Optional[str] = None) -> Dict:
        """
        Export audit trail to JSON.
        
        Args:
            data_hash: Data hash to export
            filepath: Optional file path to save
            
        Returns:
            Export data
        """
        trail = self.get_audit_trail(data_hash)
        
        export_data = {
            'data_hash': data_hash,
            'export_timestamp': datetime.now().isoformat(),
            'audit_entries': trail,
            'blockchain_info': self.get_blockchain_stats()
        }
        
        if filepath:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
        
        return export_data


# Convenience functions
def create_blockchain_client(mode: str = "simulation") -> BlockchainClient:
    """Create a blockchain client with specified mode."""
    mode_enum = BlockchainMode(mode)
    return BlockchainClient(mode=mode_enum)


def compute_data_hash(data) -> str:
    """Compute hash of data (DataFrame or dict)."""
    if hasattr(data, 'to_json'):
        data_string = data.to_json()
    else:
        data_string = json.dumps(data, sort_keys=True, default=str)
    
    return hashlib.sha256(data_string.encode()).hexdigest()
