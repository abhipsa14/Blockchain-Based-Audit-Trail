/*
 * Audit Trail Smart Contract - Rust Implementation
 * Hyperledger Fabric Chaincode for Synthetic Data Audit Trail
 * 
 * This chaincode provides immutable storage for:
 * - Data generation events
 * - Verification submissions
 * - Consensus results
 * - Compliance attestations
 */

use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use chrono::{DateTime, Utc};

// ==================== Data Structures ====================

/// Represents a synthetic data generation event
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GenerationRecord {
    pub data_hash: String,
    pub generator_type: String,
    pub parameters: HashMap<String, String>,
    pub row_count: u64,
    pub column_count: u64,
    pub timestamp: String,
    pub generator_id: String,
    pub metadata: HashMap<String, String>,
}

/// Represents a verification submission from a peer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationRecord {
    pub verification_id: String,
    pub data_hash: String,
    pub verifier_id: String,
    pub privacy_score: f64,
    pub utility_score: f64,
    pub fairness_score: f64,
    pub overall_score: f64,
    pub status: VerificationStatus,
    pub details: HashMap<String, serde_json::Value>,
    pub timestamp: String,
}

/// Verification status enum
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum VerificationStatus {
    Pending,
    Passed,
    Failed,
    Rejected,
}

impl std::fmt::Display for VerificationStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VerificationStatus::Pending => write!(f, "PENDING"),
            VerificationStatus::Passed => write!(f, "PASSED"),
            VerificationStatus::Failed => write!(f, "FAILED"),
            VerificationStatus::Rejected => write!(f, "REJECTED"),
        }
    }
}

/// Represents a consensus result from multiple verifiers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsensusRecord {
    pub verification_id: String,
    pub data_hash: String,
    pub final_status: String,
    pub consensus_score: f64,
    pub verifier_count: u32,
    pub approval_threshold: f64,
    pub individual_results: Vec<VerificationRecord>,
    pub timestamp: String,
}

/// Represents a compliance attestation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceRecord {
    pub data_hash: String,
    pub framework: ComplianceFramework,
    pub compliance_score: f64,
    pub is_compliant: bool,
    pub violations: Vec<String>,
    pub attestor: String,
    pub timestamp: String,
}

/// Supported compliance frameworks
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ComplianceFramework {
    GDPR,
    HIPAA,
    CCPA,
    EU_AI_ACT,
    Custom(String),
}

impl std::fmt::Display for ComplianceFramework {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ComplianceFramework::GDPR => write!(f, "GDPR"),
            ComplianceFramework::HIPAA => write!(f, "HIPAA"),
            ComplianceFramework::CCPA => write!(f, "CCPA"),
            ComplianceFramework::EU_AI_ACT => write!(f, "EU_AI_ACT"),
            ComplianceFramework::Custom(name) => write!(f, "{}", name),
        }
    }
}

/// Audit entry for generic logging
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub entry_id: String,
    pub data_hash: String,
    pub entry_type: String,
    pub payload: serde_json::Value,
    pub timestamp: String,
    pub creator: String,
    pub tx_id: String,
}

/// Complete audit history for a data hash
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditHistory {
    pub data_hash: String,
    pub generation: Option<GenerationRecord>,
    pub verifications: Vec<VerificationRecord>,
    pub consensus: Option<ConsensusRecord>,
    pub compliance: Vec<ComplianceRecord>,
    pub query_timestamp: String,
}

// ==================== Error Types ====================

#[derive(Debug, thiserror::Error)]
pub enum ChainCodeError {
    #[error("Record not found: {0}")]
    NotFound(String),
    
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    
    #[error("Serialization error: {0}")]
    SerializationError(String),
    
    #[error("State error: {0}")]
    StateError(String),
    
    #[error("Authorization error: {0}")]
    AuthorizationError(String),
    
    #[error("Consensus error: {0}")]
    ConsensusError(String),
}

// ==================== Chaincode Implementation ====================

/// Main Audit Trail Contract
pub struct AuditTrailContract {
    // In-memory state for simulation
    generations: HashMap<String, GenerationRecord>,
    verifications: HashMap<String, Vec<VerificationRecord>>,
    consensus_records: HashMap<String, ConsensusRecord>,
    compliance_records: HashMap<String, Vec<ComplianceRecord>>,
}

impl AuditTrailContract {
    /// Create a new AuditTrailContract instance
    pub fn new() -> Self {
        AuditTrailContract {
            generations: HashMap::new(),
            verifications: HashMap::new(),
            consensus_records: HashMap::new(),
            compliance_records: HashMap::new(),
        }
    }

    /// Initialize the ledger
    pub fn init_ledger(&mut self) -> Result<(), ChainCodeError> {
        log::info!("Audit Trail Chaincode initialized");
        Ok(())
    }

    // ==================== Generation Functions ====================

    /// Log a synthetic data generation event
    pub fn log_generation(
        &mut self,
        data_hash: String,
        generator_type: String,
        parameters: HashMap<String, String>,
        row_count: u64,
        column_count: u64,
        generator_id: String,
        metadata: HashMap<String, String>,
    ) -> Result<GenerationRecord, ChainCodeError> {
        // Validate inputs
        if data_hash.is_empty() {
            return Err(ChainCodeError::InvalidInput("data_hash cannot be empty".into()));
        }
        if generator_type.is_empty() {
            return Err(ChainCodeError::InvalidInput("generator_type cannot be empty".into()));
        }

        let record = GenerationRecord {
            data_hash: data_hash.clone(),
            generator_type,
            parameters,
            row_count,
            column_count,
            timestamp: Utc::now().to_rfc3339(),
            generator_id,
            metadata,
        };

        self.generations.insert(data_hash, record.clone());
        
        log::info!("Generation logged: {}", record.data_hash);
        Ok(record)
    }

    /// Get a generation record by data hash
    pub fn get_generation(&self, data_hash: &str) -> Result<GenerationRecord, ChainCodeError> {
        self.generations
            .get(data_hash)
            .cloned()
            .ok_or_else(|| ChainCodeError::NotFound(format!("Generation not found: {}", data_hash)))
    }

    // ==================== Verification Functions ====================

    /// Submit a verification result from a peer
    pub fn submit_verification(
        &mut self,
        verification_id: String,
        data_hash: String,
        verifier_id: String,
        privacy_score: f64,
        utility_score: f64,
        fairness_score: f64,
        details: HashMap<String, serde_json::Value>,
    ) -> Result<VerificationRecord, ChainCodeError> {
        // Validate scores
        Self::validate_score(privacy_score, "privacy_score")?;
        Self::validate_score(utility_score, "utility_score")?;
        Self::validate_score(fairness_score, "fairness_score")?;

        // Calculate overall score (weighted average)
        let overall_score = privacy_score * 0.4 + utility_score * 0.35 + fairness_score * 0.25;

        // Determine status
        let status = if overall_score >= 70.0 {
            VerificationStatus::Passed
        } else {
            VerificationStatus::Failed
        };

        let record = VerificationRecord {
            verification_id: verification_id.clone(),
            data_hash: data_hash.clone(),
            verifier_id,
            privacy_score,
            utility_score,
            fairness_score,
            overall_score,
            status,
            details,
            timestamp: Utc::now().to_rfc3339(),
        };

        // Store in verifications map
        self.verifications
            .entry(verification_id)
            .or_insert_with(Vec::new)
            .push(record.clone());

        log::info!("Verification submitted: {} by {}", record.verification_id, record.verifier_id);
        Ok(record)
    }

    /// Get all verifications for a verification ID
    pub fn get_verifications(&self, verification_id: &str) -> Result<Vec<VerificationRecord>, ChainCodeError> {
        self.verifications
            .get(verification_id)
            .cloned()
            .ok_or_else(|| ChainCodeError::NotFound(format!("Verifications not found: {}", verification_id)))
    }

    /// Validate a score is within valid range
    fn validate_score(score: f64, name: &str) -> Result<(), ChainCodeError> {
        if score < 0.0 || score > 100.0 {
            return Err(ChainCodeError::InvalidInput(
                format!("{} must be between 0 and 100, got {}", name, score)
            ));
        }
        Ok(())
    }

    // ==================== Consensus Functions ====================

    /// Record consensus result after verifier quorum is reached
    pub fn record_consensus(
        &mut self,
        verification_id: String,
        data_hash: String,
        approval_threshold: f64,
    ) -> Result<ConsensusRecord, ChainCodeError> {
        // Get all verifications
        let verifications = self.get_verifications(&verification_id)?;
        
        if verifications.is_empty() {
            return Err(ChainCodeError::ConsensusError("No verifications found".into()));
        }

        // Calculate consensus score (median of overall scores)
        let mut scores: Vec<f64> = verifications.iter()
            .map(|v| v.overall_score)
            .collect();
        scores.sort_by(|a, b| a.partial_cmp(b).unwrap());
        
        let consensus_score = if scores.len() % 2 == 0 {
            (scores[scores.len() / 2 - 1] + scores[scores.len() / 2]) / 2.0
        } else {
            scores[scores.len() / 2]
        };

        // Determine final status
        let final_status = if consensus_score >= approval_threshold {
            "APPROVED".to_string()
        } else {
            "REJECTED".to_string()
        };

        let record = ConsensusRecord {
            verification_id: verification_id.clone(),
            data_hash,
            final_status,
            consensus_score,
            verifier_count: verifications.len() as u32,
            approval_threshold,
            individual_results: verifications,
            timestamp: Utc::now().to_rfc3339(),
        };

        self.consensus_records.insert(verification_id, record.clone());
        
        log::info!("Consensus recorded: {} - {}", record.verification_id, record.final_status);
        Ok(record)
    }

    /// Query consensus result
    pub fn query_consensus(&self, verification_id: &str) -> Result<ConsensusRecord, ChainCodeError> {
        self.consensus_records
            .get(verification_id)
            .cloned()
            .ok_or_else(|| ChainCodeError::NotFound(format!("Consensus not found: {}", verification_id)))
    }

    // ==================== Compliance Functions ====================

    /// Record a compliance attestation
    pub fn record_compliance(
        &mut self,
        data_hash: String,
        framework: ComplianceFramework,
        compliance_score: f64,
        is_compliant: bool,
        violations: Vec<String>,
        attestor: String,
    ) -> Result<ComplianceRecord, ChainCodeError> {
        Self::validate_score(compliance_score, "compliance_score")?;

        let record = ComplianceRecord {
            data_hash: data_hash.clone(),
            framework,
            compliance_score,
            is_compliant,
            violations,
            attestor,
            timestamp: Utc::now().to_rfc3339(),
        };

        self.compliance_records
            .entry(data_hash)
            .or_insert_with(Vec::new)
            .push(record.clone());

        log::info!("Compliance recorded: {} - {}", record.data_hash, record.framework);
        Ok(record)
    }

    /// Query compliance for a data hash and framework
    pub fn query_compliance(
        &self,
        data_hash: &str,
        framework: &ComplianceFramework,
    ) -> Result<ComplianceRecord, ChainCodeError> {
        self.compliance_records
            .get(data_hash)
            .and_then(|records| {
                records.iter().find(|r| &r.framework == framework).cloned()
            })
            .ok_or_else(|| ChainCodeError::NotFound(
                format!("Compliance not found: {} - {}", data_hash, framework)
            ))
    }

    // ==================== Query Functions ====================

    /// Get complete audit history for a data hash
    pub fn get_audit_history(&self, data_hash: &str) -> AuditHistory {
        // Get generation record
        let generation = self.generations.get(data_hash).cloned();

        // Find all verifications related to this data hash
        let verifications: Vec<VerificationRecord> = self.verifications
            .values()
            .flatten()
            .filter(|v| v.data_hash == data_hash)
            .cloned()
            .collect();

        // Find consensus record
        let consensus = self.consensus_records
            .values()
            .find(|c| c.data_hash == data_hash)
            .cloned();

        // Get compliance records
        let compliance = self.compliance_records
            .get(data_hash)
            .cloned()
            .unwrap_or_default();

        AuditHistory {
            data_hash: data_hash.to_string(),
            generation,
            verifications,
            consensus,
            compliance,
            query_timestamp: Utc::now().to_rfc3339(),
        }
    }

    /// Verify integrity by comparing stored vs expected score
    pub fn verify_integrity(
        &self,
        verification_id: &str,
        expected_score: f64,
        tolerance: f64,
    ) -> Result<bool, ChainCodeError> {
        let consensus = self.query_consensus(verification_id)?;
        let diff = (consensus.consensus_score - expected_score).abs();
        Ok(diff <= tolerance)
    }

    /// Compute hash for data verification
    pub fn compute_hash(data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        hex::encode(hasher.finalize())
    }
}

impl Default for AuditTrailContract {
    fn default() -> Self {
        Self::new()
    }
}

// ==================== Tests ====================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_generation() {
        let mut contract = AuditTrailContract::new();
        
        let result = contract.log_generation(
            "abc123".to_string(),
            "CTGAN".to_string(),
            HashMap::from([("epochs".to_string(), "100".to_string())]),
            1000,
            10,
            "generator_1".to_string(),
            HashMap::new(),
        );

        assert!(result.is_ok());
        let record = result.unwrap();
        assert_eq!(record.data_hash, "abc123");
        assert_eq!(record.generator_type, "CTGAN");
    }

    #[test]
    fn test_submit_verification() {
        let mut contract = AuditTrailContract::new();
        
        let result = contract.submit_verification(
            "ver_001".to_string(),
            "abc123".to_string(),
            "verifier_1".to_string(),
            85.0,
            80.0,
            75.0,
            HashMap::new(),
        );

        assert!(result.is_ok());
        let record = result.unwrap();
        assert_eq!(record.status, VerificationStatus::Passed);
        assert!(record.overall_score > 70.0);
    }

    #[test]
    fn test_consensus() {
        let mut contract = AuditTrailContract::new();
        
        // Submit multiple verifications
        contract.submit_verification(
            "ver_001".to_string(),
            "abc123".to_string(),
            "verifier_1".to_string(),
            85.0, 80.0, 75.0,
            HashMap::new(),
        ).unwrap();

        contract.submit_verification(
            "ver_001".to_string(),
            "abc123".to_string(),
            "verifier_2".to_string(),
            80.0, 75.0, 70.0,
            HashMap::new(),
        ).unwrap();

        contract.submit_verification(
            "ver_001".to_string(),
            "abc123".to_string(),
            "verifier_3".to_string(),
            90.0, 85.0, 80.0,
            HashMap::new(),
        ).unwrap();

        // Record consensus
        let result = contract.record_consensus(
            "ver_001".to_string(),
            "abc123".to_string(),
            70.0,
        );

        assert!(result.is_ok());
        let consensus = result.unwrap();
        assert_eq!(consensus.final_status, "APPROVED");
        assert_eq!(consensus.verifier_count, 3);
    }

    #[test]
    fn test_compliance() {
        let mut contract = AuditTrailContract::new();
        
        let result = contract.record_compliance(
            "abc123".to_string(),
            ComplianceFramework::GDPR,
            95.0,
            true,
            vec![],
            "attestor_1".to_string(),
        );

        assert!(result.is_ok());
        
        let query = contract.query_compliance("abc123", &ComplianceFramework::GDPR);
        assert!(query.is_ok());
        assert!(query.unwrap().is_compliant);
    }

    #[test]
    fn test_audit_history() {
        let mut contract = AuditTrailContract::new();
        
        // Create a complete audit trail
        contract.log_generation(
            "abc123".to_string(),
            "CTGAN".to_string(),
            HashMap::new(),
            1000, 10,
            "gen_1".to_string(),
            HashMap::new(),
        ).unwrap();

        contract.submit_verification(
            "ver_001".to_string(),
            "abc123".to_string(),
            "verifier_1".to_string(),
            85.0, 80.0, 75.0,
            HashMap::new(),
        ).unwrap();

        contract.record_compliance(
            "abc123".to_string(),
            ComplianceFramework::GDPR,
            95.0,
            true,
            vec![],
            "attestor_1".to_string(),
        ).unwrap();

        let history = contract.get_audit_history("abc123");
        
        assert!(history.generation.is_some());
        assert_eq!(history.verifications.len(), 1);
        assert_eq!(history.compliance.len(), 1);
    }
}
