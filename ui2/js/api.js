/**
 * UI2 API Utilities
 * Shared API communication layer for all pages
 */

const BACKEND_URL = 'http://localhost:5000';

/**
 * Make API call to backend
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {string} endpoint - API endpoint path
 * @param {object} data - Request body for POST/PUT
 * @returns {Promise<object>} - Response data
 */
async function api(method, endpoint, data = null) {
    try {
        const options = {
            method: method,
            headers: { 'Content-Type': 'application/json' }
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        // Build URL with query params for GET
        let url = `${BACKEND_URL}${endpoint}`;
        if (data && method === 'GET') {
            const params = new URLSearchParams(data);
            url += '?' + params.toString();
        }

        const response = await fetch(url, options);
        const result = await response.json();

        return result;
    } catch (error) {
        console.error(`API Error: ${error.message}`);
        return { success: false, message: error.message, error: true };
    }
}

/**
 * Check if backend is connected
 * @returns {Promise<boolean>}
 */
async function checkBackendConnection() {
    const result = await api('GET', '/status');
    return result && result.state !== undefined;
}

/**
 * Connect SMU channel
 * @param {number} channel - 1 or 2
 * @param {boolean} mock - Use mock mode
 */
async function connectSMU(channel, mock = true) {
    return await api('POST', '/smu/connect', { channel, mock });
}

/**
 * Connect relays
 * @param {boolean} mock - Use mock mode
 */
async function connectRelays(mock = true) {
    return await api('POST', '/relays/connect', { mock });
}

/**
 * Disconnect all hardware
 */
async function disconnectAll() {
    await api('POST', '/smu/output', { channel: 1, enabled: false });
    await api('POST', '/smu/output', { channel: 2, enabled: false });
    await api('POST', '/relays/safe-disconnect');
    return { success: true };
}

/**
 * Run a protocol
 * @param {string} protocolId - Protocol identifier
 * @param {object} overrides - Parameter overrides
 */
async function runProtocol(protocolId, overrides = {}) {
    return await api('POST', '/protocol/run', { id: protocolId, overrides });
}

/**
 * Run inline YAML protocol
 * @param {object} yamlContent - Protocol YAML as object
 */
async function runInlineProtocol(yamlContent) {
    return await api('POST', '/protocol/run-inline', { protocol: yamlContent });
}

/**
 * Get protocol list
 */
async function getProtocolList() {
    return await api('GET', '/protocol/list');
}

/**
 * Get protocol content
 * @param {string} protocolId
 */
async function getProtocolContent(protocolId) {
    return await api('GET', `/protocol/get/${encodeURIComponent(protocolId)}`);
}

/**
 * Save protocol
 * @param {string} name - Protocol name
 * @param {object} content - Protocol YAML content
 * @param {string} folder - Folder name
 */
async function saveProtocol(name, content, folder = 'Custom') {
    return await api('POST', '/protocol/save', { name, content, folder });
}

/**
 * Get run status
 */
async function getRunStatus() {
    return await api('GET', '/status');
}

// Export for use in pages
window.UI2 = {
    api,
    BACKEND_URL,
    checkBackendConnection,
    connectSMU,
    connectRelays,
    disconnectAll,
    runProtocol,
    runInlineProtocol,
    getProtocolList,
    getProtocolContent,
    saveProtocol,
    getRunStatus
};
