"""
Metrics Evaluator Module
Consolidated evaluation metrics for synthetic data quality assessment.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from scipy import stats
from scipy.spatial.distance import cdist
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import (
    accuracy_score, f1_score, roc_auc_score,
    precision_score, recall_score, mean_squared_error
)
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')


class MetricsEvaluator:
    """
    Comprehensive metrics evaluator for synthetic data.
    
    Provides unified interface for:
    - Privacy metrics
    - Utility metrics
    - Fairness metrics
    - Statistical metrics
    """
    
    def __init__(self, real_data: pd.DataFrame, synthetic_data: pd.DataFrame):
        """
        Initialize evaluator with real and synthetic data.
        
        Args:
            real_data: Original real dataset
            synthetic_data: Generated synthetic dataset
        """
        self.real_data = real_data.copy()
        self.synthetic_data = synthetic_data.copy()
        
        # Align columns
        common_cols = list(set(real_data.columns) & set(synthetic_data.columns))
        self.real_data = self.real_data[common_cols]
        self.synthetic_data = self.synthetic_data[common_cols]
        
        # Identify column types
        self.numerical_cols = self.real_data.select_dtypes(include=[np.number]).columns.tolist()
        self.categorical_cols = self.real_data.select_dtypes(exclude=[np.number]).columns.tolist()
        
        # Cache preprocessed data
        self._real_encoded = None
        self._syn_encoded = None
    
    def _encode_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Encode data for numerical computations."""
        if self._real_encoded is not None:
            return self._real_encoded, self._syn_encoded
        
        real_encoded = self.real_data.copy()
        syn_encoded = self.synthetic_data.copy()
        
        # Encode categorical columns
        for col in self.categorical_cols:
            le = LabelEncoder()
            combined = pd.concat([real_encoded[col], syn_encoded[col]]).astype(str)
            le.fit(combined)
            real_encoded[col] = le.transform(real_encoded[col].astype(str))
            syn_encoded[col] = le.transform(syn_encoded[col].astype(str))
        
        # Scale numerical columns
        scaler = StandardScaler()
        if self.numerical_cols:
            combined_num = pd.concat([
                real_encoded[self.numerical_cols], 
                syn_encoded[self.numerical_cols]
            ])
            scaler.fit(combined_num)
            real_encoded[self.numerical_cols] = scaler.transform(real_encoded[self.numerical_cols])
            syn_encoded[self.numerical_cols] = scaler.transform(syn_encoded[self.numerical_cols])
        
        self._real_encoded = real_encoded.values
        self._syn_encoded = syn_encoded.values
        
        return self._real_encoded, self._syn_encoded
    
    # ==================== Privacy Metrics ====================
    
    def compute_dcr(self, sample_size: int = 1000) -> Dict[str, float]:
        """
        Compute Distance to Closest Record (DCR).
        
        Higher DCR indicates better privacy (synthetic records are further from real).
        
        Args:
            sample_size: Number of samples to use (for efficiency)
            
        Returns:
            DCR metrics
        """
        real_enc, syn_enc = self._encode_data()
        
        # Sample for efficiency
        if len(syn_enc) > sample_size:
            indices = np.random.choice(len(syn_enc), sample_size, replace=False)
            syn_sample = syn_enc[indices]
        else:
            syn_sample = syn_enc
        
        if len(real_enc) > sample_size:
            indices = np.random.choice(len(real_enc), sample_size, replace=False)
            real_sample = real_enc[indices]
        else:
            real_sample = real_enc
        
        # Compute pairwise distances
        distances = cdist(syn_sample, real_sample, metric='euclidean')
        min_distances = np.min(distances, axis=1)
        
        return {
            'mean_dcr': float(np.mean(min_distances)),
            'median_dcr': float(np.median(min_distances)),
            'min_dcr': float(np.min(min_distances)),
            'max_dcr': float(np.max(min_distances)),
            'std_dcr': float(np.std(min_distances)),
            'dcr_score': float(min(100, np.mean(min_distances) * 100))  # Normalized 0-100
        }
    
    def compute_k_anonymity(self, quasi_identifiers: List[str] = None) -> Dict[str, Any]:
        """
        Compute k-anonymity of synthetic data.
        
        Args:
            quasi_identifiers: Columns to consider as quasi-identifiers
            
        Returns:
            k-anonymity metrics
        """
        if quasi_identifiers is None:
            quasi_identifiers = self.categorical_cols[:3] if self.categorical_cols else []
        
        if not quasi_identifiers:
            return {'achieved_k': float('inf'), 'k_score': 100.0}
        
        # Group by quasi-identifiers
        qi_cols = [c for c in quasi_identifiers if c in self.synthetic_data.columns]
        if not qi_cols:
            return {'achieved_k': float('inf'), 'k_score': 100.0}
        
        group_sizes = self.synthetic_data.groupby(qi_cols).size()
        min_k = int(group_sizes.min())
        
        return {
            'achieved_k': min_k,
            'avg_group_size': float(group_sizes.mean()),
            'num_groups': len(group_sizes),
            'k_score': float(min(100, min_k * 10))  # k=10+ gets 100
        }
    
    def compute_membership_inference(self, sample_size: int = 1000) -> Dict[str, float]:
        """
        Simulate membership inference attack.
        
        Lower accuracy indicates better privacy (attacker can't distinguish).
        
        Args:
            sample_size: Number of samples per class
            
        Returns:
            MIA metrics
        """
        real_enc, syn_enc = self._encode_data()
        
        # Sample data
        n_real = min(sample_size, len(real_enc))
        n_syn = min(sample_size, len(syn_enc))
        
        real_sample = real_enc[np.random.choice(len(real_enc), n_real, replace=False)]
        syn_sample = syn_enc[np.random.choice(len(syn_enc), n_syn, replace=False)]
        
        # Create labeled dataset
        X = np.vstack([real_sample, syn_sample])
        y = np.array([1] * n_real + [0] * n_syn)
        
        # Split and train
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
        
        clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)
        
        y_pred = clf.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Privacy score: closer to 50% accuracy is better
        privacy_score = 100 - abs(accuracy - 0.5) * 200
        
        return {
            'mia_accuracy': float(accuracy),
            'mia_auc': float(roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])),
            'privacy_score': float(max(0, privacy_score))
        }
    
    # ==================== Utility Metrics ====================
    
    def compute_statistical_similarity(self) -> Dict[str, float]:
        """
        Compute statistical similarity between real and synthetic data.
        
        Returns:
            Statistical similarity metrics
        """
        results = {}
        
        # Numerical column statistics
        if self.numerical_cols:
            mean_diffs = []
            std_diffs = []
            
            for col in self.numerical_cols:
                real_mean = self.real_data[col].mean()
                syn_mean = self.synthetic_data[col].mean()
                real_std = self.real_data[col].std()
                syn_std = self.synthetic_data[col].std()
                
                if real_std > 0:
                    mean_diffs.append(abs(real_mean - syn_mean) / real_std)
                    std_diffs.append(abs(real_std - syn_std) / real_std)
            
            results['mean_diff'] = float(np.mean(mean_diffs)) if mean_diffs else 0.0
            results['std_diff'] = float(np.mean(std_diffs)) if std_diffs else 0.0
        
        # Categorical column distribution
        if self.categorical_cols:
            tv_distances = []
            for col in self.categorical_cols:
                real_dist = self.real_data[col].value_counts(normalize=True)
                syn_dist = self.synthetic_data[col].value_counts(normalize=True)
                
                # Align indices
                all_values = set(real_dist.index) | set(syn_dist.index)
                real_aligned = real_dist.reindex(all_values, fill_value=0)
                syn_aligned = syn_dist.reindex(all_values, fill_value=0)
                
                tv = 0.5 * np.sum(np.abs(real_aligned - syn_aligned))
                tv_distances.append(tv)
            
            results['tv_distance'] = float(np.mean(tv_distances))
        
        # Overall similarity score
        penalties = []
        if 'mean_diff' in results:
            penalties.append(results['mean_diff'])
        if 'std_diff' in results:
            penalties.append(results['std_diff'])
        if 'tv_distance' in results:
            penalties.append(results['tv_distance'])
        
        avg_penalty = np.mean(penalties) if penalties else 0
        results['similarity_score'] = float(max(0, 100 - avg_penalty * 100))
        
        return results
    
    def compute_correlation_preservation(self) -> Dict[str, float]:
        """
        Measure how well correlations are preserved.
        
        Returns:
            Correlation preservation metrics
        """
        if len(self.numerical_cols) < 2:
            return {'correlation_diff': 0.0, 'correlation_score': 100.0}
        
        real_corr = self.real_data[self.numerical_cols].corr()
        syn_corr = self.synthetic_data[self.numerical_cols].corr()
        
        # Compute mean absolute difference
        diff = np.abs(real_corr.values - syn_corr.values)
        mean_diff = np.mean(diff[~np.eye(diff.shape[0], dtype=bool)])
        
        return {
            'correlation_diff': float(mean_diff),
            'correlation_score': float(max(0, 100 - mean_diff * 100))
        }
    
    def compute_ml_efficacy(self, target_column: str, 
                           task: str = 'classification') -> Dict[str, float]:
        """
        Evaluate ML model performance (Train on Synthetic, Test on Real).
        
        Args:
            target_column: Target variable column
            task: 'classification' or 'regression'
            
        Returns:
            ML efficacy metrics
        """
        if target_column not in self.real_data.columns:
            return {'ml_efficacy_score': 0.0, 'error': 'Target column not found'}
        
        # Prepare features
        feature_cols = [c for c in self.numerical_cols if c != target_column]
        
        if not feature_cols:
            return {'ml_efficacy_score': 0.0, 'error': 'No feature columns'}
        
        X_syn = self.synthetic_data[feature_cols].values
        y_syn = self.synthetic_data[target_column].values
        X_real = self.real_data[feature_cols].values
        y_real = self.real_data[target_column].values
        
        # Handle categorical target
        if task == 'classification':
            le = LabelEncoder()
            combined_y = np.concatenate([y_syn.astype(str), y_real.astype(str)])
            le.fit(combined_y)
            y_syn = le.transform(y_syn.astype(str))
            y_real = le.transform(y_real.astype(str))
        
        # Train on synthetic
        try:
            if task == 'classification':
                model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
                model.fit(X_syn, y_syn)
                
                y_pred = model.predict(X_real)
                accuracy = accuracy_score(y_real, y_pred)
                f1 = f1_score(y_real, y_pred, average='weighted')
                
                return {
                    'accuracy': float(accuracy),
                    'f1_score': float(f1),
                    'ml_efficacy_score': float(accuracy * 100)
                }
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
                model.fit(X_syn, y_syn)
                
                y_pred = model.predict(X_real)
                rmse = np.sqrt(mean_squared_error(y_real, y_pred))
                
                # Normalize RMSE
                y_range = np.max(y_real) - np.min(y_real)
                normalized_rmse = rmse / y_range if y_range > 0 else rmse
                
                return {
                    'rmse': float(rmse),
                    'normalized_rmse': float(normalized_rmse),
                    'ml_efficacy_score': float(max(0, 100 - normalized_rmse * 100))
                }
        except Exception as e:
            return {'ml_efficacy_score': 0.0, 'error': str(e)}
    
    # ==================== Fairness Metrics ====================
    
    def compute_demographic_parity(self, protected_attr: str, 
                                   target_column: str) -> Dict[str, float]:
        """
        Compute demographic parity difference.
        
        Args:
            protected_attr: Protected attribute column
            target_column: Target/outcome column
            
        Returns:
            Demographic parity metrics
        """
        if protected_attr not in self.synthetic_data.columns:
            return {'demographic_parity': 1.0, 'dp_score': 0.0}
        
        if target_column not in self.synthetic_data.columns:
            return {'demographic_parity': 1.0, 'dp_score': 0.0}
        
        groups = self.synthetic_data.groupby(protected_attr)[target_column]
        
        # For categorical target, compute positive rate
        if self.synthetic_data[target_column].dtype == 'object':
            positive_value = self.synthetic_data[target_column].mode().iloc[0]
            rates = groups.apply(lambda x: (x == positive_value).mean())
        else:
            rates = groups.mean()
        
        if len(rates) < 2:
            return {'demographic_parity': 0.0, 'dp_score': 100.0}
        
        max_diff = rates.max() - rates.min()
        
        return {
            'demographic_parity': float(max_diff),
            'group_rates': rates.to_dict(),
            'dp_score': float(max(0, 100 - max_diff * 100))
        }
    
    def compute_disparate_impact(self, protected_attr: str,
                                 target_column: str) -> Dict[str, float]:
        """
        Compute disparate impact ratio.
        
        Args:
            protected_attr: Protected attribute column
            target_column: Target/outcome column
            
        Returns:
            Disparate impact metrics
        """
        if protected_attr not in self.synthetic_data.columns:
            return {'disparate_impact': 0.0, 'di_score': 0.0}
        
        if target_column not in self.synthetic_data.columns:
            return {'disparate_impact': 0.0, 'di_score': 0.0}
        
        groups = self.synthetic_data.groupby(protected_attr)[target_column]
        
        # Compute positive rates
        if self.synthetic_data[target_column].dtype == 'object':
            positive_value = self.synthetic_data[target_column].mode().iloc[0]
            rates = groups.apply(lambda x: (x == positive_value).mean())
        else:
            rates = groups.mean()
        
        if len(rates) < 2 or rates.max() == 0:
            return {'disparate_impact': 1.0, 'di_score': 100.0}
        
        di_ratio = rates.min() / rates.max()
        
        # 80% rule: DI should be >= 0.8
        di_score = 100 if di_ratio >= 0.8 else di_ratio * 100 / 0.8
        
        return {
            'disparate_impact': float(di_ratio),
            'passes_80_percent_rule': di_ratio >= 0.8,
            'di_score': float(di_score)
        }
    
    # ==================== Comprehensive Evaluation ====================
    
    def evaluate_all(self, target_column: str = None,
                     protected_attr: str = None,
                     quasi_identifiers: List[str] = None) -> Dict[str, Any]:
        """
        Run all evaluation metrics.
        
        Args:
            target_column: Target column for ML efficacy and fairness
            protected_attr: Protected attribute for fairness metrics
            quasi_identifiers: Columns for k-anonymity
            
        Returns:
            Comprehensive evaluation results
        """
        results = {}
        
        # Privacy metrics
        results['privacy'] = {
            'dcr': self.compute_dcr(),
            'k_anonymity': self.compute_k_anonymity(quasi_identifiers),
            'membership_inference': self.compute_membership_inference()
        }
        
        # Calculate privacy score
        privacy_scores = [
            results['privacy']['dcr']['dcr_score'],
            results['privacy']['k_anonymity']['k_score'],
            results['privacy']['membership_inference']['privacy_score']
        ]
        results['privacy']['overall_score'] = float(np.mean(privacy_scores))
        
        # Utility metrics
        results['utility'] = {
            'statistical_similarity': self.compute_statistical_similarity(),
            'correlation_preservation': self.compute_correlation_preservation()
        }
        
        if target_column:
            task = 'classification' if self.real_data[target_column].dtype == 'object' else 'regression'
            results['utility']['ml_efficacy'] = self.compute_ml_efficacy(target_column, task)
        
        # Calculate utility score
        utility_scores = [
            results['utility']['statistical_similarity']['similarity_score'],
            results['utility']['correlation_preservation']['correlation_score']
        ]
        if 'ml_efficacy' in results['utility']:
            utility_scores.append(results['utility']['ml_efficacy']['ml_efficacy_score'])
        results['utility']['overall_score'] = float(np.mean(utility_scores))
        
        # Fairness metrics
        if protected_attr and target_column:
            results['fairness'] = {
                'demographic_parity': self.compute_demographic_parity(protected_attr, target_column),
                'disparate_impact': self.compute_disparate_impact(protected_attr, target_column)
            }
            
            fairness_scores = [
                results['fairness']['demographic_parity']['dp_score'],
                results['fairness']['disparate_impact']['di_score']
            ]
            results['fairness']['overall_score'] = float(np.mean(fairness_scores))
        
        # Overall score
        overall_scores = [
            results['privacy']['overall_score'],
            results['utility']['overall_score']
        ]
        if 'fairness' in results:
            overall_scores.append(results['fairness']['overall_score'])
        
        results['overall'] = {
            'privacy_score': results['privacy']['overall_score'],
            'utility_score': results['utility']['overall_score'],
            'fairness_score': results.get('fairness', {}).get('overall_score', 100.0),
            'composite_score': float(np.mean(overall_scores))
        }
        
        return results


# Convenience function
def evaluate_synthetic_data(real_data: pd.DataFrame,
                           synthetic_data: pd.DataFrame,
                           target_column: str = None,
                           protected_attr: str = None) -> Dict[str, Any]:
    """
    Evaluate synthetic data quality.
    
    Args:
        real_data: Original dataset
        synthetic_data: Synthetic dataset
        target_column: Target column for ML metrics
        protected_attr: Protected attribute for fairness
        
    Returns:
        Evaluation results
    """
    evaluator = MetricsEvaluator(real_data, synthetic_data)
    return evaluator.evaluate_all(target_column, protected_attr)
