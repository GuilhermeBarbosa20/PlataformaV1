import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

interface UserSettings {
    news_posts_enabled: boolean;
    auto_like_on_reply: boolean;
    trends_monitoring_enabled: boolean;
    prompts_customization_enabled: boolean;
    reference_images_enabled: boolean;
}

const DEFAULT_SETTINGS: UserSettings = {
    news_posts_enabled: false,
    auto_like_on_reply: false,
    trends_monitoring_enabled: false,
    prompts_customization_enabled: false,
    reference_images_enabled: true, // Enabled by default for identity preservation
};

/**
 * GET /api/settings
 * Fetch user settings
 */
export async function GET(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        // Fetch settings from database
        const { data: settings, error } = await supabase
            .from('user_settings')
            .select('*')
            .eq('user_id', user.id)
            .single();

        if (error && error.code !== 'PGRST116') {
            // PGRST116 = no rows returned (new user, no settings yet)
            console.error('[Settings] Error fetching settings:', error);
            return NextResponse.json(
                { error: 'Failed to fetch settings' },
                { status: 500 }
            );
        }

        // Return settings or defaults
        return NextResponse.json({
            success: true,
            settings: settings ? {
                news_posts_enabled: settings.news_posts_enabled ?? DEFAULT_SETTINGS.news_posts_enabled,
                auto_like_on_reply: settings.auto_like_on_reply ?? DEFAULT_SETTINGS.auto_like_on_reply,
                trends_monitoring_enabled: settings.trends_monitoring_enabled ?? DEFAULT_SETTINGS.trends_monitoring_enabled,
                prompts_customization_enabled: settings.prompts_customization_enabled ?? DEFAULT_SETTINGS.prompts_customization_enabled,
                reference_images_enabled: settings.reference_images_enabled ?? DEFAULT_SETTINGS.reference_images_enabled,
            } : DEFAULT_SETTINGS,
        });

    } catch (error) {
        console.error('[Settings] Error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch settings' },
            { status: 500 }
        );
    }
}

/**
 * POST /api/settings
 * Update user settings
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        const body = await request.json();
        const updates: Partial<UserSettings> = {};

        // Only update fields that are provided
        if (typeof body.news_posts_enabled === 'boolean') {
            updates.news_posts_enabled = body.news_posts_enabled;
        }
        if (typeof body.auto_like_on_reply === 'boolean') {
            updates.auto_like_on_reply = body.auto_like_on_reply;
        }
        if (typeof body.trends_monitoring_enabled === 'boolean') {
            updates.trends_monitoring_enabled = body.trends_monitoring_enabled;
        }
        if (typeof body.prompts_customization_enabled === 'boolean') {
            updates.prompts_customization_enabled = body.prompts_customization_enabled;
        }
        if (typeof body.reference_images_enabled === 'boolean') {
            updates.reference_images_enabled = body.reference_images_enabled;
        }

        // Upsert settings
        const { data: settings, error } = await supabase
            .from('user_settings')
            .upsert({
                user_id: user.id,
                ...updates,
                updated_at: new Date().toISOString(),
            }, {
                onConflict: 'user_id',
            })
            .select()
            .single();

        if (error) {
            console.error('[Settings] Error updating settings:', error);
            return NextResponse.json(
                { error: 'Failed to update settings' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            settings: {
                news_posts_enabled: settings.news_posts_enabled,
                auto_like_on_reply: settings.auto_like_on_reply,
                trends_monitoring_enabled: settings.trends_monitoring_enabled,
                prompts_customization_enabled: settings.prompts_customization_enabled,
                reference_images_enabled: settings.reference_images_enabled,
            },
        });

    } catch (error) {
        console.error('[Settings] Error:', error);
        return NextResponse.json(
            { error: 'Failed to update settings' },
            { status: 500 }
        );
    }
}
