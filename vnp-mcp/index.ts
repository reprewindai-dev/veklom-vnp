import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATES_DIR = path.join(__dirname, "templates");

const server = new Server(
  {
    name: "vnp-mcp",
    version: "0.1.5",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "vnp_onboard_api",
        description: "Onboards a local API repository to the Veklom Nexus Protocol (VNP). It returns the language-specific SDK content and integration instructions for the agent to inject.",
        inputSchema: {
          type: "object",
          properties: {
            language: {
              type: "string",
              description: "The language of the target repository (python or typescript)",
              enum: ["python", "typescript"]
            },
          },
          required: ["language"],
        },
      },
      {
        name: "vnp_generate_badge",
        description: "Evaluates an API on the live VNP mesh and generates a dynamic SVG/Markdown badge for the README.",
        inputSchema: {
          type: "object",
          properties: {
            api_id: {
              type: "string",
              description: "The unique identifier of the API (e.g., openai-api)"
            },
          },
          required: ["api_id"],
        },
      },
      {
        name: "vnp_get_leaderboard",
        description: "Fetches the current leaderboard of API performance scores from the live VNP mesh.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      }
    ],
  };
});

// Implement tools
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    if (name === "vnp_onboard_api") {
      const language = args?.language as string;
      const fileName = language === "python" ? "vnp_sdk_python.py" : "vnp_sdk_javascript.ts";
      const sdkPath = path.join(TEMPLATES_DIR, fileName);
      
      if (!fs.existsSync(sdkPath)) {
        throw new Error(`SDK Template ${fileName} not found at ${sdkPath}`);
      }

      const sdkContent = fs.readFileSync(sdkPath, "utf-8");

      const instructions = language === "python" 
        ? "1. Save the above content to `vnp_sdk.py`.\n2. In the FastAPI main file, initialize the SDK: `from vnp_sdk import APISelector`\n3. Ensure port 8089 is accessible."
        : "1. Save the above content to `vnp_sdk.ts`.\n2. Import the APISelector into the Node.js/Express routes.\n3. Ensure port 8089 is accessible.";

      return {
        content: [
          {
            type: "text",
            text: `=== VNP ${language.toUpperCase()} SDK ===\n\n${sdkContent}\n\n=== INTEGRATION INSTRUCTIONS ===\n\n${instructions}`,
          },
        ],
      };
    }

    if (name === "vnp_generate_badge") {
      const api_id = args?.api_id as string;
      const LIVE_URL = "http://5.78.135.11:8089";
      
      // Attempt to fetch live score if backend is reachable
      let scoreData = null;
      try {
        const response = await fetch(`${LIVE_URL}/api/v1/badge/${api_id}.json`, { signal: AbortSignal.timeout(3000) });
        if (response.ok) {
          scoreData = await response.json();
        }
      } catch (err) {
        console.error("Could not reach live VNP backend for badge data");
      }

      const badgeUrl = `${LIVE_URL}/api/v1/badge/${api_id}.svg`;
      const markdownBadge = `[![VNP Score](${badgeUrl})](https://vnp.veklom.com/provider/${api_id})`;

      let outputText = `Here is the dynamic VNP Markdown Badge for the README:\n\n\`\`\`markdown\n${markdownBadge}\n\`\`\`\n\n`;
      if (scoreData && scoreData.score) {
        outputText += `Live Score verified at: ${scoreData.score.toFixed(1)} (${scoreData.label})`;
      } else {
        outputText += `Live score could not be fetched, but the badge will resolve once the API is actively measured.`;
      }

      return {
        content: [{ type: "text", text: outputText }],
      };
    }

    if (name === "vnp_get_leaderboard") {
      const LIVE_URL = "http://5.78.135.11:8089";
      
      try {
        const response = await fetch(`${LIVE_URL}/api/v1/scores`, { signal: AbortSignal.timeout(3000) });
        if (!response.ok) throw new Error("Failed to fetch scores");
        const data = await response.json() as any;
        
        let leaderboard = "🏆 VNP Global Leaderboard\n==========================\n\n";
        const scores = Object.entries(data.scores || {}).map(([api, info]: any) => ({
          api,
          score: info.composite_score
        })).sort((a, b) => b.score - a.score);

        scores.forEach((s, i) => {
          leaderboard += `${i+1}. ${s.api}: ${s.score.toFixed(1)}\n`;
        });

        return { content: [{ type: "text", text: leaderboard }] };
      } catch (err) {
        return {
          content: [{ type: "text", text: "The VNP Standalone service is currently unreachable or syncing. Please try again later." }],
        };
      }
    }

    throw new Error(`Unknown tool: ${name}`);
  } catch (error: any) {
    return {
      content: [{ type: "text", text: `Error: ${error.message}` }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
