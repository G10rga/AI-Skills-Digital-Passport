import type { SkillCategory } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The three official BTU stamp shapes: triangle (AI Skill), rectangle (Applied), circle (Advanced). */
export function Stamp({ category, size = 72, className }: { category: SkillCategory; size?: number; className?: string }) {
  if (category === "AI Skill") {
    return (
      <div className={cn("relative inline-flex items-end justify-center", className)} style={{ width: size, height: size * 0.88 }}>
        <svg viewBox="0 0 100 88" className="absolute inset-0 h-full w-full">
          <polygon points="50,2 98,86 2,86" className="fill-stamp-skill" />
          <polygon points="50,14 88,80 12,80" fill="none" className="stroke-background/60" strokeWidth="1.2" strokeDasharray="3 2" />
        </svg>
        <div className="relative pb-[12%] text-center leading-[1.05] text-background" style={{ fontSize: size * 0.11 }}>
          <div className="font-display">AI<br />SKILL</div>
          <div style={{ fontSize: size * 0.075 }}>FOCUSED<br />LEARNING</div>
        </div>
      </div>
    );
  }
  if (category === "AI Applied Skill") {
    return (
      <div
        className={cn("inline-flex -rotate-6 flex-col justify-center border-2 border-dashed border-background/50 bg-stamp-applied px-2 text-center text-background outline outline-2 outline-stamp-applied", className)}
        style={{ width: size * 1.5, height: size * 0.5 }}
      >
        <div className="font-display leading-none" style={{ fontSize: size * 0.15 }}>AI APPLIED SKILL</div>
        <div className="leading-none" style={{ fontSize: size * 0.12 }}>APPLIED LEARNING</div>
      </div>
    );
  }
  return (
    <div
      className={cn("inline-flex flex-col items-center justify-center rounded-full bg-stamp-advanced text-center text-background ring-2 ring-stamp-advanced ring-offset-2 ring-offset-background", className)}
      style={{ width: size * 0.8, height: size * 0.8 }}
    >
      <div className="font-display leading-none" style={{ fontSize: size * 0.085 }}>AI<br />ADVANCED<br />SKILL</div>
      <div className="mt-0.5 leading-none opacity-80" style={{ fontSize: size * 0.06 }}>EXTENDED<br />ACADEMIC</div>
    </div>
  );
}

export const categoryLabel: Record<SkillCategory, string> = {
  "AI Skill": "Focused learning",
  "AI Applied Skill": "Applied learning",
  "AI Advanced Skill": "Extended academic learning",
};
