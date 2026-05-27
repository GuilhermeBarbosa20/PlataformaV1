'use client';

import { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface RefinementHistoryItem {
  type: 'text' | 'image';
  instruction: string;
  timestamp: string;
  previousContent?: string;
  newContent?: string;
}

interface PostData {
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
  generated_image_url?: string | null;
  generated_image_prompt?: string | null;
  refinement_history?: RefinementHistoryItem[];
  text_approved?: boolean;
  image_approved?: boolean;
  post_approved?: boolean;
  custom_image_url?: string | null;
}

interface PostRefinementModalProps {
  post: PostData;
  onClose: () => void;
  onUpdate: () => Promise<void> | void;
}

type ActiveSection = 'text' | 'image' | 'photos';

export default function PostRefinementModal({
  post,
  onClose,
  onUpdate,
}: PostRefinementModalProps) {
  const [activeSection, setActiveSection] = useState<ActiveSection>('text');
  const [textInput, setTextInput] = useState('');
  const [imageInput, setImageInput] = useState('');
  const [textMessages, setTextMessages] = useState<Message[]>([]);
  const [imageMessages, setImageMessages] = useState<Message[]>([]);
  const [isLoadingText, setIsLoadingText] = useState(false);
  const [isLoadingImage, setIsLoadingImage] = useState(false);
  const [isUploadingPhotos, setIsUploadingPhotos] = useState(false);
  const [userPhotos, setUserPhotos] = useState<any[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [currentPost, setCurrentPost] = useState<PostData>(post);
  const [previewVersion, setPreviewVersion] = useState(0); // Force re-render counter

  const textChatRef = useRef<HTMLDivElement>(null);
  const imageChatRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Debug: Log when currentPost changes
  useEffect(() => {
    console.log('[PostRefinementModal] currentPost updated:', {
      caption: currentPost.caption?.substring(0, 50),
      previewVersion,
    });
  }, [currentPost, previewVersion]);

  // Fetch user photos on mount
  useEffect(() => {
    fetchUserPhotos();
  }, []);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (textChatRef.current) {
      textChatRef.current.scrollTop = textChatRef.current.scrollHeight;
    }
  }, [textMessages]);

  useEffect(() => {
    if (imageChatRef.current) {
      imageChatRef.current.scrollTop = imageChatRef.current.scrollHeight;
    }
  }, [imageMessages]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const fetchUserPhotos = async () => {
    try {
      const response = await fetch('/api/user/photos');
      if (response.ok) {
        const data = await response.json();
        setUserPhotos(data.photos || []);
      }
    } catch (error) {
      console.error('Error fetching photos:', error);
    }
  };

  const handleTextRefinement = async () => {
    if (!textInput.trim() || isLoadingText) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: textInput,
      timestamp: new Date(),
    };

    const currentInstruction = textInput;
    setTextMessages(prev => [...prev, userMessage]);
    setTextInput('');
    setIsLoadingText(true);

    try {
      // Get the current text from the post (caption or ai_content.body)
      const currentText = currentPost.caption || currentPost.ai_content?.body || '';

      const response = await fetch(`/api/posts/${currentPost.id}/refine-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction: currentInstruction,
          currentText: currentText, // Pass current text as reference
        }),
      });

      const data = await response.json();
      console.log('[PostRefinementModal] API Response:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao refinar texto');
      }

      // Clear session messages since refinement was successful
      setTextMessages([]);

      // Update local post state with new content and history
      // Use the refined text from response OR from the updated post object
      const newCaption = data.refinedText || data.post?.caption;
      console.log('[PostRefinementModal] New caption to set:', newCaption);

      if (newCaption) {
        const newHistoryItem: RefinementHistoryItem = {
          type: 'text',
          instruction: currentInstruction,
          timestamp: new Date().toISOString(),
        };

        // Create a completely new object to ensure React detects the change
        const updatedPost: PostData = {
          ...currentPost,
          caption: newCaption,
          refinement_history: [...(currentPost.refinement_history || []), newHistoryItem],
        };

        console.log('[PostRefinementModal] Text refined successfully, closing modal');
      }

      // Update parent (wait for data refresh) and then close modal so user sees fresh data
      await onUpdate();
      onClose();

    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `❌ Erro: ${error.message}`,
        timestamp: new Date(),
      };
      setTextMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoadingText(false);
    }
  };

  const handleImageRefinement = async () => {
    if (!imageInput.trim() || isLoadingImage) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: imageInput,
      timestamp: new Date(),
    };

    const currentInstruction = imageInput;
    setImageMessages(prev => [...prev, userMessage]);
    setImageInput('');
    setIsLoadingImage(true);

    try {
      const response = await fetch(`/api/posts/${currentPost.id}/refine-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction: currentInstruction,
          forceReanalyzePhotos: false,
        }),
      });

      const data = await response.json();
      console.log('[PostRefinementModal] Image API Response:', data);

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao refinar imagem');
      }

      // Clear session messages since refinement was successful
      setImageMessages([]);

      // Update local post state with new image and history
      const newImageUrl = data.imageUrl || data.post?.generated_image_url;
      console.log('[PostRefinementModal] New image URL:', newImageUrl);

      if (newImageUrl) {
        const newHistoryItem: RefinementHistoryItem = {
          type: 'image',
          instruction: currentInstruction,
          timestamp: new Date().toISOString(),
        };

        // Create a completely new object to ensure React detects the change
        const updatedPost: PostData = {
          ...currentPost,
          generated_image_url: newImageUrl,
          refinement_history: [...(currentPost.refinement_history || []), newHistoryItem],
        };

        console.log('[PostRefinementModal] Image refined successfully, closing modal');
      }

      // Update parent (wait for data refresh) and then close modal so user sees fresh data
      await onUpdate();
      onClose();

    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `❌ Erro: ${error.message}`,
        timestamp: new Date(),
      };
      setImageMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoadingImage(false);
    }
  };

  const handleGenerateImage = async () => {
    setIsLoadingImage(true);

    const loadingMessage: Message = {
      id: Date.now().toString(),
      role: 'assistant',
      content: '🎨 Gerando nova imagem...',
      timestamp: new Date(),
    };
    setImageMessages(prev => [...prev, loadingMessage]);

    try {
      const response = await fetch(`/api/posts/${post.id}/generate-image`, {
        method: 'POST',
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao gerar imagem');
      }

      const successMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `✅ Nova imagem gerada!${data.personalized ? ' 🎯 Personalizada com suas fotos.' : ''}`,
        timestamp: new Date(),
      };

      setImageMessages(prev => prev.slice(0, -1).concat(successMessage));

      // Update parent (wait for data refresh) and then close modal so user sees fresh data
      await onUpdate();
      onClose();

    } catch (error: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `❌ Erro: ${error.message}`,
        timestamp: new Date(),
      };
      setImageMessages(prev => prev.slice(0, -1).concat(errorMessage));
    } finally {
      setIsLoadingImage(false);
    }
  };

  const handlePhotoUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setIsUploadingPhotos(true);

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

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao enviar fotos');
      }

      await fetchUserPhotos();

    } catch (error: any) {
      alert(`Erro: ${error.message}`);
    } finally {
      setIsUploadingPhotos(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeletePhoto = async (photoId: string) => {
    if (!confirm('Tem certeza que deseja remover esta foto?')) return;

    try {
      const response = await fetch(`/api/user/photos?id=${photoId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Erro ao remover foto');
      }

      await fetchUserPhotos();
    } catch (error: any) {
      alert(`Erro: ${error.message}`);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handlePhotoUpload(e.dataTransfer.files);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('pt-PT', {
      weekday: 'long',
      day: 'numeric',
      month: 'long'
    });
  };

  const textSuggestions = [
    'Tom mais informal',
    'Adicionar pergunta',
    'Remover emojis',
    'Mais conciso',
    'Adicionar dados',
    'CTA mais forte',
  ];

  const imageSuggestions = [
    'Escritório moderno',
    'Mais sorridente',
    'Ambiente tech',
    'Ao ar livre',
    'Mais minimalista',
    'Luz mais quente',
  ];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100 bg-gradient-to-r from-violet-600 to-purple-600">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Refinar Post com IA</h2>
              <p className="text-sm text-white/70">{formatDate(post.scheduled_for)}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl bg-white/10 hover:bg-white/20 flex items-center justify-center text-white transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">

          {/* Left Panel - Post Preview */}
          <div className="w-[400px] border-r border-neutral-100 flex flex-col bg-neutral-50">
            <div className="p-4 border-b border-neutral-100 bg-white">
              <h3 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-violet-500"></span>
                Preview do Post
              </h3>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Image Preview Card - FIRST */}
              <div
                key={`image-preview-${previewVersion}`}
                className="bg-white rounded-xl border border-neutral-200 overflow-hidden"
              >
                <div className="px-4 py-2 border-b border-neutral-100 bg-neutral-50">
                  <h4 className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Imagem do Post</h4>
                </div>
                {currentPost.generated_image_url ? (
                  <div className="relative group">
                    <img
                      key={`img-${previewVersion}-${currentPost.generated_image_url}`}
                      src={`${currentPost.generated_image_url}?v=${previewVersion}`}
                      alt="Post image"
                      className="w-full aspect-[4/5] object-cover"
                    />
                    <a
                      href={currentPost.generated_image_url}
                      target="_blank"
                      rel="noreferrer"
                      className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-sm font-medium transition-opacity"
                    >
                      <svg className="w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      Abrir em nova aba
                    </a>
                  </div>
                ) : (
                  <div className="p-8 text-center">
                    <div className="w-12 h-12 rounded-full bg-neutral-100 flex items-center justify-center mx-auto mb-2">
                      <svg className="w-6 h-6 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <p className="text-sm text-neutral-400">Nenhuma imagem gerada</p>
                    {currentPost.approval_status === 'aprovado' && (
                      <button
                        onClick={handleGenerateImage}
                        disabled={isLoadingImage}
                        className={`mt-3 px-4 py-2 text-xs font-medium rounded-lg transition-all flex items-center justify-center gap-2 min-w-[120px] ${isLoadingImage
                            ? 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                            : 'text-violet-700 bg-violet-50 hover:bg-violet-100'
                          }`}
                      >
                        {isLoadingImage ? (
                          <>
                            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            <span>Gerando...</span>
                          </>
                        ) : (
                          'Gerar Imagem'
                        )}
                      </button>
                    )}
                    {currentPost.approval_status !== 'aprovado' && (
                      <p className="mt-2 text-xs text-amber-600">Aprove o post primeiro para gerar imagem</p>
                    )}
                  </div>
                )}
              </div>

              {/* Post Content Card - SECOND */}
              <div
                key={`post-content-${previewVersion}`}
                className="bg-white rounded-xl border border-neutral-200 p-4 space-y-3"
              >
                <div className="pb-2 border-b border-neutral-100">
                  <h4 className="text-xs font-medium text-neutral-500 uppercase tracking-wider">Texto do Post</h4>
                </div>

                {/* Show caption if it exists (refined text), otherwise show ai_content parts */}
                {currentPost.caption ? (
                  <p className="text-sm text-neutral-700 leading-relaxed whitespace-pre-wrap">
                    {currentPost.caption}
                  </p>
                ) : (
                  <>
                    {currentPost.ai_content?.headline && (
                      <h4 className="font-semibold text-neutral-900 text-sm leading-snug">
                        {currentPost.ai_content.headline}
                      </h4>
                    )}

                    {currentPost.ai_content?.hook && (
                      <p className="text-sm text-neutral-500 italic border-l-2 border-violet-300 pl-3">
                        {currentPost.ai_content.hook}
                      </p>
                    )}

                    {currentPost.ai_content?.body && (
                      <p className="text-sm text-neutral-700 leading-relaxed whitespace-pre-wrap">
                        {currentPost.ai_content.body}
                      </p>
                    )}

                    {currentPost.ai_content?.cta && (
                      <p className="text-sm font-medium text-violet-700 pt-2 border-t border-neutral-100">
                        → {currentPost.ai_content.cta}
                      </p>
                    )}
                  </>
                )}

                {/* Hashtags at the bottom of text */}
                {currentPost.ai_content?.hashtags && currentPost.ai_content.hashtags.length > 0 && (
                  <div className="pt-3 border-t border-neutral-100">
                    <p className="text-xs text-neutral-400 mb-2">Hashtags</p>
                    <div className="flex flex-wrap gap-1.5">
                      {currentPost.ai_content.hashtags.map((tag, i) => (
                        <span key={i} className="text-xs text-violet-600 bg-violet-50 px-2 py-0.5 rounded-full">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Panel - Refinement Tools */}
          <div className="flex-1 flex flex-col">

            {/* Section Tabs */}
            <div className="flex border-b border-neutral-100">
              <button
                onClick={() => setActiveSection('text')}
                className={`flex-1 px-6 py-4 text-sm font-medium transition-all relative ${activeSection === 'text'
                    ? 'text-violet-700 bg-violet-50'
                    : 'text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50'
                  }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Refinar Texto
                </span>
                {activeSection === 'text' && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-violet-600" />
                )}
              </button>

              {/* Only show image refinement tab if post is approved AND has an image */}
              {currentPost.approval_status === 'aprovado' && currentPost.generated_image_url && (
                <button
                  onClick={() => setActiveSection('image')}
                  className={`flex-1 px-6 py-4 text-sm font-medium transition-all relative ${activeSection === 'image'
                      ? 'text-purple-700 bg-purple-50'
                      : 'text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50'
                    }`}
                >
                  <span className="flex items-center justify-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    Refinar Imagem
                  </span>
                  {activeSection === 'image' && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-purple-600" />
                  )}
                </button>
              )}

              <button
                onClick={() => setActiveSection('photos')}
                className={`flex-1 px-6 py-4 text-sm font-medium transition-all relative ${activeSection === 'photos'
                    ? 'text-emerald-700 bg-emerald-50'
                    : 'text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50'
                  }`}
              >
                <span className="flex items-center justify-center gap-2">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  Minhas Fotos ({userPhotos.length})
                </span>
                {activeSection === 'photos' && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-600" />
                )}
              </button>
            </div>

            {/* Section Content */}
            <div className="flex-1 overflow-hidden">

              {/* TEXT SECTION */}
              {activeSection === 'text' && (
                <div className="h-full flex flex-col p-6">
                  {/* Input - NOW AT TOP */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-neutral-700 mb-2">
                      Descreva como quer ajustar o texto:
                    </label>
                    <div className="flex gap-3">
                      <input
                        type="text"
                        value={textInput}
                        onChange={(e) => setTextInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleTextRefinement()}
                        placeholder="Ex: Deixe mais informal, remova emojis, adicione dados..."
                        className="flex-1 px-4 py-3 bg-white border border-neutral-200 rounded-xl text-sm focus:ring-2 focus:ring-violet-200 focus:border-violet-400 outline-none transition-all"
                        disabled={isLoadingText}
                      />
                      <button
                        onClick={handleTextRefinement}
                        disabled={isLoadingText || !textInput.trim()}
                        className="px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:bg-neutral-300 text-white rounded-xl text-sm font-medium transition-colors"
                      >
                        {isLoadingText ? (
                          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          'Refinar'
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Suggestions */}
                  <div className="mb-4">
                    <p className="text-xs font-medium text-neutral-500 mb-2">Sugestões rápidas:</p>
                    <div className="flex flex-wrap gap-2">
                      {textSuggestions.map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => setTextInput(suggestion)}
                          className="px-3 py-1.5 text-xs bg-violet-50 text-violet-700 rounded-full hover:bg-violet-100 transition-colors border border-violet-200"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Chat History - SHOWS REAL REFINEMENT HISTORY */}
                  <div className="flex-1 min-h-0">
                    <p className="text-xs font-medium text-neutral-500 mb-2">Histórico de refinamentos de texto:</p>
                    <div
                      ref={textChatRef}
                      className="h-full max-h-[200px] overflow-y-auto space-y-3 bg-neutral-50 rounded-xl p-4 border border-neutral-200"
                    >
                      {/* Show saved refinement history for TEXT */}
                      {(() => {
                        const textHistory = (currentPost.refinement_history || [])
                          .filter(item => item.type === 'text')
                          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

                        if (textHistory.length === 0 && textMessages.length === 0) {
                          return (
                            <div className="flex items-center justify-center py-6">
                              <p className="text-sm text-neutral-400">Nenhum refinamento de texto ainda</p>
                            </div>
                          );
                        }

                        return (
                          <>
                            {/* Saved history from database */}
                            {textHistory.map((item, index) => (
                              <div key={`history-${index}`} className="flex justify-end">
                                <div className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm bg-violet-600 text-white rounded-br-md">
                                  <p className="whitespace-pre-wrap">{item.instruction}</p>
                                  <p className="text-xs text-violet-200 mt-1">
                                    {new Date(item.timestamp).toLocaleString('pt-BR', {
                                      day: '2-digit',
                                      month: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit'
                                    })}
                                  </p>
                                </div>
                              </div>
                            ))}
                            {/* Current session messages (only user messages) */}
                            {textMessages.filter(m => m.role === 'user').map((msg) => (
                              <div key={msg.id} className="flex justify-end">
                                <div className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm bg-violet-500 text-white rounded-br-md border-2 border-violet-300">
                                  <p className="whitespace-pre-wrap">{msg.content}</p>
                                  <p className="text-xs text-violet-200 mt-1">Agora</p>
                                </div>
                              </div>
                            ))}
                          </>
                        );
                      })()}
                      {isLoadingText && (
                        <div className="flex justify-center">
                          <div className="bg-white border border-neutral-200 rounded-2xl px-4 py-3">
                            <div className="flex items-center space-x-1.5">
                              <div className="w-2 h-2 bg-violet-500 rounded-full animate-bounce" />
                              <div className="w-2 h-2 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                              <div className="w-2 h-2 bg-violet-500 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                              <span className="text-xs text-neutral-500 ml-2">Refinando...</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* IMAGE SECTION */}
              {activeSection === 'image' && (
                <div className="h-full flex flex-col p-6">
                  {/* Input - NOW AT TOP */}
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-neutral-700 mb-2">
                      Descreva como quer ajustar a imagem:
                    </label>
                    <div className="flex gap-3">
                      <input
                        type="text"
                        value={imageInput}
                        onChange={(e) => setImageInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleImageRefinement()}
                        placeholder="Ex: Mude o cenário, adicione tecnologia, luz mais quente..."
                        className="flex-1 px-4 py-3 bg-white border border-neutral-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-200 focus:border-purple-400 outline-none transition-all"
                        disabled={isLoadingImage}
                      />
                      <button
                        onClick={handleImageRefinement}
                        disabled={isLoadingImage || !imageInput.trim()}
                        className="px-6 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-neutral-300 text-white rounded-xl text-sm font-medium transition-colors"
                      >
                        {isLoadingImage ? (
                          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          'Refinar'
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Photo status */}
                  <div className={`mb-4 flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm ${userPhotos.length > 0
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}>
                    {userPhotos.length > 0 ? (
                      <>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        {userPhotos.length} foto(s) disponíveis para personalização
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                        Adicione fotos na aba "Minhas Fotos" para personalização
                      </>
                    )}
                  </div>

                  {/* Suggestions */}
                  <div className="mb-4">
                    <p className="text-xs font-medium text-neutral-500 mb-2">Sugestões rápidas:</p>
                    <div className="flex flex-wrap gap-2">
                      {imageSuggestions.map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => setImageInput(suggestion)}
                          className="px-3 py-1.5 text-xs bg-purple-50 text-purple-700 rounded-full hover:bg-purple-100 transition-colors border border-purple-200"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Chat History - SHOWS REAL REFINEMENT HISTORY */}
                  <div className="flex-1 min-h-0">
                    <p className="text-xs font-medium text-neutral-500 mb-2">Histórico de refinamentos de imagem:</p>
                    <div
                      ref={imageChatRef}
                      className="h-full max-h-[200px] overflow-y-auto space-y-3 bg-neutral-50 rounded-xl p-4 border border-neutral-200"
                    >
                      {/* Show saved refinement history for IMAGE */}
                      {(() => {
                        const imageHistory = (currentPost.refinement_history || [])
                          .filter(item => item.type === 'image')
                          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

                        if (imageHistory.length === 0 && imageMessages.length === 0) {
                          return (
                            <div className="flex items-center justify-center py-6">
                              <p className="text-sm text-neutral-400">Nenhum refinamento de imagem ainda</p>
                            </div>
                          );
                        }

                        return (
                          <>
                            {/* Saved history from database */}
                            {imageHistory.map((item, index) => (
                              <div key={`history-${index}`} className="flex justify-end">
                                <div className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm bg-purple-600 text-white rounded-br-md">
                                  <p className="whitespace-pre-wrap">{item.instruction}</p>
                                  <p className="text-xs text-purple-200 mt-1">
                                    {new Date(item.timestamp).toLocaleString('pt-BR', {
                                      day: '2-digit',
                                      month: '2-digit',
                                      hour: '2-digit',
                                      minute: '2-digit'
                                    })}
                                  </p>
                                </div>
                              </div>
                            ))}
                            {/* Current session messages (only user messages) */}
                            {imageMessages.filter(m => m.role === 'user').map((msg) => (
                              <div key={msg.id} className="flex justify-end">
                                <div className="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm bg-purple-500 text-white rounded-br-md border-2 border-purple-300">
                                  <p className="whitespace-pre-wrap">{msg.content}</p>
                                  <p className="text-xs text-purple-200 mt-1">Agora</p>
                                </div>
                              </div>
                            ))}
                          </>
                        );
                      })()}
                      {isLoadingImage && (
                        <div className="flex justify-center">
                          <div className="bg-white border border-neutral-200 rounded-2xl px-4 py-3">
                            <div className="flex items-center space-x-2 text-sm text-neutral-500">
                              <svg className="animate-spin h-4 w-4 text-purple-500" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                              </svg>
                              <span>Gerando imagem...</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* PHOTOS SECTION */}
              {activeSection === 'photos' && (
                <div className="h-full flex flex-col p-6 overflow-y-auto">
                  <div className="mb-4">
                    <p className="text-sm text-neutral-600">
                      Adicione fotos suas para que a IA gere imagens personalizadas com sua aparência.
                      Quanto mais fotos de diferentes ângulos, melhor o resultado.
                    </p>
                  </div>

                  {/* Upload area */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${dragOver
                        ? 'border-emerald-500 bg-emerald-50'
                        : 'border-neutral-300 hover:border-emerald-400 hover:bg-neutral-50'
                      }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(e) => handlePhotoUpload(e.target.files)}
                      className="hidden"
                    />
                    {isUploadingPhotos ? (
                      <div className="flex items-center justify-center space-x-2">
                        <svg className="animate-spin h-6 w-6 text-emerald-600" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        <span className="text-emerald-600 font-medium">Enviando...</span>
                      </div>
                    ) : (
                      <>
                        <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                          <svg className="w-7 h-7 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                          </svg>
                        </div>
                        <p className="text-sm text-neutral-700 font-medium">
                          Arraste fotos aqui ou clique para selecionar
                        </p>
                        <p className="text-xs text-neutral-400 mt-1">
                          Máximo 5MB por foto • JPG, PNG, WebP
                        </p>
                      </>
                    )}
                  </div>

                  {/* Photos grid */}
                  {userPhotos.length > 0 && (
                    <div className="mt-6">
                      <h4 className="text-sm font-medium text-neutral-700 mb-3">Suas fotos ({userPhotos.length})</h4>
                      <div className="grid grid-cols-4 gap-3">
                        {userPhotos.map((photo) => (
                          <div
                            key={photo.id}
                            className="relative group aspect-square rounded-xl overflow-hidden bg-neutral-100 border border-neutral-200"
                          >
                            <img
                              src={photo.public_url}
                              alt="User photo"
                              className="w-full h-full object-cover"
                            />
                            {photo.is_primary && (
                              <div className="absolute top-2 left-2 bg-emerald-500 text-white text-[10px] px-2 py-0.5 rounded-full font-medium">
                                Principal
                              </div>
                            )}
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <button
                                onClick={(e) => { e.stopPropagation(); handleDeletePhoto(photo.id); }}
                                className="p-2 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors"
                                title="Remover foto"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {userPhotos.length === 0 && (
                    <div className="mt-6 text-center py-8">
                      <div className="w-16 h-16 rounded-full bg-neutral-100 flex items-center justify-center mx-auto mb-3">
                        <svg className="w-8 h-8 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </div>
                      <p className="text-sm text-neutral-400">Nenhuma foto adicionada ainda</p>
                    </div>
                  )}

                  {userPhotos.length > 0 && (
                    <div className="mt-4 p-3 bg-violet-50 rounded-lg border border-violet-100">
                      <p className="text-xs text-violet-700 flex items-start gap-2">
                        <svg className="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>
                          <strong>Dica:</strong> Adicione fotos de diferentes ângulos e iluminações para que a IA tenha mais referências e gere imagens mais fiéis à sua aparência.
                        </span>
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
