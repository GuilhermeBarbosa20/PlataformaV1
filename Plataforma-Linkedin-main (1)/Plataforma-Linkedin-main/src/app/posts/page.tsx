'use client';

import { useEffect, useMemo, useState, useRef } from 'react';
import PostRefinementModal from '@/components/PostRefinementModal';
import ImageUploadModal from '@/components/ImageUploadModal';

type Post = {
  id: string;
  scheduled_for: string;
  caption: string;
  ai_content: {
    headline?: string;
    hook?: string;
    body?: string;
    cta?: string;
    hashtags?: string[];
    tone?: string;
    suggestedImagePrompt?: string;
  } | null;
  approval_status: 'aguardar' | 'aprovado' | 'revisar';
  approval_notes?: string | null;
  needs_regeneration: boolean;
  generated_image_url?: string | null;
  generated_image_prompt?: string | null;
  image_generation_status?: 'idle' | 'pending' | 'ready' | 'failed';
  image_generated_at?: string | null;
  refinement_history?: any[];
  last_refined_at?: string | null;
  text_approved?: boolean;
  text_approved_at?: string | null;
  image_approved?: boolean;
  image_approved_at?: string | null;
  post_approved?: boolean;
  post_approved_at?: string | null;
  custom_image_url?: string | null;
  linkedin_post_urn?: string | null;
  published_at?: string | null;
  publish_error?: string | null;
  status?: 'planned' | 'scheduled' | 'published' | 'skipped' | 'failed';
};

interface WeekResponse {
  posts: Post[];
  days: string[];
}

const statusLabel: Record<Post['approval_status'], string> = {
  aguardar: 'Pendente',
  aprovado: 'Aprovado',
  revisar: 'Revisão',
};

const statusStyles: Record<Post['approval_status'], { bg: string; text: string; dot: string }> = {
  aguardar: { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-400' },
  aprovado: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-400' },
  revisar: { bg: 'bg-rose-50', text: 'text-rose-700', dot: 'bg-rose-400' },
};

const weekdayIntl = new Intl.DateTimeFormat('pt-PT', { weekday: 'short' });
const dayIntl = new Intl.DateTimeFormat('pt-PT', { day: '2-digit' });
const monthIntl = new Intl.DateTimeFormat('pt-PT', { month: 'short' });

export default function PostsPage() {
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [posts, setPosts] = useState<Post[]>([]);
  const [days, setDays] = useState<string[]>([]);
  const [editModal, setEditModal] = useState<{ open: boolean; post: Post | null }>({ open: false, post: null });
  const [editContent, setEditContent] = useState({ caption: '' });
  const [savingEdit, setSavingEdit] = useState(false);
  const [expandedPost, setExpandedPost] = useState<string | null>(null);
  const [refinementModal, setRefinementModal] = useState<{ open: boolean; post: Post | null }>({ open: false, post: null });
  const [uploadingImage, setUploadingImage] = useState<string | null>(null);
  const [imageUploadModal, setImageUploadModal] = useState<{ open: boolean; postId: string | null }>({ open: false, postId: null });
  const [publishingPost, setPublishingPost] = useState<string | null>(null);
  const [generatingImage, setGeneratingImage] = useState<string | null>(null);

  // Drag and drop state for Kanban
  const [draggedPost, setDraggedPost] = useState<Post | null>(null);
  const [dragOverDay, setDragOverDay] = useState<string | null>(null);

  useEffect(() => {
    fetchWeek();
  }, []);

  // Group posts by date - supports multiple posts per day
  const postsByDate = useMemo(() => {
    const map = new Map<string, Post[]>();
    posts.forEach((post) => {
      const existing = map.get(post.scheduled_for) || [];
      existing.push(post);
      map.set(post.scheduled_for, existing);
    });
    return map;
  }, [posts]);

  const fetchWeek = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/posts/week');
      if (!response.ok) throw new Error('Falha ao carregar posts');
      const data: WeekResponse = await response.json();
      setPosts(data.posts || []);
      setDays(data.days || []);
    } catch (error) {
      console.error(error);
      alert('Não foi possível carregar os posts');
    } finally {
      setLoading(false);
    }
  };

  const syncWeek = async () => {
    setSyncing(true);
    try {
      const response = await fetch('/api/posts/week', { method: 'POST' });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error?.error || 'Falha ao gerar semana');
      }
      await fetchWeek();
      alert('✅ Semana sincronizada com IA!');
    } catch (error: any) {
      console.error(error);
      alert(error?.message || 'Erro ao sincronizar semana');
    } finally {
      setSyncing(false);
    }
  };

  const callPostAction = async (url: string, options?: RequestInit) => {
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error?.error || 'Operação falhou');
    }
    await fetchWeek();
  };

  // Drag and Drop Handlers
  const handleDragStart = (e: React.DragEvent, post: Post) => {
    setDraggedPost(post);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', post.id);
  };

  const handleDragEnd = () => {
    setDraggedPost(null);
    setDragOverDay(null);
  };

  const handleDragOver = (e: React.DragEvent, day: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverDay(day);
  };

  const handleDragLeave = () => {
    setDragOverDay(null);
  };

  const handleDrop = async (e: React.DragEvent, targetDay: string) => {
    e.preventDefault();
    setDragOverDay(null);

    if (!draggedPost || draggedPost.scheduled_for === targetDay) {
      setDraggedPost(null);
      return;
    }

    if (draggedPost.status === 'published') {
      alert('Não é possível mover posts já publicados');
      setDraggedPost(null);
      return;
    }

    try {
      const response = await fetch(`/api/posts/${draggedPost.id}/reschedule`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scheduled_for: targetDay }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error?.error || 'Falha ao mover post');
      }

      await fetchWeek();
    } catch (error: any) {
      console.error('Error rescheduling:', error);
      alert(error.message || 'Erro ao mover post');
    } finally {
      setDraggedPost(null);
    }
  };

  const handleApprove = async (postId: string) => {
    try {
      await callPostAction(`/api/posts/${postId}/approve`, { method: 'POST' });
      alert('✅ Post aprovado!');
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleApproveText = async (postId: string) => {
    try {
      await callPostAction(`/api/posts/${postId}/approve-text`, { method: 'POST' });
      alert('✅ Texto aprovado!');
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleApproveImage = async (postId: string) => {
    try {
      await callPostAction(`/api/posts/${postId}/approve-image`, { method: 'POST' });
      alert('✅ Imagem aprovada!');
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleApprovePost = async (postId: string) => {
    try {
      await callPostAction(`/api/posts/${postId}/approve-post`, { method: 'POST' });
      alert('✅ Post aprovado para publicação!');
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handlePublishPost = async (postId: string) => {
    setPublishingPost(postId);
    try {
      const response = await fetch(`/api/posts/${postId}/publish`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.error || 'Falha ao publicar');
      await fetchWeek();
      alert('✅ Post publicado no LinkedIn!');
    } catch (error: any) {
      alert(error.message);
    } finally {
      setPublishingPost(null);
    }
  };

  const handleUploadImage = async (postId: string, file: File) => {
    setUploadingImage(postId);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`/api/posts/${postId}/upload-image`, {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error?.error || 'Falha ao fazer upload');
      }
      await fetchWeek();
      alert('✅ Imagem enviada!');
    } catch (error: any) {
      alert(error.message);
    } finally {
      setUploadingImage(null);
      setImageUploadModal({ open: false, postId: null });
    }
  };

  const handleReject = async (postId: string) => {
    const notes = prompt('Motivo da rejeição (opcional):');
    try {
      await callPostAction(`/api/posts/${postId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes }),
      });
      alert('Post marcado para revisão');
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleRegenerate = async (postId: string) => {
    try {
      await callPostAction(`/api/posts/${postId}/regenerate`, { method: 'POST' });
      alert('✅ Texto regenerado!');
    } catch (error: any) {
      alert(error.message);
    }
  };

  const handleGenerateImage = async (postId: string) => {
    setGeneratingImage(postId);
    try {
      await callPostAction(`/api/posts/${postId}/generate-image`, { method: 'POST' });
      alert('✅ Imagem gerada!');
    } catch (error: any) {
      alert(error.message);
    } finally {
      setGeneratingImage(null);
    }
  };

  const openEditModal = (post: Post) => {
    setEditModal({ open: true, post });
    setEditContent({
      caption: post.caption || [
        post.ai_content?.headline,
        post.ai_content?.hook,
        post.ai_content?.body,
        post.ai_content?.cta,
        post.ai_content?.hashtags?.map((h: string) => `#${h}`).join(' '),
      ].filter(Boolean).join('\n\n'),
    });
  };

  const closeEditModal = () => setEditModal({ open: false, post: null });

  const handleSaveEdit = async () => {
    if (!editModal.post) return;
    setSavingEdit(true);
    try {
      const response = await fetch(`/api/posts/${editModal.post.id}/edit`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ caption: editContent.caption }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error?.error || 'Falha ao salvar');
      }
      await fetchWeek();
      closeEditModal();
      alert('✅ Alterações salvas!');
    } catch (error: any) {
      alert(error.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const getDayLabel = (dateStr: string) => {
    const date = new Date(dateStr + 'T12:00:00');
    return {
      weekday: capitalize(weekdayIntl.format(date)),
      day: dayIntl.format(date),
      month: capitalize(monthIntl.format(date)),
    };
  };

  if (loading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
          <p className="text-sm text-neutral-500">Carregando posts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <header className="mb-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">Planejamento Semanal</h1>
              <p className="text-sm text-neutral-500 mt-1">Arraste os posts entre os dias para reorganizar</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={fetchWeek}
                className="px-4 py-2 rounded-lg bg-white border border-neutral-200 text-neutral-600 hover:bg-neutral-50 hover:border-neutral-300 transition-all text-sm font-medium"
              >
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Atualizar
                </span>
              </button>
              <button
                onClick={syncWeek}
                disabled={syncing}
                className="px-5 py-2 rounded-lg bg-neutral-900 hover:bg-neutral-800 disabled:bg-neutral-400 text-white text-sm font-medium transition-all"
              >
                {syncing ? (
                  <span className="flex items-center gap-2">
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    Gerando...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Gerar com IA
                  </span>
                )}
              </button>
            </div>
          </div>
        </header>

        {/* Kanban Board */}
        <section className="flex gap-4 overflow-x-auto pb-4">
          {days.map((day) => {
            const dayPosts = postsByDate.get(day) || [];
            const { weekday, day: dayNum, month } = getDayLabel(day);
            const isToday = new Date(day).toDateString() === new Date().toDateString();
            const isDragOver = dragOverDay === day;

            return (
              <div
                key={day}
                className="flex-shrink-0 w-[300px]"
                onDragOver={(e) => handleDragOver(e, day)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, day)}
              >
                <div
                  className={`
                    flex flex-col rounded-xl border transition-all duration-200 min-h-[500px]
                    ${isDragOver
                      ? 'bg-violet-50 border-violet-300 ring-2 ring-violet-200'
                      : isToday
                        ? 'bg-white border-neutral-300 shadow-sm ring-1 ring-neutral-200'
                        : 'bg-white border-neutral-200'
                    }
                  `}
                >
                  {/* Day Header */}
                  <div className={`px-4 py-3 border-b ${isToday ? 'bg-neutral-900 border-neutral-900' : 'bg-neutral-50 border-neutral-100'}`}>
                    <div className="flex items-center justify-between">
                      <span className={`text-xs font-medium uppercase tracking-wider ${isToday ? 'text-neutral-300' : 'text-neutral-500'}`}>
                        {weekday}
                      </span>
                      <div className={`text-right ${isToday ? 'text-white' : 'text-neutral-900'}`}>
                        <span className="text-lg font-semibold">{dayNum}</span>
                        <span className={`text-xs ml-1 ${isToday ? 'text-neutral-300' : 'text-neutral-500'}`}>{month}</span>
                      </div>
                    </div>
                    {isToday && (
                      <div className="flex items-center gap-1.5 mt-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                        <span className="text-[10px] text-neutral-300 font-medium uppercase tracking-wider">Hoje</span>
                      </div>
                    )}
                    {dayPosts.length > 0 && (
                      <div className="mt-1.5">
                        <span className={`text-[10px] ${isToday ? 'text-neutral-400' : 'text-neutral-400'}`}>
                          {dayPosts.length} post{dayPosts.length > 1 ? 's' : ''}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Posts Column */}
                  <div className="flex-1 p-3 space-y-3 overflow-y-auto">
                    {dayPosts.length > 0 ? (
                      dayPosts.map((post) => (
                        <div
                          key={post.id}
                          draggable={post.status !== 'published'}
                          onDragStart={(e) => handleDragStart(e, post)}
                          onDragEnd={handleDragEnd}
                          className={`
                            p-3 rounded-lg border bg-white transition-all
                            ${post.status === 'published' ? 'opacity-75 cursor-default' : 'cursor-grab active:cursor-grabbing hover:shadow-md hover:border-neutral-300'}
                            ${draggedPost?.id === post.id ? 'opacity-50 scale-95' : ''}
                          `}
                        >
                          {/* Status Badge */}
                          <div className="flex items-center justify-between mb-2">
                            <span className={`inline-flex items-center gap-1 text-[9px] font-medium px-2 py-0.5 rounded-full ${statusStyles[post.approval_status].bg} ${statusStyles[post.approval_status].text}`}>
                              <span className={`w-1 h-1 rounded-full ${statusStyles[post.approval_status].dot}`}></span>
                              {statusLabel[post.approval_status]}
                            </span>
                            {post.status === 'published' && (
                              <span className="text-[9px] text-emerald-600 font-medium">✓ Publicado</span>
                            )}
                          </div>

                          {/* Content Preview */}
                          <div className="mb-3">
                            {post.caption ? (
                              <p className="text-xs text-neutral-700 line-clamp-3">{post.caption.slice(0, 120)}...</p>
                            ) : post.ai_content?.headline ? (
                              <h4 className="text-sm font-semibold text-neutral-900 line-clamp-2">{post.ai_content.headline}</h4>
                            ) : (
                              <p className="text-xs text-neutral-400 italic">Sem conteúdo</p>
                            )}
                          </div>

                          {/* Image Preview */}
                          {(post.generated_image_url || post.custom_image_url) && (
                            <div className="mb-3 rounded-lg overflow-hidden">
                              <img
                                src={post.custom_image_url || post.generated_image_url || ''}
                                alt="Preview"
                                className="w-full h-20 object-cover"
                              />
                            </div>
                          )}

                          {/* Quick Actions */}
                          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-neutral-100">
                            <button
                              onClick={() => openEditModal(post)}
                              className="px-2 py-1 rounded text-[10px] font-medium text-neutral-600 bg-neutral-50 hover:bg-neutral-100 transition-colors"
                            >
                              Editar
                            </button>

                            {(post.generated_image_url || post.custom_image_url) && (
                              <a
                                href={post.custom_image_url || post.generated_image_url || ''}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-2 py-1 rounded text-[10px] font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 transition-colors"
                              >
                                👁 Imagem
                              </a>
                            )}

                            {!post.text_approved && (
                              <button
                                onClick={() => handleApproveText(post.id)}
                                className="px-2 py-1 rounded text-[10px] font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 transition-colors"
                              >
                                ✓ Texto
                              </button>
                            )}

                            {post.text_approved && !post.generated_image_url && !post.custom_image_url && (
                              <>
                                <button
                                  onClick={() => handleGenerateImage(post.id)}
                                  disabled={generatingImage === post.id}
                                  className={`px-2 py-1 rounded text-[10px] font-medium transition-colors flex items-center gap-1 ${generatingImage === post.id
                                    ? 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                                    : 'text-violet-600 bg-violet-50 hover:bg-violet-100'
                                    }`}
                                >
                                  {generatingImage === post.id ? (
                                    <>
                                      <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                      </svg>
                                      <span>...</span>
                                    </>
                                  ) : (
                                    '🎨 Gerar'
                                  )}
                                </button>
                                <button
                                  onClick={() => setImageUploadModal({ open: true, postId: post.id })}
                                  className="px-2 py-1 rounded text-[10px] font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 transition-colors"
                                >
                                  📤 Upload
                                </button>
                              </>
                            )}

                            {(post.generated_image_url || post.custom_image_url) && !post.image_approved && (
                              <button
                                onClick={() => handleApproveImage(post.id)}
                                className="px-2 py-1 rounded text-[10px] font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 transition-colors"
                              >
                                ✓ Imagem
                              </button>
                            )}

                            {/* Show Approve Post button when:
                                - Text is approved AND
                                - Either image is approved OR there's no image at all AND
                                - Post not yet approved AND
                                - Not already published */}
                            {post.text_approved &&
                              (post.image_approved || (!post.generated_image_url && !post.custom_image_url)) &&
                              !post.post_approved &&
                              !post.linkedin_post_urn && (
                                <button
                                  onClick={() => handleApprovePost(post.id)}
                                  className="px-2 py-1 rounded text-[10px] font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 transition-colors"
                                >
                                  📤 Publicar
                                </button>
                              )}

                            {post.post_approved && !post.linkedin_post_urn && (
                              <button
                                onClick={() => handlePublishPost(post.id)}
                                disabled={publishingPost === post.id}
                                className="px-2 py-1 rounded text-[10px] font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 transition-colors"
                              >
                                {publishingPost === post.id ? '...' : '🚀 Publicar'}
                              </button>
                            )}

                            <button
                              onClick={() => setRefinementModal({ open: true, post })}
                              className="px-2 py-1 rounded text-[10px] font-medium text-violet-600 bg-violet-50 hover:bg-violet-100 transition-colors"
                            >
                              ✨ Refinar
                            </button>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="flex flex-col items-center justify-center text-center py-12 h-full min-h-[200px]">
                        <div className="w-12 h-12 rounded-full bg-neutral-100 flex items-center justify-center mb-3">
                          <svg className="w-6 h-6 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                          </svg>
                        </div>
                        <p className="text-xs text-neutral-400 mb-2">Sem posts</p>
                        <p className="text-[10px] text-neutral-300">Arraste um post aqui</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </section>
      </div>

      {/* Edit Modal */}
      {editModal.open && editModal.post && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-neutral-100 flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-neutral-900">Editar Conteúdo</h2>
                <p className="text-xs text-neutral-500 mt-0.5">Modifique o conteúdo do post</p>
              </div>
              <button onClick={closeEditModal} className="p-2 hover:bg-neutral-100 rounded-lg transition-colors">
                <svg className="w-5 h-5 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <textarea
                value={editContent.caption}
                onChange={(e) => setEditContent({ caption: e.target.value })}
                className="w-full h-64 p-4 border border-neutral-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:border-transparent"
                placeholder="Conteúdo do post..."
              />
            </div>
            <div className="px-6 py-4 border-t border-neutral-100 flex justify-end gap-3">
              <button onClick={closeEditModal} className="px-4 py-2 rounded-lg border border-neutral-200 text-neutral-600 hover:bg-neutral-50 text-sm font-medium">
                Cancelar
              </button>
              <button onClick={handleSaveEdit} disabled={savingEdit} className="px-4 py-2 rounded-lg bg-neutral-900 text-white hover:bg-neutral-800 disabled:bg-neutral-400 text-sm font-medium">
                {savingEdit ? 'Salvando...' : 'Salvar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Refinement Modal */}
      {refinementModal.open && refinementModal.post && (
        <PostRefinementModal
          post={refinementModal.post}
          onClose={() => setRefinementModal({ open: false, post: null })}
          onUpdate={() => fetchWeek()}
        />
      )}

      {/* Image Upload Modal */}
      {imageUploadModal.open && imageUploadModal.postId && (
        <ImageUploadModal
          open={imageUploadModal.open}
          postId={imageUploadModal.postId}
          onClose={() => setImageUploadModal({ open: false, postId: null })}
          onUpload={(postId, file) => handleUploadImage(postId, file)}
          uploading={uploadingImage === imageUploadModal.postId}
        />
      )}
    </div>
  );
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
