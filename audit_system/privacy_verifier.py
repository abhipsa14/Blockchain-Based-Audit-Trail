"""
Privacy Verification Module
Implements privacy metrics for synthetic data validation:
- Distance to Closest Record (DCR)
- k-Anonymity
- Membership Inference Test
- Attribute Disclosure Risk
"""

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from typing import Dict, List, Optional, Tuple
import hashlib
import json
from datetime import datetime


class PrivacyVerifier:
    """
    Verifies privacy properties of synthetic data against real data.
    
    Privacy Score Formula:
    Privacy Score = 0.3 * DCR_score + 
                    0.2 * k_anonymity_score + 
                    0.3 * membership_inference_score + 
                    0.2 * attribute_disclosure_score
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame,
                 sensitive_columns: Optional[List[str]] = None,
                 quasi_identifiers: Optional[List[str]] = None):
        """
        Initialize the Privacy Verifier.
        
        Args:
            real_data: Original dataset
            synthetic_data: Generated synthetic dataset
            sensitive_columns: Columns containing sensitive information
            quasi_identifiers: Columns that could be used for re-identification
        """
        self.real_data = real_data.copy()
        self.synthetic_data = synthetic_data.copy()
        self.sensitive_columns = sensitive_columns or []
        self.quasi_identifiers = quasi_identifiers or list(real_data.columns)
        
        # Encode categorical columns for distance calculations
        self.label_encoders = {}
        self.real_encoded = self._encode_data(self.real_data)
        self.synthetic_encoded = self._encode_data(self.synthetic_data)
        
        # Results storage
        self.results = {}
        
    def _encode_data(self, df: pd.DataFrame) -> np.ndarray:
        """Encode categorical columns to numeric for distance calculations."""
        df_encoded = df.copy()
        
        for col in df.columns:
            if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                if col not in self.label_encoders:
                    self.label_encoders[col] = LabelEncoder()
                    self.label_encoders[col].fit(
                        pd.concat([self.real_data[col], self.synthetic_data[col]]).astype(str)
                    )
                df_encoded[col] = self.label_encoders[col].transform(df[col].astype(str))
        
        return df_encoded.values.astype(float)
    
    def compute_dcr(self, sample_size: int = 1000) -> Dict:
        """
        Compute Distance to Closest Record (DCR).
        
        Measures minimum distance from synthetic to real records.
        Higher DCR indicates better privacy (less memorization).
        
        Args:
            sample_size: Number of samples to use for computation
            
        Returns:
            Dictionary with DCR metrics
        """
        # Sample for efficiency
        n_real = min(sample_size, len(self.real_encoded))
        n_synth = min(sample_size, len(self.synthetic_encoded))
        
        real_sample = self.real_encoded[np.random.choice(len(self.real_encoded), n_real, replace=False)]
        synth_sample = self.synthetic_encoded[np.random.choice(len(self.synthetic_encoded), n_synth, replace=False)]
        
        # Normalize data
        real_normalized = (real_sample - real_sample.mean(axis=0)) / (real_sample.std(axis=0) + 1e-10)
        synth_normalized = (synth_sample - real_sample.mean(axis=0)) / (real_sample.std(axis=0) + 1e-10)
        
        # Compute pairwise distances
        distances = cdist(synth_normalized, real_normalized, metric='euclidean')
        
        # Get minimum distance for each synthetic record
        min_distances = distances.min(axis=1)
        
        # DCR statistics
        mean_dcr = float(np.mean(min_distances))
        median_dcr = float(np.median(min_distances))
        min_dcr = float(np.min(min_distances))
        
        # Score: Higher DCR is better (less memorization)
        # Threshold: DCR > 0.1 is considered safe
        dcr_score = min(100, (mean_dcr / 0.1) * 100) if mean_dcr < 0.1 else 100
        
        # Check for exact matches (DCR = 0)
        exact_matches = int(np.sum(min_distances < 1e-6))
        
        self.results['dcr'] = {
            'mean_dcr': mean_dcr,
            'median_dcr': median_dcr,
            'min_dcr': min_dcr,
            'exact_matches': exact_matches,
            'exact_match_rate': exact_matches / n_synth,
            'score': dcr_score,
            'passed': mean_dcr >= 0.05 and exact_matches == 0
        }
        
        return self.results['dcr']
    
    def compute_k_anonymity(self, k_threshold: int = 5) -> Dict:
        """
        Compute k-Anonymity score.
        
        Ensures each record is indistinguishable from k-1 others
        based on quasi-identifiers.
        
        Args:
            k_threshold: Minimum k value for anonymity
            
        Returns:
            Dictionary with k-anonymity metrics
        """
        if not self.quasi_identifiers:
            return {'error': 'No quasi-identifiers specified'}
        
        # Use only quasi-identifiers that exist in the data
        qi_cols = [col for col in self.quasi_identifiers if col in self.synthetic_data.columns]
        
        if not qi_cols:
            return {'error': 'No valid quasi-identifiers found'}
        
        # Group by quasi-identifiers
        groups = self.synthetic_data.groupby(qi_cols).size()
        
        # Calculate k values
        k_values = groups.values
        min_k = int(k_values.min())
        mean_k = float(k_values.mean())
        
        # Records violating k-threshold
        violating_groups = groups[groups < k_threshold]
        violating_records = int(violating_groups.sum()) if len(violating_groups) > 0 else 0
        
        # Score based on minimum k achieved
        k_score = min(100, (min_k / k_threshold) * 100)
        
        self.results['k_anonymity'] = {
            'min_k': min_k,
            'mean_k': mean_k,
            'k_threshold': k_threshold,
            'violating_records': violating_records,
            'violation_rate': violating_records / len(self.synthetic_data),
            'score': k_score,
            'passed': min_k >= k_threshold
        }
        
        return self.results['k_anonymity']
    
    def membership_inference_test(self, test_size: float = 0.3) -> Dict:
        """
        Perform Membership Inference Attack test.
        
        Trains a classifier to distinguish real vs synthetic data.
        If accuracy is close to 50%, synthetic data is private.
        
        Args:
            test_size: Fraction of data to use for testing
            
        Returns:
            Dictionary with membership inference metrics
        """
        # Create labeled dataset
        real_labeled = self.real_encoded.copy()
        synth_labeled = self.synthetic_encoded.copy()
        
        # Balance datasets
        min_size = min(len(real_labeled), len(synth_labeled))
        real_sample = real_labeled[np.random.choice(len(real_labeled), min_size, replace=False)]
        synth_sample = synth_labeled[np.random.choice(len(synth_labeled), min_size, replace=False)]
        
        # Combine and create labels
        X = np.vstack([real_sample, synth_sample])
        y = np.array([1] * min_size + [0] * min_size)  # 1 = real, 0 = synthetic
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Train classifier
        clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)
        
        # Evaluate
        accuracy = clf.score(X_test, y_test)
        
        # Privacy score: closer to 50% accuracy is better
        # Perfect privacy = 50% (random guessing)
        privacy_score = 100 - abs(accuracy - 0.5) * 200
        
        self.results['membership_inference'] = {
            'attack_accuracy': float(accuracy),
            'baseline_accuracy': 0.5,
            'privacy_leakage': float(abs(accuracy - 0.5)),
            'score': max(0, privacy_score),
            'passed': accuracy < 0.6  # Less than 60% accuracy is acceptable
        }
        
        return self.results['membership_inference']
    
    def attribute_disclosure_risk(self) -> Dict:
        """
        Measure attribute disclosure risk.
        
        Compares sensitive attribute distributions between
        real and synthetic data using Total Variation distance.
        
        Returns:
            Dictionary with attribute disclosure metrics
        """
        if not self.sensitive_columns:
            # Use all columns if no sensitive columns specified
            sensitive_cols = list(self.real_data.columns)
        else:
            sensitive_cols = [col for col in self.sensitive_columns 
                           if col in self.real_data.columns]
        
        tv_distances = {}
        
        for col in sensitive_cols:
            # Get value distributions
            real_dist = self.real_data[col].value_counts(normalize=True).to_dict()
            synth_dist = self.synthetic_data[col].value_counts(normalize=True).to_dict()
            
            # Align distributions
            all_values = set(real_dist.keys()) | set(synth_dist.keys())
            real_aligned = pd.Series({v: real_dist.get(v, 0) for v in all_values})
            synth_aligned = pd.Series({v: synth_dist.get(v, 0) for v in all_values})
            
            # Total Variation distance
            tv = 0.5 * np.abs(real_aligned - synth_aligned).sum()
            tv_distances[col] = float(tv)
        
        mean_tv = float(np.mean(list(tv_distances.values())))
        max_tv = float(max(tv_distances.values()))
        
        # Score: Lower TV is generally good, but too low might indicate memorization
        # Ideal: TV between 0.05 and 0.3
        if mean_tv < 0.05:
            score = 70  # Too similar, possible memorization
        elif mean_tv > 0.3:
            score = max(0, 100 - (mean_tv - 0.3) * 200)  # Too different
        else:
            score = 100  # Good range
        
        self.results['attribute_disclosure'] = {
            'tv_distances': tv_distances,
            'mean_tv': mean_tv,
            'max_tv': max_tv,
            'score': score,
            'passed': 0.05 <= mean_tv <= 0.3
        }
        
        return self.results['attribute_disclosure']
    
    def verify_all(self) -> Dict:
        """
        Run all privacy verification tests and compute overall score.
        
        Returns:
            Complete verification results with overall privacy score
        """
        # Run all tests
        self.compute_dcr()
        self.compute_k_anonymity()
        self.membership_inference_test()
        self.attribute_disclosure_risk()
        
        # Calculate weighted overall score
        weights = {
            'dcr': 0.3,
            'k_anonymity': 0.2,
            'membership_inference': 0.3,
            'attribute_disclosure': 0.2
        }
        
        overall_score = sum(
            self.results[key]['score'] * weight 
            for key, weight in weights.items()
            if key in self.results and 'score' in self.results[key]
        )
        
        # Overall pass/fail
        all_passed = all(
            self.results[key].get('passed', False) 
            for key in weights.keys() 
            if key in self.results
        )
        
        self.results['overall'] = {
            'privacy_score': overall_score,
            'passed': all_passed,
            'threshold': 70,
            'weights': weights
        }
        
        return self.results
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive privacy verification report."""
        if not self.results:
            self.verify_all()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'data_hash': self._compute_data_hash(),
            'real_data_shape': list(self.real_data.shape),
            'synthetic_data_shape': list(self.synthetic_data.shape),
            'verification_results': self.results,
            'summary': {
                'privacy_score': self.results['overall']['privacy_score'],
                'status': 'PASSED' if self.results['overall']['passed'] else 'FAILED',
                'recommendations': self._generate_recommendations()
            }
        }
        
        return report
    
    def _compute_data_hash(self) -> str:
        """Compute hash of the synthetic data for audit trail."""
        data_string = self.synthetic_data.to_json()
        return hashlib.sha256(data_string.encode()).hexdigest()
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on verification results."""
        recommendations = []
        
        if 'dcr' in self.results and not self.results['dcr']['passed']:
            if self.results['dcr']['exact_matches'] > 0:
                recommendations.append(
                    "WARNING: Exact matches found between synthetic and real data. "
                    "Consider adding noise or retraining the generator."
                )
            else:
                recommendations.append(
                    "DCR is below threshold. Consider increasing generator diversity."
                )
        
        if 'k_anonymity' in self.results and not self.results['k_anonymity']['passed']:
            recommendations.append(
                f"k-Anonymity violation detected. Minimum k={self.results['k_anonymity']['min_k']}. "
                "Consider generalizing quasi-identifiers."
            )
        
        if 'membership_inference' in self.results and not self.results['membership_inference']['passed']:
            recommendations.append(
                f"High membership inference risk (accuracy={self.results['membership_inference']['attack_accuracy']:.2%}). "
                "Consider using differential privacy during training."
            )
        
        if 'attribute_disclosure' in self.results and not self.results['attribute_disclosure']['passed']:
            recommendations.append(
                "Attribute disclosure risk detected. Review sensitive column distributions."
            )
        
        if not recommendations:
            recommendations.append("All privacy checks passed. Data is safe for release.")
        
        return recommendations


# Convenience function for quick verification
def verify_privacy(real_data: pd.DataFrame, synthetic_data: pd.DataFrame,
                   sensitive_columns: Optional[List[str]] = None) -> Dict:
    """
    Quick privacy verification function.
    
    Args:
        real_data: Original dataset
        synthetic_data: Generated synthetic dataset
        sensitive_columns: Optional list of sensitive columns
        
    Returns:
        Privacy verification results
    """
    verifier = PrivacyVerifier(real_data, synthetic_data, sensitive_columns)
    return verifier.verify_all()
