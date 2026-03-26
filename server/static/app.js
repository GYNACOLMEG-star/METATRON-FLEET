// METATRON-FLEET Command Center — Dashboard JS
// Vanilla ES modules, no dependencies

// ---- State ----
const state = {
  machines: [],
  commands: [],
  selectedMachineId: null,
  metricsHistory: {},   // machine_id -> [{cpu, mem, disk}]
};

// ---- Fleet Socket ----
const FleetSocket = (() => {
  let ws = null;
  let retryDelay = 1000;
  const MAX_DELAY = 30000;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${proto}://${location.host}/ws/fleet`);

    ws.onopen = () => {
      setWsStatus(true);
      retryDelay = 1000;
      // Send periodic pings to keep connection alive
      startPing();
    };

    ws.onclose = () => {
      setWsStatus(false);
      setTimeout(connect, retryDelay);
      retryDelay = Math.min(retryDelay * 2, MAX_DELAY);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        handleEvent(msg.type, msg.data);
      } catch (_) {}
    };
  }

  let pingInterval = null;
  function startPing() {
    clearInterval(pingInterval);
    pingInterval = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 20000);
  }

  function handleEvent(type, data) {
    if (type === 'FLEET_UPDATE') {
      state.machines = data.machines || [];
      MachineGrid.render();
      Sidebar.render();
      Footer.update();
    } else if (type === 'COMMAND_RESULT' || type === 'COMMAND_UPDATE') {
      const cmd = data.command;
      if (!cmd) return;
      const idx = state.commands.findIndex(c => c.id === cmd.id);
      if (idx >= 0) state.commands[idx] = cmd;
      else state.commands.unshift(cmd);
      CommandPanel.renderTable();
      Footer.update();
    }
  }

  return { connect };
})();

// ---- Utility ----
function setWsStatus(connected) {
  const el = document.getElementById('ws-status');
  el.textContent = connected ? '● CONNECTED' : '● DISCONNECTED';
  el.className = 'ws-status ' + (connected ? 'connected' : 'disconnected');
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleTimeString();
}

function pct(val) {
  return val != null ? val.toFixed(1) + '%' : '—';
}

function barClass(val) {
  if (val == null) return '';
  if (val > 90) return 'crit';
  if (val > 70) return 'warn';
  return '';
}

// ---- Sidebar ----
const Sidebar = {
  render() {
    const el = document.getElementById('sidebar-list');
    if (!state.machines.length) {
      el.innerHTML = '<div class="empty-state">No machines registered</div>';
      return;
    }
    el.innerHTML = state.machines.map(m => `
      <div class="machine-item ${state.selectedMachineId === m.id ? 'selected' : ''}"
           onclick="Sidebar.select('${m.id}')">
        <span class="status-dot ${m.status}"></span>
        <div>
          <div class="mname">${esc(m.name)}</div>
          <div class="mhost">${esc(m.hostname || m.ip_address || 'unknown')}</div>
        </div>
      </div>
    `).join('');
  },

  select(id) {
    state.selectedMachineId = id;
    Sidebar.render();
    MetricsPanel.loadAndShow(id);
  }
};
window.Sidebar = Sidebar;

// ---- Machine Grid ----
const MachineGrid = {
  render() {
    const el = document.getElementById('fleet-grid');
    const sel = document.getElementById('machine-select');

    if (!state.machines.length) {
      el.innerHTML = '<div class="empty-state">Waiting for machines to connect...</div>';
      sel.innerHTML = '<option value="">-- Select Machine --</option>';
      return;
    }

    el.innerHTML = state.machines.map(m => `
        <div class="machine-card ${m.status}" onclick="Sidebar.select('${m.id}')">
          <div class="card-name">${esc(m.name)}</div>
          <div class="card-host">${esc(m.hostname || m.ip_address || '—')}</div>
          <div class="card-metrics">
            ${metricRow('CPU', m._cpu)}
            ${metricRow('MEM', m._mem)}
            ${metricRow('DISK', m._disk)}
          </div>
          <div class="card-last-seen">Last seen: ${fmtTime(m.last_seen)}</div>
          <div class="card-actions">
            <button class="btn-reset" onclick="event.stopPropagation(); MachineGrid.resetAgent('${m.id}', '${esc(m.name)}')">Reset Agent</button>
          </div>
        </div>
      `).join('');

    // Preserve current selection when re-rendering
    const prevVal = sel.value;
    sel.innerHTML = '<option value="">-- Select Machine --</option>' +
      state.machines.map(m =>
        `<option value="${m.id}">${esc(m.name)} (${m.status})</option>`
      ).join('');
    if (prevVal) sel.value = prevVal;
  }
,

  async resetAgent(machineId, machineName) {
    if (!confirm(`Remove "${machineName}" so it can re-register fresh?\n\nThe agent will automatically re-connect on its next poll.`)) return;
    try {
      const res = await fetch(`/api/machines/${machineId}`, { method: 'DELETE' });
      if (!res.ok) { alert('Reset failed: ' + res.statusText); return; }
      state.machines = state.machines.filter(m => m.id !== machineId);
      if (state.selectedMachineId === machineId) state.selectedMachineId = null;
      MachineGrid.render();
      Sidebar.render();
      Footer.update();
    } catch (e) {
      alert('Reset failed: ' + e.message);
    }
  }
};

function metricRow(label, val) {
  const w = val != null ? Math.min(val, 100) : 0;
  const cls = barClass(val);
  return `
    <div class="metric-row">
      <span class="metric-label">${label}</span>
      <div class="metric-bar-wrap"><div class="metric-bar ${cls}" style="width:${w}%"></div></div>
      <span class="metric-val">${pct(val)}</span>
    </div>`;
}

// ---- Metrics Panel ----
const MetricsPanel = {
  async loadAndShow(machineId) {
    const machine = state.machines.find(m => m.id === machineId);
    if (!machine) return;

    document.getElementById('metrics-section').style.display = '';
    document.getElementById('metrics-machine-name').textContent = machine.name;

    try {
      const res = await fetch(`/api/machines/${machineId}`);
      const data = await res.json();
      const history = (data.metrics || []).slice(-60);
      state.metricsHistory[machineId] = history;
      this.drawCharts(machineId);
    } catch (_) {}
  },

  drawCharts(machineId) {
    const history = state.metricsHistory[machineId] || [];
    drawSparkline('chart-cpu', history.map(h => h.cpu_percent), '#00c8ff');
    drawSparkline('chart-mem', history.map(h => h.memory_percent), '#7c3aed');
    drawSparkline('chart-disk', history.map(h => h.disk_percent), '#10b981');
  }
};

function drawSparkline(canvasId, values, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.offsetWidth || 400;
  const H = canvas.offsetHeight || 60;
  canvas.width = W;
  canvas.height = H;

  ctx.clearRect(0, 0, W, H);
  if (!values || values.length < 2) {
    ctx.fillStyle = '#e2eaf4';
    ctx.fillRect(0, 0, W, H);
    return;
  }

  ctx.fillStyle = '#f8fafc';
  ctx.fillRect(0, 0, W, H);

  const max = 100;
  const pts = values.map((v, i) => ({
    x: (i / (values.length - 1)) * W,
    y: H - ((v || 0) / max) * (H - 4) - 2,
  }));

  // Fill
  ctx.beginPath();
  ctx.moveTo(pts[0].x, H);
  pts.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.lineTo(pts[pts.length - 1].x, H);
  ctx.closePath();
  ctx.fillStyle = color + '22';
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  pts.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

// ---- Command Panel ----
const CommandPanel = {
  _paused: false,

  togglePause() {
    this._paused = !this._paused;
    const btn = document.getElementById('pause-btn');
    if (this._paused) {
      btn.textContent = '▶ Resume Updates';
      btn.classList.add('paused');
    } else {
      btn.textContent = '⏸ Pause Updates';
      btn.classList.remove('paused');
      this.renderTable();
    }
  },

  async dispatch() {
    const machineId = document.getElementById('machine-select').value;
    const commandText = document.getElementById('cmd-input').value.trim();
    const timeout = parseInt(document.getElementById('timeout-input').value) || 60;

    if (!machineId) { alert('Select a machine first'); return; }
    if (!commandText) { alert('Enter a command'); return; }

    const btn = document.getElementById('dispatch-btn');
    btn.disabled = true;
    btn.textContent = 'Dispatching...';

    try {
      const res = await fetch('/api/commands/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          machine_id: machineId,
          command_text: commandText,
          timeout_seconds: timeout,
          requested_by: 'operator',
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert('Error: ' + (err.detail || res.statusText));
        return;
      }
      const cmd = await res.json();
      state.commands.unshift(cmd);
      CommandPanel.renderTable();
      document.getElementById('cmd-input').value = '';
    } catch (e) {
      alert('Dispatch failed: ' + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Dispatch via OpenClaw';
    }
  },

  renderTable() {
    if (this._paused) return;
    const tbody = document.getElementById('cmd-table-body');
    if (!state.commands.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No commands dispatched yet</td></tr>';
      return;
    }

    tbody.innerHTML = state.commands.slice(0, 100).map(cmd => {
      const machine = state.machines.find(m => m.id === cmd.machine_id);
      const mname = machine ? machine.name : cmd.machine_id.slice(0, 8);
      const outText = cmd.stdout ? esc(cmd.stdout.slice(0, 500)) : '';
      const errText = cmd.stderr ? `<span class="cmd-err">${esc(cmd.stderr.slice(0, 200))}</span>` : '';
      return `
        <tr>
          <td><span class="status-badge ${cmd.status}">${cmd.status}</span></td>
          <td>${esc(mname)}</td>
          <td><span class="cmd-text" title="${esc(cmd.command_text)}">${esc(cmd.command_text)}</span></td>
          <td>
            ${cmd.exit_code != null ? `<span style="color:var(--muted);font-size:10px">exit ${cmd.exit_code}</span> ` : ''}
            <div class="cmd-output">${outText}${errText}</div>
          </td>
          <td style="white-space:nowrap;color:var(--muted)">${fmtTime(cmd.created_at)}</td>
        </tr>
      `;
    }).join('');
  },

  async loadRecent() {
    try {
      const res = await fetch('/api/commands?limit=50');
      state.commands = await res.json();
      CommandPanel.renderTable();
    } catch (_) {}
  }
};
window.CommandPanel = CommandPanel;

// ---- Footer ----
const Footer = {
  update() {
    const online = state.machines.filter(m => m.status === 'online').length;
    document.getElementById('footer-machines').textContent =
      `Machines: ${online} online / ${state.machines.length} total`;
    const pending = state.commands.filter(c => c.status === 'pending' || c.status === 'sent').length;
    document.getElementById('footer-commands').textContent =
      `Commands: ${pending} pending`;
  }
};

// ---- Utils ----
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---- Voice Input ----
const VoiceInput = (() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return { toggle() { alert('Voice input is not supported in this browser. Try Chrome or Edge.'); } };

  const rec = new SR();
  rec.continuous = false;
  rec.interimResults = true;
  rec.lang = 'en-US';

  let active = false;
  let savedText = '';

  rec.onstart = () => {
    active = true;
    savedText = document.getElementById('cmd-input').value;
    const btn = document.getElementById('voice-btn');
    btn.classList.add('listening');
    btn.title = 'Listening\u2026 click to stop';
  };

  rec.onresult = (e) => {
    let interim = '';
    let final = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) final += e.results[i][0].transcript;
      else interim += e.results[i][0].transcript;
    }
    const input = document.getElementById('cmd-input');
    input.value = savedText + final + interim;
    if (final) savedText = savedText + final;
  };

  rec.onerror = (e) => {
    if (e.error !== 'no-speech') console.warn('Voice error:', e.error);
    stop();
  };

  rec.onend = () => stop();

  function stop() {
    active = false;
    const btn = document.getElementById('voice-btn');
    if (btn) {
      btn.classList.remove('listening');
      btn.title = 'Voice input';
    }
  }

  return {
    toggle() {
      if (active) { rec.stop(); }
      else { rec.start(); }
    }
  };
})();
window.VoiceInput = VoiceInput;

// ---- Init ----
async function init() {
  // Load initial fleet state
  try {
    const res = await fetch('/api/machines');
    state.machines = await res.json();
    MachineGrid.render();
    Sidebar.render();
    Footer.update();
  } catch (_) {}

  await CommandPanel.loadRecent();
  FleetSocket.connect();
}

// Auto-pause updates while typing in the command input
document.addEventListener('DOMContentLoaded', () => {
  const cmdInput = document.getElementById('cmd-input');
  if (cmdInput) {
    cmdInput.addEventListener('focus', () => {
      if (!CommandPanel._paused) CommandPanel.togglePause();
    });
    cmdInput.addEventListener('blur', () => {
      if (CommandPanel._paused) CommandPanel.togglePause();
    });
  }
});

init();
