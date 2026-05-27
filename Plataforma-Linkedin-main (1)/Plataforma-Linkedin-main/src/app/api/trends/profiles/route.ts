import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

const MAX_PROFILES = 10;

// Validate LinkedIn profile URL
function isValidLinkedInProfileUrl(url: string): boolean {
    const patterns = [
        /^https?:\/\/(www\.)?linkedin\.com\/in\/[\w-]+\/?$/i,
        /^linkedin\.com\/in\/[\w-]+\/?$/i,
        /^[\w-]+$/, // Just the vanity name
    ];
    return patterns.some(pattern => pattern.test(url.trim()));
}

// Normalize URL to standard format
function normalizeProfileUrl(input: string): string {
    const trimmed = input.trim();

    // If it's just a vanity name
    if (/^[\w-]+$/.test(trimmed)) {
        return `https://www.linkedin.com/in/${trimmed}/`;
    }

    // If it starts with linkedin.com
    if (/^linkedin\.com/i.test(trimmed)) {
        return `https://www.${trimmed}`;
    }

    // Already a full URL
    let url = trimmed;
    if (!url.endsWith('/')) url += '/';
    return url;
}

// Extract vanity name from URL
function extractVanityName(url: string): string | null {
    const match = url.match(/linkedin\.com\/in\/([\w-]+)\/?/i);
    return match ? match[1] : null;
}

/**
 * GET /api/trends/profiles
 * List user's monitored profiles
 */
export async function GET(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { data: profiles, error } = await supabase
            .from('monitored_profiles')
            .select('*')
            .eq('user_id', user.id)
            .order('created_at', { ascending: false });

        if (error) {
            console.error('[Trends Profiles] Error fetching profiles:', error);
            return NextResponse.json({ error: 'Failed to fetch profiles' }, { status: 500 });
        }

        return NextResponse.json({
            success: true,
            profiles: profiles || [],
            count: profiles?.length || 0,
            max: MAX_PROFILES,
        });

    } catch (error) {
        console.error('[Trends Profiles] Error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

/**
 * POST /api/trends/profiles
 * Add a new monitored profile
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const body = await request.json();
        const { profile_url, profile_name } = body;

        if (!profile_url) {
            return NextResponse.json({ error: 'URL do perfil é obrigatória' }, { status: 400 });
        }

        if (!isValidLinkedInProfileUrl(profile_url)) {
            return NextResponse.json({
                error: 'URL inválida. Use o formato: linkedin.com/in/nome ou apenas o nome do perfil'
            }, { status: 400 });
        }

        // Check profile count limit
        const { count, error: countError } = await supabase
            .from('monitored_profiles')
            .select('*', { count: 'exact', head: true })
            .eq('user_id', user.id);

        if (countError) {
            console.error('[Trends Profiles] Error counting profiles:', countError);
            return NextResponse.json({ error: 'Failed to check profile limit' }, { status: 500 });
        }

        if ((count || 0) >= MAX_PROFILES) {
            return NextResponse.json({
                error: `Limite máximo de ${MAX_PROFILES} perfis atingido`
            }, { status: 400 });
        }

        const normalizedUrl = normalizeProfileUrl(profile_url);
        const vanityName = extractVanityName(normalizedUrl);

        // Insert new profile
        const { data: profile, error: insertError } = await supabase
            .from('monitored_profiles')
            .insert({
                user_id: user.id,
                profile_url: normalizedUrl,
                profile_name: profile_name || vanityName || 'Perfil LinkedIn',
                profile_vanity_name: vanityName,
            })
            .select()
            .single();

        if (insertError) {
            if (insertError.code === '23505') { // Unique violation
                return NextResponse.json({ error: 'Este perfil já está sendo monitorado' }, { status: 400 });
            }
            console.error('[Trends Profiles] Error inserting profile:', insertError);
            return NextResponse.json({ error: 'Failed to add profile' }, { status: 500 });
        }

        console.log('[Trends Profiles] Added profile:', profile.profile_url);

        return NextResponse.json({
            success: true,
            profile,
            message: 'Perfil adicionado com sucesso!',
        });

    } catch (error) {
        console.error('[Trends Profiles] Error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}

/**
 * DELETE /api/trends/profiles?id=xxx
 * Remove a monitored profile
 */
export async function DELETE(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const { searchParams } = new URL(request.url);
        const profileId = searchParams.get('id');

        if (!profileId) {
            return NextResponse.json({ error: 'Profile ID is required' }, { status: 400 });
        }

        // Delete the profile (cascade will delete related posts)
        const { error: deleteError } = await supabase
            .from('monitored_profiles')
            .delete()
            .eq('id', profileId)
            .eq('user_id', user.id);

        if (deleteError) {
            console.error('[Trends Profiles] Error deleting profile:', deleteError);
            return NextResponse.json({ error: 'Failed to delete profile' }, { status: 500 });
        }

        console.log('[Trends Profiles] Deleted profile:', profileId);

        return NextResponse.json({
            success: true,
            message: 'Perfil removido com sucesso!',
        });

    } catch (error) {
        console.error('[Trends Profiles] Error:', error);
        return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
    }
}
