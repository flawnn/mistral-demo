import { Mistral } from "@mistralai/mistralai";
import { z } from "zod";
import { env } from "~/env";
import { AI_CONFIG } from "./config";

const mistral = new Mistral({
  apiKey: env.MISTRAL_API_KEY,
});

// Schema for findings synthesis
export const FindingsSynthesisSchema = z.object({
  summary: z.string(),
  keyFindings: z.array(z.string()),
  trend: z.enum(["increasing", "decreasing", "stable", "fluctuating"]),
  confidence: z.number(),
});

export type FindingsSynthesis = z.infer<typeof FindingsSynthesisSchema>;

interface MistralChatOptions {
  systemPrompt: string;
  userPrompt: string;
  temperature?: number;
}

/**
 *  Generate structured JSON output using Mistral AI SDK with schema validation
 */
export const generateStructuredOutput = async <T>(
  options: MistralChatOptions,
  schema: z.ZodSchema<T>,
): Promise<T> => {
  const response = await mistral.chat.complete({
    model: AI_CONFIG.model,
    temperature: options.temperature ?? AI_CONFIG.temperature,
    messages: [
      {
        role: "system",
        content: options.systemPrompt,
      },
      {
        role: "user",
        content: options.userPrompt,
      },
    ],
    responseFormat: {
      type: "json_object",
    },
  });

  const content = response.choices?.[0]?.message?.content;

  if (!content) {
    throw new Error("No response content from Mistral");
  }

  const contentString =
    typeof content === "string" ? content : JSON.stringify(content);
  const parsed: unknown = JSON.parse(contentString);
  return schema.parse(parsed);
};

/**
 * Helper to convert Zod schema to JSON schema description for prompts
 */
export const zodSchemaToPromptDescription = <T>(
  schema: z.ZodSchema<T>,
): string => {
  if (!(schema instanceof z.ZodObject)) {
    return "";
  }

  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment, @typescript-eslint/no-unsafe-call
  const shape = schema._def.shape() as Record<string, z.ZodTypeAny>;
  // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
  const fields = Object.entries(shape).map(([key, value]) => {
    const description = value.description ?? "";
    return `- ${key}: ${description}`;
  });

  return fields.join("\n");
};
