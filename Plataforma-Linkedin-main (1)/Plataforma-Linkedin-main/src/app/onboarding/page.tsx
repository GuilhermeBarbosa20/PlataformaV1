'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/utils/supabase/client';

type OnboardingStep = 'profile_url' | 'photos' | 'analyzing' | 'complete';

interface UploadedPhoto {
  id: string;
  file: File;
  preview: string;
  uploading: boolean;
  uploaded: boolean;
  storagePath?: string;
  error?: string;
}

export default function OnboardingPage() {
  const [currentStep, setCurrentStep] = useState<OnboardingStep>('profile_url');
  const [profileUrl, setProfileUrl] = useState('');
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCheckingStatus, setIsCheckingStatus] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('');
  const [progress, setProgress] = useState(0);
  const [user, setUser] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    checkUserStatus();
  }, []);

  // Cleanup previews on unmount
  useEffect(() => {
    return () => {
      photos.forEach(photo => URL.revokeObjectURL(photo.preview));
    };
  }, [photos]);

  const checkUserStatus = async () => {
    try {
      const { data: { user: currentUser } } = await supabase.auth.getUser();
      
      if (!currentUser) {
        router.push('/');
        return;
      }

      setUser(currentUser);

      // Check if user already completed onboarding
      const { data: userAgent } = await supabase
        .from('user_agents')
        .select('onboarding_completed, onboarding_step, linkedin_profile_url, has_been_analyzed')
        .eq('user_id', currentUser.id)
        .maybeSingle();

      if (userAgent?.onboarding_completed) {
        router.push('/');
        return;
      }

      // Resume from last step if available
      if (userAgent?.onboarding_step === 'photos') {
        setCurrentStep('photos');
      }

      if (userAgent?.linkedin_profile_url) {
        setProfileUrl(userAgent.linkedin_profile_url);
      }

      setIsCheckingStatus(false);
    } catch (err) {
      console.error('Error checking status:', err);
      setIsCheckingStatus(false);
    }
  };

  const validateLinkedInUrl = (url: string): boolean => {
    const patterns = [
      /^https?:\/\/(www\.)?linkedin\.com\/in\/[\w-]+\/?$/,
      /^linkedin\.com\/in\/[\w-]+\/?$/,
      /^[\w-]+$/, // Just the username
    ];
    return patterns.some(pattern => pattern.test(url.trim()));
  };

  const normalizeLinkedInUrl = (url: string): string => {
    let normalized = url.trim();
    
    if (/^[\w-]+$/.test(normalized)) {
      return `https://www.linkedin.com/in/${normalized}/`;
    }
    
    if (!normalized.startsWith('http')) {
      normalized = 'https://' + normalized;
    }
    
    if (normalized.includes('linkedin.com') && !normalized.includes('www.')) {
      normalized = normalized.replace('linkedin.com', 'www.linkedin.com');
    }
    
    if (!normalized.endsWith('/')) {
      normalized += '/';
    }
    
    return normalized;
  };

  const handleProfileUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateLinkedInUrl(profileUrl)) {
      setError('Por favor, insira um link válido do LinkedIn (ex: linkedin.com/in/seu-perfil)');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      if (!user) throw new Error('Usuário não autenticado');

      const normalizedUrl = normalizeLinkedInUrl(profileUrl);
      const vanityName = normalizedUrl.split('/in/')[1]?.replace('/', '') || null;

      // Save profile URL and update step
      const { error: upsertError } = await supabase
        .from('user_agents')
        .upsert({
          user_id: user.id,
          linkedin_profile_url: normalizedUrl,
          linkedin_vanity_name: vanityName,
          onboarding_step: 'photos',
          updated_at: new Date().toISOString(),
        }, { onConflict: 'user_id' });

      if (upsertError) throw new Error('Erro ao salvar perfil: ' + upsertError.message);

      setCurrentStep('photos');
    } catch (err: any) {
      console.error('Error:', err);
      setError(err.message || 'Erro desconhecido');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    
    const validFiles = files.filter(file => {
      if (!file.type.startsWith('image/')) {
        return false;
      }
      if (file.size > 5 * 1024 * 1024) { // 5MB
        return false;
      }
      return true;
    });

    const newPhotos: UploadedPhoto[] = validFiles.map(file => ({
      id: Math.random().toString(36).substring(7),
      file,
      preview: URL.createObjectURL(file),
      uploading: false,
      uploaded: false,
    }));

    setPhotos(prev => [...prev, ...newPhotos].slice(0, 5)); // Max 5 photos
    
    // Reset input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const removePhoto = (id: string) => {
    setPhotos(prev => {
      const photo = prev.find(p => p.id === id);
      if (photo) {
        URL.revokeObjectURL(photo.preview);
      }
      return prev.filter(p => p.id !== id);
    });
  };

  const uploadPhotos = async () => {
    if (!user) return;

    // Upload each photo to Supabase Storage
    const uploadPromises = photos.map(async (photo) => {
      if (photo.uploaded) return photo;

      setPhotos(prev => prev.map(p => 
        p.id === photo.id ? { ...p, uploading: true } : p
      ));

      try {
        const fileExt = photo.file.name.split('.').pop();
        const fileName = `${user.id}/${Date.now()}-${photo.id}.${fileExt}`;

        const { data, error } = await supabase.storage
          .from('user-photos')
          .upload(fileName, photo.file);

        if (error) throw error;

        // Get public URL
        const { data: urlData } = supabase.storage
          .from('user-photos')
          .getPublicUrl(fileName);

        // Save to database
        await supabase.from('user_photos').insert({
          user_id: user.id,
          storage_path: fileName,
          public_url: urlData.publicUrl,
          original_filename: photo.file.name,
          file_size: photo.file.size,
          mime_type: photo.file.type,
          is_primary: photos.indexOf(photo) === 0,
        });

        setPhotos(prev => prev.map(p => 
          p.id === photo.id ? { ...p, uploading: false, uploaded: true, storagePath: fileName } : p
        ));

        return { ...photo, uploaded: true };
      } catch (err: any) {
        console.error('Upload error:', err);
        setPhotos(prev => prev.map(p => 
          p.id === photo.id ? { ...p, uploading: false, error: err.message } : p
        ));
        return photo;
      }
    });

    await Promise.all(uploadPromises);
  };

  const handlePhotosSubmit = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Upload photos if any
      if (photos.length > 0) {
        setStatus('Enviando suas fotos...');
        setProgress(10);
        await uploadPhotos();
      }

      // Update step to analyzing
      setCurrentStep('analyzing');
      setStatus('Buscando seus posts do LinkedIn...');
      setProgress(30);

      // Start analysis
      const scrapeResponse = await fetch('/api/onboarding/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          profileUrl: normalizeLinkedInUrl(profileUrl),
          createAgent: true, // Flag to create AI agent
        }),
      });

      const result = await scrapeResponse.json();

      if (!scrapeResponse.ok) {
        throw new Error(result.error || 'Erro ao buscar posts');
      }

      setProgress(100);
      setStatus('✅ Configuração completa!');
      setCurrentStep('complete');

      // Mark onboarding as complete
      await supabase.from('user_agents').upsert({
        user_id: user.id,
        onboarding_completed: true,
        onboarding_step: 'complete',
        photos_uploaded_count: photos.length,
        updated_at: new Date().toISOString(),
      }, { onConflict: 'user_id' });

      setTimeout(() => router.push('/themes'), 2000);
    } catch (err: any) {
      console.error('Error:', err);
      setError(err.message || 'Erro desconhecido');
      setCurrentStep('photos');
    } finally {
      setIsLoading(false);
    }
  };

  if (isCheckingStatus) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-neutral-900"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress indicator */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {['profile_url', 'photos', 'analyzing'].map((step, index) => (
            <div key={step} className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                currentStep === step 
                  ? 'bg-neutral-900 text-white' 
                  : ['profile_url', 'photos', 'analyzing'].indexOf(currentStep) > index
                    ? 'bg-green-500 text-white'
                    : 'bg-neutral-200 text-neutral-500'
              }`}>
                {['profile_url', 'photos', 'analyzing'].indexOf(currentStep) > index ? '✓' : index + 1}
              </div>
              {index < 2 && (
                <div className={`w-12 h-0.5 mx-1 ${
                  ['profile_url', 'photos', 'analyzing'].indexOf(currentStep) > index 
                    ? 'bg-green-500' 
                    : 'bg-neutral-200'
                }`} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-neutral-200 p-8">
          {/* Step 1: Profile URL */}
          {currentStep === 'profile_url' && (
            <>
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-neutral-900 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.32 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.79M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/>
                  </svg>
                </div>
                <h1 className="text-2xl font-semibold text-neutral-900 mb-2">
                  Seu perfil LinkedIn
                </h1>
                <p className="text-neutral-500">
                  Insira o link do seu perfil para analisarmos seu conteúdo e sugerir temas personalizados.
                </p>
              </div>

              <form onSubmit={handleProfileUrlSubmit} className="space-y-6">
                <div>
                  <label htmlFor="profileUrl" className="block text-sm font-medium text-neutral-700 mb-2">
                    Link do perfil
                  </label>
                  <input
                    type="text"
                    id="profileUrl"
                    value={profileUrl}
                    onChange={(e) => {
                      setProfileUrl(e.target.value);
                      setError(null);
                    }}
                    placeholder="linkedin.com/in/seu-perfil"
                    className="w-full px-4 py-3 border border-neutral-200 rounded-xl focus:ring-2 focus:ring-neutral-900 focus:border-transparent outline-none transition-all text-neutral-900 placeholder:text-neutral-400"
                    disabled={isLoading}
                  />
                  {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-neutral-900 text-white py-3 px-4 rounded-xl font-medium hover:bg-neutral-800 transition-colors disabled:opacity-50"
                >
                  {isLoading ? 'Salvando...' : 'Continuar'}
                </button>
              </form>
            </>
          )}

          {/* Step 2: Photos */}
          {currentStep === 'photos' && (
            <>
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-neutral-900 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                </div>
                <h1 className="text-2xl font-semibold text-neutral-900 mb-2">
                  Suas fotos
                </h1>
                <p className="text-neutral-500">
                  Adicione fotos suas para que possamos gerar imagens personalizadas com seu rosto nos posts.
                </p>
              </div>

              <div className="space-y-6">
                {/* Upload area */}
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-neutral-200 rounded-xl p-8 text-center cursor-pointer hover:border-neutral-400 transition-colors"
                >
                  <svg className="w-12 h-12 text-neutral-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  <p className="text-neutral-600 font-medium">Clique para adicionar fotos</p>
                  <p className="text-neutral-400 text-sm mt-1">JPG, PNG ou WebP • Máx 5MB cada • Até 5 fotos</p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    multiple
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </div>

                {/* Photo previews */}
                {photos.length > 0 && (
                  <div className="grid grid-cols-3 gap-3">
                    {photos.map((photo, index) => (
                      <div key={photo.id} className="relative aspect-square rounded-xl overflow-hidden bg-neutral-100">
                        <img 
                          src={photo.preview} 
                          alt={`Foto ${index + 1}`}
                          className="w-full h-full object-cover"
                        />
                        {photo.uploading && (
                          <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                            <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent"></div>
                          </div>
                        )}
                        {photo.uploaded && (
                          <div className="absolute top-2 left-2 bg-green-500 text-white rounded-full p-1">
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                        )}
                        {index === 0 && (
                          <div className="absolute bottom-2 left-2 bg-neutral-900 text-white text-xs px-2 py-1 rounded-full">
                            Principal
                          </div>
                        )}
                        <button
                          onClick={() => removePhoto(photo.id)}
                          className="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600 transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {error && <p className="text-sm text-red-600">{error}</p>}

                <div className="flex gap-3">
                  <button
                    onClick={() => setCurrentStep('profile_url')}
                    className="flex-1 border border-neutral-200 text-neutral-700 py-3 px-4 rounded-xl font-medium hover:bg-neutral-50 transition-colors"
                  >
                    Voltar
                  </button>
                  <button
                    onClick={handlePhotosSubmit}
                    disabled={isLoading}
                    className="flex-1 bg-neutral-900 text-white py-3 px-4 rounded-xl font-medium hover:bg-neutral-800 transition-colors disabled:opacity-50"
                  >
                    {photos.length > 0 ? 'Continuar' : 'Pular este passo'}
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Step 3: Analyzing */}
          {currentStep === 'analyzing' && (
            <>
              <div className="text-center mb-8">
                <div className="w-16 h-16 bg-neutral-900 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-white animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h1 className="text-2xl font-semibold text-neutral-900 mb-2">
                  Analisando seu perfil
                </h1>
                <p className="text-neutral-500">
                  Estamos criando seu agente de IA personalizado...
                </p>
              </div>

              <div className="space-y-6">
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-neutral-600">{status}</span>
                    <span className="text-neutral-400">{progress}%</span>
                  </div>
                  <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-neutral-900 rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>

                <div className="bg-neutral-50 rounded-xl p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-5 h-5 mt-0.5">
                      <svg className="animate-spin text-neutral-400" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                      </svg>
                    </div>
                    <div className="text-sm text-neutral-600">
                      <p className="font-medium">Isso pode levar alguns minutos...</p>
                      <p className="text-neutral-400 mt-1">
                        Estamos buscando seus posts e criando seu assistente personalizado.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Step 4: Complete */}
          {currentStep === 'complete' && (
            <>
              <div className="text-center">
                <div className="w-16 h-16 bg-green-500 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h1 className="text-2xl font-semibold text-neutral-900 mb-2">
                  Tudo pronto!
                </h1>
                <p className="text-neutral-500 mb-6">
                  Seu agente de IA foi configurado com sucesso. Redirecionando...
                </p>
                <div className="animate-spin rounded-full h-6 w-6 border-2 border-neutral-900 border-t-transparent mx-auto"></div>
              </div>
            </>
          )}
        </div>

        <p className="text-center text-xs text-neutral-400 mt-6">
          Seus dados são usados apenas para personalizar suas sugestões de conteúdo.
        </p>
      </div>
    </div>
  );
}
