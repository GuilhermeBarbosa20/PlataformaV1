import { createClient } from '@/utils/supabase/server';

const BUCKET_NAME = 'generated-images';

interface UploadImageResult {
  success: boolean;
  storagePath?: string;
  publicUrl?: string;
  error?: string;
}

interface SaveImageMetadata {
  userId: string;
  postId?: string;
  prompt?: string;
  theme?: string;
  style?: string;
  aspectRatio?: string;
  modelUsed?: string;
  isPersonalized?: boolean;
  generationParams?: Record<string, any>;
}

/**
 * Converte base64 para Buffer
 */
function base64ToBuffer(base64: string): Buffer {
  // Remove o prefixo data:image/png;base64, se existir
  const base64Data = base64.replace(/^data:image\/\w+;base64,/, '');
  return Buffer.from(base64Data, 'base64');
}

/**
 * Gera um nome único para o arquivo
 */
function generateFileName(userId: string, postId?: string): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  const prefix = postId ? `post-${postId.substring(0, 8)}` : 'standalone';
  return `${userId}/${prefix}-${timestamp}-${random}.png`;
}

/**
 * Upload de imagem base64 para o Supabase Storage
 */
export async function uploadImageToStorage(
  base64Image: string,
  userId: string,
  postId?: string
): Promise<UploadImageResult> {
  try {
    const supabase = await createClient();
    
    // Converter base64 para buffer
    const imageBuffer = base64ToBuffer(base64Image);
    
    // Gerar nome do arquivo
    const fileName = generateFileName(userId, postId);
    
    console.log('[uploadImageToStorage] Uploading to:', fileName);
    console.log('[uploadImageToStorage] Buffer size:', imageBuffer.length, 'bytes');
    
    // Upload para o Storage
    const { data, error } = await supabase.storage
      .from(BUCKET_NAME)
      .upload(fileName, imageBuffer, {
        contentType: 'image/png',
        cacheControl: '3600',
        upsert: false
      });

    if (error) {
      console.error('[uploadImageToStorage] Upload error:', error);
      return { success: false, error: error.message };
    }

    // Obter URL pública
    const { data: urlData } = supabase.storage
      .from(BUCKET_NAME)
      .getPublicUrl(fileName);

    console.log('[uploadImageToStorage] Public URL:', urlData.publicUrl);

    return {
      success: true,
      storagePath: data.path,
      publicUrl: urlData.publicUrl
    };

  } catch (error: any) {
    console.error('[uploadImageToStorage] Exception:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Salva os metadados da imagem no banco de dados
 */
export async function saveImageMetadata(
  metadata: SaveImageMetadata & { storagePath: string; publicUrl: string }
): Promise<{ success: boolean; imageId?: string; error?: string }> {
  try {
    const supabase = await createClient();

    const { data, error } = await supabase
      .from('generated_images')
      .insert({
        user_id: metadata.userId,
        post_id: metadata.postId || null,
        storage_path: metadata.storagePath,
        public_url: metadata.publicUrl,
        prompt: metadata.prompt,
        theme: metadata.theme,
        style: metadata.style,
        aspect_ratio: metadata.aspectRatio || '1:1',
        model_used: metadata.modelUsed,
        is_personalized: metadata.isPersonalized || false,
        generation_params: metadata.generationParams || {},
        status: 'generated'
      })
      .select('id')
      .single();

    if (error) {
      console.error('[saveImageMetadata] Database error:', error);
      return { success: false, error: error.message };
    }

    console.log('[saveImageMetadata] Image saved with ID:', data.id);
    return { success: true, imageId: data.id };

  } catch (error: any) {
    console.error('[saveImageMetadata] Exception:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Upload completo: salva no Storage e registra metadados
 */
export async function uploadAndSaveImage(
  base64Image: string,
  metadata: SaveImageMetadata
): Promise<{
  success: boolean;
  imageId?: string;
  publicUrl?: string;
  storagePath?: string;
  error?: string;
}> {
  console.log('[uploadAndSaveImage] Starting upload for user:', metadata.userId);

  // 1. Upload para o Storage
  const uploadResult = await uploadImageToStorage(
    base64Image,
    metadata.userId,
    metadata.postId
  );

  if (!uploadResult.success || !uploadResult.publicUrl || !uploadResult.storagePath) {
    return { success: false, error: uploadResult.error || 'Upload failed' };
  }

  // 2. Salvar metadados no banco
  const saveResult = await saveImageMetadata({
    ...metadata,
    storagePath: uploadResult.storagePath,
    publicUrl: uploadResult.publicUrl
  });

  if (!saveResult.success) {
    // Se falhou ao salvar metadados, tenta deletar a imagem do storage
    console.log('[uploadAndSaveImage] Failed to save metadata, cleaning up storage...');
    const supabase = await createClient();
    await supabase.storage.from(BUCKET_NAME).remove([uploadResult.storagePath]);
    return { success: false, error: saveResult.error };
  }

  console.log('[uploadAndSaveImage] Complete! Image ID:', saveResult.imageId);

  return {
    success: true,
    imageId: saveResult.imageId,
    publicUrl: uploadResult.publicUrl,
    storagePath: uploadResult.storagePath
  };
}

/**
 * Atualiza o post com a referência da imagem
 */
export async function linkImageToPost(
  postId: string,
  imageId: string,
  publicUrl: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const supabase = await createClient();

    const { error } = await supabase
      .from('posts')
      .update({
        generated_image_id: imageId,
        generated_image_url: publicUrl,
        image_generated_at: new Date().toISOString()
      })
      .eq('id', postId);

    if (error) {
      console.error('[linkImageToPost] Error:', error);
      return { success: false, error: error.message };
    }

    console.log('[linkImageToPost] Linked image', imageId, 'to post', postId);
    return { success: true };

  } catch (error: any) {
    console.error('[linkImageToPost] Exception:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Busca histórico de imagens do usuário
 */
export async function getUserImageHistory(
  userId: string,
  options?: {
    limit?: number;
    offset?: number;
    theme?: string;
    status?: string;
  }
): Promise<{ images: any[]; total: number; error?: string }> {
  try {
    const supabase = await createClient();
    const limit = options?.limit || 20;
    const offset = options?.offset || 0;

    let query = supabase
      .from('generated_images')
      .select('*', { count: 'exact' })
      .eq('user_id', userId)
      .order('created_at', { ascending: false })
      .range(offset, offset + limit - 1);

    if (options?.theme) {
      query = query.eq('theme', options.theme);
    }

    if (options?.status) {
      query = query.eq('status', options.status);
    }

    const { data, count, error } = await query;

    if (error) {
      console.error('[getUserImageHistory] Error:', error);
      return { images: [], total: 0, error: error.message };
    }

    return { images: data || [], total: count || 0 };

  } catch (error: any) {
    console.error('[getUserImageHistory] Exception:', error);
    return { images: [], total: 0, error: error.message };
  }
}

/**
 * Deleta uma imagem (Storage + Database)
 */
export async function deleteImage(
  imageId: string,
  userId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const supabase = await createClient();

    // Buscar a imagem para pegar o storage_path
    const { data: image, error: fetchError } = await supabase
      .from('generated_images')
      .select('storage_path')
      .eq('id', imageId)
      .eq('user_id', userId)
      .single();

    if (fetchError || !image) {
      return { success: false, error: 'Image not found' };
    }

    // Deletar do Storage
    const { error: storageError } = await supabase.storage
      .from(BUCKET_NAME)
      .remove([image.storage_path]);

    if (storageError) {
      console.error('[deleteImage] Storage error:', storageError);
      // Continua mesmo se falhar no storage
    }

    // Deletar do Database
    const { error: dbError } = await supabase
      .from('generated_images')
      .delete()
      .eq('id', imageId)
      .eq('user_id', userId);

    if (dbError) {
      return { success: false, error: dbError.message };
    }

    console.log('[deleteImage] Deleted image:', imageId);
    return { success: true };

  } catch (error: any) {
    console.error('[deleteImage] Exception:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Atualiza métricas de performance de uma imagem
 */
export async function updateImagePerformance(
  imageId: string,
  metrics: {
    likes?: number;
    comments?: number;
    shares?: number;
    views?: number;
  }
): Promise<{ success: boolean; error?: string }> {
  try {
    const supabase = await createClient();

    const { error } = await supabase
      .from('generated_images')
      .update({
        performance_metrics: metrics,
        updated_at: new Date().toISOString()
      })
      .eq('id', imageId);

    if (error) {
      return { success: false, error: error.message };
    }

    return { success: true };

  } catch (error: any) {
    return { success: false, error: error.message };
  }
}
