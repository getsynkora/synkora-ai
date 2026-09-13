import assert from 'node:assert/strict';
import test from 'node:test';
import { successfulChatStream } from './sse-checks.mjs';

const event = value => `data: ${JSON.stringify(value)}\n\n`;
test('requires answer text and completion', () => {
    assert.equal(successfulChatStream(event({ type: 'status', content: 'working' })), false);
    assert.equal(successfulChatStream(event({ type: 'chunk', content: 'hello' })), false);
    assert.equal(successfulChatStream(event({ type: 'done' })), false);
    assert.equal(successfulChatStream(event({ type: 'chunk', content: 'hello' }) + event({ type: 'done' })), true);
});
test('rejects application errors even with HTTP success or previous content', () => {
    assert.equal(successfulChatStream(event({ type: 'error', error: 'failed' })), false);
    assert.equal(successfulChatStream(event({ type: 'chunk', content: 'partial' }) + event({ type: 'error' })), false);
    assert.equal(successfulChatStream(event({ type: 'chunk', content: 'partial' }) + event({ type: 'done' }) + event({ type: 'error' })), false);
});
test('rejects malformed events and supports CRLF', () => {
    assert.equal(successfulChatStream('data: {invalid}\n\n'), false);
    assert.equal(successfulChatStream((event({ type: 'chunk', content: 'hello' }) + event({ type: 'done' })).replaceAll('\n', '\r\n')), true);
});
