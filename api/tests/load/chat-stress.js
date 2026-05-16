/**
 * K6 Load Test - Chat Streaming Stress Test
 *
 * Focused stress test for the chat streaming endpoint.
 * This is the most resource-intensive endpoint because each request:
 * - Opens short DB sessions before/after streaming and around DB-backed tools
 * - Opens an SSE connection (long-lived HTTP connection)
 * - Triggers LLM API calls (external dependency)
 * - May trigger RAG/vector DB queries
 * - Runs prompt injection scanning
 *
 * Usage:
 *   k6 run --env AUTH_TOKEN=<jwt> --env AGENT_SLUG=<slug> chat-stress.js
 *
 *   # With custom concurrency
 *   k6 run --env AUTH_TOKEN=<jwt> --env AGENT_SLUG=<slug> --env MAX_VUS=50 chat-stress.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { config, headers, randomMessage } from './config.js';

// ─── Custom Metrics ──────────────────────────────────────────────────────────

const chatDuration = new Trend('chat_duration', true);
const chatTTFB = new Trend('chat_ttfb', true); // Time to first byte
const chatSize = new Trend('chat_response_size', true);
const chatErrors = new Counter('chat_errors');
const chatRateLimited = new Counter('chat_rate_limited');
const chatSuccessRate = new Rate('chat_success_rate');
const chatBillingErrors = new Counter('chat_billing_errors');

// ─── Options ─────────────────────────────────────────────────────────────────

const maxVUs = parseInt(__ENV.MAX_VUS || '50');

export const options = {
    scenarios: {
        chat_ramp: {
            executor: 'ramping-vus',
            startVUs: 1,
            stages: [
                { duration: '1m', target: Math.ceil(maxVUs * 0.2) },  // 20% load
                { duration: '2m', target: Math.ceil(maxVUs * 0.5) },  // 50% load
                { duration: '3m', target: maxVUs },                    // 100% load
                { duration: '2m', target: maxVUs },                    // Sustain peak
                { duration: '1m', target: 0 },                        // Ramp down
            ],
        },
    },
    thresholds: {
        chat_duration: ['p(95)<30000'],              // 95th percentile < 30s (streaming)
        chat_ttfb: ['p(95)<5000'],                   // Time to first byte < 5s
        chat_success_rate: ['rate>0.90'],             // 90% success rate
        chat_errors: ['count<50'],                    // Less than 50 total errors
        http_req_failed: ['rate<0.10'],               // Less than 10% failure rate
    },
    insecureSkipTLSVerify: true,
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// ─── Test Execution ──────────────────────────────────────────────────────────

export default function () {
    const payload = JSON.stringify({
        agent_slug: config.agentSlug,
        message: randomMessage(),
        conversation_history: [],
        conversation_id: null,
        attachments: null,
        llm_config_id: null,
    });

    const res = http.post(`${config.baseUrl}/api/v1/agents/chat/stream`, payload, {
        headers,
        tags: { endpoint: 'chat_stream' },
        timeout: '60s',
    });

    // Record metrics
    chatDuration.add(res.timings.duration);
    chatTTFB.add(res.timings.waiting); // TTFB = time server spent processing before first byte
    chatSize.add(res.body ? res.body.length : 0);

    // Handle rate limiting
    if (res.status === 429) {
        chatRateLimited.add(1);
        const retryAfter = parseInt(res.headers['Retry-After'] || '5');
        sleep(retryAfter);
        return;
    }

    // Handle billing errors
    if (res.status === 402) {
        chatBillingErrors.add(1);
        chatSuccessRate.add(false);
        return;
    }

    // Validate response
    const passed = check(res, {
        'status 200': (r) => r.status === 200,
        'is SSE content type': (r) => {
            const ct = r.headers['Content-Type'] || '';
            return ct.includes('text/event-stream');
        },
        'has response body': (r) => r.body && r.body.length > 0,
        'contains SSE events': (r) => {
            return r.body && (r.body.includes('event:') || r.body.includes('data:'));
        },
        'no error events': (r) => {
            // Check that response doesn't contain only error events
            if (!r.body) return false;
            const hasError = r.body.includes('"event_type":"error"');
            const hasContent = r.body.includes('"event_type":"chunk"') || r.body.includes('"event_type":"done"');
            return hasContent || !hasError;
        },
        'security scan passed': (r) => {
            return r.headers['X-Security-Status'] !== 'blocked';
        },
    });

    chatSuccessRate.add(passed);
    if (!passed) chatErrors.add(1);

    // Think time - simulate user reading the response
    sleep(Math.random() * 3 + 1); // 1-4 seconds
}

// ─── Lifecycle ───────────────────────────────────────────────────────────────

export function setup() {
    // Verify auth is configured
    if (!config.authToken) {
        throw new Error('AUTH_TOKEN is required for chat stress test. Set via --env AUTH_TOKEN=<jwt>');
    }

    if (!config.agentSlug) {
        throw new Error('AGENT_SLUG is required. Set via --env AGENT_SLUG=<slug>');
    }

    // Verify server and auth
    const healthRes = http.get(`${config.baseUrl}/health`);
    check(healthRes, {
        'server reachable': (r) => r.status === 200,
    });

    // Verify auth token works
    const authRes = http.get(`${config.baseUrl}/api/v1/agents/`, { headers });
    const authValid = check(authRes, {
        'auth token valid': (r) => r.status === 200,
    });

    if (!authValid) {
        throw new Error('AUTH_TOKEN is invalid or expired. Please provide a valid JWT token.');
    }

    console.log(`Chat Stress Test starting against: ${config.baseUrl}`);
    console.log(`Agent slug: ${config.agentSlug}`);
    console.log(`Max VUs: ${maxVUs}`);
    console.log(`DB pool size: 30 (pool) + 10 (overflow) = 40 max connections`);
    console.log(`Rate limit: 30 req/60s on /v1/chat/`);

    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = ((Date.now() - data.startTime) / 1000).toFixed(1);
    console.log(`\nChat Stress Test completed in ${duration}s`);
    console.log('Key metrics to check:');
    console.log('  - chat_ttfb p(95): Should be < 5s (time to first byte from LLM)');
    console.log('  - chat_duration p(95): Should be < 30s (full stream duration)');
    console.log('  - chat_success_rate: Should be > 90%');
    console.log('  - chat_rate_limited: High count = rate limits are too restrictive');
    console.log('  - chat_billing_errors: Non-zero = credit/billing issues');
}
