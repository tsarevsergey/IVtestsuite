/**
 * UI2 Utility Functions
 * Shared utilities for formatting, logging, UI helpers
 */

/**
 * Format current value with appropriate unit
 * @param {number} value - Current in Amps
 * @returns {string} - Formatted string
 */
function formatCurrent(value) {
    if (value === null || value === undefined) return '-- A';
    const abs = Math.abs(value);
    if (abs === 0) return '0 A';
    if (abs < 1e-12) return (value * 1e15).toFixed(2) + ' fA';
    if (abs < 1e-9) return (value * 1e12).toFixed(2) + ' pA';
    if (abs < 1e-6) return (value * 1e9).toFixed(2) + ' nA';
    if (abs < 1e-3) return (value * 1e6).toFixed(2) + ' μA';
    if (abs < 1) return (value * 1e3).toFixed(3) + ' mA';
    return value.toFixed(4) + ' A';
}

/**
 * Format voltage value with appropriate unit
 * @param {number} value - Voltage in Volts
 * @returns {string} - Formatted string
 */
function formatVoltage(value) {
    if (value === null || value === undefined) return '-- V';
    const abs = Math.abs(value);
    if (abs === 0) return '0 V';
    if (abs < 1e-3) return (value * 1e6).toFixed(2) + ' μV';
    if (abs < 1) return (value * 1e3).toFixed(2) + ' mV';
    return value.toFixed(4) + ' V';
}

/**
 * Format irradiance value
 * @param {number} value - Irradiance in W/cm²
 * @returns {string}
 */
function formatIrradiance(value) {
    if (value === null || value === undefined) return '-- W/cm²';
    if (value < 1e-6) return (value * 1e9).toFixed(2) + ' nW/cm²';
    if (value < 1e-3) return (value * 1e6).toFixed(2) + ' μW/cm²';
    if (value < 1) return (value * 1e3).toFixed(2) + ' mW/cm²';
    return value.toFixed(4) + ' W/cm²';
}

/**
 * Format time duration
 * @param {number} seconds
 * @returns {string}
 */
function formatDuration(seconds) {
    if (seconds < 60) return seconds.toFixed(1) + 's';
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(0);
    return `${mins}m ${secs}s`;
}

/**
 * Log message to a log box element
 * @param {string} boxId - Element ID of log box
 * @param {string} message - Message to log
 * @param {string} type - 'info', 'success', 'error', 'warning'
 */
function log(boxId, message, type = 'info') {
    const logBox = document.getElementById(boxId);
    if (!logBox) return;

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logBox.insertBefore(entry, logBox.firstChild);

    // Limit log entries
    while (logBox.children.length > 100) {
        logBox.removeChild(logBox.lastChild);
    }
}

/**
 * Download data as CSV
 * @param {Array} data - Array of objects
 * @param {string} filename - Filename for download
 * @param {Array} columns - Optional column order
 */
function downloadCSV(data, filename, columns = null) {
    if (!data || data.length === 0) {
        alert('No data to export');
        return;
    }

    // Determine columns
    const cols = columns || Object.keys(data[0]);

    // Build CSV
    let csv = cols.join(',') + '\n';
    for (const row of data) {
        const values = cols.map(col => {
            const val = row[col];
            if (typeof val === 'string' && val.includes(',')) {
                return `"${val}"`;
            }
            return val;
        });
        csv += values.join(',') + '\n';
    }

    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

/**
 * Download raw text content
 * @param {string} content - Text content
 * @param {string} filename - Filename
 * @param {string} mimeType - MIME type
 */
function downloadText(content, filename, mimeType = 'text/plain') {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

/**
 * Parse pixel string to array
 * @param {string} pixelStr - e.g. "1,2,3" or "1-4" or "1,3-5"
 * @returns {Array<number>}
 */
function parsePixelString(pixelStr) {
    const pixels = [];
    const parts = pixelStr.split(',').map(p => p.trim());

    for (const part of parts) {
        if (part.includes('-')) {
            const [start, end] = part.split('-').map(Number);
            for (let i = start; i <= end; i++) {
                pixels.push(i);
            }
        } else {
            const num = parseInt(part);
            if (!isNaN(num)) pixels.push(num);
        }
    }

    return [...new Set(pixels)].sort((a, b) => a - b);
}

/**
 * Generate timestamp string for filenames
 * @returns {string} - e.g. "20260203_131500"
 */
function getTimestamp() {
    const now = new Date();
    const pad = n => n.toString().padStart(2, '0');
    return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

/**
 * Deep clone an object
 * @param {object} obj
 * @returns {object}
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Set element visibility
 * @param {string} id - Element ID
 * @param {boolean} visible
 */
function setVisible(id, visible) {
    const el = document.getElementById(id);
    if (el) el.style.display = visible ? '' : 'none';
}

/**
 * Set element disabled state
 * @param {string} id - Element ID
 * @param {boolean} disabled
 */
function setDisabled(id, disabled) {
    const el = document.getElementById(id);
    if (el) el.disabled = disabled;
}

/**
 * Get form values as object
 * @param {string} formId - Form element ID
 * @returns {object}
 */
function getFormValues(formId) {
    const form = document.getElementById(formId);
    if (!form) return {};

    const formData = new FormData(form);
    const values = {};

    for (const [key, value] of formData.entries()) {
        values[key] = value;
    }

    return values;
}

/**
 * Show toast notification
 * @param {string} message
 * @param {string} type - 'info', 'success', 'error'
 * @param {number} duration - Duration in ms
 */
function showToast(message, type = 'info', duration = 3000) {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;display:flex;flex-direction:column-reverse;gap:10px;';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `alert alert-${type}`;
    toast.style.cssText = 'margin-bottom:0.5rem;min-width:250px;animation:slideIn 0.3s;';
    toast.textContent = message;

    container.appendChild(toast);

    // Remove after duration
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Export utilities
window.Utils = {
    formatCurrent,
    formatVoltage,
    formatIrradiance,
    formatDuration,
    log,
    downloadCSV,
    downloadText,
    parsePixelString,
    getTimestamp,
    deepClone,
    setVisible,
    setDisabled,
    getFormValues,
    showToast
};
