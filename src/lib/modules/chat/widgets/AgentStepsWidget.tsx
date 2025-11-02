import { AnimatePresence, motion } from "framer-motion";
import type React from "react";
import { cn } from "~/lib/utils";

export const ANALYSIS_STEPS = {
  ANALYZE_QUERY: "Analyze Query",
  GET_SATELLITE_IMAGES: "Get Satellite Images",
  ANALYZE_OBJECT_TYPE: "Analyze Object",
  PROCESS_IMAGES: "Process Images",
  COMPLETE: "Complete",
} as const;

export type AnalysisStep = keyof typeof ANALYSIS_STEPS;

interface AgentStepsWidgetProps {
  currentStep: AnalysisStep;
  className?: string;
}

const StepItem: React.FC<{
  step: AnalysisStep;
  isActive: boolean;
  isPassed: boolean;
}> = ({ step, isActive, isPassed }) => {
  return (
    <motion.div
      className={cn(
        "relative flex items-center gap-3 py-2 transition-colors",
        isActive
          ? "text-primary"
          : isPassed
            ? "text-muted-foreground"
            : "text-muted-foreground/60",
      )}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
    >
      {/* Step indicator dot */}
      <div
        className={cn(
          "h-2 w-2 rounded-full transition-colors",
          isActive
            ? "bg-primary"
            : isPassed
              ? "bg-muted-foreground"
              : "bg-muted-foreground/60",
        )}
      />

      {/* Step text */}
      <span className="text-sm font-medium">{ANALYSIS_STEPS[step]}</span>

      {/* Active step shimmer effect */}

      {isActive && (
        <motion.div
          className="absolute inset-0 rounded-md blur-sm"
          style={{
            background:
              "linear-gradient(to right, transparent, hsl(var(--primary) / 0.15), transparent)",
          }}
          initial={{ x: "-100%", opacity: 0.6 }}
          animate={{ x: "100%", opacity: 1 }}
          transition={{
            repeat: Infinity,
            duration: 1.6,
            ease: "easeInOut",
          }}
        />
      )}
    </motion.div>
  );
};

export const AgentStepsWidget: React.FC<AgentStepsWidgetProps> = ({
  currentStep,
  className,
}) => {
  // Get ordered array of steps
  const steps = Object.keys(ANALYSIS_STEPS) as AnalysisStep[];
  const currentStepIndex = steps.indexOf(currentStep);
  const isComplete = currentStep === "COMPLETE";

  return (
    <div className={cn("flex flex-col space-y-1", className)}>
      <AnimatePresence mode="sync">
        {steps.map((step, index) => (
          <StepItem
            key={step}
            step={step}
            isActive={!isComplete && step === currentStep}
            isPassed={isComplete || index < currentStepIndex}
          />
        ))}
      </AnimatePresence>
    </div>
  );
};
