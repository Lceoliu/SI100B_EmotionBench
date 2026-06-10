import {
  Activity,
  ClipboardCheck,
  Database,
  FileArchive,
  ListChecks,
  LogIn,
  LogOut,
  ShieldCheck,
  Table2,
  UploadCloud
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

const tabs = [
  { id: 'leaderboard', label: 'Leaderboard', icon: Table2 },
  { id: 'submit', label: 'Submit', icon: UploadCloud },
  { id: 'runs', label: 'My Runs', icon: ListChecks },
  { id: 'ops', label: 'Ops', icon: ShieldCheck }
];

const statusLabels = {
  queued: 'Queued',
  running: 'Running',
  passed: 'Passed',
  final: 'Final',
  failed: 'Failed',
  rejected: 'Rejected',
  validated: 'Validated'
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || `Request failed: ${res.status}`);
  return payload;
}

function fmtScore(value) {
  if (value === null || value === undefined) return '—';
  return Number(value).toFixed(4);
}

function fmtParams(value) {
  if (!value) return '—';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

function fmtTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value));
}

function StatusChip({ status }) {
  const tone = ['failed', 'rejected'].includes(status)
    ? 'danger'
    : ['queued', 'running'].includes(status)
      ? 'warning'
      : ['final', 'passed', 'validated'].includes(status)
        ? 'success'
        : 'neutral';
  return <span className={`status status-${tone}`}>{statusLabels[status] || status}</span>;
}

function DataTable({ columns, rows, empty }) {
  return (
    <div className="table-wrap" tabIndex="0" aria-label="scrollable data table">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="empty-cell">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.id}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function AuthPanel({ user, onSession }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ student_id: '', display_name: '', password: '', invite_code: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const payload = await api(endpoint, { method: 'POST', body: JSON.stringify(form) });
      onSession(payload.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' });
    onSession(null);
  }

  if (user) {
    return (
      <section className="utility-block">
        <div className="mini-title">Signed in</div>
        <div className="identity">
          <strong>{user.display_name}</strong>
          <span>{user.student_id} · {user.role}</span>
        </div>
        <button className="button secondary full" onClick={logout}>
          <LogOut size={16} /> Sign out
        </button>
      </section>
    );
  }

  return (
    <section className="utility-block">
      <div className="mini-title">Account</div>
      <div className="segmented">
        <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Login</button>
        <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button>
      </div>
      <form className="stack" onSubmit={submit}>
        <label>
          Student ID
          <input value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} />
        </label>
        {mode === 'register' && (
          <label>
            Display name
            <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          </label>
        )}
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        {mode === 'register' && (
          <label>
            Invite code
            <input value={form.invite_code} onChange={(e) => setForm({ ...form, invite_code: e.target.value })} />
          </label>
        )}
        {error && <p className="form-error">{error}</p>}
        <button className="button primary full" disabled={busy}>
          <LogIn size={16} /> {busy ? 'Working' : mode === 'login' ? 'Login' : 'Create account'}
        </button>
      </form>
    </section>
  );
}

function Leaderboard({ rows }) {
  const columns = [
    { key: 'rank', label: '#', render: (row) => <strong>{row.rank}</strong> },
    { key: 'display_name', label: 'Team' },
    { key: 'public_score', label: 'Public score', render: (row) => <strong>{fmtScore(row.public_score)}</strong> },
    { key: 'params', label: 'Params', render: (row) => fmtParams(row.param_count) },
    { key: 'weight', label: 'Weight', render: (row) => `${row.weight_mb} MB` },
    { key: 'status', label: 'State', render: (row) => <StatusChip status={row.status} /> },
    { key: 'updated_at', label: 'Updated', render: (row) => fmtTime(row.updated_at) }
  ];
  return (
    <section className="window">
      <header className="window-bar">
        <span>Public Split Board</span>
        <small>best valid submission per student</small>
      </header>
      <DataTable columns={columns} rows={rows} empty="No passed public submissions yet." />
    </section>
  );
}

function SubmitPanel({ user, config, onCreated }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState('public');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setMessage('');
    setError('');
    if (!user) {
      setError('Please sign in before uploading.');
      return;
    }
    if (!file) {
      setError('Choose a submission zip first.');
      return;
    }
    const body = new FormData();
    body.append('mode', mode);
    body.append('package', file);
    setBusy(true);
    try {
      const payload = await api('/api/submissions', { method: 'POST', body });
      setMessage(`${payload.submission.filename} · ${statusLabels[payload.submission.status]}`);
      setFile(null);
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="window">
      <header className="window-bar">
        <span>Submit Package</span>
        <small>safetensors static gate</small>
      </header>
      <div className="submit-grid">
        <form className="submit-form" onSubmit={submit}>
          <div className="requirements">
            <ClipboardCheck size={18} />
            <div>
              <strong>Required archive</strong>
              <p>ZIP must include <code>model.py</code> and <code>model.safetensors</code>. Static checks reject unsafe imports and invalid tensor metadata before queueing.</p>
            </div>
          </div>
          <label className="file-input">
            <FileArchive size={20} />
            <span>{file ? file.name : 'Choose submission.zip'}</span>
            <input type="file" accept=".zip" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
          <div className="segmented mode-select">
            <button type="button" className={mode === 'public' ? 'active' : ''} onClick={() => setMode('public')}>
              Public queue
            </button>
            <button type="button" className={mode === 'dry-run' ? 'active' : ''} onClick={() => setMode('dry-run')}>
              Static dry-run
            </button>
          </div>
          {error && <p className="form-error">{error}</p>}
          {message && <p className="form-ok">{message}</p>}
          <button className="button primary" disabled={busy}>
            <UploadCloud size={16} /> {busy ? 'Validating' : 'Upload'}
          </button>
        </form>
        <div className="rule-sheet">
          <dl>
            <div><dt>Daily quota</dt><dd>{config.quota_per_day ?? 2}</dd></div>
            <div><dt>Max params</dt><dd>{fmtParams(config.max_params)}</dd></div>
            <div><dt>Weight limit</dt><dd>{config.max_weight_mb ?? 200} MB</dd></div>
            <div><dt>Eval timeout</dt><dd>{config.eval_timeout_sec ?? 600}s</dd></div>
            <div><dt>Classes</dt><dd>{config.num_classes ?? 7}</dd></div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function MyRuns({ rows, onRefresh, onFinal }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'filename', label: 'Package' },
    { key: 'status', label: 'State', render: (row) => <StatusChip status={row.status} /> },
    { key: 'public_score', label: 'Public', render: (row) => fmtScore(row.public_score) },
    { key: 'param_count', label: 'Params', render: (row) => fmtParams(row.param_count) },
    { key: 'created_at', label: 'Created', render: (row) => fmtTime(row.created_at) },
    {
      key: 'final',
      label: 'Final',
      render: (row) =>
        row.final_pick ? (
          <span className="status status-success">Selected</span>
        ) : (
          <button className="link-button" disabled={!['passed', 'final'].includes(row.status)} onClick={() => onFinal(row.id)}>
            Select
          </button>
        )
    }
  ];
  return (
    <section className="window">
      <header className="window-bar">
        <span>My Submissions</span>
        <button className="bar-action" onClick={onRefresh}>Refresh</button>
      </header>
      <DataTable columns={columns} rows={rows} empty="Sign in and upload a package to see your runs." />
    </section>
  );
}

function OpsPanel({ user, rows, config }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'student_id', label: 'Student' },
    { key: 'filename', label: 'Package' },
    { key: 'status', label: 'State', render: (row) => <StatusChip status={row.status} /> },
    { key: 'message', label: 'Message' },
    { key: 'updated_at', label: 'Updated', render: (row) => fmtTime(row.updated_at) }
  ];
  return (
    <section className="window">
      <header className="window-bar">
        <span>TA Operations</span>
        <small>{user?.role === 'admin' ? 'queue visible' : 'admin login required'}</small>
      </header>
      <div className="ops-strip">
        <span><Database size={15} /> SQLite store</span>
        <span><ShieldCheck size={15} /> Docker eval image</span>
        <span><Activity size={15} /> private reveal: {config.reveal_private ? 'on' : 'off'}</span>
      </div>
      <DataTable columns={columns} rows={rows} empty="Admin queue is hidden until a TA account is signed in." />
    </section>
  );
}

function App() {
  const [active, setActive] = useState('leaderboard');
  const [user, setUser] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [mine, setMine] = useState([]);
  const [queue, setQueue] = useState([]);
  const [config, setConfig] = useState({});
  const [notice, setNotice] = useState('');

  async function loadPublic() {
    const [cfg, board, session] = await Promise.all([
      api('/api/config'),
      api('/api/leaderboard'),
      api('/api/session')
    ]);
    setConfig(cfg);
    setLeaderboard(board.rows || []);
    setUser(session.user);
  }

  async function loadMine() {
    if (!user) {
      setMine([]);
      return;
    }
    const payload = await api('/api/submissions/mine');
    setMine(payload.rows || []);
  }

  async function loadQueue() {
    if (user?.role !== 'admin') {
      setQueue([]);
      return;
    }
    const payload = await api('/api/admin/queue');
    setQueue(payload.rows || []);
  }

  useEffect(() => {
    loadPublic().catch((err) => setNotice(err.message));
  }, []);

  useEffect(() => {
    loadMine().catch(() => setMine([]));
    loadQueue().catch(() => setQueue([]));
  }, [user]);

  const topStatus = useMemo(() => {
    const running = leaderboard.filter((row) => ['queued', 'running'].includes(row.status)).length + mine.filter((row) => ['queued', 'running'].includes(row.status)).length;
    return running ? `${running} active run(s)` : 'queue quiet';
  }, [leaderboard, mine]);

  async function refreshAll() {
    try {
      await loadPublic();
      await loadMine();
      await loadQueue();
      setNotice('Refreshed');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function markFinal(id) {
    try {
      await api(`/api/submissions/${id}/final`, { method: 'POST' });
      await loadMine();
    } catch (err) {
      setNotice(err.message);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-title">EmotionBench OS</div>
          <div className="brand-subtitle">SI100B 2026 Fall evaluation console</div>
        </div>
        <nav className="tabs" aria-label="Primary sections">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} className={active === tab.id ? 'active' : ''} onClick={() => setActive(tab.id)}>
                <Icon size={16} /> {tab.label}
              </button>
            );
          })}
        </nav>
      </header>
      <div className="signature-stripe" />

      <main className="workspace">
        <section className="content">
          <div className="page-head">
            <div>
              <h1>{active === 'leaderboard' ? 'Public Benchmark' : active === 'submit' ? 'Submission Gate' : active === 'runs' ? 'Run Register' : 'Operations Desk'}</h1>
              <p>Strict package checks, visible queue states, and one place to inspect benchmark records.</p>
            </div>
            <button className="button secondary" onClick={refreshAll}>Refresh</button>
          </div>

          {notice && <div className="notice">{notice}</div>}
          {active === 'leaderboard' && <Leaderboard rows={leaderboard} />}
          {active === 'submit' && <SubmitPanel user={user} config={config} onCreated={refreshAll} />}
          {active === 'runs' && <MyRuns rows={mine} onRefresh={loadMine} onFinal={markFinal} />}
          {active === 'ops' && <OpsPanel user={user} rows={queue} config={config} />}
        </section>

        <aside className="utility">
          <AuthPanel user={user} onSession={setUser} />
          <section className="utility-block">
            <div className="mini-title">System</div>
            <dl className="system-list">
              <div><dt>Queue</dt><dd>{topStatus}</dd></div>
              <div><dt>Leaderboard</dt><dd>{config.freeze_leaderboard ? 'frozen' : 'open'}</dd></div>
              <div><dt>Final deadline</dt><dd>{config.final_pick_deadline || 'unset'}</dd></div>
            </dl>
          </section>
        </aside>
      </main>

      <footer className="statusbar">
        <span>storage/submissions indexed</span>
        <span>public labels isolated from private splits</span>
        <span>{new Date().toLocaleDateString('zh-CN')}</span>
      </footer>
    </div>
  );
}

export default App;
