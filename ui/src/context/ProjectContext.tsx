import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

type ProjectContextValue = {
  project: string;
  setProject: (value: string) => void;
};

const DEFAULT_PROJECT = "context_engine";
const STORAGE_KEY = "context-engine-project";

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

function readStoredProject(): string {
  if (typeof window === "undefined") {
    return DEFAULT_PROJECT;
  }
  return window.localStorage.getItem(STORAGE_KEY) || DEFAULT_PROJECT;
}

export function ProjectProvider({ children }: { children: ReactNode }): JSX.Element {
  const [project, setProjectState] = useState<string>(() => readStoredProject());

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, project);
    }
  }, [project]);

  const setProject = useCallback((value: string) => {
    const next = value.trim() || DEFAULT_PROJECT;
    setProjectState(next);
  }, []);

  const value = useMemo<ProjectContextValue>(() => ({ project, setProject }), [project, setProject]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useProject must be used within ProjectProvider");
  }
  return ctx;
}

export { DEFAULT_PROJECT };
