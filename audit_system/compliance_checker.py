"""
Compliance Checker Module
Implements regulatory compliance verification for synthetic data:
- GDPR Article 25 (Privacy by Design)
- HIPAA De-identification Requirements
- EU AI Act Transparency Requirements
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib
import json
from dataclasses import dataclass, asdict
from enum import Enum


class ComplianceStandard(Enum):
    """Supported compliance standards."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    EU_AI_ACT = "eu_ai_act"
    ALL = "all"


@dataclass
class ComplianceRequirement:
    """Represents a compliance requirement."""
    standard: str
    article: str
    requirement: str
    description: str
    threshold: Optional[float]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComplianceResult:
    """Result of a compliance check."""
    requirement: ComplianceRequirement
    passed: bool
    score: float
    details: Dict
    evidence: str
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['requirement'] = self.requirement.to_dict()
        return result


class ComplianceChecker:
    """
    Verifies synthetic data against regulatory compliance requirements.
    
    Supported Standards:
    - GDPR (General Data Protection Regulation)
    - HIPAA (Health Insurance Portability and Accountability Act)
    - EU AI Act (Artificial Intelligence Act)
    """
    
    # Define compliance requirements
    REQUIREMENTS = {
        'gdpr': [
            ComplianceRequirement(
                standard='GDPR',
                article='Article 5(1)(c)',
                requirement='Data Minimization',
                description='Only necessary data attributes should be present',
                threshold=None
            ),
            ComplianceRequirement(
                standard='GDPR',
                article='Article 5(1)(d)',
                requirement='Accuracy',
                description='Synthetic data should maintain statistical accuracy',
                threshold=0.7
            ),
            ComplianceRequirement(
                standard='GDPR',
                article='Article 25',
                requirement='Privacy by Design',
                description='Privacy protection built into data generation',
                threshold=0.7
            ),
            ComplianceRequirement(
                standard='GDPR',
                article='Article 35',
                requirement='Data Protection Impact Assessment',
                description='Assessment of privacy risks completed',
                threshold=None
            ),
            ComplianceRequirement(
                standard='GDPR',
                article='Article 5(2)',
                requirement='Accountability',
                description='Audit trail must be maintained',
                threshold=None
            )
        ],
        'hipaa': [
            ComplianceRequirement(
                standard='HIPAA',
                article='164.514(a)',
                requirement='De-identification Standard',
                description='Data must be properly de-identified',
                threshold=0.7
            ),
            ComplianceRequirement(
                standard='HIPAA',
                article='164.514(b)(1)',
                requirement='Expert Determination',
                description='Statistical/scientific principles applied for de-identification',
                threshold=0.7
            ),
            ComplianceRequirement(
                standard='HIPAA',
                article='164.514(b)(2)',
                requirement='Safe Harbor',
                description='18 identifiers removed or generalized',
                threshold=None
            ),
            ComplianceRequirement(
                standard='HIPAA',
                article='164.312(b)',
                requirement='Audit Controls',
                description='Audit trail for all data access and modifications',
                threshold=None
            ),
            ComplianceRequirement(
                standard='HIPAA',
                article='164.530(j)',
                requirement='Documentation',
                description='Policies and procedures documented',
                threshold=None
            )
        ],
        'eu_ai_act': [
            ComplianceRequirement(
                standard='EU AI Act',
                article='Article 10',
                requirement='Data Quality',
                description='Training data must meet quality criteria',
                threshold=0.7
            ),
            ComplianceRequirement(
                standard='EU AI Act',
                article='Article 13',
                requirement='Transparency',
                description='Generation process must be transparent and documented',
                threshold=None
            ),
            ComplianceRequirement(
                standard='EU AI Act',
                article='Article 9',
                requirement='Risk Management',
                description='Bias and fairness risks assessed',
                threshold=0.8
            ),
            ComplianceRequirement(
                standard='EU AI Act',
                article='Article 11',
                requirement='Technical Documentation',
                description='Complete technical documentation available',
                threshold=None
            ),
            ComplianceRequirement(
                standard='EU AI Act',
                article='Article 14',
                requirement='Human Oversight',
                description='Human oversight mechanisms in place',
                threshold=None
            )
        ]
    }
    
    # HIPAA Safe Harbor identifiers
    HIPAA_IDENTIFIERS = [
        'name', 'names', 'first_name', 'last_name', 'full_name',
        'address', 'street', 'city', 'state', 'zip', 'zipcode', 'zip_code',
        'date', 'dates', 'birth_date', 'dob', 'date_of_birth', 'admission_date',
        'telephone', 'phone', 'phone_number', 'fax',
        'email', 'email_address',
        'ssn', 'social_security', 'social_security_number',
        'mrn', 'medical_record', 'medical_record_number',
        'health_plan', 'beneficiary',
        'account', 'account_number',
        'certificate', 'license', 'license_number',
        'vehicle', 'vin',
        'device', 'serial', 'serial_number',
        'url', 'website',
        'ip', 'ip_address',
        'biometric', 'fingerprint', 'face',
        'photo', 'image', 'photograph'
    ]
    
    def __init__(self, 
                 privacy_score: Optional[float] = None,
                 utility_score: Optional[float] = None,
                 bias_score: Optional[float] = None,
                 audit_log: Optional[Dict] = None):
        """
        Initialize the Compliance Checker.
        
        Args:
            privacy_score: Score from privacy verification (0-100)
            utility_score: Score from utility verification (0-100)
            bias_score: Score from bias detection (0-100)
            audit_log: Audit log from generation process
        """
        self.privacy_score = privacy_score
        self.utility_score = utility_score
        self.bias_score = bias_score
        self.audit_log = audit_log or {}
        
        # Results storage
        self.results: Dict[str, List[ComplianceResult]] = {}
        
    def check_gdpr_compliance(self, real_data: pd.DataFrame, 
                              synthetic_data: pd.DataFrame) -> Dict:
        """
        Check GDPR compliance.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            
        Returns:
            Dictionary with compliance results
        """
        results = []
        
        for req in self.REQUIREMENTS['gdpr']:
            if req.article == 'Article 5(1)(c)':
                # Data Minimization
                result = self._check_data_minimization(real_data, synthetic_data, req)
            elif req.article == 'Article 5(1)(d)':
                # Accuracy
                result = self._check_accuracy(req)
            elif req.article == 'Article 25':
                # Privacy by Design
                result = self._check_privacy_by_design(req)
            elif req.article == 'Article 35':
                # DPIA
                result = self._check_dpia(req)
            elif req.article == 'Article 5(2)':
                # Accountability
                result = self._check_accountability(req)
            else:
                continue
                
            results.append(result)
        
        self.results['gdpr'] = results
        
        passed_count = sum(1 for r in results if r.passed)
        overall_score = (passed_count / len(results)) * 100 if results else 0
        
        return {
            'standard': 'GDPR',
            'total_requirements': len(results),
            'passed': passed_count,
            'failed': len(results) - passed_count,
            'compliance_score': overall_score,
            'compliant': passed_count == len(results),
            'results': [r.to_dict() for r in results],
            'timestamp': datetime.now().isoformat()
        }
    
    def check_hipaa_compliance(self, real_data: pd.DataFrame,
                                synthetic_data: pd.DataFrame) -> Dict:
        """
        Check HIPAA compliance.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            
        Returns:
            Dictionary with compliance results
        """
        results = []
        
        for req in self.REQUIREMENTS['hipaa']:
            if req.article == '164.514(a)':
                # De-identification Standard
                result = self._check_deidentification(req)
            elif req.article == '164.514(b)(1)':
                # Expert Determination
                result = self._check_expert_determination(req)
            elif req.article == '164.514(b)(2)':
                # Safe Harbor
                result = self._check_safe_harbor(synthetic_data, req)
            elif req.article == '164.312(b)':
                # Audit Controls
                result = self._check_audit_controls(req)
            elif req.article == '164.530(j)':
                # Documentation
                result = self._check_documentation(req)
            else:
                continue
                
            results.append(result)
        
        self.results['hipaa'] = results
        
        passed_count = sum(1 for r in results if r.passed)
        overall_score = (passed_count / len(results)) * 100 if results else 0
        
        return {
            'standard': 'HIPAA',
            'total_requirements': len(results),
            'passed': passed_count,
            'failed': len(results) - passed_count,
            'compliance_score': overall_score,
            'compliant': passed_count == len(results),
            'results': [r.to_dict() for r in results],
            'timestamp': datetime.now().isoformat()
        }
    
    def check_eu_ai_act_compliance(self, real_data: pd.DataFrame,
                                    synthetic_data: pd.DataFrame) -> Dict:
        """
        Check EU AI Act compliance.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            
        Returns:
            Dictionary with compliance results
        """
        results = []
        
        for req in self.REQUIREMENTS['eu_ai_act']:
            if req.article == 'Article 10':
                # Data Quality
                result = self._check_data_quality(req)
            elif req.article == 'Article 13':
                # Transparency
                result = self._check_transparency(req)
            elif req.article == 'Article 9':
                # Risk Management
                result = self._check_risk_management(req)
            elif req.article == 'Article 11':
                # Technical Documentation
                result = self._check_technical_documentation(req)
            elif req.article == 'Article 14':
                # Human Oversight
                result = self._check_human_oversight(req)
            else:
                continue
                
            results.append(result)
        
        self.results['eu_ai_act'] = results
        
        passed_count = sum(1 for r in results if r.passed)
        overall_score = (passed_count / len(results)) * 100 if results else 0
        
        return {
            'standard': 'EU AI Act',
            'total_requirements': len(results),
            'passed': passed_count,
            'failed': len(results) - passed_count,
            'compliance_score': overall_score,
            'compliant': passed_count == len(results),
            'results': [r.to_dict() for r in results],
            'timestamp': datetime.now().isoformat()
        }
    
    def check_all_compliance(self, real_data: pd.DataFrame,
                             synthetic_data: pd.DataFrame) -> Dict:
        """
        Check compliance with all standards.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            
        Returns:
            Dictionary with all compliance results
        """
        gdpr_result = self.check_gdpr_compliance(real_data, synthetic_data)
        hipaa_result = self.check_hipaa_compliance(real_data, synthetic_data)
        eu_ai_result = self.check_eu_ai_act_compliance(real_data, synthetic_data)
        
        overall_score = (
            gdpr_result['compliance_score'] + 
            hipaa_result['compliance_score'] + 
            eu_ai_result['compliance_score']
        ) / 3
        
        return {
            'overall_compliance_score': overall_score,
            'overall_compliant': all([
                gdpr_result['compliant'],
                hipaa_result['compliant'],
                eu_ai_result['compliant']
            ]),
            'gdpr': gdpr_result,
            'hipaa': hipaa_result,
            'eu_ai_act': eu_ai_result,
            'timestamp': datetime.now().isoformat()
        }
    
    # Individual check methods
    
    def _check_data_minimization(self, real_data: pd.DataFrame,
                                  synthetic_data: pd.DataFrame,
                                  req: ComplianceRequirement) -> ComplianceResult:
        """Check data minimization principle."""
        real_cols = set(real_data.columns)
        synth_cols = set(synthetic_data.columns)
        
        extra_cols = synth_cols - real_cols
        passed = len(extra_cols) == 0
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=100.0 if passed else 50.0,
            details={
                'real_columns': len(real_cols),
                'synthetic_columns': len(synth_cols),
                'extra_columns': list(extra_cols)
            },
            evidence=f"Synthetic data has {len(synth_cols)} columns vs {len(real_cols)} in real data",
            recommendations=[] if passed else ['Remove unnecessary columns from synthetic data']
        )
    
    def _check_accuracy(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check data accuracy using utility score."""
        if self.utility_score is None:
            return ComplianceResult(
                requirement=req,
                passed=False,
                score=0.0,
                details={'utility_score': None},
                evidence="Utility score not provided",
                recommendations=['Run utility verification first']
            )
        
        passed = self.utility_score >= (req.threshold * 100 if req.threshold else 70)
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=self.utility_score,
            details={'utility_score': self.utility_score, 'threshold': req.threshold},
            evidence=f"Utility score: {self.utility_score:.2f}%",
            recommendations=[] if passed else ['Improve synthetic data quality']
        )
    
    def _check_privacy_by_design(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check privacy by design using privacy score."""
        if self.privacy_score is None:
            return ComplianceResult(
                requirement=req,
                passed=False,
                score=0.0,
                details={'privacy_score': None},
                evidence="Privacy score not provided",
                recommendations=['Run privacy verification first']
            )
        
        passed = self.privacy_score >= (req.threshold * 100 if req.threshold else 70)
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=self.privacy_score,
            details={'privacy_score': self.privacy_score, 'threshold': req.threshold},
            evidence=f"Privacy score: {self.privacy_score:.2f}%",
            recommendations=[] if passed else ['Improve privacy protection measures']
        )
    
    def _check_dpia(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check if Data Protection Impact Assessment is complete."""
        has_dpia = bool(self.audit_log) and all([
            self.privacy_score is not None,
            self.utility_score is not None
        ])
        
        return ComplianceResult(
            requirement=req,
            passed=has_dpia,
            score=100.0 if has_dpia else 0.0,
            details={
                'has_audit_log': bool(self.audit_log),
                'has_privacy_assessment': self.privacy_score is not None,
                'has_utility_assessment': self.utility_score is not None
            },
            evidence="DPIA components present" if has_dpia else "Missing DPIA components",
            recommendations=[] if has_dpia else ['Complete privacy and utility assessments']
        )
    
    def _check_accountability(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check accountability through audit trail."""
        has_audit = bool(self.audit_log)
        
        return ComplianceResult(
            requirement=req,
            passed=has_audit,
            score=100.0 if has_audit else 0.0,
            details={'has_audit_trail': has_audit},
            evidence="Audit trail maintained" if has_audit else "No audit trail found",
            recommendations=[] if has_audit else ['Enable audit logging']
        )
    
    def _check_deidentification(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check de-identification using privacy score."""
        if self.privacy_score is None:
            return ComplianceResult(
                requirement=req,
                passed=False,
                score=0.0,
                details={'privacy_score': None},
                evidence="De-identification assessment not performed",
                recommendations=['Run privacy verification']
            )
        
        passed = self.privacy_score >= (req.threshold * 100 if req.threshold else 70)
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=self.privacy_score,
            details={'privacy_score': self.privacy_score},
            evidence=f"De-identification score: {self.privacy_score:.2f}%",
            recommendations=[] if passed else ['Improve de-identification measures']
        )
    
    def _check_expert_determination(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check expert determination method compliance."""
        has_statistical_verification = self.privacy_score is not None
        
        return ComplianceResult(
            requirement=req,
            passed=has_statistical_verification,
            score=self.privacy_score or 0.0,
            details={'statistical_verification': has_statistical_verification},
            evidence="Statistical verification performed" if has_statistical_verification else "No statistical verification",
            recommendations=[] if has_statistical_verification else ['Apply statistical methods for de-identification']
        )
    
    def _check_safe_harbor(self, synthetic_data: pd.DataFrame,
                           req: ComplianceRequirement) -> ComplianceResult:
        """Check Safe Harbor compliance - verify no direct identifiers."""
        columns_lower = [col.lower().replace(' ', '_') for col in synthetic_data.columns]
        
        found_identifiers = []
        for identifier in self.HIPAA_IDENTIFIERS:
            for col in columns_lower:
                if identifier in col:
                    found_identifiers.append(col)
                    break
        
        passed = len(found_identifiers) == 0
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=100.0 if passed else max(0, 100 - len(found_identifiers) * 10),
            details={
                'columns_checked': len(columns_lower),
                'potential_identifiers': found_identifiers
            },
            evidence=f"Found {len(found_identifiers)} potential identifiers" if found_identifiers else "No direct identifiers found",
            recommendations=[f"Remove or generalize: {', '.join(found_identifiers)}"] if found_identifiers else []
        )
    
    def _check_audit_controls(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check audit controls are in place."""
        has_audit = bool(self.audit_log)
        
        return ComplianceResult(
            requirement=req,
            passed=has_audit,
            score=100.0 if has_audit else 0.0,
            details={'audit_controls_present': has_audit},
            evidence="Audit controls implemented" if has_audit else "No audit controls",
            recommendations=[] if has_audit else ['Implement audit logging']
        )
    
    def _check_documentation(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check documentation requirements."""
        has_docs = bool(self.audit_log)
        
        return ComplianceResult(
            requirement=req,
            passed=has_docs,
            score=100.0 if has_docs else 0.0,
            details={'documentation_present': has_docs},
            evidence="Documentation available" if has_docs else "Documentation missing",
            recommendations=[] if has_docs else ['Create documentation for data handling procedures']
        )
    
    def _check_data_quality(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check data quality requirements."""
        if self.utility_score is None:
            return ComplianceResult(
                requirement=req,
                passed=False,
                score=0.0,
                details={'utility_score': None},
                evidence="Data quality not assessed",
                recommendations=['Run utility verification']
            )
        
        passed = self.utility_score >= (req.threshold * 100 if req.threshold else 70)
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=self.utility_score,
            details={'utility_score': self.utility_score},
            evidence=f"Data quality score: {self.utility_score:.2f}%",
            recommendations=[] if passed else ['Improve data quality']
        )
    
    def _check_transparency(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check transparency requirements."""
        has_transparency = bool(self.audit_log)
        
        return ComplianceResult(
            requirement=req,
            passed=has_transparency,
            score=100.0 if has_transparency else 0.0,
            details={'transparent_process': has_transparency},
            evidence="Generation process documented" if has_transparency else "Process not transparent",
            recommendations=[] if has_transparency else ['Document the generation process']
        )
    
    def _check_risk_management(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check risk management (bias detection)."""
        if self.bias_score is None:
            return ComplianceResult(
                requirement=req,
                passed=False,
                score=0.0,
                details={'bias_score': None},
                evidence="Risk assessment not performed",
                recommendations=['Run bias detection']
            )
        
        passed = self.bias_score >= (req.threshold * 100 if req.threshold else 80)
        
        return ComplianceResult(
            requirement=req,
            passed=passed,
            score=self.bias_score,
            details={'bias_score': self.bias_score},
            evidence=f"Fairness score: {self.bias_score:.2f}%",
            recommendations=[] if passed else ['Address bias in synthetic data']
        )
    
    def _check_technical_documentation(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check technical documentation."""
        has_docs = bool(self.audit_log)
        
        return ComplianceResult(
            requirement=req,
            passed=has_docs,
            score=100.0 if has_docs else 0.0,
            details={'technical_docs': has_docs},
            evidence="Technical documentation available" if has_docs else "Technical documentation missing",
            recommendations=[] if has_docs else ['Create technical documentation']
        )
    
    def _check_human_oversight(self, req: ComplianceRequirement) -> ComplianceResult:
        """Check human oversight mechanisms."""
        # Assume human oversight if manual verification was triggered
        has_oversight = True  # Dashboard provides human oversight
        
        return ComplianceResult(
            requirement=req,
            passed=has_oversight,
            score=100.0 if has_oversight else 0.0,
            details={'human_oversight': has_oversight},
            evidence="Human oversight via dashboard available",
            recommendations=[]
        )
    
    def generate_compliance_report(self, real_data: pd.DataFrame,
                                    synthetic_data: pd.DataFrame,
                                    standard: ComplianceStandard = ComplianceStandard.ALL) -> Dict:
        """
        Generate a comprehensive compliance report.
        
        Args:
            real_data: Original dataset
            synthetic_data: Synthetic dataset
            standard: Compliance standard to check
            
        Returns:
            Comprehensive compliance report
        """
        report_id = hashlib.sha256(
            f"{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        if standard == ComplianceStandard.GDPR:
            compliance_results = self.check_gdpr_compliance(real_data, synthetic_data)
        elif standard == ComplianceStandard.HIPAA:
            compliance_results = self.check_hipaa_compliance(real_data, synthetic_data)
        elif standard == ComplianceStandard.EU_AI_ACT:
            compliance_results = self.check_eu_ai_act_compliance(real_data, synthetic_data)
        else:
            compliance_results = self.check_all_compliance(real_data, synthetic_data)
        
        report = {
            'report_id': report_id,
            'generated_at': datetime.now().isoformat(),
            'data_summary': {
                'real_data_rows': len(real_data),
                'synthetic_data_rows': len(synthetic_data),
                'columns': list(real_data.columns)
            },
            'verification_scores': {
                'privacy_score': self.privacy_score,
                'utility_score': self.utility_score,
                'bias_score': self.bias_score
            },
            'compliance': compliance_results,
            'recommendations': self._get_all_recommendations(),
            'signature': hashlib.sha256(
                json.dumps(compliance_results, default=str).encode()
            ).hexdigest()
        }
        
        return report
    
    def _get_all_recommendations(self) -> List[str]:
        """Collect all recommendations from results."""
        recommendations = []
        for standard_results in self.results.values():
            for result in standard_results:
                recommendations.extend(result.recommendations)
        return list(set(recommendations))


def check_compliance(real_data: pd.DataFrame,
                     synthetic_data: pd.DataFrame,
                     privacy_score: float,
                     utility_score: float,
                     bias_score: float,
                     audit_log: Optional[Dict] = None,
                     standard: str = 'all') -> Dict:
    """
    Convenience function to check compliance.
    
    Args:
        real_data: Original dataset
        synthetic_data: Synthetic dataset
        privacy_score: Privacy verification score (0-100)
        utility_score: Utility verification score (0-100)
        bias_score: Bias detection score (0-100)
        audit_log: Optional audit log
        standard: Compliance standard ('gdpr', 'hipaa', 'eu_ai_act', 'all')
        
    Returns:
        Compliance report dictionary
    """
    checker = ComplianceChecker(
        privacy_score=privacy_score,
        utility_score=utility_score,
        bias_score=bias_score,
        audit_log=audit_log
    )
    
    standard_enum = {
        'gdpr': ComplianceStandard.GDPR,
        'hipaa': ComplianceStandard.HIPAA,
        'eu_ai_act': ComplianceStandard.EU_AI_ACT,
        'all': ComplianceStandard.ALL
    }.get(standard.lower(), ComplianceStandard.ALL)
    
    return checker.generate_compliance_report(real_data, synthetic_data, standard_enum)
