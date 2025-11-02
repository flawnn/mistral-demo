/** biome-ignore-all lint/complexity/noStaticOnlyClass: <explanation> */
import {
  type FindingsSynthesis,
  FindingsSynthesisSchema,
  generateStructuredOutput,
  zodSchemaToPromptDescription,
} from "~/lib/ai-sdk/client";
import {
  KEY_PLACES,
  type LocationQuery,
  LocationQuerySchema,
} from "~/lib/ai-sdk/types";

interface TimeSeriesDataPoint {
  timestamp: number;
  value: number;
}

const SYNTHESIS_SYSTEM_INSTRUCTIONS = `You are an expert analyst specializing in satellite imagery analysis and time series data interpretation.
Your task is to analyze time series data from satellite imagery and provide insightful findings.

Consider the following aspects in your analysis:
1. Identify clear patterns or trends in the data
2. Look for seasonal variations or cycles
3. Note any significant anomalies or changes
4. Consider the geographical context and object type
5. Provide confidence level based on data quality and pattern clarity

Your analysis should be:
- Clear and concise
- Backed by the data
- Relevant to the location and object type
- Actionable where possible

CRITICAL: You MUST respond with ONLY a valid JSON object. Do not include any text outside the JSON.

Required JSON structure:
{
  "summary": "string - A concise summary of findings",
  "keyFindings": ["string array - List of key observations"],
  "trend": "MUST be exactly one of: 'increasing', 'decreasing', 'stable', or 'fluctuating'",
  "confidence": "number between 0 and 1 (NOT a string, use 0.5 for uncertain)"
}

IMPORTANT RULES:
- "trend" MUST be one of these 4 values: "increasing", "decreasing", "stable", "fluctuating"
- If unsure about trend, use "stable" 
- "confidence" MUST be a number (e.g., 0.7), NOT a string (e.g., "0.7")
- If data is insufficient, use "stable" for trend and 0.3 for confidence

Example valid response:
{
  "summary": "The data shows a gradual increase in detected objects over time",
  "keyFindings": ["10 objects detected initially", "25 objects detected by end of period"],
  "trend": "increasing",
  "confidence": 0.7
}`;

const LOCATION_QUERY_SYSTEM_INSTRUCTIONS = `You are a location query parser. Extract location information from user queries.

Available key places and their coordinates are:
${Object.entries(KEY_PLACES)
  .map(([place, coords]) => `- ${place}: ${coords}`)
  .join("\n")}

Rules:
1. If a user mentions a key place, use its exact coordinates
2. If a user provides coordinates directly (in any format), convert them to "lat,lon"
3. If a location is neither a key place nor coordinates, return it if you know it
4. The type parameter must be extracted from context
5. If radius is mentioned (in any unit), convert it to meters
6. If required parameters are missing or invalid, set the error field with a message

Examples:
- "Find restaurants near EPFL" -> { "coordinates": "46.518437,6.561171", "type": "restaurant", "radius": null, "error": null }
- "Show cafes within 500m of 47.37,8.54" -> { "coordinates": "47.37,8.54", "type": "cafe", "radius": 500, "error": null }
- "List hotels in Paris" -> { "coordinates": "0,0", "type": "hotel", "radius": null, "error": "Location 'Paris' is not in the list of key places" }

You must respond with a valid JSON object matching this structure:
${zodSchemaToPromptDescription(LocationQuerySchema)}

Output format: JSON object with the above fields`;

export class AIService {
  /**
   * Evaluates a location query and returns structured data
   */
  static async evaluateQuery(query: string): Promise<LocationQuery> {
    try {
      return await generateStructuredOutput(
        {
          systemPrompt: LOCATION_QUERY_SYSTEM_INSTRUCTIONS,
          userPrompt: `User query: ${query}`,
        },
        LocationQuerySchema,
      );
    } catch (error) {
      console.error("Error in AI query evaluation:", error);
      return {
        error: "Failed to process location query",
        coordinates: "0,0",
        type: "unknown",
        radius: null,
      };
    }
  }

  /**
   * Synthesizes findings from time series data
   */
  static async synthesizeFindings(
    timeSeriesData: TimeSeriesDataPoint[],
    coordinates: { latitude: number; longitude: number },
    type: string,
  ): Promise<FindingsSynthesis> {
    try {
      const formattedData = timeSeriesData.map((point) => ({
        date: new Date(point.timestamp).toISOString().split("T")[0],
        value: point.value,
      }));

      const userPrompt = `
Location: ${coordinates.latitude}, ${coordinates.longitude}
Object Type: ${type}
Time Series Data: ${JSON.stringify(formattedData, null, 2)}

Analyze this data and provide structured insights.`;

      return await generateStructuredOutput(
        {
          systemPrompt: SYNTHESIS_SYSTEM_INSTRUCTIONS,
          userPrompt,
        },
        FindingsSynthesisSchema,
      );
    } catch (error) {
      console.error("Error in findings synthesis:", error);
      return {
        summary: "Failed to synthesize findings from the data",
        keyFindings: ["Error occurred during analysis"],
        trend: "stable",
        confidence: 0,
      };
    }
  }
}
