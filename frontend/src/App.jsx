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
  const [selectedSubmissionId, setSelectedSubmissionId] = useState(null);

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
          {active === 'leaderboard' && <Leaderboard rows={leaderboard} admin={user?.role === 'admin'} onDelete={deleteSubmission} />}
          {active === 'submit' && <SubmitPanel user={user} config={config} onCreated={refreshAll} onOpenGuide={() => setActive('dataset')} />}
          {active === 'dataset' && <DatasetGuide resources={resources} onBack={() => setActive('submit')} />}
          {active === 'runs' && (
            <MyRuns
              rows={mine}
              onRefresh={() => loadMine(user)}
              onFinal={markFinal}
              onOpenDetail={(id) => {
                setSelectedSubmissionId(id);
                setActive('submissionDetail');
              }}
            />
          )}
          {active === 'submissionDetail' && (
            <SubmissionDetail
              submissionId={selectedSubmissionId}
              onBack={() => {
                setActive('runs');
                loadMine(user).catch(() => {});
              }}
            />
          )}
          {active === 'ops' && user?.role === 'admin' && (
            <OpsPanel
              queueRows={queue}
              students={students}
              invites={invites}
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
