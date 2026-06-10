import {
  Activity,
  Ban,
  BookOpen,
  ClipboardCheck,
  Database,
  Download,
  ExternalLink,
  FileArchive,
  Home,
  ListChecks,
  LogIn,
  LogOut,
  KeyRound,
  Plus,
  ShieldCheck,
  Table2,
  Trash2,
  UploadCloud,
  Users
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

const baseTabs = [
  { id: 'home', label: '主页', icon: Home },
  { id: 'leaderboard', label: '排行榜', icon: Table2 },
  { id: 'submit', label: '提交模型', icon: UploadCloud },
  { id: 'runs', label: '我的记录', icon: ListChecks }
];

const adminTab = { id: 'ops', label: 'TA 管理', icon: ShieldCheck };

const statusLabels = {
  queued: '排队中',
  running: '运行中',
  passed: '已通过',
  final: '最终提交',
  failed: '失败',
  rejected: '已拒绝',
  validated: '已验证'
};

const lectureItems = [
  { title: '环境配置与图像基础', detail: '安装必要环境，理解图像读取、像素、通道和基本数据结构。', resourceId: 'lab1' },
  { title: 'OpenCV 基本操作', detail: '读写图像、缩放、绘制图形，并接触级联分类器做人脸检测。', resourceId: 'lab2' },
  { title: '模型训练', detail: '从基础分类网络开始，理解训练循环、损失函数和参数更新。', resourceId: 'lab3' },
  { title: '模型推理', detail: '加载训练好的模型，对输入图像执行预测并取回结果。', resourceId: 'lab4' },
  { title: '端到端流程', detail: '串联读图、人脸检测、Tensor 转换、推理和可视化输出。', resourceId: 'lab5' },
  { title: 'Matplotlib 可视化', detail: '用图表展示样本、预测结果和训练过程。', resourceId: 'lab6' },
  { title: '数据标注的重要性', detail: '分析错误样例，理解标注质量和补充数据对准确率的影响。', resourceId: 'lab7' },
  { title: '扩展主题', detail: '摄像头实时读取、YOLO 检测、数据增强等进阶方向。', resourceId: 'lab8' }
];

let csrfToken = '';

function setCsrfToken(token) {
  csrfToken = token || '';
}

function makeRequestNonce() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    const bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && options.body !== undefined) {
    headers.set('Content-Type', 'application/json');
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    if (csrfToken) headers.set('X-CSRF-Token', csrfToken);
    headers.set('X-Request-Nonce', makeRequestNonce());
    headers.set('X-Request-Time', String(Date.now()));
  }
  const res = await fetch(path, {
    credentials: 'same-origin',
    ...options,
    headers
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || `请求失败：${res.status}`);
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
    <div className="table-wrap" tabIndex="0" aria-label="可横向滚动的数据表">
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

function HomePage({ resources }) {
  const resourceMap = useMemo(() => {
    const next = new Map();
    resources.forEach((item) => next.set(item.id, item));
    return next;
  }, [resources]);
  const projectRules = resourceMap.get('project-rules');

  return (
    <div className="home-stack">
      <section className="window">
        <header className="window-bar">
          <span>项目说明</span>
          <small>Face Detection and Emotion Classification</small>
        </header>
        <div className="home-intro">
          <div>
            <h2>从人脸检测到表情识别</h2>
            <p>
              本项目为 SI100B 课程Project 人脸检测与表情分类 的评测平台。用户可以提交模型并查看公开榜结果。
            </p>
          </div>
          <ol className="process-list">
            <li><span>课程教师</span>
              <span className="ta-line">
                <a href="https://sist.shanghaitech.edu.cn/lzh/main.htm" target="_blank" rel="noreferrer">李正浩</a>
              </span></li>
            <li><span>TA</span>
              <span className="ta-line">
                <a href="https://lceoliu.github.io/" target="_blank" rel="noreferrer">刘畅</a>，<a href="" target="_blank" rel="noreferrer">张境轩</a>
              </span>
            </li>
          </ol>
        </div>
      </section>

      <section className="window">
        <header className="window-bar">
          <span>课程路径</span>
          <small>8 次 lab 主题</small>
        </header>
        <div className="lecture-grid">
          {lectureItems.map((item) => {
            const resource = resourceMap.get(item.resourceId);
            return (
            <div className="lecture-row" key={item.title}>
              <strong>{item.title}</strong>
              <p>{item.detail}</p>
              {resource?.available ? (
                <a className="download-link" href={resource.download_url}>
                  <Download size={15} />
                  <span>下载 {resource.title.split('：')[0]}</span>
                </a>
              ) : (
                <span className="download-link disabled">
                  <Download size={15} />
                  <span>资料待上传</span>
                </span>
              )}
            </div>
            );
          })}
        </div>
      </section>

      <section className="window">
        <header className="window-bar">
          <span>资源与建议</span>
          <small>课程资料入口</small>
        </header>
        <div className="resource-grid">
          <a className="resource-link" href="https://elearning.shanghaitech.edu.cn:8443/webapps/blackboard/content/listContentEditable.jsp?content_id=_173911_1&course_id=_5304_1" target="_blank" rel="noreferrer">
            <ExternalLink size={18} />
            <span>Blackboard 课程资源</span>
          </a>
          {/* <div className="resource-note">
            <strong>建议补充阅读</strong>
            <p>复习 OpenCV 图像读写和 resize、PyTorch Dataset/DataLoader、模型保存与加载、Matplotlib 可视化，以及 safetensors 模型权重格式。</p>
          </div> */}
          <div className="resource-note">
            <strong>项目评分</strong>
            <p>课程project评分包含参与与 checkpoint、bonus，以及最终提交的文字报告。平台评测只负责模型提交、公开榜和最终提交记录。完整规则请查看
              {' '}
              {projectRules?.available ? (
                <a href={projectRules.download_url}>此处的文件下载链接</a>
              ) : (
                <span>此处的文件下载链接</span>
              )}。
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

function AuthPanel({ user, onSession, onAfterLogin }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', display_name: '', password: '', invite_code: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const payload = await api(endpoint, { method: 'POST', body: JSON.stringify(form) });
      setCsrfToken(payload.csrf_token);
      onSession(payload.user);
      onAfterLogin?.(payload.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' });
    setCsrfToken('');
    onSession(null);
  }

  if (user) {
    return (
      <section className="utility-block">
        <div className="mini-title">当前账号</div>
        <div className="identity">
          <strong>{user.display_name}</strong>
          <span>{user.email} · {user.role === 'admin' ? '管理员' : '学生'}</span>
        </div>
        <button className="button secondary full" onClick={logout}>
          <LogOut size={16} /> 退出登录
        </button>
      </section>
    );
  }

  return (
    <section className="utility-block">
      <div className="mini-title">账号</div>
      <div className="segmented">
        <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>登录</button>
        <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>注册</button>
      </div>
      <form className="stack" onSubmit={submit}>
        <label>
          邮箱
          <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="name@shanghaitech.edu.cn" />
        </label>
        {mode === 'register' && (
          <label>
            希望展示的名称
            <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          </label>
        )}
        <label>
          密码
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </label>
        {mode === 'register' && (
          <label>
            邀请码
            <input value={form.invite_code} onChange={(e) => setForm({ ...form, invite_code: e.target.value })} />
          </label>
        )}
        {mode === 'register' && <p className="hint-text">仅支持 @shanghaitech.edu.cn 邮箱注册。</p>}
        {error && <p className="form-error">{error}</p>}
        <button className="button primary full" disabled={busy}>
          <LogIn size={16} /> {busy ? '处理中' : mode === 'login' ? '登录' : '创建账号'}
        </button>
      </form>
    </section>
  );
}

function GroupPanel({ user, group, onProfileUpdate }) {
  const [draft, setDraft] = useState({ display_name: '', group_name: '' });

  useEffect(() => {
    if (!user || user.role !== 'student') return;
    setDraft({ display_name: user.display_name || '', group_name: user.group_name || '' });
  }, [user]);

  async function submit(event) {
    event.preventDefault();
    await onProfileUpdate(draft);
  }

  if (!user || user.role !== 'student') return null;
  return (
    <section className="utility-block">
      <div className="mini-title">我的小组</div>
      <form className="stack profile-form" onSubmit={submit}>
        <label>
          显示名称
          <input value={draft.display_name} onChange={(event) => setDraft({ ...draft, display_name: event.target.value })} />
        </label>
        <label>
          小组名
          <input value={draft.group_name} onChange={(event) => setDraft({ ...draft, group_name: event.target.value })} placeholder="例如 1组 / Team Alpha" />
        </label>
        <button className="button secondary full">保存资料</button>
      </form>
      <div className="group-name">{group.group_name || '暂未分组'}</div>
      <ul className="mate-list">
        {(group.mates || []).map((mate) => (
          <li key={mate.id}>
            <strong>{mate.display_name}</strong>
            <span>{mate.email}</span>
          </li>
        ))}
      </ul>
      {!group.group_name && <p className="hint-text">分组后会在这里显示队友。</p>}
    </section>
  );
}

function Leaderboard({ rows, admin, onDelete }) {
  const columns = [
    { key: 'rank', label: '#', render: (row) => <strong>{row.rank}</strong> },
    { key: 'display_name', label: '队伍/姓名' },
    { key: 'group_name', label: '小组', render: (row) => row.group_name || '—' },
    { key: 'public_score', label: '公开分数', render: (row) => <strong>{fmtScore(row.public_score)}</strong> },
    { key: 'params', label: '参数量', render: (row) => fmtParams(row.param_count) },
    { key: 'weight', label: '权重大小', render: (row) => `${row.weight_mb} MB` },
    { key: 'status', label: '状态', render: (row) => <StatusChip status={row.status} /> },
    { key: 'updated_at', label: '更新时间', render: (row) => fmtTime(row.updated_at) }
  ];
  if (admin) {
    columns.push({
      key: 'admin_action',
      label: '管理',
      render: (row) => (
        <button className="link-button danger-link" onClick={() => onDelete(row.id)}>
          <Trash2 size={14} /> 删除记录
        </button>
      )
    });
  }
  return (
    <section className="window">
      <header className="window-bar">
        <span>公开榜</span>
        <small>每位学生/队伍取最高有效提交</small>
      </header>
      <DataTable columns={columns} rows={rows} empty="暂时还没有通过公开集评测的提交。" />
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
      setError('请先登录再上传。');
      return;
    }
    if (!file) {
      setError('请先选择 submission.zip。');
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
        <span>提交模型包</span>
        <small>safetensors 静态检查</small>
      </header>
      <div className="submit-grid">
        <form className="submit-form" onSubmit={submit}>
          <div className="requirements">
            <ClipboardCheck size={18} />
            <div>
              <strong>压缩包要求</strong>
              <p>ZIP 内必须包含 <code>model.py</code> 和 <code>model.safetensors</code>。平台会先检查危险导入、权重格式和参数量，再决定是否进入公开集评测队列。</p>
            </div>
          </div>
          <label className="file-input">
            <FileArchive size={20} />
            <span>{file ? file.name : '选择 submission.zip'}</span>
            <input type="file" accept=".zip" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
          <div className="segmented mode-select">
            <button type="button" className={mode === 'public' ? 'active' : ''} onClick={() => setMode('public')}>
              进入公开队列
            </button>
            <button type="button" className={mode === 'dry-run' ? 'active' : ''} onClick={() => setMode('dry-run')}>
              仅静态检查
            </button>
          </div>
          {error && <p className="form-error">{error}</p>}
          {message && <p className="form-ok">{message}</p>}
          <button className="button primary" disabled={busy}>
            <UploadCloud size={16} /> {busy ? '检查中' : '上传'}
          </button>
        </form>
        <div className="rule-sheet">
          <dl>
            <div><dt>每日次数</dt><dd>{config.quota_per_day ?? 2}</dd></div>
            <div><dt>最大参数量</dt><dd>{fmtParams(config.max_params)}</dd></div>
            <div><dt>权重上限</dt><dd>{config.max_weight_mb ?? 200} MB</dd></div>
            <div><dt>评测超时</dt><dd>{config.eval_timeout_sec ?? 600}s</dd></div>
            <div><dt>类别数</dt><dd>{config.num_classes ?? 7}</dd></div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function MyRuns({ rows, onRefresh, onFinal }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'filename', label: '文件' },
    { key: 'status', label: '状态', render: (row) => <StatusChip status={row.status} /> },
    { key: 'public_score', label: '公开分数', render: (row) => fmtScore(row.public_score) },
    { key: 'param_count', label: '参数量', render: (row) => fmtParams(row.param_count) },
    { key: 'created_at', label: '创建时间', render: (row) => fmtTime(row.created_at) },
    {
      key: 'final',
      label: '最终提交',
      render: (row) =>
        row.final_pick ? (
          <span className="status status-success">已选择</span>
        ) : (
          <button className="link-button" disabled={!['passed', 'final'].includes(row.status)} onClick={() => onFinal(row.id)}>
            设为最终
          </button>
        )
    }
  ];
  return (
    <section className="window">
      <header className="window-bar">
        <span>我的提交记录</span>
        <button className="bar-action" onClick={onRefresh}>刷新</button>
      </header>
      <DataTable columns={columns} rows={rows} empty="登录并上传模型包后，这里会显示你的提交记录。" />
    </section>
  );
}

function StudentManager({ students, onSaveGroup, onToggleDisabled, onResetPassword }) {
  const [drafts, setDrafts] = useState({});
  const [passwords, setPasswords] = useState({});
  const [groupCount, setGroupCount] = useState(8);

  useEffect(() => {
    const next = {};
    let numericMax = 0;
    students.forEach((student) => {
      next[student.id] = student.group_name || '';
      const match = String(student.group_name || '').match(/^(\d+)组$/);
      if (match) numericMax = Math.max(numericMax, Number(match[1]));
    });
    setDrafts(next);
    setGroupCount((value) => Math.max(value, numericMax, 1));
  }, [students]);

  const groupOptions = useMemo(
    () => Array.from({ length: groupCount }, (_, index) => `${index + 1}组`),
    [groupCount]
  );

  const columns = [
    { key: 'display_name', label: '姓名/队名' },
    { key: 'email', label: '邮箱' },
    {
      key: 'disabled',
      label: '账号',
      render: (row) => (
        <span className={`status ${row.disabled ? 'status-danger' : 'status-success'}`}>
          {row.disabled ? '已禁用' : '可登录'}
        </span>
      )
    },
    {
      key: 'group_name',
      label: '小组',
      render: (row) => (
        <select
          className="table-select"
          value={drafts[row.id] ?? ''}
          onChange={(event) => setDrafts({ ...drafts, [row.id]: event.target.value })}
        >
          <option value="">未分组</option>
          {drafts[row.id] && !groupOptions.includes(drafts[row.id]) && (
            <option value={drafts[row.id]}>自定义：{drafts[row.id]}</option>
          )}
          {groupOptions.map((groupName) => (
            <option value={groupName} key={groupName}>{groupName}</option>
          ))}
        </select>
      )
    },
    {
      key: 'password',
      label: '重置密码',
      render: (row) => (
        <div className="inline-actions">
          <input
            className="table-input password-input"
            type="password"
            value={passwords[row.id] ?? ''}
            onChange={(event) => setPasswords({ ...passwords, [row.id]: event.target.value })}
            placeholder="至少 8 位"
          />
          <button
            className="link-button"
            onClick={() => onResetPassword(row.id, passwords[row.id] ?? '').then((ok) => {
              if (ok) setPasswords({ ...passwords, [row.id]: '' });
            })}
          >
            <KeyRound size={14} /> 重置
          </button>
        </div>
      )
    },
    {
      key: 'actions',
      label: '管理',
      render: (row) => (
        <div className="inline-actions">
          <button className="link-button" onClick={() => onSaveGroup(row.id, drafts[row.id] ?? '')}>
            保存分组
          </button>
          <button className="link-button danger-link" onClick={() => onToggleDisabled(row.id, !row.disabled)}>
            <Ban size={14} /> {row.disabled ? '启用' : '禁用'}
          </button>
        </div>
      )
    }
  ];

  return (
    <section className="window">
      <header className="window-bar">
        <span>学生与分组</span>
        <small>数字分组候选</small>
      </header>
      <div className="group-toolbar">
        <label>
          分组数量
          <input
            type="number"
            min="1"
            max="80"
            value={groupCount}
            onChange={(event) => setGroupCount(Math.max(1, Math.min(80, Number(event.target.value) || 1)))}
          />
        </label>
        <div className="group-pills" aria-label="现有分组">
          <span className="group-pill muted-pill">未分组</span>
          {groupOptions.map((groupName) => (
            <span className="group-pill" key={groupName}>{groupName}</span>
          ))}
        </div>
      </div>
      <DataTable columns={columns} rows={students.filter((student) => student.role === 'student')} empty="暂无注册学生。" />
    </section>
  );
}

function InviteManager({ invites, onCreateInvite, onDeleteInvite }) {
  const [form, setForm] = useState({ code: '', label: '' });

  async function submit(event) {
    event.preventDefault();
    const ok = await onCreateInvite(form);
    if (ok) setForm({ code: '', label: '' });
  }

  const columns = [
    { key: 'code', label: '邀请码', render: (row) => <code>{row.code}</code> },
    { key: 'label', label: '说明', render: (row) => row.label || '—' },
    { key: 'created_at', label: '创建时间', render: (row) => fmtTime(row.created_at) },
    {
      key: 'action',
      label: '操作',
      render: (row) => (
        <button className="link-button danger-link" onClick={() => onDeleteInvite(row.id)}>
          <Trash2 size={14} /> 删除
        </button>
      )
    }
  ];

  return (
    <section className="window">
      <header className="window-bar">
        <span>注册邀请码</span>
        <small>管理员维护可用邀请码</small>
      </header>
      <form className="invite-form" onSubmit={submit}>
        <label>
          邀请码
          <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="例如 SI100B-2026" />
        </label>
        <label>
          说明
          <input value={form.label} onChange={(event) => setForm({ ...form, label: event.target.value })} placeholder="例如 第一批学生" />
        </label>
        <button className="button primary">
          <Plus size={16} /> 添加
        </button>
      </form>
      <DataTable columns={columns} rows={invites} empty="暂无可用邀请码。" />
    </section>
  );
}

function OpsPanel({ queueRows, students, invites, config, onSaveGroup, onToggleDisabled, onResetPassword, onCreateInvite, onDeleteInvite, onDeleteSubmission }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'email', label: '邮箱' },
    { key: 'display_name', label: '姓名/队名' },
    { key: 'group_name', label: '小组', render: (row) => row.group_name || '—' },
    { key: 'filename', label: '文件' },
    { key: 'status', label: '状态', render: (row) => <StatusChip status={row.status} /> },
    { key: 'message', label: '信息' },
    { key: 'updated_at', label: '更新时间', render: (row) => fmtTime(row.updated_at) },
    {
      key: 'admin_action',
      label: '管理',
      render: (row) => (
        <button className="link-button danger-link" onClick={() => onDeleteSubmission(row.id)}>
          <Trash2 size={14} /> 删除记录
        </button>
      )
    }
  ];
  return (
    <div className="ops-stack">
      <section className="window">
        <header className="window-bar">
          <span>评测运维</span>
          <small>管理员可见</small>
        </header>
        <div className="ops-strip">
          <span><Database size={15} /> SQLite 数据库</span>
          <span><ShieldCheck size={15} /> Docker 评测镜像</span>
          <span><Activity size={15} /> 私榜公开：{config.reveal_private ? '已开启' : '未开启'}</span>
        </div>
        <DataTable columns={columns} rows={queueRows} empty="暂无评测队列记录。" />
      </section>
      <StudentManager students={students} onSaveGroup={onSaveGroup} onToggleDisabled={onToggleDisabled} onResetPassword={onResetPassword} />
      <InviteManager invites={invites} onCreateInvite={onCreateInvite} onDeleteInvite={onDeleteInvite} />
    </div>
  );
}

function App() {
  const [active, setActive] = useState('home');
  const [user, setUser] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [mine, setMine] = useState([]);
  const [queue, setQueue] = useState([]);
  const [students, setStudents] = useState([]);
  const [invites, setInvites] = useState([]);
  const [resources, setResources] = useState([]);
  const [group, setGroup] = useState({ group_name: '', mates: [] });
  const [config, setConfig] = useState({});
  const [notice, setNotice] = useState('');

  const tabs = useMemo(() => (user?.role === 'admin' ? [...baseTabs, adminTab] : baseTabs), [user]);

  useEffect(() => {
    if (active === 'ops' && user?.role !== 'admin') setActive('home');
  }, [active, user]);

  async function loadPublic() {
    const [cfg, board, session, resourcePayload] = await Promise.all([
      api('/api/config'),
      api('/api/leaderboard'),
      api('/api/session'),
      api('/api/resources')
    ]);
    setCsrfToken(session.csrf_token);
    setConfig(cfg);
    setLeaderboard(board.rows || []);
    setUser(session.user);
    setResources(resourcePayload.rows || []);
  }

  async function loadMine(currentUser = user) {
    if (!currentUser) {
      setMine([]);
      setGroup({ group_name: '', mates: [] });
      return;
    }
    const [minePayload, groupPayload] = await Promise.all([
      api('/api/submissions/mine'),
      currentUser.role === 'student' ? api('/api/me/group') : Promise.resolve({ group_name: '', mates: [] })
    ]);
    setMine(minePayload.rows || []);
    setGroup(groupPayload);
  }

  async function loadAdmin(currentUser = user) {
    if (currentUser?.role !== 'admin') {
      setQueue([]);
      setStudents([]);
      setInvites([]);
      return;
    }
    const [queuePayload, studentsPayload, invitesPayload] = await Promise.all([
      api('/api/admin/queue'),
      api('/api/admin/students'),
      api('/api/admin/invites')
    ]);
    setQueue(queuePayload.rows || []);
    setStudents(studentsPayload.rows || []);
    setInvites(invitesPayload.rows || []);
  }

  useEffect(() => {
    loadPublic().catch((err) => setNotice(err.message));
  }, []);

  useEffect(() => {
    loadMine(user).catch(() => {
      setMine([]);
      setGroup({ group_name: '', mates: [] });
    });
    loadAdmin(user).catch(() => {
      setQueue([]);
      setStudents([]);
    });
  }, [user]);

  const topStatus = useMemo(() => {
    const running = leaderboard.filter((row) => ['queued', 'running'].includes(row.status)).length + mine.filter((row) => ['queued', 'running'].includes(row.status)).length;
    return running ? `${running} 个任务运行中` : '队列空闲';
  }, [leaderboard, mine]);

  async function refreshAll() {
    try {
      await loadPublic();
      await loadMine(user);
      await loadAdmin(user);
      setNotice('已刷新');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function markFinal(id) {
    try {
      await api(`/api/submissions/${id}/final`, { method: 'POST' });
      await loadMine(user);
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function updateProfile(form) {
    try {
      const payload = await api('/api/me/profile', {
        method: 'PATCH',
        body: JSON.stringify(form)
      });
      setUser(payload.user);
      await loadPublic();
      await loadMine(payload.user);
      setNotice('资料已保存');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function saveGroup(userId, groupName) {
    try {
      await api(`/api/admin/students/${userId}/group`, {
        method: 'PATCH',
        body: JSON.stringify({ group_name: groupName })
      });
      await loadAdmin(user);
      setNotice('分组已保存');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function toggleDisabled(userId, disabled) {
    try {
      await api(`/api/admin/students/${userId}/disabled`, {
        method: 'PATCH',
        body: JSON.stringify({ disabled })
      });
      await loadAdmin(user);
      setNotice(disabled ? '账号已禁用' : '账号已启用');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function resetPassword(userId, password) {
    try {
      await api(`/api/admin/students/${userId}/reset-password`, {
        method: 'POST',
        body: JSON.stringify({ password })
      });
      setNotice('密码已重置');
      return true;
    } catch (err) {
      setNotice(err.message);
      return false;
    }
  }

  async function createInvite(form) {
    try {
      await api('/api/admin/invites', {
        method: 'POST',
        body: JSON.stringify(form)
      });
      await loadAdmin(user);
      setNotice('邀请码已添加');
      return true;
    } catch (err) {
      setNotice(err.message);
      return false;
    }
  }

  async function deleteInvite(inviteId) {
    try {
      await api(`/api/admin/invites/${inviteId}`, { method: 'DELETE' });
      await loadAdmin(user);
      setNotice('邀请码已删除');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function deleteSubmission(submissionId) {
    if (!window.confirm(`确认删除提交记录 #${submissionId}？此操作会同步影响排行榜。`)) return;
    try {
      await api(`/api/admin/submissions/${submissionId}`, { method: 'DELETE' });
      await loadPublic();
      await loadMine(user);
      await loadAdmin(user);
      setNotice('提交记录已删除');
    } catch (err) {
      setNotice(err.message);
    }
  }

  const pageTitle = {
    home: '人脸检测与表情分类项目',
    leaderboard: '公开排行榜',
    submit: '模型提交',
    runs: '我的评测记录',
    ops: 'TA 管理台'
  }[active];

  const pageCopy = {
    home: 'SI100B Spring 2026 课程项目评测平台，欢迎提交模型并查看排行榜！',
    leaderboard: '公开排行榜每日更新，展示每位学生/队伍的最高有效提交结果。',
    submit: '上传包含 model.py 与 model.safetensors 的 ZIP 文件',
    runs: '查看自己的提交状态、公开分数。',
    ops: 'TA 可查看评测队列、注册学生，并统一维护学生分组。'
  }[active];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-title">Emotional Bench</div>
          <div className="brand-subtitle">Face Detection · Emotion Classification · Benchmark</div>
        </div>
        <nav className="tabs" aria-label="主导航">
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
              <h1>{pageTitle}</h1>
              <p>{pageCopy}</p>
            </div>
            <button className="button secondary" onClick={refreshAll}>刷新</button>
          </div>

          {notice && <div className="notice">{notice}</div>}
          {active === 'home' && <HomePage resources={resources} />}
          {active === 'leaderboard' && <Leaderboard rows={leaderboard} admin={user?.role === 'admin'} onDelete={deleteSubmission} />}
          {active === 'submit' && <SubmitPanel user={user} config={config} onCreated={refreshAll} />}
          {active === 'runs' && <MyRuns rows={mine} onRefresh={() => loadMine(user)} onFinal={markFinal} />}
          {active === 'ops' && user?.role === 'admin' && (
            <OpsPanel
              queueRows={queue}
              students={students}
              invites={invites}
              config={config}
              onSaveGroup={saveGroup}
              onToggleDisabled={toggleDisabled}
              onResetPassword={resetPassword}
              onCreateInvite={createInvite}
              onDeleteInvite={deleteInvite}
              onDeleteSubmission={deleteSubmission}
            />
          )}
        </section>

        <aside className="utility">
          <AuthPanel user={user} onSession={setUser} onAfterLogin={(nextUser) => setActive(nextUser.role === 'admin' ? 'ops' : 'home')} />
          <GroupPanel user={user} group={group} onProfileUpdate={updateProfile} />
          <section className="utility-block">
            <div className="mini-title">系统状态</div>
            <dl className="system-list">
              <div><dt>评测队列</dt><dd>{topStatus}</dd></div>
              <div><dt>排行榜</dt><dd>{config.freeze_leaderboard ? '已冻结' : '开放中'}</dd></div>
              <div><dt>最终提交截止</dt><dd>{config.final_pick_deadline || '未设置'}</dd></div>
            </dl>
          </section>
        </aside>
      </main>

      <footer className="statusbar">
        <span>© 2026 Chang LIU · Licensed under Apache-2.0</span>
      </footer>
    </div>
  );
}

export default App;
