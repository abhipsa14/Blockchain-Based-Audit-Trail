"""
Tests for Compliance Checker Module
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from audit_system.compliance_checker import (
    ComplianceChecker, 
    ComplianceStandard,
    check_compliance
)


@pytest.fixture
def sample_data():
    """Create sample real and synthetic data for testing."""
    np.random.seed(42)
    n_samples = 100
    
    real_data = pd.DataFrame({
        'age': np.random.randint(18, 80, n_samples),
        'income': np.random.randint(20000, 150000, n_samples),
        'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n_samples),
        'occupation': np.random.choice(['Engineer', 'Doctor', 'Teacher', 'Lawyer'], n_samples)
    })
    
    synthetic_data = pd.DataFrame({
        'age': np.random.randint(18, 80, n_samples),
        'income': np.random.randint(20000, 150000, n_samples),
        'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n_samples),
        'occupation': np.random.choice(['Engineer', 'Doctor', 'Teacher', 'Lawyer'], n_samples)
    })
    
    return real_data, synthetic_data


class TestComplianceChecker:
    """Test suite for ComplianceChecker class."""
    
    def test_initialization(self):
        """Test compliance checker initialization."""
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        assert checker.privacy_score == 85.0
        assert checker.utility_score == 78.0
        assert checker.bias_score == 90.0
        assert checker.audit_log == {'test': 'log'}
    
    def test_gdpr_compliance(self, sample_data):
        """Test GDPR compliance checking."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        results = checker.check_gdpr_compliance(real_data, synthetic_data)
        
        assert 'standard' in results
        assert results['standard'] == 'GDPR'
        assert 'total_requirements' in results
        assert 'passed' in results
        assert 'failed' in results
        assert 'compliance_score' in results
        assert 'compliant' in results
        assert 'results' in results
    
    def test_hipaa_compliance(self, sample_data):
        """Test HIPAA compliance checking."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        results = checker.check_hipaa_compliance(real_data, synthetic_data)
        
        assert results['standard'] == 'HIPAA'
        assert 'total_requirements' in results
        assert 'compliance_score' in results
    
    def test_eu_ai_act_compliance(self, sample_data):
        """Test EU AI Act compliance checking."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        results = checker.check_eu_ai_act_compliance(real_data, synthetic_data)
        
        assert results['standard'] == 'EU AI Act'
        assert 'total_requirements' in results
        assert 'compliance_score' in results
    
    def test_all_compliance(self, sample_data):
        """Test checking all compliance standards."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        results = checker.check_all_compliance(real_data, synthetic_data)
        
        assert 'overall_compliance_score' in results
        assert 'overall_compliant' in results
        assert 'gdpr' in results
        assert 'hipaa' in results
        assert 'eu_ai_act' in results
    
    def test_hipaa_safe_harbor_identifier_detection(self, sample_data):
        """Test that HIPAA Safe Harbor detects identifiers."""
        real_data, synthetic_data = sample_data
        
        # Add columns that should be flagged
        synthetic_data['email'] = 'test@example.com'
        synthetic_data['phone_number'] = '555-1234'
        synthetic_data['ssn'] = '123-45-6789'
        
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        results = checker.check_hipaa_compliance(real_data, synthetic_data)
        
        # Find the Safe Harbor result
        safe_harbor_result = None
        for result in results['results']:
            if result['requirement']['article'] == '164.514(b)(2)':
                safe_harbor_result = result
                break
        
        assert safe_harbor_result is not None
        assert not safe_harbor_result['passed']
        assert len(safe_harbor_result['details']['potential_identifiers']) > 0
    
    def test_compliance_without_scores(self, sample_data):
        """Test compliance checking when verification scores are not provided."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker()
        
        results = checker.check_gdpr_compliance(real_data, synthetic_data)
        
        # Should still run but mark score-dependent checks as failed
        assert 'compliance_score' in results
    
    def test_generate_compliance_report(self, sample_data):
        """Test generating comprehensive compliance report."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker(
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            audit_log={'test': 'log'}
        )
        
        report = checker.generate_compliance_report(
            real_data, 
            synthetic_data,
            standard=ComplianceStandard.ALL
        )
        
        assert 'report_id' in report
        assert 'generated_at' in report
        assert 'data_summary' in report
        assert 'verification_scores' in report
        assert 'compliance' in report
        assert 'recommendations' in report
        assert 'signature' in report
    
    def test_data_minimization_pass(self, sample_data):
        """Test data minimization check when synthetic has same columns."""
        real_data, synthetic_data = sample_data
        
        checker = ComplianceChecker()
        results = checker.check_gdpr_compliance(real_data, synthetic_data)
        
        # Find data minimization result
        minimization_result = None
        for result in results['results']:
            if result['requirement']['article'] == 'Article 5(1)(c)':
                minimization_result = result
                break
        
        assert minimization_result is not None
        assert minimization_result['passed']
    
    def test_data_minimization_fail(self, sample_data):
        """Test data minimization check when synthetic has extra columns."""
        real_data, synthetic_data = sample_data
        
        # Add extra column to synthetic data
        synthetic_data['extra_column'] = 'value'
        
        checker = ComplianceChecker()
        results = checker.check_gdpr_compliance(real_data, synthetic_data)
        
        # Find data minimization result
        minimization_result = None
        for result in results['results']:
            if result['requirement']['article'] == 'Article 5(1)(c)':
                minimization_result = result
                break
        
        assert minimization_result is not None
        assert not minimization_result['passed']


class TestCheckComplianceFunction:
    """Test suite for the convenience function."""
    
    def test_check_compliance_all(self, sample_data):
        """Test check_compliance convenience function with all standards."""
        real_data, synthetic_data = sample_data
        
        result = check_compliance(
            real_data=real_data,
            synthetic_data=synthetic_data,
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            standard='all'
        )
        
        assert 'compliance' in result
        assert 'overall_compliance_score' in result['compliance']
    
    def test_check_compliance_gdpr_only(self, sample_data):
        """Test check_compliance with GDPR only."""
        real_data, synthetic_data = sample_data
        
        result = check_compliance(
            real_data=real_data,
            synthetic_data=synthetic_data,
            privacy_score=85.0,
            utility_score=78.0,
            bias_score=90.0,
            standard='gdpr'
        )
        
        assert 'compliance' in result
        assert result['compliance']['standard'] == 'GDPR'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
