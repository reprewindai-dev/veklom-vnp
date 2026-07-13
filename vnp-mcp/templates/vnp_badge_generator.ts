/**
 * VNP Conformance Badge Generator
 * 
 * Generates embeddable SVG badges showing VNP score and certification level
 * 
 * ENDPOINTS:
 *   GET /v1/badge/{api-id}.svg → Returns SVG badge
 *   GET /v1/badge/{api-id}.json → Returns JSON with score data
 * 
 * EXAMPLES:
 *   <img src="https://vnp.io/badge/stripe-payments.svg" alt="VNP Certified" />
 *   ![VNP Badge](https://vnp.io/badge/openai-api.svg)
 * 
 * CERTIFICATIONS:
 *   Gold:   score >= 85
 *   Silver: score >= 75
 *   Bronze: score >= 65
 *   None:   score < 65
 */

import express, { Request, Response } from 'express';

// ============================================================================
// CONFIGURATION
// ============================================================================

const CERTIFICATIONS = {
  GOLD: { threshold: 85, color: '#FFD700', label: 'Gold' },
  SILVER: { threshold: 75, color: '#C0C0C0', label: 'Silver' },
  BRONZE: { threshold: 65, color: '#CD7F32', label: 'Bronze' },
  NONE: { threshold: 0, color: '#999999', label: 'Measured' },
};

const CACHE_MAX_AGE_SECONDS = 3600; // 1 hour

// ============================================================================
// BADGE SVG GENERATOR
// ============================================================================

function getCertification(score: number) {
  if (score >= CERTIFICATIONS.GOLD.threshold) return CERTIFICATIONS.GOLD;
  if (score >= CERTIFICATIONS.SILVER.threshold) return CERTIFICATIONS.SILVER;
  if (score >= CERTIFICATIONS.BRONZE.threshold) return CERTIFICATIONS.BRONZE;
  return CERTIFICATIONS.NONE;
}

function generateBadgeSVG(
  apiName: string,
  score: number,
  certification: typeof CERTIFICATIONS.GOLD
): string {
  const scoreStr = score.toFixed(1);
  const width = 200;
  const height = 28;
  const textY = 19;

  return `
    <svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <defs>
        <linearGradient id="badgeGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" style="stop-color:${certification.color};stop-opacity:1" />
          <stop offset="100%" style="stop-color:#333;stop-opacity:1" />
        </linearGradient>
        <filter id="shadow">
          <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.3"/>
        </filter>
      </defs>
      
      <!-- Background -->
      <rect width="${width}" height="${height}" fill="#222" rx="3" filter="url(#shadow)" />
      
      <!-- Score badge -->
      <rect x="2" y="2" width="70" height="24" fill="url(#badgeGradient)" rx="2" />
      
      <!-- Certification badge -->
      <rect x="76" y="2" width="122" height="24" fill="#1a1a1a" rx="2" stroke="${certification.color}" stroke-width="1" />
      
      <!-- Score text -->
      <text x="37" y="${textY}" font-family="Arial, sans-serif" font-size="14" font-weight="bold" text-anchor="middle" fill="white">
        ${scoreStr}
      </text>
      
      <!-- VNP Certified text -->
      <text x="138" y="${textY}" font-family="Arial, sans-serif" font-size="12" font-weight="bold" text-anchor="middle" fill="${certification.color}">
        VNP ${certification.label}
      </text>
      
      <!-- Click link -->
      <a href="https://vnp.io/provider/${apiName}" target="_blank">
        <rect width="${width}" height="${height}" fill="transparent" cursor="pointer" />
      </a>
    </svg>
  `.trim();
}

function generateBadgeJSON(
  apiId: string,
  score: number,
  confidence: [number, number],
  certification: typeof CERTIFICATIONS.GOLD
) {
  return {
    api_id: apiId,
    api_name: apiId.split(':').pop(),
    score: score,
    confidence_interval: confidence,
    certification: certification.label,
    certification_color: certification.color,
    certified: score >= CERTIFICATIONS.GOLD.threshold,
    badge_url: `https://vnp.io/v1/badge/${apiId}.svg`,
    provider_dashboard: `https://vnp.io/provider/${apiId}`,
    generated_at: new Date().toISOString(),
  };
}

// ============================================================================
// EXPRESS ENDPOINTS
// ============================================================================

export function setupBadgeRoutes(app: express.Application) {
  /**
   * GET /v1/badge/{api-id}.svg
   * 
   * Returns embeddable SVG badge showing score and certification level
   */
  app.get('/v1/badge/:apiId.svg', async (req: Request, res: Response) => {
    try {
      const apiId = req.params.apiId;
      
      // Fetch score from GraphQL
      const score = await fetchScore(apiId);
      
      if (!score) {
        // Return "not measured" badge
        const badgeSvg = generateBadgeSVG(
          apiId,
          0,
          CERTIFICATIONS.NONE
        );
        
        res.setHeader('Content-Type', 'image/svg+xml');
        res.setHeader('Cache-Control', `public, max-age=300`); // 5 min cache
        res.setHeader('X-Content-Type-Options', 'nosniff');
        return res.send(badgeSvg);
      }
      
      const certification = getCertification(score.compositeScore);
      const badgeSvg = generateBadgeSVG(
        apiId,
        score.compositeScore,
        certification
      );
      
      res.setHeader('Content-Type', 'image/svg+xml');
      res.setHeader('Cache-Control', `public, max-age=${CACHE_MAX_AGE_SECONDS}`);
      res.setHeader('X-Content-Type-Options', 'nosniff');
      res.send(badgeSvg);
    } catch (error) {
      console.error('Badge generation error:', error);
      res.status(500).send('Error generating badge');
    }
  });

  /**
   * GET /v1/badge/{api-id}.json
   * 
   * Returns JSON representation of badge/score
   */
  app.get('/v1/badge/:apiId.json', async (req: Request, res: Response) => {
    try {
      const apiId = req.params.apiId;
      
      const score = await fetchScore(apiId);
      if (!score) {
        return res.status(404).json({ error: 'API not found in VNP' });
      }
      
      const certification = getCertification(score.compositeScore);
      const badge = generateBadgeJSON(
        apiId,
        score.compositeScore,
        score.confidenceInterval95,
        certification
      );
      
      res.setHeader('Cache-Control', `public, max-age=${CACHE_MAX_AGE_SECONDS}`);
      res.json(badge);
    } catch (error) {
      console.error('Badge JSON error:', error);
      res.status(500).json({ error: 'Error generating badge' });
    }
  });

  /**
   * GET /v1/badge/status
   * 
   * Returns badge generator status
   */
  app.get('/v1/badge/status', (req: Request, res: Response) => {
    res.json({
      status: 'ok',
      service: 'VNP Badge Generator',
      version: '0.1.5',
      certifications: Object.entries(CERTIFICATIONS).reduce(
        (acc, [key, value]) => ({
          ...acc,
          [key.toLowerCase()]: { threshold: value.threshold, color: value.color }
        }),
        {}
      ),
    });
  });
}

// ============================================================================
// GRAPHQL SCORE FETCH
// ============================================================================

async function fetchScore(apiId: string): Promise<{
  compositeScore: number;
  confidenceInterval95: [number, number];
} | null> {
  const query = `
    query {
      score(api_id: "${apiId}") {
        compositeScore
        confidence_interval_95
      }
    }
  `;

  try {
    const response = await fetch(
      process.env.GRAPHQL_ENDPOINT || 'http://localhost:4000/graphql',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      }
    );

    if (!response.ok) return null;
    
    const result = await response.json();
    if (result.errors) {
      console.warn(`GraphQL error for ${apiId}:`, result.errors[0].message);
      return null;
    }

    const score = result.data?.score;
    return score ? {
      compositeScore: score.compositeScore,
      confidenceInterval95: score.confidence_interval_95,
    } : null;
  } catch (error) {
    console.error(`Failed to fetch score for ${apiId}:`, error);
    return null;
  }
}

// ============================================================================
// EXPORT
// ============================================================================

export { generateBadgeSVG, generateBadgeJSON, getCertification };
