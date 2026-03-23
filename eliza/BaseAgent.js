// BaseAgent.js — BaseMetatronAgent
// Core infrastructure for all Metatron fleet agents

'use strict';

const Anthropic = require('@anthropic-ai/sdk');
const https = require('https');
const http = require('http');

let _soulConfig = null;
function getSoulConfig() {
    if (!_soulConfig) _soulConfig = require('../soul-config');
    return _soulConfig;
}

class BaseMetatronAgent {
    constructor(agentConfig) {
        this.config    = agentConfig || {};
        this.name      = (agentConfig && agentConfig.name) || 'UnnamedAgent';
        this.role      = (agentConfig && agentConfig.role) || 'AGENT';
        this.heartbeatInterval = (agentConfig && agentConfig.heartbeatInterval)
            || 3 * 60 * 60 * 1000; // 3 hours default
        this.coherenceScore    = 1.0;
        this._heartbeatTimer   = null;
        this.anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
    }

    // ── Logging ────────────────────────────────────────────────────────────────
    log(msg) {
        console.log(`[${new Date().toISOString()}] [${this.name}] ${msg}`);
    }

    // ── HTTP helper ────────────────────────────────────────────────────────────
    _request(url, method = 'GET', body = null) {
        return new Promise((resolve, reject) => {
            const parsed = new URL(url);
            const lib    = parsed.protocol === 'https:' ? https : http;
            const opts   = {
                hostname: parsed.hostname,
                port:     parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
                path:     parsed.pathname + parsed.search,
                method,
                headers:  { 'Content-Type': 'application/json' },
            };
            const req = lib.request(opts, (res) => {
                let data = '';
                res.on('data', (chunk) => { data += chunk; });
                res.on('end',  () => {
                    try { resolve(JSON.parse(data)); } catch { resolve(data); }
                });
            });
            req.on('error', reject);
            if (body) req.write(JSON.stringify(body));
            req.end();
        });
    }

    // ── Heartbeat (override in subclass to add custom payload) ─────────────────
    async heartbeat() {
        try {
            const { PORTAL_URL } = getSoulConfig();
            await this._request(`${PORTAL_URL}/api/heartbeat`, 'POST', {
                agent:          this.name,
                role:           this.role,
                coherenceScore: this.coherenceScore,
                timestamp:      new Date().toISOString(),
            });
            this.log('Heartbeat sent.');
        } catch (err) {
            this.log(`Heartbeat failed: ${err.message}`);
        }
    }

    // ── Post content to the Metatron portal ────────────────────────────────────
    async moltPost(title, content, submolt = null) {
        try {
            const { PORTAL_URL } = getSoulConfig();
            const payload = { agent: this.name, title, content };
            if (submolt) payload.submolt = submolt;
            const result = await this._request(`${PORTAL_URL}/api/post`, 'POST', payload);
            this.log(`Post submitted: "${title}"`);
            return result;
        } catch (err) {
            this.log(`moltPost failed: ${err.message}`);
            return null;
        }
    }

    // ── Fetch feed from portal ─────────────────────────────────────────────────
    async getFeed(category = 'general', sort = 'new') {
        try {
            const { PORTAL_URL } = getSoulConfig();
            const url    = `${PORTAL_URL}/api/feed?category=${encodeURIComponent(category)}&sort=${encodeURIComponent(sort)}`;
            const result = await this._request(url);
            return Array.isArray(result) ? result : (result.items || []);
        } catch (err) {
            this.log(`getFeed failed: ${err.message}`);
            return [];
        }
    }

    // ── Ask Claude ─────────────────────────────────────────────────────────────
    async ask(prompt) {
        const msg = await this.anthropic.messages.create({
            model:      'claude-opus-4-6',
            max_tokens: 1024,
            messages:   [{ role: 'user', content: prompt }],
        });
        return msg.content[0].text;
    }

    // ── Lifecycle ──────────────────────────────────────────────────────────────
    start() {
        this.log(`Agent starting — heartbeat every ${this.heartbeatInterval / 1000}s`);
        const tick = async () => {
            try { await this.heartbeat(); }
            catch (e) { this.log(`Heartbeat error: ${e.message}`); }
        };
        tick();
        this._heartbeatTimer = setInterval(tick, this.heartbeatInterval);
    }

    stop() {
        if (this._heartbeatTimer) clearInterval(this._heartbeatTimer);
        this.log('Agent stopped.');
    }
}

module.exports = BaseMetatronAgent;
