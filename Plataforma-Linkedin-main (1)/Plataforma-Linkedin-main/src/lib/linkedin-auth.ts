'use client';

/**
 * Extracts the LinkedIn li_at cookie value from the browser
 * This is called after OAuth callback to get the user's session cookie
 */
export function getLinkedInCookie(): string | null {
  if (typeof document === 'undefined') return null;

  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'li_at') {
      return decodeURIComponent(value);
    }
  }
  return null;
}

/**
 * Sends the LinkedIn li_at cookie to the backend to be stored
 */
export async function storeLinkedInCookie() {
  const liAtCookie = getLinkedInCookie();

  if (!liAtCookie) {
    console.warn('LinkedIn li_at cookie not found');
    return false;
  }

  try {
    const response = await fetch('/api/auth/store-linkedin-cookie', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ liAtCookie }),
    });

    if (!response.ok) {
      console.error('Failed to store LinkedIn cookie:', await response.text());
      return false;
    }

    return true;
  } catch (error) {
    console.error('Error storing LinkedIn cookie:', error);
    return false;
  }
}
