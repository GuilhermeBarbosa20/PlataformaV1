import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * GET /api/linkedin-community/auth
 * Start OAuth flow for the LinkedIn Community Management app
 * This is for analytics, comments, SSI features
 */
export async function GET(request: Request) {
    try {
        // Check if user is logged in
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || new URL(request.url).origin;
            return NextResponse.redirect(`${baseUrl}/?error=not_authenticated`);
        }

        const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || new URL(request.url).origin;
        const clientId = process.env.LINKEDIN_COMMUNITY_CLIENT_ID;
        const redirectUri = process.env.LINKEDIN_COMMUNITY_REDIRECT_URI || `${baseUrl}/api/linkedin-community/callback`;
        // Scopes for Community Management API:
        // - w_member_social_feed: Post/comment/react on member posts
        // - w_member_social: Legacy scope for reactions
        // - r_member_postAnalytics: Access post analytics
        // - r_1st_connections_size: Access connection count (SSI)
        // - w_organization_social_feed: React on organization posts (if applicable)
        // - r_organization_social_feed: Read organization posts (if applicable)
        // Adding more scopes to ensure reactions work with Community Management API
        const scopes = 'w_member_social_feed w_member_social r_member_postAnalytics r_1st_connections_size w_organization_social_feed r_organization_social_feed';

        if (!clientId) {
            console.error('[LinkedIn Community] LINKEDIN_COMMUNITY_CLIENT_ID not configured');
            return NextResponse.redirect(`${baseUrl}/analytics?error=community_not_configured`);
        }

        // State para proteção CSRF - include user ID
        const state = `${user.id}:${crypto.randomUUID()}`;

        // Construir URL de autorização do LinkedIn
        const authUrl = new URL('https://www.linkedin.com/oauth/v2/authorization');
        authUrl.searchParams.set('response_type', 'code');
        authUrl.searchParams.set('client_id', clientId);
        authUrl.searchParams.set('redirect_uri', redirectUri);
        authUrl.searchParams.set('state', state);
        authUrl.searchParams.set('scope', scopes);

        console.log('[LinkedIn Community] Redirecting to LinkedIn OAuth...');
        console.log('[LinkedIn Community] Redirect URI:', redirectUri);
        console.log('[LinkedIn Community] Scopes:', scopes);

        // Salvar state em cookie para validação no callback
        const response = NextResponse.redirect(authUrl.toString());
        response.cookies.set('linkedin_community_state', state, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            maxAge: 600, // 10 minutos
            path: '/',
        });

        return response;
    } catch (error: any) {
        console.error('[LinkedIn Community Auth] Error:', error);
        const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || new URL(request.url).origin;
        return NextResponse.redirect(`${baseUrl}/analytics?error=auth_failed`);
    }
}

/**
 * DELETE /api/linkedin-community/auth
 * Disconnect the LinkedIn Community Management app
 */
export async function DELETE(request: Request) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        // Remove tokens from database
        const { error } = await supabase
            .from('linkedin_community_tokens')
            .delete()
            .eq('user_id', user.id);

        if (error) {
            console.error('[LinkedIn Community] Failed to disconnect:', error);
            return NextResponse.json(
                { error: 'Failed to disconnect account' },
                { status: 500 }
            );
        }

        return NextResponse.json({ success: true });
    } catch (error: any) {
        console.error('[LinkedIn Community] Error disconnecting:', error);
        return NextResponse.json(
            { error: error.message || 'Internal error' },
            { status: 500 }
        );
    }
}
