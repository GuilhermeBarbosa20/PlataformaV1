import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import {
    getPostComments,
    postComment,
    getPostSocialActions,
} from '@/lib/linkedin-api';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY!;

/**
 * GET /api/linkedin/comments
 * 
 * Fetches comments for a LinkedIn post using the official LinkedIn API.
 * 
 * Query params:
 * - post_urn: The LinkedIn post URN (e.g., "urn:li:share:xxx")
 */
export async function GET(request: NextRequest) {
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

        // First try community tokens (has w_member_social_feed scope for comments)
        const { data: communityData, error: communityError } = await supabase
            .from('linkedin_community_tokens')
            .select('access_token')
            .eq('user_id', user.id)
            .single();

        if (!communityError && communityData?.access_token) {
            console.log('[LinkedIn Comments] Using community token');
            return await fetchCommentsWithToken(request, communityData.access_token);
        }

        // Fallback to regular LinkedIn tokens (user_linkedin_auth)
        const { data: linkedinData, error: linkedinError } = await supabase
            .from('user_linkedin_auth')
            .select('linkedin_access_token, linkedin_person_urn')
            .eq('user_id', user.id)
            .single();

        if (linkedinError || !linkedinData?.linkedin_access_token) {
            return NextResponse.json({
                connected: false,
                error: 'LinkedIn Community não conectado. Clique em "Conectar Analytics Avançado" para habilitar comentários.',
                needsConnection: true,
            }, { status: 404 });
        }

        return await fetchCommentsWithToken(request, linkedinData.linkedin_access_token);

    } catch (error) {
        console.error('[LinkedIn Comments] Error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch comments' },
            { status: 500 }
        );
    }
}

async function fetchCommentsWithToken(request: NextRequest, accessToken: string) {
    const { searchParams } = new URL(request.url);
    const postUrn = searchParams.get('post_urn');

    if (!postUrn) {
        return NextResponse.json(
            { error: 'post_urn is required' },
            { status: 400 }
        );
    }

    console.log('[LinkedIn Comments API] Fetching comments for:', postUrn);

    // Note: LinkedIn API socialActions endpoint for reading comments 
    // is only available for organization/company pages, not personal profiles.
    // For personal profiles, we return an informative message.

    try {
        // Try to get comments using the API
        const comments = await getPostComments(accessToken, postUrn);
        const socialActions = await getPostSocialActions(accessToken, postUrn);

        return NextResponse.json({
            connected: true,
            comments,
            socialActions,
            postUrn,
        });
    } catch (error: any) {
        console.log('[LinkedIn Comments API] API not available for personal posts:', error?.message);

        // Return empty comments with informational message
        return NextResponse.json({
            connected: true,
            comments: [],
            socialActions: null,
            postUrn,
            info: 'A API oficial do LinkedIn não disponibiliza leitura de comentários para perfis pessoais. Esta funcionalidade está disponível apenas para páginas de empresas.',
        });
    }
}

/**
 * POST /api/linkedin/comments
 * 
 * Post a comment on a LinkedIn post using the official API.
 * 
 * Body:
 * - post_urn: The LinkedIn post URN
 * - text: The comment text
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

        // Get LinkedIn tokens from user_linkedin_auth
        const { data: linkedinData, error: linkedinError } = await supabase
            .from('user_linkedin_auth')
            .select('linkedin_access_token, linkedin_person_urn')
            .eq('user_id', user.id)
            .single();

        if (linkedinError || !linkedinData?.linkedin_access_token || !linkedinData?.linkedin_person_urn) {
            return NextResponse.json({
                error: 'LinkedIn não conectado adequadamente. Por favor, reconecte sua conta.',
            }, { status: 404 });
        }

        const body = await request.json();
        const { post_urn, text } = body;

        if (!text) {
            return NextResponse.json(
                { error: 'text is required' },
                { status: 400 }
            );
        }

        if (!post_urn) {
            return NextResponse.json(
                { error: 'post_urn is required' },
                { status: 400 }
            );
        }

        console.log('[LinkedIn Comments API] Posting comment on:', post_urn);

        const result = await postComment(
            linkedinData.linkedin_access_token,
            linkedinData.linkedin_person_urn,
            post_urn,
            text
        );

        if (!result.success) {
            return NextResponse.json(
                { error: result.error || 'Failed to post comment' },
                { status: 400 }
            );
        }

        return NextResponse.json({
            success: true,
            message: 'Comentário enviado com sucesso!',
        });

    } catch (error) {
        console.error('[LinkedIn Comments] Error posting:', error);
        return NextResponse.json(
            { error: 'Failed to post comment' },
            { status: 500 }
        );
    }
}
