import {
  Activity,
  BookOpen,
  ClipboardCheck,
  Database,
  ExternalLink,
  FileArchive,
  Home,
  ListChecks,
  LogIn,
  LogOut,
  ShieldCheck,
  Table2,
  UploadCloud,
  Users
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

const baseTabs = [
  { id: 'home', label: '项目主页', icon: Home },
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
  ['环境配置与图像基础', '安装必要环境，理解图像读取、像素、通道和基本数据结构。'],
  ['OpenCV 基本操作', '读写图像、缩放、绘制图形，并接触级联分类器做人脸检测。'],
  ['模型训练', '从基础分类网络开始，理解训练循环、损失函数和参数更新。'],
  ['模型推理', '加载训练好的模型，对输入图像执行预测并取回结果。'],
  ['端到端流程', '串联读图、人脸检测、Tensor 转换、推理和可视化输出。'],
  ['Matplotlib 可视化', '用图表展示样本、预测结果和训练过程。'],
  ['数据标注的重要性', '分析错误样例，理解标注质量和补充数据对准确率的影响。'],
  ['扩展主题', '摄像头实时读取、YOLO 检测、数据增强等进阶方向。']
];

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options
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

function HomePage() {
  return (
    <div className="home-stack">
      <section className="window">
        <header className="window-bar">
          <span>项目说明</span>
          <small>Face Detection and Emotion Classification</small>
        </header>
        <div className="home-intro">
          <div>
            <h2>从读入图像到识别表情</h2>
            <p>
              本项目面向 SI100B 课程实践：学生将从基础图像概念和 OpenCV 操作开始，逐步完成“读取图像、人脸检测、表情分类”的端到端流程，并通过评测平台提交模型包查看公开榜结果。
            </p>
          </div>
          <ol className="process-list">
            <li><span>读入图像</span><small>理解图像尺寸、通道和预处理。</small></li>
            <li><span>检测人脸</span><small>定位图像中的人脸区域。</small></li>
            <li><span>分类表情</span><small>用神经网络输出表情类别。</small></li>
          </ol>
        </div>
      </section>

      <section className="window">
        <header className="window-bar">
          <span>课程路径</span>
          <small>8 个 lecture 主题</small>
        </header>
        <div className="lecture-grid">
          {lectureItems.map(([title, detail]) => (
            <div className="lecture-row" key={title}>
              <strong>{title}</strong>
              <p>{detail}</p>
            </div>
          ))}
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
          <div className="resource-note">
            <strong>建议补充阅读</strong>
            <p>复习 OpenCV 图像读写和 resize、PyTorch Dataset/DataLoader、模型保存与加载、Matplotlib 可视化，以及 safetensors 模型权重格式。</p>
          </div>
          <div className="resource-note">
            <strong>评分结构</strong>
            <p>课程项目包含参与与 checkpoint、bonus，以及最终报告。平台评测只负责模型提交、公开榜和最终提交记录。</p>
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
          邮箱 / 管理员账号
          <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="name@shanghaitech.edu.cn" />
        </label>
        {mode === 'register' && (
          <label>
            姓名或队名
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
        <p className="hint-text">TA 管理员使用账号 <code>admin</code> 登录。</p>
        {error && <p className="form-error">{error}</p>}
        <button className="button primary full" disabled={busy}>
          <LogIn size={16} /> {busy ? '处理中' : mode === 'login' ? '登录' : '创建账号'}
        </button>
      </form>
    </section>
  );
}

function GroupPanel({ user, group }) {
  if (!user || user.role !== 'student') return null;
  return (
    <section className="utility-block">
      <div className="mini-title">我的小组</div>
      <div className="group-name">{group.group_name || '暂未分组'}</div>
      <ul className="mate-list">
        {(group.mates || []).map((mate) => (
          <li key={mate.id}>
            <strong>{mate.display_name}</strong>
            <span>{mate.email}</span>
          </li>
        ))}
      </ul>
      {!group.group_name && <p className="hint-text">TA 分组后会在这里显示队友。</p>}
    </section>
  );
}

function Leaderboard({ rows }) {
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

function StudentManager({ students, onSaveGroup }) {
  const [drafts, setDrafts] = useState({});

  useEffect(() => {
    const next = {};
    students.forEach((student) => {
      next[student.id] = student.group_name || '';
    });
    setDrafts(next);
  }, [students]);

  const columns = [
    { key: 'display_name', label: '姓名/队名' },
    { key: 'email', label: '邮箱' },
    {
      key: 'group_name',
      label: '小组',
      render: (row) => (
        <input
          className="table-input"
          value={drafts[row.id] ?? ''}
          onChange={(event) => setDrafts({ ...drafts, [row.id]: event.target.value })}
          placeholder="例如 A组"
        />
      )
    },
    {
      key: 'action',
      label: '操作',
      render: (row) => (
        <button className="link-button" onClick={() => onSaveGroup(row.id, drafts[row.id] ?? '')}>
          保存
        </button>
      )
    }
  ];

  return (
    <section className="window">
      <header className="window-bar">
        <span>学生与分组</span>
        <small>统一管理注册学生</small>
      </header>
      <DataTable columns={columns} rows={students.filter((student) => student.role === 'student')} empty="暂无注册学生。" />
    </section>
  );
}

function OpsPanel({ queueRows, students, config, onSaveGroup }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'email', label: '邮箱' },
    { key: 'display_name', label: '姓名/队名' },
    { key: 'group_name', label: '小组', render: (row) => row.group_name || '—' },
    { key: 'filename', label: '文件' },
    { key: 'status', label: '状态', render: (row) => <StatusChip status={row.status} /> },
    { key: 'message', label: '信息' },
    { key: 'updated_at', label: '更新时间', render: (row) => fmtTime(row.updated_at) }
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
      <StudentManager students={students} onSaveGroup={onSaveGroup} />
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
  const [group, setGroup] = useState({ group_name: '', mates: [] });
  const [config, setConfig] = useState({});
  const [notice, setNotice] = useState('');

  const tabs = useMemo(() => (user?.role === 'admin' ? [...baseTabs, adminTab] : baseTabs), [user]);

  useEffect(() => {
    if (active === 'ops' && user?.role !== 'admin') setActive('home');
  }, [active, user]);

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
      return;
    }
    const [queuePayload, studentsPayload] = await Promise.all([
      api('/api/admin/queue'),
      api('/api/admin/students')
    ]);
    setQueue(queuePayload.rows || []);
    setStudents(studentsPayload.rows || []);
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

  const pageTitle = {
    home: '人脸检测与表情分类项目',
    leaderboard: '公开排行榜',
    submit: '模型提交',
    runs: '我的评测记录',
    ops: 'TA 管理台'
  }[active];

  const pageCopy = {
    home: '课程项目资料、学习路径和评测平台入口集中在这里。',
    leaderboard: '公开集只展示可公开比较的分数，私有集与真实场景集默认不对学生公开。',
    submit: '上传包含 model.py 与 model.safetensors 的 ZIP，平台会先执行静态检查。',
    runs: '查看自己的提交状态、公开分数，并选择最终提交。',
    ops: 'TA 可查看评测队列、注册学生，并统一维护学生分组。'
  }[active];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-title">SI100B 表情识别评测平台</div>
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
          {active === 'home' && <HomePage />}
          {active === 'leaderboard' && <Leaderboard rows={leaderboard} />}
          {active === 'submit' && <SubmitPanel user={user} config={config} onCreated={refreshAll} />}
          {active === 'runs' && <MyRuns rows={mine} onRefresh={() => loadMine(user)} onFinal={markFinal} />}
          {active === 'ops' && user?.role === 'admin' && <OpsPanel queueRows={queue} students={students} config={config} onSaveGroup={saveGroup} />}
        </section>

        <aside className="utility">
          <AuthPanel user={user} onSession={setUser} onAfterLogin={(nextUser) => setActive(nextUser.role === 'admin' ? 'ops' : 'home')} />
          <GroupPanel user={user} group={group} />
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
        <span>提交归档：storage/submissions</span>
        <span>公开标签与私有评测集隔离</span>
        <span>{new Date().toLocaleDateString('zh-CN')}</span>
      </footer>
    </div>
  );
}

export default App;
