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
  final: '最终提交',
  failed: '失败',
  rejected: '已拒绝',
  validated: '已验证'
};

export const modeLabels = {
  public: '正式提交',
  'dry-run': '测试'
};

export const lectureItems = [
  { title: '环境配置与图像基础', detail: '安装必要环境，理解图像读取、像素、通道和基本数据结构。', resourceId: 'lab1' },
  { title: 'OpenCV 基本操作', detail: '读写图像、缩放、绘制图形，并接触级联分类器做人脸检测。', resourceId: 'lab2' },
  { title: '模型训练', detail: '从基础分类网络开始，理解训练循环、损失函数和参数更新。', resourceId: 'lab3' },
  { title: '模型推理', detail: '加载训练好的模型，对输入图像执行预测并取回结果。', resourceId: 'lab4' },
  { title: '端到端流程', detail: '串联读图、人脸检测、Tensor 转换、推理和可视化输出。', resourceId: 'lab5' },
  { title: 'Matplotlib 可视化', detail: '用图表展示样本、预测结果和训练过程。', resourceId: 'lab6' },
  { title: '数据标注的重要性', detail: '分析错误样例，理解标注质量和补充数据对准确率的影响。', resourceId: 'lab7' },
  { title: '扩展主题', detail: '摄像头实时读取、YOLO 检测、数据增强等进阶方向。', resourceId: 'lab8' }
];

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
  home: '人脸检测与表情分类项目',
  leaderboard: '最终排行榜',
  submit: '模型提交',
  dataset: '数据集说明',
  submissionDetail: '提交详情',
  runs: '我的评测记录',
  ops: 'TA 管理台'
};

export const pageCopy = {
  home: 'SI100B Spring 2026 课程项目评测平台。学生可提交 ONNX 模型、查看记录和排行榜。',
  leaderboard: '排行榜分数即最终平台评测分数，按排行榜评测集 Macro-F1 百分制展示。',
  submit: '上传单个 .onnx 文件，平台按 ONNX 输入声明执行固定预处理。',
  dataset: '了解公开小样本、排行榜评测集、ONNX 输入格式和评分口径。',
  submissionDetail: '查看单次提交的队列状态、指标与可视化结果。',
  runs: '查看自己的提交状态、最终分数。',
  ops: 'TA 可查看评测队列、注册学生，并统一维护学生分组。'
};
