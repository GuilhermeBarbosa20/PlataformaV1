'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/utils/supabase/client';

/**
 * Component that stores LinkedIn profile info after OAuth callback
 */
export default function LinkedInCookieCapture() {
  const [stored, setStored] = useState(false);

  useEffect(() => {
    const storeUserData = async () => {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user) {
          console.log('No user found');
          return;
        }

        // Store user's LinkedIn profile data from OAuth metadata
        const { error } = await supabase.from('user_linkedin_auth').upsert(
          {
            user_id: user.id,
            linkedin_profile_url: user.user_metadata?.profile_url || null,
            linkedin_profile_name: user.user_metadata?.full_name || user.email,
            linkedin_profile_photo: user.user_metadata?.picture || null,
            linkedin_li_at_cookie: 'pending', // Placeholder - will be updated when user accesses LinkedIn
            cookie_expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
          },
          { onConflict: 'user_id' }
        );

        if (error) {
          console.error('Failed to store user data:', error);
        } else {
          console.log('User data stored successfully');
          setStored(true);
        }
      } catch (error) {
        console.error('Error storing user data:', error);
      }
    };

    if (!stored) {
      storeUserData();
    }
  }, [stored]);

  return null;
}
