import { NextRequest, NextResponse } from 'next/server';
import { createClient as createAdminClient } from '@supabase/supabase-js';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * GET /api/linkedin-community/callback
 * Handle OAuth callback for the LinkedIn Community Management app
 */
export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');

    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || request.nextUrl.origin;

    // Verificar erro retornado pelo LinkedIn
    if (error) {
        console.error('[LinkedIn Community Callback] Error from LinkedIn:', error, errorDescription);
        return NextResponse.redirect(`${baseUrl}/analytics?error=linkedin_${error}`);
    }

    // Verificar state para proteção CSRF
    const savedState = request.cookies.get('linkedin_community_state')?.value;
    if (!state || state !== savedState) {
        console.error('[LinkedIn Community Callback] State mismatch');
        return NextResponse.redirect(`${baseUrl}/analytics?error=invalid_state`);
    }

    if (!code) {
        console.error('[LinkedIn Community Callback] No authorization code received');
        return NextResponse.redirect(`${baseUrl}/analytics?error=no_code`);
    }

    try {
        // Extract user ID from state
        const userId = state.split(':')[0];

        // Verify user is logged in
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user || user.id !== userId) {
            console.error('[LinkedIn Community Callback] User mismatch or not authenticated');
            return NextResponse.redirect(`${baseUrl}/analytics?error=user_mismatch`);
        }

        const clientId = process.env.LINKEDIN_COMMUNITY_CLIENT_ID;
        const clientSecret = process.env.LINKEDIN_COMMUNITY_CLIENT_SECRET;
        const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
        const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
        const redirectUri = process.env.LINKEDIN_COMMUNITY_REDIRECT_URI || `${baseUrl}/api/linkedin-community/callback`;

        if (!clientId || !clientSecret) {
            throw new Error('LinkedIn Community credentials not configured');
        }

        if (!supabaseUrl || !supabaseServiceKey) {
            throw new Error('Supabase credentials not configured');
        }

        console.log('[LinkedIn Community Callback] Exchanging code for access token...');

        // Exchange authorization code for access_token
        const tokenResponse = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                grant_type: 'authorization_code',
                code,
                client_id: clientId,
                client_secret: clientSecret,
                redirect_uri: redirectUri,
            }),
        });

        if (!tokenResponse.ok) {
            const errorText = await tokenResponse.text();
            console.error('[LinkedIn Community Callback] Token exchange failed:', tokenResponse.status, errorText);
            throw new Error('Failed to exchange code for token');
        }

        const tokenData = await tokenResponse.json();
        const accessToken = tokenData.access_token;
        const expiresIn = tokenData.expires_in || 5184000;
        const refreshToken = tokenData.refresh_token || null;
        const scopes = tokenData.scope?.split(' ') || [];

        console.log('[LinkedIn Community Callback] Access token received, expires_in:', expiresIn);

        // Note: We don't have identity scopes (openid, r_liteprofile, etc), so we can't call /me or /userinfo
        // The person_urn will be obtained from user_linkedin_auth table (from Supabase login) when needed
        // This is handled by the react/route.ts endpoint which already has fallback logic
        let linkedinUserId = '';
        console.log('[LinkedIn Community Callback] Skipping /me call (no identity scopes available)');

        const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();

        // Save tokens to database
        const supabaseAdmin = createAdminClient(supabaseUrl, supabaseServiceKey, {
            auth: {
                autoRefreshToken: false,
                persistSession: false,
            },
        });

        console.log('[LinkedIn Community Callback] Saving tokens for user:', user.id);

        // Check if existing record
        const { data: existing } = await supabaseAdmin
            .from('linkedin_community_tokens')
            .select('id')
            .eq('user_id', user.id)
            .single();

        const personUrn = linkedinUserId ? `urn:li:person:${linkedinUserId}` : null;

        const tokenRecord = {
            user_id: user.id,
            access_token: accessToken,
            refresh_token: refreshToken,
            expires_at: expiresAt,
            scopes,
            linkedin_user_id: linkedinUserId,
            person_urn: personUrn,
            updated_at: new Date().toISOString(),
        };

        console.log('[LinkedIn Community Callback] Person URN:', personUrn);

        let saveError: any = null;
        if (existing) {
            const { error } = await supabaseAdmin
                .from('linkedin_community_tokens')
                .update(tokenRecord)
                .eq('user_id', user.id);
            saveError = error;
        } else {
            const { error } = await supabaseAdmin
                .from('linkedin_community_tokens')
                .insert({
                    ...tokenRecord,
                    created_at: new Date().toISOString(),
                });
            saveError = error;
        }

        if (saveError) {
            console.error('[LinkedIn Community Callback] Failed to save tokens:', saveError);
            throw new Error('Failed to save tokens: ' + saveError.message);
        }

        console.log('[LinkedIn Community Callback] Tokens saved successfully!');

        // Redirect to analytics page
        const response = NextResponse.redirect(`${baseUrl}/analytics?connected=true`);
        response.cookies.delete('linkedin_community_state');

        return response;

    } catch (err: any) {
        console.error('[LinkedIn Community Callback] Error:', err);
        const response = NextResponse.redirect(`${baseUrl}/analytics?error=auth_failed&message=${encodeURIComponent(err.message)}`);
        response.cookies.delete('linkedin_community_state');
        return response;
    }
}
