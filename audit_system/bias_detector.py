"""
Bias Detection Module
Implements fairness metrics for synthetic data validation:
- Demographic Parity
- Disparate Impact
- Equal Opportunity Difference
- Statistical Parity Difference
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import confusion_matrix
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
import hashlib
import warnings
warnings.filterwarnings('ignore')


class BiasDetector:
    """
    Detects and measures bias in synthetic data.
    
    Compares fairness metrics between real and synthetic data
    to ensure bias is not amplified or introduced.
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame,
                 protected_attributes: List[str],
                 target_column: Optional[str] = None,
                 favorable_outcome: Optional[Union[str, int]] = None):
        """
        Initialize the Bias Detector.
        
        Args:
            real_data: Original dataset
            synthetic_data: Generated synthetic dataset
            protected_attributes: Columns representing protected groups (e.g., 'sex', 'race')
            target_column: Column representing the outcome/decision
            favorable_outcome: Value representing favorable outcome in target column
        """
        self.real_data = real_data.copy()
        self.synthetic_data = synthetic_data.copy()
        self.protected_attributes = [pa for pa in protected_attributes 
                                     if pa in real_data.columns]
        self.target_column = target_column
        self.favorable_outcome = favorable_outcome
        
        # Results storage
        self.results = {}
        
    def compute_demographic_parity(self) -> Dict:
        """
        Compute Demographic Parity for each protected attribute.
        
        Demographic Parity: All groups should have similar representation.
        Difference should be < 10% for fairness.
        
        Returns:
            Dictionary with demographic parity metrics
        """
        results = {}
        
        for attr in self.protected_attributes:
            # Real data distribution
            real_dist = self.real_data[attr].value_counts(normalize=True)
            synth_dist = self.synthetic_data[attr].value_counts(normalize=True)
            
            # Get all groups
            all_groups = sorted(set(real_dist.index) | set(synth_dist.index))
            
            group_comparisons = {}
            max_diff = 0
            
            for group in all_groups:
                real_prop = real_dist.get(group, 0)
                synth_prop = synth_dist.get(group, 0)
                diff = abs(real_prop - synth_prop)
                
                group_comparisons[str(group)] = {
                    'real_proportion': float(real_prop),
                    'synthetic_proportion': float(synth_prop),
                    'difference': float(diff)
                }
                
                max_diff = max(max_diff, diff)
            
            # Score: Lower difference is better
            score = max(0, 100 - max_diff * 500)
            
            results[attr] = {
                'groups': group_comparisons,
                'max_difference': float(max_diff),
                'score': score,
                'passed': max_diff < 0.1  # 10% threshold
            }
        
        # Overall demographic parity
        avg_score = np.mean([r['score'] for r in results.values()])
        all_passed = all(r['passed'] for r in results.values())
        
        self.results['demographic_parity'] = {
            'by_attribute': results,
            'overall_score': avg_score,
            'passed': all_passed
        }
        
        return self.results['demographic_parity']
    
    def compute_disparate_impact(self) -> Dict:
        """
        Compute Disparate Impact ratio.
        
        Disparate Impact = P(favorable | unprivileged) / P(favorable | privileged)
        Acceptable range: [0.8, 1.25] (80% rule)
        
        Requires target column to be specified.
        
        Returns:
            Dictionary with disparate impact metrics
        """
        if self.target_column is None or self.target_column not in self.real_data.columns:
            return {'error': 'Target column not specified or not found'}
        
        results = {}
        
        for attr in self.protected_attributes:
            # Get groups
            groups = self.real_data[attr].unique()
            
            if len(groups) < 2:
                continue
            
            # Calculate favorable outcome rate for each group
            favorable = self.favorable_outcome
            if favorable is None:
                # Auto-detect: use most common value or 1
                if self.real_data[self.target_column].dtype in ['int64', 'float64']:
                    favorable = 1
                else:
                    favorable = self.real_data[self.target_column].mode()[0]
            
            group_rates_real = {}
            group_rates_synth = {}
            
            for group in groups:
                # Real data
                group_data_real = self.real_data[self.real_data[attr] == group]
                rate_real = (group_data_real[self.target_column] == favorable).mean()
                group_rates_real[str(group)] = float(rate_real)
                
                # Synthetic data
                group_data_synth = self.synthetic_data[self.synthetic_data[attr] == group]
                if len(group_data_synth) > 0:
                    rate_synth = (group_data_synth[self.target_column] == favorable).mean()
                else:
                    rate_synth = 0
                group_rates_synth[str(group)] = float(rate_synth)
            
            # Calculate disparate impact ratios
            max_rate_real = max(group_rates_real.values())
            max_rate_synth = max(group_rates_synth.values()) if group_rates_synth else 0
            
            di_ratios_real = {}
            di_ratios_synth = {}
            
            for group in groups:
                # DI ratio = group_rate / max_rate
                di_real = group_rates_real[str(group)] / max_rate_real if max_rate_real > 0 else 0
                di_synth = group_rates_synth[str(group)] / max_rate_synth if max_rate_synth > 0 else 0
                
                di_ratios_real[str(group)] = float(di_real)
                di_ratios_synth[str(group)] = float(di_synth)
            
            # Check 80% rule
            min_di_real = min(di_ratios_real.values())
            min_di_synth = min(di_ratios_synth.values())
            
            # Compare real vs synthetic DI
            di_change = abs(min_di_real - min_di_synth)
            
            # Score based on synthetic DI being in acceptable range
            if 0.8 <= min_di_synth <= 1.25:
                score = 100
            elif min_di_synth < 0.8:
                score = max(0, min_di_synth / 0.8 * 100)
            else:
                score = max(0, 100 - (min_di_synth - 1.25) * 100)
            
            results[attr] = {
                'group_rates_real': group_rates_real,
                'group_rates_synthetic': group_rates_synth,
                'di_ratios_real': di_ratios_real,
                'di_ratios_synthetic': di_ratios_synth,
                'min_di_real': float(min_di_real),
                'min_di_synthetic': float(min_di_synth),
                'di_change': float(di_change),
                'score': score,
                'passed': 0.8 <= min_di_synth <= 1.25
            }
        
        avg_score = np.mean([r['score'] for r in results.values()]) if results else 0
        all_passed = all(r['passed'] for r in results.values()) if results else True
        
        self.results['disparate_impact'] = {
            'by_attribute': results,
            'favorable_outcome': str(favorable),
            'overall_score': avg_score,
            'passed': all_passed
        }
        
        return self.results['disparate_impact']
    
    def compute_equal_opportunity_difference(self) -> Dict:
        """
        Compute Equal Opportunity Difference.
        
        Measures difference in True Positive Rates across groups.
        EOD should be < 10% for fairness.
        
        Returns:
            Dictionary with equal opportunity metrics
        """
        if self.target_column is None or self.target_column not in self.real_data.columns:
            return {'error': 'Target column not specified or not found'}
        
        results = {}
        
        # Prepare data for ML model
        feature_cols = [col for col in self.real_data.columns 
                       if col != self.target_column and col not in self.protected_attributes]
        
        if not feature_cols:
            return {'error': 'No feature columns available'}
        
        for attr in self.protected_attributes:
            # Train classifier on synthetic, evaluate on real
            try:
                # Encode features
                X_synth = self._encode_features(self.synthetic_data[feature_cols])
                y_synth = self._encode_target(self.synthetic_data[self.target_column])
                
                X_real = self._encode_features(self.real_data[feature_cols])
                y_real = self._encode_target(self.real_data[self.target_column])
                
                # Train model
                clf = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
                clf.fit(X_synth, y_synth)
                
                # Predict on real data
                y_pred = clf.predict(X_real)
                
                # Calculate TPR for each group
                groups = self.real_data[attr].unique()
                tpr_by_group = {}
                
                for group in groups:
                    mask = self.real_data[attr] == group
                    y_true_group = y_real[mask]
                    y_pred_group = y_pred[mask]
                    
                    # True Positive Rate = TP / (TP + FN)
                    true_positives = ((y_true_group == 1) & (y_pred_group == 1)).sum()
                    actual_positives = (y_true_group == 1).sum()
                    
                    tpr = true_positives / actual_positives if actual_positives > 0 else 0
                    tpr_by_group[str(group)] = float(tpr)
                
                # Calculate EOD (max TPR difference between groups)
                tpr_values = list(tpr_by_group.values())
                eod = max(tpr_values) - min(tpr_values) if tpr_values else 0
                
                # Score: Lower EOD is better
                score = max(0, 100 - eod * 500)
                
                results[attr] = {
                    'tpr_by_group': tpr_by_group,
                    'equal_opportunity_difference': float(eod),
                    'score': score,
                    'passed': eod < 0.1
                }
                
            except Exception as e:
                results[attr] = {'error': str(e)}
        
        avg_score = np.mean([r['score'] for r in results.values() 
                           if 'score' in r]) if results else 0
        all_passed = all(r.get('passed', False) for r in results.values()) if results else True
        
        self.results['equal_opportunity'] = {
            'by_attribute': results,
            'overall_score': avg_score,
            'passed': all_passed
        }
        
        return self.results['equal_opportunity']
    
    def _encode_features(self, df: pd.DataFrame) -> np.ndarray:
        """Encode features for ML model."""
        df_encoded = df.copy()
        
        for col in df.columns:
            if df[col].dtype == 'object' or df[col].dtype.name == 'category':
                le = LabelEncoder()
                df_encoded[col] = le.fit_transform(df[col].astype(str))
            df_encoded[col] = df_encoded[col].fillna(0)
        
        return df_encoded.values
    
    def _encode_target(self, series: pd.Series) -> np.ndarray:
        """Encode target variable."""
        if series.dtype == 'object' or series.dtype.name == 'category':
            le = LabelEncoder()
            return le.fit_transform(series.astype(str))
        return series.values
    
    def compute_statistical_parity_difference(self) -> Dict:
        """
        Compute Statistical Parity Difference.
        
        SPD = P(Y=1 | unprivileged) - P(Y=1 | privileged)
        Should be close to 0 for fairness.
        
        Returns:
            Dictionary with statistical parity metrics
        """
        if self.target_column is None:
            return {'error': 'Target column not specified'}
        
        results = {}
        
        favorable = self.favorable_outcome
        if favorable is None:
            if self.real_data[self.target_column].dtype in ['int64', 'float64']:
                favorable = 1
            else:
                favorable = self.real_data[self.target_column].mode()[0]
        
        for attr in self.protected_attributes:
            groups = self.real_data[attr].unique()
            
            if len(groups) < 2:
                continue
            
            # Calculate favorable rates
            rates_real = {}
            rates_synth = {}
            
            for group in groups:
                # Real
                mask_real = self.real_data[attr] == group
                rate_real = (self.real_data.loc[mask_real, self.target_column] == favorable).mean()
                rates_real[str(group)] = float(rate_real)
                
                # Synthetic
                mask_synth = self.synthetic_data[attr] == group
                if mask_synth.sum() > 0:
                    rate_synth = (self.synthetic_data.loc[mask_synth, self.target_column] == favorable).mean()
                else:
                    rate_synth = 0
                rates_synth[str(group)] = float(rate_synth)
            
            # Calculate SPD for all pairs
            spd_pairs = {}
            max_spd = 0
            
            group_list = list(groups)
            for i, g1 in enumerate(group_list):
                for g2 in group_list[i+1:]:
                    spd_real = abs(rates_real[str(g1)] - rates_real[str(g2)])
                    spd_synth = abs(rates_synth[str(g1)] - rates_synth[str(g2)])
                    
                    pair_key = f"{g1}_vs_{g2}"
                    spd_pairs[pair_key] = {
                        'real': float(spd_real),
                        'synthetic': float(spd_synth),
                        'change': float(abs(spd_real - spd_synth))
                    }
                    max_spd = max(max_spd, spd_synth)
            
            # Score: Lower SPD is better
            score = max(0, 100 - max_spd * 500)
            
            results[attr] = {
                'favorable_rates_real': rates_real,
                'favorable_rates_synthetic': rates_synth,
                'spd_pairs': spd_pairs,
                'max_spd': float(max_spd),
                'score': score,
                'passed': max_spd < 0.1
            }
        
        avg_score = np.mean([r['score'] for r in results.values()]) if results else 0
        all_passed = all(r['passed'] for r in results.values()) if results else True
        
        self.results['statistical_parity'] = {
            'by_attribute': results,
            'overall_score': avg_score,
            'passed': all_passed
        }
        
        return self.results['statistical_parity']
    
    def verify_all(self) -> Dict:
        """
        Run all bias detection tests.
        
        Returns:
            Complete verification results with overall bias score
        """
        # Run all tests
        self.compute_demographic_parity()
        self.compute_disparate_impact()
        self.compute_equal_opportunity_difference()
        self.compute_statistical_parity_difference()
        
        # Calculate weighted overall score
        weights = {
            'demographic_parity': 0.25,
            'disparate_impact': 0.25,
            'equal_opportunity': 0.25,
            'statistical_parity': 0.25
        }
        
        overall_score = sum(
            self.results[key]['overall_score'] * weight 
            for key, weight in weights.items()
            if key in self.results and 'overall_score' in self.results[key]
        )
        
        # Overall pass/fail
        all_passed = all(
            self.results[key].get('passed', False) 
            for key in weights.keys() 
            if key in self.results
        )
        
        self.results['overall'] = {
            'fairness_score': overall_score,
            'passed': all_passed,
            'threshold': 70,
            'weights': weights
        }
        
        return self.results
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive bias detection report."""
        if not self.results:
            self.verify_all()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'protected_attributes': self.protected_attributes,
            'target_column': self.target_column,
            'favorable_outcome': str(self.favorable_outcome),
            'verification_results': self.results,
            'summary': {
                'fairness_score': self.results['overall']['fairness_score'],
                'status': 'PASSED' if self.results['overall']['passed'] else 'FAILED',
                'recommendations': self._generate_recommendations()
            }
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on results."""
        recommendations = []
        
        if 'demographic_parity' in self.results:
            if not self.results['demographic_parity']['passed']:
                failed_attrs = [
                    attr for attr, data in self.results['demographic_parity']['by_attribute'].items()
                    if not data['passed']
                ]
                if failed_attrs:
                    recommendations.append(
                        f"Demographic parity violated for: {', '.join(failed_attrs)}. "
                        "Consider rebalancing the training data."
                    )
        
        if 'disparate_impact' in self.results:
            if not self.results['disparate_impact']['passed']:
                recommendations.append(
                    "Disparate impact detected. The 80% rule is violated. "
                    "Consider using fairness-aware generation techniques."
                )
        
        if 'equal_opportunity' in self.results:
            if not self.results['equal_opportunity']['passed']:
                recommendations.append(
                    "Unequal true positive rates across groups detected. "
                    "This may indicate discriminatory patterns in the synthetic data."
                )
        
        if 'statistical_parity' in self.results:
            if not self.results['statistical_parity']['passed']:
                recommendations.append(
                    "Statistical parity difference is too high. "
                    "Favorable outcomes are not evenly distributed across groups."
                )
        
        if not recommendations:
            recommendations.append("All fairness checks passed. No significant bias detected.")
        
        return recommendations


# Convenience function
def detect_bias(real_data: pd.DataFrame, synthetic_data: pd.DataFrame,
                protected_attributes: List[str],
                target_column: Optional[str] = None) -> Dict:
    """
    Quick bias detection function.
    
    Args:
        real_data: Original dataset
        synthetic_data: Generated synthetic dataset
        protected_attributes: List of protected attribute columns
        target_column: Optional target column
        
    Returns:
        Bias detection results
    """
    detector = BiasDetector(real_data, synthetic_data, protected_attributes, target_column)
    return detector.verify_all()
