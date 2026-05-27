'use client';

import { useState, useEffect } from 'react';

interface MonitoredPost {
    id: string;
    post_content: string;
    post_url: string;
    author_name: string;
    author_avatar_url: string | null;
    posted_at: string;
    likes_count: number;
    comments_count: number;
    ai_relevance_score: number;
    ai_reason: string;
    suggested_comment: string | null;
    monitored_profiles: {
        profile_name: string;
        profile_vanity_name: string;
        profile_avatar_url: string | null;
    } | null;
}

interface Stats {
    total: number;
    relevant: number;
    unanalyzed: number;
}

export default function TrendsPage() {
    const [posts, setPosts] = useState<MonitoredPost[]>([]);
    const [stats, setStats] = useState<Stats>({ total: 0, relevant: 0, unanalyzed: 0 });
    const [loading, setLoading] = useState(true);
    const [fetching, setFetching] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [featureEnabled, setFeatureEnabled] = useState(false);
    const [hasProfiles, setHasProfiles] = useState(false);
    const [copiedId, setCopiedId] = useState<string | null>(null);

    useEffect(() => {
        checkFeatureAndLoad();
    }, []);

    const checkFeatureAndLoad = async () => {
        setLoading(true);
        try {
            // Check if feature is enabled
            const settingsRes = await fetch('/api/settings');
            const settingsData = await settingsRes.json();
            const enabled = settingsData.settings?.trends_monitoring_enabled || false;
            setFeatureEnabled(enabled);

            if (!enabled) {
                setLoading(false);
                return;
            }

            // Check if user has profiles
            const profilesRes = await fetch('/api/trends/profiles');
            const profilesData = await profilesRes.json();
            setHasProfiles((profilesData.profiles?.length || 0) > 0);

            // Load posts
            await loadPosts();
        } catch (error) {
            console.error('Error loading trends:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadPosts = async () => {
        try {
            const res = await fetch('/api/trends/posts');
            const data = await res.json();
            if (data.success) {
                setPosts(data.posts || []);
                setStats(data.stats || { total: 0, relevant: 0, unanalyzed: 0 });
            }
        } catch (error) {
            console.error('Error loading posts:', error);
        }
    };

    const handleFetch = async () => {
        setFetching(true);
        try {
            const res = await fetch('/api/trends/fetch', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(`✅ ${data.posts_count} posts coletados!`);
                await loadPosts();
            } else {
                alert(data.error || 'Erro ao buscar posts');
            }
        } catch (error) {
            console.error('Error fetching:', error);
            alert('Erro ao buscar posts');
        } finally {
            setFetching(false);
        }
    };

    const handleAnalyze = async () => {
        setAnalyzing(true);
        try {
            const res = await fetch('/api/trends/analyze', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(`✅ ${data.analyzed_count} posts analisados, ${data.relevant_count} relevantes!`);
                await loadPosts();
            } else {
                alert(data.error || 'Erro ao analisar posts');
            }
        } catch (error) {
            console.error('Error analyzing:', error);
            alert('Erro ao analisar posts');
        } finally {
            setAnalyzing(false);
        }
    };

    const handleAction = async (postId: string, action: string) => {
        setActionLoading(postId);
        try {
            const res = await fetch('/api/trends/posts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ post_id: postId, action }),
            });
            const data = await res.json();
            if (data.success) {
                // Remove post from list
                setPosts(prev => prev.filter(p => p.id !== postId));
            }
        } catch (error) {
            console.error('Error marking action:', error);
        } finally {
            setActionLoading(null);
        }
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

        if (diffHours < 1) return 'há poucos minutos';
        if (diffHours < 24) return `há ${diffHours}h`;
        const diffDays = Math.floor(diffHours / 24);
        return `há ${diffDays}d`;
    };

    const getScoreBadge = (score: number) => {
        if (score >= 80) return { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Alta' };
        if (score >= 60) return { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Média' };
        return { bg: 'bg-neutral-100', text: 'text-neutral-600', label: 'Baixa' };
    };

    const copyToClipboard = async (text: string, postId: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedId(postId);
            setTimeout(() => setCopiedId(null), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    if (loading) {
        return (
            <div className="min-h-[80vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
                    <p className="text-sm text-neutral-500">Carregando tendências...</p>
                </div>
            </div>
        );
    }

    if (!featureEnabled) {
        return (
            <div className="min-h-screen bg-neutral-50">
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
                    <div className="text-center">
                        <div className="w-16 h-16 mx-auto mb-6 bg-orange-100 rounded-2xl flex items-center justify-center">
                            <svg className="w-8 h-8 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                            </svg>
                        </div>
                        <h1 className="text-2xl font-semibold text-neutral-900 mb-2">Acompanhamento de Tendências</h1>
                        <p className="text-neutral-500 mb-8">
                            Esta funcionalidade permite monitorar perfis do LinkedIn e receber sugestões de posts para engajar.
                        </p>
                        <a
                            href="/settings"
                            className="inline-flex items-center gap-2 px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white rounded-xl font-medium transition-colors"
                        >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            </svg>
                            Ativar nas Configurações
                        </a>
                    </div>
                </div>
            </div>
        );
    }

    if (!hasProfiles) {
        return (
            <div className="min-h-screen bg-neutral-50">
                <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
                    <div className="text-center">
                        <div className="w-16 h-16 mx-auto mb-6 bg-neutral-100 rounded-2xl flex items-center justify-center">
                            <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                            </svg>
                        </div>
                        <h1 className="text-2xl font-semibold text-neutral-900 mb-2">Nenhum perfil monitorado</h1>
                        <p className="text-neutral-500 mb-8">
                            Adicione perfis do LinkedIn para começar a receber sugestões de posts para engajar.
                        </p>
                        <a
                            href="/settings"
                            className="inline-flex items-center gap-2 px-6 py-3 bg-neutral-900 hover:bg-neutral-800 text-white rounded-xl font-medium transition-colors"
                        >
                            Adicionar Perfis
                        </a>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-neutral-50">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <header className="mb-8">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-semibold text-neutral-900">Tendências</h1>
                            <p className="text-sm text-neutral-500 mt-1">
                                Posts relevantes para você engajar
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={handleFetch}
                                disabled={fetching}
                                className="px-4 py-2 bg-white border border-neutral-200 rounded-lg text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 transition-colors flex items-center gap-2"
                            >
                                {fetching ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                        Buscando...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                        </svg>
                                        Buscar Posts
                                    </>
                                )}
                            </button>
                            {stats.unanalyzed > 0 && (
                                <button
                                    onClick={handleAnalyze}
                                    disabled={analyzing}
                                    className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-50 transition-colors flex items-center gap-2"
                                >
                                    {analyzing ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                            Analisando...
                                        </>
                                    ) : (
                                        <>
                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                            </svg>
                                            Analisar ({stats.unanalyzed})
                                        </>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Stats */}
                    <div className="flex items-center gap-4 mt-4">
                        <span className="text-xs text-neutral-500">
                            <strong className="text-neutral-700">{stats.total}</strong> posts coletados
                        </span>
                        <span className="text-xs text-neutral-500">
                            <strong className="text-emerald-600">{stats.relevant}</strong> relevantes
                        </span>
                    </div>
                </header>

                {/* Posts List */}
                {posts.length === 0 ? (
                    <div className="bg-white rounded-2xl border border-neutral-200 p-12 text-center">
                        <div className="w-12 h-12 mx-auto mb-4 bg-neutral-100 rounded-xl flex items-center justify-center">
                            <svg className="w-6 h-6 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                        </div>
                        <p className="text-neutral-500 mb-4">Nenhum post relevante encontrado</p>
                        <p className="text-xs text-neutral-400">
                            Clique em "Buscar Posts" para coletar posts dos perfis monitorados
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {posts.map((post) => {
                            const scoreBadge = getScoreBadge(post.ai_relevance_score);
                            return (
                                <div
                                    key={post.id}
                                    className="bg-white rounded-2xl border border-neutral-200 p-5 hover:shadow-md transition-shadow"
                                >
                                    {/* Header */}
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded-full bg-neutral-200 flex items-center justify-center overflow-hidden">
                                                {post.author_avatar_url || post.monitored_profiles?.profile_avatar_url ? (
                                                    <img
                                                        src={post.author_avatar_url || post.monitored_profiles?.profile_avatar_url || ''}
                                                        alt={post.author_name}
                                                        className="w-full h-full object-cover"
                                                    />
                                                ) : (
                                                    <span className="text-sm font-medium text-neutral-600">
                                                        {(post.author_name || 'U').charAt(0).toUpperCase()}
                                                    </span>
                                                )}
                                            </div>
                                            <div>
                                                <p className="text-sm font-medium text-neutral-900">
                                                    {post.author_name || post.monitored_profiles?.profile_name}
                                                </p>
                                                <p className="text-xs text-neutral-400">
                                                    {formatDate(post.posted_at)}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className={`px-2 py-1 rounded-full text-[10px] font-medium ${scoreBadge.bg} ${scoreBadge.text}`}>
                                                {scoreBadge.label} ({post.ai_relevance_score}%)
                                            </span>
                                        </div>
                                    </div>

                                    {/* Content */}
                                    <p className="text-sm text-neutral-700 mb-3 whitespace-pre-wrap line-clamp-4">
                                        {post.post_content}
                                    </p>

                                    {/* AI Reason */}
                                    {post.ai_reason && (
                                        <div className="bg-orange-50 border border-orange-100 rounded-lg p-3 mb-3">
                                            <p className="text-xs text-orange-700">
                                                <strong>💡 Por que engajar:</strong> {post.ai_reason}
                                            </p>
                                        </div>
                                    )}

                                    {/* Suggested Comment */}
                                    {post.suggested_comment && (
                                        <div className="bg-violet-50 border border-violet-100 rounded-lg p-3 mb-3">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="flex-1">
                                                    <p className="text-xs font-medium text-violet-700 mb-1">💬 Comentário sugerido:</p>
                                                    <p className="text-sm text-violet-900">{post.suggested_comment}</p>
                                                </div>
                                                <button
                                                    onClick={() => copyToClipboard(post.suggested_comment!, post.id)}
                                                    className={`flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${copiedId === post.id
                                                            ? 'bg-emerald-500 text-white'
                                                            : 'bg-violet-200 text-violet-700 hover:bg-violet-300'
                                                        }`}
                                                >
                                                    {copiedId === post.id ? '✓ Copiado!' : '📋 Copiar'}
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Engagement stats */}
                                    <div className="flex items-center gap-4 mb-4 text-xs text-neutral-400">
                                        <span>👍 {post.likes_count}</span>
                                        <span>💬 {post.comments_count}</span>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex items-center gap-2 pt-3 border-t border-neutral-100">
                                        <a
                                            href={post.post_url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                                        >
                                            Abrir no LinkedIn
                                        </a>
                                        <button
                                            onClick={() => handleAction(post.id, 'liked')}
                                            disabled={actionLoading === post.id}
                                            className="px-3 py-1.5 text-xs font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors disabled:opacity-50"
                                        >
                                            ✓ Curti
                                        </button>
                                        <button
                                            onClick={() => handleAction(post.id, 'commented')}
                                            disabled={actionLoading === post.id}
                                            className="px-3 py-1.5 text-xs font-medium text-violet-600 bg-violet-50 hover:bg-violet-100 rounded-lg transition-colors disabled:opacity-50"
                                        >
                                            ✓ Comentei
                                        </button>
                                        <button
                                            onClick={() => handleAction(post.id, 'dismissed')}
                                            disabled={actionLoading === post.id}
                                            className="px-3 py-1.5 text-xs font-medium text-neutral-500 bg-neutral-100 hover:bg-neutral-200 rounded-lg transition-colors disabled:opacity-50"
                                        >
                                            Ignorar
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
