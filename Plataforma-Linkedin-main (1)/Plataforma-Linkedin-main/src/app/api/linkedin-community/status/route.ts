import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * GET /api/linkedin-community/status
 * Check if the user has connected the LinkedIn Community Management app
 */
export async function GET() {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        // Check if user has community tokens
        const { data: tokens, error } = await supabase
            .from('linkedin_community_tokens')
            .select('expires_at, scopes, linkedin_user_id')
            .eq('user_id', user.id)
            .single();

        if (error || !tokens) {
            return NextResponse.json({
                connected: false,
                message: 'Conecte sua conta LinkedIn para ver analytics e comentários',
            });
        }

        // Check if token is expired
        const isExpired = new Date(tokens.expires_at) < new Date();

        if (isExpired) {
            return NextResponse.json({
                connected: false,
                expired: true,
                message: 'Seu token expirou. Reconecte para continuar usando analytics.',
            });
        }

        return NextResponse.json({
            connected: true,
            scopes: tokens.scopes,
            linkedinUserId: tokens.linkedin_user_id,
        });

    } catch (error: any) {
        console.error('[LinkedIn Community Status] Error:', error);
        return NextResponse.json(
            { error: error.message || 'Internal error' },
            { status: 500 }
        );
    }
}
