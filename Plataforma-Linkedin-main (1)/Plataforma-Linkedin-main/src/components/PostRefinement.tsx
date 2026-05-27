'use client';

import { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface PostRefinementProps {
  postId: string;
  currentCaption: string;
  currentImageUrl?: string;
  onTextRefined?: (newCaption: string) => void;
  onImageRefined?: (newImageUrl: string) => void;
  onClose?: () => void;
}

type ActiveTab = 'text' | 'image' | 'photos';

export default function PostRefinement({
  postId,
  currentCaption,
  currentImageUrl,
  onTextRefined,
  onImageRefined,
  onClose,
}: PostRefinementProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>('text');
  const [textInput, setTextInput] = useState('');
  const [imageInput, setImageInput] = useState('');
  const [textMessages, setTextMessages] = useState<Message[]>([]);
  const [imageMessages, setImageMessages] = useState<Message[]>([]);
  const [isLoadingText, setIsLoadingText] = useState(false);
  const [isLoadingImage, setIsLoadingImage] = useState(false);
  const [isUploadingPhotos, setIsUploadingPhotos] = useState(false);
  const [userPhotos, setUserPhotos] = useState<any[]>([]);
  const [dragOver, setDragOver] = useState(false);
  
  const textChatRef = useRef<HTMLDivElement>(null);
  const imageChatRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

    setTextMessages(prev => [...prev, userMessage]);
    setTextInput('');
    setIsLoadingText(true);

    try {
      const response = await fetch(`/api/posts/${postId}/refine-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction: textInput,
          conversationHistory: textMessages.map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao refinar texto');
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `✅ Texto refinado com sucesso!\n\nNovo texto:\n\n${data.refinedText}`,
        timestamp: new Date(),
      };

      setTextMessages(prev => [...prev, assistantMessage]);
      onTextRefined?.(data.refinedText);

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

    setImageMessages(prev => [...prev, userMessage]);
    setImageInput('');
    setIsLoadingImage(true);

    try {
      const response = await fetch(`/api/posts/${postId}/refine-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction: imageInput,
          forceReanalyzePhotos: false,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Erro ao refinar imagem');
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `✅ Imagem refinada com sucesso!${data.personalized ? '\n\n🎯 Imagem personalizada com suas fotos.' : ''}`,
        timestamp: new Date(),
      };

      setImageMessages(prev => [...prev, assistantMessage]);
      onImageRefined?.(data.post.generated_image_url);

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
      alert(`${data.photos.length} foto(s) adicionada(s) com sucesso!`);

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

  const handleSetPrimary = async (photoId: string) => {
    try {
      // This would need an API endpoint to set primary
      // For now, we'll just refresh the photos
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

  const textSuggestions = [
    'Deixe o tom mais informal',
    'Adicione uma pergunta no final',
    'Remova os emojis',
    'Torne mais conciso',
    'Adicione dados/estatísticas',
    'Mude o CTA para algo mais engajador',
  ];

  const imageSuggestions = [
    'Mude o cenário para um escritório moderno',
    'Coloque a pessoa sorrindo mais',
    'Adicione elementos de tecnologia',
    'Mude para um ambiente ao ar livre',
    'Deixe mais clean e minimalista',
    'Ajuste a iluminação para mais quente',
  ];

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
        <h3 className="font-semibold text-lg">✨ Refinamento do Post</h3>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-white/20 rounded transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        <button
          onClick={() => setActiveTab('text')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'text'
              ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
              : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          📝 Refinar Texto
        </button>
        <button
          onClick={() => setActiveTab('image')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'image'
              ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50'
              : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          🖼️ Refinar Imagem
        </button>
        <button
          onClick={() => setActiveTab('photos')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeTab === 'photos'
              ? 'text-green-600 border-b-2 border-green-600 bg-green-50'
              : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
          }`}
        >
          📷 Minhas Fotos ({userPhotos.length})
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Text Refinement Tab */}
        {activeTab === 'text' && (
          <div className="space-y-4">
            {/* Current text preview */}
            <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-600 max-h-32 overflow-y-auto">
              <p className="font-medium text-gray-700 mb-1">Texto atual:</p>
              <p className="whitespace-pre-wrap">{currentCaption.substring(0, 300)}...</p>
            </div>

            {/* Suggestions */}
            <div className="flex flex-wrap gap-2">
              {textSuggestions.map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => setTextInput(suggestion)}
                  className="px-3 py-1 text-xs bg-blue-100 text-blue-700 rounded-full hover:bg-blue-200 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>

            {/* Chat messages */}
            <div
              ref={textChatRef}
              className="h-48 overflow-y-auto space-y-3 border rounded-lg p-3 bg-gray-50"
            >
              {textMessages.length === 0 && (
                <p className="text-center text-gray-400 text-sm py-8">
                  Digite uma instrução para refinar o texto do post
                </p>
              )}
              {textMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                      msg.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-700'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {isLoadingText && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleTextRefinement()}
                placeholder="Ex: Deixe o texto mais informal e adicione uma pergunta..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={isLoadingText}
              />
              <button
                onClick={handleTextRefinement}
                disabled={isLoadingText || !textInput.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoadingText ? '...' : 'Refinar'}
              </button>
            </div>
          </div>
        )}

        {/* Image Refinement Tab */}
        {activeTab === 'image' && (
          <div className="space-y-4">
            {/* Current image preview */}
            {currentImageUrl && (
              <div className="flex justify-center">
                <img
                  src={currentImageUrl}
                  alt="Current post image"
                  className="max-h-40 rounded-lg shadow-sm"
                />
              </div>
            )}

            {/* Photo count indicator */}
            <div className={`text-center text-sm ${userPhotos.length > 0 ? 'text-green-600' : 'text-orange-500'}`}>
              {userPhotos.length > 0 
                ? `✅ ${userPhotos.length} foto(s) sua(s) serão usadas para personalização`
                : '⚠️ Adicione fotos suas na aba "Minhas Fotos" para melhor personalização'
              }
            </div>

            {/* Suggestions */}
            <div className="flex flex-wrap gap-2">
              {imageSuggestions.map((suggestion, i) => (
                <button
                  key={i}
                  onClick={() => setImageInput(suggestion)}
                  className="px-3 py-1 text-xs bg-purple-100 text-purple-700 rounded-full hover:bg-purple-200 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>

            {/* Chat messages */}
            <div
              ref={imageChatRef}
              className="h-48 overflow-y-auto space-y-3 border rounded-lg p-3 bg-gray-50"
            >
              {imageMessages.length === 0 && (
                <p className="text-center text-gray-400 text-sm py-8">
                  Digite uma instrução para refinar a imagem do post
                </p>
              )}
              {imageMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                      msg.role === 'user'
                        ? 'bg-purple-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-700'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {isLoadingImage && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-2">
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      <span>Gerando imagem refinada...</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={imageInput}
                onChange={(e) => setImageInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleImageRefinement()}
                placeholder="Ex: Mude para um escritório com vista para a cidade..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                disabled={isLoadingImage}
              />
              <button
                onClick={handleImageRefinement}
                disabled={isLoadingImage || !imageInput.trim()}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoadingImage ? '...' : 'Refinar'}
              </button>
            </div>
          </div>
        )}

        {/* Photos Tab */}
        {activeTab === 'photos' && (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Adicione mais fotos suas para melhorar a personalização das imagens geradas.
              Quanto mais fotos, mais precisa será a representação.
            </p>

            {/* Upload area */}
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                dragOver
                  ? 'border-green-500 bg-green-50'
                  : 'border-gray-300 hover:border-green-400 hover:bg-gray-50'
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
                  <svg className="animate-spin h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span className="text-green-600">Enviando...</span>
                </div>
              ) : (
                <>
                  <svg className="mx-auto h-10 w-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <p className="mt-2 text-sm text-gray-600">
                    Arraste fotos aqui ou clique para selecionar
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Máximo 5MB por foto • JPG, PNG, WebP
                  </p>
                </>
              )}
            </div>

            {/* Photos grid */}
            <div className="grid grid-cols-3 gap-3">
              {userPhotos.map((photo) => (
                <div
                  key={photo.id}
                  className="relative group aspect-square rounded-lg overflow-hidden bg-gray-100"
                >
                  <img
                    src={photo.public_url}
                    alt="User photo"
                    className="w-full h-full object-cover"
                  />
                  {photo.is_primary && (
                    <div className="absolute top-1 left-1 bg-green-500 text-white text-xs px-2 py-0.5 rounded-full">
                      Principal
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    {!photo.is_primary && (
                      <button
                        onClick={() => handleSetPrimary(photo.id)}
                        className="p-2 bg-green-500 text-white rounded-full hover:bg-green-600"
                        title="Definir como principal"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </button>
                    )}
                    <button
                      onClick={() => handleDeletePhoto(photo.id)}
                      className="p-2 bg-red-500 text-white rounded-full hover:bg-red-600"
                      title="Remover foto"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {userPhotos.length === 0 && (
              <p className="text-center text-gray-400 text-sm py-4">
                Nenhuma foto adicionada ainda
              </p>
            )}

            {userPhotos.length > 0 && (
              <p className="text-xs text-gray-500 text-center">
                💡 Dica: Adicione fotos de diferentes ângulos e iluminações para melhor resultado
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
