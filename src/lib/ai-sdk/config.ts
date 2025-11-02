// Check the README.md for further background on choices

export const SYNTHESIS_AI_CONFIG = {
  model: "mistral-small-latest",
  temperature: 0.7,
} as const;

export const QUERY_EXTRACTION_AI_CONFIG = {
  model: "mistral-small-latest",
  temperature: 0.3,
} as const;
