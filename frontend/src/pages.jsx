import {
  Activity,
  ArrowLeft,
  Ban,
  BookOpen,
  ClipboardCheck,
  Database,
  Download,
  ExternalLink,
  FileArchive,
  KeyRound,
  LogIn,
  LogOut,
  Plus,
  RotateCw,
  ShieldCheck,
  Trash2,
  UploadCloud
} from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { api, setCsrfToken } from './api.js';
import { DataTable, StatusChip } from './components.jsx';
import { datasetExamples, lectureItems, modeLabels, statusLabels } from './constants.jsx';
import { fmtParams, fmtScore, fmtTime } from './formatters.js';

function resourceMapFrom(resources) {
  const next = new Map();
  resources.forEach((item) => next.set(item.id, item));
  return next;
}

export function HomePage({ resources }) {
  const resourceMap = useMemo(() => resourceMapFrom(resources), [resources]);
  const projectRules = resourceMap.get('project-rules');
  const codeFramework = resourceMap.get('student-kit');

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
              本项目为 SI100B 课程Project 人脸检测与表情分类的评测平台。用户可以提交模型并查看最终排行榜结果。
            </p>
          </div>
          <ol className="process-list">
            <li>
              <span>课程教师</span>
              <span className="ta-line">
                <a href="https://sist.shanghaitech.edu.cn/lzh/main.htm" target="_blank" rel="noreferrer">李正浩</a>
              </span>
            </li>
            <li>
              <span>TA</span>
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
          {codeFramework?.available && (
            <a className="resource-link" href={codeFramework.download_url}>
              <Download size={18} />
              <span>代码框架与样本数据集</span>
            </a>
          )}
          <div className="resource-note">
            <strong>项目评分</strong>
            <p>
              课程project评分包含参与与 checkpoint、bonus，以及最终提交的文字报告。平台评测只负责模型提交、最终排行榜和最终提交记录。完整规则请查看{' '}
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

export function DatasetGuide({ resources, onBack }) {
  const resourceMap = useMemo(() => resourceMapFrom(resources), [resources]);
  const codeFramework = resourceMap.get('student-kit');
  const projectRules = resourceMap.get('project-rules');

  return (
    <div className="home-stack">
      <section className="window">
        <header className="window-bar">
          <span>数据集与评测规则</span>
          <button className="bar-action" onClick={onBack}>
            <ArrowLeft size={14} /> 返回提交模型
          </button>
        </header>
        <div className="guide-layout">
          <div>
            <h2>输入格式与类别顺序</h2>
            <p>
              测试平台会把每张图读取为 RGB，resize 到 <code>224×224</code>，再做 ImageNet mean/std 归一化。
              即使训练集只有灰度图，你的提交模型也必须能接收 <code>[B, 3, 224, 224]</code> 的输入Tensor。
            </p>
            <div className="class-strip" aria-label="类别顺序">
              {datasetExamples.map((item, index) => (
                <span key={item.label}><strong>{index}</strong>{item.label}<small>{item.zh}</small></span>
              ))}
            </div>
          </div>
          <div className="rule-sheet guide-facts">
            <dl>
              <div><dt>公开小样本</dt><dd>70 张</dd></div>
              <div><dt>排行榜评测集</dt><dd>约 1k 张</dd></div>
              <div><dt>显示分数</dt><dd>Macro-F1 × 100</dd></div>
              <div><dt>图像通道</dt><dd>RGB</dd></div>
            </dl>
          </div>
        </div>
      </section>

      <section className="window">
        <header className="window-bar">
          <span>样例展示</span>
          <small>来自公开小样本，仅用于理解格式</small>
        </header>
        <div className="example-grid">
          {datasetExamples.map((item, index) => {
            const resource = resourceMap.get(item.resourceId);
            return (
              <figure className="example-tile" key={item.label}>
                {resource?.available ? (
                  <img src={`${resource.download_url}?v=${resource.size || 0}`} alt={`${item.zh} / ${item.label} 样例`} loading="lazy" />
                ) : (
                  <div className="example-placeholder">{index}</div>
                )}
                <figcaption>
                  <strong>{index}. {item.label}</strong>
                  <span>{item.zh}</span>
                </figcaption>
              </figure>
            );
          })}
        </div>
      </section>

      <section className="window">
        <header className="window-bar">
          <span>提交建议</span>
          <small>让本地测试与服务器更接近</small>
        </header>
        <div className="guide-notes">
          <div>
            <strong>不要把 70 张小样本当作排行榜测试集</strong>
            <p>它只用于检查读取、类别顺序和提交流程。最终排行榜使用的是排行榜评测集，不公开标签和图片。</p>
          </div>
          <div>
            <strong>注意灰度训练与 RGB 评测的差异</strong>
            <p>如果你用 FER2013 训练，可以在训练时显式复制到三通道，或在模型前几层中处理 RGB 到灰度/特征的映射。</p>
          </div>
          <div>
            <strong>合理使用数据增强和验证集</strong>
            <p>轻微裁切、翻转、旋转、亮度/对比度扰动通常可以提升模型能力；请优先检查每类 F1，而不是只看 accuracy。</p>
          </div>
        </div>
        <div className="guide-downloads">
          {codeFramework?.available && (
            <a className="download-link" href={codeFramework.download_url}>
              <Download size={15} />
              <span>下载代码框架和样本数据集</span>
            </a>
          )}
          {projectRules?.available && (
            <a className="download-link" href={projectRules.download_url}>
              <Download size={15} />
              <span>下载项目评分规则</span>
            </a>
          )}
        </div>
      </section>
    </div>
  );
}

export function AuthPanel({ user, onSession, onAfterLogin }) {
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

export function GroupPanel({ user, group, onProfileUpdate }) {
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

export function Leaderboard({ rows, admin, onDelete }) {
  const columns = [
    { key: 'rank', label: '#', render: (row) => <strong>{row.rank}</strong> },
    { key: 'display_name', label: '队伍/姓名' },
    { key: 'group_name', label: '小组', render: (row) => row.group_name || '—' },
    { key: 'public_score', label: '最终分数', render: (row) => <strong>{fmtScore(row.public_score)}</strong> },
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
        <span>最终排行榜</span>
        <small>按排行榜评测集 Macro-F1 排序，显示为百分制</small>
      </header>
      <DataTable columns={columns} rows={rows} empty="暂时还没有通过最终评测的提交。" />
    </section>
  );
}

export function SubmitPanel({ user, config, onCreated, onOpenGuide }) {
  const [file, setFile] = useState(null);
  const [mode, setMode] = useState('public');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [frameworkConfirmed, setFrameworkConfirmed] = useState(false);

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
    if (!frameworkConfirmed) {
      const ok = window.confirm('提交前请确认：本次 submission.zip 使用了平台提供的代码框架生成，并已在本地运行 python bench.py check 或测试流程。是否继续提交？');
      if (!ok) {
        setError('请先使用代码框架完成本地检查后再提交。');
        return;
      }
      setFrameworkConfirmed(true);
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
              <p>ZIP 内必须包含 <code>model.py</code> 和 <code>model.safetensors</code>。请使用我们提供的代码框架修改、测试、打包和提交。第一次提交建议先测试：测试会进入真实环境检查，不计分、不占每日配额。</p>
              <button type="button" className="inline-guide-link" onClick={onOpenGuide}>
                <BookOpen size={15} />
                查看数据集说明、样例与代码框架下载
              </button>
            </div>
          </div>
          <label className="file-input">
            <FileArchive size={20} />
            <span>{file ? file.name : '选择 submission.zip'}</span>
            <input type="file" accept=".zip" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </label>
          <div className="segmented mode-select">
            <button type="button" className={mode === 'public' ? 'active' : ''} onClick={() => setMode('public')}>
              正式提交
            </button>
            <button type="button" className={mode === 'dry-run' ? 'active' : ''} onClick={() => setMode('dry-run')}>
              先测试
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

export function MyRuns({ rows, onRefresh, onFinal, onOpenDetail }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'filename', label: '文件' },
    { key: 'mode', label: '模式', render: (row) => modeLabels[row.mode] || row.mode || '正式提交' },
    { key: 'status', label: '状态', render: (row) => <StatusChip status={row.status} /> },
    { key: 'public_score', label: '最终分数', render: (row) => fmtScore(row.public_score) },
    { key: 'param_count', label: '参数量', render: (row) => fmtParams(row.param_count) },
    { key: 'created_at', label: '创建时间', render: (row) => fmtTime(row.created_at) },
    {
      key: 'detail',
      label: '详情',
      render: (row) => (
        <button className="link-button" onClick={() => onOpenDetail(row.id)}>
          查看详情
        </button>
      )
    },
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

function averageMetric(score, key) {
  const values = Object.values(score?.per_class || {})
    .map((item) => Number(item?.[key]))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function metricText(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${(Number(value) * 100).toFixed(1)}`;
}

function pickPrimaryScore(scores) {
  return scores.find((score) => score.split === 'final') || scores.find((score) => score.split === 'public') || scores[0] || null;
}

export function SubmissionDetail({ submissionId, onBack }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function loadReport() {
    if (!submissionId) return;
    setBusy(true);
    setError('');
    try {
      const payload = await api(`/api/me/report/${submissionId}`);
      setReport(payload);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadReport();
  }, [submissionId]);

  const submission = report?.submission;
  const score = pickPrimaryScore(report?.scores || []);
  const meanRecall = averageMetric(score, 'recall');
  const meanPrecision = averageMetric(score, 'precision');
  const perClass = Object.entries(score?.per_class || {});
  const running = ['queued', 'running'].includes(submission?.status);

  return (
    <div className="home-stack">
      <section className="window">
        <header className="window-bar">
          <span>提交 #{submissionId}</span>
          <div className="inline-actions">
            <button className="bar-action" onClick={loadReport} disabled={busy}>
              <RotateCw size={14} /> 刷新
            </button>
            <button className="bar-action" onClick={onBack}>
              <ArrowLeft size={14} /> 返回我的记录
            </button>
          </div>
        </header>
        {error && <p className="form-error">{error}</p>}
        <div className="detail-summary">
          <div className="detail-status">
            <StatusChip status={submission?.status || 'queued'} />
            <strong>{running ? '评测进行中' : submission?.status === 'passed' || submission?.status === 'final' ? '评测已完成' : '等待结果'}</strong>
            <p>{submission?.message || '正在同步提交状态。'}</p>
          </div>
          <div className="detail-score">
            <strong>{metricText(score?.macro_f1)}</strong>
            <span>总分 / Macro-F1</span>
            <small>
              Accuracy {metricText(score?.accuracy)} · Recall {metricText(meanRecall)} · Precision {metricText(meanPrecision)}
            </small>
          </div>
        </div>
      </section>

      <section className="window">
        <header className="window-bar">
          <span>指标详情</span>
          <small>{score ? `${score.split} split` : '评测完成后显示'}</small>
        </header>
        {score ? (
          <div className="metric-grid">
            <div><dt>Macro-F1</dt><dd>{metricText(score.macro_f1)}</dd></div>
            <div><dt>Accuracy</dt><dd>{metricText(score.accuracy)}</dd></div>
            <div><dt>平均 Recall</dt><dd>{metricText(meanRecall)}</dd></div>
            <div><dt>置信区间</dt><dd>{metricText(score.ci_low)} - {metricText(score.ci_high)}</dd></div>
          </div>
        ) : (
          <p className="empty-cell">评测完成后，这里会显示总分、accuracy、recall 和置信区间。</p>
        )}
      </section>

      {score && (
        <section className="window">
          <header className="window-bar">
            <span>逐类 F1</span>
            <small>用于定位类别短板</small>
          </header>
          <div className="class-bars">
            {perClass.map(([label, item]) => {
              const value = Number(item.f1 || 0);
              return (
                <div className="class-bar" key={label}>
                  <span>{label}</span>
                  <div><i style={{ width: `${Math.max(2, value * 100)}%` }} /></div>
                  <strong>{metricText(value)}</strong>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="window">
        <header className="window-bar">
          <span>混淆矩阵</span>
          <small>评测彻底完成后生成</small>
        </header>
        {score?.confusion_url ? (
          <div className="confusion-panel">
            <img src={`${score.confusion_url}?v=${encodeURIComponent(score.updated_at || '')}`} alt="混淆矩阵" />
          </div>
        ) : (
          <p className="empty-cell">暂无混淆矩阵图片。排队、运行中或历史提交未生成图片时会显示此提示。</p>
        )}
      </section>
    </div>
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

export function OpsPanel({ queueRows, students, invites, onSaveGroup, onToggleDisabled, onResetPassword, onCreateInvite, onDeleteInvite, onDeleteSubmission }) {
  const columns = [
    { key: 'id', label: 'ID' },
    { key: 'email', label: '邮箱' },
    { key: 'display_name', label: '姓名/队名' },
    { key: 'group_name', label: '小组', render: (row) => row.group_name || '—' },
    { key: 'mode', label: '模式', render: (row) => modeLabels[row.mode] || row.mode || '正式提交' },
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
          <span><Activity size={15} /> 最终评测：排行榜评测集</span>
        </div>
        <DataTable columns={columns} rows={queueRows} empty="暂无评测队列记录。" />
      </section>
      <StudentManager students={students} onSaveGroup={onSaveGroup} onToggleDisabled={onToggleDisabled} onResetPassword={onResetPassword} />
      <InviteManager invites={invites} onCreateInvite={onCreateInvite} onDeleteInvite={onDeleteInvite} />
    </div>
  );
}
