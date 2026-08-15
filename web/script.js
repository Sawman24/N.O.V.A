// Tab switching
function switchTab(tabId, el) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.sidebar li').forEach(l => l.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    el.classList.add('active');
}

// Backend info
async function loadBackendInfo() {
    try {
        const res = await fetch('/api/backend');
        if (res.ok) {
            const data = await res.json();
            document.getElementById('backend-badge').textContent = `${data.backend} — ${data.model}`;
        } else {
            document.getElementById('backend-badge').textContent = 'Offline';
        }
    } catch (e) {
        document.getElementById('backend-badge').textContent = 'Offline';
    }
}

// ── Chat ──────────────────────────────────────────────────────────────────────

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
}

function appendMessage(role, text) {
    const box = document.getElementById('chat-box');
    const div = document.createElement('div');
    div.className = `chat-msg ${role === 'user' ? 'msg-user' : 'msg-ai'}`;
    div.innerHTML = `<strong>${role === 'user' ? 'You' : 'Nova'}</strong><br>${escapeHtml(text)}`;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function handleChatKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

function getSessionId() {
    let sid = localStorage.getItem('nova_session_id');
    if (!sid) {
        sid = 'session_' + Math.random().toString(36).substring(2, 11);
        localStorage.setItem('nova_session_id', sid);
    }
    return sid;
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('send-btn');
    const message = input.value.trim();
    if (!message) return;

    appendMessage('user', message);
    input.value = '';
    btn.disabled = true;
    btn.textContent = '…';

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: getSessionId() })
        });
        const data = await res.json();
        appendMessage('agent', res.ok ? data.response : `Error: ${data.detail}`);
    } catch (e) {
        appendMessage('agent', 'Failed to reach Nova. Is the server running?');
    }

    btn.disabled = false;
    btn.textContent = 'Send';
    document.getElementById('chat-input').focus();
}

// ── Config ────────────────────────────────────────────────────────────────────

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        if (!res.ok) return;
        const data = await res.json();
        document.getElementById('autonomous_mode').checked = data.autonomous_mode;
        document.getElementById('agent_model').value = data.agent_model;
    } catch (e) {}
}

async function saveConfig() {
    const data = {
        autonomous_mode: document.getElementById('autonomous_mode').checked,
        agent_model: document.getElementById('agent_model').value
    };
    const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    alert(res.ok ? 'Settings saved! Model switched immediately.' : 'Failed to save settings.');
}

// ── Model management ──────────────────────────────────────────────────────────

async function loadInstalledModels() {
    const container = document.getElementById('installed-models');
    try {
        const res = await fetch('/api/models');
        if (!res.ok) return;
        const data = await res.json();
        if (!data.models || data.models.length === 0) {
            container.innerHTML = '<span class="muted-sm">No models installed yet. Pull one below.</span>';
            return;
        }
        container.innerHTML = data.models.map(m =>
            `<div class="model-chip" onclick="document.getElementById('agent_model').value='${m.name}'" title="Click to select">
                <span class="model-name">${m.name}</span>
                <span class="model-size">${m.size_gb}GB</span>
            </div>`
        ).join('');
    } catch (e) {
        container.innerHTML = '<span class="muted-sm">Could not reach Ollama.</span>';
    }
}

async function downloadModel() {
    const modelName = document.getElementById('agent_model').value.trim();
    if (!modelName) return alert('Enter a model name first (e.g. qwen2.5:7b).');

    const btn = document.getElementById('download-btn');
    const progressArea = document.getElementById('pull-progress');
    const progressFill = document.getElementById('progress-fill');
    const statusText = document.getElementById('pull-status-text');

    btn.disabled = true;
    btn.textContent = 'Pulling…';
    progressArea.style.display = 'block';
    progressFill.style.width = '0%';
    statusText.textContent = 'Connecting to Ollama…';

    try {
        const res = await fetch('/api/models/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model_name: modelName })
        });

        if (!res.ok) {
            const err = await res.json();
            statusText.textContent = `Error: ${err.detail}`;
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // hold the last incomplete line

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));

                    if (data.error) {
                        statusText.textContent = `Error: ${data.error}`;
                        progressFill.style.background = '#e17055';
                        return;
                    }

                    if (data.done) {
                        progressFill.style.width = '100%';
                        statusText.textContent = `✓ ${modelName} ready!`;
                        await loadInstalledModels();
                        return;
                    }

                    // Update progress bar if we have byte counts
                    if (data.total && data.completed) {
                        const pct = Math.min(100, Math.round((data.completed / data.total) * 100));
                        progressFill.style.width = `${pct}%`;
                        const dlGB = (data.completed / 1e9).toFixed(2);
                        const totalGB = (data.total / 1e9).toFixed(2);
                        statusText.textContent = `${data.status} — ${dlGB} / ${totalGB} GB (${pct}%)`;
                    } else if (data.status) {
                        statusText.textContent = data.status;
                    }
                } catch (e) { /* skip malformed lines */ }
            }
        }
    } catch (e) {
        statusText.textContent = `Connection lost: ${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Pull';
    }
}

// ── Hugging Face model management ────────────────────────────────────────────

async function loadHFModels() {
    const container = document.getElementById('hf-installed-models');
    try {
        const res = await fetch('/api/hf/models');
        if (!res.ok) return;
        const data = await res.json();
        if (!data.models || data.models.length === 0) {
            container.innerHTML = '<span class="muted-sm">No GGUF models downloaded yet.</span>';
            return;
        }
        container.innerHTML = data.models.map(m =>
            `<div class="model-chip" onclick="selectHFModel('${m.filename}')" title="Click to activate">
                <span class="model-name">${m.filename}</span>
                <span class="model-size">${m.size_gb}GB</span>
            </div>`
        ).join('');
    } catch (e) {
        container.innerHTML = '<span class="muted-sm">Could not load downloaded models.</span>';
    }
}

function selectHFModel(filename) {
    // Populate HF_MODEL_FILE env field if visible, otherwise show a quick tip
    const envField = document.getElementById('env_HF_MODEL_FILE');
    if (envField) {
        envField.value = `models/${filename}`;
        envField.closest('.form-group').scrollIntoView({ behavior: 'smooth' });
    } else {
        alert(`To activate this model:\n1. Set BACKEND=huggingface in the Environment tab.\n2. Set HF_MODEL_FILE=models/${filename}\n3. Restart Nova.`);
    }
}

async function browseHFFiles() {
    const repoId = document.getElementById('hf-repo-id').value.trim();
    if (!repoId) return alert('Enter a Hugging Face repository ID (e.g. bartowski/Qwen2.5-7B-Instruct-GGUF).');

    const btn = document.getElementById('hf-browse-btn');
    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        const res = await fetch(`/api/hf/files?repo_id=${encodeURIComponent(repoId)}`);
        const data = await res.json();

        if (!res.ok) {
            alert(`Error: ${data.detail || 'Could not fetch file list.'}`);
            return;
        }

        if (!data.files || data.files.length === 0) {
            alert('No GGUF files found in this repository.');
            return;
        }

        const select = document.getElementById('hf-file-select');
        select.innerHTML = data.files.map(f => `<option value="${f}">${f}</option>`).join('');
        document.getElementById('hf-file-group').style.display = 'block';
    } catch (e) {
        alert(`Failed to reach server: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Browse';
    }
}

async function downloadHFModel() {
    const repoId = document.getElementById('hf-repo-id').value.trim();
    const filename = document.getElementById('hf-file-select').value;
    if (!repoId || !filename) return;

    const btn = document.getElementById('hf-download-btn');
    const progressArea = document.getElementById('hf-pull-progress');
    const progressFill = document.getElementById('hf-progress-fill');
    const statusText = document.getElementById('hf-pull-status-text');

    btn.disabled = true;
    btn.textContent = 'Downloading...';
    progressArea.style.display = 'block';
    progressFill.style.width = '0%';
    progressFill.style.background = '';
    statusText.textContent = `Connecting to Hugging Face...`;

    try {
        const res = await fetch('/api/hf/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_id: repoId, filename })
        });

        if (!res.ok) {
            const err = await res.json();
            statusText.textContent = `Error: ${err.detail}`;
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const data = JSON.parse(line.slice(6));

                    if (data.error) {
                        statusText.textContent = `Error: ${data.error}`;
                        progressFill.style.background = '#e17055';
                        return;
                    }

                    if (data.done) {
                        progressFill.style.width = '100%';
                        statusText.textContent = `✓ ${data.filename} downloaded!`;
                        await loadHFModels();
                        return;
                    }

                    if (data.total_bytes && data.bytes_downloaded) {
                        const pct = data.pct;
                        progressFill.style.width = `${pct}%`;
                        const dlGB = (data.bytes_downloaded / 1e9).toFixed(2);
                        const totalGB = (data.total_bytes / 1e9).toFixed(2);
                        statusText.textContent = `Downloading ${data.filename} — ${dlGB} / ${totalGB} GB (${pct}%)`;
                    }
                } catch (e) { /* skip malformed lines */ }
            }
        }
    } catch (e) {
        statusText.textContent = `Connection lost: ${e.message}`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Download';
    }
}

// ── Environment ──────────────────────────────────────────────────────────────

const SENSITIVE_KEYS = ['EMAIL_APP_PASSWORD', 'LOCAL_API_KEY'];

const ENV_CATEGORIES = [
    {
        title: '🤖 Model & Backend',
        keys: ['BACKEND', 'AGENT_MODEL', 'BUILDER_MODEL', 'OLLAMA_BASE_URL', 'LOCAL_BASE_URL', 'LOCAL_API_KEY']
    },
    {
        title: '🤗 Hugging Face Backend',
        keys: ['HF_TOKEN', 'HF_MODEL_FILE', 'N_GPU_LAYERS', 'N_CTX', 'TEMPERATURE']
    },
    {
        title: '📧 Email Integration',
        keys: ['EMAIL_ADDRESS', 'EMAIL_APP_PASSWORD', 'IMAP_SERVER', 'SMTP_SERVER']
    },
    {
        title: '⚙️ General Settings',
        keys: ['HEADLESS_MODE']
    }
];

async function loadEnv() {
    try {
        const res = await fetch('/api/env');
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById('env-fields');

        const renderedKeys = new Set();
        let html = '';

        ENV_CATEGORIES.forEach(cat => {
            const catKeys = cat.keys.filter(k => k in data);
            if (catKeys.length === 0) return;

            html += `<div class="env-section">
                <h3 class="env-section-title">${cat.title}</h3>
                <div class="env-grid">`;

            catKeys.forEach(key => {
                renderedKeys.add(key);
                const isSensitive = SENSITIVE_KEYS.includes(key);
                html += `
                    <div class="form-group">
                        <label>${key}</label>
                        <input
                            type="${isSensitive ? 'password' : 'text'}"
                            id="env_${key}"
                            value="${escapeHtml(data[key] || '')}"
                            placeholder="${isSensitive ? '(hidden)' : ''}"
                            autocomplete="off"
                        >
                    </div>`;
            });

            html += `</div></div>`;
        });

        // Render any uncategorized keys
        const remainingKeys = Object.keys(data).filter(k => !renderedKeys.has(k));
        if (remainingKeys.length > 0) {
            html += `<div class="env-section">
                <h3 class="env-section-title">🔧 Other Variables</h3>
                <div class="env-grid">`;
            remainingKeys.forEach(key => {
                const isSensitive = SENSITIVE_KEYS.includes(key);
                html += `
                    <div class="form-group">
                        <label>${key}</label>
                        <input
                            type="${isSensitive ? 'password' : 'text'}"
                            id="env_${key}"
                            value="${escapeHtml(data[key] || '')}"
                            placeholder="${isSensitive ? '(hidden)' : ''}"
                            autocomplete="off"
                        >
                    </div>`;
            });
            html += `</div></div>`;
        }

        container.innerHTML = html;
    } catch (e) {}
}

async function saveEnv() {
    const fields = document.getElementById('env-fields').querySelectorAll('input');
    const vars = {};
    fields.forEach(input => {
        const key = input.id.replace('env_', '');
        vars[key] = input.value;
    });
    const res = await fetch('/api/env', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vars })
    });
    alert(res.ok ? 'Environment saved! Changes are live.' : 'Failed to save environment.');
}

// ── Profiles ──────────────────────────────────────────────────────────────────

async function loadProfiles() {
    try {
        const res = await fetch('/api/profiles');
        if (!res.ok) return;
        const profiles = await res.json();
        const list = document.getElementById('profile-list');
        list.innerHTML = '';
        profiles.forEach(p => {
            const div = document.createElement('div');
            div.className = 'profile-card';
            div.textContent = p.name;
            div.onclick = () => {
                document.getElementById('profile_name').value = p.name;
                document.getElementById('profile_content').value = p.content;
            };
            list.appendChild(div);
        });
    } catch (e) {}
}

async function saveProfile() {
    const name = document.getElementById('profile_name').value.trim();
    const content = document.getElementById('profile_content').value;
    if (!name) return alert('Enter a profile name.');
    await fetch('/api/profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content })
    });
    alert('Profile saved! Changes are active in all sessions.');
    loadProfiles();
}

// ── Init ──────────────────────────────────────────────────────────────────────

window.onload = () => {
    loadBackendInfo();
    loadConfig();
    loadProfiles();
    loadInstalledModels();
    loadHFModels();
    loadEnv();
    document.getElementById('chat-input').focus();
};
