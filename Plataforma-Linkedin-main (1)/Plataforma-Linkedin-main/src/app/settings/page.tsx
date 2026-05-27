'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/utils/supabase/client';
import PromptsEditor from '@/components/PromptsEditor';

interface UserSettings {
    news_posts_enabled: boolean;
    auto_like_on_reply: boolean;
    trends_monitoring_enabled: boolean;
    prompts_customization_enabled: boolean;
    reference_images_enabled: boolean;
}

interface RSSFeed {
    id: string;
    name: string;
    url: string;
    is_active: boolean;
    created_at: string;
}

interface MonitoredProfile {
    id: string;
    profile_url: string;
    profile_name: string;
    profile_vanity_name: string;
    last_fetched_at: string | null;
    created_at: string;
}

interface UserPhoto {
    id: string;
    public_url: string;
    is_primary: boolean;
    original_filename: string;
    created_at: string;
}

const DEFAULT_SETTINGS: UserSettings = {
    news_posts_enabled: false,
    auto_like_on_reply: false,
    trends_monitoring_enabled: false,
    prompts_customization_enabled: false,
    reference_images_enabled: true, // Enabled by default for identity preservation
};

export default function SettingsPage() {
    const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    // RSS Feeds state
    const [feeds, setFeeds] = useState<RSSFeed[]>([]);
    const [loadingFeeds, setLoadingFeeds] = useState(false);
    const [newFeedName, setNewFeedName] = useState('');
    const [newFeedUrl, setNewFeedUrl] = useState('');
    const [addingFeed, setAddingFeed] = useState(false);
    const [deletingFeed, setDeletingFeed] = useState<string | null>(null);

    // Monitored Profiles state
    const [profiles, setProfiles] = useState<MonitoredProfile[]>([]);
    const [loadingProfiles, setLoadingProfiles] = useState(false);
    const [newProfileName, setNewProfileName] = useState('');
    const [newProfileUrl, setNewProfileUrl] = useState('');
    const [addingProfile, setAddingProfile] = useState(false);
    const [deletingProfile, setDeletingProfile] = useState<string | null>(null);

    // Reference Photos state
    const [photos, setPhotos] = useState<UserPhoto[]>([]);
    const [loadingPhotos, setLoadingPhotos] = useState(false);
    const [uploadingPhoto, setUploadingPhoto] = useState(false);
    const [deletingPhoto, setDeletingPhoto] = useState<string | null>(null);

    useEffect(() => {
        loadSettings();
    }, []);

    useEffect(() => {
        if (settings.news_posts_enabled) {
            loadFeeds();
        }
    }, [settings.news_posts_enabled]);

    useEffect(() => {
        if (settings.trends_monitoring_enabled) {
            loadProfiles();
        }
    }, [settings.trends_monitoring_enabled]);

    useEffect(() => {
        if (settings.reference_images_enabled) {
            loadPhotos();
        }
    }, [settings.reference_images_enabled]);

    const loadSettings = async () => {
        try {
            const response = await fetch('/api/settings');
            const data = await response.json();

            if (data.success && data.settings) {
                setSettings(data.settings);
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadFeeds = async () => {
        setLoadingFeeds(true);
        try {
            const response = await fetch('/api/rss/feeds');
            const data = await response.json();

            if (data.success) {
                setFeeds(data.feeds || []);
            }
        } catch (error) {
            console.error('Error loading feeds:', error);
        } finally {
            setLoadingFeeds(false);
        }
    };

    const saveSettings = async (newSettings: UserSettings) => {
        setSaving(true);
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newSettings),
            });

            const data = await response.json();
            if (data.success) {
                setSettings(data.settings);
            }
        } catch (error) {
            console.error('Error saving settings:', error);
        } finally {
            setSaving(false);
        }
    };

    const handleToggle = (key: keyof UserSettings) => {
        const newSettings = { ...settings, [key]: !settings[key] };
        saveSettings(newSettings);
    };

    const handleAddFeed = async () => {
        if (!newFeedName.trim() || !newFeedUrl.trim()) {
            alert('Nome e URL são obrigatórios');
            return;
        }

        setAddingFeed(true);
        try {
            const response = await fetch('/api/rss/feeds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: newFeedName.trim(),
                    url: newFeedUrl.trim(),
                }),
            });

            const data = await response.json();
            if (data.success) {
                setFeeds(prev => [data.feed, ...prev]);
                setNewFeedName('');
                setNewFeedUrl('');
                alert(`✅ Feed adicionado!\n\nRSS descoberto: ${data.discoveredUrl || data.feed.url}`);
            } else {
                alert(data.error || 'Erro ao adicionar feed');
            }
        } catch (error) {
            console.error('Error adding feed:', error);
            alert('Erro ao adicionar feed');
        } finally {
            setAddingFeed(false);
        }
    };

    const handleDeleteFeed = async (feedId: string) => {
        if (!confirm('Tem certeza que deseja remover este feed?')) return;

        setDeletingFeed(feedId);
        try {
            const response = await fetch(`/api/rss/feeds?id=${feedId}`, {
                method: 'DELETE',
            });

            const data = await response.json();
            if (data.success) {
                setFeeds(prev => prev.filter(f => f.id !== feedId));
            } else {
                alert(data.error || 'Erro ao remover feed');
            }
        } catch (error) {
            console.error('Error deleting feed:', error);
        } finally {
            setDeletingFeed(null);
        }
    };

    const loadProfiles = async () => {
        setLoadingProfiles(true);
        try {
            const response = await fetch('/api/trends/profiles');
            const data = await response.json();

            if (data.success) {
                setProfiles(data.profiles || []);
            }
        } catch (error) {
            console.error('Error loading profiles:', error);
        } finally {
            setLoadingProfiles(false);
        }
    };

    const handleAddProfile = async () => {
        if (!newProfileUrl.trim()) {
            alert('URL do perfil é obrigatória');
            return;
        }

        setAddingProfile(true);
        try {
            const response = await fetch('/api/trends/profiles', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile_url: newProfileUrl.trim(),
                    profile_name: newProfileName.trim() || undefined,
                }),
            });

            const data = await response.json();
            if (data.success) {
                setProfiles(prev => [data.profile, ...prev]);
                setNewProfileName('');
                setNewProfileUrl('');
                alert('✅ Perfil adicionado!');
            } else {
                alert(data.error || 'Erro ao adicionar perfil');
            }
        } catch (error) {
            console.error('Error adding profile:', error);
            alert('Erro ao adicionar perfil');
        } finally {
            setAddingProfile(false);
        }
    };

    const handleDeleteProfile = async (profileId: string) => {
        if (!confirm('Tem certeza que deseja remover este perfil?')) return;

        setDeletingProfile(profileId);
        try {
            const response = await fetch(`/api/trends/profiles?id=${profileId}`, {
                method: 'DELETE',
            });

            const data = await response.json();
            if (data.success) {
                setProfiles(prev => prev.filter(p => p.id !== profileId));
            } else {
                alert(data.error || 'Erro ao remover perfil');
            }
        } catch (error) {
            console.error('Error deleting profile:', error);
        } finally {
            setDeletingProfile(null);
        }
    };

    // Reference Photos handlers
    const loadPhotos = async () => {
        setLoadingPhotos(true);
        try {
            const response = await fetch('/api/user/photos');
            const data = await response.json();
            if (data.photos) {
                setPhotos(data.photos);
            }
        } catch (error) {
            console.error('Error loading photos:', error);
        } finally {
            setLoadingPhotos(false);
        }
    };

    const handleUploadPhoto = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setUploadingPhoto(true);
        try {
            const formData = new FormData();
            Array.from(files).forEach(file => {
                formData.append('photos', file);
            });
            formData.append('analyzeImmediately', 'true');

            const response = await fetch('/api/user/photos', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            if (data.success) {
                await loadPhotos();
                alert('✅ Foto adicionada!');
            } else {
                alert(data.error || 'Erro ao enviar foto');
            }
        } catch (error) {
            console.error('Error uploading photo:', error);
            alert('Erro ao enviar foto');
        } finally {
            setUploadingPhoto(false);
            e.target.value = '';
        }
    };

    const handleDeletePhoto = async (photoId: string) => {
        if (!confirm('Tem certeza que deseja remover esta foto?')) return;

        setDeletingPhoto(photoId);
        try {
            const response = await fetch(`/api/user/photos?id=${photoId}`, {
                method: 'DELETE',
            });

            const data = await response.json();
            if (data.success) {
                setPhotos(prev => prev.filter(p => p.id !== photoId));
            } else {
                alert(data.error || 'Erro ao remover foto');
            }
        } catch (error) {
            console.error('Error deleting photo:', error);
        } finally {
            setDeletingPhoto(null);
        }
    };

    const handleSetPrimaryPhoto = async (photoId: string) => {
        try {
            const response = await fetch('/api/user/photos', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ photoId, is_primary: true }),
            });

            const data = await response.json();
            if (data.success) {
                await loadPhotos();
            }
        } catch (error) {
            console.error('Error setting primary photo:', error);
        }
    };

    if (loading) {
        return (
            <div className="min-h-[80vh] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
                    <p className="text-sm text-neutral-500">Carregando configurações...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-neutral-50">
            <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {/* Header */}
                <header className="mb-8 animate-fadeIn">
                    <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">Configurações</h1>
                    <p className="mt-1 text-sm text-neutral-500">
                        Personalize o comportamento da plataforma
                    </p>
                </header>

                {/* Settings Sections */}
                <div className="space-y-6 animate-fadeIn">
                    {/* Comments Section */}
                    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
                        <div className="px-6 py-4 border-b border-neutral-100">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                                    <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                    </svg>
                                </div>
                                <div>
                                    <h2 className="text-base font-semibold text-neutral-900">Comentários</h2>
                                    <p className="text-xs text-neutral-500">Configurações de interação com comentários</p>
                                </div>
                            </div>
                        </div>

                        <div className="divide-y divide-neutral-100">
                            {/* Auto-like Setting */}
                            <div className="px-6 py-5 flex items-center justify-between">
                                <div className="flex-1 pr-4">
                                    <h3 className="text-sm font-medium text-neutral-900">
                                        Curtir automaticamente ao responder
                                    </h3>
                                    <p className="mt-1 text-xs text-neutral-500">
                                        Quando ativado, ao responder um comentário, o sistema automaticamente dará um like no comentário original
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleToggle('auto_like_on_reply')}
                                    disabled={saving}
                                    className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 ${settings.auto_like_on_reply ? 'bg-emerald-600' : 'bg-neutral-200'
                                        }`}
                                >
                                    <span className="sr-only">Toggle auto-like</span>
                                    <span
                                        className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${settings.auto_like_on_reply ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                    />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* News Posts Section */}
                    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
                        <div className="px-6 py-4 border-b border-neutral-100">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
                                    <svg className="w-5 h-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                                    </svg>
                                </div>
                                <div>
                                    <h2 className="text-base font-semibold text-neutral-900">Notícias & RSS</h2>
                                    <p className="text-xs text-neutral-500">Gere posts baseados em notícias de feeds RSS</p>
                                </div>
                            </div>
                        </div>

                        <div className="divide-y divide-neutral-100">
                            {/* Toggle */}
                            <div className="px-6 py-5 flex items-center justify-between">
                                <div className="flex-1 pr-4">
                                    <h3 className="text-sm font-medium text-neutral-900">
                                        Gerar posts com notícias
                                    </h3>
                                    <p className="mt-1 text-xs text-neutral-500">
                                        Habilita a aba "Notícias" onde você pode ver headlines e gerar posts baseados em notícias
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleToggle('news_posts_enabled')}
                                    disabled={saving}
                                    className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 disabled:opacity-50 ${settings.news_posts_enabled ? 'bg-violet-600' : 'bg-neutral-200'
                                        }`}
                                >
                                    <span className="sr-only">Toggle news posts</span>
                                    <span
                                        className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${settings.news_posts_enabled ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                    />
                                </button>
                            </div>

                            {/* RSS Feeds Management (shown when enabled) */}
                            {settings.news_posts_enabled && (
                                <div className="px-6 py-5">
                                    <h3 className="text-sm font-medium text-neutral-900 mb-4">
                                        Feeds RSS
                                    </h3>

                                    {/* Add New Feed Form */}
                                    <div className="bg-neutral-50 rounded-xl p-4 mb-4">
                                        <p className="text-xs text-neutral-500 mb-3">
                                            Digite apenas o domínio do site - o RSS será descoberto automaticamente
                                        </p>
                                        <div className="space-y-3">
                                            <input
                                                type="text"
                                                placeholder="Nome do feed (ex: Jornal de Negócios)"
                                                value={newFeedName}
                                                onChange={(e) => setNewFeedName(e.target.value)}
                                                className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-violet-400 focus:ring-2 focus:ring-violet-100 outline-none"
                                            />
                                            <div>
                                                <input
                                                    type="text"
                                                    placeholder="dominio.com (ex: jornaldenegocios.pt)"
                                                    value={newFeedUrl}
                                                    onChange={(e) => setNewFeedUrl(e.target.value)}
                                                    className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-violet-400 focus:ring-2 focus:ring-violet-100 outline-none"
                                                />
                                                <p className="mt-1 text-[10px] text-neutral-400">
                                                    https:// e /rss serão adicionados automaticamente
                                                </p>
                                            </div>
                                            <button
                                                onClick={handleAddFeed}
                                                disabled={addingFeed || !newFeedName.trim() || !newFeedUrl.trim()}
                                                className="w-full px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:bg-neutral-300 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2"
                                            >
                                                {addingFeed ? (
                                                    <>
                                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                                        Descobrindo RSS...
                                                    </>
                                                ) : (
                                                    <>
                                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                                        </svg>
                                                        Adicionar Feed
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Feeds List */}
                                    {loadingFeeds ? (
                                        <div className="flex items-center justify-center py-8">
                                            <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                        </div>
                                    ) : feeds.length === 0 ? (
                                        <div className="text-center py-6 text-neutral-400 text-sm">
                                            Nenhum feed adicionado ainda
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {feeds.map((feed) => (
                                                <div
                                                    key={feed.id}
                                                    className="flex items-center justify-between p-3 bg-white rounded-lg border border-neutral-200"
                                                >
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium text-neutral-900 truncate">
                                                            {feed.name}
                                                        </p>
                                                        <p className="text-xs text-neutral-400 truncate">
                                                            {feed.url}
                                                        </p>
                                                    </div>
                                                    <button
                                                        onClick={() => handleDeleteFeed(feed.id)}
                                                        disabled={deletingFeed === feed.id}
                                                        className="ml-3 p-2 rounded-lg text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors disabled:opacity-50"
                                                    >
                                                        {deletingFeed === feed.id ? (
                                                            <div className="w-4 h-4 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                                        ) : (
                                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                            </svg>
                                                        )}
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Trends Monitoring Section */}
                    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
                        <div className="px-6 py-4 border-b border-neutral-100">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center">
                                    <svg className="w-5 h-5 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                    </svg>
                                </div>
                                <div>
                                    <h2 className="text-base font-semibold text-neutral-900">Acompanhamento de Tendências</h2>
                                    <p className="text-xs text-neutral-500">Monitore perfis e descubra posts relevantes para engajar</p>
                                </div>
                            </div>
                        </div>

                        <div className="divide-y divide-neutral-100">
                            {/* Toggle */}
                            <div className="px-6 py-5 flex items-center justify-between">
                                <div className="flex-1 pr-4">
                                    <h3 className="text-sm font-medium text-neutral-900">
                                        Monitorar perfis do LinkedIn
                                    </h3>
                                    <p className="mt-1 text-xs text-neutral-500">
                                        Acompanhe posts de até 10 perfis e receba sugestões de engajamento baseadas nos seus temas
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleToggle('trends_monitoring_enabled')}
                                    disabled={saving}
                                    className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 disabled:opacity-50 ${settings.trends_monitoring_enabled ? 'bg-orange-600' : 'bg-neutral-200'
                                        }`}
                                >
                                    <span className="sr-only">Toggle trends monitoring</span>
                                    <span
                                        className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${settings.trends_monitoring_enabled ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                    />
                                </button>
                            </div>

                            {/* Profile Management (shown when enabled) */}
                            {settings.trends_monitoring_enabled && (
                                <div className="px-6 py-5">
                                    <h3 className="text-sm font-medium text-neutral-900 mb-4">
                                        Perfis Monitorados ({profiles.length}/10)
                                    </h3>

                                    {/* Add New Profile Form */}
                                    <div className="bg-neutral-50 rounded-xl p-4 mb-4">
                                        <p className="text-xs text-neutral-500 mb-3">
                                            Adicione o URL ou nome de usuário do LinkedIn
                                        </p>
                                        <div className="space-y-3">
                                            <input
                                                type="text"
                                                placeholder="Nome do perfil (opcional)"
                                                value={newProfileName}
                                                onChange={(e) => setNewProfileName(e.target.value)}
                                                className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-orange-400 focus:ring-2 focus:ring-orange-100 outline-none"
                                            />
                                            <div>
                                                <input
                                                    type="text"
                                                    placeholder="linkedin.com/in/nome ou apenas o nome"
                                                    value={newProfileUrl}
                                                    onChange={(e) => setNewProfileUrl(e.target.value)}
                                                    className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-orange-400 focus:ring-2 focus:ring-orange-100 outline-none"
                                                />
                                                <p className="mt-1 text-[10px] text-neutral-400">
                                                    Ex: billgates, linkedin.com/in/billgates
                                                </p>
                                            </div>
                                            <button
                                                onClick={handleAddProfile}
                                                disabled={addingProfile || !newProfileUrl.trim() || profiles.length >= 10}
                                                className="w-full px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-700 disabled:bg-neutral-300 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2"
                                            >
                                                {addingProfile ? (
                                                    <>
                                                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                                        Adicionando...
                                                    </>
                                                ) : (
                                                    <>
                                                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                                        </svg>
                                                        Adicionar Perfil
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Profiles List */}
                                    {loadingProfiles ? (
                                        <div className="flex items-center justify-center py-8">
                                            <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                        </div>
                                    ) : profiles.length === 0 ? (
                                        <div className="text-center py-6 text-neutral-400 text-sm">
                                            Nenhum perfil adicionado ainda
                                        </div>
                                    ) : (
                                        <div className="space-y-2">
                                            {profiles.map((profile) => (
                                                <div
                                                    key={profile.id}
                                                    className="flex items-center justify-between p-3 bg-white rounded-lg border border-neutral-200"
                                                >
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium text-neutral-900 truncate">
                                                            {profile.profile_name}
                                                        </p>
                                                        <p className="text-xs text-neutral-400 truncate">
                                                            {profile.profile_vanity_name || profile.profile_url}
                                                        </p>
                                                    </div>
                                                    <button
                                                        onClick={() => handleDeleteProfile(profile.id)}
                                                        disabled={deletingProfile === profile.id}
                                                        className="ml-3 p-2 rounded-lg text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-colors disabled:opacity-50"
                                                    >
                                                        {deletingProfile === profile.id ? (
                                                            <div className="w-4 h-4 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                                        ) : (
                                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                            </svg>
                                                        )}
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Reference Images Section */}
                    <div className="bg-white rounded-2xl border border-neutral-200 overflow-hidden">
                        <div className="px-6 py-4 border-b border-neutral-100">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-sky-100 flex items-center justify-center">
                                    <svg className="w-5 h-5 text-sky-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <div>
                                    <h2 className="text-base font-semibold text-neutral-900">Imagens de Referência</h2>
                                    <p className="text-xs text-neutral-500">Use seu rosto nas imagens geradas pela IA</p>
                                </div>
                            </div>
                        </div>

                        <div className="divide-y divide-neutral-100">
                            {/* Toggle */}
                            <div className="px-6 py-5 flex items-center justify-between">
                                <div className="flex-1 pr-4">
                                    <h3 className="text-sm font-medium text-neutral-900">
                                        Preservação de Identidade
                                    </h3>
                                    <p className="mt-1 text-xs text-neutral-500">
                                        Quando ativado, as imagens geradas usarão suas fotos de referência para manter sua aparência
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleToggle('reference_images_enabled')}
                                    disabled={saving}
                                    className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 disabled:opacity-50 ${settings.reference_images_enabled ? 'bg-sky-600' : 'bg-neutral-200'
                                        }`}
                                >
                                    <span className="sr-only">Toggle reference images</span>
                                    <span
                                        className={`pointer-events-none inline-block h-6 w-6 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${settings.reference_images_enabled ? 'translate-x-5' : 'translate-x-0'
                                            }`}
                                    />
                                </button>
                            </div>

                            {/* Photo Management (shown when enabled) */}
                            {settings.reference_images_enabled && (
                                <div className="px-6 py-5">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-sm font-medium text-neutral-900">
                                            Suas Fotos ({photos.length}/5)
                                        </h3>
                                        <label className="cursor-pointer inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-700 text-white text-xs font-medium transition-colors">
                                            {uploadingPhoto ? (
                                                <>
                                                    <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                                    Enviando...
                                                </>
                                            ) : (
                                                <>
                                                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                                    </svg>
                                                    Adicionar Foto
                                                </>
                                            )}
                                            <input
                                                type="file"
                                                accept="image/jpeg,image/png,image/webp"
                                                onChange={handleUploadPhoto}
                                                disabled={uploadingPhoto || photos.length >= 5}
                                                className="hidden"
                                            />
                                        </label>
                                    </div>

                                    <p className="text-xs text-neutral-400 mb-4">
                                        💡 Use fotos nítidas do seu rosto para melhores resultados. A foto principal será usada na geração.
                                    </p>

                                    {/* Photos Grid */}
                                    {loadingPhotos ? (
                                        <div className="flex items-center justify-center py-8">
                                            <div className="w-6 h-6 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                                        </div>
                                    ) : photos.length === 0 ? (
                                        <div className="text-center py-8 bg-neutral-50 rounded-xl border-2 border-dashed border-neutral-200">
                                            <svg className="w-12 h-12 text-neutral-300 mx-auto mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                            </svg>
                                            <p className="text-sm text-neutral-500">Nenhuma foto adicionada</p>
                                            <p className="text-xs text-neutral-400 mt-1">Adicione fotos para personalizar as imagens geradas</p>
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                            {photos.map((photo) => (
                                                <div key={photo.id} className="relative group">
                                                    <div className={`aspect-square rounded-xl overflow-hidden border-2 ${photo.is_primary ? 'border-sky-500' : 'border-neutral-200'}`}>
                                                        <img
                                                            src={photo.public_url}
                                                            alt="Foto de referência"
                                                            className="w-full h-full object-cover"
                                                        />
                                                    </div>

                                                    {/* Primary badge */}
                                                    {photo.is_primary && (
                                                        <div className="absolute top-2 left-2 px-2 py-0.5 bg-sky-600 text-white text-[10px] font-medium rounded-full">
                                                            Principal
                                                        </div>
                                                    )}

                                                    {/* Actions overlay */}
                                                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl flex items-center justify-center gap-2">
                                                        {!photo.is_primary && (
                                                            <button
                                                                onClick={() => handleSetPrimaryPhoto(photo.id)}
                                                                className="p-2 rounded-lg bg-white/20 hover:bg-white/30 text-white transition-colors"
                                                                title="Definir como principal"
                                                            >
                                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                                                </svg>
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleDeletePhoto(photo.id)}
                                                            disabled={deletingPhoto === photo.id}
                                                            className="p-2 rounded-lg bg-rose-500/80 hover:bg-rose-600 text-white transition-colors disabled:opacity-50"
                                                            title="Remover foto"
                                                        >
                                                            {deletingPhoto === photo.id ? (
                                                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                                            ) : (
                                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                                </svg>
                                                            )}
                                                        </button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Prompts Customization Section */}
                    <div className="bg-white rounded-2xl border border-neutral-200 shadow-sm overflow-hidden">
                        <div className="px-6 py-5 border-b border-neutral-100 flex items-center justify-between">
                            <div>
                                <h2 className="text-base font-semibold text-neutral-900">Prompts Personalizados</h2>
                                <p className="mt-1 text-sm text-neutral-500">
                                    Personaliza os prompts de IA utilizados na plataforma
                                </p>
                            </div>
                            <button
                                onClick={() => handleToggle('prompts_customization_enabled')}
                                disabled={saving}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${settings.prompts_customization_enabled ? 'bg-violet-600' : 'bg-neutral-200'
                                    }`}
                            >
                                <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm ${settings.prompts_customization_enabled ? 'translate-x-6' : 'translate-x-1'
                                        }`}
                                />
                            </button>
                        </div>

                        {/* Prompts Editor Component */}
                        <PromptsEditor enabled={settings.prompts_customization_enabled} />
                    </div>
                </div>
            </div>
        </div>
    );
}
