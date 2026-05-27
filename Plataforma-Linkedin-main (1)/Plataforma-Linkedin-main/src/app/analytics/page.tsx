'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/utils/supabase/client';

interface PostAnalytics {
    post_id: string;
    social_id: string;
    caption: string;
    published_at: string;
    reaction_counter: number;
    comment_counter: number;
    repost_counter: number;
    impressions_counter: number;
    linkedin_post_urn?: string;
    analytics?: {
        impressions: number;
        engagements: number;
        engagement_rate: number;
        clicks: number;
        clickthrough_rate: number;
        followers_gained_from_this_post: number;
    };
}

interface AggregatedAnalytics {
    totalPosts: number;
    totalReactions: number;
    totalComments: number;
    totalReposts: number;
    totalImpressions: number;
    totalEngagements: number;
    totalClicks: number;
    avgEngagementRate: number;
    totalFollowersGained: number;
    posts: PostAnalytics[];
    topPerformingPost: PostAnalytics | null;
    lastUpdated: string | null;
}

interface Comment {
    id: string;
    author: string | { id: string; name: string; headline?: string; avatar_url?: string | null; profile_url?: string };
    text: string;
    date: string;
    reaction_counter?: number;
    reply_counter?: number;
}

export default function AnalyticsPage() {
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [analytics, setAnalytics] = useState<AggregatedAnalytics | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Community Management app connection state
    const [communityConnected, setCommunityConnected] = useState<boolean | null>(null);
    const [checkingCommunity, setCheckingCommunity] = useState(false);

    // Comments Modal State
    const [commentsModal, setCommentsModal] = useState<{
        open: boolean;
        post: PostAnalytics | null;
        loading: boolean;
        comments: Comment[];
        socialId: string | null;
        replyText: string;
        replying: boolean;
        liking: string | null;
        replyingToId: string | null;
        generatingReply: boolean;
    }>({
        open: false,
        post: null,
        loading: false,
        comments: [],
        socialId: null,
        replyText: '',
        replying: false,
        liking: null,
        replyingToId: null,
        generatingReply: false,
    });

    useEffect(() => {
        fetchAnalytics();
        checkCommunityStatus();
    }, []);

    // Check if user has connected the Community Management app
    const checkCommunityStatus = async () => {
        try {
            setCheckingCommunity(true);
            const res = await fetch('/api/linkedin-community/status');
            const data = await res.json();
            setCommunityConnected(data.connected === true);
        } catch (e) {
            setCommunityConnected(false);
        } finally {
            setCheckingCommunity(false);
        }
    };

    // Disconnect Analytics
    const handleDisconnect = async () => {
        if (!confirm('Tem certeza que deseja desconectar o Analytics Avançado? Você precisará reconectar para ver métricas e interagir.')) {
            return;
        }

        try {
            setCheckingCommunity(true);
            const response = await fetch('/api/linkedin-community/auth', {
                method: 'DELETE',
            });
            const data = await response.json();

            if (data.success) {
                setCommunityConnected(false);
                alert('Analytics desconectado com sucesso. Conecte novamente para atualizar as permissões.');
            } else {
                alert(data.error || 'Erro ao desconectar');
            }
        } catch (error: any) {
            alert(error.message || 'Erro ao desconectar');
        } finally {
            setCheckingCommunity(false);
        }
    };

    const fetchAnalytics = async () => {
        try {
            setLoading(true);
            setError(null);

            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session?.access_token) {
                setError('Faça login para ver análises');
                setLoading(false);
                return;
            }

            const response = await fetch('/api/analytics', {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });

            const data = await response.json();

            if (data.success) {
                setAnalytics(data.analytics);
            } else {
                setError(data.error || 'Erro ao carregar análises');
            }
        } catch (err: any) {
            setError(err.message || 'Erro ao carregar análises');
        } finally {
            setLoading(false);
        }
    };

    const refreshAnalytics = async () => {
        try {
            setRefreshing(true);
            setError(null);

            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session?.access_token) {
                setError('Faça login para atualizar análises');
                setRefreshing(false);
                return;
            }

            const response = await fetch('/api/analytics', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });

            const data = await response.json();

            if (data.success) {
                await fetchAnalytics();
                alert(`✅ ${data.message}`);
            } else {
                setError(data.error || 'Erro ao atualizar análises');
            }
        } catch (err: any) {
            setError(err.message || 'Erro ao atualizar análises');
        } finally {
            setRefreshing(false);
        }
    };

    // View Comments
    const handleViewComments = async (post: PostAnalytics) => {
        setCommentsModal({
            open: true,
            post,
            loading: true,
            comments: [],
            socialId: post.social_id || null,
            replyText: '',
            replying: false,
            liking: null,
            replyingToId: null,
            generatingReply: false,
        });

        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session?.access_token) {
                setCommentsModal(prev => ({ ...prev, loading: false }));
                return;
            }

            const urn = post.linkedin_post_urn || post.social_id;
            const response = await fetch(`/api/linkedin/comments?post_urn=${encodeURIComponent(urn)}`, {
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                },
            });

            const data = await response.json();

            // Comments API returns { connected: true, comments: [...], postUrn: ... }
            if (response.ok && data.connected) {
                // Check if API returned an informational message
                if (data.info && data.comments?.length === 0) {
                    setCommentsModal(prev => ({
                        ...prev,
                        loading: false,
                        comments: [],
                        socialId: data.postUrn || prev.socialId,
                    }));
                    // Show info message to user
                    alert(data.info);
                } else {
                    setCommentsModal(prev => ({
                        ...prev,
                        loading: false,
                        comments: data.comments || [],
                        socialId: data.postUrn || data.socialId || prev.socialId,
                    }));
                }
            } else {
                setCommentsModal(prev => ({ ...prev, loading: false }));
                alert(data.error || 'Erro ao carregar comentários');
            }
        } catch (error: any) {
            setCommentsModal(prev => ({ ...prev, loading: false }));
            alert(error.message || 'Erro ao carregar comentários');
        }
    };

    // Reply to Post
    const handleReplyToPost = async () => {
        if (!commentsModal.replyText.trim() || !commentsModal.socialId) return;

        setCommentsModal(prev => ({ ...prev, replying: true }));

        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session?.access_token) {
                throw new Error('Sessão expirada');
            }

            const replyingToCommentId = commentsModal.replyingToId !== 'post' ? commentsModal.replyingToId : null;

            const response = await fetch('/api/linkedin/comments', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    post_urn: commentsModal.socialId,
                    text: commentsModal.replyText,
                }),
            });

            const data = await response.json();

            if (data.success) {
                // Reload comments
                if (commentsModal.post) {
                    handleViewComments(commentsModal.post);
                }
                setCommentsModal(prev => ({ ...prev, replyText: '', replying: false, replyingToId: null }));
            } else {
                alert(data.error || 'Erro ao enviar comentário');
                setCommentsModal(prev => ({ ...prev, replying: false }));
            }
        } catch (error: any) {
            alert(error.message || 'Erro ao enviar comentário');
            setCommentsModal(prev => ({ ...prev, replying: false }));
        }
    };

    // Generate AI Reply
    const generateAIReply = async (
        responseType: 'agradecer' | 'agregar_valor' | 'resposta_simples' | 'perguntar',
        commentText: string,
        commentAuthor: string
    ) => {
        setCommentsModal(prev => ({ ...prev, generatingReply: true }));

        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session?.access_token) {
                throw new Error('Sessão expirada');
            }

            const response = await fetch('/api/generate-comment-reply', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    post_text: commentsModal.post?.caption || '',
                    comment_text: commentText,
                    comment_author: commentAuthor,
                    response_type: responseType,
                }),
            });

            const data = await response.json();

            if (data.success && data.reply) {
                setCommentsModal(prev => ({ ...prev, replyText: data.reply, generatingReply: false }));
            } else {
                alert(data.error || 'Erro ao gerar resposta');
                setCommentsModal(prev => ({ ...prev, generatingReply: false }));
            }
        } catch (error: any) {
            alert(error.message || 'Erro ao gerar resposta');
            setCommentsModal(prev => ({ ...prev, generatingReply: false }));
        }
    };

    // Like Comment - Using LinkedIn Reactions API v202505
    const handleLikeComment = async (commentId: string) => {
        try {
            const supabase = createClient();
            const { data: { session } } = await supabase.auth.getSession();

            if (!session?.access_token) {
                alert('Você precisa estar logado');
                return;
            }

            const response = await fetch('/api/linkedin/comments/react', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${session.access_token}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    comment_urn: commentId,
                    action: 'like',
                }),
            });

            const data = await response.json();

            if (data.success) {
                // Refresh comments to update like count
                if (commentsModal.post) {
                    handleViewComments(commentsModal.post);
                }
            } else {
                alert(data.error || 'Erro ao curtir comentário');
            }
        } catch (error: any) {
            alert(error.message || 'Erro ao curtir comentário');
        }
    };

    const formatNumber = (num: number) => {
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
        return num.toString();
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    if (loading) {
        return (
            <div className="min-h-[80vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
                    <p className="text-sm text-neutral-500">Carregando análises...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-neutral-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <header className="mb-8 animate-fadeIn">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">Análise de Resultados</h1>
                            <p className="text-sm text-neutral-500 mt-1">
                                Métricas de performance dos seus posts no LinkedIn
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            {/* Community connection button */}
                            {communityConnected === false && (
                                <a
                                    href="/api/linkedin-community/auth"
                                    className="px-3 py-2 rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white text-xs font-medium transition-all flex items-center gap-2 shadow-sm"
                                >
                                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
                                    </svg>
                                    Conectar Analytics Avançado
                                </a>
                            )}
                            {communityConnected === true && (
                                <div className="flex items-center gap-2">
                                    <span className="px-2 py-1 rounded-full bg-green-100 text-green-700 text-[10px] font-medium flex items-center gap-1">
                                        <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                                        Analytics conectado
                                    </span>
                                    <button
                                        onClick={handleDisconnect}
                                        disabled={checkingCommunity}
                                        className="px-2 py-1 rounded-lg bg-red-100 hover:bg-red-200 text-red-700 text-[10px] font-medium transition-colors"
                                        title="Desconectar para revalidar permissões"
                                    >
                                        Desconectar
                                    </button>
                                </div>
                            )}
                            {analytics?.lastUpdated && (
                                <span className="text-xs text-neutral-400">
                                    Atualizado: {formatDate(analytics.lastUpdated)}
                                </span>
                            )}
                            <button
                                onClick={refreshAnalytics}
                                disabled={refreshing}
                                className="px-4 py-2 rounded-lg bg-neutral-900 hover:bg-neutral-800 disabled:bg-neutral-400 text-white text-sm font-medium transition-all flex items-center gap-2"
                            >
                                {refreshing ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-neutral-500 border-t-white rounded-full animate-spin"></div>
                                        Atualizando...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                        </svg>
                                        Atualizar Analytics
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </header>

                {
                    error && (
                        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                            {error}
                        </div>
                    )
                }

                {
                    analytics && analytics.totalPosts === 0 ? (
                        <div className="bg-white border border-dashed border-neutral-300 p-12 rounded-2xl text-center">
                            <div className="w-16 h-16 bg-neutral-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                                <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                            </div>
                            <h3 className="text-lg font-semibold text-neutral-900 mb-2">Nenhum post publicado</h3>
                            <p className="text-neutral-500 text-sm">
                                Publique posts no LinkedIn para ver análises aqui
                            </p>
                        </div>
                    ) : analytics && (
                        <div className="space-y-6">
                            {/* Section 1: Métricas de Engajamento */}
                            <section className="bg-white rounded-2xl border border-neutral-200 overflow-hidden animate-fadeIn">
                                <div className="px-6 py-4 border-b border-neutral-100">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                                            <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                                            </svg>
                                        </div>
                                        <div>
                                            <h2 className="text-base font-semibold text-neutral-900">Métricas de Engajamento</h2>
                                            <p className="text-xs text-neutral-500">Interações totais nos seus posts</p>
                                        </div>
                                    </div>
                                </div>
                                <div className="p-6">
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div className="bg-gradient-to-br from-rose-50 to-rose-100 rounded-xl p-4 border border-rose-200">
                                            <div className="text-2xl font-bold text-rose-700">{formatNumber(analytics.totalReactions)}</div>
                                            <div className="text-xs text-rose-600 mt-1">Reações</div>
                                        </div>
                                        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-4 border border-blue-200">
                                            <div className="text-2xl font-bold text-blue-700">{formatNumber(analytics.totalComments)}</div>
                                            <div className="text-xs text-blue-600 mt-1">Comentários</div>
                                        </div>
                                        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200">
                                            <div className="text-2xl font-bold text-purple-700">{formatNumber(analytics.totalReposts)}</div>
                                            <div className="text-xs text-purple-600 mt-1">Compartilhamentos</div>
                                        </div>
                                        <div className="bg-gradient-to-br from-amber-50 to-amber-100 rounded-xl p-4 border border-amber-200">
                                            <div className="text-2xl font-bold text-amber-700">{analytics.avgEngagementRate.toFixed(2)}%</div>
                                            <div className="text-xs text-amber-600 mt-1">Taxa de Engajamento</div>
                                        </div>
                                    </div>
                                </div>
                            </section>

                            {/* Section 2: Alcance dos Posts */}
                            <section className="bg-white rounded-2xl border border-neutral-200 overflow-hidden animate-fadeIn" style={{ animationDelay: '0.1s' }}>
                                <div className="px-6 py-4 border-b border-neutral-100">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                                            <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                        </div>
                                        <div>
                                            <h2 className="text-base font-semibold text-neutral-900">Alcance dos Posts</h2>
                                            <p className="text-xs text-neutral-500">Visualizações e impressões</p>
                                        </div>
                                    </div>
                                </div>
                                <div className="p-6">
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 rounded-xl p-4 border border-indigo-200">
                                            <div className="text-2xl font-bold text-indigo-700">{formatNumber(analytics.totalImpressions)}</div>
                                            <div className="text-xs text-indigo-600 mt-1">Impressões</div>
                                        </div>
                                        <div className="bg-gradient-to-br from-cyan-50 to-cyan-100 rounded-xl p-4 border border-cyan-200">
                                            <div className="text-2xl font-bold text-cyan-700">{formatNumber(analytics.totalClicks)}</div>
                                            <div className="text-xs text-cyan-600 mt-1">Cliques</div>
                                        </div>
                                        <div className="bg-gradient-to-br from-teal-50 to-teal-100 rounded-xl p-4 border border-teal-200">
                                            <div className="text-2xl font-bold text-teal-700">{formatNumber(analytics.totalFollowersGained)}</div>
                                            <div className="text-xs text-teal-600 mt-1">Novos Seguidores</div>
                                        </div>
                                        <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl p-4 border border-slate-200">
                                            <div className="text-2xl font-bold text-slate-700">{analytics.totalPosts}</div>
                                            <div className="text-xs text-slate-600 mt-1">Posts Publicados</div>
                                        </div>
                                    </div>
                                </div>
                            </section>

                            {/* Section 3: Feedback e Comentários */}
                            <section className="bg-white rounded-2xl border border-neutral-200 overflow-hidden animate-fadeIn" style={{ animationDelay: '0.2s' }}>
                                <div className="px-6 py-4 border-b border-neutral-100">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
                                            <svg className="w-5 h-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                            </svg>
                                        </div>
                                        <div>
                                            <h2 className="text-base font-semibold text-neutral-900">Feedback e Comentários</h2>
                                            <p className="text-xs text-neutral-500">Visualize e responda comentários dos seus posts</p>
                                        </div>
                                    </div>
                                </div>
                                <div className="p-6">
                                    {/* Posts Grid with Comments */}
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                        {analytics.posts.map((post) => (
                                            <div
                                                key={post.post_id}
                                                className="bg-neutral-50 rounded-xl border border-neutral-200 overflow-hidden hover:border-neutral-300 hover:shadow-sm transition-all"
                                            >
                                                {/* Post Preview */}
                                                <div className="p-4">
                                                    <p className="text-sm text-neutral-800 line-clamp-3 mb-3 min-h-[60px]">
                                                        {post.caption.substring(0, 120)}...
                                                    </p>
                                                    <div className="flex items-center gap-3 text-xs text-neutral-500 mb-3">
                                                        <span className="text-rose-600">❤️ {post.reaction_counter}</span>
                                                        <span className="text-blue-600 font-medium">💬 {post.comment_counter}</span>
                                                        <span className="text-neutral-400 ml-auto text-[10px]">
                                                            {new Date(post.published_at).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
                                                        </span>
                                                    </div>
                                                </div>
                                                {/* View Comments Button */}
                                                <div className="px-4 pb-4">
                                                    <button
                                                        onClick={() => handleViewComments(post)}
                                                        disabled={post.comment_counter === 0}
                                                        className={`w-full py-2 px-3 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-all ${post.comment_counter > 0
                                                            ? 'bg-violet-100 text-violet-700 hover:bg-violet-200'
                                                            : 'bg-neutral-100 text-neutral-400 cursor-not-allowed'
                                                            }`}
                                                    >
                                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                                        </svg>
                                                        {post.comment_counter > 0 ? `Ver ${post.comment_counter} Comentário${post.comment_counter > 1 ? 's' : ''}` : 'Sem comentários'}
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </section>
                        </div>
                    )
                }
            </div >

            {/* Comments Modal */}
            {
                commentsModal.open && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                        <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col animate-fadeIn">
                            {/* Modal Header */}
                            <div className="px-6 py-4 border-b border-neutral-100 flex justify-between items-center flex-shrink-0">
                                <div>
                                    <h2 className="text-lg font-semibold text-neutral-900">Comentários</h2>
                                    <p className="text-xs text-neutral-500 mt-0.5 line-clamp-1">
                                        {commentsModal.post?.caption.substring(0, 60)}...
                                    </p>
                                </div>
                                <button
                                    onClick={() => setCommentsModal(prev => ({ ...prev, open: false }))}
                                    className="w-8 h-8 rounded-full bg-neutral-100 hover:bg-neutral-200 flex items-center justify-center text-neutral-500 hover:text-neutral-700 transition-colors"
                                >
                                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>

                            {/* Modal Body */}
                            <div className="flex-1 overflow-y-auto p-6">
                                {commentsModal.loading ? (
                                    <div className="flex items-center justify-center py-12">
                                        <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
                                    </div>
                                ) : commentsModal.comments.length === 0 ? (
                                    <div className="text-center py-12 text-neutral-500 text-sm">
                                        Nenhum comentário ainda
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {commentsModal.comments.map((comment) => {
                                            // Handle author as string or object
                                            const authorName = typeof comment.author === 'string'
                                                ? comment.author
                                                : comment.author?.name || 'Anônimo';
                                            const avatarUrl = typeof comment.author === 'object'
                                                ? comment.author?.avatar_url
                                                : null;

                                            return (
                                                <div key={comment.id} className="bg-neutral-50 rounded-xl p-4 border border-neutral-200">
                                                    <div className="flex items-start gap-3">
                                                        {avatarUrl ? (
                                                            <img
                                                                src={avatarUrl}
                                                                alt={authorName}
                                                                className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                                                            />
                                                        ) : (
                                                            <div className="w-10 h-10 rounded-full bg-neutral-200 flex items-center justify-center flex-shrink-0">
                                                                <span className="text-neutral-500 text-sm font-medium">
                                                                    {authorName.charAt(0)}
                                                                </span>
                                                            </div>
                                                        )}
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-center justify-between gap-2">
                                                                <p className="text-sm font-medium text-neutral-900 truncate">{authorName}</p>
                                                                <span className="text-[10px] text-neutral-400 flex-shrink-0">
                                                                    {new Date(comment.date).toLocaleDateString('pt-BR', {
                                                                        day: '2-digit',
                                                                        month: 'short',
                                                                    })}
                                                                </span>
                                                            </div>
                                                            <p className="text-sm text-neutral-700 mt-1">{comment.text}</p>
                                                            <div className="flex items-center gap-3 mt-3">
                                                                <button
                                                                    onClick={() => handleLikeComment(comment.id)}
                                                                    disabled={commentsModal.liking === comment.id}
                                                                    className="text-xs text-neutral-500 hover:text-rose-600 flex items-center gap-1 transition-colors"
                                                                >
                                                                    {commentsModal.liking === comment.id ? (
                                                                        <div className="w-3 h-3 border border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                                                    ) : (
                                                                        <span>❤️</span>
                                                                    )}
                                                                    {comment.reaction_counter || 0}
                                                                </button>
                                                                <button
                                                                    onClick={() => setCommentsModal(prev => ({
                                                                        ...prev,
                                                                        replyingToId: comment.id,
                                                                        replyText: '',
                                                                    }))}
                                                                    className="text-xs text-neutral-500 hover:text-blue-600 flex items-center gap-1 transition-colors"
                                                                >
                                                                    💬 Responder
                                                                </button>
                                                            </div>

                                                            {/* Reply Input for this comment */}
                                                            {commentsModal.replyingToId === comment.id && (
                                                                <div className="mt-4 pt-4 border-t border-neutral-200">
                                                                    <p className="text-xs text-violet-600 mb-2">Respondendo a {authorName}</p>

                                                                    {/* AI Prompts */}
                                                                    <div className="flex flex-wrap gap-2 mb-3">
                                                                        {['agradecer', 'agregar_valor', 'resposta_simples', 'perguntar'].map((type) => (
                                                                            <button
                                                                                key={type}
                                                                                onClick={() => generateAIReply(type as any, comment.text, authorName)}
                                                                                disabled={commentsModal.generatingReply}
                                                                                className="px-2 py-1 rounded-md bg-neutral-100 hover:bg-neutral-200 text-neutral-600 text-[10px] transition-colors disabled:opacity-50"
                                                                            >
                                                                                {type === 'agradecer' && '🙏 Agradecer'}
                                                                                {type === 'agregar_valor' && '💡 Agregar'}
                                                                                {type === 'resposta_simples' && '💬 Simples'}
                                                                                {type === 'perguntar' && '❓ Perguntar'}
                                                                            </button>
                                                                        ))}
                                                                        {commentsModal.generatingReply && (
                                                                            <span className="text-[10px] text-neutral-400 flex items-center gap-1">
                                                                                <div className="w-3 h-3 border border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                                                                Gerando...
                                                                            </span>
                                                                        )}
                                                                    </div>

                                                                    <div className="flex gap-2">
                                                                        <input
                                                                            type="text"
                                                                            value={commentsModal.replyText}
                                                                            onChange={(e) => setCommentsModal(prev => ({ ...prev, replyText: e.target.value }))}
                                                                            placeholder="Escreva sua resposta..."
                                                                            className="flex-1 px-3 py-2 text-sm rounded-lg bg-white border border-neutral-300 focus:border-violet-400 focus:ring-2 focus:ring-violet-100 outline-none"
                                                                        />
                                                                        <button
                                                                            onClick={handleReplyToPost}
                                                                            disabled={commentsModal.replying || !commentsModal.replyText.trim()}
                                                                            className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:bg-neutral-300 text-white text-sm font-medium transition-colors"
                                                                        >
                                                                            {commentsModal.replying ? '...' : 'Enviar'}
                                                                        </button>
                                                                        <button
                                                                            onClick={() => setCommentsModal(prev => ({ ...prev, replyingToId: null, replyText: '' }))}
                                                                            className="px-3 py-2 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-600 text-sm transition-colors"
                                                                        >
                                                                            ✕
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>

                            {/* Reply to Post Input */}
                            {!commentsModal.replyingToId && (
                                <div className="px-6 py-4 border-t border-neutral-100 flex-shrink-0">
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={commentsModal.replyText}
                                            onChange={(e) => setCommentsModal(prev => ({ ...prev, replyText: e.target.value }))}
                                            onFocus={() => setCommentsModal(prev => ({ ...prev, replyingToId: 'post' }))}
                                            placeholder="Adicionar comentário ao post..."
                                            className="flex-1 px-4 py-2.5 text-sm rounded-xl bg-neutral-100 border border-transparent focus:border-neutral-300 focus:bg-white outline-none transition-all"
                                        />
                                        <button
                                            onClick={handleReplyToPost}
                                            disabled={commentsModal.replying || !commentsModal.replyText.trim()}
                                            className="px-5 py-2.5 rounded-xl bg-neutral-900 hover:bg-neutral-800 disabled:bg-neutral-300 text-white text-sm font-medium transition-colors"
                                        >
                                            {commentsModal.replying ? 'Enviando...' : 'Comentar'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )
            }
        </div >
    );
}
