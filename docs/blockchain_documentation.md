# Blockchain Implementation Documentation

## Overview

This document describes the blockchain implementation for the audit trail system, including both simulation and production modes.

---

## Architecture

### Two-Mode Design

The system supports two operational modes:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BlockchainClient                             │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │   SIMULATION MODE   │    │   PRODUCTION MODE    │           │
│  │                     │    │                      │           │
│  │  SimulatedBlockchain│    │  HyperledgerFabric   │           │
│  │  - In-memory        │    │  - Distributed       │           │
│  │  - Instant          │    │  - Multi-org         │           │
│  │  - Testing/Dev      │    │  - Permissioned      │           │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Current Implementation: Simulation Mode

### Features

| Feature | Implementation |
|---------|----------------|
| **Blocks** | In-memory linked list |
| **Hashing** | SHA-256 |
| **Timestamps** | ISO format |
| **Persistence** | Session-only (no disk storage) |
| **Consensus** | Instant (no network delay) |

### SimulatedBlockchain Class

```python
class SimulatedBlockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self._create_genesis_block()
    
    def add_transaction(self, transaction: Dict) -> str:
        """Add transaction to pending pool."""
        tx_id = compute_hash(transaction)
        self.pending_transactions.append({
            'id': tx_id,
            'data': transaction,
            'timestamp': datetime.now().isoformat()
        })
        return tx_id
    
    def mine_block(self) -> Dict:
        """Create new block from pending transactions."""
        block = {
            'index': len(self.chain),
            'timestamp': datetime.now().isoformat(),
            'transactions': self.pending_transactions,
            'previous_hash': self.chain[-1]['hash'] if self.chain else '0',
            'hash': self._compute_block_hash()
        }
        self.chain.append(block)
        self.pending_transactions = []
        return block
```

### Limitations of Simulation Mode

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **No persistence** | Data lost on restart | Export reports to JSON |
| **No distribution** | Single point of failure | Simulation only for testing |
| **No real consensus** | Instant approval | Simulates multi-verifier workflow |
| **No tamper resistance** | Data can be modified | For development only |
| **No cryptographic signing** | No identity verification | Uses mock verifier IDs |

---

## Production Mode: Hyperledger Fabric

### Planned Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Hyperledger Fabric Network                    │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Org 1:     │  │   Org 2:     │  │   Org 3:     │          │
│  │   Hospital   │  │   Regulator  │  │   Research   │          │
│  │              │  │              │  │              │          │
│  │  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────┐  │          │
│  │  │ Peer 0 │  │  │  │ Peer 0 │  │  │  │ Peer 0 │  │          │
│  │  │ Peer 1 │  │  │  │ Peer 1 │  │  │  │ Peer 1 │  │          │
│  │  └────────┘  │  │  └────────┘  │  │  └────────┘  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Ordering Service                          ││
│  │                    (RAFT Consensus)                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Channel: verification                     ││
│  │                    Chaincode: audit_trail                    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Smart Contract Design (Chaincode)

#### verification_consensus.go

```go
package main

import (
    "encoding/json"
    "fmt"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type VerificationContract struct {
    contractapi.Contract
}

type VerificationRecord struct {
    DataHash      string             `json:"data_hash"`
    VerifierID    string             `json:"verifier_id"`
    Timestamp     string             `json:"timestamp"`
    PrivacyScore  float64            `json:"privacy_score"`
    UtilityScore  float64            `json:"utility_score"`
    BiasScore     float64            `json:"bias_score"`
    OverallScore  float64            `json:"overall_score"`
    Status        string             `json:"status"`
}

type ConsensusRecord struct {
    DataHash           string  `json:"data_hash"`
    FinalPrivacyScore  float64 `json:"final_privacy_score"`
    FinalUtilityScore  float64 `json:"final_utility_score"`
    FinalBiasScore     float64 `json:"final_bias_score"`
    FinalOverallScore  float64 `json:"final_overall_score"`
    FinalStatus        string  `json:"final_status"`
    NumVerifiers       int     `json:"num_verifiers"`
    ConsensusTimestamp string  `json:"consensus_timestamp"`
}

// SubmitVerification submits a verification result
func (vc *VerificationContract) SubmitVerification(
    ctx contractapi.TransactionContextInterface,
    dataHash string,
    verifierID string,
    privacyScore float64,
    utilityScore float64,
    biasScore float64,
) error {
    overallScore := (privacyScore + utilityScore + biasScore) / 3.0
    status := "pending"
    if overallScore >= 70.0 {
        status = "approved"
    } else {
        status = "rejected"
    }
    
    record := VerificationRecord{
        DataHash:     dataHash,
        VerifierID:   verifierID,
        Timestamp:    ctx.GetStub().GetTxTimestamp().String(),
        PrivacyScore: privacyScore,
        UtilityScore: utilityScore,
        BiasScore:    biasScore,
        OverallScore: overallScore,
        Status:       status,
    }
    
    key := fmt.Sprintf("verification_%s_%s", dataHash, verifierID)
    recordJSON, _ := json.Marshal(record)
    return ctx.GetStub().PutState(key, recordJSON)
}

// QueryConsensus retrieves consensus result for a data hash
func (vc *VerificationContract) QueryConsensus(
    ctx contractapi.TransactionContextInterface,
    dataHash string,
) (*ConsensusRecord, error) {
    // Implementation queries all verifications and computes median
    // ...
}
```

### Deployment Requirements

#### Prerequisites

```bash
# Docker & Docker Compose
docker --version  # >= 20.10
docker-compose --version  # >= 2.0

# Go (for chaincode)
go version  # >= 1.19

# Node.js (for SDK)
node --version  # >= 16.0

# Hyperledger Fabric binaries
curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.5.0
```

#### Network Configuration Files

```yaml
# docker-compose.yaml (excerpt)
version: '3.7'

services:
  orderer.example.com:
    container_name: orderer.example.com
    image: hyperledger/fabric-orderer:2.5
    environment:
      - ORDERER_GENERAL_LISTENADDRESS=0.0.0.0
      - ORDERER_GENERAL_BOOTSTRAPMETHOD=none
      - ORDERER_CHANNELPARTICIPATION_ENABLED=true
    volumes:
      - ./orderer:/var/hyperledger/orderer
    ports:
      - 7050:7050

  peer0.org1.example.com:
    container_name: peer0.org1.example.com
    image: hyperledger/fabric-peer:2.5
    environment:
      - CORE_PEER_ID=peer0.org1.example.com
      - CORE_PEER_ADDRESS=peer0.org1.example.com:7051
      - CORE_PEER_GOSSIP_BOOTSTRAP=peer0.org1.example.com:7051
    volumes:
      - ./org1/peer0:/var/hyperledger/peer
    ports:
      - 7051:7051
```

---

## Migration Path: Simulation → Production

### Step 1: Verify Simulation Works

```bash
python main_verification_pipeline.py \
    --real-data data/raw/adult.csv \
    --generate \
    --threshold 70
```

### Step 2: Set Up Fabric Test Network

```bash
cd fabric-samples/test-network
./network.sh up createChannel -c verification -ca
```

### Step 3: Deploy Chaincode

```bash
./network.sh deployCC \
    -ccn audit_trail \
    -ccp ../../blockchain/chaincode \
    -ccl go
```

### Step 4: Update Environment

```bash
# .env
BLOCKCHAIN_MODE=fabric
FABRIC_GATEWAY_HOST=localhost
FABRIC_GATEWAY_PORT=7051
FABRIC_CHANNEL=verification
FABRIC_CHAINCODE=audit_trail
```

### Step 5: Run with Production Mode

```bash
python main_verification_pipeline.py \
    --blockchain-mode fabric \
    --real-data data/raw/adult.csv \
    --generate
```

---

## Security Considerations

### Simulation Mode Risks

| Risk | Severity | Notes |
|------|----------|-------|
| Data tampering | High | No cryptographic protection |
| Result manipulation | High | In-memory only |
| Replay attacks | Medium | No nonce/sequence numbers |
| Identity spoofing | High | No MSP/certificates |

### Production Mode Protections

| Protection | Implementation |
|------------|----------------|
| **Identity** | X.509 certificates via MSP |
| **Integrity** | Block hashing + chain linking |
| **Consensus** | RAFT/PBFT with 2f+1 nodes |
| **Access Control** | Channel policies |
| **Audit** | Immutable transaction history |

---

## Performance Comparison

| Metric | Simulation | Production (est.) |
|--------|------------|-------------------|
| Transaction latency | < 1 ms | 100-500 ms |
| Throughput | 10,000+ tx/s | 1,000-3,000 tx/s |
| Storage | RAM only | Distributed ledger |
| Consensus time | Instant | 1-3 seconds |
| Setup complexity | None | High |

---

## Recommendations

### For Development/Testing
- Use **Simulation Mode**
- Focus on verification logic
- Export reports for audit trail

### For Production Deployment
- Deploy **Hyperledger Fabric** network
- Configure multi-organization setup
- Implement proper MSP/identity management
- Set up monitoring and logging

### For Research/Demos
- Simulation mode is sufficient
- Document limitations clearly
- Show architecture for production path

---

## Conclusion

The current implementation uses simulation mode for rapid development and testing. The architecture is designed to be compatible with Hyperledger Fabric deployment. For production use with real tamper-resistance guarantees, follow the migration path outlined above.

**Current Status:** Simulation Mode (Development/Testing)

**Production Readiness:** Architecture designed, chaincode templates available, deployment scripts pending.
