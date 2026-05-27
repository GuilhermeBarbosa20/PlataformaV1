import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

interface RouteParams {
  params: { postId: string };
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Get post
    const { data: post, error: fetchError } = await supabase
      .from('posts')
      .select('*')
      .eq('id', params.postId)
      .eq('user_id', user.id)
      .single();

    if (fetchError || !post) {
      return NextResponse.json({ error: 'Post não encontrado' }, { status: 404 });
    }

    // Parse form data
    const formData = await request.formData();
    const file = formData.get('image') as File;

    if (!file) {
      return NextResponse.json({ error: 'Nenhuma imagem enviada' }, { status: 400 });
    }

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
    if (!allowedTypes.includes(file.type)) {
      return NextResponse.json(
        { error: 'Tipo de arquivo não permitido. Use JPEG, PNG, WebP ou GIF.' },
        { status: 400 }
      );
    }

    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      return NextResponse.json(
        { error: 'Arquivo muito grande. Máximo 10MB.' },
        { status: 400 }
      );
    }

    // Convert file to buffer
    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);

    // Upload to Supabase Storage
    const timestamp = Date.now();
    const extension = file.type.split('/')[1] || 'jpg';
    const fileName = `${user.id}/${params.postId}/${timestamp}.${extension}`;

    const { data: uploadData, error: uploadError } = await supabase.storage
      .from('post-images')
      .upload(fileName, buffer, {
        contentType: file.type,
        upsert: true,
      });

    if (uploadError) {
      console.error('Upload error:', uploadError);
      return NextResponse.json(
        { error: 'Falha ao fazer upload da imagem' },
        { status: 500 }
      );
    }

    // Get public URL
    const { data: urlData } = supabase.storage
      .from('post-images')
      .getPublicUrl(fileName);

    const publicUrl = urlData.publicUrl;

    // Update post with custom image URL
    const { data: updated, error: updateError } = await supabase
      .from('posts')
      .update({
        custom_image_url: publicUrl,
        generated_image_url: publicUrl, // Also set as main image
        image_generation_status: 'ready',
        updated_at: new Date().toISOString(),
      })
      .eq('id', params.postId)
      .select()
      .single();

    if (updateError) {
      console.error('Error updating post with custom image:', updateError);
      return NextResponse.json({ error: 'Falha ao salvar imagem' }, { status: 500 });
    }

    return NextResponse.json({
      success: true,
      post: updated,
      imageUrl: publicUrl,
      message: 'Imagem personalizada carregada com sucesso!',
    });
  } catch (error: any) {
    console.error('Upload custom image error:', error);
    return NextResponse.json(
      { error: error.message || 'Erro ao fazer upload da imagem' },
      { status: 500 }
    );
  }
}
