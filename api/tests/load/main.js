/**
 * K6 Load Test - High Frequency Endpoints
 *
 * Targets the most frequently called endpoints:
 * 1. GET  /health              - Health check (K8s probes)
 * 2. GET  /ready               - Readiness probe
 * 3. GET  /api/v1/agents/      - List agents (dashboard)
 * 4. POST /api/v1/agents/chat/stream - Chat streaming (core feature)
 * 5. POST /api/v1/widgets/chat - Widget chat (public traffic)
 * 6. POST /api/v1/knowledge-bases/{id}/search - KB search
 *
 * Usage:
 *   # Smoke test (quick sanity check)
 *   k6 run --env SCENARIO=smoke --env BASE_URL=http://localhost:5001 main.js
 *
 *   # Load test with auth
 *   k6 run --env SCENARIO=load --env AUTH_TOKEN=<jwt> main.js
 *
 *   # Stress test
 *   k6 run --env SCENARIO=stress --env AUTH_TOKEN=<jwt> main.js
 *
 *   # Spike test
 *   k6 run --env SCENARIO=spike --env AUTH_TOKEN=<jwt> main.js
 *
 *   # Soak test (memory leaks)
 *   k6 run --env SCENARIO=soak --env AUTH_TOKEN=<jwt> main.js
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { config, headers, thresholds, scenarios, randomMessage, randomSearchQuery } from './config.js';

// ─── Custom Metrics ──────────────────────────────────────────────────────────

const healthDuration = new Trend('health_duration', true);
const listAgentsDuration = new Trend('list_agents_duration', true);
const chatStreamDuration = new Trend('chat_stream_duration', true);
const kbSearchDuration = new Trend('kb_search_duration', true);
const widgetChatDuration = new Trend('widget_chat_duration', true);

const errors = new Counter('errors');
const rateLimited = new Counter('rate_limited');
const successRate = new Rate('success_rate');

// ─── K6 Options ──────────────────────────────────────────────────────────────

const selectedScenario = __ENV.SCENARIO || 'smoke';

export const options = {
    scenarios: {
        default: scenarios[selectedScenario] || scenarios.smoke,
    },
    thresholds,

    // Disable TLS verification for local testing
    insecureSkipTLSVerify: true,

    // Summary output
    summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'],
};

// ─── Test Functions ──────────────────────────────────────────────────────────

function testHealthCheck() {
    const res = http.get(`${config.baseUrl}/health`, {
        tags: { endpoint: 'health' },
    });

    healthDuration.add(res.timings.duration);

    const passed = check(res, {
        'health: status 200': (r) => r.status === 200,
        'health: has status field': (r) => {
            try {
                return JSON.parse(r.body).status === 'healthy';
            } catch {
                return false;
            }
        },
        'health: response < 2s': (r) => r.timings.duration < 2000,
    });

    successRate.add(passed);
    if (!passed) errors.add(1);
}

function testReadinessProbe() {
    const res = http.get(`${config.baseUrl}/ready`, {
        tags: { endpoint: 'ready' },
    });

    const passed = check(res, {
        'ready: status 200': (r) => r.status === 200,
        'ready: db check ok': (r) => {
            try {
                return JSON.parse(r.body).checks.database === 'ok';
            } catch {
                return false;
            }
        },
        'ready: redis check ok': (r) => {
            try {
                return JSON.parse(r.body).checks.redis === 'ok';
            } catch {
                return false;
            }
        },
    });

    successRate.add(passed);
    if (!passed) errors.add(1);
}

function testListAgents() {
    if (!config.authToken) return;

    const res = http.get(`${config.baseUrl}/api/v1/agents/`, {
        headers,
        tags: { endpoint: 'list_agents' },
    });

    listAgentsDuration.add(res.timings.duration);

    if (res.status === 429) {
        rateLimited.add(1);
        return;
    }

    const passed = check(res, {
        'list agents: status 200': (r) => r.status === 200,
        'list agents: response < 2s': (r) => r.timings.duration < 2000,
        'list agents: valid JSON': (r) => {
            try {
                JSON.parse(r.body);
                return true;
            } catch {
                return false;
            }
        },
    });

    successRate.add(passed);
    if (!passed) errors.add(1);
}

function testChatStream() {
    if (!config.authToken || !config.agentSlug) return;

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

    chatStreamDuration.add(res.timings.duration);

    if (res.status === 429) {
        rateLimited.add(1);
        return;
    }

    const passed = check(res, {
        'chat stream: status 200': (r) => r.status === 200,
        'chat stream: is SSE': (r) => {
            const ct = r.headers['Content-Type'] || '';
            return ct.includes('text/event-stream');
        },
        'chat stream: has body': (r) => r.body && r.body.length > 0,
    });

    successRate.add(passed);
    if (!passed) errors.add(1);
}

function testWidgetChat() {
    if (!config.widgetApiKey) return;

    const payload = JSON.stringify({
        message: randomMessage(),
        conversation_id: null,
    });

    const res = http.post(`${config.baseUrl}/api/v1/widgets/chat`, payload, {
        headers: {
            'Content-Type': 'application/json',
            'X-Widget-API-Key': config.widgetApiKey,
        },
        tags: { endpoint: 'widget_chat' },
        timeout: '60s',
    });

    widgetChatDuration.add(res.timings.duration);

    if (res.status === 429) {
        rateLimited.add(1);
        return;
    }

    const passed = check(res, {
        'widget chat: status 200 or 401': (r) => r.status === 200 || r.status === 401,
    });

    successRate.add(passed);
    if (!passed) errors.add(1);
}

function testKnowledgeBaseSearch() {
    if (!config.authToken || !config.kbId) return;

    const payload = JSON.stringify({
        query: randomSearchQuery(),
        top_k: 5,
    });

    const res = http.post(
        `${config.baseUrl}/api/v1/knowledge-bases/${config.kbId}/search`,
        payload,
        {
            headers,
            tags: { endpoint: 'kb_search' },
        }
    );

    kbSearchDuration.add(res.timings.duration);

    if (res.status === 429) {
        rateLimited.add(1);
        return;
    }

    const passed = check(res, {
        'kb search: status 200': (r) => r.status === 200,
        'kb search: response < 2s': (r) => r.timings.duration < 2000,
        'kb search: valid JSON': (r) => {
            try {
                JSON.parse(r.body);
                return true;
            } catch {
                return false;
            }
        },
    });

    successRate.add(passed);
    if (!passed) errors.add(1);
}

// ─── Main Test Execution ─────────────────────────────────────────────────────
// Traffic distribution reflects real-world usage patterns:
//   40% health/ready (K8s probes, monitoring)
//   25% list agents (dashboard loads)
//   20% chat stream (core feature)
//   10% widget chat (public traffic)
//   5%  KB search (RAG queries)

export default function () {
    const rand = Math.random();

    if (rand < 0.25) {
        group('Health Checks', () => {
            testHealthCheck();
            sleep(0.1);
            testReadinessProbe();
        });
    } else if (rand < 0.50) {
        group('List Agents', () => {
            testListAgents();
        });
    } else if (rand < 0.70) {
        group('Chat Stream', () => {
            testChatStream();
        });
    } else if (rand < 0.85) {
        group('Widget Chat', () => {
            testWidgetChat();
        });
    } else {
        group('KB Search', () => {
            testKnowledgeBaseSearch();
        });
    }

    // Think time between requests (simulates real user behavior)
    sleep(Math.random() * 2 + 0.5); // 0.5 - 2.5 seconds
}

// ─── Lifecycle Hooks ─────────────────────────────────────────────────────────

export function setup() {
    // Verify the server is reachable before starting
    const res = http.get(`${config.baseUrl}/health`);
    const passed = check(res, {
        'setup: server is reachable': (r) => r.status === 200,
    });

    if (!passed) {
        throw new Error(`Server not reachable at ${config.baseUrl}`);
    }

    console.log(`Load test starting against: ${config.baseUrl}`);
    console.log(`Scenario: ${selectedScenario}`);
    console.log(`Auth: ${config.authToken ? 'configured' : 'NOT configured (authenticated endpoints will be skipped)'}`);
    console.log(`Agent slug: ${config.agentSlug || 'NOT set'}`);
    console.log(`KB ID: ${config.kbId || 'NOT set (KB search will be skipped)'}`);

    return { startTime: Date.now() };
}

export function teardown(data) {
    const duration = ((Date.now() - data.startTime) / 1000).toFixed(1);
    console.log(`Load test completed in ${duration}s`);
}
