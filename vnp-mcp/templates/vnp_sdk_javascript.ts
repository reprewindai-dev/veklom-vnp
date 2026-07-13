/**
 * VNP Agent SDK - JavaScript/TypeScript
 * 
 * One-line API selection for LLM agents and applications.
 * 
 * INSTALL:
 *   npm install @vnp/sdk
 * 
 * USAGE:
 *   import { selectBestAPI } from '@vnp/sdk';
 *   
 *   const best = await selectBestAPI({
 *     candidates: ['openai', 'anthropic', 'together'],
 *     constraint: 'latency < 500ms'
 *   });
 *   
 *   // Use best.uri for API calls
 *   const response = await fetch(`${best.uri}/completions`, { ... });
 */

export enum UseCase {
  IMAGE_GENERATION = 'image_generation',
  TEXT_GENERATION = 'text_generation',
  TEXT_EMBEDDING = 'text_embedding',
  SPEECH_TO_TEXT = 'speech_to_text',
  TEXT_TO_SPEECH = 'text_to_speech',
  TRANSLATION = 'translation',
  PAYMENT_PROCESSING = 'payment_processing',
}

export interface VNPScore {
  apiId: string;
  apiName: string;
  compositeScore: number;
  confidenceInterval95: [number, number];
  p99LatencyMs: number;
  errorRatePct: number;
  availabilityPct: number;
  throughputRps: number;
  regionalScores: Record<string, number>;
  measurementCount: number;
  lastUpdated: string;
  vnpUri: string;
}

export interface APISelection {
  api: string;
  score: number;
  confidence: number;
  p99LatencyMs: number;
  errorRatePct: number;
  availabilityPct: number;
  uri: string;
  reason: string;
  alternatives: Array<{
    api: string;
    score: number;
    confidence: number;
  }>;
  selectedAt: string;
}

export interface SelectOptions {
  candidates: string[];
  useCase?: UseCase;
  constraint?: string;
  region?: string;
  preferCostEfficient?: boolean;
  fallbackChain?: number;
}

// ============================================================================
// CONFIGURATION
// ============================================================================

const VNP_API_URL = process.env.VNP_API_URL || 'https://api.vnp.io';
const VNP_GRAPHQL_URL = `${VNP_API_URL}/graphql`;
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// ============================================================================
// CACHE
// ============================================================================

class SimpleCache<T> {
  private cache = new Map<string, { data: T; expiry: number }>();

  set(key: string, value: T, ttlMs: number = CACHE_TTL_MS): void {
    this.cache.set(key, {
      data: value,
      expiry: Date.now() + ttlMs,
    });
  }

  get(key: string): T | null {
    const item = this.cache.get(key);
    if (!item) return null;
    if (Date.now() > item.expiry) {
      this.cache.delete(key);
      return null;
    }
    return item.data;
  }

  clear(): void {
    this.cache.clear();
  }
}

// ============================================================================
// VNP CLIENT
// ============================================================================

class VNPClient {
  private apiUrl: string;
  private graphqlUrl: string;
  private cache = new SimpleCache<VNPScore>();

  constructor(apiUrl: string = VNP_API_URL) {
    this.apiUrl = apiUrl;
    this.graphqlUrl = `${apiUrl}/graphql`;
  }

  async getScore(apiId: string): Promise<VNPScore | null> {
    // Check cache first
    const cached = this.cache.get(`score:${apiId}`);
    if (cached) {
      return cached;
    }

    const query = `
      query {
        score(api_id: "${apiId}") {
          apiId
          compositeScore
          confidence_interval_95
          dimensions {
            p99_latency { score }
            error_rate { score }
            availability { score }
            throughput { score }
          }
          regional_scores
          measurement_count
          computed_at
        }
      }
    `;

    try {
      const response = await fetch(this.graphqlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        console.error(`VNP API error: ${response.statusText}`);
        return null;
      }

      const result = await response.json();

      if (result.errors) {
        console.error(`VNP GraphQL error: ${result.errors[0].message}`);
        return null;
      }

      const data = result.data?.score;
      if (!data) {
        return null;
      }

      const score: VNPScore = {
        apiId: data.apiId,
        apiName: data.apiId.split(':').pop() || '',
        compositeScore: data.compositeScore,
        confidenceInterval95: data.confidence_interval_95,
        p99LatencyMs: data.dimensions.p99_latency.score,
        errorRatePct: data.dimensions.error_rate.score,
        availabilityPct: data.dimensions.availability.score,
        throughputRps: data.dimensions.throughput.score,
        regionalScores: data.regional_scores || {},
        measurementCount: data.measurement_count,
        lastUpdated: data.computed_at,
        vnpUri: `https://vnp.io/provider/${data.apiId}`,
      };

      this.cache.set(`score:${apiId}`, score);
      return score;
    } catch (error) {
      console.error(`Failed to fetch VNP score for ${apiId}:`, error);
      return null;
    }
  }

  async batchScores(apiIds: string[]): Promise<Map<string, VNPScore | null>> {
    const results = await Promise.all(apiIds.map((id) => this.getScore(id)));
    return new Map(apiIds.map((id, i) => [id, results[i]]));
  }

  clearCache(): void {
    this.cache.clear();
  }
}

// ============================================================================
// API SELECTOR
// ============================================================================

class APISelector {
  private client: VNPClient;
  private apiEndpoints: Record<string, string>;

  constructor(apiUrl: string = VNP_API_URL) {
    this.client = new VNPClient(apiUrl);
    this.apiEndpoints = this.loadApiEndpoints();
  }

  private loadApiEndpoints(): Record<string, string> {
    return {
      openai: 'https://api.openai.com/v1',
      anthropic: 'https://api.anthropic.com/v1',
      together: 'https://api.together.xyz/v1',
      groq: 'https://api.groq.com/v1',
      stripe: 'https://api.stripe.com/v1',
      twilio: 'https://api.twilio.com',
      cloudflare: 'https://api.cloudflare.com/client/v4',
      cohere: 'https://api.cohere.ai',
      replicate: 'https://api.replicate.com/v1',
    };
  }

  async select(options: SelectOptions): Promise<APISelection> {
    const {
      candidates,
      constraint,
      region,
      fallbackChain = 3,
    } = options;

    // Normalize to VNP IDs
    const apiIds = candidates.map((name) => `did:vnp:api:${name}`);

    // Fetch scores
    const scoreMap = await this.client.batchScores(apiIds);

    // Filter valid scores
    const validScores = new Map<string, VNPScore>();
    for (let i = 0; i < candidates.length; i++) {
      const score = scoreMap.get(apiIds[i]);
      if (score) {
        validScores.set(candidates[i], score);
      }
    }

    if (validScores.size === 0) {
      throw new Error(`No VNP scores found for candidates: ${candidates.join(', ')}`);
    }

    // Apply constraints
    const filtered = this.applyConstraints(validScores, constraint, region);
    const toRank = filtered.size > 0 ? filtered : validScores;

    // Rank by score
    const ranked = Array.from(toRank.entries()).sort((a, b) =>
      b[1].compositeScore - a[1].compositeScore
    );

    const [bestName, bestScore] = ranked[0];

    // Build alternatives
    const alternatives = ranked.slice(1, fallbackChain).map(([name, score]) => ({
      api: name,
      score: score.compositeScore,
      confidence: score.confidenceInterval95[1] - score.confidenceInterval95[0],
    }));

    return {
      api: bestName,
      score: bestScore.compositeScore,
      confidence: bestScore.confidenceInterval95[1] - bestScore.confidenceInterval95[0],
      p99LatencyMs: bestScore.p99LatencyMs,
      errorRatePct: bestScore.errorRatePct,
      availabilityPct: bestScore.availabilityPct,
      uri: this.apiEndpoints[bestName] || `https://api.${bestName}.com`,
      reason: `Best VNP score (${bestScore.compositeScore.toFixed(1)}) with ${bestScore.measurementCount.toLocaleString()} measurements`,
      alternatives,
      selectedAt: new Date().toISOString(),
    };
  }

  private applyConstraints(
    scores: Map<string, VNPScore>,
    constraint?: string,
    region?: string
  ): Map<string, VNPScore> {
    if (!constraint) {
      return scores;
    }

    const filtered = new Map<string, VNPScore>();
    for (const [name, score] of scores) {
      if (this.checkConstraint(score, constraint)) {
        filtered.set(name, score);
      }
    }

    return filtered;
  }

  private checkConstraint(score: VNPScore, constraint: string): boolean {
    // Parse simple constraints
    if (constraint.includes('latency') && constraint.includes('<')) {
      const match = constraint.match(/< *(\d+)/);
      if (match) {
        const maxLatency = parseInt(match[1], 10);
        return score.p99LatencyMs < maxLatency;
      }
    }

    if (constraint.includes('error_rate') && constraint.includes('<')) {
      const match = constraint.match(/< *(\d+\.?\d*)/);
      if (match) {
        const maxError = parseFloat(match[1]);
        return score.errorRatePct < maxError;
      }
    }

    if (constraint.includes('availability') && constraint.includes('>')) {
      const match = constraint.match(/> *(\d+\.?\d*)/);
      if (match) {
        const minAvail = parseFloat(match[1]);
        return score.availabilityPct > minAvail;
      }
    }

    return true;
  }
}

// ============================================================================
// CONVENIENCE FUNCTIONS
// ============================================================================

/**
 * One-liner API selection
 * 
 * EXAMPLE:
 *   const best = await selectBestAPI({
 *     candidates: ['openai', 'anthropic', 'together']
 *   });
 *   console.log(best.api); // "anthropic"
 */
export async function selectBestAPI(options: SelectOptions): Promise<APISelection> {
  const selector = new APISelector();
  return selector.select(options);
}

/**
 * One-liner score fetch
 * 
 * EXAMPLE:
 *   const score = await getAPIScore('openai');
 *   console.log(score.compositeScore); // 87.4
 */
export async function getAPIScore(apiName: string): Promise<VNPScore | null> {
  const client = new VNPClient();
  return client.getScore(`did:vnp:api:${apiName}`);
}

/**
 * Configure SDK
 */
export function configure(options: {
  apiUrl?: string;
  cacheTtlMs?: number;
}): void {
  if (options.apiUrl) {
    // Would require refactoring to make this global
    console.warn('Configuring API URL requires re-creating selector instances');
  }
}

// ============================================================================
// EXPORTS
// ============================================================================

export { APISelector, VNPClient };
