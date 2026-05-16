/**
 * K6 Load Test Configuration
 *
 * Environment variables:
 * - BASE_URL: API base URL (default: http://localhost:5001)
 * - AUTH_TOKEN: JWT auth token for authenticated endpoints
 * - AGENT_SLUG: Agent slug to test (default: test-agent)
 * - WIDGET_API_KEY: Widget API key for widget chat tests
 * - KB_ID: Knowledge base ID for search tests
 */

export const config = {
    baseUrl: __ENV.BASE_URL || 'http://localhost:5001',
    authToken: __ENV.AUTH_TOKEN || '',
    agentSlug: __ENV.AGENT_SLUG || __ENV.AGENT_NAME || 'test-agent',
    kbId: __ENV.KB_ID || '',
    agentId: __ENV.AGENT_ID || '',
    widgetApiKey: __ENV.WIDGET_API_KEY || '',
};

export const headers = {
    'Content-Type': 'application/json',
    ...(config.authToken && { 'Authorization': `Bearer ${config.authToken}` }),
};

// Thresholds for pass/fail criteria
// NOTE: Per-endpoint thresholds are more meaningful than general http_req_duration
// because streaming endpoints have inherently longer response times
// NOTE: These thresholds are tuned for local Docker development. For production,
// consider tightening: health<200ms, ready<500ms, list_agents<200ms
export const thresholds = {
    // HTTP request failure rate
    http_req_failed: ['rate<0.05'], // Less than 5% failure rate

    // Per-endpoint thresholds (tuned for local Docker)
    'http_req_duration{endpoint:health}': ['p(95)<2000'],       // Local Docker overhead
    'http_req_duration{endpoint:ready}': ['p(95)<2000'],        // Local Docker overhead
    'http_req_duration{endpoint:list_agents}': ['p(95)<2000'],  // Local Docker overhead
    'http_req_duration{endpoint:chat_stream}': ['p(95)<30000'], // Streaming takes longer
    'http_req_duration{endpoint:widget_chat}': ['p(95)<30000'], // Streaming takes longer
    'http_req_duration{endpoint:kb_search}': ['p(95)<3000'],
};

// Test scenarios
export const scenarios = {
    // Smoke test - minimal load to verify functionality
    smoke: {
        executor: 'constant-vus',
        vus: 1,
        duration: '30s',
    },

    // Load test - normal expected load
    load: {
        executor: 'ramping-vus',
        startVUs: 0,
        stages: [
            { duration: '2m', target: 50 },   // Ramp up to 50 users
            { duration: '5m', target: 50 },   // Stay at 50 users
            { duration: '2m', target: 0 },    // Ramp down
        ],
    },

    // Stress test - find breaking point
    stress: {
        executor: 'ramping-vus',
        startVUs: 0,
        stages: [
            { duration: '2m', target: 50 },   // Ramp up
            { duration: '3m', target: 100 },  // Push to 100
            { duration: '3m', target: 200 },  // Push to 200
            { duration: '3m', target: 300 },  // Push to 300
            { duration: '2m', target: 0 },    // Ramp down
        ],
    },

    // Spike test - sudden traffic surge
    spike: {
        executor: 'ramping-vus',
        startVUs: 0,
        stages: [
            { duration: '1m', target: 10 },   // Baseline
            { duration: '10s', target: 200 }, // Spike!
            { duration: '2m', target: 200 },  // Hold spike
            { duration: '10s', target: 10 },  // Drop
            { duration: '1m', target: 10 },   // Recovery
            { duration: '30s', target: 0 },   // Ramp down
        ],
    },

    // Soak test - extended duration for memory leaks
    soak: {
        executor: 'constant-vus',
        vus: 30,
        duration: '30m',
    },
};

// Test data generators
export function randomMessage() {
    const messages = [
        'Hello, how can you help me today?',
        'What are your capabilities?',
        'Can you explain how this works?',
        'I need help with a task',
        'Tell me about your features',
        'How do I get started?',
        'What can you do for me?',
        'I have a question about the product',
    ];
    return messages[Math.floor(Math.random() * messages.length)];
}

export function randomSearchQuery() {
    const queries = [
        'how to configure',
        'getting started guide',
        'API documentation',
        'troubleshooting errors',
        'best practices',
        'integration guide',
        'security features',
        'performance optimization',
    ];
    return queries[Math.floor(Math.random() * queries.length)];
}
