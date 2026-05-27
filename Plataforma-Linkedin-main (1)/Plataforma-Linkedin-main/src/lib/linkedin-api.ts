/**
 * LinkedIn API Service
 * Handles publishing posts to LinkedIn using the official API
 */

const LINKEDIN_API_BASE = 'https://api.linkedin.com/v2';
const LINKEDIN_REST_API_BASE = 'https://api.linkedin.com/rest';

export interface LinkedInAuthData {
  access_token: string;
  person_urn: string;
}

export interface PublishPostParams {
  text: string;
  imageUrl?: string | null;
  visibility?: 'PUBLIC' | 'CONNECTIONS';
}

export interface PublishResult {
  success: boolean;
  linkedinPostUrn?: string;
  error?: string;
}

/**
 * Get the LinkedIn Person URN for the authenticated user
 */
export async function getLinkedInPersonUrn(accessToken: string): Promise<string | null> {
  try {
    const response = await fetch(`${LINKEDIN_API_BASE}/userinfo`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      console.error('[LinkedIn] Failed to get userinfo:', response.status);
      return null;
    }

    const data = await response.json();
    // The 'sub' field contains the person ID
    if (data.sub) {
      return `urn:li:person:${data.sub}`;
    }

    return null;
  } catch (error) {
    console.error('[LinkedIn] Error getting person URN:', error);
    return null;
  }
}

/**
 * Register an image for upload to LinkedIn
 */
async function registerImageUpload(
  accessToken: string,
  personUrn: string
): Promise<{ uploadUrl: string; asset: string } | null> {
  try {
    const response = await fetch(`${LINKEDIN_API_BASE}/assets?action=registerUpload`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify({
        registerUploadRequest: {
          recipes: ['urn:li:digitalmediaRecipe:feedshare-image'],
          owner: personUrn,
          serviceRelationships: [
            {
              relationshipType: 'OWNER',
              identifier: 'urn:li:userGeneratedContent',
            },
          ],
        },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn] Failed to register image upload:', response.status, errorText);
      return null;
    }

    const data = await response.json();
    const uploadUrl = data.value?.uploadMechanism?.['com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest']?.uploadUrl;
    const asset = data.value?.asset;

    if (!uploadUrl || !asset) {
      console.error('[LinkedIn] Missing uploadUrl or asset in response');
      return null;
    }

    return { uploadUrl, asset };
  } catch (error) {
    console.error('[LinkedIn] Error registering image upload:', error);
    return null;
  }
}

/**
 * Upload an image to LinkedIn
 */
async function uploadImageToLinkedIn(
  uploadUrl: string,
  imageUrl: string,
  accessToken: string
): Promise<boolean> {
  try {
    // First, fetch the image from the URL
    const imageResponse = await fetch(imageUrl);
    if (!imageResponse.ok) {
      console.error('[LinkedIn] Failed to fetch image from URL:', imageUrl);
      return false;
    }

    const imageBuffer = await imageResponse.arrayBuffer();
    const contentType = imageResponse.headers.get('content-type') || 'image/png';

    // Upload to LinkedIn
    const uploadResponse = await fetch(uploadUrl, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': contentType,
      },
      body: imageBuffer,
    });

    if (!uploadResponse.ok && uploadResponse.status !== 201) {
      console.error('[LinkedIn] Failed to upload image:', uploadResponse.status);
      return false;
    }

    return true;
  } catch (error) {
    console.error('[LinkedIn] Error uploading image:', error);
    return false;
  }
}

/**
 * Create a text-only post on LinkedIn using UGC API
 */
async function createTextPost(
  accessToken: string,
  personUrn: string,
  text: string,
  visibility: 'PUBLIC' | 'CONNECTIONS'
): Promise<PublishResult> {
  try {
    const response = await fetch(`${LINKEDIN_API_BASE}/ugcPosts`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify({
        author: personUrn,
        lifecycleState: 'PUBLISHED',
        specificContent: {
          'com.linkedin.ugc.ShareContent': {
            shareCommentary: {
              text: text,
            },
            shareMediaCategory: 'NONE',
          },
        },
        visibility: {
          'com.linkedin.ugc.MemberNetworkVisibility': visibility,
        },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn] Failed to create text post:', response.status, errorText);
      return {
        success: false,
        error: `LinkedIn API error: ${response.status} - ${errorText}`,
      };
    }

    // Get the post URN from the X-RestLi-Id header
    const postUrn = response.headers.get('X-RestLi-Id') || response.headers.get('x-restli-id');

    return {
      success: true,
      linkedinPostUrn: postUrn || undefined,
    };
  } catch (error: any) {
    console.error('[LinkedIn] Error creating text post:', error);
    return {
      success: false,
      error: error.message || 'Unknown error creating post',
    };
  }
}

/**
 * Create a post with an image on LinkedIn using UGC API
 */
async function createImagePost(
  accessToken: string,
  personUrn: string,
  text: string,
  imageAsset: string,
  visibility: 'PUBLIC' | 'CONNECTIONS'
): Promise<PublishResult> {
  try {
    const response = await fetch(`${LINKEDIN_API_BASE}/ugcPosts`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify({
        author: personUrn,
        lifecycleState: 'PUBLISHED',
        specificContent: {
          'com.linkedin.ugc.ShareContent': {
            shareCommentary: {
              text: text,
            },
            shareMediaCategory: 'IMAGE',
            media: [
              {
                status: 'READY',
                media: imageAsset,
              },
            ],
          },
        },
        visibility: {
          'com.linkedin.ugc.MemberNetworkVisibility': visibility,
        },
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn] Failed to create image post:', response.status, errorText);
      return {
        success: false,
        error: `LinkedIn API error: ${response.status} - ${errorText}`,
      };
    }

    // Get the post URN from the X-RestLi-Id header
    const postUrn = response.headers.get('X-RestLi-Id') || response.headers.get('x-restli-id');

    return {
      success: true,
      linkedinPostUrn: postUrn || undefined,
    };
  } catch (error: any) {
    console.error('[LinkedIn] Error creating image post:', error);
    return {
      success: false,
      error: error.message || 'Unknown error creating post',
    };
  }
}

/**
 * Main function to publish a post to LinkedIn
 * Handles both text-only and image posts
 */
export async function publishToLinkedIn(
  auth: LinkedInAuthData,
  params: PublishPostParams
): Promise<PublishResult> {
  const { access_token, person_urn } = auth;
  const { text, imageUrl, visibility = 'PUBLIC' } = params;

  console.log('[LinkedIn] Starting publish process...');
  console.log('[LinkedIn] Has image:', !!imageUrl);
  console.log('[LinkedIn] Text length:', text.length);

  // If no image, create a simple text post
  if (!imageUrl) {
    console.log('[LinkedIn] Creating text-only post...');
    return createTextPost(access_token, person_urn, text, visibility);
  }

  // If we have an image, we need to:
  // 1. Register the upload
  // 2. Upload the image
  // 3. Create the post with the image asset

  console.log('[LinkedIn] Registering image upload...');
  const uploadRegistration = await registerImageUpload(access_token, person_urn);

  if (!uploadRegistration) {
    return {
      success: false,
      error: 'Failed to register image upload with LinkedIn',
    };
  }

  console.log('[LinkedIn] Uploading image to LinkedIn...');
  const uploadSuccess = await uploadImageToLinkedIn(
    uploadRegistration.uploadUrl,
    imageUrl,
    access_token
  );

  if (!uploadSuccess) {
    return {
      success: false,
      error: 'Failed to upload image to LinkedIn',
    };
  }

  console.log('[LinkedIn] Creating image post...');
  return createImagePost(
    access_token,
    person_urn,
    text,
    uploadRegistration.asset,
    visibility
  );
}

/**
 * Validate that we have the required LinkedIn credentials
 */
export function validateLinkedInAuth(auth: Partial<LinkedInAuthData>): auth is LinkedInAuthData {
  return !!(auth.access_token && auth.person_urn);
}

// ============================================
// Analytics Functions
// ============================================

export interface PostAnalytics {
  postUrn: string;
  impressionCount?: number;
  uniqueImpressionsCount?: number;
  clickCount?: number;
  likeCount?: number;
  commentCount?: number;
  shareCount?: number;
  engagementRate?: number;
}

/**
 * Get analytics for user's posts using LinkedIn's memberCreatorPostAnalytics API
 * Requires r_member_postAnalytics scope
 */
export async function getPostAnalytics(
  accessToken: string
): Promise<PostAnalytics[]> {
  try {
    console.log('[LinkedIn Analytics] Fetching post analytics...');

    const response = await fetch(
      `${LINKEDIN_REST_API_BASE}/memberCreatorPostAnalytics?q=me`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'LinkedIn-Version': '202412',
          'X-Restli-Protocol-Version': '2.0.0',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Analytics] Failed to get analytics:', response.status, errorText);
      return [];
    }

    const data = await response.json();
    console.log('[LinkedIn Analytics] Response:', JSON.stringify(data).substring(0, 500));

    // Transform the response to our format
    const elements = data.elements || [];
    return elements.map((element: any) => ({
      postUrn: element.post || element.entity,
      impressionCount: element.impressionCount,
      uniqueImpressionsCount: element.uniqueImpressionsCount,
      clickCount: element.clickCount,
      likeCount: element.likeCount,
      commentCount: element.commentCount,
      shareCount: element.shareCount,
      engagementRate: element.engagementRate,
    }));
  } catch (error) {
    console.error('[LinkedIn Analytics] Error:', error);
    return [];
  }
}

export async function getSinglePostAnalytics(
  accessToken: string,
  postUrn: string
): Promise<PostAnalytics | null> {
  try {
    console.log('[LinkedIn Analytics] Fetching analytics for post:', postUrn);

    // Fetch all posts analytics with q=me including required parameters
    // queryType: IMPRESSION (for impression counts)
    // aggregation: TOTAL (for lifetime stats, not daily breakdown)
    const response = await fetch(
      `${LINKEDIN_REST_API_BASE}/memberCreatorPostAnalytics?q=me&queryType=IMPRESSION&aggregation=TOTAL`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'LinkedIn-Version': '202505',
          'X-Restli-Protocol-Version': '2.0.0',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Analytics] Failed to get post analytics:', response.status, errorText);
      return null;
    }

    const data = await response.json();
    const elements = data.elements || [];

    // Find the specific post in the response
    // The 'post' field or 'entity' field should match our postUrn
    const targetElement = elements.find((element: any) => {
      const elementUrn = element.post || element.entity || '';
      // Also check for activity URN match (shares can have corresponding activities)
      return elementUrn === postUrn ||
        elementUrn.includes(postUrn.replace('urn:li:share:', '')) ||
        postUrn.includes(elementUrn.replace('urn:li:activity:', '').replace('urn:li:ugcPost:', ''));
    });

    if (!targetElement) {
      console.log('[LinkedIn Analytics] Post not found in analytics response, elements count:', elements.length);
      // Log first few elements for debugging
      if (elements.length > 0) {
        console.log('[LinkedIn Analytics] Sample elements:', elements.slice(0, 2).map((e: any) => e.post || e.entity));
      }
      return null;
    }

    console.log('[LinkedIn Analytics] Found analytics for post:', postUrn);
    return {
      postUrn: targetElement.post || targetElement.entity || postUrn,
      impressionCount: targetElement.impressionCount,
      uniqueImpressionsCount: targetElement.uniqueImpressionsCount,
      clickCount: targetElement.clickCount,
      likeCount: targetElement.likeCount,
      commentCount: targetElement.commentCount,
      shareCount: targetElement.shareCount,
      engagementRate: targetElement.engagementRate,
    };
  } catch (error) {
    console.error('[LinkedIn Analytics] Error:', error);
    return null;
  }
}

// ============================================
// Comments Functions - Official LinkedIn API
// ============================================

export interface LinkedInComment {
  id: string;
  text: string;
  author: {
    id: string;
    name: string;
    headline?: string;
    avatar_url?: string;
  };
  created_at: string;
  likes_count?: number;
  replies?: LinkedInComment[];
}

/**
 * Get comments for a LinkedIn post using the official API v202505
 * Uses the /rest/socialActions endpoint (Community Management API)
 * Requires w_member_social_feed or r_organization_social_feed scope
 */
export async function getPostComments(
  accessToken: string,
  postUrn: string
): Promise<LinkedInComment[]> {
  try {
    console.log('[LinkedIn Comments] Fetching comments for post:', postUrn);

    // Use the REST API base with LinkedIn-Version header
    const encodedUrn = encodeURIComponent(postUrn);
    const response = await fetch(
      `${LINKEDIN_REST_API_BASE}/socialActions/${encodedUrn}/comments`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'LinkedIn-Version': '202505',
          'X-Restli-Protocol-Version': '2.0.0',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Comments] Failed to get comments:', response.status, errorText);
      throw new Error(`API error: ${response.status} - ${errorText}`);
    }

    const data = await response.json();
    console.log('[LinkedIn Comments] Full Response:', JSON.stringify(data, null, 2).substring(0, 2000));

    const elements = data.elements || [];

    // Transform comments to our format and fetch author details
    const comments = await Promise.all(elements.map(async (comment: any) => {
      // Actor can be URN like "urn:li:person:abc123" or "urn:li:organization:123"
      const actorUrn = comment.actor || '';

      // Try to get author profile info
      let authorInfo = {
        id: actorUrn,
        name: 'LinkedIn User',
        headline: '',
        avatar_url: null as string | null,
      };

      // If we have an actor URN, try to fetch profile
      if (actorUrn && actorUrn.includes('urn:li:person:')) {
        try {
          const profile = await fetchMemberProfile(accessToken, actorUrn);
          if (profile) {
            authorInfo = {
              id: actorUrn,
              name: profile.name || 'LinkedIn User',
              headline: profile.headline || '',
              avatar_url: profile.profilePicture || null,
            };
          }
        } catch (e) {
          console.log('[LinkedIn Comments] Could not fetch author profile:', e);
        }
      }

      // Parse the date - LinkedIn returns timestamp in milliseconds
      let createdAt = new Date().toISOString();
      if (comment.created?.time) {
        // created.time is in milliseconds
        createdAt = new Date(comment.created.time).toISOString();
      } else if (comment.lastModified?.time) {
        createdAt = new Date(comment.lastModified.time).toISOString();
      }

      return {
        id: comment['$URN'] || comment.commentUrn || comment.id || '',
        text: comment.message?.text || comment.content?.message?.text || '',
        author: authorInfo,
        created_at: createdAt,
        likes_count: comment.likesSummary?.totalLikes || 0,
      };
    }));

    return comments;
  } catch (error) {
    console.error('[LinkedIn Comments] Error:', error);
    throw error; // Re-throw to let caller handle
  }
}

/**
 * Fetch member profile (name, headline, picture) from LinkedIn API
 */
async function fetchMemberProfile(
  accessToken: string,
  personUrn: string
): Promise<{ name: string; headline: string; profilePicture: string | null } | null> {
  try {
    // Extract person ID from URN
    const personId = personUrn.replace('urn:li:person:', '');

    // Use the /me endpoint or /people endpoint based on context
    // For other users, we can try the people endpoint
    const response = await fetch(
      `${LINKEDIN_API_BASE}/people/(id:${personId})?projection=(id,firstName,lastName,headline,profilePicture(displayImage~:playableStreams))`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'X-Restli-Protocol-Version': '2.0.0',
        },
      }
    );

    if (!response.ok) {
      // If people endpoint doesn't work, just return null
      console.log('[LinkedIn Profile] Could not fetch profile for:', personUrn);
      return null;
    }

    const data = await response.json();

    // Build full name from localized names
    const firstName = data.firstName?.localized?.en_US || data.firstName?.localized?.pt_BR || '';
    const lastName = data.lastName?.localized?.en_US || data.lastName?.localized?.pt_BR || '';
    const name = `${firstName} ${lastName}`.trim() || 'LinkedIn User';

    // Get headline
    const headline = data.headline?.localized?.en_US || data.headline?.localized?.pt_BR || '';

    // Get profile picture URL (largest available)
    let profilePicture: string | null = null;
    const displayImage = data.profilePicture?.['displayImage~']?.elements;
    if (displayImage && displayImage.length > 0) {
      // Get the largest image
      const largestImage = displayImage[displayImage.length - 1];
      profilePicture = largestImage?.identifiers?.[0]?.identifier || null;
    }

    return { name, headline, profilePicture };
  } catch (error) {
    console.log('[LinkedIn Profile] Error fetching profile:', error);
    return null;
  }
}

/**
 * Post a comment on a LinkedIn post using the official API v202505
 * Uses the /rest/socialActions endpoint (Community Management API)
 * Requires w_member_social_feed scope
 */
export async function postComment(
  accessToken: string,
  personUrn: string,
  postUrn: string,
  text: string
): Promise<{ success: boolean; error?: string }> {
  try {
    console.log('[LinkedIn Comments] Posting comment on:', postUrn);

    const encodedUrn = encodeURIComponent(postUrn);
    const response = await fetch(
      `${LINKEDIN_REST_API_BASE}/socialActions/${encodedUrn}/comments`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
          'LinkedIn-Version': '202505',
          'X-Restli-Protocol-Version': '2.0.0',
        },
        body: JSON.stringify({
          actor: personUrn,
          message: {
            text: text,
          },
        }),
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Comments] Failed to post comment:', response.status, errorText);
      return { success: false, error: errorText };
    }

    console.log('[LinkedIn Comments] Comment posted successfully');
    return { success: true };
  } catch (error: any) {
    console.error('[LinkedIn Comments] Error posting comment:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Get social actions (likes, comments count) for a post using API v202505
 */
export async function getPostSocialActions(
  accessToken: string,
  postUrn: string
): Promise<{ likes: number; comments: number } | null> {
  try {
    console.log('[LinkedIn Social] Fetching social actions for:', postUrn);

    const encodedUrn = encodeURIComponent(postUrn);
    const response = await fetch(
      `${LINKEDIN_REST_API_BASE}/socialActions/${encodedUrn}`,
      {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'LinkedIn-Version': '202505',
          'X-Restli-Protocol-Version': '2.0.0',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Social] Failed to get social actions:', response.status, errorText);
      return null;
    }

    const data = await response.json();
    return {
      likes: data.likesSummary?.totalLikes || 0,
      comments: data.commentsSummary?.totalFirstLevelComments || 0,
    };
  } catch (error) {
    console.error('[LinkedIn Social] Error:', error);
    return null;
  }
}

/**
 * Like a comment on LinkedIn using the Reactions API v202505
 * Uses the /rest/reactions endpoint (Community Management API)
 * Requires w_member_social_feed scope
 */
export async function likeComment(
  accessToken: string,
  personUrn: string,
  commentUrn: string
): Promise<{ success: boolean; error?: string }> {
  try {
    console.log('[LinkedIn Likes] Liking comment:', commentUrn);
    console.log('[LinkedIn Likes] Actor:', personUrn);

    // Using /rest/socialActions/{target}/likes endpoint
    // This endpoint is available in Community Management API with w_member_social_feed scope

    // POST /rest/socialActions/{target}/likes
    // Body: { actor: personUrn, object: activityUrn }

    // Parse the activity URN from comment URN
    // Format: urn:li:comment:(urn:li:activity:123,456) -> object: urn:li:activity:123
    let objectUrn = '';
    const match = commentUrn.match(/urn:li:comment:\(([^,]+),/);
    if (match && match[1]) {
      objectUrn = match[1];
    }
    console.log('[LinkedIn Likes] Object (activity):', objectUrn);

    // Encode the target URN for URL
    const encodeLinkedInUrn = (urn: string) => {
      return encodeURIComponent(urn)
        .replace(/:/g, '%3A')
        .replace(/\(/g, '%28')
        .replace(/\)/g, '%29')
        .replace(/,/g, '%2C');
    };

    const encodedTarget = encodeLinkedInUrn(commentUrn);
    const url = `${LINKEDIN_REST_API_BASE}/socialActions/${encodedTarget}/likes`;

    // Body with required fields
    const requestBody = {
      actor: personUrn,
      object: objectUrn,
    };

    console.log('[LinkedIn Likes] URL:', url);
    console.log('[LinkedIn Likes] Body:', JSON.stringify(requestBody));

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'LinkedIn-Version': '202505',
        'X-Restli-Protocol-Version': '2.0.0',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Likes] Failed to like comment:', response.status, errorText);
      return { success: false, error: errorText };
    }

    console.log('[LinkedIn Likes] Comment liked successfully!');
    return { success: true };
  } catch (error: any) {
    console.error('[LinkedIn Likes] Error liking comment:', error);
    return { success: false, error: error.message };
  }
}

/**
 * Unlike a comment on LinkedIn using the modern Reactions API
 */
export async function unlikeComment(
  accessToken: string,
  personUrn: string,
  commentUrn: string
): Promise<{ success: boolean; error?: string }> {
  try {
    console.log('[LinkedIn Reactions] Unliking comment:', commentUrn);
    console.log('[LinkedIn Reactions] Actor:', personUrn);

    // The MODERN Reactions API DELETE endpoint
    // DELETE /rest/reactions/(actor:{actorUrn},entity:{entityUrn})
    // The key is a compound key with actor and entity

    // LinkedIn requires certain characters to be encoded for path variables
    const encodeLinkedInUrn = (urn: string) => {
      return encodeURIComponent(urn)
        .replace(/:/g, '%3A')
        .replace(/\(/g, '%28')
        .replace(/\)/g, '%29')
        .replace(/,/g, '%2C');
    };

    // Build the compound key: (actor:{personUrn},entity:{commentUrn})
    const reactionKey = `(actor:${personUrn},entity:${commentUrn})`;
    const encodedKey = encodeLinkedInUrn(reactionKey);

    console.log('[LinkedIn Reactions] Endpoint: DELETE /rest/reactions/' + reactionKey);

    const response = await fetch(
      `${LINKEDIN_REST_API_BASE}/reactions/${encodedKey}`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'LinkedIn-Version': '202505',
          'X-Restli-Protocol-Version': '2.0.0',
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[LinkedIn Reactions] Failed to unlike comment:', response.status, errorText);
      return { success: false, error: errorText };
    }

    console.log('[LinkedIn Reactions] Comment unliked successfully!');
    return { success: true };
  } catch (error: any) {
    console.error('[LinkedIn Reactions] Error unliking comment:', error);
    return { success: false, error: error.message };
  }
}
