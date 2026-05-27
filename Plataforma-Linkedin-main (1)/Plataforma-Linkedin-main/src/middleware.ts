import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Security headers to add to all responses
const securityHeaders = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'X-XSS-Protection': '1; mode=block',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

// Paths that don't require authentication
const publicPaths = [
  '/',
  '/auth/callback',
  '/api/auth/callback',
  '/api/linkedin/auth',      // LinkedIn OAuth start
  '/api/linkedin/callback',  // LinkedIn OAuth callback
];

// Paths that are API routes requiring authentication
const protectedApiPaths = [
  '/api/posts',
  '/api/onboarding',
  '/api/user',
  '/api/apify',
  '/api/analyze-past-posts',
  '/api/linkedin/status',    // Only status needs auth
  '/api/linkedin/profile',   // Only profile needs auth
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  
  // Add security headers to all responses
  const response = NextResponse.next();
  
  Object.entries(securityHeaders).forEach(([key, value]) => {
    response.headers.set(key, value);
  });

  // Check if it's an API route that requires authentication
  const isProtectedApi = protectedApiPaths.some(path => pathname.startsWith(path));
  
  if (isProtectedApi) {
    // Check for Supabase auth cookie (basic check, actual auth is done in routes)
    const authCookie = request.cookies.get('sb-access-token') || 
                       request.cookies.get('supabase-auth-token') ||
                       request.cookies.getAll().find(c => c.name.includes('auth-token'));
    
    // If no auth cookie found, check for Authorization header
    const authHeader = request.headers.get('authorization');
    
    if (!authCookie && !authHeader) {
      // This is a basic check - actual authentication is done in the route handlers
      // We just want to fail fast for obviously unauthenticated requests
      console.log('[middleware] No auth found for protected route:', pathname);
    }
  }

  // CORS headers for API routes
  if (pathname.startsWith('/api/')) {
    const origin = request.headers.get('origin') || '';
    const allowedOrigins = [
      process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000',
      'http://localhost:3000',
      'http://localhost:3001',
    ];

    // In production, only allow same origin or configured origins
    if (process.env.NODE_ENV === 'production') {
      if (origin && !allowedOrigins.includes(origin)) {
        response.headers.set('Access-Control-Allow-Origin', allowedOrigins[0]);
      } else if (origin) {
        response.headers.set('Access-Control-Allow-Origin', origin);
      }
    } else {
      // In development, be more permissive
      response.headers.set('Access-Control-Allow-Origin', origin || '*');
    }

    response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
    response.headers.set('Access-Control-Allow-Credentials', 'true');
    response.headers.set('Access-Control-Max-Age', '86400');

    // Handle preflight requests
    if (request.method === 'OPTIONS') {
      return new NextResponse(null, { status: 200, headers: response.headers });
    }
  }

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (public directory)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
