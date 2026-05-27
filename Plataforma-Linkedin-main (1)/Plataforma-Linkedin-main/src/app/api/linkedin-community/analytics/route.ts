import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';
import { getPostAnalytics } from '@/lib/linkedin-api';

export const dynamic = 'force-dynamic';

/**
 * GET /api/linkedin-community/analytics
 * Get post analytics using the Community Management app tokens
 */
export async function GET() {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        // Get community tokens
        const { data: tokens, error: tokensError } = await supabase
            .from('linkedin_community_tokens')
            .select('access_token, expires_at')
            .eq('user_id', user.id)
            .single();

        if (tokensError || !tokens) {
            return NextResponse.json(
                {
                    error: 'NOT_CONNECTED',
                    message: 'Conecte sua conta LinkedIn para ver analytics',
                    connectUrl: '/api/linkedin-community/auth',
                },
                { status: 403 }
            );
        }

        // Check if token is expired
        if (new Date(tokens.expires_at) < new Date()) {
            return NextResponse.json(
                {
                    error: 'TOKEN_EXPIRED',
                    message: 'Seu token expirou. Reconecte para continuar.',
                    connectUrl: '/api/linkedin-community/auth',
                },
                { status: 403 }
            );
        }

        // Fetch analytics from LinkedIn
        console.log('[Community Analytics] Fetching analytics...');
        const analytics = await getPostAnalytics(tokens.access_token);

        return NextResponse.json({
            success: true,
            analytics,
        });

    } catch (error: any) {
        console.error('[Community Analytics] Error:', error);
        return NextResponse.json(
            { error: error.message || 'Internal error' },
            { status: 500 }
        );
    }
}
