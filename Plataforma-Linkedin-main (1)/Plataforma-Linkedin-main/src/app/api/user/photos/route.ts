import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { analyzeUserPhoto } from '@/lib/posts/postGeneration';
import { checkRateLimit, checkApiRateLimit } from '@/lib/rateLimit';
import { optimizeUserPhoto } from '@/lib/imageOptimization';

export const dynamic = 'force-dynamic';

export async function POST(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  // Check API rate limit (abuse prevention)
  const apiLimit = checkApiRateLimit(user.id);
  if (!apiLimit.allowed) {
    return NextResponse.json(
      { error: `Too many requests. Retry after ${apiLimit.retryAfter} seconds.` },
      { status: 429 }
    );
  }

  // Check usage rate limit (plan limits for photos)
  const rateLimit = await checkRateLimit(user.id, 'photo');
  if (!rateLimit.allowed) {
    return NextResponse.json(
      {
        error: rateLimit.reason,
        usage: rateLimit.usage,
        limits: rateLimit.limits,
      },
      { status: 429 }
    );
  }

  try {
    const formData = await request.formData();
    const files = formData.getAll('photos') as File[];
    const setAsPrimary = formData.get('setAsPrimary') === 'true';
    const analyzeImmediately = formData.get('analyzeImmediately') !== 'false';

    if (!files || files.length === 0) {
      return NextResponse.json({ error: 'Nenhuma foto enviada' }, { status: 400 });
    }

    console.log('[upload-photos] Uploading', files.length, 'photos for user', user.id);

    // Check current photo count using plan limits
    const maxPhotos = rateLimit.limits?.maxPhotos || 10;
    const currentPhotos = rateLimit.usage?.photosCount || 0;

    if (currentPhotos + files.length > maxPhotos) {
      return NextResponse.json(
        { error: `Limite de ${maxPhotos} fotos atingido. Atual: ${currentPhotos}` },
        { status: 400 }
      );
    }

    const uploadedPhotos = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      // Validate file
      if (!file.type.startsWith('image/')) {
        console.log('[upload-photos] Skipping non-image file:', file.name);
        continue;
      }

      if (file.size > 5 * 1024 * 1024) {
        console.log('[upload-photos] Skipping large file:', file.name, file.size);
        continue;
      }

      // Generate unique filename
      const timestamp = Date.now();
      const filename = `${timestamp}-${i}.webp`; // Always save as WebP after optimization
      const storagePath = `${user.id}/${filename}`;

      // Optimize the image before upload (resize to 1024px max, convert to WebP)
      const fileBuffer = await file.arrayBuffer();
      const optimized = await optimizeUserPhoto(fileBuffer);
      console.log('[upload-photos] Optimized:', Math.round(optimized.originalSize / 1024), 'KB →', Math.round(optimized.optimizedSize / 1024), 'KB');

      // Upload optimized image to Supabase Storage
      const { data: uploadData, error: uploadError } = await supabase.storage
        .from('user-photos')
        .upload(storagePath, optimized.buffer, {
          contentType: optimized.mimeType,
          upsert: false,
        });

      if (uploadError) {
        console.error('[upload-photos] Upload error:', uploadError);
        continue;
      }

      // Get public URL
      const { data: urlData } = supabase.storage
        .from('user-photos')
        .getPublicUrl(storagePath);

      const publicUrl = urlData.publicUrl;

      // If this is the first photo or setAsPrimary, make it primary
      const isPrimary = setAsPrimary && i === 0;

      // If setting as primary, unset current primary
      if (isPrimary) {
        await supabase
          .from('user_photos')
          .update({ is_primary: false })
          .eq('user_id', user.id);
      }

      // Analyze photo for appearance description if requested
      let appearanceDescription = '';
      if (analyzeImmediately) {
        console.log('[upload-photos] Analyzing photo for appearance...');
        appearanceDescription = await analyzeUserPhoto(publicUrl);
      }

      // Save to database
      const { data: photoRecord, error: dbError } = await supabase
        .from('user_photos')
        .insert({
          user_id: user.id,
          storage_path: storagePath,
          public_url: publicUrl,
          original_filename: file.name,
          file_size: optimized.optimizedSize, // Store optimized size
          mime_type: optimized.mimeType,
          width: optimized.width,
          height: optimized.height,
          is_primary: isPrimary,
          metadata: {
            uploaded_at: new Date().toISOString(),
            appearance_description: appearanceDescription || undefined,
            original_size: optimized.originalSize,
            compression_ratio: optimized.compressionRatio,
          },
        })
        .select()
        .single();

      if (dbError) {
        console.error('[upload-photos] DB error:', dbError);
        // Try to delete uploaded file
        await supabase.storage.from('user-photos').remove([storagePath]);
        continue;
      }

      uploadedPhotos.push(photoRecord);
      console.log('[upload-photos] ✅ Uploaded:', filename);
    }

    if (uploadedPhotos.length === 0) {
      return NextResponse.json(
        { error: 'Nenhuma foto foi enviada com sucesso' },
        { status: 400 }
      );
    }

    // Update user_agents photo count
    await supabase
      .from('user_agents')
      .update({
        photos_uploaded_count: currentPhotos + uploadedPhotos.length,
        updated_at: new Date().toISOString(),
      })
      .eq('user_id', user.id);

    console.log('[upload-photos] ✅ Successfully uploaded', uploadedPhotos.length, 'photos');

    return NextResponse.json({
      success: true,
      photos: uploadedPhotos,
      message: `${uploadedPhotos.length} foto(s) enviada(s) com sucesso!`,
      totalPhotos: currentPhotos + uploadedPhotos.length,
    });

  } catch (error: any) {
    console.error('[upload-photos] Error:', error);
    return NextResponse.json(
      { error: error.message || 'Falha ao enviar fotos' },
      { status: 500 }
    );
  }
}

// GET - List user's photos
export async function GET(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { data: photos, error } = await supabase
    .from('user_photos')
    .select('*')
    .eq('user_id', user.id)
    .order('is_primary', { ascending: false })
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ photos });
}

// DELETE - Remove a photo
export async function DELETE(request: NextRequest) {
  const supabase = await createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const photoId = searchParams.get('id');

  if (!photoId) {
    return NextResponse.json({ error: 'Photo ID required' }, { status: 400 });
  }

  // Get photo info
  const { data: photo, error: fetchError } = await supabase
    .from('user_photos')
    .select('*')
    .eq('id', photoId)
    .eq('user_id', user.id)
    .single();

  if (fetchError || !photo) {
    return NextResponse.json({ error: 'Foto não encontrada' }, { status: 404 });
  }

  // Delete from storage
  if (photo.storage_path) {
    await supabase.storage.from('user-photos').remove([photo.storage_path]);
  }

  // Delete from database
  const { error: deleteError } = await supabase
    .from('user_photos')
    .delete()
    .eq('id', photoId);

  if (deleteError) {
    return NextResponse.json({ error: deleteError.message }, { status: 500 });
  }

  // Update photo count
  const { count } = await supabase
    .from('user_photos')
    .select('*', { count: 'exact', head: true })
    .eq('user_id', user.id);

  await supabase
    .from('user_agents')
    .update({
      photos_uploaded_count: count || 0,
      updated_at: new Date().toISOString(),
    })
    .eq('user_id', user.id);

  return NextResponse.json({ success: true, message: 'Foto removida' });
}
