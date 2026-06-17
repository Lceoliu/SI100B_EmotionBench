import { useEffect, useMemo, useState } from 'react';

import { api, setCsrfToken } from './api.js';
import { adminTab, baseTabs, pageCopy, pageTitles } from './constants.jsx';
import {
  AuthPanel,
  DatasetGuide,
  GroupPanel,
  HomePage,
  Leaderboard,
  MyRuns,
  OpsPanel,
  SubmissionDetail,
  SubmitPanel
} from './pages.jsx';

const footerLinks = [
  {
    href: 'https://github.com/Lceoliu',
    label: 'GitHub',
    icon: 'https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg'
  },
  {
    href: 'https://www.linkedin.com/in/chang-liu-143b303a0/',
    label: 'LinkedIn',
    icon: 'https://upload.wikimedia.org/wikipedia/commons/8/81/LinkedIn_icon.svg'
  },
  {
    href: 'https://lceoliu.github.io/SP26_SI100B_Tutorial/',
    label: 'Tutorial',
    icon: 'https://upload.wikimedia.org/wikipedia/commons/0/0f/Book-icon.svg'
  }
];

function App() {
  const [active, setActive] = useState('home');
  const [user, setUser] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [mine, setMine] = useState([]);
  const [queue, setQueue] = useState([]);
  const [students, setStudents] = useState([]);
  const [invites, setInvites] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [resources, setResources] = useState([]);
  const [group, setGroup] = useState({ group_name: '', mates: [] });
  const [config, setConfig] = useState({});
  const [notice, setNotice] = useState('');
  const [selectedSubmissionId, setSelectedSubmissionId] = useState(null);
  const [detailOrigin, setDetailOrigin] = useState('runs');

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
    try {
      const dashboardPayload = await api('/api/admin/dashboard');
      setDashboard(dashboardPayload);
    } catch {
      setDashboard(null);
    }
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
      setDashboard(null);
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
      await api(`/api/admin/students/${userId}/controls`, {
        method: 'PATCH',
        body: JSON.stringify({ disabled })
      });
      await loadAdmin(user);
      setNotice(disabled ? '账号已禁用' : '账号已启用');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function updateStudentControls(userId, controls) {
    try {
      await api(`/api/admin/students/${userId}/controls`, {
        method: 'PATCH',
        body: JSON.stringify(controls)
      });
      await loadPublic();
      await loadAdmin(user);
      setNotice('学生控制已更新');
    } catch (err) {
      setNotice(err.message);
    }
  }

  async function updateSettings(form) {
    try {
      const payload = await api('/api/admin/settings', {
        method: 'PATCH',
        body: JSON.stringify(form)
      });
      setConfig(payload.config || {});
      await loadPublic();
      await loadAdmin(user);
      setNotice('系统设置已保存');
      return true;
    } catch (err) {
      setNotice(err.message);
      return false;
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

  async function exportLeaderboardCsv() {
    try {
      const response = await fetch('/api/admin/leaderboard.csv', { credentials: 'same-origin' });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `导出失败：${response.status}`);
      }
      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition') || '';
      const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
      const filename = filenameMatch?.[1] || `emotion-bench-leaderboard-${new Date().toISOString().slice(0, 10)}.csv`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice('排行榜 CSV 已开始下载');
    } catch (err) {
      setNotice(err.message);
    }
  }

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
              <h1>{pageTitles[active]}</h1>
              <p>{pageCopy[active]}</p>
            </div>
            <button className="button secondary" onClick={refreshAll}>刷新</button>
          </div>

          {notice && <div className="notice">{notice}</div>}
          {active === 'home' && <HomePage resources={resources} />}
          {active === 'leaderboard' && (
            <Leaderboard
              rows={leaderboard}
              user={user}
              admin={user?.role === 'admin'}
              onDelete={deleteSubmission}
              onExportCsv={exportLeaderboardCsv}
            />
          )}
          {active === 'submit' && <SubmitPanel user={user} config={config} onCreated={refreshAll} onOpenGuide={() => setActive('dataset')} />}
          {active === 'dataset' && <DatasetGuide resources={resources} onBack={() => setActive('submit')} />}
          {active === 'runs' && (
            <MyRuns
              rows={mine}
              onRefresh={() => loadMine(user)}
              onFinal={markFinal}
              onOpenDetail={(id) => {
                setSelectedSubmissionId(id);
                setDetailOrigin('runs');
                setActive('submissionDetail');
              }}
            />
          )}
          {active === 'submissionDetail' && (
            <SubmissionDetail
              submissionId={selectedSubmissionId}
              adminView={detailOrigin === 'ops' && user?.role === 'admin'}
              backLabel={detailOrigin === 'ops' ? '返回管理台' : '返回我的记录'}
              onBack={() => {
                setActive(detailOrigin);
                if (detailOrigin === 'ops') loadAdmin(user).catch(() => {});
                else loadMine(user).catch(() => {});
              }}
            />
          )}
          {active === 'ops' && user?.role === 'admin' && (
            <OpsPanel
              queueRows={queue}
              students={students}
              invites={invites}
              config={config}
              dashboard={dashboard}
              onSaveGroup={saveGroup}
              onToggleDisabled={toggleDisabled}
              onUpdateControls={updateStudentControls}
              onResetPassword={resetPassword}
              onCreateInvite={createInvite}
              onDeleteInvite={deleteInvite}
              onDeleteSubmission={deleteSubmission}
              onOpenSubmissionDetail={(id) => {
                setSelectedSubmissionId(id);
                setDetailOrigin('ops');
                setActive('submissionDetail');
              }}
              onSaveSettings={updateSettings}
              onRefreshDashboard={() => loadAdmin(user)}
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
              <div><dt>最终提交截止</dt><dd>{deadlineDisplay(config.final_pick_deadline)}</dd></div>
              <div><dt>倒计时</dt><dd>{deadlineText(config.final_pick_deadline)}</dd></div>
            </dl>
          </section>
        </aside>
      </main>

      <footer className="statusbar">
        <span>© 2026 Chang LIU · Licensed under Apache-2.0</span>
        <nav className="footer-links" aria-label="项目链接">
          {footerLinks.map((link) => (
            <a key={link.href} href={link.href} target="_blank" rel="noreferrer" aria-label={link.label}>
              <img className="footer-icon" src={link.icon} alt="" loading="lazy" aria-hidden="true" />
              <span>{link.label}</span>
            </a>
          ))}
        </nav>
      </footer>
    </div>
  );
}

function deadlineText(value) {
  if (!value || String(value).includes('XX')) return '未设置';
  const end = new Date(value).getTime();
  if (!Number.isFinite(end)) return '未设置';
  const diff = end - Date.now();
  if (diff <= 0) return '已截止';
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const minutes = Math.floor((diff % 3600000) / 60000);
  if (days > 0) return `还剩 ${days} 天 ${hours} 小时`;
  if (hours > 0) return `还剩 ${hours} 小时 ${minutes} 分钟`;
  return `还剩 ${Math.max(1, minutes)} 分钟`;
}

function deadlineDisplay(value) {
  if (!value || String(value).includes('XX')) return '未设置';
  const end = new Date(value);
  if (!Number.isFinite(end.getTime())) return '未设置';
  return value;
}

export default App;
