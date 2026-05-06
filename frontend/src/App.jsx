import React, { useEffect, useRef, useState } from 'react';
import * as echarts from 'echarts';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import userAvatar from './assets/user-avatar.svg';
import aiAvatar from './assets/ai-avatar.svg';
import DataOverview from './DataOverview';

// 从环境变量读取后端基础地址，默认使用线上 Railway 地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://demo-production-d6aa.up.railway.app';

function MarkdownMessage({ content }) {
    return (
        <div className="text-left text-[15px] leading-7 wrap-break-word text-inherit">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeSanitize]}
                components={{
                    p: ({ children }) => (
                        <p className="my-2 first:mt-0 last:mb-0 [&>strong:first-child]:text-[16px] [&>strong:first-child]:font-semibold [&>strong:first-child]:tracking-[0.01em]">
                            {children}
                        </p>
                    ),
                    ul: ({ children }) => <ul className="my-2 list-disc pl-6 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="my-2 list-decimal pl-6 space-y-1">{children}</ol>,
                    li: ({ children }) => (
                        <li className="marker:text-gray-500 [&>strong:first-child]:text-[15.5px] [&>strong:first-child]:font-semibold">
                            {children}
                        </li>
                    ),
                    strong: ({ children }) => <strong className="font-bold text-inherit">{children}</strong>,
                    em: ({ children }) => <em className="italic">{children}</em>,
                    h1: ({ children }) => <h1 className="mt-3 mb-2 text-xl font-bold text-gray-900">{children}</h1>,
                    h2: ({ children }) => <h2 className="mt-3 mb-2 text-lg font-bold text-gray-900">{children}</h2>,
                    h3: ({ children }) => <h3 className="mt-3 mb-2 text-base font-bold text-gray-900">{children}</h3>,
                    h4: ({ children }) => <h4 className="mt-3 mb-2 text-[15px] font-semibold text-gray-900">{children}</h4>,
                    h5: ({ children }) => <h5 className="mt-2 mb-1.5 text-[14.5px] font-semibold text-gray-900">{children}</h5>,
                    h6: ({ children }) => <h6 className="mt-2 mb-1 text-[14px] font-semibold tracking-[0.01em] text-gray-800">{children}</h6>,
                    blockquote: ({ children }) => (
                        <blockquote className="my-3 border-l-4 border-red-300 bg-red-50/70 px-4 py-2 italic text-gray-700">
                            {children}
                        </blockquote>
                    ),
                    a: ({ href, children }) => (
                        <a
                            href={href}
                            target="_blank"
                            rel="noreferrer"
                            className="text-red-700 underline decoration-red-300 underline-offset-2"
                        >
                            {children}
                        </a>
                    ),
                    code: ({ inline, children }) =>
                        inline ? (
                            <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-[13px] text-red-700">{children}</code>
                        ) : (
                            <code className="block overflow-x-auto rounded-xl bg-stone-900/95 p-4 font-mono text-[13px] leading-6 text-stone-100">
                                {children}
                            </code>
                        ),
                    pre: ({ children }) => <pre className="my-3 overflow-x-auto">{children}</pre>
                }}
            >
                {content || ''}
            </ReactMarkdown>
        </div>
    );
}

function buildMessagesFromHistory(records = []) {
    const historyMessages = [];

    records.forEach(record => {
        historyMessages.push({
            role: 'user',
            content: record.user_message,
            chatId: record.id,
            analysis: {
                hidden_needs: record.user_hidden_needs ? record.user_hidden_needs.split(',').filter(n => n.trim()) : [],
                emotion_score: record.user_emotion_score || 0
            }
        });

        historyMessages.push({
            role: 'ai',
            content: record.ai_reply,
            chatId: record.id,
            aiAnalysis: {
                score: record.ai_reply_score || 0,
                feedback: record.ai_reply_feedback || '',
                selected_model: record.selected_model || '',
                model_comparison: {
                    qwen: {
                        score: record.qwen_score || 0,
                        feedback: ''
                    },
                    deepseek: {
                        score: record.deepseek_score || 0,
                        feedback: ''
                    },
                    kimi: {
                        score: record.kimi_score || 0,
                        feedback: ''
                    }
                }
            }
        });
    });

    return historyMessages;
}

function formatConversationTime(value) {
    if (!value) return '';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';

    return new Intl.DateTimeFormat('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function getNewsBatch(items, pageIndex, batchSize) {
    if (!items.length) return [];

    const normalizedBatchSize = Math.max(batchSize, 1);
    const startIndex = (pageIndex * normalizedBatchSize) % items.length;
    const endIndex = startIndex + normalizedBatchSize;

    if (endIndex <= items.length) {
        return items.slice(startIndex, endIndex);
    }

    return [...items.slice(startIndex), ...items.slice(0, endIndex - items.length)];
}

function formatDiscussionTime(value) {
    if (!value) return '';

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';

    return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function App() {
    const [isLoggedIn, setIsLoggedIn] = useState(false);
    const [hasEnteredChat, setHasEnteredChat] = useState(false);
    const [activeWorkspace, setActiveWorkspace] = useState('chat');
    const [authMode, setAuthMode] = useState("login");
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [loginIdentity, setLoginIdentity] = useState("普通用户");
    const [showPermissions, setShowPermissions] = useState(false);
    const [permissionsAgreed, setPermissionsAgreed] = useState(false);
    const [identity, setIdentity] = useState("大一新生");
    const [ageGroup, setAgeGroup] = useState("20-25岁");
    const [currentMajor, setCurrentMajor] = useState("计算机科学");
    const [customIdentity, setCustomIdentity] = useState("");
    const [customMajor, setCustomMajor] = useState("");
    const [conversations, setConversations] = useState([]);
    const [currentConversationId, setCurrentConversationId] = useState(null);
    const [discussionCategories, setDiscussionCategories] = useState([]);
    const [selectedDiscussionCategory, setSelectedDiscussionCategory] = useState('');
    const [selectedDiscussionTopic, setSelectedDiscussionTopic] = useState('');
    const [discussionPosts, setDiscussionPosts] = useState([]);
    const [discussionTitle, setDiscussionTitle] = useState('');
    const [discussionContent, setDiscussionContent] = useState('');
    const [isDiscussionLoading, setIsDiscussionLoading] = useState(false);
    const [isDiscussionSubmitting, setIsDiscussionSubmitting] = useState(false);
    const [discussionActionPostId, setDiscussionActionPostId] = useState(null);
    const [discussionError, setDiscussionError] = useState('');
    const [dailyNews, setDailyNews] = useState([]);
    const [isNewsLoading, setIsNewsLoading] = useState(false);
    const [newsError, setNewsError] = useState("");
    const [dailyNewsPage, setDailyNewsPage] = useState(0);
    const [recommendedNews, setRecommendedNews] = useState([]);
    const [isRecommendedNewsLoading, setIsRecommendedNewsLoading] = useState(false);
    const [recommendedNewsError, setRecommendedNewsError] = useState("");
    const [recommendedNewsPage, setRecommendedNewsPage] = useState(0);
    const [input, setInput] = useState("");
    const [messages, setMessages] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isCreatingConversation, setIsCreatingConversation] = useState(false);
    const [streamingText, setStreamingText] = useState("");
    const [selectedMessage, setSelectedMessage] = useState(null);
    const [showMessageAnalysis, setShowMessageAnalysis] = useState(false);
    const [selectedAIMessage, setSelectedAIMessage] = useState(null);
    const [showAIAnalysis, setShowAIAnalysis] = useState(false);
    const [userRole, setUserRole] = useState('user');
    const [portrait, setPortrait] = useState({
        ideal: 80,
        logic: 80,
        practice: 70,
        psychological: 75,
        emotion: 70,
        learning_preference: [],
        hidden_needs: [],
        current_major: "未设置"
    });
    const radarRef = useRef(null);
    const radarChartRef = useRef(null);
    const isAdmin = userRole === 'admin';
    const isProfileWorkspace = isLoggedIn && hasEnteredChat && activeWorkspace === 'profile';

    useEffect(() => {
        if (activeWorkspace === 'overview' && !isAdmin) {
            setActiveWorkspace('chat');
        }
    }, [activeWorkspace, isAdmin]);

    useEffect(() => {
        if (!isProfileWorkspace || !radarRef.current) {
            if (radarChartRef.current) {
                radarChartRef.current.dispose();
                radarChartRef.current = null;
            }
            return;
        }

        if (!radarChartRef.current) {
            radarChartRef.current = echarts.init(radarRef.current);
        }
        radarChartRef.current.resize();

        const handleResize = () => {
            if (radarChartRef.current) {
                radarChartRef.current.resize();
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
        };
    }, [isProfileWorkspace]);

    useEffect(() => {
        if (!isProfileWorkspace || !radarChartRef.current) return;

        const safeValue = (value) => (typeof value === 'number' && !Number.isNaN(value) ? value : 0);
        const radarValues = [
            safeValue(portrait.ideal),
            safeValue(portrait.logic),
            safeValue(portrait.practice),
            safeValue(portrait.psychological),
            safeValue(portrait.emotion)
        ];

        radarChartRef.current.setOption({
            tooltip: { trigger: 'item' },
            radar: {
                indicator: [
                    { name: '理想信念', max: 100 },
                    { name: '逻辑思维', max: 100 },
                    { name: '实践能力', max: 100 },
                    { name: '心理素质', max: 100 },
                    { name: '情感状态', max: 100 }
                ],
                splitNumber: 4,
                axisName: { color: '#374151', fontSize: 12 },
                splitLine: { lineStyle: { color: ['#f3f4f6', '#e5e7eb'] } },
                splitArea: { areaStyle: { color: ['#fff7f7', '#ffffff'] } },
                axisLine: { lineStyle: { color: '#e5e7eb' } }
            },
            series: [
                {
                    name: '用户画像',
                    type: 'radar',
                    data: [
                        {
                            value: radarValues,
                            areaStyle: { color: 'rgba(220, 38, 38, 0.18)' },
                            lineStyle: { color: '#dc2626', width: 2 },
                            itemStyle: { color: '#dc2626' }
                        }
                    ]
                }
            ]
        });
    }, [portrait, isProfileWorkspace]);

    useEffect(() => {
        if (!isLoggedIn || hasEnteredChat) return;

        let isCancelled = false;

        const loadDailyNews = async () => {
            setIsNewsLoading(true);
            setNewsError('');

            try {
                const res = await fetch(`${API_BASE_URL}/news/daily?limit=8`);
                const data = await res.json();

                if (isCancelled) return;

                if (data.status === 'success' && data.data?.news) {
                    setDailyNews(data.data.news);
                    setDailyNewsPage(0);
                } else {
                    throw new Error(data.message || '新闻加载失败');
                }
            } catch (err) {
                if (!isCancelled) {
                    setNewsError('今日新闻暂时加载失败，请稍后刷新重试。');
                    setDailyNews([]);
                }
            } finally {
                if (!isCancelled) {
                    setIsNewsLoading(false);
                }
            }
        };

        loadDailyNews();

        return () => {
            isCancelled = true;
        };
    }, [isLoggedIn, hasEnteredChat]);

    useEffect(() => {
        if (!isLoggedIn || hasEnteredChat || !username) return;

        let isCancelled = false;

        const loadRecommendedNews = async () => {
            setIsRecommendedNewsLoading(true);
            setRecommendedNewsError('');

            try {
                const res = await fetch(`${API_BASE_URL}/news/recommended?username=${encodeURIComponent(username)}&limit=6`);
                const data = await res.json();

                if (isCancelled) return;

                if (data.status === 'success' && data.data?.news) {
                    setRecommendedNews(data.data.news);
                    setRecommendedNewsPage(0);
                } else {
                    throw new Error(data.message || '推荐新闻加载失败');
                }
            } catch (err) {
                if (!isCancelled) {
                    setRecommendedNews([]);
                    setRecommendedNewsError('暂时无法生成个性推荐，可先查看实时新闻。');
                }
            } finally {
                if (!isCancelled) {
                    setIsRecommendedNewsLoading(false);
                }
            }
        };

        loadRecommendedNews();

        return () => {
            isCancelled = true;
        };
    }, [isLoggedIn, hasEnteredChat, username]);

    useEffect(() => {
        if (!isLoggedIn) return;

        let isCancelled = false;

        const loadDiscussionCatalog = async () => {
            try {
                const res = await fetch(`${API_BASE_URL}/discussion/topics`);
                const data = await res.json();

                if (isCancelled) return;

                if (data.status === 'success' && data.data?.categories) {
                    const categories = data.data.categories;
                    setDiscussionCategories(categories);
                    setSelectedDiscussionCategory(prev => (
                        categories.some(item => item.category === prev) ? prev : (categories[0]?.category || '')
                    ));
                    setSelectedDiscussionTopic(prev => (
                        categories.some(item => item.topics?.includes(prev)) ? prev : (categories[0]?.topics?.[0] || '')
                    ));
                } else {
                    throw new Error(data.message || '讨论区主题加载失败');
                }
            } catch (err) {
                if (!isCancelled) {
                    setDiscussionCategories([]);
                    setDiscussionError('讨论区主题加载失败，请稍后重试。');
                }
            }
        };

        loadDiscussionCatalog();

        return () => {
            isCancelled = true;
        };
    }, [isLoggedIn]);

    useEffect(() => {
        if (!isLoggedIn || !hasEnteredChat || activeWorkspace !== 'discussion' || !selectedDiscussionTopic) return;

        let isCancelled = false;

        const loadDiscussionPosts = async () => {
            setIsDiscussionLoading(true);
            setDiscussionError('');

            try {
                const res = await fetch(`${API_BASE_URL}/discussion/posts?topic=${encodeURIComponent(selectedDiscussionTopic)}&username=${encodeURIComponent(username)}&limit=50`);
                const data = await res.json();

                if (isCancelled) return;

                if (data.status === 'success' && data.data?.posts) {
                    setDiscussionPosts(data.data.posts);
                } else {
                    throw new Error(data.message || '讨论内容加载失败');
                }
            } catch (err) {
                if (!isCancelled) {
                    setDiscussionPosts([]);
                    setDiscussionError('当前主题讨论内容加载失败，请稍后重试。');
                }
            } finally {
                if (!isCancelled) {
                    setIsDiscussionLoading(false);
                }
            }
        };

        loadDiscussionPosts();

        return () => {
            isCancelled = true;
        };
    }, [activeWorkspace, hasEnteredChat, isLoggedIn, selectedDiscussionTopic]);

    const resetConversationView = () => {
        setMessages([]);
        setInput("");
        setStreamingText("");
        setSelectedMessage(null);
        setShowMessageAnalysis(false);
        setSelectedAIMessage(null);
        setShowAIAnalysis(false);
    };

    const upsertConversation = (conversation) => {
        if (!conversation?.id) return;

        setConversations(prev => {
            const next = prev.filter(item => item.id !== conversation.id);
            return [conversation, ...next];
        });
        setCurrentConversationId(conversation.id);
    };

    const loadConversationMessages = async (conversationId, activeUsername = username) => {
        resetConversationView();
        setCurrentConversationId(conversationId);

        const res = await fetch(
            `${API_BASE_URL}/conversations/${conversationId}/messages?username=${encodeURIComponent(activeUsername)}`,
            { method: 'GET' }
        );
        const data = await res.json();

        if (data.status === 'success' && data.data?.messages) {
            setMessages(buildMessagesFromHistory(data.data.messages));
        } else {
            throw new Error(data.message || '加载会话消息失败');
        }
    };

    const loadConversations = async (activeUsername = username) => {
        const res = await fetch(`${API_BASE_URL}/conversations?username=${encodeURIComponent(activeUsername)}`, {
            method: 'GET'
        });
        const data = await res.json();

        if (data.status === 'success' && data.data?.conversations) {
            const nextConversations = data.data.conversations;
            setConversations(nextConversations);
            return nextConversations;
        }

        throw new Error(data.message || '加载会话列表失败');
    };

    const createConversation = async (activeUsername = username) => {
        setIsCreatingConversation(true);
        try {
            const res = await fetch(`${API_BASE_URL}/conversations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: activeUsername })
            });
            const data = await res.json();

            if (data.status !== 'success' || !data.data?.conversation) {
                throw new Error(data.message || '创建会话失败');
            }

            const conversation = data.data.conversation;
            upsertConversation(conversation);
            resetConversationView();
            return conversation;
        } finally {
            setIsCreatingConversation(false);
        }
    };

    const initializeConversationsAfterLogin = async (activeUsername) => {
        const loadedConversations = await loadConversations(activeUsername);

        if (loadedConversations.length > 0) {
            await loadConversationMessages(loadedConversations[0].id, activeUsername);
        } else {
            setCurrentConversationId(null);
            resetConversationView();
        }
    };

    const handleEnterChat = async () => {
        try {
            if (conversations.length === 0) {
                await createConversation(username);
            } else if (!currentConversationId) {
                await loadConversationMessages(conversations[0].id, username);
            }

            setHasEnteredChat(true);
        } catch (err) {
            alert('进入聊天失败，请稍后重试');
        }
    };

    const handleStartNewChat = async () => {
        if (isLoading || isCreatingConversation) return;

        try {
            await createConversation(username);
        } catch (err) {
            alert('创建新对话失败，请稍后重试');
        }
    };

    const handleSelectConversation = async (conversationId) => {
        if (isLoading || conversationId === currentConversationId) return;

        try {
            await loadConversationMessages(conversationId, username);
        } catch (err) {
            alert('切换对话失败，请稍后重试');
        }
    };

    const handleEnterDiscussion = () => {
        setActiveWorkspace('discussion');
        setHasEnteredChat(true);
    };

    const handleEnterGame = () => {
        setActiveWorkspace('game');
        setHasEnteredChat(true);
    };

    const handleSelectDiscussionCategory = (category) => {
        setSelectedDiscussionCategory(category.category);
        if (category.topics?.length > 0) {
            setSelectedDiscussionTopic(category.topics[0]);
        }
    };

    const handleSelectDiscussionTopic = (topic, categoryName) => {
        setSelectedDiscussionTopic(topic);
        if (categoryName) {
            setSelectedDiscussionCategory(categoryName);
        }
    };

    const handlePublishDiscussionPost = async () => {
        if (!selectedDiscussionTopic) {
            alert('请先选择一个讨论主题');
            return;
        }

        if (!discussionContent.trim()) {
            alert('请输入讨论内容');
            return;
        }

        setIsDiscussionSubmitting(true);
        try {
            const res = await fetch(`${API_BASE_URL}/discussion/posts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username,
                    topic: selectedDiscussionTopic,
                    title: discussionTitle,
                    content: discussionContent
                })
            });
            const data = await res.json();

            if (data.status !== 'success' || !data.data?.post) {
                throw new Error(data.message || '发布失败');
            }

            setDiscussionPosts(prev => [data.data.post, ...prev]);
            setDiscussionTitle('');
            setDiscussionContent('');
            setDiscussionError('');
        } catch (err) {
            alert('发布失败，请稍后重试');
        } finally {
            setIsDiscussionSubmitting(false);
        }
    };

    const syncDiscussionPost = (nextPost) => {
        if (!nextPost?.id) return;

        setDiscussionPosts(prev => prev.map(post => (
            post.id === nextPost.id ? nextPost : post
        )));
    };

    const handleToggleDiscussionLike = async (postId) => {
        setDiscussionActionPostId(postId);
        try {
            const res = await fetch(`${API_BASE_URL}/discussion/posts/${postId}/like`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });
            const data = await res.json();

            if (data.status !== 'success' || !data.data?.post) {
                throw new Error(data.message || '点赞操作失败');
            }

            syncDiscussionPost(data.data.post);
        } catch (err) {
            alert('点赞操作失败，请稍后重试');
        } finally {
            setDiscussionActionPostId(null);
        }
    };

    const handleReportDiscussionPost = async (postId) => {
        setDiscussionActionPostId(postId);
        try {
            const res = await fetch(`${API_BASE_URL}/discussion/posts/${postId}/report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username })
            });
            const data = await res.json();

            if (data.status !== 'success' || !data.data?.post) {
                throw new Error(data.message || '举报失败');
            }

            syncDiscussionPost(data.data.post);
            alert(data.message || '举报已提交');
        } catch (err) {
            alert('举报失败，请稍后重试');
        } finally {
            setDiscussionActionPostId(null);
        }
    };

    const visibleDailyNews = getNewsBatch(dailyNews, dailyNewsPage, 4);
    const visibleRecommendedNews = getNewsBatch(recommendedNews, recommendedNewsPage, 3);
    const currentDiscussionCategory = discussionCategories.find(item => item.category === selectedDiscussionCategory) || discussionCategories[0];
    const currentDiscussionTopics = currentDiscussionCategory?.topics || [];
    const forumAllTopics = Array.from(new Set(discussionCategories.flatMap(item => item.topics || [])));
    const forumHotTopics = [...discussionPosts]
        .sort((a, b) => (b.like_count || 0) - (a.like_count || 0))
        .slice(0, 5);
    const forumRankUsers = Object.values(
        discussionPosts.reduce((acc, post) => {
            const name = post.author || '匿名用户';
            if (!acc[name]) {
                acc[name] = { name, posts: 0, likes: 0 };
            }
            acc[name].posts += 1;
            acc[name].likes += post.like_count || 0;
            return acc;
        }, {})
    )
        .sort((a, b) => (b.likes - a.likes) || (b.posts - a.posts))
        .slice(0, 5);

    const handleRefreshDailyBatch = () => {
        if (dailyNews.length <= 1) return;
        setDailyNewsPage(prev => prev + 1);
    };

    const handleRefreshRecommendedBatch = () => {
        if (recommendedNews.length <= 1) return;
        setRecommendedNewsPage(prev => prev + 1);
    };

    const handleAuth = async () => {
        if (!username || !password) {
            alert("请填写完整账号密码");
            return;
        }
        if (!permissionsAgreed) {
            alert("请先阅读并勾选权限申请");
            return;
        }
        const finalIdentity = identity === "其他" ? customIdentity : identity;
        const finalAgeGroup = ageGroup;
        const finalMajor = currentMajor === "其他" ? customMajor : currentMajor;
        if (authMode === "register") {
            if (identity === "其他" && !finalIdentity.trim()) {
                alert("请填写身份");
                return;
            }
            if (currentMajor === "其他" && !finalMajor.trim()) {
                alert("请填写专业");
                return;
            }
        }
        const endpoint = authMode === "login" ? "/login" : "/register";
        const requestBody = authMode === "login"
            ? { username, password, identity: loginIdentity }
            : { username, password, identity: finalIdentity, age_group: finalAgeGroup, current_major: finalMajor };
        try {
            const res = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            const data = await res.json();
            if (data.status === "success") {
                if (authMode === "login") {
                    setIsLoggedIn(true);
                    setHasEnteredChat(false);
                    setActiveWorkspace('chat');
                    setUserRole(data.data?.role === 'admin' ? 'admin' : 'user');
                    if (data.data && data.data.portrait) {
                        setPortrait(prev => ({ ...prev, ...data.data.portrait }));
                    }

                    try {
                        await initializeConversationsAfterLogin(username);
                    } catch (historyErr) {
                        console.error("加载会话列表失败:", historyErr);
                    }
                } else {
                    alert("注册成功！请切换到登录界面");
                    setAuthMode("login");
                }
            } else {
                alert(data.message);
            }
        } catch (err) {
            alert("连接服务器失败，请检查后端是否启动");
        }
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        let activeConversationId = currentConversationId;
        if (!activeConversationId) {
            try {
                const createdConversation = await createConversation(username);
                activeConversationId = createdConversation.id;
            } catch (err) {
                alert('创建会话失败，请稍后重试');
                return;
            }
        }

        const userMsg = { role: 'user', content: input, analysis: null };
        setMessages(prev => [...prev, userMsg]);
        const currentInput = input;
        const userMsgIndex = messages.length;
        setInput("");
        setIsLoading(true);

        try {
            const res = await fetch(`${API_BASE_URL}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, message: currentInput, conversation_id: activeConversationId })
            });
            const data = await res.json();

            if (data.conversation) {
                upsertConversation(data.conversation);
            }

            const reply = data.reply;
            setStreamingText("");
            let currentIndex = 0;

            if (!reply) {
                setMessages(prev => [...prev, { role: 'ai', content: "⚠️ 未收到有效回复" }]);
                setIsLoading(false);
                return;
            }

            const streamInterval = setInterval(() => {
                if (currentIndex < reply.length) {
                    setStreamingText(reply.substring(0, currentIndex + 1));
                    currentIndex++;
                } else {
                    clearInterval(streamInterval);
                    setMessages(prev => [...prev, {
                        role: 'ai',
                        content: reply,
                        chatId: data.chat_id,
                        aiAnalysis: {
                            score: data.portrait_analysis?.review?.score || 0,
                            feedback: data.portrait_analysis?.review?.feedback || '',
                            selected_model: data.selected_model || '',
                            model_comparison: data.model_comparison || {}
                        }
                    }]);
                    setStreamingText("");
                }
            }, 10);

            if (data.portrait_analysis) {
                setMessages(prev => {
                    const updated = [...prev];
                    if (updated[userMsgIndex]) {
                        updated[userMsgIndex] = {
                            ...updated[userMsgIndex],
                            chatId: data.chat_id,
                            analysis: {
                                hidden_needs: (data.portrait_analysis.dimensions.emotional_need || []).slice(0, 6),
                                emotion_score: data.portrait_analysis.scores.emotional_state ?? 0
                            }
                        };
                    }
                    return updated;
                });

                setPortrait({
                    ideal: data.portrait_analysis.scores.ideal_belief,
                    logic: data.portrait_analysis.scores.logic_thinking,
                    practice: data.portrait_analysis.scores.practice_ability ?? portrait.practice,
                    psychological: data.portrait_analysis.scores.psychological_quality ?? portrait.psychological,
                    emotion: data.portrait_analysis.scores.emotional_state ?? portrait.emotion,
                    learning_preference: (data.portrait_analysis.dimensions.behavior_preference || []).slice(0, 6),
                    hidden_needs: (data.portrait_analysis.dimensions.emotional_need || []).slice(0, 6),
                    current_major: portrait.current_major
                });
            }
        } catch (err) {
            setMessages(prev => [...prev, { role: 'ai', content: "⚠️ 网络连接错误" }]);
        } finally {
            setIsLoading(false);
        }
    };

    if (!isLoggedIn) {
        return (
            <>
                <style>{`
          .login-page{
            min-height:100vh;display:grid;grid-template-columns:480px 1fr;background:#FAF6F0;
            font-family:"PingFang SC","Source Han Sans CN","Microsoft YaHei",sans-serif;
          }
          .login-page *{box-sizing:border-box}
          .login-page h1,.login-page h2,.login-page h3{font-family:"Source Han Serif CN","STSong","SimSun",serif}
          .login-left{
            background:#fff;padding:60px 56px;display:flex;flex-direction:column;
            position:relative;overflow:hidden;
          }
          .login-left::before{
            content:"";position:absolute;top:0;left:0;right:0;height:6px;
            background:linear-gradient(90deg,#8B1A1A,#C8102E,#D4A017);
          }
          .login-brand-blk{display:flex;align-items:center;gap:12px;margin-bottom:60px}
          .login-brand-blk .logo-circle{
            width:48px;height:48px;border-radius:50%;background:#8B1A1A;
            display:flex;align-items:center;justify-content:center;
          }
          .login-brand-blk .logo-circle svg{width:28px;height:28px;fill:#D4A017}
          .login-brand-blk h2{font-size:22px;color:#8B1A1A;letter-spacing:3px;margin:0}
          .login-brand-blk .sub{font-size:11px;color:rgba(0,0,0,.42);letter-spacing:1px;margin-top:2px}

          .login-welcome{margin-bottom:36px}
          .login-welcome h1{font-size:28px;color:#1A1A1A;margin:0 0 8px}
          .login-welcome p{font-size:13px;color:rgba(0,0,0,.65);font-style:italic;margin:0}

          .login-form{display:flex;flex-direction:column;gap:18px}
          .form-item label{display:block;font-size:12.5px;color:rgba(0,0,0,.65);margin-bottom:6px;font-weight:500}
          .form-item input,.form-item select{
            width:100%;padding:12px 14px;border:1px solid rgba(139,26,26,.12);
            border-radius:6px;font-size:13.5px;background:#FAF6F0;transition:all .15s;font-family:inherit;
          }
          .form-item input:focus,.form-item select:focus{outline:none;border-color:#C8102E;background:#fff}
          .form-row{display:flex;justify-content:space-between;align-items:center;font-size:12px;margin-top:-4px}
          .form-row .checkbox{display:flex;align-items:center;gap:6px;color:rgba(0,0,0,.65);cursor:pointer}
          .form-row .checkbox input{accent-color:#C8102E}
          .form-row button{color:#C8102E;text-decoration:none;background:none;border:none;cursor:pointer;padding:0}
          .form-row button:hover{text-decoration:underline}

          .permission-row{font-size:12px;color:rgba(0,0,0,.65);margin-top:-8px;display:flex;align-items:center;gap:8px}
          .permission-row input{accent-color:#C8102E}
          .permission-row button{color:#C8102E;background:none;border:none;padding:0;cursor:pointer;font-weight:600}
          .permission-row button:hover{text-decoration:underline}

          .login-btn{
            padding:13px;background:#C8102E;color:#fff;border:none;border-radius:6px;
            font-size:14px;font-weight:600;cursor:pointer;transition:all .15s;
            font-family:inherit;letter-spacing:2px;
          }
          .login-btn:hover{background:#8B1A1A}
          .login-btn:disabled{background:#ccc;cursor:not-allowed}
          .form-switch{font-size:12px;text-align:center;margin-top:8px;color:rgba(0,0,0,.65)}
          .form-switch button{color:#C8102E;text-decoration:none;background:none;border:none;cursor:pointer}
          .form-switch button:hover{text-decoration:underline}

          .login-divider{display:flex;align-items:center;gap:14px;margin:24px 0 16px;color:rgba(0,0,0,.42);font-size:11px}
          .login-divider::before,.login-divider::after{content:"";flex:1;height:1px;background:rgba(139,26,26,.12)}
          .login-alt{display:flex;justify-content:center;gap:16px}
          .login-alt .alt-btn{
            width:44px;height:44px;border-radius:50%;background:#F0E9DC;
            display:flex;align-items:center;justify-content:center;cursor:pointer;
            font-size:14px;color:rgba(0,0,0,.65);transition:all .15s;border:1px solid rgba(139,26,26,.12);font-weight:600;
          }
          .login-alt .alt-btn:hover{background:#C8102E;color:#fff;border-color:#C8102E}

          .login-footer{margin-top:auto;padding-top:30px;font-size:11px;color:rgba(0,0,0,.42);text-align:center}

          .login-right{
            background:linear-gradient(135deg,#8B1A1A,#C8102E);
            position:relative;overflow:hidden;display:flex;flex-direction:column;
            justify-content:center;align-items:center;padding:60px;color:#fff;
          }
          .login-right::before{
            content:"";position:absolute;inset:0;
            background-image:
              radial-gradient(circle at 30% 30%, rgba(212,160,23,0.15), transparent 40%),
              radial-gradient(circle at 70% 70%, rgba(255,255,255,0.05), transparent 50%);
          }
          .deco-star{
            position:absolute;background:rgba(212,160,23,.08);
            clip-path:polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);
          }
          .deco-star.s1{top:8%;right:10%;width:120px;height:120px;transform:rotate(15deg)}
          .deco-star.s2{bottom:12%;left:8%;width:160px;height:160px;transform:rotate(-20deg)}
          .deco-star.s3{top:50%;right:30%;width:80px;height:80px;opacity:.5}

          .login-hero{position:relative;z-index:1;text-align:center;max-width:520px;padding:40px;display:flex;flex-direction:column;justify-content:center}
          .hero-title h2 {font-size: 28px;color: #1e293b;margin-bottom: 8px;margin-top:0}
          .hero-title p {color: #64748b;margin-bottom: 30px;margin-top:0}
          .card-grid {
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            grid-template-rows: auto auto auto;
            grid-template-areas:
              "left  right-top"
              "left  right-bottom"
              "bottom-left bottom-right";
            gap: 16px;
            height: 100%;
          }
          .card {
            border-radius: 16px;
            padding: 24px;
            color: #333;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            background: #ffffff;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            border: 1px solid rgba(255,255,255,0.6);
          }
          .card:hover {transform: translateY(-5px);box-shadow: 0 12px 30px rgba(0,0,0,0.1)}
          .pos-left {grid-area: left;background: linear-gradient(135deg, #e0f2fe 0%, #ffffff 100%);text-align: left}
          .pos-right-top {grid-area: right-top}
          .pos-right-bottom {grid-area: right-bottom}
          .pos-bottom-left {grid-area: bottom-left;flex-direction: row;align-items: center;gap: 15px;height:180px;padding:0;display:flex}
          .pos-bottom-right {grid-area: bottom-right;flex-direction: row;align-items: center;gap: 15px;height:180px;padding:0;display:flex}
          .card-header {display: flex;justify-content: space-between;align-items: center;margin-bottom: 12px}
          .card-icon {font-size: 28px}
          .card h3 {font-size: 20px;font-weight: 700;margin: 0 0 8px 0;color: #1e293b}
          .card p {font-size: 13px;color: #64748b;line-height: 1.5;margin: 0}
          .card-tag {font-size: 10px;font-weight: 700;letter-spacing: 1px;color: #94a3b8;text-transform: uppercase}
          .mock-input {margin-top: 20px;padding: 10px 16px;background: rgba(255,255,255,0.8);border-radius: 8px;font-size: 13px;color: #94a3b8;border: 1px solid #e2e8f0;align-self: flex-start}
          .custom-content {display: flex;align-items: center;height: 100%;padding: 20px}
          .vertical-title {display: flex;flex-direction: column;align-items: center;justify-content: center;margin-right: 25px;border-right: 1px solid #eee;padding-right: 20px;color: #1e293b}
          .vertical-title .icon {font-size: 24px;margin-bottom: 5px}
          .vertical-title .text {font-size: 20px;font-weight: 800;letter-spacing: 2px;writing-mode: vertical-rl;text-orientation: upright}
          .news-list {list-style: none;padding: 0;margin: 0;text-align: left;flex: 1}
          .news-list li {font-size: 14px;color: #475569;margin-bottom: 12px;cursor: pointer;transition: color 0.2s}
          .news-list li:hover {color: #3b82f6}
          .tag-group {display: flex;flex-wrap: wrap;gap: 10px;align-content: center}
          .tag {background-color: #f1f5f9;color: #475569;padding: 6px 12px;border-radius: 6px;font-size: 13px;font-weight: 500;transition: all 0.2s;cursor: pointer}
          .tag:hover {background-color: #3b82f6;color: white;transform: translateY(-2px)}

          @media (max-width:900px){
            .login-page{grid-template-columns:1fr}
            .login-right{display:none}
          }
        `}</style>

                <div className="login-page">
                    <div className="login-left">
                        <div className="login-brand-blk">
                            <div className="logo-circle">
                                <svg viewBox="0 0 24 24"><path d="M3 6 L21 6 L19 8 L17 6 L15 8 L13 6 L11 8 L9 6 L7 8 L5 6 L3 8 Z M5 14 L19 14 L19 16 L5 16 Z M3 18 L21 18 L21 20 L3 20 Z" /><circle cx="12" cy="11" r="2" /></svg>
                            </div>
                            <div>
                                <h2>政芯智教</h2>
                                <div className="sub">智汇政芯 · 智慧传承</div>
                            </div>
                        </div>

                        <div className="login-welcome">
                            <h1>{authMode === "login" ? "欢迎回来" : "注册账号"}</h1>
                            <p>{authMode === "login" ? "登录账号，继续思政学习之旅" : "创建账号，开启思政学习之旅"}</p>
                        </div>

                        <form className="login-form" onSubmit={(e) => { e.preventDefault(); handleAuth(); }}>
                            <div className="form-item">
                                <label>用户名</label>
                                <input type="text" placeholder="请输入用户名" value={username} onChange={e => setUsername(e.target.value)} required />
                            </div>
                            <div className="form-item">
                                <label>登录密码</label>
                                <input type="password" placeholder="请输入登录密码" value={password} onChange={e => setPassword(e.target.value)} required />
                            </div>

                            {authMode === "login" && (
                                <div className="form-item">
                                    <label>登录身份</label>
                                    <select value={loginIdentity} onChange={e => setLoginIdentity(e.target.value)}>
                                        <option value="普通用户">普通用户</option>
                                        <option value="管理员">管理员</option>
                                    </select>
                                </div>
                            )}

                            {authMode === "register" && (
                                <>
                                    <div className="form-item">
                                        <label>身份</label>
                                        <select value={identity} onChange={e => setIdentity(e.target.value)}>
                                            <option value="大一新生">大一新生</option>
                                            <option value="大二学生">大二学生</option>
                                            <option value="大三学生">大三学生</option>
                                            <option value="大四学生">大四学生</option>
                                            <option value="研究生">研究生</option>
                                            <option value="其他">其他</option>
                                        </select>
                                    </div>
                                    {identity === "其他" && (
                                        <div className="form-item">
                                            <input placeholder="请输入您的身份" value={customIdentity} onChange={e => setCustomIdentity(e.target.value)} />
                                        </div>
                                    )}
                                    <div className="form-item">
                                        <label>年龄段</label>
                                        <select value={ageGroup} onChange={e => setAgeGroup(e.target.value)}>
                                            <option value="18岁以下">18岁以下</option>
                                            <option value="18-20岁">18-20岁</option>
                                            <option value="20-25岁">20-25岁</option>
                                            <option value="25-30岁">25-30岁</option>
                                            <option value="30岁以上">30岁以上</option>
                                        </select>
                                    </div>
                                    <div className="form-item">
                                        <label>当前专业</label>
                                        <select value={currentMajor} onChange={e => setCurrentMajor(e.target.value)}>
                                            <option value="计算机科学">计算机科学</option>
                                            <option value="软件工程">软件工程</option>
                                            <option value="人工智能">人工智能</option>
                                            <option value="数据科学">数据科学</option>
                                            <option value="信息安全">信息安全</option>
                                            <option value="网络工程">网络工程</option>
                                            <option value="电子工程">电子工程</option>
                                            <option value="机械工程">机械工程</option>
                                            <option value="土木工程">土木工程</option>
                                            <option value="经济学">经济学</option>
                                            <option value="管理学">管理学</option>
                                            <option value="法学">法学</option>
                                            <option value="文学">文学</option>
                                            <option value="历史学">历史学</option>
                                            <option value="哲学">哲学</option>
                                            <option value="教育学">教育学</option>
                                            <option value="心理学">心理学</option>
                                            <option value="其他">其他</option>
                                        </select>
                                    </div>
                                    {currentMajor === "其他" && (
                                        <div className="form-item">
                                            <input placeholder="请输入您的专业" value={customMajor} onChange={e => setCustomMajor(e.target.value)} />
                                        </div>
                                    )}
                                </>
                            )}

                            <div className="form-row">
                                <label className="checkbox"><input type="checkbox" defaultChecked /> 记住我</label>
                                <button type="button">忘记密码？</button>
                            </div>

                            <label className="permission-row">
                                <input
                                    id="permissions-agree"
                                    type="checkbox"
                                    checked={permissionsAgreed}
                                    onChange={(e) => setPermissionsAgreed(e.target.checked)}
                                />
                                <span>
                                    我已阅读并同意
                                    <button type="button" onClick={() => setShowPermissions(true)}>权限申请</button>
                                </span>
                            </label>

                            <button className="login-btn" type="submit" disabled={!permissionsAgreed}>
                                {authMode === "login" ? "登 录" : "注 册"}
                            </button>
                        </form>

                        <div className="form-switch">
                            {authMode === "login" ? "还没有账号？" : "已有账号？"}
                            <button type="button" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "立即注册" : "立即登录"}</button>
                        </div>

                        <div className="login-divider">其他登录方式</div>
                        <div className="login-alt">
                            <div className="alt-btn" title="微信登录">微信</div>
                            <div className="alt-btn" title="单位 OA 登录">OA</div>
                            <div className="alt-btn" title="组织码登录">组码</div>
                        </div>

                        <div className="login-footer">© 2026 政芯智教平台</div>
                    </div>

                    <div className="login-right">
                        <div className="deco-star s1"></div>
                        <div className="deco-star s2"></div>
                        <div className="deco-star s3"></div>

                        <div className="login-hero">
                            <div className="hero-title">
                                <h2>智汇政芯 · 博学笃行</h2>
                                <p>欢迎进入新一代思政教育智能平台</p>
                            </div>

                            <div className="card-grid">
                                <div className="card pos-left">
                                    <div className="card-header">
                                        <div className="card-tag">CORE FEATURE</div>
                                        <div className="card-icon">🤖</div>
                                    </div>
                                    <h3>智能问答</h3>
                                    <p>集成大模型生成式多模态问答，全天候为您解析理论难点，不仅是搜索，更是思考的伙伴。</p>
                                    <div className="mock-input">请输入您想了解的思政知识...</div>
                                </div>
                                <div className="card pos-right-top">
                                    <div className="card-header">
                                        <div className="card-icon">🎨</div>
                                        <div className="card-tag">DATA</div>
                                    </div>
                                    <h3>思政画像</h3>
                                    <p>多维度分析学习轨迹，生成专属能力雷达图。</p>
                                </div>
                                <div className="card pos-right-bottom">
                                    <div className="card-header">
                                        <div className="card-icon">🎮</div>
                                        <div className="card-tag">FUN</div>
                                    </div>
                                    <h3>游戏导学</h3>
                                    <p>寓教于乐的互动闯关，在挑战中重温红色历史。</p>
                                </div>
                                <div className="card pos-bottom-left">
                                    <div className="custom-content">
                                        <div className="vertical-title">
                                            <span className="icon">🔥</span>
                                            <span className="text">时政热点</span>
                                        </div>
                                        <ul className="news-list">
                                            <li>• 二十届三中全会精神解读</li>
                                            <li>• 新质生产力发展报告</li>
                                            <li>• 高质量发展调研</li>
                                        </ul>
                                    </div>
                                </div>
                                <div className="card pos-bottom-right">
                                    <div className="custom-content">
                                        <div className="vertical-title">
                                            <span className="icon">💬</span>
                                            <span className="text">话题广场</span>
                                        </div>
                                        <div className="tag-group">
                                            <span className="tag"># 青年担当</span>
                                            <span className="tag"># 乡村振兴</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {showPermissions && (
                    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
                        <div className="bg-white w-full max-w-lg rounded-xl shadow-2xl p-6">
                            <h2 className="text-lg font-bold text-gray-800 mb-3">权限申请说明</h2>
                            <p className="text-sm text-gray-500 mb-4">
                                为提供完整服务，我们需要以下权限，仅用于本系统内功能。
                            </p>
                            <ul className="text-sm text-gray-700 space-y-2 mb-6">
                                <li>• 基本账号（专业、年级等）信息：用于登录与账号识别</li>
                                <li>• 画像数据（兴趣、偏好等）：用于生成个性化分析</li>
                                <li>• 对话内容：用于模型交互与结果展示</li>
                            </ul>
                            <div className="flex items-center justify-between">
                                <button
                                    type="button"
                                    className="text-gray-500"
                                    onClick={() => setShowPermissions(false)}
                                >
                                    关闭
                                </button>
                                <button
                                    type="button"
                                    className="bg-red-600 text-white px-4 py-2 rounded-lg font-bold hover:bg-red-700"
                                    onClick={() => {
                                        setPermissionsAgreed(true);
                                        setShowPermissions(false);
                                    }}
                                >
                                    同意并勾选
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </>
        );
    }

    if (!hasEnteredChat) {
        return (
            <>
                <style>{`
          .zx-home{background:#FAF6F0;color:#1A1A1A;min-height:100vh;font-family:"PingFang SC","Source Han Sans CN","Microsoft YaHei",sans-serif}
          .zx-home *{box-sizing:border-box}
          .zx-home h1,.zx-home h2,.zx-home h3,.zx-home h4{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-weight:700}
          .zx-shell-topbar{height:64px;background:#8B1A1A;display:flex;align-items:center;padding:0 28px;box-shadow:0 2px 12px rgba(139,26,26,.25)}
          .zx-shell-brand{display:flex;align-items:center;gap:12px;color:#fff;text-decoration:none}
          .zx-shell-brand-logo{width:38px;height:38px;border-radius:50%;background:#D4A017;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 3px rgba(212,160,23,.3)}
          .zx-shell-brand-logo svg{width:22px;height:22px;fill:#8B1A1A}
          .zx-shell-brand .name{font-size:18px;letter-spacing:2px}
          .zx-shell-brand .slogan{font-size:11px;opacity:.75;letter-spacing:1px;margin-top:1px}
          .zx-shell-nav{display:flex;gap:4px;margin-left:48px}
          .zx-shell-nav button{padding:8px 18px;color:rgba(255,255,255,.75);font-size:13px;border:none;background:transparent;border-radius:4px;cursor:pointer;display:flex;align-items:center;gap:6px}
          .zx-shell-nav button:hover{background:rgba(255,255,255,.08);color:#fff}
          .zx-shell-nav button.active{background:rgba(255,255,255,.15);color:#fff;font-weight:600}
          .zx-shell-right{margin-left:auto;display:flex;align-items:center;gap:10px}
          .zx-shell-user{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.1);padding:5px 14px 5px 5px;border-radius:24px;color:#fff}
          .zx-shell-user .avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#D4A017,#E5B73B);border:2px solid #D4A017;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#8B1A1A}
          .zx-shell-user .lvl{font-size:11px;opacity:.85}
          .zx-shell-sticky{position:sticky;top:0;z-index:100}

          .zx-shell-strip{background:#D4A017;color:#8B1A1A;padding:6px 28px;font-size:12px;display:flex;align-items:center;gap:10px;border-bottom:1px solid rgba(0,0,0,.08)}
          .zx-shell-strip .tag{padding:1px 8px;background:rgba(139,26,26,.15);border-radius:3px;font-size:10.5px;font-weight:600}
          .zx-layout{padding:24px 28px;max-width:1480px;margin:0 auto}
          .home-banner{background:linear-gradient(120deg,#8B1A1A 0%,#C8102E 70%,#A21425 100%);border-radius:14px;padding:36px 40px;color:#fff;position:relative;overflow:hidden;display:grid;grid-template-columns:1fr 320px;gap:30px;align-items:center}
          .home-banner::before{content:"";position:absolute;right:-50px;top:-50px;width:300px;height:300px;border:14px solid rgba(212,160,23,.1);border-radius:50%}
          .home-banner::after{content:"";position:absolute;right:80px;bottom:-80px;width:200px;height:200px;border:8px solid rgba(255,255,255,.06);border-radius:50%}
          .banner-text{position:relative;z-index:1}
          .banner-text h1{font-size:30px;margin-bottom:8px}
          .banner-text h1 .gold{color:#D4A017}
          .banner-text p{font-size:13.5px;opacity:.9;line-height:1.7;margin-bottom:18px;max-width:500px}
          .banner-tags{display:flex;gap:10px;flex-wrap:wrap}
          .banner-tags span{padding:5px 14px;background:rgba(255,255,255,.12);border-radius:14px;font-size:12px;border:1px solid rgba(212,160,23,.4)}
          .quick-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
          .quick-stat{background:rgba(255,255,255,.08);backdrop-filter:blur(10px);border:1px solid rgba(212,160,23,.25);border-radius:8px;padding:12px;text-align:center}
          .quick-stat .v{font-size:22px;color:#D4A017;font-weight:700}
          .quick-stat .l{font-size:11px;opacity:.85;margin-top:2px}
          .quick-cta{width:100%;background:#D4A017;color:#8B1A1A;border:none;padding:11px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;letter-spacing:1px}
          .quick-cta:hover{background:#E5B73B}

          .module-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-top:20px}
          .module-card{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:14px;padding:24px 20px;cursor:pointer;transition:all .25s;position:relative;overflow:hidden;min-height:200px;display:flex;flex-direction:column;color:inherit}
          .module-card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;background:var(--accent,#C8102E)}
          .module-card::after{content:"";position:absolute;right:-30px;bottom:-30px;width:100px;height:100px;background:var(--accent,#C8102E);opacity:.06;border-radius:50%;transition:all .25s}
          .module-card:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(139,26,26,.12)}
          .module-card:hover::after{transform:scale(1.4);opacity:.1}
          .module-card.m1{--accent:#C8102E}.module-card.m2{--accent:#8B6914}.module-card.m3{--accent:#5E8B3F}.module-card.m4{--accent:#2C5F8D}.module-card.m5{--accent:#2F4F7F}
          .module-icon{width:52px;height:52px;border-radius:12px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:14px;position:relative;z-index:1}
          .module-card h3{font-size:16px;color:#1A1A1A;margin:0 0 6px}
          .module-card .desc{font-size:12px;color:rgba(0,0,0,.65);line-height:1.6;flex:1;position:relative;z-index:1}
          .module-card .stat-line{margin-top:14px;padding-top:12px;border-top:1px dashed rgba(139,26,26,.12);display:flex;justify-content:space-between;align-items:center;font-size:11px;color:rgba(0,0,0,.42);position:relative;z-index:1}
          .module-card .stat-line .arr{color:var(--accent);font-weight:600;font-size:12px}

          .home-bottom{display:grid;grid-template-columns:1.6fr 1fr;gap:20px;margin-top:20px}
          .zx-card{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.04)}
          .section-hd{padding:18px 22px;border-bottom:1px solid rgba(139,26,26,.12);display:flex;align-items:center;gap:12px;background:linear-gradient(90deg,#fff,#FAF6F0)}
          .section-hd .title{font-size:16px;color:#1A1A1A;display:flex;align-items:center;gap:10px}
          .section-hd .title::before{content:"";width:5px;height:18px;background:#C8102E;border-radius:2px}
          .section-hd .actions{margin-left:auto}
          .zx-btn{padding:6px 14px;border:1px solid rgba(139,26,26,.12);background:#fff;border-radius:6px;font-size:12px;cursor:pointer;color:rgba(0,0,0,.65)}
          .zx-btn:hover{border-color:#C8102E;color:#C8102E}

          .news-list-wrap{padding:6px 22px 18px}
          .news-item{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid rgba(139,26,26,.12)}
          .news-item:last-child{border:none}
          .news-img{width:120px;height:80px;border-radius:8px;flex-shrink:0;background:linear-gradient(135deg,#8B1A1A,#C8102E);display:flex;align-items:center;justify-content:center;color:#D4A017;font-size:28px;font-weight:700;position:relative;overflow:hidden}
          .news-img::before{content:"";position:absolute;top:-20px;right:-20px;width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,.1)}
          .news-info{flex:1;min-width:0}
          .news-tag{display:inline-block;padding:1px 7px;background:#FCE8EB;color:#8B1A1A;font-size:10.5px;border-radius:3px;font-weight:600;margin-bottom:6px}
          .news-title{font-size:14px;color:#1A1A1A;font-weight:600;line-height:1.5;margin-bottom:6px}
          .news-meta{font-size:11px;color:rgba(0,0,0,.42);display:flex;gap:12px}

          .calendar-card{background:linear-gradient(135deg,#8B1A1A,#C8102E);color:#fff;border-radius:12px;padding:22px;position:relative;overflow:hidden}
          .calendar-card::before{content:"";position:absolute;right:-40px;bottom:-40px;width:160px;height:160px;border:10px solid rgba(212,160,23,.15);border-radius:50%}
          .cal-date{display:flex;align-items:baseline;gap:8px;position:relative}
          .cal-date .day{font-size:42px;font-weight:700;color:#D4A017}
          .cal-date .ym{font-size:14px;opacity:.85}
          .cal-event{font-size:15px;margin-top:12px;line-height:1.6;font-weight:600;position:relative}
          .cal-detail{font-size:12px;opacity:.8;margin-top:6px;line-height:1.6;position:relative}
          .cal-link{display:inline-block;margin-top:14px;font-size:12px;color:#D4A017;border-bottom:1px dashed #D4A017;padding-bottom:1px;position:relative}

          @media (max-width:1280px){
            .module-grid{grid-template-columns:repeat(2,1fr)}
            .home-bottom{grid-template-columns:1fr}
            .home-banner{grid-template-columns:1fr}
          }
        `}</style>

                <div className="zx-home">
                    <div className="zx-shell-sticky">
                        <header className="zx-shell-topbar">
                            <a className="zx-shell-brand" href="#">
                                <div className="zx-shell-brand-logo"><svg viewBox="0 0 24 24"><path d="M3 6 L21 6 L19 8 L17 6 L15 8 L13 6 L11 8 L9 6 L7 8 L5 6 L3 8 Z M5 14 L19 14 L19 16 L5 16 Z M3 18 L21 18 L21 20 L3 20 Z" /><circle cx="12" cy="11" r="2" /></svg></div>
                                <div><div className="name">政芯智教</div><div className="slogan">智汇政芯 · 智慧传承</div></div>
                            </a>
                            <nav className="zx-shell-nav">
                                <button className="active" type="button">⌂ 学习首页</button>
                                <button type="button" onClick={() => { setActiveWorkspace('chat'); handleEnterChat(); }}>✦ 红芯问答</button>
                                <button type="button" onClick={handleEnterDiscussion}>◈ 思政论坛</button>
                                <button type="button" onClick={handleEnterGame}>⛰ 游戏导学</button>
                                <button type="button" onClick={() => { setActiveWorkspace('profile'); setHasEnteredChat(true); }}>▦ 我的档案</button>
                                {isAdmin && <button type="button" onClick={() => { setActiveWorkspace('overview'); setHasEnteredChat(true); }}>▤ 数据概览</button>}
                            </nav>
                            <div className="zx-shell-right">
                                <div className="zx-shell-user"><div className="avatar">{username?.charAt(0) || '?'}</div><div>{username} <span className="lvl">· {isAdmin ? '管理员' : '学员'}</span></div></div>
                            </div>
                        </header>

                        <div className="zx-shell-strip">
                            <span className="tag">党史上的今天</span>
                            <b>{new Date().toLocaleDateString('zh-CN')}</b>
                            <span>传承红色基因，汲取奋进力量。</span>
                            <span style={{ marginLeft: 'auto' }}>查看全部 →</span>
                        </div>
                    </div>

                    <div className="zx-layout">
                        <section className="home-banner">
                            <div className="banner-text">
                                <h1>欢迎回来，<span className="gold">{username}</span></h1>
                                <p>您已接入政芯智教学习体系。可从红芯问答快速提问，也可进入论坛参与观点交流。</p>
                                <div className="banner-tags">
                                    <span>★ 思政学习</span>
                                    <span>★ 画像分析</span>
                                    <span>★ 实时热点</span>
                                </div>
                            </div>
                            <div>
                                <div className="quick-stats">
                                    <div className="quick-stat"><div className="v">{dailyNews.length}</div><div className="l">实时新闻</div></div>
                                    <div className="quick-stat"><div className="v">{recommendedNews.length}</div><div className="l">个性推荐</div></div>
                                    <div className="quick-stat"><div className="v">{conversations.length}</div><div className="l">历史会话</div></div>
                                    <div className="quick-stat"><div className="v">{discussionPosts.length}</div><div className="l">论坛帖子</div></div>
                                </div>
                                <button className="quick-cta" type="button" onClick={() => { setActiveWorkspace('chat'); handleEnterChat(); }}>✦ 开始学习 →</button>
                            </div>
                        </section>

                        <div className="module-grid">
                            <button type="button" className="module-card m1" onClick={() => { setActiveWorkspace('profile'); setHasEnteredChat(true); }}>
                                <div className="module-icon">▦</div>
                                <h3>学员档案</h3>
                                <div className="desc">查看思想画像雷达图、学习偏好、隐形需求等画像信息。</div>
                                <div className="stat-line"><span>多维画像模型</span><span className="arr">进入 →</span></div>
                            </button>
                            <button type="button" className="module-card m2" onClick={() => { setActiveWorkspace('chat'); handleEnterChat(); }}>
                                <div className="module-icon">✦</div>
                                <h3>红芯智能问答</h3>
                                <div className="desc">基于大模型进行思政问答，支持多轮会话与回答质量分析。</div>
                                <div className="stat-line"><span>当前可直接提问</span><span className="arr">提问 →</span></div>
                            </button>
                            <button type="button" className="module-card m3" onClick={handleEnterDiscussion}>
                                <div className="module-icon">◈</div>
                                <h3>思政论坛</h3>
                                <div className="desc">按主题参与讨论，浏览观点动态，进行点赞与举报反馈。</div>
                                <div className="stat-line"><span>开放主题讨论</span><span className="arr">参与 →</span></div>
                            </button>
                            <button type="button" className="module-card m4" onClick={handleEnterGame}>
                                <div className="module-icon">⛰</div>
                                <h3>游戏导学</h3>
                                <div className="desc">进入韶山红色文化互动闯关，通过剧情与问答完成沉浸式学习。</div>
                                <div className="stat-line"><span>红色足迹闯关</span><span className="arr">开始 →</span></div>
                            </button>
                            {isAdmin && (
                                <button type="button" className="module-card m5" onClick={() => setActiveWorkspace('overview')}>
                                    <div className="module-icon">▤</div>
                                    <h3>数据概览</h3>
                                    <div className="desc">查看系统运行与学习统计数据，辅助教学分析与展示。</div>
                                    <div className="stat-line"><span>可视化看板</span><span className="arr">查看 →</span></div>
                                </button>
                            )}
                        </div>

                        <div className="home-bottom">
                            <div className="zx-card">
                                <div className="section-hd">
                                    <div className="title">时政热点</div>
                                    <div className="actions"><button type="button" className="zx-btn" onClick={handleRefreshDailyBatch} disabled={isNewsLoading || dailyNews.length <= 4}>换一批</button></div>
                                </div>
                                <div className="news-list-wrap">
                                    {isNewsLoading && <div className="news-item"><div className="news-info"><div className="news-title">正在获取时政新闻...</div></div></div>}
                                    {!isNewsLoading && newsError && <div className="news-item"><div className="news-info"><div className="news-title">{newsError}</div></div></div>}
                                    {!isNewsLoading && !newsError && visibleDailyNews.map((item, index) => (
                                        <a key={`${item.url}-${index}`} href={item.url} target="_blank" rel="noreferrer" className="news-item" style={{ textDecoration: 'none' }}>
                                            <div className="news-img">热</div>
                                            <div className="news-info">
                                                <span className="news-tag">{item.source || '新闻源'}</span>
                                                <div className="news-title">{item.title}</div>
                                                <div className="news-meta"><span>点击查看原文</span><span>刚刚</span></div>
                                            </div>
                                        </a>
                                    ))}
                                </div>
                            </div>

                            <div className="calendar-card">
                                <div className="cal-date">
                                    <span className="day">{new Date().getDate()}</span>
                                    <span className="ym">{new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', weekday: 'long' })}</span>
                                </div>
                                <div className="cal-event">今日学习推荐</div>
                                <div className="cal-detail">你有 {recommendedNews.length} 条个性化推荐新闻，建议先浏览热点再进入问答深度学习。</div>
                                <span className="cal-link">前往学习专题 →</span>
                            </div>
                        </div>
                    </div>
                </div>
            </>
        );
    }

    return (
        <div className="min-h-screen bg-[#FAF6F0] text-gray-800" style={{ fontFamily: '"PingFang SC", "Source Han Sans CN", "Microsoft YaHei", sans-serif' }}>
            <style>{`
        .zx-shell-topbar{height:64px;background:#8B1A1A;display:flex;align-items:center;padding:0 28px;box-shadow:0 2px 12px rgba(139,26,26,.25)}
        .zx-shell-brand{display:flex;align-items:center;gap:12px;color:#fff;text-decoration:none}
        .zx-shell-brand-logo{width:38px;height:38px;border-radius:50%;background:#D4A017;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 3px rgba(212,160,23,.3)}
        .zx-shell-brand-logo svg{width:22px;height:22px;fill:#8B1A1A}
        .zx-shell-brand .name{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:18px;font-weight:700;letter-spacing:2px}
        .zx-shell-brand .slogan{font-size:11px;opacity:.75;letter-spacing:1px;margin-top:1px}
        .zx-shell-nav{display:flex;gap:4px;margin-left:48px}
        .zx-shell-nav button{padding:8px 18px;color:rgba(255,255,255,.75);font-size:13px;border:none;background:transparent;border-radius:4px;cursor:pointer;display:flex;align-items:center;gap:6px}
        .zx-shell-nav button:hover{background:rgba(255,255,255,.08);color:#fff}
        .zx-shell-nav button.active{background:rgba(255,255,255,.15);color:#fff;font-weight:600}
        .zx-shell-right{margin-left:auto;display:flex;align-items:center;gap:12px}
        .zx-shell-user{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.1);padding:5px 14px 5px 5px;border-radius:24px;color:#fff}
        .zx-shell-user .avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#D4A017,#E5B73B);border:2px solid #D4A017;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#8B1A1A}
        .zx-shell-user .lvl{font-size:11px;opacity:.85}
        .zx-shell-strip{background:#D4A017;color:#8B1A1A;padding:6px 28px;font-size:12px;display:flex;align-items:center;gap:10px;border-bottom:1px solid rgba(0,0,0,.08)}
        .zx-shell-strip .tag{padding:1px 8px;background:rgba(139,26,26,.15);border-radius:3px;font-size:10.5px;font-weight:600}
        .zx-shell-sticky{position:sticky;top:0;z-index:100}
        .zx-shell-layout{padding:18px 20px;max-width:100%;margin:0 auto;height:calc(100vh - 94px)}
        .zx-layout{padding:24px 28px;max-width:1480px;margin:0 auto}
        .home-banner{background:linear-gradient(120deg,#8B1A1A 0%,#C8102E 70%,#A21425 100%);border-radius:14px;padding:36px 40px;color:#fff;position:relative;overflow:hidden;display:grid;grid-template-columns:1fr 320px;gap:30px;align-items:center}
        .home-banner::before{content:"";position:absolute;right:-50px;top:-50px;width:300px;height:300px;border:14px solid rgba(212,160,23,.1);border-radius:50%}
        .home-banner::after{content:"";position:absolute;right:80px;bottom:-80px;width:200px;height:200px;border:8px solid rgba(255,255,255,.06);border-radius:50%}
        .banner-text{position:relative;z-index:1}
        .banner-text h1{font-size:30px;margin-bottom:8px}
        .banner-text h1 .gold{color:#D4A017}
        .banner-text p{font-size:13.5px;opacity:.9;line-height:1.7;margin-bottom:18px;max-width:500px}
        .banner-tags{display:flex;gap:10px;flex-wrap:wrap}
        .banner-tags span{padding:5px 14px;background:rgba(255,255,255,.12);border-radius:14px;font-size:12px;border:1px solid rgba(212,160,23,.4)}
        .quick-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
        .quick-stat{background:rgba(255,255,255,.08);backdrop-filter:blur(10px);border:1px solid rgba(212,160,23,.25);border-radius:8px;padding:12px;text-align:center}
        .quick-stat .v{font-size:22px;color:#D4A017;font-weight:700}
        .quick-stat .l{font-size:11px;opacity:.85;margin-top:2px}
        .quick-cta{width:100%;background:#D4A017;color:#8B1A1A;border:none;padding:11px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit;letter-spacing:1px}
        .quick-cta:hover{background:#E5B73B}
        .module-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:20px}
        .module-card{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:14px;padding:24px 20px;cursor:pointer;transition:all .25s;position:relative;overflow:hidden;min-height:200px;display:flex;flex-direction:column;color:inherit}
        .module-card::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;background:var(--accent,#C8102E)}
        .module-card::after{content:"";position:absolute;right:-30px;bottom:-30px;width:100px;height:100px;background:var(--accent,#C8102E);opacity:.06;border-radius:50%;transition:all .25s}
        .module-card:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(139,26,26,.12)}
        .module-card:hover::after{transform:scale(1.4);opacity:.1}
        .module-card.m1{--accent:#C8102E}.module-card.m2{--accent:#8B6914}.module-card.m3{--accent:#5E8B3F}.module-card.m4{--accent:#2C5F8D}
        .module-icon{width:52px;height:52px;border-radius:12px;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:14px;position:relative;z-index:1}
        .module-card h3{font-size:16px;color:#1A1A1A;margin:0 0 6px}
        .module-card .desc{font-size:12px;color:rgba(0,0,0,.65);line-height:1.6;flex:1;position:relative;z-index:1}
        .module-card .stat-line{margin-top:14px;padding-top:12px;border-top:1px dashed rgba(139,26,26,.12);display:flex;justify-content:space-between;align-items:center;font-size:11px;color:rgba(0,0,0,.42);position:relative;z-index:1}
        .module-card .stat-line .arr{color:var(--accent);font-weight:600;font-size:12px}
        .home-bottom{display:grid;grid-template-columns:1.6fr 1fr;gap:20px;margin-top:20px}
        .zx-card{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.04)}
        .section-hd{padding:18px 22px;border-bottom:1px solid rgba(139,26,26,.12);display:flex;align-items:center;gap:12px;background:linear-gradient(90deg,#fff,#FAF6F0)}
        .section-hd .title{font-size:16px;color:#1A1A1A;display:flex;align-items:center;gap:10px}
        .section-hd .title::before{content:"";width:5px;height:18px;background:#C8102E;border-radius:2px}
        .section-hd .actions{margin-left:auto}
        .zx-btn{padding:6px 14px;border:1px solid rgba(139,26,26,.12);background:#fff;border-radius:6px;font-size:12px;cursor:pointer;color:rgba(0,0,0,.65)}
        .zx-btn:hover{border-color:#C8102E;color:#C8102E}
        .news-list-wrap{padding:6px 22px 18px}
        .news-item{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid rgba(139,26,26,.12)}
        .news-item:last-child{border:none}
        .news-img{width:120px;height:80px;border-radius:8px;flex-shrink:0;background:linear-gradient(135deg,#8B1A1A,#C8102E);display:flex;align-items:center;justify-content:center;color:#D4A017;font-size:28px;font-weight:700;position:relative;overflow:hidden}
        .news-img::before{content:"";position:absolute;top:-20px;right:-20px;width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,.1)}
        .news-info{flex:1;min-width:0}
        .news-tag{display:inline-block;padding:1px 7px;background:#FCE8EB;color:#8B1A1A;font-size:10.5px;border-radius:3px;font-weight:600;margin-bottom:6px}
        .news-title{font-size:14px;color:#1A1A1A;font-weight:600;line-height:1.5;margin-bottom:6px}
        .news-meta{font-size:11px;color:rgba(0,0,0,.42);display:flex;gap:12px}
        .calendar-card{background:linear-gradient(135deg,#8B1A1A,#C8102E);color:#fff;border-radius:12px;padding:22px;position:relative;overflow:hidden}
        .calendar-card::before{content:"";position:absolute;right:-40px;bottom:-40px;width:160px;height:160px;border:10px solid rgba(212,160,23,.15);border-radius:50%}
        .cal-date{display:flex;align-items:baseline;gap:8px;position:relative}
        .cal-date .day{font-size:42px;font-weight:700;color:#D4A017}
        .cal-date .ym{font-size:14px;opacity:.85}
        .cal-event{font-size:15px;margin-top:12px;line-height:1.6;font-weight:600;position:relative}
        .cal-detail{font-size:12px;opacity:.8;margin-top:6px;line-height:1.6;position:relative}
        .cal-link{display:inline-block;margin-top:14px;font-size:12px;color:#D4A017;border-bottom:1px dashed #D4A017;padding-bottom:1px;position:relative}

        .qa-layout{display:grid;grid-template-columns:260px 1fr 300px;gap:20px;height:100%}
        .qa-history{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:12px;padding:16px;height:100%;overflow-y:auto}
        .new-btn{width:100%;padding:11px;background:#C8102E;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;margin-bottom:16px;letter-spacing:1px}
        .new-btn:hover{background:#8B1A1A}
        .qa-cat-title{font-size:11px;color:rgba(0,0,0,.42);font-weight:600;letter-spacing:1px;padding:10px 4px 6px;display:flex;align-items:center;gap:6px}
        .qa-cat-title::before{content:"";width:3px;height:10px;background:#C8102E;border-radius:2px}
        .qa-history-item{padding:10px 12px;background:#FAF6F0;border-radius:6px;font-size:12px;cursor:pointer;color:rgba(0,0,0,.65);margin-bottom:6px;line-height:1.5;border-left:3px solid transparent;text-align:left;width:100%;border-top:none;border-right:none;border-bottom:none}
        .qa-history-item:hover{border-left-color:#C8102E;color:#1A1A1A}
        .qa-history-item.active{background:#FCE8EB;border-left-color:#C8102E;color:#8B1A1A;font-weight:500}
        .qa-history-item .time{font-size:10px;color:rgba(0,0,0,.42);margin-top:3px}

        .qa-main{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:12px;display:flex;flex-direction:column;height:100%}
        .qa-conv{padding:24px 28px;flex:1;display:flex;flex-direction:column;gap:20px;overflow-y:auto}
        .quote-card{background:linear-gradient(135deg,#FCE8EB,#FBF3D9);border-left:4px solid #C8102E;border-radius:8px;padding:18px 22px;font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:16px;color:#1A1A1A;position:relative}
        .quote-card::before{content:"\\201C";position:absolute;top:-8px;left:10px;font-family:serif;font-size:52px;color:#C8102E;opacity:.25}
        .quote-card .text{padding-left:32px;line-height:1.7;font-weight:600}
        .quote-card .src{margin-top:10px;text-align:right;font-size:12px;color:#8B1A1A;font-family:inherit;font-style:normal;font-weight:normal}

        .dialog-block{display:flex;gap:12px;align-items:flex-start}
        .dialog-block.user{flex-direction:row-reverse}
        .dialog-avatar{width:38px;height:38px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:16px}
        .dialog-avatar.ai{background:linear-gradient(135deg,#C8102E,#8B1A1A);color:#D4A017;box-shadow:0 0 0 2px #FBF3D9;font-weight:700}
        .dialog-avatar.user{background:linear-gradient(135deg,#D4A017,#B8860B);color:#fff;font-weight:700;font-size:14px}
        .bubble{background:#FAF6F0;border:1px solid rgba(139,26,26,.12);border-radius:10px;padding:14px 18px;font-size:13.5px;color:#1A1A1A;max-width:80%;line-height:1.75}
        .bubble.user-b{background:#C8102E;color:#fff;border-color:#C8102E}
        .thinking{display:flex;gap:4px;padding:14px 18px;background:#FAF6F0;border:1px solid rgba(139,26,26,.12);border-radius:10px;width:fit-content}
        .thinking .dot{width:8px;height:8px;border-radius:50%;background:#C8102E;animation:think 1.4s infinite ease-in-out}
        .thinking .dot:nth-child(2){animation-delay:.2s}
        .thinking .dot:nth-child(3){animation-delay:.4s}
        @keyframes think{0%,80%,100%{opacity:.3;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}

        .qa-input-area{border-top:1px solid rgba(139,26,26,.12);padding:16px 24px;background:#FAF6F0}
        .suggested-q{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
        .q-chip{padding:6px 12px;background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:14px;font-size:12px;color:rgba(0,0,0,.65);cursor:pointer}
        .q-chip:hover{background:#FCE8EB;color:#8B1A1A;border-color:#C8102E}
        .q-chip .ico{margin-right:4px;color:#D4A017}
        .qq-input{padding:10px 14px;background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:24px;display:flex;align-items:center;gap:8px}
        .qq-input input{flex:1;border:none;background:transparent;outline:none;font-size:13.5px;color:#1A1A1A;font-family:inherit}
        .qq-input input::placeholder{color:rgba(0,0,0,.42)}
        .qq-input .send{width:34px;height:34px;border-radius:50%;background:#C8102E;color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px}
        .qq-input .send:hover{background:#8B1A1A}
        .qq-input .file-btn{width:28px;height:28px;border-radius:50%;background:#FAF6F0;color:rgba(0,0,0,.42);border:1px solid rgba(139,26,26,.12);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:13px}

        .qa-recommend{display:flex;flex-direction:column;gap:14px;height:100%;overflow-y:auto}
        .recom-card{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:10px;padding:14px 16px}
        .recom-card .blk-title{margin-bottom:12px;font-size:13px;font-family:"Source Han Serif CN","STSong","SimSun",serif;font-weight:700;display:flex;align-items:center;gap:6px}
        .recom-card .blk-title::before{content:"";width:4px;height:14px;background:#C8102E;border-radius:2px}
        .hot-q{padding:9px 0;border-bottom:1px dashed rgba(139,26,26,.12);font-size:12.5px;color:rgba(0,0,0,.65);cursor:pointer;display:flex;align-items:flex-start;gap:8px;line-height:1.5}
        .hot-q:last-child{border:none}
        .hot-q .num{width:18px;height:18px;border-radius:4px;background:#F0E9DC;color:rgba(0,0,0,.42);font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px;font-family:"Source Han Serif CN","STSong","SimSun",serif}
        .hot-q.hot .num{background:#C8102E;color:#fff}
        .hot-q.hot2 .num{background:#D87A2C;color:#fff}
        .hot-q.hot3 .num{background:#D4A017;color:#fff}
        .hot-q:hover{color:#8B1A1A}
        .citation-ref{background:#FAF6F0;border-radius:6px;padding:10px 12px;display:flex;gap:10px;align-items:flex-start;font-size:11.5px;margin-bottom:8px}
        .citation-ref:last-child{margin-bottom:0}
        .citation-ref .book-ico{width:28px;height:36px;background:linear-gradient(135deg,#8B1A1A,#C8102E);border-radius:2px;display:flex;align-items:center;justify-content:center;color:#D4A017;font-size:11px;font-weight:700;font-family:"Source Han Serif CN","STSong","SimSun",serif;flex-shrink:0;text-align:center;line-height:1.2}
        .citation-ref .info .title{font-weight:600;color:#1A1A1A;margin-bottom:2px}
        .citation-ref .info .meta{color:rgba(0,0,0,.42);font-size:11px}

        .forum-layout{display:grid;grid-template-columns:1fr 320px;gap:20px;height:100%}
        .topic-banner{background:linear-gradient(120deg,#8B1A1A,#C8102E);border-radius:12px;padding:26px 30px;color:#fff;margin-bottom:20px;display:flex;align-items:center;gap:24px;position:relative;overflow:hidden}
        .topic-banner::before{content:"";position:absolute;right:-40px;top:-40px;width:200px;height:200px;border:10px solid rgba(212,160,23,.15);border-radius:50%}
        .topic-banner h2{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:24px;margin-bottom:6px}
        .topic-banner p{font-size:13px;opacity:.85;line-height:1.6}
        .topic-banner .post-btn{margin-left:auto;padding:12px 24px;background:#D4A017;color:#8B1A1A;border:none;border-radius:8px;font-size:13.5px;font-weight:700;cursor:pointer;font-family:inherit;letter-spacing:1px;position:relative;z-index:1}
        .topic-banner .post-btn:hover{background:#E5B73B}

        .topic-tags{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:10px;padding:14px 18px;margin-bottom:16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
        .topic-tags .label{font-size:12px;color:rgba(0,0,0,.42);font-weight:600;margin-right:6px}
        .topic-tag{padding:5px 14px;background:#FAF6F0;border:1px solid rgba(139,26,26,.12);border-radius:14px;font-size:12px;color:rgba(0,0,0,.65);cursor:pointer}
        .topic-tag.active{background:#C8102E;color:#fff;border-color:#C8102E;font-weight:600}
        .topic-tag:hover{border-color:#C8102E;color:#8B1A1A}

        .pk-card{background:linear-gradient(135deg,#8B1A1A,#C8102E);color:#fff;border-radius:12px;padding:22px 24px;margin-bottom:16px;position:relative;overflow:hidden}
        .pk-card::before{content:"VS";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:120px;font-weight:900;color:rgba(212,160,23,.12)}
        .pk-tag{display:inline-block;padding:3px 10px;background:#D4A017;color:#8B1A1A;border-radius:10px;font-size:11px;font-weight:700;margin-bottom:10px;letter-spacing:1px}
        .pk-title{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:22px;margin-bottom:6px;line-height:1.4;position:relative;z-index:1}
        .pk-sub{font-size:12px;opacity:.85;margin-bottom:18px;position:relative;z-index:1}
        .pk-bars{position:relative;z-index:1;margin-bottom:14px}
        .pk-bar-row{display:flex;align-items:center;gap:14px;margin-bottom:10px;font-size:13px}
        .pk-bar-row .side-label{flex:0 0 90px;font-weight:600;display:flex;align-items:center;gap:6px}
        .pk-bar-row .pk-bar{flex:1;height:14px;background:rgba(255,255,255,.15);border-radius:7px;overflow:hidden;position:relative}
        .pk-fill{height:100%;border-radius:7px;display:flex;align-items:center;padding:0 10px;font-size:11px;font-weight:700}
        .pk-fill.left{background:linear-gradient(90deg,#D4A017,#E5B73B);color:#8B1A1A;justify-content:flex-end}
        .pk-fill.right{background:linear-gradient(90deg,#E5B73B,#fff);color:#8B1A1A}
        .pk-buttons{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px;position:relative;z-index:1}
        .pk-btn{padding:11px;background:rgba(255,255,255,.1);border:1.5px solid rgba(212,160,23,.4);border-radius:8px;color:#fff;cursor:pointer;font-size:13px;font-weight:600;transition:all .15s;font-family:inherit}
        .pk-btn:hover{background:#D4A017;color:#8B1A1A;border-color:#D4A017}
        .pk-foot{font-size:11px;opacity:.75;margin-top:10px;position:relative;z-index:1;display:flex;justify-content:space-between}

        .post-list{display:flex;flex-direction:column;gap:14px}
        .post-card{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:10px;padding:18px 22px;transition:all .15s}
        .post-card:hover{border-color:#C8102E;box-shadow:0 4px 12px rgba(139,26,26,.08)}
        .post-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
        .post-avatar{width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,#E5C088,#B8916A);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:13px;flex-shrink:0}
        .post-author{flex:1}
        .post-author .name{font-size:13.5px;font-weight:600;color:#1A1A1A;display:flex;align-items:center;gap:6px}
        .post-author .meta{font-size:11px;color:rgba(0,0,0,.42);margin-top:1px}
        .post-tag-line{display:flex;gap:6px}
        .post-tag-line span{padding:2px 8px;background:#FAF6F0;font-size:11px;color:rgba(0,0,0,.65);border-radius:3px}
        .post-title{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:17px;color:#1A1A1A;margin-bottom:10px;font-weight:700;line-height:1.5}
        .post-excerpt{font-size:13px;color:rgba(0,0,0,.65);line-height:1.7;margin-bottom:14px;white-space:pre-wrap}
        .post-foot{display:flex;align-items:center;gap:18px;font-size:12px;color:rgba(0,0,0,.42);flex-wrap:wrap}
        .post-foot .stat{display:flex;align-items:center;gap:4px;cursor:pointer;background:none;border:none;padding:0;color:inherit}
        .post-foot .stat:hover{color:#C8102E}
        .post-foot .stat.hot{color:#C8102E;font-weight:600}

        .side-panel{display:flex;flex-direction:column;gap:16px;overflow-y:auto}
        .side-block{background:#fff;border:1px solid rgba(139,26,26,.12);border-radius:10px;padding:16px}
        .side-block h4{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-size:14px;margin-bottom:12px;display:flex;align-items:center}
        .side-block h4::before{content:"";width:4px;height:14px;background:#C8102E;border-radius:2px;margin-right:8px}
        .side-block h4 .more{margin-left:auto;font-size:11px;color:#C8102E;cursor:pointer;font-weight:400}
        .hot-topic-item{display:flex;align-items:flex-start;gap:10px;padding:9px 0;border-bottom:1px solid rgba(139,26,26,.12);cursor:pointer;font-size:12.5px;line-height:1.5}
        .hot-topic-item:last-child{border:none}
        .hot-topic-item:hover{color:#8B1A1A}
        .hot-topic-item .rank{width:18px;height:18px;border-radius:4px;font-size:10px;font-weight:700;display:flex;align-items:center;justify-content:center;color:#fff;flex-shrink:0;margin-top:2px;background:rgba(0,0,0,.18);font-family:"Source Han Serif CN","STSong","SimSun",serif}
        .hot-topic-item .heat{margin-left:auto;font-size:10.5px;color:#C8102E;font-weight:600;flex-shrink:0;margin-top:2px}
        .rank-list-block .rank-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid rgba(139,26,26,.12)}
        .rank-list-block .rank-item:last-child{border:none}
        .rank-no{width:26px;height:26px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:"Source Han Serif CN","STSong","SimSun",serif;font-weight:700;font-size:12.5px;background:#f5f0e8;color:rgba(0,0,0,.42);flex-shrink:0}
        .rank-no.r1{background:linear-gradient(135deg,#D4A017,#E5B73B);color:#fff}
        .rank-no.r2{background:linear-gradient(135deg,#C0C0C0,#E0E0E0);color:#fff}
        .rank-no.r3{background:linear-gradient(135deg,#CD7F32,#E5A055);color:#fff}
        .rank-mini-avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#E5C088,#B8916A);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:12px;flex-shrink:0}
        .rank-info{flex:1;min-width:0;font-size:12.5px}
        .rank-info .name{color:#1A1A1A;font-weight:600}
        .rank-info .branch{font-size:10.5px;color:rgba(0,0,0,.42);margin-top:1px}
        .rank-score-mini{font-family:"Source Han Serif CN","STSong","SimSun",serif;font-weight:700;color:#8B1A1A;font-size:14px}

        @media (max-width:1280px){.qa-layout{grid-template-columns:1fr}.qa-history,.qa-recommend{display:none}}
        @media (max-width:1280px){.forum-layout{grid-template-columns:1fr}.side-panel{display:none}}
      `}</style>

            <div className="zx-shell-sticky">
                <header className="zx-shell-topbar">
                    <a className="zx-shell-brand" href="#">
                        <div className="zx-shell-brand-logo"><svg viewBox="0 0 24 24"><path d="M3 6 L21 6 L19 8 L17 6 L15 8 L13 6 L11 8 L9 6 L7 8 L5 6 L3 8 Z M5 14 L19 14 L19 16 L5 16 Z M3 18 L21 18 L21 20 L3 20 Z" /><circle cx="12" cy="11" r="2" /></svg></div>
                        <div>
                            <div className="name">政芯智教</div>
                            <div className="slogan">智汇政芯 · 智慧传承</div>
                        </div>
                    </a>
                    <nav className="zx-shell-nav">
                        <button type="button" className={!hasEnteredChat ? 'active' : ''} onClick={() => setHasEnteredChat(false)}>⌂ 学习首页</button>
                        <button type="button" className={hasEnteredChat && activeWorkspace === 'chat' ? 'active' : ''} onClick={() => { setActiveWorkspace('chat'); handleEnterChat(); }}>✦ 红芯问答</button>
                        <button type="button" className={hasEnteredChat && activeWorkspace === 'discussion' ? 'active' : ''} onClick={handleEnterDiscussion}>◈ 思政论坛</button>
                        <button type="button" className={hasEnteredChat && activeWorkspace === 'game' ? 'active' : ''} onClick={handleEnterGame}>⛰ 游戏导学</button>
                        <button type="button" className={hasEnteredChat && activeWorkspace === 'profile' ? 'active' : ''} onClick={() => { setActiveWorkspace('profile'); setHasEnteredChat(true); }}>▦ 我的档案</button>
                        {isAdmin && <button type="button" className={hasEnteredChat && activeWorkspace === 'overview' ? 'active' : ''} onClick={() => { setActiveWorkspace('overview'); setHasEnteredChat(true); }}>▤ 数据概览</button>}
                    </nav>
                    <div className="zx-shell-right">
                        <div className="zx-shell-user">
                            <div className="avatar">{username?.charAt(0) || '?'}</div>
                            <div>{username} <span className="lvl">· {isAdmin ? '管理员' : '学员'}</span></div>
                        </div>
                    </div>
                </header>

                <div className="zx-shell-strip">
                    {!hasEnteredChat ? (
                        <><span className="tag">党史上的今天</span><b>{new Date().toLocaleDateString('zh-CN')}</b><span>传承红色基因，汲取奋进力量。</span><span style={{ marginLeft: 'auto' }}>查看全部 →</span></>
                    ) : (
                        <><span className="tag">学习提示</span><b>{activeWorkspace === 'chat' ? '当前处于红芯问答模式' : activeWorkspace === 'discussion' ? '当前处于思政论坛模式' : activeWorkspace === 'game' ? '当前处于游戏导学模式' : activeWorkspace === 'profile' ? '当前处于我的档案模式' : '当前处于数据概览模式'}</b><span>可通过顶部导航快速切换模块。</span></>
                    )}
                </div>
            </div>

            {!hasEnteredChat && (
                <div className="zx-layout">
                    <section className="home-banner">
                        <div className="banner-text">
                            <h1>欢迎回来，<span className="gold">{username}</span></h1>
                            <p>您已接入政芯智教学习体系。可从红芯问答快速提问，也可进入论坛参与观点交流。</p>
                            <div className="banner-tags">
                                <span>★ 思政学习</span>
                                <span>★ 画像分析</span>
                                <span>★ 实时热点</span>
                            </div>
                        </div>
                        <div>
                            <div className="quick-stats">
                                <div className="quick-stat"><div className="v">{dailyNews.length}</div><div className="l">实时新闻</div></div>
                                <div className="quick-stat"><div className="v">{recommendedNews.length}</div><div className="l">个性推荐</div></div>
                                <div className="quick-stat"><div className="v">{conversations.length}</div><div className="l">历史会话</div></div>
                                <div className="quick-stat"><div className="v">{discussionPosts.length}</div><div className="l">论坛帖子</div></div>
                            </div>
                            <button className="quick-cta" type="button" onClick={() => { setActiveWorkspace('chat'); handleEnterChat(); }}>✦ 开始学习 →</button>
                        </div>
                    </section>
                    <div className="module-grid">
                        <button type="button" className="module-card m1" onClick={() => { setActiveWorkspace('profile'); setHasEnteredChat(true); }}>
                            <div className="module-icon">▦</div>
                            <h3>学员档案</h3>
                            <div className="desc">查看思想画像雷达图、学习偏好、隐形需求等画像信息。</div>
                            <div className="stat-line"><span>多维画像模型</span><span className="arr">进入 →</span></div>
                        </button>
                        <button type="button" className="module-card m2" onClick={() => { setActiveWorkspace('chat'); handleEnterChat(); }}>
                            <div className="module-icon">✦</div>
                            <h3>红芯智能问答</h3>
                            <div className="desc">基于大模型进行思政问答，支持多轮会话与回答质量分析。</div>
                            <div className="stat-line"><span>当前可直接提问</span><span className="arr">提问 →</span></div>
                        </button>
                        <button type="button" className="module-card m3" onClick={handleEnterDiscussion}>
                            <div className="module-icon">◈</div>
                            <h3>思政论坛</h3>
                            <div className="desc">按主题参与讨论，浏览观点动态，进行点赞与举报反馈。</div>
                            <div className="stat-line"><span>开放主题讨论</span><span className="arr">参与 →</span></div>
                        </button>
                        {isAdmin && (
                            <button type="button" className="module-card m4" onClick={() => { setActiveWorkspace('overview'); setHasEnteredChat(true); }}>
                                <div className="module-icon">▤</div>
                                <h3>数据概览</h3>
                                <div className="desc">查看系统运行与学习统计数据，辅助教学分析与展示。</div>
                                <div className="stat-line"><span>可视化看板</span><span className="arr">查看 →</span></div>
                            </button>
                        )}
                    </div>
                    <div className="home-bottom">
                        <div className="zx-card">
                            <div className="section-hd">
                                <div className="title">时政热点</div>
                                <div className="actions"><button type="button" className="zx-btn" onClick={handleRefreshDailyBatch} disabled={isNewsLoading || dailyNews.length <= 4}>换一批</button></div>
                            </div>
                            <div className="news-list-wrap">
                                {isNewsLoading && <div className="news-item"><div className="news-info"><div className="news-title">正在获取时政新闻...</div></div></div>}
                                {!isNewsLoading && newsError && <div className="news-item"><div className="news-info"><div className="news-title">{newsError}</div></div></div>}
                                {!isNewsLoading && !newsError && visibleDailyNews.map((item, index) => (
                                    <a key={`${item.url}-${index}`} href={item.url} target="_blank" rel="noreferrer" className="news-item" style={{ textDecoration: 'none' }}>
                                        <div className="news-img">热</div>
                                        <div className="news-info">
                                            <span className="news-tag">{item.source || '新闻源'}</span>
                                            <div className="news-title">{item.title}</div>
                                            <div className="news-meta"><span>点击查看原文</span><span>刚刚</span></div>
                                        </div>
                                    </a>
                                ))}
                            </div>
                        </div>
                        <div className="calendar-card">
                            <div className="cal-date">
                                <span className="day">{new Date().getDate()}</span>
                                <span className="ym">{new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', weekday: 'long' })}</span>
                            </div>
                            <div className="cal-event">今日学习推荐</div>
                            <div className="cal-detail">你有 {recommendedNews.length} 条个性化推荐新闻，建议先浏览热点再进入问答深度学习。</div>
                            <span className="cal-link">前往学习专题 →</span>
                        </div>
                    </div>
                </div>
            )}

            {hasEnteredChat && (
                <div className="zx-shell-layout">

                    {activeWorkspace === 'chat' && (
                        <div className="qa-layout">
                            <aside className="qa-history">
                                <button className="new-btn" type="button" onClick={handleStartNewChat} disabled={isLoading || isCreatingConversation}>
                                    {isCreatingConversation ? '创建中...' : '+ 发起新对话'}
                                </button>

                                <div className="qa-cat-title">历史会话</div>
                                {conversations.length > 0 ? conversations.map(conversation => (
                                    <button
                                        key={conversation.id}
                                        type="button"
                                        className={`qa-history-item ${conversation.id === currentConversationId ? 'active' : ''}`}
                                        onClick={() => handleSelectConversation(conversation.id)}
                                        disabled={isLoading}
                                    >
                                        {(conversation.title || '新对话').slice(0, 28)}
                                        <div className="time">{formatConversationTime(conversation.updated_at) || '刚刚'} · {conversation.message_count || 0} 轮</div>
                                    </button>
                                )) : (
                                    <div className="qa-history-item">暂无历史会话<div className="time">点击上方按钮开始</div></div>
                                )}
                            </aside>

                            <main className="qa-main">
                                <div className="section-hd">
                                    <div className="title">红芯智能问答 <span className="sub">· 您身边的思政学习助手</span></div>
                                    <div className="actions">
                                        <button className="zx-btn" type="button">生成纪要</button>
                                        <button className="zx-btn" type="button">分享对话</button>
                                        <button className="zx-btn" type="button" onClick={handleStartNewChat}>+ 新对话</button>
                                    </div>
                                </div>

                                <div className="qa-conv">
                                    {messages.length === 0 && !streamingText && !isLoading && (
                                        <div className="quote-card">
                                            <div className="text">实事求是，是马克思主义的根本观点，是中国共产党人认识世界、改造世界的根本要求。</div>
                                            <div className="src">习近平 · 党的二十大报告 · 2022年10月16日</div>
                                        </div>
                                    )}
                                    {messages.map((m, i) => (
                                        <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                            <div className={`dialog-block ${m.role === 'user' ? 'user' : ''}`} onClick={async () => {
                                                if (m.role === 'ai' && m.aiAnalysis) {
                                                    if (m.chatId) {
                                                        try {
                                                            const res = await fetch(`${API_BASE_URL}/chat/history/${m.chatId}`);
                                                            if (res.ok) {
                                                                const data = await res.json();
                                                                if (data.status === 'success' && data.data) {
                                                                    const record = data.data;
                                                                    setSelectedAIMessage({
                                                                        ...m,
                                                                        aiAnalysis: {
                                                                            score: record.ai_reply_score || 0,
                                                                            feedback: record.ai_reply_feedback || '',
                                                                            selected_model: record.selected_model || '',
                                                                            model_comparison: {
                                                                                qwen: {
                                                                                    score: record.qwen_score || 0,
                                                                                    feedback: ''
                                                                                },
                                                                                deepseek: {
                                                                                    score: record.deepseek_score || 0,
                                                                                    feedback: ''
                                                                                },
                                                                                kimi: {
                                                                                    score: record.kimi_score || 0,
                                                                                    feedback: ''
                                                                                }
                                                                            }
                                                                        }
                                                                    });
                                                                } else {
                                                                    setSelectedAIMessage(m);
                                                                }
                                                            } else {
                                                                setSelectedAIMessage(m);
                                                            }
                                                        } catch (err) {
                                                            console.error('查询AI回答分析失败:', err);
                                                            setSelectedAIMessage(m);
                                                        }
                                                    } else {
                                                        setSelectedAIMessage(m);
                                                    }
                                                    setShowAIAnalysis(true);
                                                }
                                            }}>
                                                <div className={`dialog-avatar ${m.role === 'user' ? 'user' : 'ai'}`}>
                                                    {m.role === 'user' ? (username?.charAt(0) || '我') : '★'}
                                                </div>
                                                <div
                                                    className={`bubble ${m.role === 'user' ? 'user-b' : ''} ${m.role === 'ai' && m.aiAnalysis ? 'cursor-pointer' : ''}`}
                                                    onClick={async () => {
                                                        if (m.role === 'user' && m.analysis) {
                                                            if (m.chatId) {
                                                                try {
                                                                    const res = await fetch(`${API_BASE_URL}/chat/history/${m.chatId}`);
                                                                    if (res.ok) {
                                                                        const data = await res.json();
                                                                        if (data.status === 'success' && data.data) {
                                                                            const record = data.data;
                                                                            setSelectedMessage({
                                                                                ...m,
                                                                                analysis: {
                                                                                    hidden_needs: (record.user_hidden_needs || '').split(',').filter(n => n.trim()),
                                                                                    emotion_score: record.user_emotion_score || 0
                                                                                }
                                                                            });
                                                                        } else {
                                                                            setSelectedMessage(m);
                                                                        }
                                                                    } else {
                                                                        setSelectedMessage(m);
                                                                    }
                                                                } catch (err) {
                                                                    console.error('查询消息分析失败:', err);
                                                                    setSelectedMessage(m);
                                                                }
                                                            } else {
                                                                setSelectedMessage(m);
                                                            }
                                                            setShowMessageAnalysis(true);
                                                        }
                                                    }}
                                                    title={m.role === 'user' && m.analysis ? '点击查看消息分析' : ''}
                                                >
                                                    {m.role === 'ai' ? <MarkdownMessage content={m.content} /> : m.content}
                                                    {m.role === 'user' && m.analysis && (
                                                        <div className="mt-2 text-xs opacity-75">📊 点击查看分析</div>
                                                    )}
                                                    {m.role === 'ai' && m.aiAnalysis && (
                                                        <div className="mt-2 text-xs text-gray-500">📊 点击查看AI评分</div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    {streamingText && (
                                        <div className="flex justify-start">
                                            <div className="dialog-block">
                                                <div className="dialog-avatar ai">★</div>
                                                <div className="bubble">
                                                    <MarkdownMessage content={streamingText} />
                                                    <div className="mt-1 text-left text-sm text-gray-400">
                                                        <span className="animate-pulse">▌</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    {isLoading && !streamingText && (
                                        <div className="flex justify-start">
                                            <div className="dialog-block">
                                                <div className="dialog-avatar ai">★</div>
                                                <div className="thinking">
                                                    <span className="dot"></span><span className="dot"></span><span className="dot"></span>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>

                                <div className="qa-input-area">
                                    <div className="suggested-q">
                                        <div className="q-chip" onClick={() => setInput('如何理解新质生产力的党性内涵？')}><span className="ico">✦</span>如何理解新质生产力的党性内涵？</div>
                                        <div className="q-chip" onClick={() => setInput('两个结合的深层含义是什么？')}><span className="ico">✦</span>两个结合的深层含义是什么？</div>
                                        <div className="q-chip" onClick={() => setInput('遵义会议的历史意义')}><span className="ico">✦</span>遵义会议的历史意义</div>
                                        <div className="q-chip" onClick={() => setInput('中国式现代化五大特征')}><span className="ico">✦</span>中国式现代化五大特征</div>
                                    </div>

                                    <div className="qq-input">
                                        <button className="file-btn" type="button" title="附件">📎</button>
                                        <input
                                            value={input}
                                            onChange={e => setInput(e.target.value)}
                                            onKeyDown={(e) => { if (e.key === 'Enter' && !isLoading) handleSend(); }}
                                            placeholder="向红芯提问，例如：如何理解中国式现代化？"
                                            disabled={isLoading}
                                        />
                                        <button className="send" type="button" title="发送" onClick={handleSend} disabled={isLoading}>→</button>
                                    </div>
                                </div>

                            </main>

                            <aside className="qa-recommend">
                                <div className="recom-card">
                                    <div className="blk-title">★ 今日热问</div>
                                    <div className="hot-q hot" onClick={() => setInput('如何理解二十届三中全会提出的进一步全面深化改革？')}><div className="num">1</div><div>如何理解二十届三中全会提出的进一步全面深化改革？</div></div>
                                    <div className="hot-q hot2" onClick={() => setInput('新质生产力与传统生产力的本质区别')}><div className="num">2</div><div>新质生产力与传统生产力的本质区别</div></div>
                                    <div className="hot-q hot3" onClick={() => setInput('中国式现代化与西方现代化有哪些根本不同？')}><div className="num">3</div><div>中国式现代化与西方现代化有哪些根本不同？</div></div>
                                    <div className="hot-q" onClick={() => setInput('为什么说两个结合是又一次的思想解放？')}><div className="num">肆</div><div>为什么说两个结合是又一次的思想解放？</div></div>
                                    <div className="hot-q" onClick={() => setInput('党的群众路线在新时代的具体体现')}><div className="num">伍</div><div>党的群众路线在新时代的具体体现</div></div>
                                </div>

                                <div className="recom-card">
                                    <div className="blk-title">📚 参考文献</div>
                                    <div className="citation-ref"><div className="book-ico">二十<br />大</div><div className="info"><div className="title">党的二十大报告</div><div className="meta">习近平 · 2022-10-16</div></div></div>
                                    <div className="citation-ref"><div className="book-ico">改革</div><div className="info"><div className="title">关于全面深化改革若干重大问题的决定</div><div className="meta">中共中央</div></div></div>
                                    <div className="citation-ref"><div className="book-ico">毛选</div><div className="info"><div className="title">《毛泽东选集》第三卷</div><div className="meta">《改造我们的学习》</div></div></div>
                                </div>

                                <div className="recom-card" style={{ background: 'linear-gradient(135deg,#FCE8EB,#FBF3D9)', border: 'none' }}>
                                    <div className="blk-title" style={{ color: '#8B1A1A' }}>💡 学习小贴士</div>
                                    <div style={{ fontSize: '12.5px', color: '#1A1A1A', lineHeight: 1.7 }}>
                                        向红芯提问时，附上具体的<b style={{ color: '#8B1A1A' }}>政策文件章节</b>或
                                        <b style={{ color: '#8B1A1A' }}>历史事件背景</b>，可以获得更精准的引用解答。
                                    </div>
                                </div>
                            </aside>
                        </div>
                    )}

                    {activeWorkspace === 'discussion' && (
                        <div className="forum-layout">
                            <main className="h-full overflow-y-auto pr-1">
                                <section className="topic-banner">
                                    <div>
                                        <h2>思政论坛 · 思想交流园地</h2>
                                        <p>汇聚多元观点，共同学习交流，传承红色基因，弘扬正能量。</p>
                                    </div>
                                    <button className="post-btn" type="button" onClick={() => document.getElementById('publish-anchor')?.scrollIntoView({ behavior: 'smooth' })}>+ 发起话题</button>
                                </section>

                                <div className="topic-tags">
                                    <span className="label">话题分类：</span>
                                    {forumAllTopics.length === 0 && <span className="topic-tag active">加载中</span>}
                                    {forumAllTopics.map(topic => {
                                        const matchedCategory = discussionCategories.find(c => (c.topics || []).includes(topic));
                                        return (
                                            <span
                                                key={topic}
                                                className={`topic-tag ${selectedDiscussionTopic === topic ? 'active' : ''}`}
                                                onClick={() => handleSelectDiscussionTopic(topic, matchedCategory?.category)}
                                            >
                                                {topic}
                                            </span>
                                        );
                                    })}
                                </div>

                                <section className="post-list">
                                    {isDiscussionLoading && (
                                        <article className="post-card"><p className="post-excerpt">正在加载当前主题的讨论内容...</p></article>
                                    )}

                                    {!isDiscussionLoading && discussionError && (
                                        <article className="post-card"><p className="post-excerpt">{discussionError}</p></article>
                                    )}

                                    {!isDiscussionLoading && !discussionError && discussionPosts.length === 0 && (
                                        <article className="post-card"><p className="post-excerpt">当前主题还没有发言，欢迎发布第一条讨论内容。</p></article>
                                    )}

                                    {!isDiscussionLoading && !discussionError && discussionPosts.map((post, index) => (
                                        <article key={post.id} className="post-card">
                                            <div className="post-head">
                                                <div className="post-avatar" style={{
                                                    background: [
                                                        'linear-gradient(135deg,#E5C088,#B8916A)',
                                                        'linear-gradient(135deg,#A8C5E5,#7AA0CC)',
                                                        'linear-gradient(135deg,#D8A88E,#B8866A)',
                                                        'linear-gradient(135deg,#B8D8A8,#8DB878)'
                                                    ][index % 4]
                                                }}>{(post.author || '用').charAt(0)}</div>
                                                <div className="post-author">
                                                    <div className="name">{post.author || '匿名'}</div>
                                                    <div className="meta">{formatDiscussionTime(post.created_at) || '刚刚'}</div>
                                                </div>
                                                <div className="post-tag-line"><span>{post.topic || '讨论'}</span></div>
                                            </div>

                                            <h3 className="post-title">{post.title || '无标题'}</h3>
                                            <p className="post-excerpt">{post.content}</p>

                                            <div className="post-foot">
                                                <button
                                                    type="button"
                                                    className={`stat ${post.user_liked ? 'hot' : ''}`}
                                                    onClick={() => handleToggleDiscussionLike(post.id)}
                                                    disabled={discussionActionPostId === post.id}
                                                >
                                                    ★ {post.like_count || 0} 点赞
                                                </button>
                                                <span className="stat">🚩 {post.report_count || 0} 举报</span>
                                                <button
                                                    type="button"
                                                    className="stat"
                                                    onClick={() => handleReportDiscussionPost(post.id)}
                                                    disabled={discussionActionPostId === post.id || post.user_reported}
                                                >
                                                    {post.user_reported ? '已举报' : '📤 举报'}
                                                </button>
                                            </div>
                                        </article>
                                    ))}
                                </section>

                                <section id="publish-anchor" className="side-block" style={{ marginTop: '16px' }}>
                                    <h4>发布观点</h4>
                                    <div className="text-xs text-gray-500 mb-3">当前主题：{selectedDiscussionTopic || '请先选择主题'}</div>
                                    <input
                                        className="w-full rounded-xl border border-red-100 bg-white px-3 py-2.5 text-sm outline-none transition-all focus:border-red-300 focus:ring-2 focus:ring-red-200 mb-3"
                                        value={discussionTitle}
                                        onChange={(e) => setDiscussionTitle(e.target.value)}
                                        placeholder="可选：输入帖子标题"
                                        maxLength={80}
                                    />
                                    <textarea
                                        className="min-h-44 w-full rounded-2xl border border-red-100 bg-white px-3 py-3 text-sm leading-7 outline-none transition-all focus:border-red-300 focus:ring-2 focus:ring-red-200"
                                        value={discussionContent}
                                        onChange={(e) => setDiscussionContent(e.target.value)}
                                        placeholder="分享你的观点、故事、实践经历或思考..."
                                    />
                                    <button
                                        type="button"
                                        className="mt-3 w-full rounded-xl bg-linear-to-r from-red-500 to-red-700 px-4 py-2.5 text-sm font-bold text-white transition-all hover:from-red-600 hover:to-red-800 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed"
                                        onClick={handlePublishDiscussionPost}
                                        disabled={isDiscussionSubmitting || !selectedDiscussionTopic}
                                    >
                                        {isDiscussionSubmitting ? '发布中...' : '发布到当前主题'}
                                    </button>
                                </section>
                            </main>

                            <aside className="side-panel">
                                <div className="side-block">
                                    <h4>热门话题 <span className="more">更多</span></h4>
                                    {forumHotTopics.length === 0 && (
                                        <div className="hot-topic-item"><span className="rank">1</span><span>暂无热门话题数据</span></div>
                                    )}
                                    {forumHotTopics.map((post, idx) => (
                                        <div key={post.id} className="hot-topic-item" onClick={() => handleSelectDiscussionTopic(post.topic, currentDiscussionCategory?.category)}>
                                            <span className="rank">{idx + 1}</span>
                                            <span>{post.title || post.topic}</span>
                                            <span className="heat">{post.like_count || 0}</span>
                                        </div>
                                    ))}
                                </div>

                                <div className="side-block rank-list-block">
                                    <h4>活跃用户榜 <span className="more">本周</span></h4>
                                    {forumRankUsers.length === 0 && (
                                        <div className="rank-item"><span className="rank-no">-</span><div className="rank-info"><div className="name">暂无数据</div></div></div>
                                    )}
                                    {forumRankUsers.map((item, idx) => (
                                        <div key={item.name} className="rank-item">
                                            <span className={`rank-no ${idx === 0 ? 'r1' : idx === 1 ? 'r2' : idx === 2 ? 'r3' : ''}`}>{idx + 1}</span>
                                            <span className="rank-mini-avatar">{item.name.charAt(0)}</span>
                                            <div className="rank-info">
                                                <div className="name">{item.name}</div>
                                                <div className="branch">发帖 {item.posts} · 获赞 {item.likes}</div>
                                            </div>
                                            <span className="rank-score-mini">{item.likes}</span>
                                        </div>
                                    ))}
                                </div>

                                <div className="side-block" style={{ background: 'linear-gradient(135deg,#FCE8EB,#FBF3D9)' }}>
                                    <h4>论坛提示</h4>
                                    <div style={{ fontSize: '12.5px', lineHeight: 1.7, color: '#1A1A1A' }}>
                                        参与讨论时请结合<b style={{ color: '#8B1A1A' }}>政策依据</b>与
                                        <b style={{ color: '#8B1A1A' }}>个人实践</b>，有助于形成更有价值的观点交流。
                                    </div>
                                </div>
                            </aside>
                        </div>
                    )}

                    {activeWorkspace === 'game' && (
                        <div className="h-full overflow-y-auto pr-1">
                            <section className="bg-white border border-[rgba(139,26,26,.12)] rounded-xl p-5 shadow-sm mb-4">
                                <h2 className="text-2xl font-bold text-[#8B1A1A] mb-2" style={{ fontFamily: '"Source Han Serif CN","STSong","SimSun",serif' }}>红色足迹：韶山之旅</h2>
                                <p className="text-sm text-gray-600 mb-4">沉浸式游戏导学已接入。请先在后端运行 `python run.py`（backend 目录）后开始体验。</p>
                                <div className="flex gap-3 flex-wrap">
                                    <button
                                        type="button"
                                        className="rounded-lg bg-[#C8102E] text-white px-4 py-2 text-sm font-semibold hover:bg-[#8B1A1A]"
                                        onClick={() => window.open('https://shaoshan-game-production.up.railway.app/', '_blank', 'noopener,noreferrer')}
                                    >
                                        新窗口打开游戏
                                    </button>
                                    <span className="text-xs text-gray-500 self-center">若下方无法加载，请使用新窗口打开。</span>
                                </div>
                            </section>

                            <div className="bg-white border border-[rgba(139,26,26,.12)] rounded-xl shadow-sm overflow-hidden" style={{ height: 'calc(100vh - 260px)', minHeight: '560px' }}>
                                <iframe
                                    title="游戏导学"
                                    src="https://shaoshan-game-production.up.railway.app/"
                                    className="w-full h-full border-0"
                                    loading="lazy"
                                />
                            </div>
                        </div>
                    )}

                    {activeWorkspace === 'overview' && (
                        <DataOverview username={username} onBack={() => setHasEnteredChat(false)} />
                    )}

                    {activeWorkspace === 'profile' && (
                        <div className="h-full overflow-y-auto pr-1 space-y-4">

                            <section className="relative rounded-2xl overflow-hidden shadow-md" style={{ background: 'linear-gradient(135deg,#7B0C1E 0%,#B8102E 45%,#C8102E 60%,#8B4513 100%)' }}>
                                <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, #fff 1px, transparent 1px), radial-gradient(circle at 80% 20%, #fff 1px, transparent 1px)', backgroundSize: '40px 40px' }}></div>
                                <div className="absolute top-0 right-0 w-64 h-64 rounded-full opacity-5" style={{ background: '#D4A017', transform: 'translate(30%,-30%)' }}></div>

                                <div className="relative p-6 flex flex-col md:flex-row items-center md:items-start gap-6">
                                    <div className="flex flex-col items-center gap-2 shrink-0">
                                        <div className="w-24 h-24 rounded-full p-[3px]" style={{ background: 'conic-gradient(#D4A017 72%, rgba(212,160,23,.25) 0)' }}>
                                            <div className="w-full h-full rounded-full bg-white p-[2px]">
                                                <div className="w-full h-full rounded-full flex items-center justify-center text-white text-4xl font-bold relative" style={{ background: 'linear-gradient(135deg,#E5C088,#A0522D)' }}>
                                                    {username?.charAt(0) || '?'}
                                                    <span className="absolute -bottom-0.5 -right-0.5 w-6 h-6 rounded-full border-2 border-white text-xs flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#D4A017,#B8860B)', color: '#fff' }}>★</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex gap-1.5">
                                            <span className="px-2 py-0.5 text-[10px] rounded-full font-medium" style={{ background: 'rgba(212,160,23,.25)', color: '#FBE99E', border: '1px solid rgba(212,160,23,.4)' }}>党史先锋</span>
                                            <span className="px-2 py-0.5 text-[10px] rounded-full font-medium" style={{ background: 'rgba(255,255,255,.12)', color: '#fff', border: '1px solid rgba(255,255,255,.25)' }}>理论之星</span>
                                        </div>
                                    </div>

                                    <div className="flex-1 text-center md:text-left">
                                        <div className="text-white text-2xl font-bold" style={{ fontFamily: '"Source Han Serif CN","STSong","SimSun",serif', textShadow: '0 1px 6px rgba(0,0,0,.3)' }}>{username || '学员'}</div>
                                        <div className="text-[13px] mt-0.5" style={{ color: 'rgba(255,255,255,.65)' }}>{portrait.current_major && portrait.current_major !== '未设置' ? portrait.current_major : '思政学习者'}</div>

                                        <div className="mt-3 max-w-xs mx-auto md:mx-0">
                                            <div className="flex justify-between text-[11px] mb-1" style={{ color: 'rgba(255,255,255,.7)' }}>
                                                <span>学习等级 Lv.{Math.ceil(conversations.length / 5) + 1}</span>
                                                <span>距下一级 {Math.max(5 - (conversations.length % 5), 1)} 次对话</span>
                                            </div>
                                            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,.15)' }}>
                                                <div className="h-full rounded-full transition-all duration-700" style={{ width: `${(conversations.length % 5) / 5 * 100}%`, background: 'linear-gradient(90deg,#F5D57A,#D4A017)' }}></div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-3 gap-3 shrink-0">
                                        {[
                                            { icon: '⏳', val: Math.max(12, conversations.length * 3), label: '学时' },
                                            { icon: '★', val: Math.max(120, Math.round((portrait.ideal + portrait.logic + portrait.practice + portrait.psychological + portrait.emotion) * 5)), label: '积分' },
                                            { icon: '💬', val: conversations.length || 0, label: '问答数' },
                                        ].map(item => (
                                            <div key={item.label} className="text-center rounded-xl py-3 px-2" style={{ background: 'rgba(255,255,255,.1)', backdropFilter: 'blur(6px)', border: '1px solid rgba(255,255,255,.18)' }}>
                                                <div className="text-base mb-0.5">{item.icon}</div>
                                                <div className="text-xl font-bold text-white" style={{ fontFamily: 'serif' }}>{item.val}</div>
                                                <div className="text-[10px]" style={{ color: 'rgba(255,255,255,.65)' }}>{item.label}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </section>

                            <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
                                <section className="bg-white rounded-2xl border border-[rgba(139,26,26,.1)] shadow-sm overflow-hidden">
                                    <div className="px-5 py-3.5 border-b border-[rgba(139,26,26,.08)] flex items-center gap-2">
                                        <span className="w-1 h-5 rounded bg-[#C8102E]"></span>
                                        <span className="text-sm font-semibold text-[#1A1A1A]">思政素养画像</span>
                                    </div>
                                    <div className="p-5 grid gap-5 md:grid-cols-[200px_1fr] items-center">
                                        <div ref={radarRef} className="w-full h-[200px]"></div>
                                        <div className="space-y-3">
                                            {[
                                                { label: '理想信念', icon: '🏴', val: portrait.ideal || 0, color: '#C8102E' },
                                                { label: '逻辑思维', icon: '🧠', val: portrait.logic || 0, color: '#1565C0' },
                                                { label: '实践能力', icon: '⚡', val: portrait.practice || 0, color: '#2E7D32' },
                                                { label: '心理素质', icon: '🧘', val: portrait.psychological || 0, color: '#6A1B9A' },
                                                { label: '情感状态', icon: '❤️', val: portrait.emotion || 0, color: '#D4A017' },
                                            ].map((item) => {
                                                const pct = Math.max(0, Math.min(100, Number(item.val) || 0));
                                                return (
                                                    <div key={item.label}>
                                                        <div className="flex items-center justify-between mb-1">
                                                            <span className="text-xs text-gray-600 flex items-center gap-1.5"><span>{item.icon}</span>{item.label}</span>
                                                            <span className="text-xs font-bold" style={{ color: item.color }}>{Math.round(pct)}</span>
                                                        </div>
                                                        <div className="h-2 bg-[#f4f0eb] rounded-full overflow-hidden">
                                                            <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: `linear-gradient(90deg,${item.color}99,${item.color})` }}></div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </section>

                                <div className="space-y-4">
                                    <section className="bg-white rounded-2xl border border-[rgba(139,26,26,.1)] shadow-sm overflow-hidden">
                                        <div className="px-4 py-3 border-b border-[rgba(139,26,26,.08)] flex items-center gap-2">
                                            <span className="w-1 h-4 rounded bg-[#1565C0]"></span>
                                            <span className="text-sm font-semibold text-[#1A1A1A]">学习偏好</span>
                                        </div>
                                        <div className="p-4 flex flex-wrap gap-2">
                                            {(portrait.learning_preference && portrait.learning_preference.length > 0
                                                ? portrait.learning_preference
                                                : ['视觉型学习', '碎片化学习', '互动积极', '案例驱动']
                                            ).slice(0, 8).map((tag, idx) => (
                                                <span key={idx} className="px-2.5 py-1 text-[11px] rounded-full font-medium" style={{ background: 'rgba(21,101,192,.08)', color: '#1565C0', border: '1px solid rgba(21,101,192,.18)' }}>{tag}</span>
                                            ))}
                                        </div>
                                    </section>

                                    <section className="bg-white rounded-2xl border border-[rgba(139,26,26,.1)] shadow-sm overflow-hidden">
                                        <div className="px-4 py-3 border-b border-[rgba(139,26,26,.08)] flex items-center gap-2">
                                            <span className="w-1 h-4 rounded bg-[#C8102E]"></span>
                                            <span className="text-sm font-semibold text-[#1A1A1A]">隐性需求</span>
                                        </div>
                                        <div className="p-4 flex flex-wrap gap-2">
                                            {(portrait.hidden_needs && portrait.hidden_needs.length > 0
                                                ? portrait.hidden_needs
                                                : ['需要激励', '时间管理困难', '缺乏反馈']
                                            ).slice(0, 8).map((need, idx) => (
                                                <span key={idx} className="px-2.5 py-1 text-[11px] rounded-full font-medium" style={{ background: 'rgba(200,16,46,.07)', color: '#8B1A1A', border: '1px solid rgba(200,16,46,.2)' }}>• {need}</span>
                                            ))}
                                        </div>
                                    </section>

                                    <section className="bg-white rounded-2xl border border-[rgba(139,26,26,.1)] shadow-sm overflow-hidden">
                                        <div className="px-4 py-3 border-b border-[rgba(139,26,26,.08)] flex items-center gap-2">
                                            <span className="w-1 h-4 rounded bg-[#D4A017]"></span>
                                            <span className="text-sm font-semibold text-[#1A1A1A]">最近动态</span>
                                        </div>
                                        <div className="p-4 space-y-3">
                                            {[
                                                { icon: '✦', bg: 'rgba(200,16,46,.08)', color: '#C8102E', text: '向红芯提问并完成复盘' },
                                                { icon: '★', bg: 'rgba(212,160,23,.12)', color: '#8B6914', text: '参与论坛观点讨论' },
                                                { icon: '⛰', bg: 'rgba(46,125,50,.08)', color: '#2E7D32', text: '完成红色基地学习任务' },
                                            ].map((item, idx) => (
                                                <div key={idx} className="flex items-center gap-3 p-2.5 rounded-xl" style={{ background: item.bg }}>
                                                    <span className="w-7 h-7 rounded-full flex items-center justify-center text-sm shrink-0" style={{ background: item.bg, color: item.color, border: `1px solid ${item.color}30` }}>{item.icon}</span>
                                                    <span className="text-xs text-[#1A1A1A]">{item.text}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </section>
                                </div>
                            </div>

                            <section className="bg-white rounded-2xl border border-[rgba(139,26,26,.1)] shadow-sm overflow-hidden">
                                <div className="px-5 py-3.5 border-b border-[rgba(139,26,26,.08)] flex items-center gap-2">
                                    <span className="w-1 h-5 rounded bg-[#D4A017]"></span>
                                    <span className="text-sm font-semibold text-[#1A1A1A]">成就勋章</span>
                                </div>
                                <div className="p-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
                                    {[
                                        { icon: '🏅', name: '党史先锋', desc: '完成党史专题学习', earned: true },
                                        { icon: '📚', name: '理论之星', desc: '累计问答 10 次以上', earned: conversations.length >= 10 },
                                        { icon: '💬', name: '论坛达人', desc: '发布 5 条优质帖子', earned: false },
                                        { icon: '⛰', name: '红色足迹', desc: '完成游戏导学通关', earned: false },
                                    ].map((badge) => (
                                        <div key={badge.name} className="flex flex-col items-center gap-1.5 p-3 rounded-xl text-center transition-all duration-200" style={{ background: badge.earned ? 'linear-gradient(135deg,#FBF3D9,#F5E4A8)' : '#f8f8f8', border: `1px solid ${badge.earned ? 'rgba(212,160,23,.35)' : 'rgba(0,0,0,.07)'}`, opacity: badge.earned ? 1 : 0.5, filter: badge.earned ? 'none' : 'grayscale(1)' }}>
                                            <span className="text-3xl">{badge.icon}</span>
                                            <span className="text-xs font-bold" style={{ color: badge.earned ? '#8B6914' : '#999' }}>{badge.name}</span>
                                            <span className="text-[10px]" style={{ color: badge.earned ? '#A0862A' : '#bbb' }}>{badge.desc}</span>
                                        </div>
                                    ))}
                                </div>
                            </section>

                        </div>
                    )}

                </div>
            )}

            {showMessageAnalysis && selectedMessage && (
                <div className="fixed inset-0 bg-black/45 backdrop-blur-[1px] flex items-center justify-center p-4 z-50" onClick={() => setShowMessageAnalysis(false)}>
                    <div className="bg-white/95 w-full max-w-2xl rounded-2xl border border-red-100 shadow-[0_20px_55px_rgba(15,23,42,0.25)] p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-red-700 flex items-center gap-2">
                                <div className="w-2 h-6 bg-red-600 rounded"></div> 消息分析
                            </h2>
                            <button
                                type="button"
                                className="px-3 py-1.5 rounded-full text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                                onClick={() => setShowMessageAnalysis(false)}
                            >
                                关闭
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div className="bg-amber-50 p-4 rounded-xl border border-amber-100">
                                <p className="text-xs text-amber-600 font-bold mb-2 uppercase">💬 消息内容</p>
                                <p className="text-sm text-gray-800">{selectedMessage.content}</p>
                            </div>

                            <div className="bg-purple-50 p-4 rounded-xl border border-purple-100">
                                <p className="text-xs text-purple-600 font-bold mb-3 uppercase flex items-center gap-2">
                                    😊 情感评分
                                </p>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-gray-700">情感状态</span>
                                        <span className="text-2xl font-bold text-purple-700">
                                            {selectedMessage.analysis?.emotion_score?.toFixed(1) || 0}
                                            <span className="text-sm text-gray-500">/100</span>
                                        </span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                                        <div
                                            className="bg-linear-to-r from-purple-400 to-purple-600 h-full rounded-full transition-all duration-500"
                                            style={{ width: `${selectedMessage.analysis?.emotion_score || 0}%` }}
                                        ></div>
                                    </div>
                                    <p className="text-xs text-gray-500 mt-2">
                                        {selectedMessage.analysis?.emotion_score >= 80 ? '😊 情感状态积极向上' :
                                            selectedMessage.analysis?.emotion_score >= 60 ? '😐 情感状态较为平稳' :
                                                selectedMessage.analysis?.emotion_score >= 40 ? '😔 情感状态略显低落' :
                                                    '😢 情感状态需要关注'}
                                    </p>
                                </div>
                            </div>

                            <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                                <p className="text-xs text-blue-600 font-bold mb-3 uppercase flex items-center gap-2">
                                    🎯 隐形需求感知
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {selectedMessage.analysis?.hidden_needs && selectedMessage.analysis.hidden_needs.length > 0 ? (
                                        selectedMessage.analysis.hidden_needs.map((need, idx) => (
                                            <span key={idx} className="text-sm text-blue-900 bg-blue-100 px-3 py-2 rounded-lg border border-blue-200 shadow-sm">
                                                • {need}
                                            </span>
                                        ))
                                    ) : (
                                        <p className="text-sm text-blue-900 italic">暂无隐形需求分析数据</p>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {showAIAnalysis && selectedAIMessage && (
                <div className="fixed inset-0 bg-black/45 backdrop-blur-[1px] flex items-center justify-center p-4 z-50" onClick={() => setShowAIAnalysis(false)}>
                    <div className="bg-white/95 w-full max-w-2xl rounded-2xl border border-amber-100 shadow-[0_20px_55px_rgba(15,23,42,0.25)] p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-bold text-amber-700 flex items-center gap-2">
                                <div className="w-2 h-6 bg-amber-600 rounded"></div> AI回答分析
                            </h2>
                            <button
                                type="button"
                                className="px-3 py-1.5 rounded-full text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
                                onClick={() => setShowAIAnalysis(false)}
                            >
                                关闭
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div className="bg-purple-50 p-4 rounded-xl border border-purple-100">
                                <p className="text-xs text-purple-600 font-bold mb-3 uppercase flex items-center gap-2">
                                    ⭐ 回答评分
                                </p>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm text-gray-700">综合得分</span>
                                        <span className="text-2xl font-bold text-purple-700">
                                            {selectedAIMessage.aiAnalysis?.score?.toFixed(1) || 0}
                                            <span className="text-sm text-gray-500">/100</span>
                                        </span>
                                    </div>
                                    <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                                        <div
                                            className="bg-linear-to-r from-purple-400 to-purple-600 h-full rounded-full transition-all duration-500"
                                            style={{ width: `${selectedAIMessage.aiAnalysis?.score || 0}%` }}
                                        ></div>
                                    </div>
                                    <p className="text-xs text-gray-500 mt-2">
                                        {selectedAIMessage.aiAnalysis?.score >= 90 ? '🌟 优秀回答' :
                                            selectedAIMessage.aiAnalysis?.score >= 80 ? '👍 良好回答' :
                                                selectedAIMessage.aiAnalysis?.score >= 70 ? '✅ 合格回答' :
                                                    '⚠️ 需要改进'}
                                    </p>
                                    {selectedAIMessage.aiAnalysis?.selected_model && (
                                        <div className="mt-3 pt-3 border-t border-purple-200">
                                            <p className="text-xs text-gray-600 mb-2">选择的模型: <span className="font-semibold text-purple-700">{selectedAIMessage.aiAnalysis.selected_model}</span></p>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {selectedAIMessage.aiAnalysis?.model_comparison && Object.keys(selectedAIMessage.aiAnalysis.model_comparison).length > 0 && (
                                <div className="bg-linear-to-r from-indigo-50 to-purple-50 p-4 rounded-xl border border-indigo-200">
                                    <p className="text-xs text-indigo-600 font-bold mb-3 uppercase">📊 三模型评分对比</p>
                                    <div className="grid grid-cols-3 gap-3">
                                        {Object.entries(selectedAIMessage.aiAnalysis.model_comparison).map(([model, data]) => (
                                            <div key={model} className="bg-white p-3 rounded-lg border-2 border-indigo-100 text-center hover:border-indigo-300 transition-colors">
                                                <p className="text-xs text-gray-500 mb-1 uppercase font-semibold">{model}</p>
                                                <p className="text-2xl font-bold text-indigo-700">{data.score?.toFixed(1) || 0}</p>
                                                <p className="text-xs text-gray-400 mt-1">/100</p>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {selectedAIMessage.aiAnalysis?.feedback && (
                                <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                                    <p className="text-xs text-blue-600 font-bold mb-2 uppercase flex items-center gap-2">
                                        💭 综合评价反馈
                                    </p>
                                    <p className="text-sm text-gray-700 whitespace-pre-wrap">{selectedAIMessage.aiAnalysis.feedback}</p>
                                </div>
                            )}

                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;