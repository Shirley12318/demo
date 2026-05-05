import React, { useState, useEffect } from 'react';
import { Users, MessageSquare, BookOpen, AlertTriangle, Newspaper, ArrowLeft } from 'lucide-react';

function DataOverview({ onBack, username }) {
  const [overviewData, setOverviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchOverviewData();
  }, [username]);

  const fetchOverviewData = async () => {
    if (!username) {
      setError('缺少登录用户信息，请重新登录');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError('');
      const res = await fetch(`http://127.0.0.1:8000/api/overview?username=${encodeURIComponent(username)}`);
      const data = await res.json();

      if (!res.ok) {
        setError(data.detail || data.message || '无权限访问数据概览');
        return;
      }

      if (data.status === 'success') {
        setOverviewData(data.data);
      } else {
        setError(data.message || '获取数据失败');
      }
    } catch (err) {
      setError('网络错误：' + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-slate-600">加载数据中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="text-center text-red-600">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4" />
          <p>{error}</p>
          <button
            onClick={fetchOverviewData}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            重新加载
          </button>
        </div>
      </div>
    );
  }

  const data = overviewData || {};
  const stats = data.stats || {};
  const recentQuestions = data.recent_questions || [];
  const riskMapping = data.risk_mapping || [];
  const newsTitles = data.news_titles || [];
  const topics = data.topics || [];
  const users = data.users || [];

  return (
    <div className="h-full bg-gradient-to-br from-slate-50 to-slate-100 overflow-auto">
      {/* 顶部导航栏 */}
      <div className="sticky top-0 z-20 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-md">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-bold text-slate-800">系统数据概览</h1>
          <button
            onClick={onBack}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg border border-slate-300 text-slate-700 bg-white hover:bg-slate-50 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            返回欢迎页
          </button>
        </div>
      </div>

      {/* 页面内容 */}
      <div className="p-6">
      {/* 顶部统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <StatCard
          icon={Users}
          label="用户总数"
          value={stats.user_count || 0}
          color="bg-blue-50 text-blue-600"
        />
        <StatCard
          icon={MessageSquare}
          label="问题总数"
          value={stats.question_count || 0}
          color="bg-green-50 text-green-600"
        />
        <StatCard
          icon={AlertTriangle}
          label="风险类型"
          value={stats.risk_category_count || 0}
          color="bg-red-50 text-red-600"
        />
        <StatCard
          icon={BookOpen}
          label="讨论话题"
          value={stats.topic_count || 0}
          color="bg-amber-50 text-amber-600"
        />
      </div>

      {/* 主要内容区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* 1. 最近提问 */}
        <Section title="最近提问" icon={MessageSquare}>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {recentQuestions.length > 0 ? (
              recentQuestions.map((q, idx) => (
                <div key={idx} className="p-3 bg-slate-50 rounded border-l-2 border-blue-300">
                  <p className="text-sm font-semibold text-slate-700">{q.username}</p>
                  <p className="text-sm text-slate-600 mt-1">{q.user_message}</p>
                  <p className="text-xs text-slate-400 mt-1">{q.created_at}</p>
                </div>
              ))
            ) : (
              <p className="text-slate-400 text-sm text-center py-4">暂无提问</p>
            )}
          </div>
        </Section>

        {/* 2. 风险匹配 */}
        <Section title="风险匹配" icon={AlertTriangle}>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {riskMapping.length > 0 ? (
              riskMapping.map((risk, idx) => (
                <div key={idx} className="p-3 bg-slate-50 rounded border-l-2 border-red-300">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-slate-700">{risk.label}</p>
                    <span className={`text-xs px-2 py-1 rounded ${
                      risk.level === 'high' ? 'bg-red-100 text-red-700' :
                      risk.level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {risk.level === 'high' ? '高风险' : risk.level === 'medium' ? '中风险' : '低风险'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">编码: {risk.code}</p>
                </div>
              ))
            ) : (
              <p className="text-slate-400 text-sm text-center py-4">暂无风险类型</p>
            )}
          </div>
        </Section>
      </div>

      {/* 新闻标题 */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
          <Newspaper className="w-5 h-5 mr-2 text-amber-500" />
          时政新闻
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {newsTitles.length > 0 ? (
            newsTitles.map((news, idx) => (
              <div key={idx} className="p-4 bg-gradient-to-br from-amber-50 to-orange-50 rounded-lg border border-amber-200">
                <p className="font-semibold text-slate-800 text-sm mb-2">{news.title}</p>
                <p className="text-xs text-slate-500">来源: {news.source}</p>
              </div>
            ))
          ) : (
            <p className="text-slate-400 text-sm">暂无新闻</p>
          )}
        </div>
      </div>

      {/* 讨论话题 */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
          <BookOpen className="w-5 h-5 mr-2 text-green-500" />
          讨论话题分类
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {topics.length > 0 ? (
            topics.map((category, idx) => (
              <div key={idx} className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg border border-green-200">
                <p className="font-semibold text-slate-800 mb-2">{category.category}</p>
                <div className="text-sm text-slate-600">
                  <p className="text-xs text-slate-500 mb-1">话题数: {category.topics.length}</p>
                  <div className="flex flex-wrap gap-1">
                    {category.topics.slice(0, 3).map((topic, tidx) => (
                      <span key={tidx} className="text-xs bg-green-200 text-green-800 px-2 py-1 rounded">
                        {topic}
                      </span>
                    ))}
                    {category.topics.length > 3 && (
                      <span className="text-xs text-slate-500">+{category.topics.length - 3}</span>
                    )}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <p className="text-slate-400 text-sm">暂无话题</p>
          )}
        </div>
      </div>

      {/* 用户及其画像 */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
          <Users className="w-5 h-5 mr-2 text-purple-500" />
          用户及其画像
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {users.length > 0 ? (
            users.map((user, idx) => (
              <div key={idx} className="p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                {/* 用户基本信息 */}
                <div className="mb-4">
                  <p className="font-semibold text-slate-800">{user.username}</p>
                  <div className="text-sm text-slate-600 mt-2">
                    <p>身份: {user.identity}</p>
                    <p>年龄: {user.age_group}</p>
                    <p>专业: {user.major}</p>
                  </div>
                </div>

                {/* 用户画像数据展示 */}
                <div className="bg-white rounded p-3 mb-3">
                  <div className="space-y-1">
                    <div className="flex justify-between items-center text-xs">
                      <span>理想信念</span>
                      <span className="font-bold">{user.portrait?.ideal || 80}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="h-full bg-purple-500 rounded-full"
                        style={{ width: `${(user.portrait?.ideal || 80) / 100 * 100}%` }}
                      ></div>
                    </div>

                    <div className="flex justify-between items-center text-xs mt-2">
                      <span>逻辑思维</span>
                      <span className="font-bold">{user.portrait?.logic || 80}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${(user.portrait?.logic || 80) / 100 * 100}%` }}
                      ></div>
                    </div>

                    <div className="flex justify-between items-center text-xs mt-2">
                      <span>实践能力</span>
                      <span className="font-bold">{user.portrait?.practice || 70}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="h-full bg-green-500 rounded-full"
                        style={{ width: `${(user.portrait?.practice || 70) / 100 * 100}%` }}
                      ></div>
                    </div>

                    <div className="flex justify-between items-center text-xs mt-2">
                      <span>心理素质</span>
                      <span className="font-bold">{user.portrait?.psychological || 75}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="h-full bg-yellow-500 rounded-full"
                        style={{ width: `${(user.portrait?.psychological || 75) / 100 * 100}%` }}
                      ></div>
                    </div>

                    <div className="flex justify-between items-center text-xs mt-2">
                      <span>情绪状态</span>
                      <span className="font-bold">{user.portrait?.emotion || 70}</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div
                        className="h-full bg-red-500 rounded-full"
                        style={{ width: `${(user.portrait?.emotion || 70) / 100 * 100}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {/* 标签和需求 */}
                <div className="text-sm">
                  {user.tags && user.tags.length > 0 && (
                    <div className="mb-2">
                      <p className="text-xs font-semibold text-slate-600 mb-1">标签:</p>
                      <div className="flex flex-wrap gap-1">
                        {user.tags.map((tag, tidx) => (
                          <span key={tidx} className="text-xs bg-purple-200 text-purple-800 px-2 py-0.5 rounded">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {user.hidden_needs && user.hidden_needs.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-slate-600 mb-1">隐性需求:</p>
                      <div className="flex flex-wrap gap-1">
                        {user.hidden_needs.map((need, nidx) => (
                          <span key={nidx} className="text-xs bg-pink-200 text-pink-800 px-2 py-0.5 rounded">
                            {need}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          ) : (
            <p className="text-slate-400 text-sm">暂无用户</p>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className={`bg-white rounded-lg shadow-md p-4 border-l-4 ${
      color === 'bg-blue-50 text-blue-600' ? 'border-blue-500' :
      color === 'bg-green-50 text-green-600' ? 'border-green-500' :
      color === 'bg-red-50 text-red-600' ? 'border-red-500' :
      'border-amber-500'
    }`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-600 text-sm">{label}</p>
          <p className={`text-3xl font-bold ${
            color === 'bg-blue-50 text-blue-600' ? 'text-blue-600' :
            color === 'bg-green-50 text-green-600' ? 'text-green-600' :
            color === 'bg-red-50 text-red-600' ? 'text-red-600' :
            'text-amber-600'
          }`}>{value}</p>
        </div>
        <Icon className="w-10 h-10 opacity-30" />
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children }) {
  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center">
        <Icon className="w-5 h-5 mr-2" style={{
          color: title.includes('提问') ? '#3b82f6' :
                 title.includes('风险') ? '#ef4444' :
                 '#8b5cf6'
        }} />
        {title}
      </h2>
      {children}
    </div>
  );
}

export default DataOverview;

