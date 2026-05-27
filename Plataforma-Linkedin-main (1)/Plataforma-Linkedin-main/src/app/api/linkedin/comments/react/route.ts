import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { likeComment, unlikeComment } from '@/lib/linkedin-api';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

/**
 * POST /api/linkedin/comments/react
 * 
 * Like or unlike a comment using the LinkedIn Reactions API v202505
 * 
 * Body:
 * - comment_urn: The LinkedIn comment URN
 * - action: 'like' or 'unlike'
 */
export async function POST(request: NextRequest) {
    try {
        const authHeader = request.headers.get('authorization');
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return NextResponse.json(
                { error: 'Missing or invalid authorization header' },
                { status: 401 }
            );
        }

        const token = authHeader.replace('Bearer ', '');
        const supabase = createClient(supabaseUrl, supabaseServiceKey);
        const { data: { user }, error: authError } = await supabase.auth.getUser(token);

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Invalid or expired token' },
                { status: 401 }
            );
        }

        const body = await request.json();
        const { comment_urn, action } = body;

        if (!comment_urn) {
            return NextResponse.json(
                { error: 'comment_urn is required' },
                { status: 400 }
            );
        }

        if (!action || !['like', 'unlike'].includes(action)) {
            return NextResponse.json(
                { error: 'action must be "like" or "unlike"' },
                { status: 400 }
            );
        }

        console.log('[LinkedIn Reactions API] Checking tokens for User UUID:', user.id);
        console.log('[LinkedIn Reactions API] User Email:', user.email);

        // First try community tokens (has w_member_social_feed scope)
        // Select ONLY access_token and linkedin_user_id because person_urn might be missing in the table schema
        const { data: communityData, error: communityError } = await supabase
            .from('linkedin_community_tokens')
            .select('access_token, linkedin_user_id')
            .eq('user_id', user.id)
            .single();

        if (communityError) {
            console.log('[LinkedIn Reactions API] Community token check error/not found:', communityError.message);
        }

        // Use user_linkedin_auth instead of linkedin_tokens (which doesn't exist)
        const { data: linkedinData, error: linkedinError } = await supabase
            .from('user_linkedin_auth')
            .select('linkedin_access_token, linkedin_person_urn')
            .eq('user_id', user.id)
            .single();

        if (linkedinError) {
            console.log('[LinkedIn Reactions API] LinkedIn token check error/not found:', linkedinError.message);
        }

        let accessToken: string | null = null;
        let personUrn: string | null = linkedinData?.linkedin_person_urn || null;

        // Try to get person_urn from any available ID if it's missing
        if (!personUrn) {
            // Priority 1: From community tokens
            let userId = communityData?.linkedin_user_id;

            // Priority 2: From user metadata (the LinkedIn login saves this)
            if (!userId && user.user_metadata?.linkedin_id) {
                userId = user.user_metadata.linkedin_id;
                console.log('[LinkedIn Reactions API] Using userId from user_metadata:', userId);
            }

            // Priority 3: From user identity data if available
            if (!userId && user.identities) {
                const linkedInIdentity = (user.identities as any[]).find(id => id.provider === 'linkedin_oidc' || id.provider === 'linkedin');
                if (linkedInIdentity) {
                    userId = linkedInIdentity.id;
                    console.log('[LinkedIn Reactions API] Using userId from identity:', userId);
                }
            }

            if (userId) {
                personUrn = userId.startsWith('urn:li:person:') ? userId : `urn:li:person:${userId}`;
                console.log('[LinkedIn Reactions API] Derived person_urn:', personUrn);
            }
        }

        console.log('[LinkedIn Reactions API] Final Person URN:', personUrn);

        // Prefer community token (has w_member_social_feed scope)
        if (communityData?.access_token) {
            accessToken = communityData.access_token;
            console.log('[LinkedIn Reactions API] Selected community access token');
        } else if (linkedinData?.linkedin_access_token) {
            accessToken = linkedinData.linkedin_access_token;
            console.log('[LinkedIn Reactions API] Selected regular LinkedIn access token');
        }

        // If no person_urn, try to get it from the LinkedIn API
        if (!personUrn && accessToken) {
            try {
                console.log('[LinkedIn Reactions API] Fetching person URN from API /v2/userinfo...');
                const userInfoResponse = await fetch('https://api.linkedin.com/v2/userinfo', {
                    headers: { 'Authorization': `Bearer ${accessToken}` },
                });
                if (userInfoResponse.ok) {
                    const userInfo = await userInfoResponse.json();
                    if (userInfo.sub) {
                        personUrn = `urn:li:person:${userInfo.sub}`;
                        console.log('[LinkedIn Reactions API] Got person URN from API:', personUrn);
                    }
                } else {
                    console.log('[LinkedIn Reactions API] API /v2/userinfo failed:', userInfoResponse.status);
                }
            } catch (e) {
                console.log('[LinkedIn Reactions API] Failed to fetch person URN from API:', e);
            }
        }

        if (!accessToken) {
            return NextResponse.json({
                error: 'LinkedIn não conectado. Por favor, conecte o "Analytics Avançado" na aba de Analytics.',
            }, { status: 404 });
        }

        if (!personUrn) {
            return NextResponse.json({
                error: 'Não foi possível identificar seu perfil do LinkedIn. Tente reconectar sua conta.',
            }, { status: 404 });
        }

        console.log('[LinkedIn Reactions API] Action:', action, 'on comment:', comment_urn);

        // Track errors for fallback
        let lastError = null;

        // Define tokens to try in order
        const tokensToTry = [];

        // 1. First try community token (it's supposed to have advanced scopes)
        if (communityData?.access_token) {
            tokensToTry.push({
                token: communityData.access_token,
                name: 'community'
            });
        }

        // 2. Then try main account token (might have w_member_social)
        if (linkedinData?.linkedin_access_token) {
            tokensToTry.push({
                token: linkedinData.linkedin_access_token,
                name: 'main_account'
            });
        }

        if (tokensToTry.length === 0) {
            return NextResponse.json({
                error: 'LinkedIn não conectado adequadamente. Por favor, conecte o "Analytics Avançado" na aba de Analytics.',
            }, { status: 404 });
        }

        for (const tokenInfo of tokensToTry) {
            console.log(`[LinkedIn Reactions API] Trying reaction with ${tokenInfo.name} token...`);

            let result;
            if (action === 'like') {
                result = await likeComment(tokenInfo.token, personUrn, comment_urn);
            } else {
                result = await unlikeComment(tokenInfo.token, personUrn, comment_urn);
            }

            if (result.success) {
                console.log(`[LinkedIn Reactions API] Success with ${tokenInfo.name} token!`);
                return NextResponse.json({
                    success: true,
                    message: action === 'like' ? 'Comentário curtido!' : 'Curtida removida!',
                    token_used: tokenInfo.name
                });
            }

            console.log(`[LinkedIn Reactions API] ${tokenInfo.name} token failed:`, result.error);
            lastError = result.error;

            // If error is not 403 or 401, maybe it's a structural error, don't fallback?
            // Actually, let's always try the other one if available.
        }

        return NextResponse.json(
            { error: 'Falha ao processar reação no LinkedIn', details: lastError },
            { status: 400 }
        );

    } catch (error: any) {
        console.error('[LinkedIn Reactions API] Error:', error);
        return NextResponse.json(
            { error: 'Erro ao processar reação', details: error.message },
            { status: 500 }
        );
    }
}
