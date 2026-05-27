import { NextResponse } from 'next/server';
import { validateGoogleCredentials } from '@/lib/google-auth';

export const dynamic = 'force-dynamic';

/**
 * Health Check API
 * GET /api/health
 * 
 * Returns the health status of the application and its dependencies
 */
export async function GET() {
  const checks: Record<string, { status: 'ok' | 'error' | 'warning'; message?: string }> = {};
  let overallStatus: 'healthy' | 'degraded' | 'unhealthy' = 'healthy';

  // Check environment variables
  const requiredEnvVars = [
    'NEXT_PUBLIC_SUPABASE_URL',
    'NEXT_PUBLIC_SUPABASE_ANON_KEY',
    'OPENAI_API_KEY',
  ];

  const optionalEnvVars = [
    'APIFY_TOKEN',
    'VERTEX_PROJECT_ID',
  ];

  // Check required env vars
  const missingRequired = requiredEnvVars.filter(v => !process.env[v]);
  if (missingRequired.length > 0) {
    checks.environment = {
      status: 'error',
      message: `Missing required: ${missingRequired.join(', ')}`,
    };
    overallStatus = 'unhealthy';
  } else {
    const missingOptional = optionalEnvVars.filter(v => !process.env[v]);
    if (missingOptional.length > 0) {
      checks.environment = {
        status: 'warning',
        message: `Missing optional: ${missingOptional.join(', ')}`,
      };
      if (overallStatus === 'healthy') overallStatus = 'degraded';
    } else {
      checks.environment = { status: 'ok' };
    }
  }

  // Check Google Cloud credentials
  try {
    const googleResult = await validateGoogleCredentials();
    if (googleResult.valid) {
      checks.googleCloud = {
        status: 'ok',
        message: `Project: ${googleResult.projectId}`,
      };
    } else {
      checks.googleCloud = {
        status: 'error',
        message: googleResult.error || 'Invalid credentials',
      };
      overallStatus = 'unhealthy';
    }
  } catch (error: any) {
    checks.googleCloud = {
      status: 'error',
      message: error.message || 'Failed to validate',
    };
    overallStatus = 'unhealthy';
  }

  // Check OpenAI (simple validation - just check if key format is valid)
  const openaiKey = process.env.OPENAI_API_KEY;
  if (openaiKey && openaiKey.startsWith('sk-')) {
    checks.openai = { status: 'ok' };
  } else {
    checks.openai = {
      status: 'error',
      message: 'Invalid or missing API key',
    };
    overallStatus = 'unhealthy';
  }

  // Check Apify
  const apifyToken = process.env.APIFY_TOKEN || process.env.APIFY_API_TOKEN;
  if (apifyToken) {
    checks.apify = { status: 'ok' };
  } else {
    checks.apify = {
      status: 'warning',
      message: 'Token not configured (LinkedIn scraping disabled)',
    };
    if (overallStatus === 'healthy') overallStatus = 'degraded';
  }

  // Memory usage
  const memUsage = process.memoryUsage();
  const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);
  const heapTotalMB = Math.round(memUsage.heapTotal / 1024 / 1024);
  checks.memory = {
    status: heapUsedMB > heapTotalMB * 0.9 ? 'warning' : 'ok',
    message: `${heapUsedMB}MB / ${heapTotalMB}MB`,
  };

  return NextResponse.json({
    status: overallStatus,
    timestamp: new Date().toISOString(),
    version: process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0',
    uptime: Math.round(process.uptime()),
    checks,
  }, {
    status: overallStatus === 'unhealthy' ? 503 : 200,
  });
}
