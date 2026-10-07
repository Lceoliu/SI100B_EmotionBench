import { Home, ListChecks, ShieldCheck, Table2, UploadCloud } from 'lucide-react';

export const baseTabs = [
  { id: 'home', label: '主页', icon: Home },
  { id: 'leaderboard', label: '排行榜', icon: Table2 },
  { id: 'submit', label: '提交模型', icon: UploadCloud },
  { id: 'runs', label: '我的记录', icon: ListChecks }
];

export const adminTab = { id: 'ops', label: 'TA 管理', icon: ShieldCheck };

export const statusLabels = {
  queued: '排队中',
  running: '运行中',
  passed: '已通过',
  failed: '模型失败',
  error: '系统错误',
  rejected: '已拒绝',
  validated: '已验证'
};

export const auditActionLabels = {
  'settings.update': '修改系统设置',
  'submission.delete': '删除提交',
  'submission.rejudge': '重新评测',
  'submission.rejudge_errors': '批量重评系统错误',
  'student.controls': '修改学生控制',
  'student.reset_password': '重置学生密码',
  'student.reset_quota': '刷新小组次数',
  'group.assign': 'TA 修改分组',
  'group.bulk_assign': '批量分组',
  'group.self_change': '学生修改小组',
  'invite.create': '添加邀请码',
  'invite.delete': '删除邀请码',
  'user.register': '新用户注册',
  'password.change': '修改密码'
};

export const auditFieldLabels = {
  quota_per_day: '每日次数',
  final_pick_deadline: '截止时间',
  freeze_leaderboard: '冻结排行榜',
  disabled: '禁用账号',
  submit_disabled: '暂停提交',
  leaderboard_hidden: '隐藏榜单',
  previous_status: '原状态',
  previous_score: '原分数',
  members: '成员',
  ids: '提交',
  owner: '提交者',
  group: '小组',
  status: '状态',
  score: '分数',
  label: '说明',
  invite_code: '邀请码',
  changes: '变更'
};

export const modeLabels = {
  public: '正式提交',
  'dry-run': '测试'
};

export const datasetExamples = [
  { label: 'angry', zh: '愤怒', resourceId: 'example-angry' },
  { label: 'disgust', zh: '厌恶', resourceId: 'example-disgust' },
  { label: 'fear', zh: '恐惧', resourceId: 'example-fear' },
  { label: 'happy', zh: '高兴', resourceId: 'example-happy' },
  { label: 'neutral', zh: '中性', resourceId: 'example-neutral' },
  { label: 'sad', zh: '悲伤', resourceId: 'example-sad' },
  { label: 'surprise', zh: '惊讶', resourceId: 'example-surprise' }
];

export const pageTitles = {
  home: '课程项目评测平台',
  leaderboard: '小组排行榜',
  submit: '模型提交',
  dataset: '数据集说明',
  submissionDetail: '提交详情',
  runs: '我的评测记录',
  ops: 'TA 管理台'
};

export const pageCopy = {
  home: '学生可提交 ONNX 模型、查看记录和小组排行榜。',
  leaderboard: '成绩按小组计算：每组取组内成员所有正式提交中的最高 Macro-F1（百分制）排名。',
  submit: '上传单个 .onnx 文件，平台按 ONNX 输入声明执行固定预处理。',
  dataset: '了解公开小样本、排行榜评测集、ONNX 输入格式和评分口径。',
  submissionDetail: '查看单次提交的队列状态、指标与可视化结果。',
  runs: '查看自己的提交状态和分数，以及哪一次是小组最佳。',
  ops: 'TA 可查看评测队列、注册学生，并统一维护学生分组。'
};
