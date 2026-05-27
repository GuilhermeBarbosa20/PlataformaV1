import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { DEFAULT_PROMPTS, getAllPromptTypes } from '@/lib/prompts/defaultPrompts';

export const dynamic = 'force-dynamic';

/**
 * GET /api/prompts
 * Get all prompts (merge user's custom with defaults)
 */
export async function GET(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        // Get user's custom prompts
        const { data: customPrompts } = await supabase
            .from('user_custom_prompts')
            .select('*')
            .eq('user_id', user.id);

        // Merge with defaults
        const allPromptTypes = getAllPromptTypes();
        const prompts = allPromptTypes.map(defaultPrompt => {
            const custom = customPrompts?.find(cp => cp.prompt_type === defaultPrompt.type);
            return {
                type: defaultPrompt.type,
                name: defaultPrompt.name,
                description: defaultPrompt.description,
                variables: defaultPrompt.variables,
                default_content: defaultPrompt.content,
                custom_content: custom?.prompt_content || null,
                is_customized: !!custom,
                is_active: custom?.is_active ?? true,
                updated_at: custom?.updated_at || null,
            };
        });

        return NextResponse.json({
            success: true,
            prompts,
        });

    } catch (error: any) {
        console.error('[PROMPTS API] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}

/**
 * POST /api/prompts
 * Create or update a custom prompt
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { prompt_type, prompt_content } = body;

        if (!prompt_type || !prompt_content) {
            return NextResponse.json({
                error: 'prompt_type e prompt_content são obrigatórios'
            }, { status: 400 });
        }

        // Validate prompt type
        if (!DEFAULT_PROMPTS[prompt_type]) {
            return NextResponse.json({
                error: 'Tipo de prompt inválido'
            }, { status: 400 });
        }

        // Upsert custom prompt
        const { data, error } = await supabase
            .from('user_custom_prompts')
            .upsert({
                user_id: user.id,
                prompt_type,
                prompt_content,
                is_active: true,
                updated_at: new Date().toISOString(),
            }, {
                onConflict: 'user_id,prompt_type',
            })
            .select()
            .single();

        if (error) {
            console.error('[PROMPTS API] Error saving prompt:', error);
            return NextResponse.json({ error: 'Falha ao guardar prompt' }, { status: 500 });
        }

        return NextResponse.json({
            success: true,
            message: 'Prompt guardado com sucesso',
            prompt: data,
        });

    } catch (error: any) {
        console.error('[PROMPTS API] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}

/**
 * DELETE /api/prompts?type=prompt_type
 * Reset prompt to default (delete custom)
 */
export async function DELETE(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { searchParams } = new URL(request.url);
        const promptType = searchParams.get('type');

        if (!promptType) {
            return NextResponse.json({
                error: 'Parâmetro type é obrigatório'
            }, { status: 400 });
        }

        // Delete custom prompt
        const { error } = await supabase
            .from('user_custom_prompts')
            .delete()
            .eq('user_id', user.id)
            .eq('prompt_type', promptType);

        if (error) {
            console.error('[PROMPTS API] Error deleting prompt:', error);
            return NextResponse.json({ error: 'Falha ao repor prompt' }, { status: 500 });
        }

        return NextResponse.json({
            success: true,
            message: 'Prompt reposto para o padrão',
        });

    } catch (error: any) {
        console.error('[PROMPTS API] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}
