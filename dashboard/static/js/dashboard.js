/**
 * Dashboard JavaScript - Synthetic Data Audit Trail
 */

// Global state
const state = {
    currentTab: 'overview',
    verificationResults: null,
    auditTrail: [],
    isLoading: false
};

// API endpoints
const API = {
    verify: '/api/verify',
    auditTrail: '/api/audit-trail',
    generateSynthetic: '/api/generate',
    blockchainStatus: '/api/blockchain/status',
    metrics: '/api/metrics'
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initFileUpload();
    loadDashboardData();
    setupEventListeners();
});

// Tab navigation
function initTabs() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            switchTab(tabId);
        });
    });
}

function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabId);
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('hidden', content.id !== `${tabId}-tab`);
    });
    
    state.currentTab = tabId;
}

// File upload handling
function initFileUpload() {
    const uploadArea = document.getElementById('file-upload-area');
    const fileInput = document.getElementById('file-input');
    
    if (!uploadArea || !fileInput) return;
    
    // Click to upload
    uploadArea.addEventListener('click', () => fileInput.click());
    
    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

function handleFileSelect(file) {
    if (!file.name.endsWith('.csv')) {
        showAlert('Please upload a CSV file', 'danger');
        return;
    }
    
    const fileInfo = document.getElementById('file-info');
    if (fileInfo) {
        fileInfo.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
        fileInfo.classList.remove('hidden');
    }
    
    state.selectedFile = file;
    
    // Enable verify button
    const verifyBtn = document.getElementById('verify-btn');
    if (verifyBtn) {
        verifyBtn.disabled = false;
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Verification
async function runVerification() {
    if (!state.selectedFile) {
        showAlert('Please select a file first', 'warning');
        return;
    }
    
    showLoading('Running verification...');
    
    const formData = new FormData();
    formData.append('file', state.selectedFile);
    formData.append('threshold', document.getElementById('threshold-input')?.value || 70);
    
    try {
        const response = await fetch(API.verify, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Verification failed');
        }
        
        const results = await response.json();
        state.verificationResults = results;
        
        displayVerificationResults(results);
        showAlert('Verification completed successfully', 'success');
    } catch (error) {
        console.error('Verification error:', error);
        showAlert('Verification failed: ' + error.message, 'danger');
    } finally {
        hideLoading();
    }
}

function displayVerificationResults(results) {
    // Update score gauges
    updateScoreGauge('privacy-gauge', results.privacy_score || 0);
    updateScoreGauge('utility-gauge', results.utility_score || 0);
    updateScoreGauge('fairness-gauge', results.fairness_score || 0);
    updateScoreGauge('overall-gauge', results.overall_score || 0);
    
    // Update status badge
    const statusBadge = document.getElementById('verification-status');
    if (statusBadge) {
        const status = results.status || 'PENDING';
        statusBadge.textContent = status;
        statusBadge.className = `badge badge-${status === 'APPROVED' ? 'success' : status === 'REJECTED' ? 'danger' : 'warning'}`;
    }
    
    // Update details table
    updateDetailsTable(results);
    
    // Show results section
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.classList.remove('hidden');
    }
}

function updateScoreGauge(gaugeId, score) {
    const gauge = document.getElementById(gaugeId);
    if (!gauge) return;
    
    const scoreElement = gauge.querySelector('.gauge-score');
    const valueCircle = gauge.querySelector('.gauge-value');
    
    if (scoreElement) {
        scoreElement.textContent = Math.round(score);
    }
    
    if (valueCircle) {
        const circumference = 2 * Math.PI * 45; // radius = 45
        const progress = (score / 100) * circumference;
        valueCircle.style.strokeDasharray = `${progress} ${circumference}`;
        
        // Update color class
        valueCircle.classList.remove('excellent', 'good', 'warning', 'danger');
        if (score >= 80) valueCircle.classList.add('excellent');
        else if (score >= 60) valueCircle.classList.add('good');
        else if (score >= 40) valueCircle.classList.add('warning');
        else valueCircle.classList.add('danger');
    }
}

function updateDetailsTable(results) {
    const tbody = document.getElementById('metrics-tbody');
    if (!tbody) return;
    
    const metrics = [
        { name: 'DCR Score', value: results.dcr_score, category: 'Privacy' },
        { name: 'K-Anonymity', value: results.k_anonymity, category: 'Privacy' },
        { name: 'MIA Score', value: results.mia_score, category: 'Privacy' },
        { name: 'Statistical Similarity', value: results.statistical_similarity, category: 'Utility' },
        { name: 'Correlation Preservation', value: results.correlation_preservation, category: 'Utility' },
        { name: 'ML Efficacy', value: results.ml_efficacy, category: 'Utility' },
        { name: 'Demographic Parity', value: results.demographic_parity, category: 'Fairness' },
        { name: 'Disparate Impact', value: results.disparate_impact, category: 'Fairness' }
    ];
    
    tbody.innerHTML = metrics.map(m => `
        <tr>
            <td>${m.name}</td>
            <td><span class="badge badge-info">${m.category}</span></td>
            <td>${m.value !== undefined ? m.value.toFixed(2) : 'N/A'}</td>
            <td>
                <div class="progress-bar">
                    <div class="progress-value ${getScoreClass(m.value)}" 
                         style="width: ${m.value || 0}%"></div>
                </div>
            </td>
        </tr>
    `).join('');
}

function getScoreClass(score) {
    if (score >= 80) return 'excellent';
    if (score >= 60) return 'good';
    if (score >= 40) return 'warning';
    return 'danger';
}

// Audit Trail
async function loadAuditTrail() {
    try {
        const response = await fetch(API.auditTrail);
        if (response.ok) {
            const data = await response.json();
            state.auditTrail = data.entries || [];
            displayAuditTrail(state.auditTrail);
        }
    } catch (error) {
        console.error('Failed to load audit trail:', error);
    }
}

function displayAuditTrail(entries) {
    const timeline = document.getElementById('audit-timeline');
    if (!timeline) return;
    
    if (entries.length === 0) {
        timeline.innerHTML = '<p class="text-center text-secondary">No audit entries found</p>';
        return;
    }
    
    timeline.innerHTML = entries.map(entry => `
        <div class="timeline-item">
            <div class="timeline-content">
                <div class="timeline-title">${entry.entry_type}</div>
                <div class="timeline-time">${formatDate(entry.timestamp)}</div>
                <p class="mt-2">${entry.description || 'No description'}</p>
                ${entry.data_hash ? `<code class="mt-2">${entry.data_hash.substring(0, 16)}...</code>` : ''}
            </div>
        </div>
    `).join('');
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Dashboard data
async function loadDashboardData() {
    try {
        // Load blockchain status
        const statusResponse = await fetch(API.blockchainStatus);
        if (statusResponse.ok) {
            const status = await statusResponse.json();
            updateBlockchainStatus(status);
        }
        
        // Load recent metrics
        const metricsResponse = await fetch(API.metrics);
        if (metricsResponse.ok) {
            const metrics = await metricsResponse.json();
            updateDashboardMetrics(metrics);
        }
        
        // Load audit trail
        await loadAuditTrail();
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

function updateBlockchainStatus(status) {
    const modeElement = document.getElementById('blockchain-mode');
    const statusElement = document.getElementById('blockchain-status');
    const entriesElement = document.getElementById('blockchain-entries');
    
    if (modeElement) modeElement.textContent = status.mode || 'Simulation';
    if (statusElement) {
        statusElement.textContent = status.connected ? 'Connected' : 'Disconnected';
        statusElement.className = `badge badge-${status.connected ? 'success' : 'danger'}`;
    }
    if (entriesElement) entriesElement.textContent = status.total_entries || 0;
}

function updateDashboardMetrics(metrics) {
    const statsContainer = document.getElementById('stats-container');
    if (!statsContainer || !metrics) return;
    
    // Update stat cards with actual data
    document.querySelectorAll('.stat-value').forEach(el => {
        const statType = el.dataset.stat;
        if (statType && metrics[statType] !== undefined) {
            el.textContent = typeof metrics[statType] === 'number' 
                ? metrics[statType].toFixed(1) 
                : metrics[statType];
        }
    });
}

// Event listeners
function setupEventListeners() {
    // Verify button
    const verifyBtn = document.getElementById('verify-btn');
    if (verifyBtn) {
        verifyBtn.addEventListener('click', runVerification);
    }
    
    // Generate synthetic button
    const generateBtn = document.getElementById('generate-btn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateSyntheticData);
    }
    
    // Download report button
    const downloadBtn = document.getElementById('download-report-btn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', downloadReport);
    }
    
    // Refresh audit trail
    const refreshBtn = document.getElementById('refresh-audit-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadAuditTrail);
    }
}

// Synthetic data generation
async function generateSyntheticData() {
    if (!state.selectedFile) {
        showAlert('Please select a real data file first', 'warning');
        return;
    }
    
    showLoading('Generating synthetic data...');
    
    const formData = new FormData();
    formData.append('file', state.selectedFile);
    formData.append('num_rows', document.getElementById('num-rows-input')?.value || 1000);
    
    try {
        const response = await fetch(API.generateSynthetic, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Generation failed');
        }
        
        const result = await response.json();
        showAlert('Synthetic data generated successfully', 'success');
        
        // Trigger download
        if (result.download_url) {
            window.location.href = result.download_url;
        }
    } catch (error) {
        console.error('Generation error:', error);
        showAlert('Generation failed: ' + error.message, 'danger');
    } finally {
        hideLoading();
    }
}

// Report download
function downloadReport() {
    if (!state.verificationResults) {
        showAlert('No verification results to download', 'warning');
        return;
    }
    
    const report = {
        timestamp: new Date().toISOString(),
        results: state.verificationResults,
        audit_trail: state.auditTrail
    };
    
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `verification_report_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// UI helpers
function showLoading(message = 'Loading...') {
    state.isLoading = true;
    let overlay = document.getElementById('loading-overlay');
    
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="spinner"></div>
            <p class="loading-text">${message}</p>
        `;
        document.body.appendChild(overlay);
    } else {
        overlay.querySelector('.loading-text').textContent = message;
        overlay.style.display = 'flex';
    }
}

function hideLoading() {
    state.isLoading = false;
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alert-container') || document.body;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button class="btn-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    alertContainer.prepend(alert);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alert.parentElement) {
            alert.remove();
        }
    }, 5000);
}

// Modal functions
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

// Export functions for use in HTML
window.runVerification = runVerification;
window.generateSyntheticData = generateSyntheticData;
window.downloadReport = downloadReport;
window.openModal = openModal;
window.closeModal = closeModal;
window.switchTab = switchTab;
