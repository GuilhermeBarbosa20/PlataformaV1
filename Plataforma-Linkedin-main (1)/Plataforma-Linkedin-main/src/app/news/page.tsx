'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface Headline {
    title: string;
    description: string;
    link: string;
    pubDate: string;
    feedName: string;
    feedId: string;
}

interface GeneratedPost {
    headline: string;
    hook: string;
    body: string;
    cta: string;
    hashtags: string[];
    caption: string;
}

export default function NewsPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [headlines, setHeadlines] = useState<Headline[]>([]);
    const [errors, setErrors] = useState<string[]>([]);
    const [enabled, setEnabled] = useState<boolean | null>(null);

    // Post generation state
    const [generating, setGenerating] = useState<string | null>(null);
    const [generatedPost, setGeneratedPost] = useState<GeneratedPost | null>(null);
    const [selectedArticle, setSelectedArticle] = useState<Headline | null>(null);
    const [showModal, setShowModal] = useState(false);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        checkAccess();
    }, []);

    const checkAccess = async () => {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();

            if (!data.settings?.news_posts_enabled) {
                setEnabled(false);
                setLoading(false);
                return;
            }

            setEnabled(true);
            await fetchHeadlines();
        } catch (error) {
            console.error('Error checking access:', error);
            setEnabled(false);
        } finally {
            setLoading(false);
        }
    };

    const fetchHeadlines = async () => {
        setRefreshing(true);
        try {
            const response = await fetch('/api/rss/headlines');
            const data = await response.json();

            if (data.success) {
                setHeadlines(data.headlines || []);
                setErrors(data.errors || []);
            }
        } catch (error) {
            console.error('Error fetching headlines:', error);
        } finally {
            setRefreshing(false);
        }
    };

    const handleGeneratePost = async (article: Headline) => {
        setGenerating(article.title);
        setSelectedArticle(article);

        try {
            const response = await fetch('/api/rss/generate-post', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ article }),
            });

            const data = await response.json();

            if (data.success && data.post) {
                setGeneratedPost(data.post);
                setShowModal(true);
            } else {
                alert(data.error || 'Erro ao gerar post');
            }
        } catch (error) {
            console.error('Error generating post:', error);
            alert('Erro ao gerar post');
        } finally {
            setGenerating(null);
        }
    };

    const handleSavePost = async () => {
        if (!generatedPost || !selectedArticle) return;

        setSaving(true);
        try {
            // Create a scheduled post for today
            const today = new Date().toISOString().split('T')[0];

            const response = await fetch('/api/posts/create-from-news', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    caption: generatedPost.caption,
                    ai_content: generatedPost,
                    source: {
                        type: 'rss',
                        title: selectedArticle.title,
                        link: selectedArticle.link,
                        feedName: selectedArticle.feedName,
                    },
                    scheduled_for: today,
                }),
            });

            const data = await response.json();

            if (data.success) {
                alert('✅ Post criado com sucesso! Vá para Posts para revisar.');
                setShowModal(false);
                setGeneratedPost(null);
                setSelectedArticle(null);
            } else {
                alert(data.error || 'Erro ao salvar post');
            }
        } catch (error) {
            console.error('Error saving post:', error);
            alert('Erro ao salvar post');
        } finally {
            setSaving(false);
        }
    };

    const closeModal = () => {
        setShowModal(false);
        setGeneratedPost(null);
        setSelectedArticle(null);
    };

    const formatDate = (dateStr: string) => {
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit',
            });
        } catch {
            return dateStr;
        }
    };

    if (loading) {
        return (
            <div className="min-h-[80vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
                    <p className="text-sm text-neutral-500">Carregando notícias...</p>
                </div>
            </div>
        );
    }

    if (!enabled) {
        return (
            <div className="min-h-[80vh] flex items-center justify-center">
                <div className="text-center max-w-md mx-auto px-4">
                    <div className="w-16 h-16 bg-neutral-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                        <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                        </svg>
                    </div>
                    <h2 className="text-lg font-semibold text-neutral-900 mb-2">Notícias Desabilitadas</h2>
                    <p className="text-sm text-neutral-500 mb-6">
                        Para usar esta funcionalidade, ative "Gerar posts com notícias" nas configurações e adicione feeds RSS.
                    </p>
                    <button
                        onClick={() => router.push('/settings')}
                        className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium transition-colors"
                    >
                        Ir para Configurações
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-neutral-50">
            <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <header className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
                                <svg className="w-5 h-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                                </svg>
                            </div>
                            Notícias
                        </h1>
                        <p className="mt-1 text-sm text-neutral-500">
                            Veja as últimas notícias dos seus feeds e gere posts para o LinkedIn
                        </p>
                    </div>
                    <button
                        onClick={fetchHeadlines}
                        disabled={refreshing}
                        className="px-4 py-2 rounded-xl bg-white border border-neutral-200 hover:bg-neutral-50 text-sm font-medium text-neutral-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                    >
                        {refreshing ? (
                            <>
                                <div className="w-4 h-4 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                Atualizando...
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                </svg>
                                Atualizar
                            </>
                        )}
                    </button>
                </header>

                {/* Errors */}
                {errors.length > 0 && (
                    <div className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200">
                        <p className="text-sm font-medium text-amber-800 mb-1">Alguns feeds apresentaram erros:</p>
                        <ul className="text-xs text-amber-700 space-y-0.5">
                            {errors.map((error, i) => (
                                <li key={i}>• {error}</li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Headlines Grid */}
                {headlines.length === 0 ? (
                    <div className="text-center py-16">
                        <div className="w-16 h-16 bg-neutral-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                            <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                        </div>
                        <h2 className="text-lg font-medium text-neutral-900 mb-2">Nenhuma notícia encontrada</h2>
                        <p className="text-sm text-neutral-500 mb-4">
                            Adicione feeds RSS nas configurações para ver notícias aqui.
                        </p>
                        <button
                            onClick={() => router.push('/settings')}
                            className="text-sm text-violet-600 hover:text-violet-700 font-medium"
                        >
                            Gerenciar Feeds →
                        </button>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {headlines.map((headline, index) => (
                            <div
                                key={`${headline.feedId}-${index}`}
                                className="bg-white rounded-2xl border border-neutral-200 p-5 hover:shadow-lg transition-shadow"
                            >
                                {/* Feed Badge */}
                                <div className="flex items-center justify-between mb-3">
                                    <span className="px-2.5 py-1 rounded-full bg-neutral-100 text-[11px] font-medium text-neutral-600">
                                        {headline.feedName}
                                    </span>
                                    <span className="text-[11px] text-neutral-400">
                                        {formatDate(headline.pubDate)}
                                    </span>
                                </div>

                                {/* Title */}
                                <h3 className="text-sm font-semibold text-neutral-900 mb-2 line-clamp-2">
                                    {headline.title}
                                </h3>

                                {/* Description */}
                                {headline.description && (
                                    <p className="text-xs text-neutral-500 mb-4 line-clamp-3">
                                        {headline.description}
                                    </p>
                                )}

                                {/* Actions */}
                                <div className="flex items-center gap-2 mt-auto pt-3 border-t border-neutral-100">
                                    <a
                                        href={headline.link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="flex-1 px-3 py-2 rounded-lg bg-neutral-50 hover:bg-neutral-100 text-xs font-medium text-neutral-600 text-center transition-colors"
                                    >
                                        Ler Notícia
                                    </a>
                                    <button
                                        onClick={() => handleGeneratePost(headline)}
                                        disabled={generating === headline.title}
                                        className="flex-1 px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:bg-violet-400 text-xs font-medium text-white text-center transition-colors flex items-center justify-center gap-1.5"
                                    >
                                        {generating === headline.title ? (
                                            <>
                                                <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                                Gerando...
                                            </>
                                        ) : (
                                            <>
                                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                                </svg>
                                                Gerar Post
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Generated Post Modal */}
            {showModal && generatedPost && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                        {/* Header */}
                        <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between">
                            <div>
                                <h2 className="text-lg font-semibold text-neutral-900">Post Gerado</h2>
                                <p className="text-xs text-neutral-500">Revise e salve o post para seus rascunhos</p>
                            </div>
                            <button
                                onClick={closeModal}
                                className="w-8 h-8 rounded-full bg-neutral-100 hover:bg-neutral-200 flex items-center justify-center text-neutral-500 hover:text-neutral-700 transition-colors"
                            >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Source */}
                        {selectedArticle && (
                            <div className="px-6 py-3 bg-violet-50 border-b border-violet-100">
                                <p className="text-xs text-violet-600 font-medium">Baseado em:</p>
                                <p className="text-sm text-violet-800 line-clamp-1">{selectedArticle.title}</p>
                            </div>
                        )}

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto p-6">
                            <div className="bg-neutral-50 rounded-xl p-4 whitespace-pre-wrap text-sm text-neutral-800 leading-relaxed">
                                {generatedPost.caption}
                            </div>
                        </div>

                        {/* Footer */}
                        <div className="px-6 py-4 border-t border-neutral-100 flex justify-end gap-3">
                            <button
                                onClick={closeModal}
                                className="px-4 py-2 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-700 text-sm font-medium transition-colors"
                            >
                                Cancelar
                            </button>
                            <button
                                onClick={handleSavePost}
                                disabled={saving}
                                className="px-5 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:bg-violet-400 text-white text-sm font-medium transition-colors flex items-center gap-2"
                            >
                                {saving ? (
                                    <>
                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                        Salvando...
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                        Salvar Post
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
