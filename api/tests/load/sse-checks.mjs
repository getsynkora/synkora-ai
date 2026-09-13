// Shared by k6 and Node contract tests. HTTP 200 alone is not a successful run.
export function successfulChatStream(body) {
    if (typeof body !== 'string') return false;
    let done = false;
    let answer = false;
    for (const frame of body.replace(/\r\n/g, '\n').split('\n\n')) {
        const data = frame.split('\n').filter(line => line.startsWith('data:'))
            .map(line => line.slice(5).trimStart()).join('\n');
        if (!data) continue;
        let event;
        try { event = JSON.parse(data); } catch { return false; }
        if (!event || typeof event.type !== 'string' || event.type === 'error') return false;
        if (event.type === 'done') done = true;
        if (event.type === 'chunk' && typeof event.content === 'string' && event.content.length) answer = true;
    }
    return done && answer;
}
